# 自动化运维平台

一个基于 FastAPI 的自动化运维管理平台，提供脚本调度、任务执行和健康检查等功能。

## 功能特性
- 健康检查 (`/health`)
- 元数据管理 (`/meta`)
- 任务管理 (`/tasks`)
- 脚本管理 (`/scripts`)
- 运行记录 (`/runs`)

## 部署方式

### 容器化部署
```bash
# 构建镜像
docker build -t automation-hub .

# 运行容器
docker run -d -p 8000:8000 automation-hub
```

### Helm 部署 (推荐)

使用 Helm 进行 Kubernetes 部署：

```bash
# 开发环境
helm upgrade --install dev-env charts/automation-hub \
  --namespace automation-hub-dev --create-namespace \
  --values charts/automation-hub/values-dev.yaml

# 生产环境
helm upgrade --install prod-env charts/automation-hub \
  --namespace automation-hub-prod --create-namespace \
  --values charts/automation-hub/values-prod.yaml
```

详细部署指南见 [docs/helm-deployment.md](docs/helm-deployment.md)。

## CI/CD 流水线
GitHub Actions CI 使用 kind 和 Helm 实现端到端测试，每次 push 自动验证构建、部署和接口连通性。

## GitOps
通过 Argo CD 实现 GitOps，提交即部署。详见 `argocd/` 目录。

## 审计与安全

### 审计日志
- 所有任务执行记录存储在 `runs` 表中
- 支持按脚本名称、状态、触发者、结果、失败类型等多维度查询
- 提供 `/runs` API 端点用于检索历史记录

### 安全控制
- **最小权限原则**：Worker服务使用专用ServiceAccount，仅允许必要操作
- **网络隔离**：通过NetworkPolicy限制出网流量
- **工作目录限制**：所有脚本在 `/workspace` 目录下执行
- **命令白名单**：通过manifest.json声明允许执行的命令

详见 [docs/api-reference.md](docs/api-reference.md)。
