# 新功能使用指南

## 🎉 已实现的三大功能

### 1️⃣ 工具依赖检查器

自动检测系统是否安装了必要的外部工具（ripgrep、git、docker等）

**使用方法:**

```bash
# 检查所有依赖
python automation-hub/cli.py check-deps

# 显示详细信息
python automation-hub/cli.py check-deps --verbose

# 只检查特定依赖
python automation-hub/cli.py check-deps --check ripgrep --check git

# 独立使用
python automation-hub/utils/dependency_checker.py
```

**特性:**
- ✅ 自动检测命令是否存在
- ✅ 获取并验证版本号
- ✅ 区分必需和可选依赖
- ✅ 提供安装提示
- ✅ 彩色报告输出

---

### 2️⃣ 定时任务系统

基于APScheduler实现的定时任务调度系统

**使用方法:**

```bash
# 安装依赖
pip install apscheduler

# 列出所有定时任务
python automation-hub/cli.py schedule list

# 创建Cron定时任务（每天凌晨2点）
python automation-hub/cli.py schedule create \
  --name "每日备份" \
  --tool backup_notes \
  --cron "0 2 * * *"

# 创建间隔任务（每小时）
python automation-hub/cli.py schedule create \
  --name "每小时检查" \
  --tool fetch_rss \
  --interval 1h

# 创建带参数的任务
python automation-hub/cli.py schedule create \
  --name "代码搜索" \
  --tool code_search \
  --interval 30m \
  --args '{"pattern": "TODO"}'

# 启用/禁用任务
python automation-hub/cli.py schedule enable <job_id>
python automation-hub/cli.py schedule disable <job_id>

# 删除任务
python automation-hub/cli.py schedule delete <job_id>
```

**触发器类型:**
- **Cron**: 使用Cron表达式（分 时 日 月 周）
- **Interval**: 间隔执行（1h, 30m, 60s）
- **Date**: 单次定时执行（暂未在CLI中暴露）

**示例任务:**

```python
# 在Python代码中使用
from automation_hub.scheduler import SchedulerService

scheduler = SchedulerService("data/automation_hub.sqlite3")

# 每天凌晨2点备份
scheduler.create_job(
    name="每日备份",
    tool_id="backup_notes",
    trigger_type="cron",
    trigger_config={"hour": 2, "minute": 0}
)

# 每小时获取RSS
scheduler.create_job(
    name="RSS更新",
    tool_id="fetch_rss",
    trigger_type="interval",
    trigger_config={"hours": 1}
)

# 启动调度器
scheduler.start()
```

---

### 3️⃣ Web UI (Streamlit)

基于Streamlit的可视化管理界面

**使用方法:**

```bash
# 安装依赖
pip install streamlit pandas

# 启动Web UI（默认端口8501）
python automation-hub/cli.py webui

# 自定义端口和主机
python automation-hub/cli.py webui --port 8080 --host 0.0.0.0

# 或直接运行
streamlit run automation-hub/ui/app.py
```

**访问:** http://localhost:8501

**功能页面:**

1. **📊 仪表盘**
   - 系统概览（启用工具数、任务数、审批数、成功率）
   - 最近任务列表
   - 任务状态分布图

2. **🔧 工具管理**
   - 列表查看（支持过滤）
   - 启用/禁用工具
   - 查看工具详情
   - 添加新工具

3. **▶️ 任务执行**
   - 选择工具执行
   - 输入参数（JSON格式）
   - 查看执行结果
   - 任务历史（支持过滤）

4. **✅ 审批管理**
   - 待审批请求列表
   - 一键批准/拒绝
   - 审批历史记录

5. **📋 审计日志**
   - 事件类型过滤
   - 时间范围筛选
   - 详细信息展示

6. **⏰ 定时任务**
   - 任务列表
   - 创建/启用/禁用/删除
   - 执行统计

**截图示例:**
- 界面美观，使用Rich样式
- 表格展示，支持排序
- 实时数据，自动刷新
- 响应式布局，宽屏友好

---

## 🚀 完整使用流程

### 快速开始

```bash
# 1. 安装所有依赖
pip install -r automation-hub/requirements.txt
pip install -r automation-hub/requirements-cli.txt

# 2. 检查系统依赖
python automation-hub/cli.py check-deps --verbose

# 3. 注册工具
python automation-hub/scripts/register_tools.py

# 4. 查看系统状态
python automation-hub/cli.py status

# 5. 启动Web UI
python automation-hub/cli.py webui
```

### 高级用法

```bash
# 创建定时任务：每天凌晨2点备份笔记
python automation-hub/cli.py schedule create \
  --name "每日备份" \
  --tool backup_notes \
  --cron "0 2 * * *"

# 创建定时任务：每小时搜索TODO注释
python automation-hub/cli.py schedule create \
  --name "TODO检查" \
  --tool code_search \
  --interval 1h \
  --args '{"pattern": "TODO", "path": "."}'

# 查看定时任务
python automation-hub/cli.py schedule list

# 执行工具（CLI）
python automation-hub/cli.py run code_search --args '{"pattern": "FIXME"}'

# 查看任务历史
python automation-hub/cli.py runs list --status succeeded --last 24h
```

---

## 📦 依赖清单

### requirements.txt (已更新)
```
# 核心依赖
fastapi==0.105.0
uvicorn[standard]==0.24.0
pydantic==1.10.13
redis==5.0.8
rq==1.16.2

# 新增：定时任务
apscheduler==3.10.4

# 新增：Web UI
streamlit==1.29.0
pandas==2.1.4
```

### requirements-cli.txt
```
click>=8.1.0
rich>=13.0.0
```

---

## 🎯 下一步建议

1. **文件监控** - 使用watchdog监控文件变化，自动触发任务
2. **通知系统** - 邮件/Webhook/Telegram通知
3. **数据可视化** - Grafana集成，任务执行统计图表
4. **备份恢复** - 数据库自动备份和恢复
5. **配置管理** - YAML配置文件支持

需要实现哪个功能？
