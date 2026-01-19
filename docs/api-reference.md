# API 参考文档

## /runs - 运行记录管理

### GET /runs
获取运行记录列表，支持多维度过滤。

**查询参数**：
- `script_name`: 脚本名称过滤
- `status`: 任务状态（queued, running, succeeded, failed）
- `triggered_by`: 触发者（system, user）
- `result_status`: 结果状态（success, failure）
- `failure_type`: 失败类型（timeout, nonzero, exception）
- `start_date`: 开始时间范围
- `end_date`: 结束时间范围

**响应示例**：
```json
[
  {
    "id": 1,
    "script_name": "daily_report",
    "parameters": "{\"output_path\": \"/workspace/reports/daily_2023-01-01.md\"}",
    "status": "succeeded",
    "start_time": "2023-01-01T09:00:00",
    "end_time": "2023-01-01T09:05:00",
    "triggered_by": "system",
    "result_status": "success",
    "failure_type": null
  }
]
```

### POST /runs/runs
触发脚本执行。

**请求体**：
```json
{
  "script_name": "string",
  "parameters": {}
}
```

**响应**：
```json
{
  "run_id": 1,
  "status": "queued"
}
```