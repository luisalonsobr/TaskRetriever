import subprocess
import os
import shutil
import time
import sys
import shlex
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict

class MacNotifier:
    def __init__(self):
        self.script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        self.python_cmd = sys.executable or "python3"
        
    def send_task_notification(self, task_data: Dict, message: Dict, task_id: int = None):
        """Send a clickable macOS notification for a new task"""
        try:
            # Prepare notification content
            title = self._escape_applescript_string(f"Nova Tarefa - {message['chat_name']}")
            subtitle = self._escape_applescript_string(f"De: {message['sender']}")
            message_text = str(task_data['task_description'])
            
            # Priority emoji
            priority_emoji = {
                'alta': '🔴',
                'média': '🟡',
                'baixa': '🟢'
            }.get(task_data.get('priority', 'média'), '🟡')
            
            body = f"{priority_emoji} {message_text}"
            
            # Add deadline if present
            if task_data.get('deadline'):
                body += f"\n⏰ Prazo: {task_data['deadline']}"
            body_for_applescript = self._escape_applescript_string(body)
            execute_cmd = self._build_gui_launch_command(task_id)
            
            # Keep this as a single line for robust parsing.
            applescript = (
                f'display notification "{body_for_applescript}" '
                f'with title "{title}" subtitle "{subtitle}"'
            )

            sent = self._send_with_terminal_notifier(
                title=f"Nova Tarefa - {message['chat_name']}",
                subtitle=f"De: {message['sender']}",
                message=body,
                execute=execute_cmd,
            )
            if not sent:
                sent = self._send_with_osascript(applescript)

            if sent:
                print(f"✅ Notification sent: {task_data['task_description']}")
            else:
                print("❌ Notification failed with all available methods")

        except Exception as e:
            print(f"❌ Unexpected error in notification: {e}")

    def _escape_applescript_string(self, value: str) -> str:
        """Escape untrusted text before embedding in AppleScript string literals."""
        if not isinstance(value, str):
            value = str(value)
        
        # Limit length to prevent overly long notifications
        if len(value) > 500:
            value = value[:497] + "..."
        
        return (
            value
            .replace("\\", "\\\\")  # Backslashes first
            .replace('"', '\\"')    # Double quotes
            .replace("\r", " ")     # Carriage returns
            .replace("\n", " ")     # Newlines
            .replace("\t", " ")     # Tabs
        )
    
    def send_summary_notification(self, task_count: int):
        """Send a summary notification when multiple tasks are detected"""
        if task_count == 0:
            return
            
        try:
            title = "WhatsApp Tasks"
            body = f"🔔 {task_count} nova{'s' if task_count > 1 else ''} tarefa{'s' if task_count > 1 else ''} detectada{'s' if task_count > 1 else ''}!"

            applescript = (
                f'display notification "{self._escape_applescript_string(body)}" '
                f'with title "{self._escape_applescript_string(title)}"'
            )
            if not self._send_with_terminal_notifier(
                title=title,
                subtitle="",
                message=body,
                execute=self._build_gui_launch_command(None),
            ):
                self._send_with_osascript(applescript)

        except Exception as e:
            print(f"❌ Failed to send summary notification: {e}")
    
    def test_notifications(self):
        """Test if notifications work"""
        try:
            tn_path = self._find_terminal_notifier()
            if tn_path:
                print(f"ℹ️ terminal-notifier path: {tn_path}")
            else:
                print("ℹ️ terminal-notifier path: not found")

            applescript = (
                'display notification "Sistema de tarefas funcionando!" '
                'with title "WhatsApp Tasks" subtitle "Teste"'
            )
            if self._send_with_terminal_notifier(
                title="WhatsApp Tasks",
                subtitle="",
                message="Sistema de tarefas funcionando!",
            ):
                print("✅ Test notification sent successfully (terminal-notifier)")
                return True

            if self._send_with_osascript(applescript):
                print("✅ Test notification sent successfully (osascript)")
                return True

            print("❌ Test notification failed in all methods")
            return False
        except Exception as e:
            print(f"❌ Test notification failed: {e}")
            return False

    def _send_with_osascript(self, script: str) -> bool:
        """Try delivering a notification via osascript."""
        result = subprocess.run(
            ['osascript', '-e', script],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True

        stderr = (result.stderr or "").strip()
        if stderr:
            print(f"⚠️ osascript notification error: {stderr}")
        else:
            print(f"⚠️ osascript notification failed with code {result.returncode}")
        return False

    def _send_with_terminal_notifier(
        self,
        title: str,
        subtitle: str,
        message: str,
        execute: str = "",
    ) -> bool:
        """Fallback notifier if terminal-notifier is installed."""
        binary = self._find_terminal_notifier()
        if not binary:
            print("⚠️ terminal-notifier not found in PATH or common install paths")
            return False

        # Use a unique group id to avoid macOS coalescing/replacing previous notifications.
        group_id = f"whatsapp-task-{int(time.time() * 1000)}"
        cmd = [
            binary,
            "-title", title,
            "-message", message,
            "-group", group_id,
        ]
        if subtitle:
            cmd.extend(["-subtitle", subtitle])
        if execute:
            cmd.extend(["-execute", execute])

        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            return True

        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        if stdout:
            print(f"⚠️ terminal-notifier output: {stdout}")
        if stderr:
            print(f"⚠️ terminal-notifier error: {stderr}")
        if result.returncode < 0:
            print(f"⚠️ terminal-notifier terminated by signal {-result.returncode}")
        else:
            print(f"⚠️ terminal-notifier exit code: {result.returncode}")
        return False

    def _build_gui_launch_command(self, task_id: int = None) -> str:
        """Build shell-safe command to open the GUI, optionally focused on a task."""
        app_path = os.path.expanduser("~/Applications/WhatsApp Task Manager.app")
        if os.path.isdir(app_path):
            parts = ["open", "-a", app_path, "--args"]
        else:
            parts = [self.python_cmd, self.script_path, "gui"]

        if task_id is not None:
            parts.extend(["--focus-task", str(task_id)])
        return " ".join(shlex.quote(part) for part in parts)

    def _find_terminal_notifier(self) -> str:
        """Find terminal-notifier across common Homebrew locations."""
        env_path = os.getenv("TERMINAL_NOTIFIER_PATH", "").strip()
        candidates = []
        if env_path:
            candidates.append(env_path)
        which_path = shutil.which("terminal-notifier")
        if which_path:
            candidates.append(which_path)
        candidates.extend([
            "/opt/homebrew/bin/terminal-notifier",
            "/usr/local/bin/terminal-notifier",
        ])

        for path in candidates:
            if path and os.path.exists(path) and os.access(path, os.X_OK):
                return path
        return ""


class EmailNotifier:
    def __init__(self):
        from config import MAIL_HOST, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_ENCRYPTION, MAIL_TO, MAIL_FROM
        self.host = MAIL_HOST
        self.port = MAIL_PORT
        self.username = MAIL_USERNAME
        self.password = MAIL_PASSWORD
        self.encryption = MAIL_ENCRYPTION.lower()
        self.mail_to = MAIL_TO
        self.mail_from = MAIL_FROM
    def is_configured(self) -> bool:
        return bool(self.host and self.mail_to)

    def _connect(self) -> smtplib.SMTP:
        """Open an authenticated SMTP connection and return the server object."""
        if self.encryption == 'tls':
            server = smtplib.SMTP_SSL(self.host, self.port)
        else:
            server = smtplib.SMTP(self.host, self.port)
            if self.encryption == 'starttls':
                server.ehlo()
                server.starttls()
                server.ehlo()
        if self.username and self.password:
            server.login(self.username, self.password)
        return server

    def _log_send_error(self, e: Exception, prefix: str = "⚠️ Email"):
        """Log a categorised SMTP/network error."""
        if isinstance(e, smtplib.SMTPAuthenticationError):
            print(f"{prefix} auth failed for {self.username}: {e}")
        elif isinstance(e, smtplib.SMTPConnectError):
            print(f"{prefix} connection failed ({self.host}:{self.port}): {e}")
        elif isinstance(e, smtplib.SMTPException):
            print(f"{prefix} SMTP error: {e}")
        elif isinstance(e, ssl.SSLError):
            hint = ""
            if self.encryption == 'tls' and self.port == 587:
                hint = " — port 587 requires MAIL_ENCRYPTION=starttls"
            elif self.encryption == 'starttls' and self.port == 465:
                hint = " — port 465 requires MAIL_ENCRYPTION=tls"
            print(f"{prefix} SSL error{hint}: {e}")
        else:
            print(f"{prefix} network error: {e}")

    def test(self) -> bool:
        """Send a test email to MAIL_TO and return True on success."""
        if not self.is_configured():
            print("⚠️ Email not configured (MAIL_HOST or MAIL_TO missing) — skipping email test")
            return True  # Not a failure, just not set up

        print(f"  Connecting to {self.host}:{self.port} (encryption={self.encryption})...")
        try:
            if self.username:
                print(f"  Authenticating as {self.username}...")
            server = self._connect()

            msg = MIMEMultipart()
            msg['From'] = self.mail_from
            msg['To'] = self.mail_to
            msg['Subject'] = "WhatsApp Task Manager - Test Email"
            msg.attach(MIMEText(
                "This is a test email from WhatsApp Task Manager.\n\n"
                "If you received this, email notifications are working correctly.",
                'plain'
            ))

            server.sendmail(msg['From'], self.mail_to, msg.as_string())
            server.quit()
            print(f"  Test email sent to {self.mail_to}")
            return True
        except Exception as e:
            self._log_send_error(e, prefix="  ❌")
            return False

    def send_task_notification(self, task_data: Dict, message: Dict, task_id: int = None):
        if not self.is_configured():
            return

        priority_label = {
            'alta': 'High',
            'média': 'Medium',
            'baixa': 'Low',
        }.get(task_data.get('priority', 'média'), 'Medium')

        task_id_str = f"#{task_id}" if task_id else ""
        subject = f"New Task {task_id_str}: {task_data['task_description'][:60]}"
        deadline_line = f"Deadline: {task_data['deadline']}" if task_data.get('deadline') else "Deadline: -"

        body = (
            f"New task detected from WhatsApp.\n\n"
            f"Task {task_id_str}\n"
            f"{'=' * 40}\n"
            f"Description : {task_data['task_description']}\n"
            f"Priority    : {priority_label}\n"
            f"{deadline_line}\n\n"
            f"Chat        : {message.get('chat_name', '')}\n"
            f"Sender      : {message.get('sender', '')}\n\n"
            f"Original message:\n{message.get('message_content', '')}\n"
        )

        msg = MIMEMultipart()
        msg['From'] = self.username or f"taskmanager@{self.host}"
        msg['To'] = self.mail_to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            server = self._connect()
            server.sendmail(msg['From'], self.mail_to, msg.as_string())
            server.quit()
            print(f"📧 Email notification sent to {self.mail_to}")
        except Exception as e:
            self._log_send_error(e)
