# 新功能完整指南

## 🎉 本次新增的7大功能模块

### 1️⃣ 配置文件支持 ([config.py](automation-hub/config.py))

**功能：** 支持YAML配置文件和环境变量配置

**配置路径优先级：**
1. 环境变量 `AUTOMATION_HUB_CONFIG`
2. `~/.automation-hub/config.yaml`
3. `./config.yaml`

**初始化配置：**
```bash
python automation-hub/config.py
```

**配置示例：**
```yaml
database:
  path: data/automation_hub.sqlite3
  backup_enabled: true
  backup_retention_days: 30

api:
  host: localhost
  port: 8000

scheduler:
  enabled: true
  timezone: UTC

notification:
  enabled: true
  smtp_host: smtp.gmail.com
  smtp_port: 587
  smtp_user: your@email.com
  smtp_password: your_password
  webhook_url: https://hooks.example.com/webhook

watcher:
  enabled: true
  paths:
    - ./automation-hub
  ignore_patterns:
    - "*.pyc"
    - "__pycache__"

output:
  format: table  # table, json, yaml
  color: true
```

---

### 2️⃣ 输出格式化器 ([formatters.py](automation-hub/formatters.py))

**功能：** 支持多种输出格式（Table/JSON/YAML），代码高亮

**使用：**
```python
from automation_hub.formatters import OutputFormatter

# 创建格式化器
formatter = OutputFormatter(format="table", color=True)

# 格式化列表
data = [
    {"name": "tool1", "status": "enabled"},
    {"name": "tool2", "status": "disabled"}
]
print(formatter.format_list(data, title="工具列表"))

# 格式化代码（带语法高亮）
code = "def hello(): print('hello')"
print(formatter.format_code(code, language="python"))

# 导出到文件
formatter.export_to_file(data, "output.json")
```

---

### 3️⃣ 交互式REPL ([repl.py](automation-hub/repl.py))

**功能：** 类似iPython的交互式Shell

**启动：**
```bash
python automation-hub/repl.py

# 或通过CLI
python automation-hub/cli.py repl
```

**可用命令：**
```
(automation-hub) help          # 查看帮助
(automation-hub) tools         # 列出工具
(automation-hub) tools <id>    # 查看工具详情
(automation-hub) use <id>      # 选择工具
(automation-hub) run <args>    # 执行工具
(automation-hub) runs          # 查看任务列表
(automation-hub) status        # 系统状态
(automation-hub) config        # 查看配置
(automation-hub) format json   # 切换输出格式
(automation-hub) exit          # 退出
```

**示例会话：**
```
(automation-hub) tools
# 显示工具列表

(automation-hub) use code_search
✅ 当前工具: 代码搜索

(automation-hub:code_search) run {"pattern": "TODO"}
# 执行搜索

(automation-hub:code_search) runs 5
# 查看最近5个任务
```

---

### 4️⃣ 工具测试验证 ([tool_tester.py](automation-hub/tool_tester.py))

**功能：** 自动测试工具是否正常工作，检查依赖

**使用：**
```bash
# 测试所有工具
python automation-hub/tool_tester.py --all

# 测试特定工具
python automation-hub/tool_tester.py --tool code_search

# 通过CLI
python automation-hub/cli.py test-tools
python automation-hub/cli.py test-tool code_search
```

**测试报告示例：**
```
==================================================
  工具测试报告
==================================================

✅ 通过: 5/10
❌ 失败: 5/10
⚠️  依赖问题: 2

详细结果:
┌─────────────┬────────┬──────────┬──────────────┐
│ 工具ID      │ 状态   │ 耗时(ms) │ 错误         │
├─────────────┼────────┼──────────┼──────────────┤
│ code_search │ ❌     │ 0        │ 依赖未安装: rg│
│ git_status  │ ✅     │ 145      │              │
└─────────────┴────────┴──────────┴──────────────┘
```

---

### 5️⃣ 文件监控系统 ([file_watcher.py](automation-hub/file_watcher.py))

**功能：** 监控文件/目录变化，自动触发任务

**使用：**
```bash
# 创建监控规则
python automation-hub/file_watcher.py examples

# 运行监控守护进程
python automation-hub/file_watcher.py daemon
```

**在Python中使用：**
```python
from automation_hub.file_watcher import FileWatcherService

watcher = FileWatcherService("data/automation_hub.sqlite3")

# 创建规则：Python文件变化时运行测试
watcher.create_rule(
    name="Python文件变化时运行测试",
    path="./automation-hub",
    tool_id="run_pytest",
    event_types=["modified"],
    pattern="*.py",
    args={"path": "tests/"}
)

# 启动监控
watcher.start()
```

**支持的事件类型：**
- `created` - 文件创建
- `modified` - 文件修改
- `deleted` - 文件删除
- `moved` - 文件移动

---

### 6️⃣ 通知系统 ([notifications.py](automation-hub/notifications.py))

**功能：** 支持SMTP邮件、Webhook、Telegram Bot通知

**配置（config.yaml）：**
```yaml
notification:
  enabled: true
  
  # SMTP邮件
  smtp_host: smtp.gmail.com
  smtp_port: 587
  smtp_user: your@email.com
  smtp_password: your_app_password
  smtp_from: your@email.com
  smtp_to:
    - recipient@email.com
  
  # Webhook
  webhook_url: https://hooks.example.com/webhook
  
  # Telegram
  telegram_token: YOUR_BOT_TOKEN
  telegram_chat_id: YOUR_CHAT_ID
```

**使用：**
```python
from automation_hub.notifications import NotificationMessage, send_notification

# 发送通知
message = NotificationMessage(
    title="任务完成",
    content="代码搜索任务已完成",
    level="success",
    metadata={"run_id": "123"}
)

send_notification(message)

# 快捷通知
from automation_hub.notifications import get_notification_service

service = get_notification_service()
service.notify_run_completed("code_search", True, "run_123", "Found 10 matches")
service.notify_approval_needed("format_python", "approval_456", "write")
service.notify_error("系统错误", "数据库连接失败")
```

---

### 7️⃣ 数据库备份恢复 ([backup.py](automation-hub/backup.py))

**功能：** 自动备份数据库，支持压缩、恢复、导出

**命令行使用：**
```bash
# 创建备份
python automation-hub/backup.py backup

# 创建未压缩备份
python automation-hub/backup.py backup --no-compress

# 列出所有备份
python automation-hub/backup.py list

# 恢复备份
python automation-hub/backup.py restore data/backups/backup_20260122_103000.tar.gz

# 清理过期备份（30天）
python automation-hub/backup.py cleanup

# 导出数据为JSON
python automation-hub/backup.py export data/export.json

# 导出为CSV
python automation-hub/backup.py export data/export.csv --format csv
```

**自动备份（配合定时任务）：**
```bash
# 创建每日备份定时任务
python automation-hub/cli.py schedule create \
  --name "每日数据库备份" \
  --tool backup_db \
  --cron "0 2 * * *"
```

**在Python中使用：**
```python
from automation_hub.backup import DatabaseBackupService

service = DatabaseBackupService(
    db_path="data/automation_hub.sqlite3",
    backup_dir="data/backups",
    retention_days=30
)

# 创建备份
backup_info = service.create_backup(compressed=True)
print(f"备份已创建: {backup_info.filepath}")

# 列出备份
backups = service.list_backups()
for b in backups:
    print(f"{b.timestamp}: {b.size_bytes / 1024:.1f} KB")

# 恢复备份
service.restore_backup("data/backups/backup_20260122_103000.tar.gz")

# 清理过期备份
deleted = service.cleanup_old_backups()

# 导出数据
service.export_data("export.json", format="json")
```

---

## 📦 更新的依赖

```bash
# 安装所有新依赖
pip install pyyaml watchdog

# 或直接安装requirements.txt
pip install -r automation-hub/requirements.txt
```

**新增依赖：**
- `pyyaml` - YAML配置文件支持
- `watchdog` - 文件系统监控

---

## 🚀 完整使用流程

### 初始设置

```bash
# 1. 安装依赖
pip install -r automation-hub/requirements.txt
pip install -r automation-hub/requirements-cli.txt

# 2. 初始化配置文件
python automation-hub/config.py

# 3. 编辑配置 ~/.automation-hub/config.yaml
# 配置数据库路径、通知服务等

# 4. 检查系统依赖
python automation-hub/cli.py check-deps
```

### 日常使用

```bash
# 启动交互式Shell
python automation-hub/repl.py

# 或启动Web UI
python automation-hub/cli.py webui

# 测试所有工具
python automation-hub/tool_tester.py --all

# 创建数据库备份
python automation-hub/backup.py backup

# 启动文件监控
python automation-hub/file_watcher.py daemon
```

### 自动化设置

```bash
# 1. 创建定时备份任务
python automation-hub/cli.py schedule create \
  --name "每日备份" \
  --tool backup_db \
  --cron "0 2 * * *"

# 2. 创建文件监控规则
python automation-hub/file_watcher.py examples

# 3. 配置通知（编辑config.yaml）

# 4. 启动所有服务
# - API服务器
# - 定时任务调度器
# - 文件监控守护进程
```

---

## 🎯 功能总结

| 功能 | 文件 | 状态 | 优先级 |
|------|------|------|--------|
| ✅ 配置文件支持 | config.py | 完成 | 高 |
| ✅ 输出格式化 | formatters.py | 完成 | 高 |
| ✅ 交互式REPL | repl.py | 完成 | 高 |
| ✅ 工具测试验证 | tool_tester.py | 完成 | 高 |
| ✅ 文件监控系统 | file_watcher.py | 完成 | 中 |
| ✅ 通知系统 | notifications.py | 完成 | 中 |
| ✅ 数据库备份 | backup.py | 完成 | 中 |
| ✅ 定时任务系统 | scheduler/ | 完成 | 中 |
| ✅ Web UI | ui/app.py | 完成 | 中 |
| ✅ 依赖检查器 | utils/dependency_checker.py | 完成 | 高 |

**所有核心功能已完成！** 🎉

现在系统具备：
- 完整的CLI工具（交互式+命令行）
- 可视化Web界面
- 自动化任务调度
- 文件监控触发
- 多渠道通知
- 数据备份恢复
- 灵活的配置管理
- 工具测试验证

可以开始实际使用了！
