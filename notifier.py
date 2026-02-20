import subprocess
import os
import shutil
import time
from typing import Dict

class MacNotifier:
    def __init__(self):
        self.script_path = "/Users/hardlou/dev/task-manager/main.py"
        
    def send_task_notification(self, task_data: Dict, message: Dict):
        """Send a clickable macOS notification for a new task"""
        try:
            # Prepare notification content
            title = self._escape_applescript_string(f"Nova Tarefa - {message['chat_name']}")
            subtitle = self._escape_applescript_string(f"De: {message['sender']}")
            message_text = task_data['task_description']
            
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
            body = self._escape_applescript_string(body)
            
            # Keep this as a single line for robust parsing.
            applescript = (
                f'display notification "{body}" '
                f'with title "{title}" subtitle "{subtitle}"'
            )

            sent = self._send_with_terminal_notifier(
                title=f"Nova Tarefa - {message['chat_name']}",
                subtitle=f"De: {message['sender']}",
                message=body,
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
        return (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", " ")
            .replace("\n", " ")
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
            if not self._send_with_terminal_notifier(title=title, subtitle="", message=body):
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

    def _send_with_terminal_notifier(self, title: str, subtitle: str, message: str) -> bool:
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
