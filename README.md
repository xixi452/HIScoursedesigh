# 03 · 门诊 HIS（A 门诊线）交付物总目录

> 项目：社区医院门诊信息系统 MVP（A 门诊线）
> 主线：挂号（扣号源）→ 就诊 → 开方 → 收费（算金额）→ 发药（扣批次库存）
> 组员：田晓萱（202301020424）

本目录汇总第 4、5、6、7、10 课 **PPT 要求的全部交付物 + 完整可运行代码**。

---

## 一、按课程对照交付物

| 课程 | PPT 要求 | 本目录位置 |
|---|---|---|
| **第 4 课 立项选题** | 功能点清单（实现/不实现及理由）、ER 图 + 建表 SQL、一页范围说明书 | `立项文档/`、`04_schema.sql`、`06_seed_reference.sql` |
| **第 5 课 核心模块** | 挂号分系统代码（≥3 功能点）+ 300 字 bug 实录 | `backend/` + `frontend/`；`docs/06_第5课_核心开发bug实录.md` |
| **第 6 课 药房收费** | 药房收费闭环代码 + 全流程演示截图 + 交叉测试 Issues（≥3）+ AGENTS.md 工程组织 | `backend/` + `frontend/`；`screenshots/04_full_flow_demo.png`；`docs/07_第6课_交叉测试Issues.md`；`AGENTS.md` |
| **第 7 课 认证安全** | JWT/RBAC/bcrypt 代码 + AI 审查报告（人工复核）+ 敏感信息自查 | `backend/security.py` + `routers/auth.py`；`docs/03_AI安全审查报告.md` |
| （第 8 课 测试） | 三层测试 + 全绿截图 + 覆盖率 | `backend/tests/`、`e2e/`、`screenshots/01~03` |
| **第 10 课 数据规范** | CSV 批量导入（服务端校验/错误明细）+ 操作审计日志 + 统计报表 + 200 字思考题 | `backend/routers/drugs.py`、`import_patients.py`、`audit.py`、`report.py` + `audit_middleware.py`；`screenshots/05_lesson10_demo.png`；`docs/08`、`09` |
| **第 9 课 部署运维** | Docker 配置 + docker-compose + GitHub Actions + 公网 HTTPS 地址 + 环境变量配置 | `backend/Dockerfile`、`frontend/Dockerfile`、`docker-compose.yml`、`.github/workflows/ci.yml`、`.env.example`、`backend/seed_all.py`；`docs/10_第9课_部署说明.md` |
| **第 12 课 验收复盘** | 6 节点演示 PPT 大纲 + 答辩稿（答辩三问） | `docs/11_第12课_演示PPT大纲.md`、`docs/12_第12课_答辩稿.md` |

---

## 二、目录结构

```
03/
├── AGENTS.md               # 工程规范（目录/迁移/字段三规矩）
├── README.md               # 本文件
├── 04_schema.sql           # 建表（10 核心实体 + audit_logs）
├── 06_seed_reference.sql   # 角色/权限种子
├── 立项文档/                # 第 4 课：功能点清单、范围说明书、ER 图、人工核对
├── backend/                # 完整后端（security/RBAC/审计中间件/导入/报表/测试/Dockerfile）
├── frontend/               # 完整前端（登录 + 角色菜单 + 数据导入 + 审计日志/Dockerfile）
├── e2e/                    # Playwright E2E
├── samples/                # 演示 CSV（药品导入、患者导入）
├── screenshots/            # 全绿截图 + 覆盖率 + 全流程演示 + 第10课演示
├── docs/                   # 第 5/6/7/9/10/12 课报告（含演示PPT大纲、答辩稿）
├── docker-compose.yml      # 一条命令起前端+后端+SQLite（第 9 课）
├── .github/workflows/ci.yml# GitHub Actions：push 即测试（第 9 课）
├── .env.example            # 环境变量模板（真实值绝不出现在仓库）
└── .codebuddy/agents/      # 团队角色提示词（后端/前端/数据/QA）
```

---

## 三、完整可运行代码（如何跑起来）

```bash
# 1) 后端（backend/）
cd backend
pip install -r requirements.txt          # fastapi/uvicorn/pydantic/bcrypt/PyJWT/pytest/pytest-cov
python seed_users.py                     # 五角色用户（bcrypt）
python seed_schedules.py                 # 批量排班 + 药品 + 库存
python -m uvicorn main:app --reload --port 8000

# 2) 前端（frontend/）
cd frontend
npm install
npm run dev                              # http://localhost:5173

# 3) 测试
cd backend && python -m pytest -v        # 60 passed，覆盖率 84%
cd e2e && npm install && npx playwright test   # 4 passed

# 4) 全流程演示（第 6 课）
cd backend && python demo_full_flow.py   # 挂号→开方→收费(扣库存)→发药

# 5) 第 10 课演示（导入 + 审计 + 报表）
cd backend && python gen_drugs_csv.py    # 从《药品数据.xlsx》生成导入 CSV
cd backend && python demo_lesson10.py    # 药品/患者导入 + 审计日志 + 统计报表

# 6) Docker 一键启动（第 9 课）
docker compose up --build                 # 前端 http://localhost:5173 后端 http://localhost:8000/docs
```

> 演示账号：admin/Admin@123 · registrar/Reg@12345 · doctor/Doc@12345 · cashier/Cash@12345 · pharmacist/Pharm@12345

---

## 四、关键结论

- **闭环**：挂号扣号源、开方服务端计价、收费 FEFO 扣库存 + 记账、发药确认，事务 + 条件更新 + 唯一约束兜底。
- **安全**：bcrypt 密码、JWT 鉴权、RBAC 四角色、越权 403、号源不足 409、身份取自令牌、身份证脱敏（HMAC 哈希）。
- **质量**：pytest 60 passed、覆盖率 84%、Playwright 4 passed；AI 审查修复 6 个真实漏洞、澄清 1 个误报、记录 3 个遗留。
- **数据**：药品五要素（通用名/商品名/规格/剂型/医保类别）对齐真实医保目录；CSV 导入服务端校验 + 错误明细；审计中间件自动留痕；日报统计。
