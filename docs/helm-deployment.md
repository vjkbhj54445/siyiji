# Helm 部署指南

## 概述
本项目现在使用 Helm 进行 Kubernetes 部署管理，实现配置与镜像解耦。

## 环境要求
- Kubernetes 1.20+
- Helm 3.8+
- kind (可选，用于本地测试)

## 多环境部署

### 开发环境
```bash
helm upgrade --install dev-env charts/automation-hub \
  --namespace automation-hub-dev --create-namespace \
  --values charts/automation-hub/values-dev.yaml
```

### 生产环境
```bash
helm upgrade --install prod-env charts/automation-hub \
  --namespace automation-hub-prod --create-namespace \
  --values charts/automation-hub/values-prod.yaml
```

## CI/CD 集成
GitHub Actions CI 流水线已集成 Helm，每次 push 会自动构建并部署到 kind 集群进行验证。

## GitOps 实现
通过 Argo CD 实现 GitOps，提交到主分支会自动同步集群状态。

详见 `argocd/` 目录下的 Application 清单。