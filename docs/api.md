<!-- 模块说明：API 使用说明。 -->

# API 文档

## Health 检查接口

### GET /health

检查系统健康状态。

**响应示例：**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-15T13:29:26"
}
```

## 脚本管理接口

### GET /scripts/

获取所有可用脚本列表。

**响应示例：**
```json
[
  {
    "name": "fetch_rss.py",
    "description": "抓取RSS源",
    "parameters": [
      {
        "name": "url",
        "type": "string",
        "required": true,
        "description": "RSS URL地址"
      },
      {
        "name": "limit",
        "type": "integer",
        "required": false,
        "description": "抓取条目数量限制"
      }
    ]
  }
]
```

### POST /scripts/

注册新脚本。

**请求体示例：**
```json
{
  "name": "my_script.py",
  "description": "描述",
  "parameters": []
}
```

## 任务管理接口

### GET /tasks/

获取所有任务列表。

### POST /tasks/

创建新任务。

### GET /tasks/{task_id}

获取特定任务详情。

### PUT /tasks/{task_id}

更新特定任务。

### DELETE /tasks/{task_id}

删除特定任务。

## 运行管理接口

### GET /runs/

获取所有运行记录。

### POST /runs/

触发脚本运行。

**请求体示例：**
```json
{
  "script_name": "fetch_rss.py",
  "parameters": {
    "url": "https://example.com/rss",
    "limit": 10
  }
}
```

### GET /runs/{run_id}

获取特定运行记录详情。
# API（10 个最小接口）

> 启动后可访问 http://localhost:8000/docs 查看 OpenAPI 文档（交互式）。

1. `GET /health` 健康检查  
2. `GET /version` 版本信息  
3. `GET /scripts` 列出可用脚本（来自 `scripts/manifest.json`）  
4. `GET /scripts/{script_id}` 获取脚本详情  
5. `POST /tasks` 创建待办任务  
6. `GET /tasks` 列出任务（可选 `?status=todo`）  
7. `PATCH /tasks/{task_id}` 更新任务  
8. `DELETE /tasks/{task_id}` 删除任务  
9. `POST /runs` 触发脚本执行（异步入队列）  
10. `GET /runs` 列出运行记录（默认 50 条）  
11. `GET /runs/{run_id}` 获取运行详情（包含 stdout/stderr tail）  

> 注：第 11 个是为了“可用性”额外给的（你可以把它当成必选接口之一）。
