# -*- coding: utf-8 -*-
"""第 10 课演示：药品 CSV 导入 + 患者 CSV 导入 + 审计日志 + 统计报表。

在 backend 目录运行：python demo_lesson10.py
"""
import os
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
os.environ["HIS_DB_PATH"] = str(BACKEND / "data" / "demo10.db")
os.environ["HIS_JWT_SECRET"] = "demo10-secret-key-for-his-mvp-lesson10-0123456789"

from main import DB_PATH, app, get_connection, init_database  # noqa: E402
from seed_demo import seed_demo  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

if DB_PATH.exists():
    DB_PATH.unlink()
init_database()
conn = get_connection()
try:
    seed_demo(conn)
finally:
    conn.close()

client = TestClient(app)


def login(username, password):
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


print("=" * 66)
print("第 10 课 · 数据规范与集成 演示")
print("=" * 66)

# 1) 药品 CSV 批量导入（药师）
print("\n【1】药品 CSV 批量导入（药师 pharmacist）")
drugs_csv = (BACKEND / "data" / "drugs_import_demo.csv").read_bytes()
h = login("pharmacist", "Pharm@12345")
r = client.post("/api/drugs/import", files={"file": ("drugs.csv", drugs_csv, "text/csv")}, headers=h)
d = r.json()
print(f"  共 {d['total']} 行：成功 {d['success']} 条，失败 {d['fail']} 条")
for e in d["errors"][:5]:
    print(f"    第 {e['line']} 行失败：{e['reason']}")

# 2) 患者 CSV 批量导入（挂号员，身份证脱敏）
print("\n【2】患者 CSV 批量导入（挂号员 registrar，身份证脱敏）")
patients_csv = ("name,gender,birth_date,id_card,phone\n"
                "张三,男,1990-03-15,110101199003151234,13812345678\n"
                "李四,女,1985-07-20,110101198507201245,13912345678\n"
                "错误性别,外星人,1990-01-01,110101199001011234,13812345678\n")
h = login("registrar", "Reg@12345")
r = client.post("/api/import/patients",
                data={"csv_text": patients_csv}, headers=h)
p = r.json()
print(f"  成功 {p['success']} 条，失败 {p['failed']} 条")
for c in p["created_patients"]:
    print(f"    新建 {c['patient_no']} {c['name']} 身份证={c['id_card_masked']}")
for e in p["errors"]:
    print(f"    第 {e['row']} 行失败：{e['reason']}")

# 3) 操作审计日志（发一盒药后查得到）
print("\n【3】操作审计日志（中间件自动留痕）")
cash_h = login("cashier", "Cash@12345")
client.post("/api/pay", json={"prescription_id": 1, "request_id": "d10-req"}, headers=cash_h)
pharm_h = login("pharmacist", "Pharm@12345")
client.post("/api/dispense", json={"prescription_id": 1}, headers=pharm_h)

admin_h = login("admin", "Admin@123")
r = client.get("/api/audit-logs", params={"page_size": 6}, headers=admin_h)
logs = r.json()["items"]
print(f"  最近 {len(logs)} 条写操作审计：")
for lg in logs:
    print(f"    [{lg['action']}] user={lg['username'] or lg['user_id']} "
          f"entity_id={lg['entity_id']}  {lg['created_at']}")

# 4) 统计报表
print("\n【4】统计报表（今日）")
r = client.get("/api/report/daily", headers=admin_h)
rep = r.json()
print(f"  今日挂号量：{rep['reg_count']}  退号：{rep['reg_refund']}")
print(f"  今日收费金额：{rep['charge_cents']} 分  退费：{rep['refund_cents']} 分")
print(f"  今日发药数量：{rep['dispense_qty']}  开方量：{rep['prescription_count']}")

print("\n" + "=" * 66)
print("第 10 课三项（导入 / 审计 / 报表）全部跑通 ✓")
print("=" * 66)
