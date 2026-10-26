r"""批量生成门诊排班表 + 基础依赖 + 药品档案 + 库存批次演示数据，可重复执行。

生成内容：
- 3 个科室（内科 D01 / 外科 D02 / 儿科 D03），每科室 2~3 名医生；
- 未来 3 天 × 上午/下午 × 号别（普通号/专家号/急诊号）批量排班；
- 依赖数据：roles + role_permissions + sys_users（收费员/药师/挂号员）、
  departments、doctors；
- 药品档案 drugs（price_cents 为整数分，便于口算核对）+ 库存批次 drug_stocks；
- 临界值场景，满足三条硬规则：
  硬规则1（事务回滚）：造 1 个 remaining_count=1 的号源；
  硬规则2（金额由后端算）：打印“药品 × 数量 = 金额”对照表；
  硬规则3（库存≥0、400拦截）：所有 quantity≥0，蒙脱石散总可用仅 1 盒。

运行方式：
    cd backend && python seed_schedules.py
"""
import sqlite3
from datetime import date, timedelta

from main import DB_PATH, init_database
from security import hash_password

# ---------- 基础依赖数据 ----------
DEPARTMENTS = [
    (1, "D01", "内科", "1号楼2层"),
    (2, "D02", "外科", "2号楼3层"),
    (3, "D03", "儿科", "3号楼1层"),
]

# doctor_id, doctor_no, name, title, dept_id, specialty
DOCTORS = [
    (11, "DOC011", "李建国", "主任医师", 1, "呼吸内科"),
    (12, "DOC012", "王淑芬", "副主任医师", 1, "消化内科"),
    (13, "DOC013", "赵明", "主治医师", 1, "心血管内科"),
    (14, "DOC014", "孙伟", "主任医师", 2, "普外科"),
    (15, "DOC015", "周涛", "副主任医师", 2, "骨科"),
    (16, "DOC016", "吴磊", "主治医师", 2, "泌尿外科"),
    (17, "DOC017", "郑华", "主任医师", 3, "小儿呼吸"),
    (18, "DOC018", "冯丽", "副主任医师", 3, "小儿消化"),
]

# roles + role_permissions（已存在于 SEED_SQL，这里 INSERT OR IGNORE 兜底）
ROLES = [
    (2, "registrar", "挂号员"),
    (4, "cashier", "收费员"),
    (5, "pharmacist", "药师"),
]
ROLE_PERMISSIONS = [
    (2, 5), (2, 7),          # 挂号员：挂号、挂号查询
    (4, 12), (4, 14),        # 收费员：收费、收费查询
    (5, 15), (5, 18),        # 药师：发药、库存查询
]

# sys_users（user_id, username, password_hash, real_name, role_id, dept_id）
SYS_USERS = [
    (101, "reg01", "seed_pwd", "挂号员小陈", 2, 1),
    (102, "cashier01", "seed_pwd", "收费员小钱", 4, 1),
    (103, "pharma01", "seed_pwd", "药师小孙", 5, 1),
]

# ---------- 排班规则 ----------
SLOTS = ["上午", "下午"]
LEVELS = [("普通号", 20, 1500), ("专家号", 10, 3000), ("急诊号", 5, 5000)]  # 号别, total, fee
DAYS_AHEAD = [1, 2, 3]
# 硬规则1：下列排班造为 total=1, remaining=1（演示第二次挂号触发回滚）
CRITICAL = (11, 1, "上午", "普通号")

# ---------- 药品档案（硬规则2：整数分，便于口算） ----------
DRUGS = [
    (3, "D1003", "头孢呋辛酯片", "0.25g*12片", "片剂", "盒", 2000),
    (4, "D1004", "蒲地蓝消炎口服液", "10ml*10支", "口服液", "盒", 3500),
    (5, "D1005", "蒙脱石散", "3g*10袋", "散剂", "盒", 1200),
]

# ---------- 库存批次（硬规则3：quantity≥0；≥2 效期批次；蒙脱石散仅 1 盒） ----------
DRUG_STOCKS = [
    # drug_id, batch_no, production_date, expiry_date, quantity, location
    (3, "CFX202701", "2026-01-20", "2027-01-31", 20, "C-01"),
    (3, "CFX202801", "2027-01-20", "2028-01-31", 15, "C-02"),
    (4, "PDL202706", "2026-06-20", "2027-06-30", 10, "P-01"),
    (4, "PDL202806", "2027-06-20", "2028-06-30", 8, "P-02"),
    (5, "MTS202612", "2025-12-20", "2026-12-31", 1, "M-01"),   # 仅 1 盒，演示 400
    (5, "MTS202712", "2026-12-20", "2027-12-31", 0, "M-02"),   # 第二效期批次（空）
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def seed():
    init_database()
    conn = get_conn()
    try:
        # ---- 科室（D01 已存在则改名，其余插入）----
        for dept_id, code, name, loc in DEPARTMENTS:
            conn.execute(
                "INSERT OR IGNORE INTO departments (dept_id, dept_code, name, location) "
                "VALUES (?, ?, ?, ?)",
                (dept_id, code, name, loc),
            )
            conn.execute(
                "UPDATE departments SET name=?, location=? WHERE dept_id=?",
                (name, loc, dept_id),
            )

        # ---- 角色与权限（兜底）----
        for role_id, code, rname in ROLES:
            conn.execute(
                "INSERT OR IGNORE INTO roles (role_id, role_code, role_name) "
                "VALUES (?, ?, ?)",
                (role_id, code, rname),
            )
        for role_id, perm_id in ROLE_PERMISSIONS:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) "
                "VALUES (?, ?)",
                (role_id, perm_id),
            )

        # ---- 系统用户（收费员/药师/挂号员，密码 bcrypt 哈希）----
        for uid, uname, pwd, real, role_id, dept_id in SYS_USERS:
            conn.execute(
                "INSERT INTO sys_users "
                "(user_id, username, password_hash, real_name, role_id, dept_id) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(username) DO UPDATE SET "
                "    password_hash = excluded.password_hash, "
                "    real_name = excluded.real_name, "
                "    role_id = excluded.role_id, "
                "    dept_id = excluded.dept_id, "
                "    status = '启用'",
                (uid, uname, hash_password(pwd), real, role_id, dept_id),
            )

        # ---- 医生 ----
        for doc_id, no, name, title, dept_id, spec in DOCTORS:
            conn.execute(
                "INSERT OR IGNORE INTO doctors "
                "(doctor_id, doctor_no, name, title, dept_id, specialty) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (doc_id, no, name, title, dept_id, spec),
            )

        # ---- 批量排班（循环 INSERT，幂等用 ON CONFLICT DO UPDATE）----
        n = 0
        for doc_id, _no, _name, _title, dept_id, _spec in DOCTORS:
            for d in DAYS_AHEAD:
                work_date = (date.today() + timedelta(days=d)).isoformat()
                for slot in SLOTS:
                    for level, total, fee in LEVELS:
                        # 硬规则1：临界号源
                        if (doc_id, d, slot, level) == CRITICAL:
                            total, remaining = 1, 1
                        else:
                            remaining = total
                        conn.execute(
                            "INSERT INTO schedules "
                            "(doctor_id, dept_id, work_date, time_slot, reg_level, "
                            " fee_cents, total_count, remaining_count) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT(doctor_id, work_date, time_slot, reg_level) "
                            "DO UPDATE SET "
                            "   dept_id = excluded.dept_id, "
                            "   fee_cents = excluded.fee_cents, "
                            "   total_count = excluded.total_count, "
                            "   remaining_count = excluded.remaining_count, "
                            "   status = '正常', version = schedules.version + 1",
                            (doc_id, dept_id, work_date, slot, level,
                             fee, total, remaining),
                        )
                        n += 1

        # ---- 药品档案 ----
        for drug_id, code, name, spec, form, unit, price in DRUGS:
            conn.execute(
                "INSERT OR IGNORE INTO drugs "
                "(drug_id, drug_code, generic_name, spec, dosage_form, unit, price_cents) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (drug_id, code, name, spec, form, unit, price),
            )

        # ---- 库存批次（幂等用 ON CONFLICT DO UPDATE）----
        for drug_id, batch, prod, expiry, qty, loc in DRUG_STOCKS:
            conn.execute(
                "INSERT INTO drug_stocks "
                "(drug_id, batch_no, production_date, expiry_date, quantity, location, status) "
                "VALUES (?, ?, ?, ?, ?, ?, '正常') "
                "ON CONFLICT(drug_id, batch_no) DO UPDATE SET "
                "   expiry_date = excluded.expiry_date, "
                "   quantity = excluded.quantity, "
                "   location = excluded.location, "
                "   status = '正常', version = drug_stocks.version + 1",
                (drug_id, batch, prod, expiry, qty, loc),
            )

        conn.commit()
    finally:
        conn.close()
    return n


def report(schedule_count: int):
    conn = get_conn()
    try:
        avail = conn.execute("SELECT COUNT(*) AS n FROM v_available_schedules").fetchone()["n"]
        sched_total = conn.execute("SELECT COUNT(*) AS n FROM schedules").fetchone()["n"]
        min_rem = conn.execute("SELECT MIN(remaining_count) AS m FROM schedules").fetchone()["m"]
        min_qty = conn.execute("SELECT MIN(quantity) AS m FROM drug_stocks").fetchone()["m"]

        # 临界号源 schedule_id
        crit = conn.execute(
            "SELECT schedule_id FROM schedules "
            "WHERE doctor_id=? AND work_date=? AND time_slot=? AND reg_level=?",
            (CRITICAL[0],
             (date.today() + timedelta(days=CRITICAL[1])).isoformat(),
             CRITICAL[2], CRITICAL[3]),
        ).fetchone()
        crit_id = crit["schedule_id"] if crit else None

        # 库存仅 1 盒的药品
        one_box = conn.execute(
            "SELECT ds.drug_id AS drug_id, dr.generic_name AS generic_name, "
            "SUM(ds.quantity) AS total "
            "FROM drug_stocks ds JOIN drugs dr ON dr.drug_id = ds.drug_id "
            "GROUP BY ds.drug_id HAVING total = 1 LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    print("=" * 56)
    print("【硬规则2】药品 × 数量 = 金额 对照表（price_cents 由后端计算）")
    print("-" * 56)
    print(f"{'药品':<14}{'单价(分)':>10}{'数量':>6}{'金额(分)':>10}")
    for _id, _c, name, _s, _f, _u, price in DRUGS:
        for q in (1, 2, 3):
            print(f"{name:<14}{price:>10}{q:>6}{price * q:>10}")
    print("-" * 56)

    print("【生成统计】")
    print(f"  本次循环写入排班条数(含幂等覆盖): {schedule_count}")
    print(f"  schedules 总条数: {sched_total}")
    print(f"  v_available_schedules(未来日期生效): {avail}")
    print(f"  schedules.remaining_count 最小值: {min_rem}  (硬规则1: ≥0)")
    print(f"  drug_stocks.quantity 最小值: {min_qty}  (硬规则3: ≥0)")

    print("【演示关键 ID】")
    print(f"  号源=1 的 schedule_id(第二次挂号演示回滚): {crit_id}")
    if one_box:
        print(f"  库存仅1盒的药品 drug_id={one_box['drug_id']} "
              f"({one_box['generic_name']})，处方要2盒→收费被400拦截")
    print("=" * 56)


if __name__ == "__main__":
    count = seed()
    report(count)
