"""发药接口（POST /api/dispense）—— 语义改为「确认发药」（库存已在收费阶段 /api/pay 扣减）。

三条硬规则落实位置：
- 【事务】：第 55 行 BEGIN IMMEDIATE 开启；把收费阶段写入的 dispense_records 的
  pharmacist_id 更新为本次药师（第 74~76 行）、prescription_items.dispensed_quantity
  置为 quantity 且 status='已发药'（第 80~83 行）、prescriptions.status='已发药'
  （第 87~89 行）全部在同一事务内，失败 rollback（第 107 行）。BEGIN IMMEDIATE
  失败返回 503（第 56~57 行）。
- 【金额】：本接口不涉及金额；金额已在收费阶段由后端按档案单价现算（见 payment.py 硬规则2）。
- 【库存】：库存扣减已前移至 /api/pay（见 payment.py 硬规则3）。本接口只做处方状态
  校验，非"已收费"返回 400（第 39~42、74~78 行），不再做库存拦截。
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from security import require_permission

router = APIRouter(prefix="/api", tags=["发药"])


class DispenseRequest(BaseModel):
    prescription_id: int = Field(..., gt=0, description="处方ID")


@router.post("/dispense")
def dispense(
    req: DispenseRequest,
    user: dict = Depends(require_permission("pharmacy:dispense")),
) -> dict:
    from main import get_connection

    # 药师身份取自 JWT，忽略并防止前端伪造 pharmacist_id
    pharmacist_id = user["user_id"]

    conn = get_connection()
    conn.isolation_level = None
    try:
        # 校验处方状态必须是"已收费"才能确认发药
        prescription = conn.execute(
            "SELECT prescription_id, status FROM prescriptions WHERE prescription_id = ?",
            (req.prescription_id,),
        ).fetchone()
        if prescription is None:
            raise HTTPException(status_code=404, detail="处方不存在")
        if prescription["status"] != "已收费":
            raise HTTPException(
                status_code=400,
                detail=f"处方当前状态为“{prescription['status']}”，不可发药",
            )

        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise HTTPException(status_code=503, detail="系统繁忙，请稍后重试") from exc

        try:
            # 复检处方状态
            prescription = conn.execute(
                "SELECT status FROM prescriptions WHERE prescription_id = ?",
                (req.prescription_id,),
            ).fetchone()
            if prescription["status"] != "已收费":
                conn.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"处方当前状态为“{prescription['status']}”，不可发药",
                )

            # 把收费阶段写入的发药记录 pharmacist_id 更新为本次药师
            conn.execute(
                "UPDATE dispense_records SET pharmacist_id = ? "
                "WHERE prescription_id = ? AND record_type = '发药'",
                (pharmacist_id, req.prescription_id),
            )
            # 置已发药数量与明细状态
            conn.execute(
                "UPDATE prescription_items "
                "SET dispensed_quantity = quantity, status = '已发药' "
                "WHERE prescription_id = ? AND status <> '作废'",
                (req.prescription_id,),
            )
            # 处方状态改为已发药
            conn.execute(
                "UPDATE prescriptions SET status = '已发药' "
                "WHERE prescription_id = ? AND status = '已收费'",
                (req.prescription_id,),
            )

            # 返回本次确认的发药批次明细
            records = conn.execute(
                "SELECT d.generic_name AS drug, dr.batch_no, dr.quantity "
                "FROM dispense_records dr "
                "JOIN prescription_items pi ON pi.item_id = dr.item_id "
                "JOIN drugs d ON d.drug_id = pi.drug_id "
                "WHERE dr.prescription_id = ? AND dr.record_type = '发药' "
                "ORDER BY dr.dispense_id",
                (req.prescription_id,),
            ).fetchall()

            conn.commit()
        except HTTPException:
            raise
        except sqlite3.Error:
            conn.rollback()
            raise

        return {
            "prescription_id": req.prescription_id,
            "status": "已发药",
            "records": [dict(r) for r in records],
        }
    finally:
        conn.close()
