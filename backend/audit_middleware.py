"""操作审计日志中间件（第 10 课 · 纯 ASGI 实现）。

- 拦截所有写操作（POST/PUT/PATCH/DELETE），GET 只读不落审计；
- 同时缓冲请求体与响应体，记录：操作人(user_id，从 JWT 解析)、动作(action)、
  实体(entity)、实体ID(entity_id，从响应体提取新建记录 ID)、请求摘要(detail，
  含状态码)、来源 IP、时间；
- 审计写入失败绝不阻断业务请求（try/except 兜底，可用性优先）。

用户身份：从 Authorization Bearer JWT 的 sub 解析（与全局鉴权一致）。
"""

import json

from starlette.types import ASGIApp, Receive, Scope, Send

from main import get_connection

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

ENTITY_BY_PREFIX = {
    "/api/register": "挂号",
    "/api/pay": "收费",
    "/api/dispense": "发药",
    "/api/prescriptions": "处方",
    "/api/drugs/import": "药品导入",
    "/api/import/patients": "患者导入",
    "/api/login": "登录",
}

ENTITY_ID_KEYS = (
    "reg_id", "prescription_id", "bill_id", "dispense_id", "patient_id",
    "item_id", "stock_id", "drug_id", "schedule_id", "id",
)


def _resolve_entity(path: str) -> str:
    for prefix, name in ENTITY_BY_PREFIX.items():
        if path.startswith(prefix):
            return name
    return path


def _extract_id(obj: dict, keys: tuple) -> str | None:
    if not isinstance(obj, dict):
        return None
    for key in keys:
        if key in obj and obj[key] is not None:
            return str(obj[key])
    return None


def _resolve_user_id(raw_headers: dict) -> int | None:
    """从 JWT 解析操作人（与鉴权一致，不信任 X-User-Id 头）。"""
    auth = raw_headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        from security import decode_token

        payload = decode_token(auth[7:])
        return int(payload["sub"])
    except Exception:
        return None


def _write_audit_log(user_id, action, entity, entity_id, detail, ip) -> None:
    try:
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO audit_logs (user_id, action, entity, entity_id, detail, ip) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, action, entity, entity_id, detail, ip),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # 审计失败不阻断业务


class AuditMiddleware:
    """纯 ASGI 中间件：缓冲请求/响应体后落一条审计日志。"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        if method not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return

        raw_headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                       for k, v in scope.get("headers", [])}
        content_type = raw_headers.get("content-type", "")

        # ---- 缓冲请求体 ----
        chunks: list[bytes] = []
        more = True
        while more:
            message = await receive()
            chunks.append(message.get("body", b""))
            more = message.get("more_body", False)
        request_body = b"".join(chunks)

        body_json: dict | None = None
        body_text = ""
        if request_body:
            try:
                body_text = request_body.decode("utf-8", errors="replace")
                if content_type.startswith("application/json"):
                    body_json = json.loads(body_text)
            except Exception:
                body_json = None

        user_id = _resolve_user_id(raw_headers)
        entity = _resolve_entity(path)

        # ---- 重新注入请求体，交给下游路由 ----
        body_sent = False

        async def _receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": request_body, "more_body": False}
            return await receive()

        # ---- 缓冲响应体 ----
        status_code = 200
        response_chunks: list[bytes] = []

        async def _send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                response_chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, _receive, _send)

        # ---- 解析响应体以提取新建实体 ID ----
        response_json: dict | None = None
        if response_chunks:
            try:
                response_json = json.loads(b"".join(response_chunks).decode("utf-8", errors="replace"))
            except Exception:
                response_json = None

        entity_id = _extract_id(response_json or {}, ENTITY_ID_KEYS) \
            or _extract_id(body_json or {}, ENTITY_ID_KEYS)

        if content_type.startswith("multipart/form-data"):
            detail = f"(multipart 文件上传) -> HTTP {status_code}"
        elif body_text:
            detail = body_text[:1000] + f" -> HTTP {status_code}"
        else:
            detail = f"HTTP {status_code}"

        ip = scope.get("client", [None, None])[0] if scope.get("client") else None

        # action=中文动作标签，entity=HTTP 路径
        _write_audit_log(user_id, entity, path, entity_id, detail, ip)
