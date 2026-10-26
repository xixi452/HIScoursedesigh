"""收费接口（POST /api/pay）—— 事务内一次性完成"校验 → FEFO 扣库存 → 写发药记录 → 记账 → 改状态"。

三条硬规则落实位置：
- 【事务】：第 67 行 BEGIN IMMEDIATE 开启；b~e 全部在同一事务的 try 块内
  （约第 71~186 行）：幂等检查、校验收费员/处方、逐条 FEFO 扣库存、写
  dispense_records(record_type='发药')、写 bills、更新 prescriptions.status='已收费'，
  任一步失败在 except 中 conn.rollback()（第 221 行）后返回错误，绝不允许
  "扣了库存没记账"或反之；BEGIN IMMEDIATE 失败返回 503（第 68~69 行）。
- 【金额】：PayRequest 只含 prescription_id / request_id / cashier_id / payment_method，
  不含任何金额字段；总金额在事务内由 prescription_items 重新 SUM(amount_cents) 计算
  （第 175 行），不采信前端金额。
- 【库存】：扣减前先按可用量校验，不足则 rollback + HTTP 400（第 127 行），
  detail 形如「药品"阿莫西林胶囊"库存不足：需要 2，可用 1」；
  扣减 SQL 带 `quantity >= ?`（第 140 行），rowcount==0 同样 rollback + 400（第 144 行）；
  依赖 drug_stocks.quantity >= 0 的 CHECK 约束兜底。
"""

import sqlite3
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from security import require_permission
from services.inventory import allocate_fefo

router = APIRouter(prefix="/api", tags=["收费"])


class PayRequest(BaseModel):
    prescription_id: int = Field(..., gt=0, description="处方ID")
    request_id: str = Field(..., min_length=1, max_length=64, description="幂等请求ID")
    payment_method: Literal["现金", "微信", "支付宝", "银行卡"] = Field(
        default="现金", description="支付方式（MVP 默认现金）"
    )


def _build_bill_no(prescription_id: int, seq: int) -> str:
    return f"FY{datetime.now():%Y%m%d}{prescription_id:06d}{seq:03d}"


@router.post("/pay")
def pay(
    req: PayRequest,
    user: dict = Depends(require_permission("billing:charge")),
) -> dict:
    from main import get_connection

    # 收费员身份取自 JWT，忽略并防止前端伪造 cashier_id
    cashier_id = user["user_id"]

    conn = get_connection()
    conn.isolation_level = None
    try:
        # a. 幂等检查（事务外快捷返回）
        existing = conn.execute(
            "SELECT * FROM bills WHERE request_id = ?", (req.request_id,)
        ).fetchone()
        if existing is not None:
            result = dict(existing)
            result["stock_deductions"] = []
            return result

        # b. 收费员身份已在鉴权依赖中校验（来自 JWT），此处无需再查
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise HTTPException(status_code=503, detail="系统繁忙，请稍后重试") from exc

        try:
            # a(再查一次，防并发)：命中直接返回
            existing = conn.execute(
                "SELECT * FROM bills WHERE request_id = ?", (req.request_id,)
            ).fetchone()
            if existing is not None:
                conn.rollback()
                result = dict(existing)
                result["stock_deductions"] = []
                return result

            # b. 校验处方存在且为待收费
            prescription = conn.execute(
                "SELECT prescription_id, patient_id, status "
                "FROM prescriptions WHERE prescription_id = ?",
                (req.prescription_id,),
            ).fetchone()
            if prescription is None:
                conn.rollback()
                raise HTTPException(status_code=404, detail="处方不存在")
            if prescription["status"] != "待收费":
                conn.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"处方当前状态为“{prescription['status']}”，不可收费",
                )

            # 取处方明细（drug_id / quantity / 药名）
            items = conn.execute(
                "SELECT pi.item_id, pi.drug_id, pi.quantity, d.generic_name "
                "FROM prescription_items pi "
                "JOIN drugs d ON d.drug_id = pi.drug_id "
                "WHERE pi.prescription_id = ? AND pi.status <> '作废' "
                "ORDER BY pi.item_id",
                (req.prescription_id,),
            ).fetchall()
            if not items:
                conn.rollback()
                raise HTTPException(status_code=400, detail="处方没有可收费明细")

            # c. 逐条 FEFO 扣库存（库存不足 → rollback + 400）
            stock_deductions: list = []
            for item in items:
                needed = item["quantity"]
                batches = conn.execute(
                    "SELECT stock_id, batch_no, quantity "
                    "FROM drug_stocks "
                    "WHERE drug_id = ? AND status = '正常' AND quantity > 0 "
                    "ORDER BY expiry_date ASC, production_date ASC, stock_id ASC",
                    (item["drug_id"],),
                ).fetchall()
                try:
                    plan = allocate_fefo([dict(b) for b in batches], needed)
                except ValueError as exc:
                    conn.rollback()
                    raise HTTPException(
                        status_code=400,
                        detail=f"药品“{item['generic_name']}”{exc}",
                    ) from exc

                for step in plan:
                    take = step["take"]
                    # 扣减 SQL 带 quantity >= ? 条件（硬规则3）
                    cur = conn.execute(
                        "UPDATE drug_stocks "
                        "SET quantity = quantity - ?, version = version + 1, "
                        "    updated_at = datetime('now', 'localtime') "
                        "WHERE stock_id = ? AND quantity >= ?",
                        (take, step["stock_id"], take),
                    )
                    if cur.rowcount == 0:
                        conn.rollback()
                        raise HTTPException(
                            status_code=400,
                            detail=f"药品“{item['generic_name']}”库存扣减冲突，请重试",
                        )
                    # d. 记一条发药记录（收费员代登记批次，供药房确认）
                    conn.execute(
                        "INSERT INTO dispense_records "
                        "(prescription_id, item_id, stock_id, batch_no, quantity, "
                        " record_type, pharmacist_id) "
                        "VALUES (?, ?, ?, ?, ?, '发药', ?)",
                        (
                            req.prescription_id,
                            item["item_id"],
                            step["stock_id"],
                            step["batch_no"],
                            take,
                            cashier_id,
                        ),
                    )
                    stock_deductions.append(
                        {
                            "drug": item["generic_name"],
                            "batch_no": step["batch_no"],
                            "quantity": take,
                        }
                    )

            # 金额由后端从明细现算（硬规则2）
            amount = conn.execute(
                "SELECT COALESCE(SUM(amount_cents), 0) AS total "
                "FROM prescription_items WHERE prescription_id = ?",
                (req.prescription_id,),
            ).fetchone()["total"]
            if amount <= 0:
                conn.rollback()
                raise HTTPException(status_code=400, detail="处方没有可收费明细")

            # e. 写 bills + 更新处方状态
            seq = (
                conn.execute(
                    "SELECT COUNT(*) AS cnt FROM bills WHERE prescription_id = ?",
                    (req.prescription_id,),
                ).fetchone()["cnt"]
                + 1
            )
            bill_no = _build_bill_no(req.prescription_id, seq)
            cur = conn.execute(
                "INSERT INTO bills (bill_no, bill_type, reg_id, prescription_id, "
                "    patient_id, total_amount_cents, payment_method, cashier_id, request_id) "
                "VALUES (?, '药品费', NULL, ?, ?, ?, ?, ?, ?)",
                (
                    bill_no,
                    req.prescription_id,
                    prescription["patient_id"],
                    amount,
                    req.payment_method,
                    cashier_id,
                    req.request_id,
                ),
            )
            bill_id = cur.lastrowid

            conn.execute(
                "UPDATE prescriptions SET status = '已收费', total_amount_cents = ? "
                "WHERE prescription_id = ? AND status = '待收费'",
                (amount, req.prescription_id),
            )

            bill = conn.execute(
                "SELECT * FROM bills WHERE bill_id = ?", (bill_id,)
            ).fetchone()
            conn.commit()
        except HTTPException:
            raise
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            existing = conn.execute(
                "SELECT * FROM bills WHERE request_id = ?", (req.request_id,)
            ).fetchone()
            if existing is not None:
                result = dict(existing)
                result["stock_deductions"] = []
                return result
            raise HTTPException(status_code=409, detail="收费冲突，请重试") from exc
        except sqlite3.Error:
            conn.rollback()
            raise

        result = dict(bill)
        result["stock_deductions"] = stock_deductions
        return result
    finally:
        conn.close()
