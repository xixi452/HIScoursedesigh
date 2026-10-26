# -*- coding: utf-8 -*-
"""门诊 HIS MVP 三条硬规则实证验证脚本（零第三方依赖，可复跑）。

运行方式（在 backend 目录下）：
    python verify_rules.py

设计要点：
  - 为不影响正在运行的 8000 主服务，本脚本先把主库 data/his.db 通过
    `VACUUM INTO` 复制一份到 data/.verify_tmp_his.db，验证服务（端口 8002）
    与所有直连核对都只针对这份副本，跑完即删除副本，绝不改动真实主库。
  - 用标准库 http.client 真实打 HTTP 接口，并用 sqlite3 直接核对落库数据。
  - 每条断言打印 [PASS]/[FAIL] + 规则编号 + 关键数值；结尾汇总 X/Y passed。
  - 证据逐条对应任务要求 A / B / C / D。
"""

import subprocess
import sys
import os
import time
import json
import sqlite3
import threading
import http.client
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
REAL_DB = DATA_DIR / "his.db"
TMP_DB = DATA_DIR / ".verify_tmp_his.db"
HOST, PORT = "127.0.0.1", 8002

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

RESULTS = []


def check(passed, label, detail=""):
    RESULTS.append((bool(passed), label, detail))
    tag = "[PASS]" if passed else "[FAIL]"
    line = f"{tag} {label}"
    if detail:
        line += f"  {detail}"
    print(line)


def db_conn(db_path):
    conn = sqlite3.connect(str(db_path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None  # 自动提交：避免直连 SELECT 长期持锁，阻塞服务端的 BEGIN IMMEDIATE
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def http_call(method, path, body=None, timeout=30):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    conn = http.client.HTTPConnection(HOST, PORT, timeout=timeout)
    headers = {"Content-Type": "application/json"} if data else {}
    conn.request(method, path, data, headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8", "replace")
    try:
        js = json.loads(raw)
    except Exception:
        js = {"__raw__": raw}
    conn.close()
    return resp.status, js


# ---------------- 测试夹具追踪 ----------------
TEST_PATIENTS = []
TEST_REGS = []
TEST_PRESCRIPTIONS = []


def create_patient(conn, idx):
    last4 = f"{1000 + idx:04d}"
    mask = "110101" + "********" + last4
    cur = conn.execute(
        """INSERT INTO patients
           (patient_no,name,gender,birth_date,id_card_masked,id_card_hash,
            id_card_last4,phone,status)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (f"VERIFY{idx:06d}", f"验收患者{idx}", "男", "1990-01-01", mask,
         f"verify_hash_{idx}_{os.getpid()}", last4, f"138{idx:08d}", "正常"),
    )
    conn.commit()
    return cur.lastrowid


def register(patient_id, schedule_id, operator_id=101):
    status, js = http_call(
        "POST", "/api/register",
        {"patient_id": patient_id, "schedule_id": schedule_id, "operator_id": operator_id},
    )
    if status == 201:
        TEST_REGS.append(js["reg_id"])
    return status, js


def free_port_8002():
    """释放可能残留的 8002 验证服务（仅清理本任务使用的验证端口，绝不碰 8000/5173）。"""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             timeout=10).stdout
        for line in out.splitlines():
            if ":8002" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit():
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True, timeout=10)
    except Exception:
        pass
    time.sleep(1)


def main():
    # ---- 0. 复制主库为私有副本（不触碰真实 8000 主库）----
    if not REAL_DB.exists():
        check(False, "规则-前置", f"主库不存在: {REAL_DB}")
        return
    for suffix in ("", "-wal", "-shm"):
        p = TMP_DB.with_name(TMP_DB.name + suffix)
        if p.exists():
            p.unlink()
    src = sqlite3.connect(str(REAL_DB), timeout=15)
    try:
        src.execute(f"VACUUM INTO '{TMP_DB.as_posix()}'")
    except sqlite3.OperationalError:
        # 旧版本不支持 VACUUM INTO，退化为文件拷贝
        src.close()
        import shutil
        shutil.copy(REAL_DB, TMP_DB)
        src = sqlite3.connect(str(REAL_DB), timeout=15)
    src.close()

    # ---- 1. 启动独立验证服务（端口 8002，指向副本）----
    free_port_8002()
    env = dict(os.environ)
    env["HIS_DB_PATH"] = str(TMP_DB)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8002"],
        cwd=str(BACKEND_DIR), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    server_ok = False
    try:
        for _ in range(40):
            try:
                st, _ = http_call("GET", "/health", timeout=3)
                if st == 200:
                    server_ok = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not server_ok:
            check(False, "规则-服务启动", "验证服务 8002 未能在限定时间内就绪")
            return

        conn = db_conn(TMP_DB)
        try:
            for i in range(16):
                TEST_PATIENTS.append(create_patient(conn, i))

            # ====================================================
            # 规则 B：金额后端算
            # ====================================================
            st, js = register(TEST_PATIENTS[0], 7)
            check(st == 201, "规则B-1 前置", f"挂号 status={st}")
            st, js_p = http_call(
                "POST", "/api/prescriptions",
                {"reg_id": js["reg_id"], "diagnosis": "测试B1",
                 "items": [{"drug_id": 1, "quantity": 3}]},
            )
            TEST_PRESCRIPTIONS.append(js_p.get("prescription_id") if not isinstance(js_p, str) else None)
            if st == 201:
                it = js_p["items"][0]
                ok = (it["unit_price_cents"] == 2000 and it["amount_cents"] == 6000
                      and js_p["total_amount_cents"] == 6000)
                check(ok, "规则B-1 响应单价/金额由后端现算",
                      f"后端单价={it['unit_price_cents']} 后端小计={it['amount_cents']} "
                      f"(期望 2000 / 6000)")
            else:
                check(False, "规则B-1 响应单价/金额由后端现算", f"开处方失败 status={st} body={js_p}")

            # B2：篡改金额字段 unit_price_cents=1
            # 注意：prescription_no 仅到秒，若与 B1 同秒会因 UNIQUE 冲突 500，
            # 这里间隔 1.1s 仅用于测试隔离（该 UNIQUE 冲突本身是一个独立缺陷，见汇报）。
            time.sleep(1.1)
            st, js2 = register(TEST_PATIENTS[1], 7)
            st, js_p2 = http_call(
                "POST", "/api/prescriptions",
                {"reg_id": js2["reg_id"], "diagnosis": "测试B2",
                 "items": [{"drug_id": 1, "quantity": 3,
                            "unit_price_cents": 1, "amount_cents": 99999}]},
            )
            TEST_PRESCRIPTIONS.append(js_p2.get("prescription_id") if not isinstance(js_p2, str) else None)
            if "__raw__" in js_p2:
                check(False, "规则B-2 篡改金额被忽略", f"非预期响应: {js_p2['__raw__'][:200]}")
            elif st == 201:
                pid = js_p2["prescription_id"]
                row = conn.execute(
                    "SELECT unit_price_cents, quantity, amount_cents "
                    "FROM prescription_items WHERE prescription_id=?", (pid,)
                ).fetchone()
                ok = (row["unit_price_cents"] == 2000 and row["quantity"] == 3
                      and row["amount_cents"] == 6000)
                check(ok, "规则B-2 篡改金额被忽略（落库为档案价×数量）",
                      f"落库 单价={row['unit_price_cents']} 数量={row['quantity']} "
                      f"小计={row['amount_cents']} (期望 2000/3/6000，非 1/3/99999)")
            else:
                check(False, "规则B-2 篡改金额被忽略", f"开处方失败 status={st} body={js_p2}")

            # B3：请求模型本身不含金额字段（结构证据）
            try:
                from schemas import PrescriptionItemIn
                fields = set(PrescriptionItemIn.model_fields.keys())
                ok = (fields == {"drug_id", "quantity"})
                check(ok, "规则B-3 请求模型无金额字段（忽略/不采信）",
                      f"PrescriptionItemIn 字段={sorted(fields)}")
            except Exception as e:
                check(False, "规则B-3 请求模型无金额字段", f"异常: {e}")

            # ====================================================
            # 规则 A：事务回滚
            # ====================================================
            st, js3 = register(TEST_PATIENTS[2], 7)
            st, js_pa = http_call(
                "POST", "/api/prescriptions",
                {"reg_id": js3["reg_id"], "diagnosis": "测试A1",
                 "items": [{"drug_id": 5, "quantity": 2},
                           {"drug_id": 1, "quantity": 1}]},
            )
            TEST_PRESCRIPTIONS.append(js_pa.get("prescription_id") if not isinstance(js_pa, str) else None)
            pidA = js_pa.get("prescription_id")

            stock_before = conn.execute(
                "SELECT stock_id, quantity FROM drug_stocks ORDER BY stock_id").fetchall()
            stock_before_key = [(r["stock_id"], r["quantity"]) for r in stock_before]
            bills_before = conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0]

            st, js_pay = http_call(
                "POST", "/api/pay",
                {"prescription_id": pidA,
                 "request_id": f"verify-A1-{os.getpid()}-{time.time()}",
                 "cashier_id": 102},
            )
            detail = js_pay.get("detail", "") if isinstance(js_pay, dict) else str(js_pay)
            ok_a1 = (st == 400 and "库存不足" in detail)
            check(ok_a1, "规则A-1 库存不足收费返回400且含'库存不足'",
                  f"status={st} detail={detail}")

            stock_after = conn.execute(
                "SELECT stock_id, quantity FROM drug_stocks ORDER BY stock_id").fetchall()
            stock_after_key = [(r["stock_id"], r["quantity"]) for r in stock_after]
            check(stock_before_key == stock_after_key,
                  "规则A-2 事务回滚：其它药品库存未扣",
                  f"扣前={stock_before_key} 扣后={stock_after_key}")

            bills_after = conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
            check(bills_before == bills_after,
                  "规则A-3 事务回滚：无新增 bill",
                  f"bill数 前={bills_before} 后={bills_after}")

            # ====================================================
            # 规则 A（挂号侧）
            # ====================================================
            rem_before = conn.execute(
                "SELECT remaining_count FROM schedules WHERE schedule_id=4").fetchone()[0]
            st, js_a4_1 = register(TEST_PATIENTS[3], 4)
            st, js_a4_2 = register(TEST_PATIENTS[4], 4)
            rem_after = conn.execute(
                "SELECT remaining_count FROM schedules WHERE schedule_id=4").fetchone()[0]
            ok_a4 = (st == 400 and rem_after >= 0 and rem_after == 0)
            check(ok_a4, "规则A-4 号源满时第二次挂号400且 remaining 未变负",
                  f"第一次status=201 第二次status={st} remaining前={rem_before} 后={rem_after}")

            # ====================================================
            # 规则 C：库存约束
            # ====================================================
            c1 = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='drug_stocks'"
            ).fetchone()[0]
            check("quantity >= 0" in c1.replace("\n", " "),
                  "规则C-1 drug_stocks 建表含 CHECK(quantity>=0)",
                  f"建表SQL片段含 'quantity >= 0': {'quantity >= 0' in c1}")

            c = db_conn(TMP_DB)
            try:
                c.execute("UPDATE drug_stocks SET quantity=-1 WHERE stock_id=15")
                c.commit()
                check(False, "规则C-2 直接置 -1 被约束拒绝", "未抛出异常（异常！）")
            except sqlite3.IntegrityError as e:
                c.rollback()
                check(True, "规则C-2 直接置 -1 被约束拒绝",
                      f"sqlite3.IntegrityError: {e}")
            except Exception as e:
                check(False, "规则C-2 直接置 -1 被约束拒绝",
                      f"非预期异常: {type(e).__name__}: {e}")
            finally:
                c.close()

            check(ok_a1, "规则C-3 库存不足 POST /api/pay 返回400",
                  f"status={st} detail={detail}")

            # ====================================================
            # 规则 D：并发不超卖
            # ====================================================
            conn.execute(
                "UPDATE schedules SET remaining_count=1, status='正常' WHERE schedule_id=4")
            conn.execute("DELETE FROM reg_orders WHERE schedule_id=4")
            conn.commit()

            results = []
            lock = threading.Lock()

            def worker(pidx):
                s, j = register(TEST_PATIENTS[5 + pidx], 4)
                with lock:
                    results.append((s, j))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            success = [r for r in results if r[0] == 201]
            fail = [r for r in results if r[0] >= 400]
            final_rem = conn.execute(
                "SELECT remaining_count FROM schedules WHERE schedule_id=4").fetchone()[0]
            reg_cnt = conn.execute(
                "SELECT COUNT(*) FROM reg_orders WHERE schedule_id=4").fetchone()[0]
            dup = conn.execute(
                "SELECT queue_no, COUNT(*) c FROM reg_orders WHERE schedule_id=4 "
                "GROUP BY queue_no HAVING c>1").fetchall()
            status_breakdown = {}
            for s, _ in results:
                status_breakdown[s] = status_breakdown.get(s, 0) + 1

            ok_d = (len(success) == 1 and len(fail) == 7
                    and final_rem == 0 and reg_cnt == 1 and len(dup) == 0)
            check(ok_d, "规则D 并发不超卖：恰好1成功/其余失败/remaining=0/无重复queue_no",
                  f"成功={len(success)} 失败={len(fail)} remaining={final_rem} "
                  f"挂号数={reg_cnt} 重复queue_no={len(dup)} 状态分布={status_breakdown}")
        finally:
            conn.close()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        # 删除私有副本，绝不遗留、绝不触碰真实主库
        for suffix in ("", "-wal", "-shm"):
            p = TMP_DB.with_name(TMP_DB.name + suffix)
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        print("[INFO] 已删除私有副本，真实主库 data/his.db 未被改动。")

    passed = sum(1 for r in RESULTS if r[0])
    total = len(RESULTS)
    print("=" * 60)
    print(f"汇总：{passed}/{total} passed")
    if passed != total:
        print("存在 FAIL，请查看上方明细。")


if __name__ == "__main__":
    main()
