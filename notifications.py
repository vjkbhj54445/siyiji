"""
通知系统

支持多种通知渠道：SMTP邮件、Webhook、Telegram
"""

import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class NotificationMessage:
    """通知消息"""
    title: str
    content: str
    level: str = "info"  # info, warning, error, success
    metadata: Optional[Dict[str, Any]] = None


class SMTPNotifier:
    """SMTP邮件通知器"""
    
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        to_addrs: List[str]
    ):
        """
        初始化SMTP通知器
        
        Args:
            host: SMTP服务器地址
            port: SMTP端口
            user: 用户名
            password: 密码
            from_addr: 发件人地址
            to_addrs: 收件人地址列表
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
    
    def send(self, message: NotificationMessage) -> bool:
        """
        发送邮件通知
        
        Args:
            message: 通知消息
            
        Returns:
            是否成功
        """
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{message.level.upper()}] {message.title}"
            msg['From'] = self.from_addr
            msg['To'] = ", ".join(self.to_addrs)
            
            # 文本内容
            text_part = MIMEText(message.content, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # HTML内容（可选）
            html_content = self._format_html(message)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 发送
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
            
            logger.info(f"邮件通知已发送: {message.title}")
            return True
        
        except Exception as e:
            logger.exception(f"邮件发送失败: {e}")
            return False
    
    def _format_html(self, message: NotificationMessage) -> str:
        """格式化HTML邮件内容"""
        level_colors = {
            "info": "#3498db",
            "success": "#2ecc71",
            "warning": "#f39c12",
            "error": "#e74c3c"
        }
        
        color = level_colors.get(message.level, "#95a5a6")
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: {color}; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .metadata {{ background-color: #ecf0f1; padding: 10px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{message.title}</h2>
            </div>
            <div class="content">
                <pre>{message.content}</pre>
            </div>
        """
        
        if message.metadata:
            html += f"""
            <div class="metadata">
                <strong>元数据:</strong><br>
                <pre>{json.dumps(message.metadata, indent=2, ensure_ascii=False)}</pre>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        return html


class WebhookNotifier:
    """Webhook通知器"""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        """
        初始化Webhook通知器
        
        Args:
            url: Webhook URL
            headers: 自定义请求头
        """
        self.url = url
        self.headers = headers or {}
    
    def send(self, message: NotificationMessage) -> bool:
        """
        发送Webhook通知
        
        Args:
            message: 通知消息
            
        Returns:
            是否成功
        """
        try:
            payload = {
                "title": message.title,
                "content": message.content,
                "level": message.level,
                "metadata": message.metadata or {}
            }
            
            response = requests.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            response.raise_for_status()
            
            logger.info(f"Webhook通知已发送: {message.title}")
            return True
        
        except Exception as e:
            logger.exception(f"Webhook发送失败: {e}")
            return False


class TelegramNotifier:
    """Telegram Bot通知器"""
    
    def __init__(self, token: str, chat_id: str):
        """
        初始化Telegram通知器
        
        Args:
            token: Bot Token
            chat_id: 聊天ID
        """
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"
    
    def send(self, message: NotificationMessage) -> bool:
        """
        发送Telegram通知
        
        Args:
            message: 通知消息
            
        Returns:
            是否成功
        """
        try:
            # 格式化消息
            level_emoji = {
                "info": "ℹ️",
                "success": "✅",
                "warning": "⚠️",
                "error": "❌"
            }
            
            emoji = level_emoji.get(message.level, "📢")
            
            text = f"{emoji} *{message.title}*\n\n{message.content}"
            
            if message.metadata:
                text += f"\n\n_元数据:_\n```json\n{json.dumps(message.metadata, indent=2, ensure_ascii=False)}\n```"
            
            # 发送消息
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                },
                timeout=10
            )
            
            response.raise_for_status()
            
            logger.info(f"Telegram通知已发送: {message.title}")
            return True
        
        except Exception as e:
            logger.exception(f"Telegram发送失败: {e}")
            return False


class NotificationService:
    """通知服务（统一入口）"""
    
    def __init__(self):
        """初始化通知服务"""
        from automation_hub.config import get_config
        
        config = get_config()
        self.notifiers = []
        
        # 初始化SMTP
        if config.notification.enabled and config.notification.smtp_host:
            try:
                smtp = SMTPNotifier(
                    host=config.notification.smtp_host,
                    port=config.notification.smtp_port,
                    user=config.notification.smtp_user,
                    password=config.notification.smtp_password,
                    from_addr=config.notification.smtp_from,
                    to_addrs=config.notification.smtp_to
                )
                self.notifiers.append(smtp)
                logger.info("SMTP通知器已初始化")
            except Exception as e:
                logger.warning(f"SMTP通知器初始化失败: {e}")
        
        # 初始化Webhook
        if config.notification.enabled and config.notification.webhook_url:
            try:
                webhook = WebhookNotifier(url=config.notification.webhook_url)
                self.notifiers.append(webhook)
                logger.info("Webhook通知器已初始化")
            except Exception as e:
                logger.warning(f"Webhook通知器初始化失败: {e}")
        
        # 初始化Telegram
        if config.notification.enabled and config.notification.telegram_token:
            try:
                telegram = TelegramNotifier(
                    token=config.notification.telegram_token,
                    chat_id=config.notification.telegram_chat_id
                )
                self.notifiers.append(telegram)
                logger.info("Telegram通知器已初始化")
            except Exception as e:
                logger.warning(f"Telegram通知器初始化失败: {e}")
    
    def send(self, message: NotificationMessage):
        """
        发送通知到所有渠道
        
        Args:
            message: 通知消息
        """
        if not self.notifiers:
            logger.warning("没有配置通知渠道")
            return
        
        for notifier in self.notifiers:
            try:
                notifier.send(message)
            except Exception as e:
                logger.exception(f"通知发送失败: {e}")
    
    def notify_run_completed(
        self,
        tool_name: str,
        success: bool,
        run_id: str,
        output: str = ""
    ):
        """
        通知任务完成
        
        Args:
            tool_name: 工具名称
            success: 是否成功
            run_id: 任务ID
            output: 输出内容
        """
        level = "success" if success else "error"
        title = f"任务{'成功' if success else '失败'}: {tool_name}"
        
        content = f"任务ID: {run_id}\n"
        if output:
            content += f"\n输出:\n{output[:500]}"  # 截断长输出
        
        message = NotificationMessage(
            title=title,
            content=content,
            level=level,
            metadata={"run_id": run_id, "tool": tool_name}
        )
        
        self.send(message)
    
    def notify_approval_needed(
        self,
        tool_name: str,
        approval_id: str,
        risk_level: str
    ):
        """
        通知需要审批
        
        Args:
            tool_name: 工具名称
            approval_id: 审批ID
            risk_level: 风险级别
        """
        message = NotificationMessage(
            title=f"需要审批: {tool_name}",
            content=f"工具: {tool_name}\n风险级别: {risk_level}\n审批ID: {approval_id}",
            level="warning",
            metadata={"approval_id": approval_id, "risk_level": risk_level}
        )
        
        self.send(message)
    
    def notify_error(self, title: str, error: str):
        """
        通知错误
        
        Args:
            title: 标题
            error: 错误信息
        """
        message = NotificationMessage(
            title=title,
            content=error,
            level="error"
        )
        
        self.send(message)


# 全局通知服务实例
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """获取通知服务实例"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def send_notification(message: NotificationMessage):
    """发送通知（便捷函数）"""
    service = get_notification_service()
    service.send(message)


if __name__ == "__main__":
    # 测试
    message = NotificationMessage(
        title="测试通知",
        content="这是一条测试消息",
        level="info",
        metadata={"test": True}
    )
    
    send_notification(message)
