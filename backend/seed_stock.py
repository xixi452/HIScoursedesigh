r"""发药测试库存脚本，可重复执行（每次运行重置各批次数量与状态）。

为两种测试药品插入多个不同效期的批次，用于验证 FEFO（先到期先出）：
- 阿莫西林（drug 1）：最早效期批次只放 1 盒，发 2 盒会拆到两个批次；
- 布洛芬（drug 2）：最早效期批次 1 盒，刚好满足处方需要。

用法：在 backend 目录下执行
    .venv\Scripts\python seed_stock.py
"""
import sqlite3

from main import DB_PATH, init_database

DRUGS = (
    (1, "D1001", "阿莫西林胶囊", "0.25g*24粒", "胶囊", "盒", 2000),
    (2, "D1002", "布洛芬片", "0.3g*20片", "片剂", "盒", 3500),
)

STOCKS = (
    # drug_id, batch_no, production_date, expiry_date, quantity, location
    (1, "AMX202701", "2026-01-10", "2027-01-31", 1, "A-01"),
    (1, "AMX202706", "2026-06-10", "2027-06-30", 5, "A-01"),
    (1, "AMX202801", "2027-01-10", "2028-01-31", 3, "A-02"),
    (2, "BLF202612", "2025-12-10", "2026-12-31", 1, "B-01"),
    (2, "BLF202808", "2027-08-10", "2028-08-31", 4, "B-02"),
)

init_database()

conn = sqlite3.connect(DB_PATH)
try:
    for drug_id, code, name, spec, form, unit, price in DRUGS:
        conn.execute(
            "INSERT OR IGNORE INTO drugs (drug_id, drug_code, generic_name, spec, "
            "                             dosage_form, unit, price_cents) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (drug_id, code, name, spec, form, unit, price),
        )
    for drug_id, batch_no, prod, expiry, qty, loc in STOCKS:
        conn.execute(
            "INSERT INTO drug_stocks (drug_id, batch_no, production_date, expiry_date, "
            "                         quantity, location, status) "
            "VALUES (?, ?, ?, ?, ?, ?, '正常') "
            "ON CONFLICT(drug_id, batch_no) DO UPDATE SET "
            "    expiry_date = excluded.expiry_date, "
            "    quantity = excluded.quantity, "
            "    location = excluded.location, "
            "    status = '正常'",
            (drug_id, batch_no, prod, expiry, qty, loc),
        )
    conn.commit()
finally:
    conn.close()

print("drug_stocks seeded:")
for drug_id, batch_no, prod, expiry, qty, loc in STOCKS:
    print(f"  drug_id={drug_id}  batch={batch_no}  expiry={expiry}  quantity={qty}  location={loc}")
print("预期 FEFO：阿莫西林发 2 盒 -> AMX202701 扣 1 + AMX202706 扣 1；布洛芬发 1 盒 -> BLF202612 扣 1")
