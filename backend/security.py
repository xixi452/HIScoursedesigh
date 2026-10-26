"""认证与授权（第 7 课：Authenticate · Authorize · Audit）。

职责：
1. 密码安全存储：使用 bcrypt 加盐哈希，禁止明文或 md5/sha256 直接存；
2. 签发与校验 JWT：登录成功后签发带角色信息的令牌；
3. 依赖注入式鉴权：get_current_user 解析令牌并校验账号状态，
   require_permission 按角色-权限表做接口级授权，无权限返回 403。

安全要点：
- 操作员身份一律取自令牌（sub），绝不信任请求体里的 operator_id /
  cashier_id / pharmacist_id，杜绝身份伪造（IDOR / 越权）。
- 每次请求都从数据库读取最新用户与角色权限，令牌里的角色仅作快速提示，
  不以令牌为准（避免"停用/改权限后令牌仍可用"）。
"""

import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from main import get_connection

# JWT 配置：生产环境必须通过环境变量注入，禁止使用默认值。
SECRET_KEY = os.environ.get("HIS_JWT_SECRET", "dev-only-insecure-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("HIS_JWT_EXPIRE_MINUTES", "120"))

# bcrypt 输入上限（字节）：bcrypt 只取前 72 字节，超长直接拒绝，避免静默截断。
_BCRYPT_MAX_BYTES = 72

_bearer = HTTPBearer(auto_error=False)


def _as_bytes(value: str) -> bytes:
    data = value.encode("utf-8")
    if len(data) > _BCRYPT_MAX_BYTES:
        raise ValueError("密码长度超出 bcrypt 支持上限（72 字节）")
    return data


def hash_password(plain: str) -> str:
    """使用 bcrypt 加盐哈希密码。"""
    return bcrypt.hashpw(_as_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码，任何异常（格式错误/超长）一律返回 False，不泄露内部细节。"""
    try:
        return bcrypt.checkpw(_as_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, username: str, role_code: str) -> str:
    """签发 JWT，含 sub（用户 ID）、username、role（角色代码）与过期时间。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role_code,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """校验并解析 JWT，失败时抛出 HTTPException(401)。"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的登录凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _load_user(user_id: int) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT u.user_id, u.username, u.real_name, u.role_id, "
            "       u.dept_id, u.status, r.role_code, r.role_name "
            "FROM sys_users u JOIN roles r ON r.role_id = u.role_id "
            "WHERE u.user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row is not None else {}
    finally:
        conn.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """解析 Bearer 令牌并返回当前用户（含角色）。未登录/令牌无效返回 401。"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或缺少凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="无效的登录凭证")

    user = _load_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="账号不存在")
    if user["status"] != "启用":
        raise HTTPException(status_code=403, detail="账号已停用，请联系管理员")
    return user


def require_permission(permission_code: str):
    """返回一个鉴权依赖：当前用户的角色须拥有指定权限，否则返回 403。"""

    def _check(user: dict = Depends(get_current_user)) -> dict:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT 1 FROM role_permissions rp "
                "JOIN permissions p ON p.permission_id = rp.permission_id "
                "WHERE rp.role_id = ? AND p.permission_code = ?",
                (user["role_id"], permission_code),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"当前角色（{user['role_name']}）无权执行该操作",
            )
        return user

    return _check


# ======================================================================
# 身份证/手机号脱敏与哈希（第 10 课 · 数据集成，与 04_schema.sql 约束一致）
# ======================================================================

_ID_CARD_RE = re.compile(r"^\d{17}[\dX]$")
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")

# 加盐密钥：生产环境务必通过环境变量 HIS_ID_SALT 注入，切勿硬编码。
ID_SALT = os.getenv("HIS_ID_SALT", "his-mvp-id-salt-2024")


def _normalize(value: str) -> str:
    if not value:
        return ""
    return value.replace(" ", "").replace("-", "").upper()


def is_valid_id_card(value: str) -> bool:
    """是否为完整 18 位身份证号（格式校验）。"""
    return bool(_ID_CARD_RE.match(_normalize(value)))


def is_valid_phone(value: str) -> bool:
    """是否为完整 11 位手机号。"""
    return bool(_PHONE_RE.match(_normalize(value)))


def id_card_checksum_ok(value: str) -> bool:
    """GB 11643-1999 末位校验码校验（可选增强；MVP 未强制）。"""
    v = _normalize(value)
    if not _ID_CARD_RE.match(v):
        return False
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    codes = "10X98765432"
    total = sum(int(v[i]) * weights[i] for i in range(17))
    return codes[total % 11] == v[17]


def mask_id_card(value: str) -> str:
    """身份证脱敏：前 6 后 4，中间 8 位 *。330106199001011234 -> 330106********1234"""
    v = _normalize(value)
    return f"{v[:6]}********{v[-4:]}" if len(v) == 18 else "********"


def id_card_last4(value: str) -> str:
    v = _normalize(value)
    return v[-4:] if len(v) == 18 else ""


def hash_id_card(value: str) -> str:
    """HMAC-SHA256 加盐哈希，用于唯一性校验（不可逆）。"""
    return hmac.new(
        ID_SALT.encode("utf-8"),
        _normalize(value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def mask_phone(value: str) -> str:
    """手机号脱敏：前 3 后 4。13812345678 -> 138****5678"""
    v = _normalize(value)
    return f"{v[:3]}****{v[-4:]}" if len(v) == 11 else "****"
