"""统计报表接口（GET /api/report/daily）。

第 10 课作业：统计报表要能出「今日挂号量」与「收费金额」。
"""
from fastapi import APIRouter, Depends

from main import get_connection
from security import require_permission

router = APIRouter(prefix="/api", tags=["报表"])


@router.get("/report/daily")
def daily_report(user: dict = Depends(require_permission("report:read"))) -> dict:
    conn = get_connection()
    try:
        reg_count = conn.execute(
            "SELECT COUNT(*) FROM reg_orders "
            "WHERE date(reg_time) = date('now','localtime') "
            "AND status IN ('候诊','就诊','完成')"
        ).fetchone()[0]
        reg_refund = conn.execute(
            "SELECT COUNT(*) FROM reg_orders "
            "WHERE date(reg_time) = date('now','localtime') AND status = '退号'"
        ).fetchone()[0]

        charge = conn.execute(
            "SELECT COALESCE(SUM(total_amount_cents), 0) FROM bills "
            "WHERE date(paid_at) = date('now','localtime') AND status = '已收费'"
        ).fetchone()[0]
        refund = conn.execute(
            "SELECT COALESCE(SUM(total_amount_cents), 0) FROM bills "
            "WHERE date(paid_at) = date('now','localtime') AND status = '已退费'"
        ).fetchone()[0]

        dispense_qty = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM dispense_records "
            "WHERE date(dispensed_at) = date('now','localtime') AND record_type = '发药'"
        ).fetchone()[0]

        prescription_count = conn.execute(
            "SELECT COUNT(*) FROM prescriptions "
            "WHERE date(prescribe_time) = date('now','localtime')"
        ).fetchone()[0]
        today = conn.execute("SELECT date('now','localtime')").fetchone()[0]
    finally:
        conn.close()

    return {
        "date": today,
        "reg_count": reg_count,          # 今日挂号量
        "reg_refund": reg_refund,        # 今日退号量
        "prescription_count": prescription_count,  # 今日开方量
        "charge_cents": charge,          # 今日收费金额（分）
        "refund_cents": refund,          # 今日退费金额（分）
        "dispense_qty": dispense_qty,    # 今日发药数量
    }
