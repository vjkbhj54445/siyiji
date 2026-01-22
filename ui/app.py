"""
Automation Hub Web UI

基于Streamlit的可视化管理界面
"""

import streamlit as st
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pandas as pd


# 页面配置
st.set_page_config(
    page_title="Automation Hub",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 数据库路径
DB_PATH = "data/automation_hub.sqlite3"


def get_db_connection():
    """获取数据库连接"""
    return sqlite3.connect(DB_PATH)


def format_datetime(dt_str: str) -> str:
    """格式化时间显示"""
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_str


def get_risk_level_color(risk_level: str) -> str:
    """获取风险级别颜色"""
    colors = {
        "read": "🟢",
        "exec_low": "🟡",
        "exec_high": "🟠",
        "write": "🔴"
    }
    return colors.get(risk_level, "⚪")


# ==================== 侧边栏 ====================
st.sidebar.title("🤖 Automation Hub")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "导航",
    ["📊 仪表盘", "🔧 工具管理", "▶️ 任务执行", "✅ 审批管理", "📋 审计日志", "⏰ 定时任务"]
)

st.sidebar.markdown("---")
st.sidebar.info("💡 **提示**: 选择左侧菜单浏览不同功能")


# ==================== 仪表盘 ====================
if page == "📊 仪表盘":
    st.title("📊 系统仪表盘")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 统计卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        cursor.execute("SELECT COUNT(*) FROM tools WHERE enabled = 1")
        enabled_tools = cursor.fetchone()[0]
        st.metric("启用工具", enabled_tools, delta=None)
    
    with col2:
        cursor.execute("SELECT COUNT(*) FROM runs WHERE created_at > datetime('now', '-24 hours')")
        recent_runs = cursor.fetchone()[0]
        st.metric("24小时任务", recent_runs, delta=None)
    
    with col3:
        cursor.execute("SELECT COUNT(*) FROM approval_requests WHERE status = 'pending'")
        pending_approvals = cursor.fetchone()[0]
        st.metric("待审批", pending_approvals, delta=None, delta_color="inverse")
    
    with col4:
        cursor.execute("SELECT COUNT(*) FROM runs WHERE status = 'succeeded' AND completed_at > datetime('now', '-24 hours')")
        success_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM runs WHERE completed_at > datetime('now', '-24 hours')")
        total_count = cursor.fetchone()[0]
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        st.metric("24小时成功率", f"{success_rate:.1f}%", delta=None)
    
    st.markdown("---")
    
    # 最近任务
    st.subheader("🕐 最近任务")
    
    cursor.execute("""
        SELECT r.id, t.name, r.status, r.created_at, r.completed_at, r.exit_code
        FROM runs r
        LEFT JOIN tools t ON r.tool_id = t.id
        ORDER BY r.created_at DESC
        LIMIT 10
    """)
    
    runs = cursor.fetchall()
    
    if runs:
        runs_data = []
        for run in runs:
            status_icon = {
                "succeeded": "✅",
                "failed": "❌",
                "running": "🔄",
                "queued": "⏳",
                "blocked": "🚫"
            }.get(run[2], "❓")
            
            runs_data.append({
                "ID": run[0][:8],
                "工具": run[1] or "Unknown",
                "状态": f"{status_icon} {run[2]}",
                "创建时间": format_datetime(run[3]),
                "完成时间": format_datetime(run[4]),
                "退出码": run[5] if run[5] is not None else "N/A"
            })
        
        st.dataframe(runs_data, use_container_width=True, hide_index=True)
    else:
        st.info("暂无任务记录")
    
    # 任务状态分布图
    st.subheader("📈 任务状态分布（最近7天）")
    
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM runs
        WHERE created_at > datetime('now', '-7 days')
        GROUP BY status
    """)
    
    status_data = cursor.fetchall()
    
    if status_data:
        df = pd.DataFrame(status_data, columns=["状态", "数量"])
        st.bar_chart(df.set_index("状态"))
    else:
        st.info("暂无数据")
    
    conn.close()


# ==================== 工具管理 ====================
elif page == "🔧 工具管理":
    st.title("🔧 工具管理")
    
    tab1, tab2 = st.tabs(["工具列表", "添加工具"])
    
    with tab1:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 过滤选项
        col1, col2 = st.columns(2)
        with col1:
            show_disabled = st.checkbox("显示已禁用工具", value=False)
        with col2:
            risk_filter = st.multiselect(
                "风险级别",
                ["read", "exec_low", "exec_high", "write"],
                default=[]
            )
        
        # 查询工具
        query = "SELECT id, name, risk_level, enabled, executor, timeout_seconds FROM tools WHERE 1=1"
        params = []
        
        if not show_disabled:
            query += " AND enabled = 1"
        
        if risk_filter:
            placeholders = ",".join(["?"] * len(risk_filter))
            query += f" AND risk_level IN ({placeholders})"
            params.extend(risk_filter)
        
        query += " ORDER BY name"
        
        cursor.execute(query, params)
        tools = cursor.fetchall()
        
        if tools:
            for tool in tools:
                tool_id, name, risk_level, enabled, executor, timeout = tool
                
                with st.expander(f"{get_risk_level_color(risk_level)} {name} {'✅' if enabled else '❌'}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**ID**: `{tool_id}`")
                        st.write(f"**风险级别**: {risk_level}")
                    
                    with col2:
                        st.write(f"**执行器**: {executor}")
                        st.write(f"**超时**: {timeout}秒")
                    
                    with col3:
                        st.write(f"**状态**: {'启用' if enabled else '禁用'}")
                    
                    # 操作按钮
                    col1, col2, col3 = st.columns([1, 1, 3])
                    
                    with col1:
                        if enabled:
                            if st.button(f"禁用", key=f"disable_{tool_id}"):
                                cursor.execute("UPDATE tools SET enabled = 0 WHERE id = ?", (tool_id,))
                                conn.commit()
                                st.success(f"已禁用工具: {name}")
                                st.rerun()
                        else:
                            if st.button(f"启用", key=f"enable_{tool_id}"):
                                cursor.execute("UPDATE tools SET enabled = 1 WHERE id = ?", (tool_id,))
                                conn.commit()
                                st.success(f"已启用工具: {name}")
                                st.rerun()
                    
                    with col2:
                        if st.button("查看详情", key=f"view_{tool_id}"):
                            cursor.execute("SELECT * FROM tools WHERE id = ?", (tool_id,))
                            detail = cursor.fetchone()
                            st.json({
                                "id": detail[0],
                                "name": detail[1],
                                "description": detail[2],
                                "command": json.loads(detail[6]),
                                "args_schema": json.loads(detail[7]) if detail[7] else {}
                            })
        else:
            st.info("暂无工具")
        
        conn.close()
    
    with tab2:
        st.subheader("添加新工具")
        st.info("💡 提示: 建议使用脚本批量注册工具")
        
        with st.form("add_tool_form"):
            tool_id = st.text_input("工具ID *", placeholder="my_tool")
            tool_name = st.text_input("工具名称 *", placeholder="我的工具")
            description = st.text_area("描述", placeholder="工具功能说明")
            risk_level = st.selectbox("风险级别 *", ["read", "exec_low", "exec_high", "write"])
            executor = st.selectbox("执行器 *", ["Host", "Docker", "K8sJob"])
            command = st.text_input("命令 *", placeholder='["echo", "hello"]')
            timeout = st.number_input("超时时间（秒）", min_value=1, max_value=3600, value=60)
            
            submitted = st.form_submit_button("添加工具")
            
            if submitted:
                if not tool_id or not tool_name or not command:
                    st.error("请填写所有必填字段")
                else:
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        
                        cursor.execute("""
                            INSERT INTO tools (id, name, description, risk_level, executor, command_json, timeout_seconds)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (tool_id, tool_name, description, risk_level, executor, command, timeout))
                        
                        conn.commit()
                        conn.close()
                        
                        st.success(f"✅ 工具添加成功: {tool_name}")
                    
                    except sqlite3.IntegrityError:
                        st.error(f"❌ 工具ID已存在: {tool_id}")
                    except Exception as e:
                        st.error(f"❌ 添加失败: {e}")


# ==================== 任务执行 ====================
elif page == "▶️ 任务执行":
    st.title("▶️ 任务执行")
    
    tab1, tab2 = st.tabs(["执行工具", "任务历史"])
    
    with tab1:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 选择工具
        cursor.execute("SELECT id, name, risk_level FROM tools WHERE enabled = 1 ORDER BY name")
        tools = cursor.fetchall()
        
        if not tools:
            st.warning("暂无可用工具，请先注册工具")
        else:
            tool_options = {f"{t[1]} ({get_risk_level_color(t[2])} {t[2]})": t[0] for t in tools}
            
            selected_tool_name = st.selectbox("选择工具", options=list(tool_options.keys()))
            selected_tool_id = tool_options[selected_tool_name]
            
            # 获取工具详情
            cursor.execute("SELECT name, description, args_schema_json, risk_level FROM tools WHERE id = ?", (selected_tool_id,))
            tool = cursor.fetchone()
            
            if tool:
                st.write(f"**描述**: {tool[1] or 'N/A'}")
                st.write(f"**风险级别**: {get_risk_level_color(tool[3])} {tool[3]}")
                
                # 参数输入
                args_json = st.text_area(
                    "参数 (JSON格式)",
                    value='{}',
                    help="例如: {\"pattern\": \"TODO\", \"path\": \".\"}"
                )
                
                if st.button("执行", type="primary"):
                    try:
                        args = json.loads(args_json)
                        
                        # 使用SimpleExecutor执行
                        from automation_hub.simple_executor import SimpleExecutor
                        
                        executor = SimpleExecutor(DB_PATH)
                        
                        with st.spinner("执行中..."):
                            result = executor.execute_tool(
                                tool_id=selected_tool_id,
                                args=args,
                                user_id="web_ui"
                            )
                        
                        if result.get("success"):
                            st.success("✅ 执行成功")
                            
                            if result.get("stdout"):
                                st.code(result["stdout"], language="text")
                            
                            if "run_id" in result:
                                st.info(f"任务ID: {result['run_id']}")
                        
                        elif result.get("status") == "pending_approval":
                            st.warning(f"⚠️ 需要审批: {result.get('message')}")
                            st.info(f"审批ID: {result.get('approval_id')}")
                        
                        else:
                            st.error(f"❌ 执行失败: {result.get('error')}")
                            
                            if result.get("stderr"):
                                st.code(result["stderr"], language="text")
                    
                    except json.JSONDecodeError:
                        st.error("❌ 参数格式错误，请输入有效的JSON")
                    except Exception as e:
                        st.error(f"❌ 执行异常: {e}")
        
        conn.close()
    
    with tab2:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 过滤选项
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.multiselect(
                "状态",
                ["queued", "running", "succeeded", "failed", "blocked"],
                default=[]
            )
        
        with col2:
            time_range = st.selectbox(
                "时间范围",
                ["最近1小时", "最近24小时", "最近7天", "全部"],
                index=1
            )
        
        with col3:
            limit = st.number_input("显示数量", min_value=10, max_value=1000, value=50)
        
        # 构建查询
        query = """
            SELECT r.id, t.name, r.status, r.created_at, r.completed_at, 
                   r.stdout, r.stderr, r.exit_code
            FROM runs r
            LEFT JOIN tools t ON r.tool_id = t.id
            WHERE 1=1
        """
        params = []
        
        if status_filter:
            placeholders = ",".join(["?"] * len(status_filter))
            query += f" AND r.status IN ({placeholders})"
            params.extend(status_filter)
        
        if time_range != "全部":
            hours_map = {
                "最近1小时": 1,
                "最近24小时": 24,
                "最近7天": 168
            }
            hours = hours_map[time_range]
            query += f" AND r.created_at > datetime('now', '-{hours} hours')"
        
        query += f" ORDER BY r.created_at DESC LIMIT {limit}"
        
        cursor.execute(query, params)
        runs = cursor.fetchall()
        
        if runs:
            for run in runs:
                run_id, tool_name, status, created_at, completed_at, stdout, stderr, exit_code = run
                
                status_icon = {
                    "succeeded": "✅",
                    "failed": "❌",
                    "running": "🔄",
                    "queued": "⏳",
                    "blocked": "🚫"
                }.get(status, "❓")
                
                with st.expander(f"{status_icon} {tool_name or 'Unknown'} - {format_datetime(created_at)}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**任务ID**: `{run_id}`")
                        st.write(f"**状态**: {status}")
                        st.write(f"**创建时间**: {format_datetime(created_at)}")
                    
                    with col2:
                        st.write(f"**完成时间**: {format_datetime(completed_at)}")
                        st.write(f"**退出码**: {exit_code if exit_code is not None else 'N/A'}")
                    
                    if stdout:
                        st.subheader("标准输出")
                        st.code(stdout, language="text")
                    
                    if stderr:
                        st.subheader("标准错误")
                        st.code(stderr, language="text")
        else:
            st.info("暂无任务记录")
        
        conn.close()


# ==================== 审批管理 ====================
elif page == "✅ 审批管理":
    st.title("✅ 审批管理")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 待审批列表
    st.subheader("⏳ 待审批请求")
    
    cursor.execute("""
        SELECT a.id, a.resource_type, a.resource_id, a.requested_by, a.created_at,
               t.name, t.risk_level
        FROM approval_requests a
        LEFT JOIN runs r ON a.resource_id = r.id
        LEFT JOIN tools t ON r.tool_id = t.id
        WHERE a.status = 'pending'
        ORDER BY a.created_at DESC
    """)
    
    pending = cursor.fetchall()
    
    if pending:
        for approval in pending:
            approval_id, resource_type, resource_id, requested_by, created_at, tool_name, risk_level = approval
            
            with st.container():
                st.markdown(f"### {get_risk_level_color(risk_level)} {tool_name or 'Unknown'}")
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**审批ID**: `{approval_id}`")
                    st.write(f"**资源**: {resource_type} / `{resource_id[:8]}...`")
                
                with col2:
                    st.write(f"**请求者**: {requested_by}")
                    st.write(f"**时间**: {format_datetime(created_at)}")
                
                with col3:
                    col_approve, col_deny = st.columns(2)
                    
                    with col_approve:
                        if st.button("✅ 批准", key=f"approve_{approval_id}"):
                            cursor.execute("""
                                UPDATE approval_requests
                                SET status = 'approved', decided_by = 'web_ui', decided_at = ?
                                WHERE id = ?
                            """, (datetime.utcnow().isoformat(), approval_id))
                            conn.commit()
                            st.success("已批准")
                            st.rerun()
                    
                    with col_deny:
                        if st.button("❌ 拒绝", key=f"deny_{approval_id}"):
                            cursor.execute("""
                                UPDATE approval_requests
                                SET status = 'denied', decided_by = 'web_ui', decided_at = ?
                                WHERE id = ?
                            """, (datetime.utcnow().isoformat(), approval_id))
                            conn.commit()
                            st.warning("已拒绝")
                            st.rerun()
                
                st.markdown("---")
    else:
        st.info("暂无待审批请求")
    
    # 审批历史
    st.subheader("📜 审批历史")
    
    cursor.execute("""
        SELECT a.id, a.resource_type, a.status, a.decided_by, a.decided_at,
               t.name
        FROM approval_requests a
        LEFT JOIN runs r ON a.resource_id = r.id
        LEFT JOIN tools t ON r.tool_id = t.id
        WHERE a.status != 'pending'
        ORDER BY a.decided_at DESC
        LIMIT 20
    """)
    
    history = cursor.fetchall()
    
    if history:
        history_data = []
        for h in history:
            status_icon = "✅" if h[2] == "approved" else "❌"
            history_data.append({
                "ID": h[0][:8],
                "工具": h[5] or "Unknown",
                "状态": f"{status_icon} {h[2]}",
                "决策者": h[3] or "N/A",
                "决策时间": format_datetime(h[4])
            })
        
        st.dataframe(history_data, use_container_width=True, hide_index=True)
    else:
        st.info("暂无审批历史")
    
    conn.close()


# ==================== 审计日志 ====================
elif page == "📋 审计日志":
    st.title("📋 审计日志")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 过滤选项
    col1, col2, col3 = st.columns(3)
    
    with col1:
        event_type_filter = st.multiselect(
            "事件类型",
            ["auth.login", "tool.registered", "tool.executed", "run.executed", "approval.approved"],
            default=[]
        )
    
    with col2:
        time_range = st.selectbox(
            "时间范围",
            ["最近1小时", "最近24小时", "最近7天", "全部"],
            index=1
        )
    
    with col3:
        limit = st.number_input("显示数量", min_value=10, max_value=1000, value=100)
    
    # 构建查询
    query = """
        SELECT event_type, actor_user_id, resource_type, resource_id, 
               status, details, timestamp
        FROM audit_events
        WHERE 1=1
    """
    params = []
    
    if event_type_filter:
        placeholders = ",".join(["?"] * len(event_type_filter))
        query += f" AND event_type IN ({placeholders})"
        params.extend(event_type_filter)
    
    if time_range != "全部":
        hours_map = {
            "最近1小时": 1,
            "最近24小时": 24,
            "最近7天": 168
        }
        hours = hours_map[time_range]
        query += f" AND timestamp > datetime('now', '-{hours} hours')"
    
    query += f" ORDER BY timestamp DESC LIMIT {limit}"
    
    cursor.execute(query, params)
    events = cursor.fetchall()
    
    if events:
        for event in events:
            event_type, actor, resource_type, resource_id, status, details, timestamp = event
            
            status_icon = "✅" if status == "success" else "❌" if status == "fail" else "ℹ️"
            
            with st.expander(f"{status_icon} {event_type} - {format_datetime(timestamp)}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**事件类型**: {event_type}")
                    st.write(f"**操作者**: {actor or 'system'}")
                    st.write(f"**状态**: {status}")
                
                with col2:
                    st.write(f"**资源类型**: {resource_type or 'N/A'}")
                    st.write(f"**资源ID**: `{resource_id or 'N/A'}`")
                    st.write(f"**时间**: {format_datetime(timestamp)}")
                
                if details:
                    st.write(f"**详情**: {details}")
    else:
        st.info("暂无审计日志")
    
    conn.close()


# ==================== 定时任务 ====================
elif page == "⏰ 定时任务":
    st.title("⏰ 定时任务")
    
    tab1, tab2 = st.tabs(["任务列表", "创建任务"])
    
    with tab1:
        try:
            from automation_hub.scheduler import SchedulerService
            
            scheduler = SchedulerService(DB_PATH)
            jobs = scheduler.list_jobs()
            
            if jobs:
                for job in jobs:
                    status_icon = "✅" if job.enabled else "⏸️"
                    
                    with st.expander(f"{status_icon} {job.name}"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.write(f"**ID**: `{job.id[:8]}...`")
                            st.write(f"**工具**: {job.tool_id}")
                            st.write(f"**触发器**: {job.trigger_type}")
                        
                        with col2:
                            st.write(f"**状态**: {'启用' if job.enabled else '禁用'}")
                            st.write(f"**执行次数**: {job.run_count}")
                            st.write(f"**最后执行**: {format_datetime(job.last_run_at)}")
                        
                        with col3:
                            trigger_config = json.loads(job.trigger_config)
                            st.write(f"**触发配置**:")
                            st.json(trigger_config)
                        
                        # 操作按钮
                        col1, col2, col3 = st.columns([1, 1, 3])
                        
                        with col1:
                            if job.enabled:
                                if st.button("禁用", key=f"disable_job_{job.id}"):
                                    scheduler.disable_job(job.id)
                                    st.success("已禁用")
                                    st.rerun()
                            else:
                                if st.button("启用", key=f"enable_job_{job.id}"):
                                    scheduler.enable_job(job.id)
                                    st.success("已启用")
                                    st.rerun()
                        
                        with col2:
                            if st.button("删除", key=f"delete_job_{job.id}"):
                                scheduler.delete_job(job.id)
                                st.warning("已删除")
                                st.rerun()
            else:
                st.info("暂无定时任务")
        
        except ImportError:
            st.error("❌ 定时任务功能需要安装APScheduler: `pip install apscheduler`")
    
    with tab2:
        st.subheader("创建定时任务")
        
        try:
            from automation_hub.scheduler import SchedulerService
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM tools WHERE enabled = 1")
            tools = cursor.fetchall()
            conn.close()
            
            if not tools:
                st.warning("暂无可用工具")
            else:
                with st.form("create_job_form"):
                    job_name = st.text_input("任务名称 *", placeholder="每日备份")
                    
                    tool_options = {t[1]: t[0] for t in tools}
                    selected_tool_name = st.selectbox("选择工具 *", options=list(tool_options.keys()))
                    selected_tool_id = tool_options[selected_tool_name]
                    
                    trigger_type = st.selectbox(
                        "触发类型 *",
                        ["cron", "interval"],
                        format_func=lambda x: "Cron表达式" if x == "cron" else "间隔执行"
                    )
                    
                    if trigger_type == "cron":
                        st.write("**Cron配置**")
                        col1, col2 = st.columns(2)
                        with col1:
                            hour = st.number_input("小时 (0-23)", min_value=0, max_value=23, value=0)
                            minute = st.number_input("分钟 (0-59)", min_value=0, max_value=59, value=0)
                        with col2:
                            day_of_week = st.text_input("星期几 (可选)", placeholder="mon,tue,wed")
                        
                        trigger_config = {"hour": hour, "minute": minute}
                        if day_of_week:
                            trigger_config["day_of_week"] = day_of_week
                    
                    else:  # interval
                        st.write("**间隔配置**")
                        interval_value = st.number_input("间隔值", min_value=1, value=1)
                        interval_unit = st.selectbox("间隔单位", ["hours", "minutes", "seconds"])
                        
                        trigger_config = {interval_unit: interval_value}
                    
                    args_json = st.text_area("参数 (JSON)", value="{}")
                    
                    submitted = st.form_submit_button("创建任务")
                    
                    if submitted:
                        if not job_name:
                            st.error("请填写任务名称")
                        else:
                            try:
                                args = json.loads(args_json)
                                
                                scheduler = SchedulerService(DB_PATH)
                                job_id = scheduler.create_job(
                                    name=job_name,
                                    tool_id=selected_tool_id,
                                    trigger_type=trigger_type,
                                    trigger_config=trigger_config,
                                    args=args,
                                    created_by="web_ui"
                                )
                                
                                st.success(f"✅ 任务创建成功: {job_name}")
                                st.info(f"任务ID: {job_id}")
                            
                            except json.JSONDecodeError:
                                st.error("❌ 参数格式错误，请输入有效的JSON")
                            except Exception as e:
                                st.error(f"❌ 创建失败: {e}")
        
        except ImportError:
            st.error("❌ 定时任务功能需要安装APScheduler: `pip install apscheduler`")


# ==================== 页脚 ====================
st.sidebar.markdown("---")
st.sidebar.caption("Automation Hub v2.0")
st.sidebar.caption("© 2026 - 基于Streamlit构建")
