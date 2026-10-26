"""开处方接口（POST /api/prescriptions）与药品列表（GET /api/drugs）。

三条硬规则落实位置：
- 【事务】：第 72 行 BEGIN IMMEDIATE 开启；校验 reg_id / 药品、逐条按 drugs.price_cents
  现算 unit_price_cents 与 amount_cents、写入 prescription_items、汇总 total_amount_cents
  写入 prescriptions（status='待收费'）全部在同一事务的 try 块内（约第 76~124 行），
  任一步失败在 except 中 conn.rollback()（第 147 行）后返回错误；
  BEGIN IMMEDIATE 失败返回 503（第 73~74 行）。
- 【金额】：请求体 PrescriptionCreateIn 只含 reg_id / diagnosis /
  items[{drug_id,quantity}]，不含任何金额字段（见 schemas.PrescriptionItemIn，
  第 23~27 行）；金额在事务内从药品档案现算：
  amount_cents = quantity * drugs.price_cents（第 114 行），
  total_amount_cents = SUM(amount_cents)（第 145 行 UPDATE）。
- 【库存】：本接口不扣库存（扣库存在收费阶段 /api/pay 完成，见 payment.py 硬规则3）。
  此处仅做药品 status='启用' 的业务校验（停用返回 400，第 51~54 行；
  事务内再次校验，第 84~87 行）。
"""

import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from schemas import PrescriptionCreateIn, PrescriptionOut, PrescriptionItemOut
from security import require_permission
from services.pricing import compute_line_amount

router = APIRouter(prefix="/api", tags=["处方"])


def _build_prescription_no() -> str:
    # 带微秒：只用秒级时间戳时，同一秒内开两张处方会撞 prescriptions.prescription_no 的 UNIQUE
    return f"CF{datetime.now():%Y%m%d%H%M%S%f}"


@router.post("/prescriptions", status_code=201, response_model=PrescriptionOut)
def create_prescription(
    req: PrescriptionCreateIn,
    user: dict = Depends(require_permission("prescription:create")),
) -> dict:
    from main import get_connection

    conn = get_connection()
    conn.isolation_level = None
    try:
        # 事务外预校验（只读）：挂号单存在且为候诊
        reg = conn.execute(
            "SELECT reg_id, patient_id, doctor_id, status "
            "FROM reg_orders WHERE reg_id = ?",
            (req.reg_id,),
        ).fetchone()
        if reg is None:
            raise HTTPException(status_code=404, detail="挂号单不存在")
        if reg["status"] != "候诊":
            raise HTTPException(
                status_code=400,
                detail=f"挂号单当前状态为“{reg['status']}”，不可开处方",
            )

        # 预校验药品存在且启用（只读）
        drug_cache: dict = {}
        for it in req.items:
            drug = conn.execute(
                "SELECT drug_id, drug_code, generic_name, spec, unit, price_cents, status "
                "FROM drugs WHERE drug_id = ?",
                (it.drug_id,),
            ).fetchone()
            if drug is None:
                raise HTTPException(status_code=404, detail=f"药品 {it.drug_id} 不存在")
            if drug["status"] != "启用":
                raise HTTPException(
                    status_code=400,
                    detail=f"药品“{drug['generic_name']}”已停用，不可开方",
                )
            drug_cache[it.drug_id] = drug

        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise HTTPException(status_code=503, detail="系统繁忙，请稍后重试") from exc

        try:
            # 事务内复检挂号单
            reg = conn.execute(
                "SELECT reg_id, patient_id, doctor_id, status "
                "FROM reg_orders WHERE reg_id = ?",
                (req.reg_id,),
            ).fetchone()
            if reg is None:
                conn.rollback()
                raise HTTPException(status_code=404, detail="挂号单不存在")
            if reg["status"] != "候诊":
                conn.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"挂号单当前状态为“{reg['status']}”，不可开处方",
                )

            pres_no = _build_prescription_no()
            cur = conn.execute(
                "INSERT INTO prescriptions "
                "(prescription_no, reg_id, patient_id, doctor_id, diagnosis, "
                " total_amount_cents, status) "
                "VALUES (?, ?, ?, ?, ?, 0, '待收费')",
                (
                    pres_no,
                    reg["reg_id"],
                    reg["patient_id"],
                    reg["doctor_id"],
                    req.diagnosis,
                ),
            )
            pid = cur.lastrowid

            total = 0
            out_items: list = []
            for it in req.items:
                drug = drug_cache[it.drug_id]
                price = drug["price_cents"]
                amount = compute_line_amount(it.quantity, price)  # 金额由后端现算
                total += amount
                cur_i = conn.execute(
                    "INSERT INTO prescription_items "
                    "(prescription_id, drug_id, quantity, unit_price_cents, "
                    " amount_cents, status) "
                    "VALUES (?, ?, ?, ?, ?, '待发药')",
                    (pid, it.drug_id, it.quantity, price, amount),
                )
                item_id = cur_i.lastrowid
                out_items.append(
                    {
                        "item_id": item_id,
                        "drug_id": it.drug_id,
                        "drug_code": drug["drug_code"],
                        "generic_name": drug["generic_name"],
                        "spec": drug["spec"],
                        "unit": drug["unit"],
                        "quantity": it.quantity,
                        "unit_price_cents": price,
                        "amount_cents": amount,
                    }
                )

            conn.execute(
                "UPDATE prescriptions SET total_amount_cents = ? WHERE prescription_id = ?",
                (total, pid),
            )

            conn.commit()
        except HTTPException:
            raise
        except sqlite3.Error:
            conn.rollback()
            raise

        return {
            "prescription_id": pid,
            "prescription_no": pres_no,
            "reg_id": req.reg_id,
            "total_amount_cents": total,
            "status": "待收费",
            "items": out_items,
        }
    finally:
        conn.close()


@router.get("/drugs")
def list_drugs(user: dict = Depends(require_permission("prescription:read"))) -> list:
    """返回所有启用药品（status='启用'），按 drug_id 排序。"""
    from main import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT drug_id, drug_code, generic_name, spec, dosage_form, unit, price_cents "
            "FROM drugs WHERE status = '启用' ORDER BY drug_id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
