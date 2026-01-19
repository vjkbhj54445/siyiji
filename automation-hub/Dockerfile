# 多阶段构建 - 构建阶段
FROM python:3.11-slim AS builder

# 安装构建所需的依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制并安装依赖，利用Docker构建缓存
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# 多阶段构建 - 运行阶段
FROM python:3.11-slim

# 安装运行时所需的基本工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建专用用户以非root身份运行（安全实践）
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m -s /bin/bash appuser

# 切换到非root用户并设置家目录为工作区
WORKDIR /home/appuser

# 从构建阶段复制已安装的Python包到用户目录
COPY --from=builder /root/.local /home/appuser/.local

# 设置用户级bin目录到PATH
ENV PATH="/home/appuser/.local/bin:${PATH}"

# 复制应用代码
COPY . .

# 创建数据目录并设置权限
RUN mkdir -p /data && mkdir -p /data/runs /data/backups /data/reports /data/rss && \
    chown -R appuser:appuser /home/appuser && \
    chmod -R 755 /home/appuser && \
    chown -R appuser:appuser /data

# 切换到非root用户运行
USER appuser

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/automation_hub.sqlite3 \
    SCRIPTS_MANIFEST=/home/appuser/scripts/manifest.json \
    RUNS_DIR=/data/runs

EXPOSE 8000

# 启动时先初始化数据库，然后启动应用
CMD ["sh", "-c", "python -c \"from api.db import init_db; init_db()\" && uvicorn api.main:app --host 0.0.0.0 --port 8000"]