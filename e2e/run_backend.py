"""E2E 后端启动脚本：初始化并种入演示数据后启动 uvicorn。

供 Playwright webServer 配置调用，端口 8002。
"""
import os
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

os.environ["HIS_DB_PATH"] = str(BACKEND / "data" / "e2e.db")
os.environ["HIS_JWT_SECRET"] = "e2e-secret-key-for-his-mvp-0123456789abcdef"

from main import DB_PATH, app, get_connection, init_database  # noqa: E402
from seed_demo import seed_demo  # noqa: E402
import uvicorn  # noqa: E402


def _reset_and_seed() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
        for suffix in ("-wal", "-shm"):
            p = pathlib.Path(str(DB_PATH) + suffix)
            if p.exists():
                p.unlink()
    init_database()
    conn = get_connection()
    try:
        seed_demo(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    _reset_and_seed()
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")
