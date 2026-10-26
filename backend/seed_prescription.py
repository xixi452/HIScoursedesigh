r"""收费接口测试处方脚本，可重复执行。

每次运行：清除该测试处方的旧明细与旧账单，重建一张状态为“待收费”的
测试处方（含两条药品明细），最后打印 prescription_id 和推荐请求体。

用法：在 backend 目录下执行
    .venv\Scripts\python seed_prescription.py
"""
import sqlite3
from datetime import date, timedelta

from main import DB_PATH, init_database

DEPT_ID = 1
DOCTOR_ID = 1
PATIENT_ID = 1
OPERATOR_ID = 1
SCHEDULE_ID = 3
REG_NO = "GHSEED000001"
PRESCRIPTION_NO = "CFSEED0001"
DRUGS = (
    (1, "D1001", "阿莫西林胶囊", "0.25g*24粒", "胶囊", "盒", 2000, 2),
    (2, "D1002", "布洛芬片", "0.3g*20片", "片剂", "盒", 3500, 1),
)

init_database()
tomorrow = (date.today() + timedelta(days=1)).isoformat()

conn = sqlite3.connect(DB_PATH)
try:
    conn.execute(
        "INSERT OR IGNORE INTO departments (dept_id, dept_code, name) "
        "VALUES (?, 'D01', '测试内科')",
        (DEPT_ID,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO doctors (doctor_id, doctor_no, name, title, dept_id) "
        "VALUES (?, 'DOC001', '张测试', '主治医师', ?)",
        (DOCTOR_ID, DEPT_ID),
    )
    conn.execute(
        "INSERT OR IGNORE INTO patients (patient_id, patient_no, name, gender, birth_date, "
        "                               id_card_masked, id_card_hash, id_card_last4) "
        "VALUES (?, 'P00001', '王测试', '男', '1990-01-01', "
        "        '110101********0001', 'seed_hash_1', '0001')",
        (PATIENT_ID,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO sys_users (user_id, username, password_hash, real_name, role_id, dept_id) "
        "VALUES (?, 'admin', 'x', '管理员', 1, ?)",
        (OPERATOR_ID, DEPT_ID),
    )

    conn.execute(
        "INSERT INTO schedules (schedule_id, doctor_id, dept_id, work_date, time_slot, "
        "                       reg_level, fee_cents, total_count, remaining_count) "
        "VALUES (?, ?, ?, ?, '下午', '普通号', 1500, 10, 10) "
        "ON CONFLICT(schedule_id) DO UPDATE SET "
        "    work_date = excluded.work_date, "
        "    total_count = 10, remaining_count = 10, status = '正常'",
        (SCHEDULE_ID, DOCTOR_ID, DEPT_ID, tomorrow),
    )

    conn.execute(
        "INSERT OR IGNORE INTO reg_orders (reg_no, patient_id, doctor_id, dept_id, "
        "                                  schedule_id, queue_no, fee_cents, status, operator_id) "
        "VALUES (?, ?, ?, ?, ?, 1, 1500, '候诊', ?)",
        (REG_NO, PATIENT_ID, DOCTOR_ID, DEPT_ID, SCHEDULE_ID, OPERATOR_ID),
    )
    reg_id = conn.execute(
        "SELECT reg_id FROM reg_orders WHERE reg_no = ?", (REG_NO,)
    ).fetchone()[0]

    for drug_id, code, name, spec, form, unit, price, _qty in DRUGS:
        conn.execute(
            "INSERT OR IGNORE INTO drugs (drug_id, drug_code, generic_name, spec, dosage_form, unit, price_cents) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (drug_id, code, name, spec, form, unit, price),
        )

    conn.execute(
        "DELETE FROM bills WHERE prescription_id = "
        "(SELECT prescription_id FROM prescriptions WHERE prescription_no = ?)",
        (PRESCRIPTION_NO,),
    )
    conn.execute(
        "DELETE FROM prescription_items WHERE prescription_id = "
        "(SELECT prescription_id FROM prescriptions WHERE prescription_no = ?)",
        (PRESCRIPTION_NO,),
    )
    conn.execute(
        "INSERT INTO prescriptions (prescription_no, reg_id, patient_id, doctor_id, "
        "                           diagnosis, status, total_amount_cents) "
        "VALUES (?, ?, ?, ?, '上呼吸道感染', '待收费', 0) "
        "ON CONFLICT(prescription_no) DO UPDATE SET "
        "    reg_id = excluded.reg_id, "
        "    patient_id = excluded.patient_id, "
        "    doctor_id = excluded.doctor_id, "
        "    diagnosis = excluded.diagnosis, "
        "    status = '待收费', total_amount_cents = 0",
        (PRESCRIPTION_NO, reg_id, PATIENT_ID, DOCTOR_ID),
    )
    prescription_id = conn.execute(
        "SELECT prescription_id FROM prescriptions WHERE prescription_no = ?",
        (PRESCRIPTION_NO,),
    ).fetchone()[0]

    total = 0
    for drug_id, code, name, spec, form, unit, price, qty in DRUGS:
        conn.execute(
            "INSERT INTO prescription_items (prescription_id, drug_id, quantity, "
            "                                unit_price_cents, amount_cents) "
            "VALUES (?, ?, ?, ?, ?)",
            (prescription_id, drug_id, qty, price, qty * price),
        )
        total += qty * price

    conn.commit()
finally:
    conn.close()

print(f"prescription_id = {prescription_id}")
print(f"明细金额合计 = {total} 分")
print(f"Swagger 请求体: {{\"prescription_id\": {prescription_id}, \"request_id\": \"req-test-{prescription_id}\"}}")
