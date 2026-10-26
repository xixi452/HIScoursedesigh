"""演示数据完整种子：用户 + 科室/医生/患者/号源/药品/库存 + 一张待收费处方。

供单元/接口测试（tests/conftest.py）与 E2E 复用，保证两套环境数据一致。

演示账号（bcrypt 哈希，仅课程演示，上线前必须改）：
    admin / Admin@123     registrar / Reg@12345   doctor / Doc@12345
    cashier / Cash@12345  pharmacist / Pharm@12345
"""
from datetime import date, timedelta

from security import hash_password

USERS = (
    (1, "admin", "Admin@123", "系统管理员", "admin"),
    (2, "registrar", "Reg@12345", "挂号员小王", "registrar"),
    (3, "doctor", "Doc@12345", "张医生", "doctor"),
    (4, "cashier", "Cash@12345", "收费员小李", "cashier"),
    (5, "pharmacist", "Pharm@12345", "药师小赵", "pharmacist"),
)


def seed_demo(conn) -> None:
    """向一个已初始化 schema 的连接写入完整演示数据。"""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # 1) 用户（bcrypt 哈希密码）
    for user_id, username, password, real_name, role_code in USERS:
        role_id = conn.execute(
            "SELECT role_id FROM roles WHERE role_code = ?", (role_code,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO sys_users (user_id, username, password_hash, real_name, role_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, hash_password(password), real_name, role_id),
        )

    # 2) 科室、医生、患者
    conn.execute(
        "INSERT INTO departments (dept_id, dept_code, name, location) "
        "VALUES (1, 'D01', '测试内科', '1号楼2层')"
    )
    conn.execute(
        "INSERT INTO doctors (doctor_id, doctor_no, name, title, dept_id) "
        "VALUES (1, 'DOC001', '张医生', '主治医师', 1)"
    )
    conn.execute(
        "INSERT INTO patients (patient_id, patient_no, name, gender, birth_date, "
        "                       id_card_masked, id_card_hash, id_card_last4, phone) "
        "VALUES (1, 'P00001', '王患者', '男', '1990-01-01', "
        "        '110101********0001', 'test_hash_1', '0001', '13800000001')"
    )

    # 3) 号源：schedule 1 余量充足；schedule 2 余量 1；schedule 3 余量 0（竞态窗口，供 409）
    for sid, slot, total, remaining in (
        (1, "上午", 10, 10),
        (2, "下午", 1, 1),
        (3, "夜间", 1, 0),
    ):
        conn.execute(
            "INSERT INTO schedules (schedule_id, doctor_id, dept_id, work_date, time_slot, "
            "                           reg_level, fee_cents, total_count, remaining_count, status) "
            "VALUES (?, 1, 1, ?, ?, '普通号', 1500, ?, ?, '正常')",
            (sid, tomorrow, slot, total, remaining),
        )

    # 4) 药品（drug 3 停用，供"停用药品不可开方"测试）
    conn.execute(
        "INSERT INTO drugs (drug_id, drug_code, generic_name, spec, dosage_form, unit, price_cents) VALUES "
        "(1, 'D1001', '阿莫西林胶囊', '0.25g*24粒', '胶囊', '盒', 2000),"
        "(2, 'D1002', '布洛芬片', '0.3g*20片', '片剂', '盒', 3500),"
        "(3, 'D1003', '已停用药品', '10mg*10片', '片剂', '盒', 1000)"
    )
    conn.execute("UPDATE drugs SET status = '停用' WHERE drug_id = 3")

    # 5) 库存（FEFO 验证用，多批次不同效期）
    conn.execute(
        "INSERT INTO drug_stocks (drug_id, batch_no, production_date, expiry_date, quantity, location, status) VALUES "
        "(1, 'AMX202701', '2026-01-10', '2027-01-31', 1, 'A-01', '正常'),"
        "(1, 'AMX202706', '2026-06-10', '2027-06-30', 5, 'A-01', '正常'),"
        "(2, 'BLF202612', '2025-12-10', '2026-12-31', 1, 'B-01', '正常'),"
        "(2, 'BLF202808', '2027-08-10', '2028-08-31', 4, 'B-02', '正常')"
    )

    # 6) 一张待收费处方（prescription_id=1），供收费/发药测试。
    #    挂号单挂在 schedule 2 上，保证 schedule 1 干净，挂号用例排队号从 1 开始。
    conn.execute(
        "INSERT INTO reg_orders (reg_id, reg_no, patient_id, doctor_id, dept_id, "
        "                           schedule_id, queue_no, fee_cents, status, operator_id) "
        "VALUES (1, 'GH-TEST-0001', 1, 1, 1, 2, 1, 1500, '候诊', 2)"
    )
    conn.execute(
        "INSERT INTO prescriptions (prescription_id, prescription_no, reg_id, patient_id, "
        "                              doctor_id, diagnosis, status, total_amount_cents) "
        "VALUES (1, 'CF-TEST-0001', 1, 1, 1, '上呼吸道感染', '待收费', 7500)"
    )
    conn.execute(
        "INSERT INTO prescription_items (prescription_id, drug_id, quantity, unit_price_cents, amount_cents) VALUES "
        "(1, 1, 2, 2000, 4000),"
        "(1, 2, 1, 3500, 3500)"
    )
    conn.commit()
