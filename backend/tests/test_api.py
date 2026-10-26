"""API 接口测试（FastAPI TestClient，基于 04 版完整闭环）。

覆盖：登录认证、JWT 鉴权（401/403 越权拦截）、挂号（201/404/409）、
开方（服务端计价/停用药品拦截）、收费（幂等 + FEFO 扣库存）、发药（确认）、
以及"挂号→开方→收费→发药"全链路。状态码均有断言。
"""


# ================================================================ 登录认证
class TestLogin:
    def test_login_success(self, client):
        r = client.post("/api/login", json={"username": "cashier", "password": "Cash@12345"})
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"]
        assert body["user"]["role_code"] == "cashier"

    def test_login_wrong_password(self, client):
        r = client.post("/api/login", json={"username": "cashier", "password": "wrong"})
        assert r.status_code == 401

    def test_login_unknown_user_same_message(self, client):
        r = client.post("/api/login", json={"username": "no_such", "password": "x"})
        assert r.status_code == 401
        assert r.json()["detail"] == "用户名或密码错误"

    def test_login_disabled(self, client):
        import main

        conn = main.get_connection()
        conn.execute("UPDATE sys_users SET status='停用' WHERE username='pharmacist'")
        conn.commit()
        conn.close()
        r = client.post("/api/login", json={"username": "pharmacist", "password": "Pharm@12345"})
        assert r.status_code == 403


class TestAuthMiddleware:
    def test_me_with_token(self, client, auth):
        h = auth("doctor", "Doc@12345")
        r = client.get("/api/me", headers=h)
        assert r.status_code == 200
        assert r.json()["role_code"] == "doctor"

    def test_me_without_token(self, client):
        assert client.get("/api/me").status_code == 401

    def test_invalid_token(self, client):
        r = client.get("/api/me", headers={"Authorization": "Bearer garbage.token.here"})
        assert r.status_code == 401

    def test_protected_endpoint_requires_token(self, client):
        assert client.get("/api/schedules").status_code == 401
        assert client.post("/api/register", json={"patient_id": 1, "schedule_id": 1}).status_code == 401


# ================================================================ RBAC 越权
class TestRBAC:
    def test_cashier_cannot_prescribe(self, client, auth):
        h = auth("cashier", "Cash@12345")
        r = client.post(
            "/api/prescriptions",
            json={"reg_id": 1, "diagnosis": "越权", "items": [{"drug_id": 1, "quantity": 1}]},
            headers=h,
        )
        assert r.status_code == 403

    def test_cashier_cannot_register(self, client, auth):
        h = auth("cashier", "Cash@12345")
        r = client.post("/api/register", json={"patient_id": 1, "schedule_id": 1}, headers=h)
        assert r.status_code == 403

    def test_doctor_cannot_pay(self, client, auth):
        h = auth("doctor", "Doc@12345")
        r = client.post(
            "/api/pay",
            json={"prescription_id": 1, "request_id": "req-doc-1"},
            headers=h,
        )
        assert r.status_code == 403

    def test_doctor_cannot_dispense(self, client, auth):
        h = auth("doctor", "Doc@12345")
        r = client.post("/api/dispense", json={"prescription_id": 1}, headers=h)
        assert r.status_code == 403

    def test_pharmacist_cannot_pay(self, client, auth):
        h = auth("pharmacist", "Pharm@12345")
        r = client.post(
            "/api/pay",
            json={"prescription_id": 1, "request_id": "req-pharm-1"},
            headers=h,
        )
        assert r.status_code == 403


# ================================================================ 挂号
class TestRegister:
    def test_register_success(self, client, auth):
        h = auth("registrar", "Reg@12345")
        r = client.post("/api/register", json={"patient_id": 1, "schedule_id": 1}, headers=h)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["reg_no"].startswith("GH")
        assert body["queue_no"] == 1
        assert body["fee_cents"] == 1500
        assert body["status"] == "候诊"

    def test_register_insufficient_source_409(self, client, auth):
        h = auth("registrar", "Reg@12345")
        r = client.post("/api/register", json={"patient_id": 1, "schedule_id": 3}, headers=h)
        assert r.status_code == 409

    def test_register_patient_not_found(self, client, auth):
        h = auth("registrar", "Reg@12345")
        r = client.post("/api/register", json={"patient_id": 999, "schedule_id": 1}, headers=h)
        assert r.status_code == 404

    def test_register_schedule_not_found(self, client, auth):
        h = auth("registrar", "Reg@12345")
        r = client.post("/api/register", json={"patient_id": 1, "schedule_id": 999}, headers=h)
        assert r.status_code == 404

    def test_register_decrements_remaining(self, client, auth):
        h = auth("registrar", "Reg@12345")
        client.post("/api/register", json={"patient_id": 1, "schedule_id": 1}, headers=h)
        sched = client.get("/api/schedules", headers=h).json()
        s1 = next(s for s in sched if s["schedule_id"] == 1)
        assert s1["remaining_count"] == 9


# ================================================================ 开方
class TestPrescribe:
    def test_prescribe_success_server_pricing(self, client, auth):
        h = auth("doctor", "Doc@12345")
        r = client.post(
            "/api/prescriptions",
            json={
                "reg_id": 1,
                "diagnosis": "上呼吸道感染",
                "items": [
                    {"drug_id": 1, "quantity": 2},
                    {"drug_id": 2, "quantity": 1},
                ],
            },
            headers=h,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        # 金额由服务端按药品目录单价重算：2*2000 + 1*3500 = 7500
        assert body["total_amount_cents"] == 7500
        assert body["status"] == "待收费"

    def test_prescribe_disabled_drug(self, client, auth):
        h = auth("doctor", "Doc@12345")
        r = client.post(
            "/api/prescriptions",
            json={"reg_id": 1, "diagnosis": "x", "items": [{"drug_id": 3, "quantity": 1}]},
            headers=h,
        )
        assert r.status_code == 400

    def test_prescribe_empty_items_rejected(self, client, auth):
        h = auth("doctor", "Doc@12345")
        r = client.post(
            "/api/prescriptions",
            json={"reg_id": 1, "diagnosis": "x", "items": []},
            headers=h,
        )
        assert r.status_code == 422

    def test_prescribe_reg_not_found(self, client, auth):
        h = auth("doctor", "Doc@12345")
        r = client.post(
            "/api/prescriptions",
            json={"reg_id": 999, "diagnosis": "x", "items": [{"drug_id": 1, "quantity": 1}]},
            headers=h,
        )
        assert r.status_code == 404


# ================================================================ 收费（含 FEFO 扣库存）
class TestPay:
    def test_pay_success_fefo(self, client, auth):
        h = auth("cashier", "Cash@12345")
        r = client.post(
            "/api/pay",
            json={"prescription_id": 1, "request_id": "req-1"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_amount_cents"] == 7500
        assert body["bill_no"].startswith("FY")
        # 04 版在收费阶段 FEFO 扣库存：阿莫西林先扣最早效期批次 AMX202701
        amx = [s for s in body["stock_deductions"] if s["drug"] == "阿莫西林胶囊"]
        assert amx[0]["batch_no"] == "AMX202701"
        assert amx[0]["quantity"] == 1
        assert amx[1]["batch_no"] == "AMX202706"

    def test_pay_idempotent(self, client, auth):
        h = auth("cashier", "Cash@12345")
        payload = {"prescription_id": 1, "request_id": "req-idem"}
        first = client.post("/api/pay", json=payload, headers=h).json()
        second = client.post("/api/pay", json=payload, headers=h).json()
        assert first["bill_id"] == second["bill_id"]

    def test_pay_wrong_status(self, client, auth):
        h = auth("cashier", "Cash@12345")
        client.post("/api/pay", json={"prescription_id": 1, "request_id": "req-a"}, headers=h)
        r = client.post("/api/pay", json={"prescription_id": 1, "request_id": "req-b"}, headers=h)
        assert r.status_code == 400

    def test_pay_insufficient_stock_400(self, client, auth):
        # 把某药品库存清零后收费，应 400 且整单回滚
        import main

        conn = main.get_connection()
        conn.execute("UPDATE drug_stocks SET quantity = 0 WHERE drug_id = 1")
        conn.commit()
        conn.close()
        h = auth("cashier", "Cash@12345")
        r = client.post(
            "/api/pay", json={"prescription_id": 1, "request_id": "req-short"}, headers=h
        )
        assert r.status_code == 400
        assert "库存不足" in r.json()["detail"]


# ================================================================ 发药（确认）
class TestDispense:
    def test_dispense_success(self, client, auth):
        # 先收费（扣库存），再发药确认
        cash_h = auth("cashier", "Cash@12345")
        client.post("/api/pay", json={"prescription_id": 1, "request_id": "req-pay"}, headers=cash_h)

        pharm_h = auth("pharmacist", "Pharm@12345")
        r = client.post("/api/dispense", json={"prescription_id": 1}, headers=pharm_h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "已发药"
        assert len(body["records"]) > 0

    def test_dispense_not_paid(self, client, auth):
        h = auth("pharmacist", "Pharm@12345")
        r = client.post("/api/dispense", json={"prescription_id": 1}, headers=h)
        assert r.status_code == 400


# ================================================================ 全链路
class TestFullFlow:
    def test_register_prescribe_pay_dispense(self, client, auth):
        # 挂号员挂号
        reg_h = auth("registrar", "Reg@12345")
        reg = client.post(
            "/api/register", json={"patient_id": 1, "schedule_id": 1}, headers=reg_h
        )
        assert reg.status_code == 201
        reg_id = reg.json()["reg_id"]

        # 医生开方
        doc_h = auth("doctor", "Doc@12345")
        rx = client.post(
            "/api/prescriptions",
            json={
                "reg_id": reg_id,
                "diagnosis": "上呼吸道感染",
                "items": [{"drug_id": 1, "quantity": 2}, {"drug_id": 2, "quantity": 1}],
            },
            headers=doc_h,
        )
        assert rx.status_code == 201
        rx_id = rx.json()["prescription_id"]

        # 收费员收费（扣库存）
        cash_h = auth("cashier", "Cash@12345")
        pay = client.post(
            "/api/pay", json={"prescription_id": rx_id, "request_id": "req-flow"}, headers=cash_h
        )
        assert pay.status_code == 200

        # 药师发药（确认）
        pharm_h = auth("pharmacist", "Pharm@12345")
        disp = client.post("/api/dispense", json={"prescription_id": rx_id}, headers=pharm_h)
        assert disp.status_code == 200
        assert disp.json()["status"] == "已发药"
