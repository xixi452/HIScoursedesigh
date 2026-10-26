"""挂号接口（POST /api/register）。

并发安全核心规则（SQLite）：
1. 挂号扣号源必须在同一事务内完成：BEGIN IMMEDIATE 立刻获取写锁，
   将"扣号源 -> 计算排队号 -> 插入挂号单"串行化，防止并发重复挂号；
2. 库存拦截：执行
   UPDATE schedules SET remaining_count = remaining_count - 1
   WHERE schedule_id = ? AND remaining_count > 0
   受影响行数为 0 说明号源已满，必须 ROLLBACK 并返回 400；
3. 排队号 queue_no 在事务内按当前号源下已挂号人数递增生成
   （COUNT(*) + 1），配合表级 UNIQUE(schedule_id, queue_no) 约束
   双保险，防止并发下产生重复排队号。
"""

import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from main import get_connection
from security import require_permission
from services.registration import next_queue_no

router = APIRouter(prefix="/api", tags=["挂号"])


class RegisterRequest(BaseModel):
    patient_id: int = Field(..., gt=0, description="患者ID")
    schedule_id: int = Field(..., gt=0, description="排班号源ID")


def _build_reg_no(schedule_id: int, queue_no: int) -> str:
    return f"GH{datetime.now():%Y%m%d}{schedule_id:05d}{queue_no:04d}"


@router.post("/register", status_code=201)
def register(
    req: RegisterRequest,
    user: dict = Depends(require_permission("reg:create")),
) -> dict:
    # 操作员身份取自 JWT，忽略并防止前端伪造 operator_id
    operator_id = user["user_id"]
    conn = get_connection()
    conn.isolation_level = None
    try:
        schedule = conn.execute(
            "SELECT schedule_id, doctor_id, dept_id, fee_cents, status "
            "FROM schedules WHERE schedule_id = ?",
            (req.schedule_id,),
        ).fetchone()
        if schedule is None:
            raise HTTPException(status_code=404, detail="排班号源不存在")
        if schedule["status"] != "正常":
            raise HTTPException(status_code=400, detail="该号源当前不可挂号")

        if (
            conn.execute(
                "SELECT 1 FROM patients WHERE patient_id = ?",
                (req.patient_id,),
            ).fetchone()
            is None
        ):
            raise HTTPException(status_code=404, detail="患者不存在")

        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise HTTPException(status_code=503, detail="系统繁忙，请稍后重试") from exc

        try:
            cur = conn.execute(
                "UPDATE schedules "
                "SET remaining_count = remaining_count - 1, "
                "    updated_at = datetime('now', 'localtime') "
                "WHERE schedule_id = ? AND remaining_count > 0",
                (req.schedule_id,),
            )
            if cur.rowcount == 0:
                conn.rollback()
                # 号源不足/已满：规范要求返回 409（冲突），而非 400
                raise HTTPException(status_code=409, detail="号源已满，挂号失败")

            conn.execute(
                "UPDATE schedules "
                "SET status = '满号', updated_at = datetime('now', 'localtime') "
                "WHERE schedule_id = ? AND remaining_count = 0",
                (req.schedule_id,),
            )

            queue_no = next_queue_no(
                conn.execute(
                    "SELECT COUNT(*) AS cnt FROM reg_orders WHERE schedule_id = ?",
                    (req.schedule_id,),
                ).fetchone()["cnt"]
            )

            reg_no = _build_reg_no(req.schedule_id, queue_no)
            cur = conn.execute(
                "INSERT INTO reg_orders "
                "(reg_no, patient_id, doctor_id, dept_id, schedule_id, "
                " queue_no, fee_cents, status, operator_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, '候诊', ?)",
                (
                    reg_no,
                    req.patient_id,
                    schedule["doctor_id"],
                    schedule["dept_id"],
                    req.schedule_id,
                    queue_no,
                    schedule["fee_cents"],
                    operator_id,
                ),
            )
            reg_id = cur.lastrowid

            order = conn.execute(
                "SELECT reg_id, reg_no, patient_id, doctor_id, dept_id, "
                "       schedule_id, reg_time, queue_no, fee_cents, status, "
                "       operator_id "
                "FROM reg_orders WHERE reg_id = ?",
                (reg_id,),
            ).fetchone()

            conn.commit()
        except HTTPException:
            raise
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise HTTPException(status_code=409, detail="挂号冲突，请重试") from exc
        except sqlite3.Error:
            conn.rollback()
            raise

        return dict(order)
    finally:
        conn.close()
