# 任务四 · AI 提示词记录

> 按课程要求：CSV 解析、审计日志中间件、AI 接口代码「让 AI 完成大部分」，
> 本文件如实记录下发给 AI 的三条核心提示词，供答辩核对。

---

## 提示词 1 —— CSV 批量导入（数据工程师角色）

```
你是一名数据工程师。请为 FastAPI 门诊系统新增「患者 CSV 批量导入」接口，要求：

1. 接口 POST /api/import/patients，支持两种入参：
   - 文件上传（UploadFile，multipart/form-data）
   - 原始文本（csv_text，Form 字段，便于 curl 测试）
   二选一，优先 file。

2. CSV 表头用英文 snake_case（name,gender,birth_date,id_card,phone），
   但要兼容中文表头（姓名/性别/出生日期/身份证号/手机号），并处理 UTF-8 BOM 与 GBK 编码。

3. 逐行校验，**错误行只记录、不影响合法行入库**：
   - name 非空且 ≤50；gender ∈ {男,女,未知}（兼容 male/female/unknown）；
   - birth_date 必须是合法 YYYY-MM-DD；id_card 必须是 18 位（\d{17}[\dX]）；
   - phone 可选，若提供必须是 11 位手机号。

4. 身份证号必须「脱敏入库」，绝不落完整号：
   - id_card_masked = 前 6 后 4、中间 8 位 *（如 330106********1234）
   - id_card_hash  = HMAC-SHA256 加盐哈希（不可逆）
   - id_card_last4 = 末 4 位
   （与 04_schema.sql 中 patients 表的 CHECK 约束保持一致）

5. 去重：按 id_card_hash 同时校验「库内已存在」与「本批次内重复」，重复行记为失败。

6. 合法行一次性写入同一事务（BEGIN IMMEDIATE），返回逐行结果明细：
   {total_rows, success, failed, created_patients[], errors[{row,name,reason}]}

7. 额外提供 GET /api/import/patients/template 返回导入模板。
```

## 提示词 2 —— 审计日志中间件（安全/数据工程师角色）

```
你是一名安全工程师。系统 04_schema.sql 已有 audit_logs 表
（log_id, user_id, action, entity, entity_id, detail, ip, created_at）。
请实现一个「基于中间件的审计日志拦截器」，要求：

1. 用纯 ASGI 中间件实现，拦截所有写操作 POST/PUT/PATCH/DELETE，
   GET 等只读请求不落审计（避免噪音）。

2. 同时缓冲请求体与响应体，记录：
   - user_id：优先 X-User-Id 请求头，其次请求体 operator_id/cashier_id/pharmacist_id/user_id
   - action：METHOD + path
   - entity：路径映射为业务实体（挂号/收费/发药/处方/患者导入/AI分诊）
   - entity_id：从响应体 JSON 提取新建记录 ID（reg_id/prescription_id/bill_id 等）
   - detail：请求摘要（JSON 截断 1000 字）+ 响应状态码；multipart 只记“(文件上传)”
   - ip：client 地址；created_at 自动

3. 硬性要求：审计写入失败绝不能阻断业务请求（try/except 兜底）。

4. 新增 GET /api/audit-logs 分页查询接口（支持 user_id/entity/action 过滤）。
```

## 提示词 3 —— AI 智能分诊接口（AI 应用工程师角色）

```
你是一名 AI 应用工程师。请为门诊系统新增「AI 智能分诊」接口 POST /api/triage，
入参 {symptoms, gender?, age?}，调用 DeepSeek 或 GLM 大模型推荐科室。

硬性约束（人工设定，必须遵守）：
1. 【超时降级】统一 10 秒超时；超时/网络异常/未配置密钥/返回无法解析，
   一律降级返回「全科门诊」（source='fallback'），绝不让前端报错。
2. 【免责声明】响应始终携带 disclaimer 字段：
   「本建议由AI生成，仅供参考，请以医生诊断为准」。

实现要求：
1. 用 OpenAI 兼容协议 POST {base}/chat/completions，DeepSeek 与 GLM 均可复用同一实现。
2. 密钥/模型/超时全部走环境变量（DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL、
   DEEPSEEK_MODEL、GLM_API_KEY、GLM_BASE_URL、GLM_MODEL、AI_TIMEOUT_SECONDS、AI_PROVIDER）。
3. 提示词要求 AI 只从固定科室列表中选择一个，并只输出 JSON
   {"department":"科室","reason":"一句话理由"}。
4. 稳健解析：兼容 ```json 代码块包裹；科室不在白名单内视为失败走降级。
5. 返回 {department, reason, source, provider, disclaimer, latency_ms, timeout_seconds}。
```

---

## 提示词之外的「人工兜底」

- 以上三条提示词产出的代码，均经人工**逐条复核**并做了必要的工程化修正
  （如：患者编号改为基于 patient_no 数字后缀生成、审计中间件对 multipart 正文
  做了脱噪处理、AI 响应解析加了白名单校验等）。
- 详见《人工核对清单_任务四.md》。
