"""药品 CSV 批量导入（第 10 课 · 服务端校验 + 去重 + 错误明细）。

三条设计点（缺一不可）：
1. 校验在服务端，不信任上传文件；
2. 错误行不影响合法行——不是"一错全错"；
3. 返回错误明细，用户知道哪一行为什么失败。
"""

import csv
import io
from datetime import date, timedelta

VALID_INSURANCE = {"甲类", "乙类", "自费", "丙类"}

# CSV 列名（中文表头）
COLS = ["药品编码", "通用名", "商品名", "规格", "剂型", "单位", "单价", "医保类别", "库存数量"]


def decode_csv(data: bytes) -> str:
    """自动检测编码：UTF-8 BOM / UTF-8 / GBK（Excel 导出的 CSV 常是 GBK）。"""
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gbk")


def _price_to_cents(value: str):
    """单价（元）转分，非法返回 None。"""
    try:
        yuan = float(value)
    except (TypeError, ValueError):
        return None
    if yuan <= 0:
        return None
    return round(yuan * 100)


def _qty_to_int(value: str):
    try:
        qty = int(value)
    except (TypeError, ValueError):
        return None
    return qty if qty > 0 else None


def import_drugs_csv(conn, data: bytes) -> dict:
    """解析 + 校验 + 去重 + 入库，返回导入统计与错误明细。"""
    text = decode_csv(data)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return {"total": 0, "success": 0, "fail": 0, "errors": []}

    header = [h.strip() for h in rows[0]]
    col = {name: i for i, name in enumerate(header)}

    def get(row, name):
        i = col.get(name)
        if i is None or i >= len(row):
            return ""
        return (row[i] or "").strip()

    success = 0
    errors = []
    seen_codes = set()

    for lineno, row in enumerate(rows[1:], start=2):
        code = get(row, "药品编码")
        name = get(row, "通用名")
        spec = get(row, "规格")
        form = get(row, "剂型")
        unit = get(row, "单位") or "盒"
        trade = get(row, "商品名")
        price_s = get(row, "单价")
        insurance = get(row, "医保类别")
        qty_s = get(row, "库存数量")

        # 逐条校验（错误行记录原因后 continue，不影响后续合法行）
        if not code:
            errors.append({"line": lineno, "reason": "药品编码缺失"})
            continue
        if not name:
            errors.append({"line": lineno, "reason": "通用名缺失"})
            continue
        if not spec:
            errors.append({"line": lineno, "reason": "规格缺失"})
            continue
        if not form:
            errors.append({"line": lineno, "reason": "剂型缺失"})
            continue
        if insurance not in VALID_INSURANCE:
            errors.append({"line": lineno, "reason": f"医保类别非法：{insurance or '空'}"})
            continue
        price_cents = _price_to_cents(price_s)
        if price_cents is None:
            errors.append({"line": lineno, "reason": f"单价非法：{price_s or '空'}"})
            continue
        qty = _qty_to_int(qty_s)
        if qty is None:
            errors.append({"line": lineno, "reason": f"库存数量非法：{qty_s or '空'}"})
            continue
        if code in seen_codes:
            errors.append({"line": lineno, "reason": f"药品编码重复：{code}"})
            continue

        seen_codes.add(code)

        # 药品档案（去重入库）
        conn.execute(
            "INSERT INTO drugs (drug_code, generic_name, trade_name, spec, dosage_form, "
            "                    unit, price_cents, insurance_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(drug_code) DO UPDATE SET "
            "  generic_name=excluded.generic_name, spec=excluded.spec, "
            "  dosage_form=excluded.dosage_form, unit=excluded.unit, "
            "  price_cents=excluded.price_cents, insurance_type=excluded.insurance_type, "
            "  status='启用'",
            (code, name, trade, spec, form, unit, price_cents, insurance),
        )

        # 初始库存（批次 IMP-{code}，效期一年后）
        expiry = (date.today() + timedelta(days=365)).isoformat()
        conn.execute(
            "INSERT INTO drug_stocks (drug_id, batch_no, production_date, expiry_date, "
            "                          quantity, location, status) "
            "SELECT drug_id, ?, ?, ?, ?, '导入', '正常' FROM drugs WHERE drug_code = ? "
            "ON CONFLICT(drug_id, batch_no) DO UPDATE SET quantity = excluded.quantity",
            (f"IMP-{code}", date.today().isoformat(), expiry, qty, code),
        )
        success += 1

    conn.commit()
    return {"total": len(rows) - 1, "success": success, "fail": len(errors), "errors": errors}
