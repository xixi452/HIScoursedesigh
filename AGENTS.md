# AGENTS.md

> 门诊 HIS MVP（A 门诊线）工程规范。AI 每次干活先读本文件，目录规范、迁移、字段三规矩必须遵守。

## 项目简介

社区医院门诊信息系统 MVP，按《医院信息系统基本功能规范》（卫办发〔2002〕116 号）实现 A 门诊线闭环：**挂号（扣号源）→ 就诊 → 开方 → 收费（算金额）→ 发药（扣批次库存）**。

## 技术栈

- 前端：React + Vite（`frontend/`）
- 后端：Python 3.10+ / FastAPI / SQLite（`backend/`），Pydantic 做字段校验
- 测试：pytest（单元 + API）、Playwright（E2E）
- 协作：OpenCode + DeepSeek 等大模型，Vibe Coding

## 目录结构（第 6 课三规矩之一：目录写进 AGENTS.md）

```
his-mvp/
├── AGENTS.md              # 本文件
├── 04_schema.sql          # SQLite 建表（10 核心实体）
├── 06_seed_reference.sql  # 角色/权限/角色权限种子
├── backend/
│   ├── main.py            # FastAPI 入口 + get_connection + init_database
│   ├── security.py        # bcrypt 密码哈希 + JWT 签发/校验 + RBAC 依赖
│   ├── schemas.py         # Pydantic 请求/响应模型（金额字段绝不进输入）
│   ├── routers/           # registration / prescription / payment / dispense / query / auth
│   ├── services/          # 可测纯函数：pricing / inventory / registration
│   ├── seed_*.py          # 种子脚本（用户/排班/药品/库存/演示数据）
│   └── tests/             # conftest / test_unit / test_api
├── frontend/
│   └── src/
│       ├── api.js         # 统一请求 + JWT 携带
│       ├── App.jsx        # 登录 + 角色菜单
│       └── pages/         # RegisterDesk / DoctorStation / CashierDesk / PharmacyDesk
└── e2e/                   # Playwright（flow.spec.js）
```

## 三条规矩（第 6 课）

1. **目录规范**：后端 `models/routers/schemas`、前端 `pages/components/api`，AI 每次按本文件目录落代码。
2. **迁移不删库**：要加字段就写迁移脚本（先 `PRAGMA table_info` 检查列是否存在再 `ALTER TABLE`），**禁止删库重建**；演示前一天数据全没等于事故。
3. **前后端字段一致**：后端 Pydantic 用 snake_case（`patient_id`），前端对应用 camelCase（`patientId`），AI 生成前端类型时引用后端 schema 对齐。

## 业务红线（必须写进提示词，AI 不会主动做）

- **号源/库存扣减走事务**：`BEGIN IMMEDIATE` + 条件更新（`WHERE remaining_count > 0` / `quantity >= ?`），并发不超卖。
- **金额后端算**：单价以药品档案为准，绝不信任前端传价；金额用「分」存整数。
- **收费与扣库存同事务**：要么都成功要么都回滚；库存不足返回 400，禁扣成负数（`CHECK(quantity>=0)` 兜底）。
- **密码 bcrypt 哈希**，身份证脱敏（前 6 + 8 星 + 后 4），不存明文。

## 禁止事项

1. 禁止交付未经人工验证的代码（前端能打开、后端接口测过、pytest 全绿）。
2. 禁止明文存储/提交敏感信息（密码、身份证、API Key、JWT 密钥）。
3. 禁止擅自偏离需求规格；需求模糊先给方案确认再编码。
