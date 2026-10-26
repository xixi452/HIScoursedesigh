"""操作审计日志查询接口（GET /api/audit-logs）。

审计日志是医院系统的"黑匣子"：谁在什么时候对什么做了什么。
写操作由中间件自动留痕，本接口提供分页 + 按用户/动作/实体/日期过滤（仅管理员）。
"""

from fastapi import APIRouter, Depends, Query

from main import get_connection
from security import require_permission

router = APIRouter(prefix="/api", tags=["审计"])


@router.get("/audit-logs")
def list_audit_logs(
    user: dict = Depends(require_permission("admin:audit")),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int | None = Query(default=None, description="按用户过滤"),
    action: str | None = Query(default=None, description="按动作过滤（挂号/收费/发药/开方/登录/药品导入/患者导入）"),
    entity: str | None = Query(default=None, description="按实体路径过滤"),
    date: str | None = Query(default=None, description="按日期过滤，格式 YYYY-MM-DD"),
) -> dict:
    conn = get_connection()
    try:
        where, params = [], []
        if user_id is not None:
            where.append("a.user_id = ?")
            params.append(user_id)
        if action:
            where.append("a.action = ?")
            params.append(action)
        if entity:
            where.append("a.entity = ?")
            params.append(entity)
        if date:
            where.append("date(a.created_at) = ?")
            params.append(date)
        cond = ("WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) AS n FROM audit_logs a {cond}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT a.log_id, a.user_id, u.username, u.real_name, "
            f"       a.action, a.entity, a.entity_id, a.detail, a.ip, a.created_at "
            f"FROM audit_logs a LEFT JOIN sys_users u ON u.user_id = a.user_id "
            f"{cond} ORDER BY a.log_id DESC LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        conn.close()
