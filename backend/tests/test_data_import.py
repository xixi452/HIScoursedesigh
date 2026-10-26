"""第 10 课测试：药品 CSV 导入、操作审计日志、统计报表。"""


class TestDrugImport:
    CSV = (
        "药品编码,通用名,商品名,规格,剂型,单位,单价,医保类别,库存数量\n"
        "D20001,测试药A,某品牌A,0.25g*24粒,胶囊,盒,20.50,乙类,100\n"
        "D20002,测试药B,,10mg*30片,片剂,盒,35.00,甲类,200\n"
        "D20003,非法单价药,,5ml*10,口服液体剂,瓶,abc,乙类,60\n"
        "D20004,缺规格药,,,胶囊,盒,12.00,乙类,80\n"
    )

    def test_import_partial_success(self, client, auth):
        h = auth("pharmacist", "Pharm@12345")
        files = {"file": ("drugs.csv", self.CSV.encode("utf-8"), "text/csv")}
        r = client.post("/api/drugs/import", files=files, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 4
        assert body["success"] == 2
        assert body["fail"] == 2
        reasons = [e["reason"] for e in body["errors"]]
        assert any("单价非法" in x for x in reasons)
        assert any("规格缺失" in x for x in reasons)

    def test_import_writes_valid_rows_only(self, client, auth):
        h = auth("pharmacist", "Pharm@12345")
        files = {"file": ("drugs.csv", self.CSV.encode("utf-8"), "text/csv")}
        client.post("/api/drugs/import", files=files, headers=h)

        import main

        conn = main.get_connection()
        try:
            good = conn.execute(
                "SELECT COUNT(*) FROM drugs WHERE drug_code IN ('D20001','D20002')"
            ).fetchone()[0]
            bad = conn.execute(
                "SELECT COUNT(*) FROM drugs WHERE drug_code IN ('D20003','D20004')"
            ).fetchone()[0]
        finally:
            conn.close()
        assert good == 2
        assert bad == 0

    def test_import_requires_permission(self, client, auth):
        # 医生无权导入药品（需 pharmacy:stock_in）
        h = auth("doctor", "Doc@12345")
        files = {"file": ("drugs.csv", self.CSV.encode("utf-8"), "text/csv")}
        r = client.post("/api/drugs/import", files=files, headers=h)
        assert r.status_code == 403


class TestAuditLog:
    def test_write_op_is_audited(self, client, auth):
        # 发一盒药：先收费再发药，日志里应能查到"发药"
        cash_h = auth("cashier", "Cash@12345")
        client.post("/api/pay", json={"prescription_id": 1, "request_id": "req-audit"}, headers=cash_h)
        pharm_h = auth("pharmacist", "Pharm@12345")
        client.post("/api/dispense", json={"prescription_id": 1}, headers=pharm_h)

        admin_h = auth("admin", "Admin@123")
        r = client.get("/api/audit-logs", params={"action": "发药"}, headers=admin_h)
        assert r.status_code == 200
        logs = r.json()["items"]
        assert len(logs) >= 1
        # 发药日志记录了处方 ID（entity_id）
        assert logs[0]["action"] == "发药"
        assert logs[0]["entity_id"] == "1"

    def test_audit_filter_by_action(self, client, auth):
        reg_h = auth("registrar", "Reg@12345")
        client.post("/api/register", json={"patient_id": 1, "schedule_id": 1}, headers=reg_h)

        admin_h = auth("admin", "Admin@123")
        r = client.get("/api/audit-logs", params={"action": "挂号"}, headers=admin_h)
        assert r.status_code == 200
        assert all(x["action"] == "挂号" for x in r.json()["items"])

    def test_audit_requires_admin(self, client, auth):
        h = auth("cashier", "Cash@12345")
        r = client.get("/api/audit-logs", headers=h)
        assert r.status_code == 403


class TestDailyReport:
    def test_report_today(self, client, auth):
        # 挂号 + 收费后查今日报表
        reg_h = auth("registrar", "Reg@12345")
        client.post("/api/register", json={"patient_id": 1, "schedule_id": 1}, headers=reg_h)

        cash_h = auth("cashier", "Cash@12345")
        client.post("/api/pay", json={"prescription_id": 1, "request_id": "req-report"}, headers=cash_h)

        admin_h = auth("admin", "Admin@123")
        r = client.get("/api/report/daily", headers=admin_h)
        assert r.status_code == 200
        body = r.json()
        assert body["reg_count"] >= 1
        assert body["charge_cents"] >= 7500


class TestPatientImport:
    CSV = (
        "name,gender,birth_date,id_card,phone\n"
        "张三,男,1990-03-15,110101199003151234,13812345678\n"
        "李四,女,1985-07-20,110101198507201245,13912345678\n"
        "错误性别,外星人,1990-01-01,110101199001011234,13812345678\n"
        "缺身份证,,1990-01-01,,13812345678\n"
    )

    def test_import_masks_id_card(self, client, auth):
        h = auth("registrar", "Reg@12345")
        files = {"file": ("patients.csv", self.CSV.encode("utf-8"), "text/csv")}
        r = client.post("/api/import/patients", files=files, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] == 2
        assert body["failed"] == 2

        # 身份证脱敏入库：绝不落完整号
        import main

        conn = main.get_connection()
        try:
            row = conn.execute(
                "SELECT id_card_masked, id_card_last4 FROM patients WHERE name='张三'"
            ).fetchone()
        finally:
            conn.close()
        assert row["id_card_masked"] == "110101********1234"
        assert row["id_card_last4"] == "1234"

    def test_import_dedupe(self, client, auth):
        h = auth("registrar", "Reg@12345")
        files = {"file": ("patients.csv", self.CSV.encode("utf-8"), "text/csv")}
        client.post("/api/import/patients", files=files, headers=h)
        # 再次导入：身份证重复 → 记失败
        r = client.post("/api/import/patients", files=files, headers=h)
        body = r.json()
        assert any("已在库中存在" in e["reason"] for e in body["errors"])

    def test_import_requires_permission(self, client, auth):
        h = auth("cashier", "Cash@12345")
        files = {"file": ("patients.csv", self.CSV.encode("utf-8"), "text/csv")}
        r = client.post("/api/import/patients", files=files, headers=h)
        assert r.status_code == 403
