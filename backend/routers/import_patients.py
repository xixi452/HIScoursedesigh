"""患者数据 CSV 批量导入（第 10 课 · 数据集成）。

设计要点：
1. 服务端逐行校验：格式/枚举/日期/手机号/身份证，错误行只记录、不影响合法行；
2. 身份证「脱敏入库」：只落 id_card_masked + id_card_hash + id_card_last4，绝不落完整号；
3. 唯一性去重：按 id_card_hash 校验「库内已存在」与「本批次内重复」；
4. 合法行一次性写入同一事务（BEGIN IMMEDIATE），返回逐行结果明细。

接口：
- POST /api/import/patients        multipart 上传 file 或 csv_text
- GET  /api/import/patients/template  下载导入模板
"""

import csv
import io
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

import security
from main import get_connection
from security import require_permission

router = APIRouter(prefix="/api", tags=["数据导入"])

HEADER_ALIASES = {
    "name": "name", "姓名": "name", "患者姓名": "name",
    "gender": "gender", "性别": "gender",
    "birth_date": "birth_date", "出生日期": "birth_date", "生日": "birth_date",
    "id_card": "id_card", "身份证号": "id_card", "身份证": "id_card",
    "phone": "phone", "手机号": "phone", "手机": "phone", "联系电话": "phone",
}

GENDERS = {"男": "男", "女": "女", "未知": "未知",
           "male": "男", "female": "女", "unknown": "未知",
           "M": "男", "F": "女"}

TEMPLATE_HEADER = "name,gender,birth_date,id_card,phone\n"
TEMPLATE_SAMPLE = "张三,男,1990-03-15,330106199003151234,13812345678\n"


def _decode(raw: bytes | str) -> str:
    if isinstance(raw, str):
        return raw
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", errors="replace")


def _parse_csv(text: str) -> list[dict]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV 内容为空")

    header_raw = [h.strip() for h in rows[0]]
    header = [HEADER_ALIASES.get(h, h) for h in header_raw]
    if "name" not in header or "id_card" not in header:
        raise HTTPException(status_code=400, detail="CSV 表头缺少必要列（需含 name/gender/birth_date/id_card）")

    parsed = []
    for i, cells in enumerate(rows[1:], start=2):
        if not any(str(c).strip() for c in cells):
            continue
        record = {header[j]: str(cells[j]).strip() for j in range(len(cells))}
        record["__row__"] = i
        parsed.append(record)
    return parsed


def _validate_row(rec: dict):
    name = (rec.get("name") or "").strip()
    if not name:
        return None, "姓名为空"
    if len(name) > 50:
        return None, "姓名超长（>50）"

    gender_raw = (rec.get("gender") or "").strip()
    gender = GENDERS.get(gender_raw)
    if gender is None:
        return None, f"性别非法“{gender_raw}”（应为 男/女/未知）"

    birth_date = (rec.get("birth_date") or "").strip()
    if not birth_date:
        return None, "出生日期为空"
    try:
        datetime.strptime(birth_date, "%Y-%m-%d")
    except ValueError:
        return None, f"出生日期格式非法“{birth_date}”（应为 YYYY-MM-DD）"

    id_card = (rec.get("id_card") or "").strip()
    if not id_card:
        return None, "身份证号为空"
    if not security.is_valid_id_card(id_card):
        return None, f"身份证号非法“{id_card}”（应为 18 位）"

    phone = (rec.get("phone") or "").strip() or None
    if phone is not None and not security.is_valid_phone(phone):
        return None, f"手机号非法“{phone}”（应为 11 位）"

    return {
        "name": name, "gender": gender, "birth_date": birth_date,
        "id_card": security._normalize(id_card), "phone": phone,
    }, None


def _next_patient_no(conn: sqlite3.Connection, offset: int) -> str:
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(patient_no, 2) AS INTEGER)) AS m "
        "FROM patients WHERE patient_no GLOB 'P[0-9]*'"
    ).fetchone()
    max_no = row["m"] or 0
    return f"P{max_no + 1 + offset:05d}"


@router.get("/import/patients/template", response_class=PlainTextResponse)
def download_template(user: dict = Depends(require_permission("patient:create"))):
    return TEMPLATE_HEADER + TEMPLATE_SAMPLE


@router.post("/import/patients")
async def import_patients(
    file: UploadFile | None = File(None),
    csv_text: str | None = Form(None),
    user: dict = Depends(require_permission("patient:create")),
) -> dict:
    """批量导入患者（挂号员/管理员）。file 与 csv_text 二选一，优先 file。"""
    if file is not None:
        raw = await file.read()
    elif csv_text:
        raw = csv_text
    else:
        raise HTTPException(status_code=400, detail="请上传 file 或提供 csv_text")

    try:
        text = _decode(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSV 解码失败：{exc}") from exc

    records = _parse_csv(text)
    if not records:
        raise HTTPException(status_code=400, detail="CSV 无数据行")

    # 第一阶段：逐行校验
    valid = []
    errors = []
    for rec in records:
        row_no = rec["__row__"]
        data, err = _validate_row(rec)
        if err is not None:
            errors.append({"row": row_no, "name": rec.get("name", ""), "reason": err})
        else:
            valid.append((row_no, data))

    # 第二阶段：本批次内去重（按 id_card_hash）
    seen_hashes = set()
    deduped = []
    for row_no, data in valid:
        h = security.hash_id_card(data["id_card"])
        if h in seen_hashes:
            errors.append({"row": row_no, "name": data["name"], "reason": "批次内身份证号重复"})
            continue
        seen_hashes.add(h)
        data["__hash__"] = h
        deduped.append((row_no, data))

    # 第三阶段：写库（同一事务）
    conn = get_connection()
    conn.isolation_level = None
    created = []
    try:
        conn.execute("BEGIN IMMEDIATE")
        for idx, (row_no, data) in enumerate(deduped):
            exists = conn.execute(
                "SELECT 1 FROM patients WHERE id_card_hash = ?", (data["__hash__"],)
            ).fetchone()
            if exists is not None:
                errors.append({"row": row_no, "name": data["name"], "reason": "身份证号已在库中存在（重复导入）"})
                continue

            patient_no = _next_patient_no(conn, len(created))
            cur = conn.execute(
                "INSERT INTO patients "
                "(patient_no, name, gender, birth_date, id_card_masked, "
                " id_card_hash, id_card_last4, phone, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, '正常')",
                (patient_no, data["name"], data["gender"], data["birth_date"],
                 security.mask_id_card(data["id_card"]), data["__hash__"],
                 security.id_card_last4(data["id_card"]), data["phone"]),
            )
            created.append({
                "row": row_no, "patient_no": patient_no, "name": data["name"],
                "id_card_masked": security.mask_id_card(data["id_card"]),
            })
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"导入写库失败：{exc}") from exc
    finally:
        conn.close()

    errors.sort(key=lambda e: e["row"])
    return {
        "total_rows": len(records), "success": len(created),
        "failed": len(errors), "created_patients": created, "errors": errors,
    }
