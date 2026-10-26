"""查询类接口：可选号源列表、待就诊患者列表。"""

from fastapi import APIRouter, Depends

from main import get_connection
from security import require_permission

router = APIRouter(prefix="/api", tags=["查询"])


@router.get("/schedules")
def list_schedules(
    user: dict = Depends(require_permission("schedule:read")),
) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT schedule_id, work_date, time_slot, reg_level, fee_cents, "
            "       remaining_count, doctor_name, doctor_title, dept_name, dept_location "
            "FROM v_available_schedules "
            "ORDER BY work_date, time_slot, doctor_id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/reg-orders/waiting")
def list_waiting(
    user: dict = Depends(require_permission("reg:read")),
) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r.reg_id, r.reg_no, r.queue_no, r.reg_time, "
            "       p.name AS patient_name, d.name AS doctor_name, "
            "       dep.name AS dept_name "
            "FROM reg_orders r "
            "JOIN patients p ON p.patient_id = r.patient_id "
            "JOIN doctors d ON d.doctor_id = r.doctor_id "
            "JOIN departments dep ON dep.dept_id = r.dept_id "
            "WHERE r.status = '候诊' "
            "ORDER BY r.schedule_id, r.queue_no"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
