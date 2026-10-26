r"""挂号接口测试数据脚本，可重复执行（每次运行会重置排班号源的余量）。

用法：在 backend 目录下执行
    .venv\Scripts\python seed_test_data.py
"""
import sqlite3
from datetime import date, timedelta

from main import DB_PATH, init_database

DEPT_ID = 1
DOCTOR_ID = 1
PATIENT_ID = 1
OPERATOR_ID = 1
SCHEDULE_ID = 2

init_database()

tomorrow = (date.today() + timedelta(days=1)).isoformat()

conn = sqlite3.connect(DB_PATH)
try:
    conn.execute(
        "INSERT OR IGNORE INTO departments (dept_id, dept_code, name, location) "
        "VALUES (?, 'D01', '测试内科', '1号楼2层')",
        (DEPT_ID,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO doctors (doctor_id, doctor_no, name, title, dept_id) "
        "VALUES (?, 'DOC001', '张测试', '主治医师', ?)",
        (DOCTOR_ID, DEPT_ID),
    )
    conn.execute(
        "INSERT OR IGNORE INTO patients (patient_id, patient_no, name, gender, birth_date, "
        "                               id_card_masked, id_card_hash, id_card_last4, phone) "
        "VALUES (?, 'P00001', '王测试', '男', '1990-01-01', "
        "        '110101********0001', 'seed_hash_1', '0001', '13800000001')",
        (PATIENT_ID,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO sys_users (user_id, username, password_hash, real_name, role_id, dept_id) "
        "VALUES (?, 'admin', 'x', '管理员', 1, ?)",
        (OPERATOR_ID, DEPT_ID),
    )

    conn.execute("DELETE FROM reg_orders WHERE schedule_id = ?", (SCHEDULE_ID,))
    conn.execute(
        "INSERT INTO schedules (schedule_id, doctor_id, dept_id, work_date, time_slot, "
        "                       reg_level, fee_cents, total_count, remaining_count) "
        "VALUES (?, ?, ?, ?, '上午', '普通号', 1500, 10, 10) "
        "ON CONFLICT(schedule_id) DO UPDATE SET "
        "    work_date = excluded.work_date, "
        "    total_count = excluded.total_count, "
        "    remaining_count = excluded.remaining_count, "
        "    status = '正常'",
        (SCHEDULE_ID, DOCTOR_ID, DEPT_ID, tomorrow),
    )
    conn.commit()
finally:
    conn.close()

print(f"DB: {DB_PATH}")
print(f"排班日期（明天）: {tomorrow}")
print(f"patient_id={PATIENT_ID}  schedule_id={SCHEDULE_ID}  operator_id={OPERATOR_ID}")
print('请求体: {"patient_id": %d, "schedule_id": %d, "operator_id": %d}' % (PATIENT_ID, SCHEDULE_ID, OPERATOR_ID))
