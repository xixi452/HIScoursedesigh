"""pytest 公共夹具：临时测试库 + 完整业务种子数据。

每个测试用例拿到一个全新的、已种好数据的 SQLite 库与 TestClient，
用例之间互不影响（function 作用域，每次重建数据库）。
"""

import os
import pathlib
import tempfile

# 必须在 import main 之前设置环境变量，固定测试用 JWT 密钥与库路径
_TEST_DIR = tempfile.mkdtemp(prefix="his_test_")
os.environ["HIS_DB_PATH"] = os.path.join(_TEST_DIR, "his_test.db")
os.environ["HIS_JWT_SECRET"] = "test-secret-key-for-his-mvp-unit-tests-0123456789"

import pytest  # noqa: E402

import main  # noqa: E402
from seed_demo import seed_demo  # noqa: E402


def _reset_db() -> None:
    if main.DB_PATH.exists():
        main.DB_PATH.unlink()
        for suffix in ("-wal", "-shm"):
            p = pathlib.Path(str(main.DB_PATH) + suffix)
            if p.exists():
                p.unlink()
    main.init_database()
    conn = main.get_connection()
    try:
        seed_demo(conn)
    finally:
        conn.close()


@pytest.fixture()
def client():
    _reset_db()
    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def login(client):
    """返回一个登录函数：login(username, password) -> access_token。"""

    def _login(username: str, password: str) -> str:
        resp = client.post("/api/login", json={"username": username, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _login


@pytest.fixture()
def auth(login):
    """返回一个鉴权头函数：auth(username, password) -> {"Authorization": ...}。"""

    def _auth(username: str, password: str) -> dict:
        return {"Authorization": f"Bearer {login(username, password)}"}

    return _auth
