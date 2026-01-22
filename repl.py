"""
交互式REPL模式

提供类似iPython的交互式命令行界面
"""

import cmd
import sqlite3
import json
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from automation_hub.config import get_config
from automation_hub.formatters import OutputFormatter, ResultFormatter
from automation_hub.simple_executor import SimpleExecutor


class AutomationHubREPL(cmd.Cmd):
    """Automation Hub 交互式Shell"""
    
    intro = """
╔══════════════════════════════════════════════════════════╗
║          Automation Hub Interactive Shell               ║
║                                                          ║
║  输入 'help' 查看可用命令                                  ║
║  输入 'exit' 或 Ctrl+D 退出                               ║
╚══════════════════════════════════════════════════════════╝
    """
    
    prompt = '(automation-hub) '
    
    def __init__(self):
        super().__init__()
        self.console = Console()
        self.config = get_config()
        self.db_path = self.config.database.path
        self.executor = SimpleExecutor(self.db_path)
        self.formatter = OutputFormatter(
            format=self.config.output.format,
            color=self.config.output.color
        )
        self.current_tool = None
    
    def do_tools(self, arg):
        """
        工具管理
        
        用法:
            tools               - 列出所有工具
            tools <tool_id>     - 查看工具详情
        """
        if not arg:
            # 列出所有工具
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, risk_level, enabled 
                FROM tools 
                ORDER BY name
            """)
            
            tools = cursor.fetchall()
            conn.close()
            
            if not tools:
                self.console.print("[yellow]暂无工具[/yellow]")
                return
            
            table = Table(title="工具列表", box=box.ROUNDED)
            table.add_column("ID", style="cyan")
            table.add_column("名称", style="white")
            table.add_column("风险级别", style="yellow")
            table.add_column("状态", style="green")
            
            for tool in tools:
                status = "✅ 启用" if tool[3] else "❌ 禁用"
                table.add_row(tool[0], tool[1], tool[2], status)
            
            self.console.print(table)
        
        else:
            # 查看工具详情
            tool_id = arg.strip()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, description, risk_level, executor, 
                       command_json, args_schema_json, enabled
                FROM tools
                WHERE id = ?
            """, (tool_id,))
            
            tool = cursor.fetchone()
            conn.close()
            
            if not tool:
                self.console.print(f"[red]工具不存在: {tool_id}[/red]")
                return
            
            self.console.print(Panel(f"[bold]{tool[1]}[/bold]", box=box.ROUNDED))
            self.console.print(f"[cyan]ID:[/cyan] {tool[0]}")
            self.console.print(f"[cyan]描述:[/cyan] {tool[2] or 'N/A'}")
            self.console.print(f"[cyan]风险级别:[/cyan] {tool[3]}")
            self.console.print(f"[cyan]执行器:[/cyan] {tool[4]}")
            self.console.print(f"[cyan]状态:[/cyan] {'✅ 启用' if tool[7] else '❌ 禁用'}")
            
            if tool[5]:
                command = json.loads(tool[5])
                self.console.print(f"\n[cyan]命令:[/cyan]")
                self.console.print(json.dumps(command, indent=2))
            
            if tool[6]:
                schema = json.loads(tool[6])
                self.console.print(f"\n[cyan]参数Schema:[/cyan]")
                self.console.print(json.dumps(schema, indent=2))
    
    def do_use(self, arg):
        """
        选择工具（设置为当前工具）
        
        用法:
            use <tool_id>
        """
        if not arg:
            self.console.print("[red]请指定工具ID[/red]")
            return
        
        tool_id = arg.strip()
        
        # 验证工具存在
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM tools WHERE id = ?", (tool_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            self.console.print(f"[red]工具不存在: {tool_id}[/red]")
            return
        
        self.current_tool = tool_id
        self.prompt = f'(automation-hub:{tool_id}) '
        self.console.print(f"[green]✅ 当前工具: {result[0]}[/green]")
    
    def do_run(self, arg):
        """
        执行工具
        
        用法:
            run <tool_id> <args_json>   - 执行指定工具
            run <args_json>              - 执行当前工具（需先use）
        
        示例:
            run code_search {"pattern": "TODO"}
            use code_search
            run {"pattern": "FIXME"}
        """
        if not arg and not self.current_tool:
            self.console.print("[red]请先使用 'use <tool_id>' 选择工具，或指定工具ID[/red]")
            return
        
        # 解析参数
        parts = arg.split(None, 1)
        
        if self.current_tool and (not parts or parts[0].startswith('{')):
            # 使用当前工具
            tool_id = self.current_tool
            args_str = arg if arg else '{}'
        else:
            # 指定工具
            if len(parts) < 2:
                self.console.print("[red]用法: run <tool_id> <args_json>[/red]")
                return
            tool_id = parts[0]
            args_str = parts[1]
        
        # 解析参数JSON
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError as e:
            self.console.print(f"[red]参数JSON格式错误: {e}[/red]")
            return
        
        # 执行
        with self.console.status(f"[cyan]执行中: {tool_id}...[/cyan]"):
            result = self.executor.execute_tool(
                tool_id=tool_id,
                args=args,
                user_id="repl"
            )
        
        # 显示结果
        formatted = ResultFormatter.format_run_result(result, self.formatter)
        self.console.print(formatted)
    
    def do_runs(self, arg):
        """
        查看任务列表
        
        用法:
            runs           - 列出最近的任务
            runs <limit>   - 列出指定数量的任务
        """
        limit = 10
        if arg:
            try:
                limit = int(arg)
            except ValueError:
                self.console.print("[red]参数必须是数字[/red]")
                return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT r.id, t.name, r.status, r.created_at, r.exit_code
            FROM runs r
            LEFT JOIN tools t ON r.tool_id = t.id
            ORDER BY r.created_at DESC
            LIMIT ?
        """, (limit,))
        
        runs = cursor.fetchall()
        conn.close()
        
        if not runs:
            self.console.print("[yellow]暂无任务记录[/yellow]")
            return
        
        table = Table(title=f"最近 {limit} 个任务", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("工具", style="white")
        table.add_column("状态", style="yellow")
        table.add_column("时间", style="dim")
        table.add_column("退出码", justify="right")
        
        for run in runs:
            status_icon = {
                "succeeded": "✅",
                "failed": "❌",
                "running": "🔄",
                "queued": "⏳"
            }.get(run[2], "❓")
            
            table.add_row(
                run[0][:8],
                run[1] or "Unknown",
                f"{status_icon} {run[2]}",
                run[3][:19] if run[3] else "",
                str(run[4]) if run[4] is not None else "N/A"
            )
        
        self.console.print(table)
    
    def do_config(self, arg):
        """
        配置管理
        
        用法:
            config             - 显示当前配置
            config reload      - 重新加载配置
        """
        if arg == "reload":
            from automation_hub.config import reload_config
            reload_config()
            self.config = get_config()
            self.console.print("[green]✅ 配置已重新加载[/green]")
        else:
            # 显示配置
            self.console.print(Panel("[bold]当前配置[/bold]", box=box.ROUNDED))
            self.console.print(f"[cyan]数据库:[/cyan] {self.config.database.path}")
            self.console.print(f"[cyan]API:[/cyan] {self.config.api.base_url}")
            self.console.print(f"[cyan]输出格式:[/cyan] {self.config.output.format}")
            self.console.print(f"[cyan]彩色输出:[/cyan] {self.config.output.color}")
    
    def do_format(self, arg):
        """
        设置输出格式
        
        用法:
            format table   - 表格格式
            format json    - JSON格式
            format yaml    - YAML格式
        """
        if arg not in ["table", "json", "yaml"]:
            self.console.print("[red]格式必须是: table, json, yaml[/red]")
            return
        
        self.config.output.format = arg
        self.formatter = OutputFormatter(
            format=arg,
            color=self.config.output.color
        )
        self.console.print(f"[green]✅ 输出格式已设置为: {arg}[/green]")
    
    def do_status(self, arg):
        """显示系统状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM tools WHERE enabled = 1")
        enabled_tools = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM runs WHERE status = 'queued'")
        queued = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM runs WHERE status = 'running'")
        running = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM approval_requests WHERE status = 'pending'")
        pending_approvals = cursor.fetchone()[0]
        
        conn.close()
        
        self.console.print(Panel("[bold]系统状态[/bold]", box=box.ROUNDED))
        self.console.print(f"[cyan]启用工具:[/cyan] {enabled_tools}")
        self.console.print(f"[cyan]排队任务:[/cyan] {queued}")
        self.console.print(f"[cyan]运行中:[/cyan] {running}")
        self.console.print(f"[cyan]待审批:[/cyan] {pending_approvals}")
    
    def do_clear(self, arg):
        """清屏"""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def do_exit(self, arg):
        """退出REPL"""
        self.console.print("[yellow]再见！[/yellow]")
        return True
    
    def do_quit(self, arg):
        """退出REPL（同exit）"""
        return self.do_exit(arg)
    
    def do_EOF(self, arg):
        """Ctrl+D退出"""
        print()  # 换行
        return self.do_exit(arg)
    
    def emptyline(self):
        """空行不执行任何操作"""
        pass
    
    def default(self, line):
        """处理未知命令"""
        self.console.print(f"[red]未知命令: {line}[/red]")
        self.console.print("[dim]输入 'help' 查看可用命令[/dim]")


def start_repl():
    """启动REPL"""
    repl = AutomationHubREPL()
    try:
        repl.cmdloop()
    except KeyboardInterrupt:
        print("\n再见！")


if __name__ == "__main__":
    start_repl()
