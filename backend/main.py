import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DB_PATH = Path(os.environ.get("HIS_DB_PATH", str(BASE_DIR / "data" / "his.db")))
SCHEMA_SQL = PROJECT_ROOT / "04_schema.sql"
SEED_SQL = PROJECT_ROOT / "06_seed_reference.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _schema_ready() -> bool:
    if not DB_PATH.exists():
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='departments'"
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def init_database() -> None:
    if _schema_ready():
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        for script in (SCHEMA_SQL, SEED_SQL):
            conn.executescript(script.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(title="门诊 HIS MVP API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 操作审计：对写操作自动留痕（第 10 课）
from audit_middleware import AuditMiddleware  # noqa: E402

app.add_middleware(AuditMiddleware)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


from routers.registration import router as registration_router
from routers.payment import router as payment_router
from routers.dispense import router as dispense_router
from routers.query import router as query_router
from routers.prescription import router as prescription_router
from routers.auth import router as auth_router
from routers.drugs import router as drugs_router
from routers.import_patients import router as import_patients_router
from routers.report import router as report_router
from routers.audit import router as audit_router

app.include_router(auth_router)
app.include_router(registration_router)
app.include_router(payment_router)
app.include_router(dispense_router)
app.include_router(query_router)
app.include_router(prescription_router)
app.include_router(drugs_router)
app.include_router(import_patients_router)
app.include_router(report_router)
app.include_router(audit_router)

