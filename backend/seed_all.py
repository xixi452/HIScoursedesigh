# -*- coding: utf-8 -*-
"""部署启动种子（第 9 课）：建表 + 五角色账号 + 演示业务数据，幂等可重复执行。

Render / Docker 启动后端前先跑本脚本，保证公网实例一打开就能走完 6 节点演示。
"""
from main import init_database, get_connection
from seed_users import seed_users
from seed_schedules import seed as seed_schedules


def seed_patient(conn) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO patients (patient_id, patient_no, name, gender, birth_date, "
        "                                  id_card_masked, id_card_hash, id_card_last4, phone) "
        "VALUES (1, 'P00001', '王患者', '男', '1990-01-01', "
        "        '110101********0001', 'demo_hash_1', '0001', '13800000001')"
    )
    conn.commit()


def main() -> None:
    init_database()          # 建表 + 角色/权限种子
    seed_users()             # admin/registrar/doctor/cashier/pharmacist（bcrypt）
    seed_schedules()         # 科室/医生/排班/药品/库存
    conn = get_connection()
    try:
        seed_patient(conn)   # 演示患者
    finally:
        conn.close()
    print("部署种子完成：5 账号 + 3科室/8医生/排班 + 药品/库存 + 1 患者")


if __name__ == "__main__":
    main()
