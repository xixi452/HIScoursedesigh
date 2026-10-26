# 后端镜像：Python 3.11 + FastAPI + SQLite
# 构建上下文必须是 his-mvp 根目录（因为 main.py 里 SCHEMA_SQL 指向 /app/04_schema.sql）
FROM python:3.11-slim

WORKDIR /app

# 先复制依赖清单并安装（利用 Docker 层缓存，改代码不用重装依赖）
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 复制后端代码 + 建表/种子 SQL（与 main.py 的 PROJECT_ROOT 路径对应）
COPY backend/ /app/backend/
COPY 04_schema.sql 06_seed_reference.sql /app/

WORKDIR /app/backend

EXPOSE 8000

# 启动前自动建表+种数据，再起 uvicorn
CMD ["sh", "-c", "python seed_all.py && uvicorn main:app --host 0.0.0.0 --port 8000"]
