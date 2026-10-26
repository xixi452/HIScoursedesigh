r"""初始化系统用户（含 bcrypt 密码哈希），可重复执行。

为 5 种角色各创建一个账号，密码使用 bcrypt 加盐哈希存储，绝不存明文。

演示账号（仅用于课程演示，上线前必须修改）：
    admin       / Admin@123
    registrar   / Reg@12345
    doctor      / Doc@12345
    cashier     / Cash@12345
    pharmacist  / Pharm@12345

用法：在 backend 目录下执行
    python seed_users.py
"""
import sqlite3

from main import DB_PATH, init_database
from security import hash_password

USERS = (
    # username, password, real_name, role_code
    ("admin", "Admin@123", "系统管理员", "admin"),
    ("registrar", "Reg@12345", "挂号员小王", "registrar"),
    ("doctor", "Doc@12345", "张医生", "doctor"),
    ("cashier", "Cash@12345", "收费员小李", "cashier"),
    ("pharmacist", "Pharm@12345", "药师小赵", "pharmacist"),
)


def seed_users() -> None:
    init_database()
    conn = sqlite3.connect(DB_PATH)
    try:
        for username, password, real_name, role_code in USERS:
            role_id = conn.execute(
                "SELECT role_id FROM roles WHERE role_code = ?", (role_code,)
            ).fetchone()[0]
            hashed = hash_password(password)
            conn.execute(
                "INSERT INTO sys_users (username, password_hash, real_name, role_id) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(username) DO UPDATE SET "
                "    password_hash = excluded.password_hash, "
                "    real_name = excluded.real_name, "
                "    role_id = excluded.role_id, "
                "    status = '启用'",
                (username, hashed, real_name, role_id),
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed_users()
    print("已初始化 5 个系统用户（密码已 bcrypt 哈希）：")
    for username, password, real_name, role_code in USERS:
        print(f"  {username:12s} / {password:12s}  角色={role_code}  姓名={real_name}")
