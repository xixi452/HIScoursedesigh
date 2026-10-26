"""登录与当前用户接口（POST /api/login、GET /api/me）。

安全要点：
- 登录失败统一返回 401「用户名或密码错误」，不区分"账号不存在"，
  避免被枚举出有效用户名。
- 密码校验使用 bcrypt（security.verify_password）。
- 登录成功签发带角色信息的 JWT，并更新 last_login_at 留痕。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from main import get_connection
from security import (
    create_access_token,
    get_current_user,
    verify_password,
)

router = APIRouter(prefix="/api", tags=["认证"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=72)


@router.post("/login")
def login(req: LoginRequest) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id, username, password_hash, real_name, role_id, "
            "       dept_id, status "
            "FROM sys_users WHERE username = ?",
            (req.username,),
        ).fetchone()
        if row is None or not verify_password(req.password, row["password_hash"]):
            # 统一口径，不泄露账号是否存在
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )
        if row["status"] != "启用":
            raise HTTPException(status_code=403, detail="账号已停用，请联系管理员")

        role = conn.execute(
            "SELECT role_code, role_name FROM roles WHERE role_id = ?",
            (row["role_id"],),
        ).fetchone()

        conn.execute(
            "UPDATE sys_users SET last_login_at = ? WHERE user_id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["user_id"]),
        )
        conn.commit()

        token = create_access_token(row["user_id"], row["username"], role["role_code"])
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": row["user_id"],
                "username": row["username"],
                "real_name": row["real_name"],
                "role_code": role["role_code"],
                "role_name": role["role_name"],
            },
        }
    finally:
        conn.close()


@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    """返回当前登录用户信息，不返回任何敏感字段（如 password_hash）。"""
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "real_name": user["real_name"],
        "role_code": user["role_code"],
        "role_name": user["role_name"],
        "dept_id": user["dept_id"],
    }
