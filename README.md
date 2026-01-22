<!-- 模块说明：Automation Hub 项目说明。 -->

# Automation Hub

一个面向学习者的入门级 DevOps 实践项目，通过构建"个人自动化中心"帮助开发者掌握 Docker、Docker Compose 和未来 Kubernetes 的核心技能。

## 项目概述

本项目旨在解决以下问题：
- 如何将 Python 脚本系统工程化并容器化？
- 如何实现 API 与后台 Worker 解耦？
- 如何持久化任务记录、日志和运行产物？
- 如何为后续迁移到 K8s 打下基础？

## 功能特性

- **脚本管理**：注册、查询可用自动化脚本
- **任务管理**：创建、更新、查询待办任务
- **运行控制**：触发脚本执行，生成唯一运行实例
- **日志审计**：保存每次运行的标准输出/错误日志
- **数据持久化**：使用 SQLite 存储元数据，本地目录存储运行产物

## 技术栈

- FastAPI
- Redis + RQ (Python Redis Queue)
- SQLite
- Docker & Docker Compose
- Python 3.11

## 快速开始

```bash
# 构建并启动项目
docker compose up --build

# 访问服务
# API: http://localhost:8000
# 健康检查: http://localhost:8000/health
# OpenAPI 文档: http://localhost:8000/docs
```

- Automation Hub (Starter)

一个从零入门的 **Docker + Docker Compose + Kubernetes** 学习型项目：先做“个人自动化中心”（脚本/待办/定时/日志/审计），未来可无缝升级到“AI 工具助手”的安全执行底座。

## 你将学到什么
- Dockerfile：把 FastAPI + Worker 打包成镜像
- Docker Compose：编排 api/worker/redis，持久化数据卷，healthcheck
- 基础工程化：API/Worker 解耦、运行记录落库、日志保存
- 未来可扩展到 K8s：Deployment/Service/Ingress/PVC/CronJob（下一阶段）

## 运行方式（本地）
1) 安装 Docker Desktop（或 Linux Docker）
2) 在项目根目录执行：
```bash
docker compose up --build
```

- API 地址：http://localhost:8000
- 健康检查：http://localhost:8000/health
- OpenAPI 文档：http://localhost:8000/docs

> 可选：把你要跑测试的代码仓库放到 `./workspace` 目录，容器内映射为 `/workspace`，脚本 `run_tests` 会在这里运行 pytest。

## 快速试用（curl）
### 1) 查看可用脚本
```bash
curl -s http://localhost:8000/scripts | python -m json.tool
```

### 2) 创建一个待办任务
```bash
curl -s -X POST http://localhost:8000/tasks   -H "Content-Type: application/json"   -d '{"title":"每日备份笔记","tags":["backup","daily"],"status":"todo"}' | python -m json.tool
```

### 3) 触发一次脚本执行（示例：爬 RSS）
```bash
curl -s -X POST http://localhost:8000/runs   -H "Content-Type: application/json"   -d '{"script_id":"fetch_rss","args":{"url":"https://www.people.com.cn/rss/politics.xml","limit":10}}' | python -m json.tool
```

### 4) 查看运行记录
```bash
curl -s http://localhost:8000/runs | python -m json.tool
```

## 数据在哪里？
- SQLite：`./data/automation_hub.sqlite3`
- 日志与产物：
  - `./data/runs/<run_id>/stdout.txt`
  - `./data/runs/<run_id>/stderr.txt`
  - `./data/backups/`
  - `./data/reports/`
  - `./data/rss/`
