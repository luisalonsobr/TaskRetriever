import subprocess
import os
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
            
            # AppleScript for clickable notification
            applescript = f'''
            display notification "{body}" with title "{title}" subtitle "{subtitle}" sound name "Glass"
            '''
            
            # Execute the notification
            subprocess.run(['osascript', '-e', applescript], check=True)
            
            print(f"✅ Notification sent: {task_data['task_description']}")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to send notification: {e}")
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
            
            # Make it clickable to open the task list
            applescript = f'''
            set response to display notification "{body}" with title "{title}" sound name "Glass"
            '''
            
            subprocess.run(['osascript', '-e', applescript], check=True)
            
        except Exception as e:
            print(f"❌ Failed to send summary notification: {e}")
    
    def test_notifications(self):
        """Test if notifications work"""
        try:
            applescript = '''
            display notification "Sistema de tarefas funcionando!" with title "WhatsApp Tasks" subtitle "Teste" sound name "Glass"
            '''
            subprocess.run(['osascript', '-e', applescript], check=True)
            print("✅ Test notification sent successfully")
            return True
        except Exception as e:
            print(f"❌ Test notification failed: {e}")
            return False
