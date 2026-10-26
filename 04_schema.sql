PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE departments (
    dept_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_code    TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    location     TEXT,
    intro        TEXT,
    status       TEXT NOT NULL DEFAULT '启用'
                 CHECK (status IN ('启用', '停用')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE roles (
    role_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    role_code    TEXT NOT NULL UNIQUE,
    role_name    TEXT NOT NULL
);

CREATE TABLE permissions (
    permission_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    permission_code TEXT NOT NULL UNIQUE,
    permission_name TEXT NOT NULL
);

CREATE TABLE role_permissions (
    role_id       INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(permission_id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE sys_users (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    real_name      TEXT NOT NULL,
    role_id        INTEGER NOT NULL REFERENCES roles(role_id),
    dept_id        INTEGER REFERENCES departments(dept_id),
    status         TEXT NOT NULL DEFAULT '启用'
                   CHECK (status IN ('启用', '停用')),
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    last_login_at  TEXT
);

CREATE TABLE doctors (
    doctor_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_no    TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    title        TEXT CHECK (title IN ('主任医师', '副主任医师', '主治医师', '住院医师')),
    dept_id      INTEGER NOT NULL REFERENCES departments(dept_id),
    specialty    TEXT,
    status       TEXT NOT NULL DEFAULT '在岗'
                 CHECK (status IN ('在岗', '停诊', '离岗')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE patients (
    patient_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_no      TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    gender          TEXT NOT NULL CHECK (gender IN ('男', '女', '未知')),
    birth_date      TEXT NOT NULL
                    CHECK (birth_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    id_card_masked  TEXT NOT NULL
                    CHECK (length(id_card_masked) = 18
                           AND substr(id_card_masked, 7, 8) = '********'
                           AND substr(id_card_masked, 1, 6) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
                           AND substr(id_card_masked, 15, 4) GLOB '[0-9][0-9][0-9][0-9]'),
    id_card_hash    TEXT NOT NULL UNIQUE,
    id_card_last4   TEXT NOT NULL
                    CHECK (length(id_card_last4) = 4
                           AND id_card_last4 = substr(id_card_masked, 15, 4)),
    phone           TEXT
                    CHECK (phone IS NULL
                           OR (length(phone) = 11
                               AND phone GLOB '1[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]')),
    status          TEXT NOT NULL DEFAULT '正常'
                    CHECK (status IN ('正常', '停用')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE schedules (
    schedule_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id        INTEGER NOT NULL REFERENCES doctors(doctor_id),
    dept_id          INTEGER NOT NULL REFERENCES departments(dept_id),
    work_date        TEXT NOT NULL
                     CHECK (work_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    time_slot        TEXT NOT NULL CHECK (time_slot IN ('上午', '下午', '夜间')),
    reg_level        TEXT NOT NULL DEFAULT '普通号'
                     CHECK (reg_level IN ('普通号', '专家号', '急诊号')),
    fee_cents        INTEGER NOT NULL CHECK (fee_cents >= 0),
    total_count      INTEGER NOT NULL CHECK (total_count > 0),
    remaining_count  INTEGER NOT NULL
                     CHECK (remaining_count >= 0 AND remaining_count <= total_count),
    status           TEXT NOT NULL DEFAULT '正常'
                     CHECK (status IN ('正常', '停诊', '满号')),
    version          INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (doctor_id, work_date, time_slot, reg_level)
);

CREATE TABLE reg_orders (
    reg_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_no         TEXT NOT NULL UNIQUE,
    patient_id     INTEGER NOT NULL REFERENCES patients(patient_id),
    doctor_id      INTEGER NOT NULL REFERENCES doctors(doctor_id),
    dept_id        INTEGER NOT NULL REFERENCES departments(dept_id),
    schedule_id    INTEGER NOT NULL REFERENCES schedules(schedule_id),
    reg_time       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    queue_no       INTEGER NOT NULL CHECK (queue_no > 0),
    fee_cents      INTEGER NOT NULL CHECK (fee_cents >= 0),
    status         TEXT NOT NULL DEFAULT '候诊'
                   CHECK (status IN ('候诊', '就诊', '完成', '退号', '取消')),
    operator_id    INTEGER NOT NULL REFERENCES sys_users(user_id),
    cancel_reason  TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (schedule_id, queue_no)
);

CREATE TABLE drugs (
    drug_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_code       TEXT NOT NULL UNIQUE,
    generic_name    TEXT NOT NULL,
    trade_name      TEXT,
    spec            TEXT NOT NULL,
    dosage_form     TEXT NOT NULL,
    unit            TEXT NOT NULL,
    price_cents     INTEGER NOT NULL CHECK (price_cents >= 0),
    insurance_type  TEXT NOT NULL DEFAULT '自费'
                    CHECK (insurance_type IN ('甲类', '乙类', '自费', '丙类')),
    status          TEXT NOT NULL DEFAULT '启用'
                    CHECK (status IN ('启用', '停用')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE prescriptions (
    prescription_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_no    TEXT NOT NULL UNIQUE,
    reg_id             INTEGER NOT NULL REFERENCES reg_orders(reg_id),
    patient_id         INTEGER NOT NULL REFERENCES patients(patient_id),
    doctor_id          INTEGER NOT NULL REFERENCES doctors(doctor_id),
    diagnosis          TEXT NOT NULL,
    prescribe_time     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    total_amount_cents INTEGER NOT NULL DEFAULT 0 CHECK (total_amount_cents >= 0),
    status             TEXT NOT NULL DEFAULT '草稿'
                       CHECK (status IN ('草稿', '待收费', '已收费', '已发药', '已退费', '已退药', '作废')),
    created_at         TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE prescription_items (
    item_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id     INTEGER NOT NULL REFERENCES prescriptions(prescription_id) ON DELETE CASCADE,
    drug_id             INTEGER NOT NULL REFERENCES drugs(drug_id),
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents    INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    amount_cents        INTEGER NOT NULL
                        CHECK (amount_cents >= 0 AND amount_cents = quantity * unit_price_cents),
    dosage              TEXT,
    frequency           TEXT,
    usage_text          TEXT,
    days                INTEGER CHECK (days IS NULL OR days > 0),
    dispensed_quantity  INTEGER NOT NULL DEFAULT 0
                        CHECK (dispensed_quantity >= 0 AND dispensed_quantity <= quantity),
    status              TEXT NOT NULL DEFAULT '待发药'
                        CHECK (status IN ('待发药', '已发药', '已退药', '作废')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE drug_stocks (
    stock_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id          INTEGER NOT NULL REFERENCES drugs(drug_id),
    batch_no         TEXT NOT NULL,
    production_date  TEXT
                     CHECK (production_date IS NULL
                            OR (production_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                                AND production_date <= expiry_date)),
    expiry_date      TEXT NOT NULL
                     CHECK (expiry_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    quantity         INTEGER NOT NULL CHECK (quantity >= 0),
    location         TEXT,
    status           TEXT NOT NULL DEFAULT '正常'
                     CHECK (status IN ('正常', '冻结', '过期', '召回')),
    version          INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (drug_id, batch_no)
);

CREATE TABLE bills (
    bill_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_no             TEXT NOT NULL UNIQUE,
    bill_type           TEXT NOT NULL CHECK (bill_type IN ('挂号费', '药品费')),
    reg_id              INTEGER REFERENCES reg_orders(reg_id),
    prescription_id     INTEGER REFERENCES prescriptions(prescription_id),
    patient_id          INTEGER NOT NULL REFERENCES patients(patient_id),
    total_amount_cents  INTEGER NOT NULL CHECK (total_amount_cents >= 0),
    payment_method      TEXT NOT NULL
                        CHECK (payment_method IN ('现金', '微信', '支付宝', '银行卡')),
    cashier_id          INTEGER NOT NULL REFERENCES sys_users(user_id),
    paid_at             TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    status              TEXT NOT NULL DEFAULT '已收费'
                        CHECK (status IN ('已收费', '已退费')),
    invoice_no          TEXT UNIQUE,
    request_id          TEXT NOT NULL UNIQUE,
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    CHECK (
        (bill_type = '挂号费' AND reg_id IS NOT NULL AND prescription_id IS NULL)
        OR
        (bill_type = '药品费' AND reg_id IS NULL AND prescription_id IS NOT NULL)
    )
);

CREATE TABLE dispense_records (
    dispense_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id INTEGER NOT NULL REFERENCES prescriptions(prescription_id),
    item_id         INTEGER NOT NULL REFERENCES prescription_items(item_id),
    stock_id        INTEGER NOT NULL REFERENCES drug_stocks(stock_id),
    batch_no        TEXT NOT NULL,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    record_type     TEXT NOT NULL CHECK (record_type IN ('发药', '退药')),
    pharmacist_id   INTEGER NOT NULL REFERENCES sys_users(user_id),
    dispensed_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE audit_logs (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES sys_users(user_id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    entity      TEXT,
    entity_id   TEXT,
    detail      TEXT,
    ip          TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX idx_schedules_lookup
    ON schedules(work_date, dept_id, doctor_id, status);

CREATE INDEX idx_reg_orders_patient
    ON reg_orders(patient_id, reg_time);

CREATE INDEX idx_reg_orders_schedule_status
    ON reg_orders(schedule_id, status);

CREATE INDEX idx_prescriptions_reg
    ON prescriptions(reg_id);

CREATE INDEX idx_prescriptions_status
    ON prescriptions(status);

CREATE INDEX idx_prescription_items_prescription
    ON prescription_items(prescription_id);

CREATE INDEX idx_drug_stocks_fefo
    ON drug_stocks(drug_id, status, expiry_date);

CREATE INDEX idx_bills_prescription
    ON bills(prescription_id, status);

CREATE INDEX idx_dispense_records_prescription
    ON dispense_records(prescription_id);

CREATE INDEX idx_audit_logs_created
    ON audit_logs(created_at);

CREATE VIEW v_available_schedules AS
SELECT
    s.schedule_id,
    s.work_date,
    s.time_slot,
    s.reg_level,
    s.fee_cents,
    s.total_count,
    s.remaining_count,
    s.status,
    d.doctor_id,
    d.name AS doctor_name,
    d.title AS doctor_title,
    dep.dept_id,
    dep.name AS dept_name,
    dep.location AS dept_location
FROM schedules s
JOIN doctors d ON d.doctor_id = s.doctor_id
JOIN departments dep ON dep.dept_id = s.dept_id
WHERE s.status = '正常'
  AND s.remaining_count > 0
  AND s.work_date >= date('now', 'localtime');

CREATE VIEW v_stock_alert AS
SELECT
    ds.stock_id,
    ds.drug_id,
    dr.generic_name,
    dr.spec,
    dr.unit,
    ds.batch_no,
    ds.quantity,
    ds.expiry_date,
    ds.status,
    CASE
        WHEN ds.expiry_date < date('now', 'localtime') THEN '已过期'
        WHEN ds.expiry_date <= date('now', 'localtime', '+30 days') THEN '近效期'
        WHEN ds.quantity <= 10 THEN '低库存'
        ELSE '正常'
    END AS alert_type
FROM drug_stocks ds
JOIN drugs dr ON dr.drug_id = ds.drug_id
WHERE ds.status <> '召回'
  AND (
      ds.quantity <= 10
      OR ds.expiry_date <= date('now', 'localtime', '+30 days')
  );

CREATE VIEW v_prescription_payable AS
SELECT
    p.prescription_id,
    p.prescription_no,
    p.reg_id,
    p.patient_id,
    pt.name AS patient_name,
    p.doctor_id,
    d.name AS doctor_name,
    p.diagnosis,
    p.prescribe_time,
    p.total_amount_cents,
    p.status
FROM prescriptions p
JOIN patients pt ON pt.patient_id = p.patient_id
JOIN doctors d ON d.doctor_id = p.doctor_id
WHERE p.status = '待收费';
