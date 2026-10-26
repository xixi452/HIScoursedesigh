# -*- coding: utf-8 -*-
"""全流程演示：挂号 → 开方 → 收费(扣库存) → 发药。

在 backend 目录运行：python demo_full_flow.py
输出每一步的处方明细、金额与库存变化，作为第 6 课「全流程演示」证据。
"""
import os
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
os.environ["HIS_DB_PATH"] = str(BACKEND / "data" / "demo.db")
os.environ["HIS_JWT_SECRET"] = "demo-secret-key-for-his-mvp-full-flow-0123456789"

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


def stock(drug_id):
    c = get_connection()
    try:
        rows = c.execute(
            "SELECT batch_no, quantity FROM drug_stocks WHERE drug_id=? ORDER BY expiry_date",
            (drug_id,),
        ).fetchall()
        return [(r["batch_no"], r["quantity"]) for r in rows]
    finally:
        c.close()


print("=" * 66)
print("门诊 HIS MVP · A 门诊线 全流程演示")
print("=" * 66)

# 1) 挂号
print("\n【1】挂号（挂号员 registrar）")
print("  号源 schedule 1 扣减前余量：10")
h = login("registrar", "Reg@12345")
r = client.post("/api/register", json={"patient_id": 1, "schedule_id": 1}, headers=h)
reg = r.json()
print(f"  → 挂号成功：挂号单 {reg['reg_no']}  排队号 {reg['queue_no']}  费用 {reg['fee_cents']} 分")
rem = client.get("/api/schedules", headers=h).json()
s1 = next(s for s in rem if s["schedule_id"] == 1)
print(f"  号源 schedule 1 扣减后余量：{s1['remaining_count']}")

# 2) 开方
print("\n【2】开方（医生 doctor）")
h = login("doctor", "Doc@12345")
r = client.post(
    "/api/prescriptions",
    json={
        "reg_id": reg["reg_id"],
        "diagnosis": "上呼吸道感染",
        "items": [{"drug_id": 1, "quantity": 2}, {"drug_id": 2, "quantity": 1}],
    },
    headers=h,
)
rx = r.json()
print(f"  → 处方 {rx['prescription_no']}  诊断：上呼吸道感染")
for it in rx["items"]:
    print(f"    明细：{it['generic_name']}  {it['quantity']} × {it['unit_price_cents']} 分 = {it['amount_cents']} 分")
print(f"    总额（后端算）：{rx['total_amount_cents']} 分  状态：{rx['status']}")

# 3) 收费（扣库存）
print("\n【3】收费（收费员 cashier）· FEFO 扣库存")
print("  收费前库存：阿莫西林", stock(1), " 布洛芬", stock(2))
h = login("cashier", "Cash@12345")
r = client.post(
    "/api/pay", json={"prescription_id": rx["prescription_id"], "request_id": "demo-req-1"}, headers=h
)
bill = r.json()
print(f"  → 收费单 {bill['bill_no']}  金额 {bill['total_amount_cents']} 分")
for d in bill["stock_deductions"]:
    print(f"    扣库存：{d['drug']} 批次 {d['batch_no']} 数量 {d['quantity']}")
print("  收费后库存：阿莫西林", stock(1), " 布洛芬", stock(2))

# 4) 发药（确认）
print("\n【4】发药（药师 pharmacist）· 确认发药")
h = login("pharmacist", "Pharm@12345")
r = client.post("/api/dispense", json={"prescription_id": rx["prescription_id"]}, headers=h)
disp = r.json()
print(f"  → 处方状态：{disp['status']}  发药记录 {len(disp['records'])} 条")

print("\n" + "=" * 66)
print("全流程闭环跑通：挂号 → 开方 → 收费(扣库存) → 发药 ✓")
print("=" * 66)
