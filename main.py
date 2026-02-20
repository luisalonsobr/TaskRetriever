#!/usr/bin/env python3

import sys
import time
import argparse
from datetime import datetime
from typing import List

from db_manager import DatabaseManager
from task_detector import TaskDetector
from notifier import MacNotifier
from config import POLL_INTERVAL

class WhatsAppTaskManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.detector = TaskDetector()
        self.notifier = MacNotifier()
        
    def scan_for_tasks(self) -> int:
        """Scan for new tasks and return count of tasks found"""
        print("🔍 Scanning for new messages...")
        
        # Get new unprocessed messages
        messages = self.db.get_new_messages()
        
        if not messages:
            print("📝 No new messages found")
            return 0
            
        print(f"📨 Found {len(messages)} new messages")
        
        tasks_detected = 0
        
        for message in messages:
            try:
                print(f"Analyzing message from {message['sender']} in {message['chat_name']}")
                
                # Detect if message contains a task
                task_data = self.detector.detect_task(message)
                
                if task_data:
                    # Save task to database
                    task_id = self.db.save_task(message, task_data)
                    
                    # Send notification
                    self.notifier.send_task_notification(task_data, message)
                    
                    tasks_detected += 1
                    print(f"✅ Task #{task_id} detected: {task_data['task_description']}")
                
                # Mark message as processed regardless of task detection
                self.db.mark_message_processed(message['id'])
                
            except Exception as e:
                print(f"❌ Error processing message {message['id']}: {e}")
                # Still mark as processed to avoid reprocessing
                self.db.mark_message_processed(message['id'])
                
        if tasks_detected > 0:
            print(f"🎉 Detected {tasks_detected} new task{'s' if tasks_detected > 1 else ''}!")
        else:
            print("📭 No tasks detected in new messages")
            
        return tasks_detected
    
    def list_tasks(self):
        """List all pending tasks"""
        tasks = self.db.get_pending_tasks()
        
        if not tasks:
            print("📭 No pending tasks")
            return
            
        print(f"\n📋 Pending Tasks ({len(tasks)} total):")
        print("=" * 60)
        
        for task in tasks:
            priority_emoji = {
                'alta': '🔴',
                'média': '🟡', 
                'baixa': '🟢'
            }.get(task['priority'], '🟡')
            
            print(f"\n#{task['id']} {priority_emoji} {task['task_description']}")
            print(f"   📱 {task['chat_name']} | 👤 {task['sender']}")
            print(f"   📅 {self._format_timestamp(task['timestamp'])}")
            
            if task['deadline']:
                print(f"   ⏰ Prazo: {task['deadline']}")
                
            print(f"   💬 \"{task['message_content'][:50]}...\"")
            
        print("\n💡 Use 'python main.py done <task_id>' to mark a task as completed")
    
    def mark_task_done(self, task_id: int) -> bool:
        """Mark a task as completed"""
        success = self.db.mark_task_completed(task_id)
        if success:
            print(f"✅ Task #{task_id} marked as completed!")
        else:
            print(f"❌ Task #{task_id} not found")
        return success
    
    def watch_mode(self):
        """Run in daemon mode, continuously scanning for tasks"""
        print(f"👁️  Starting watch mode (checking every {POLL_INTERVAL} seconds)")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                try:
                    tasks_found = self.scan_for_tasks()
                    
                    if tasks_found > 0:
                        print(f"🔔 {tasks_found} new task{'s' if tasks_found > 1 else ''} detected!")
                    
                    time.sleep(POLL_INTERVAL)
                    
                except KeyboardInterrupt:
                    print("\n👋 Stopping watch mode...")
                    break
                except Exception as e:
                    print(f"❌ Error in watch mode: {e}")
                    time.sleep(POLL_INTERVAL)
                    
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
    
    def test_system(self):
        """Test all system components"""
        print("🧪 Testing WhatsApp Task Manager...")
        
        # Test Ollama connection
        print("Testing Ollama connection...")
        if self.detector.test_connection():
            print("✅ Ollama connection successful")
        else:
            print("❌ Ollama connection failed - make sure Ollama is running and qwen3:4b is installed")
            return False
            
        # Test notifications
        print("Testing notifications...")
        if self.notifier.test_notifications():
            print("✅ Notifications working")
        else:
            print("❌ Notification test failed")
            return False
            
        # Test database
        print("Testing database connections...")
        try:
            monitored_jids = self.db.get_monitored_chat_jids()
            print(f"✅ Found {len(monitored_jids)} monitored chats")
            if monitored_jids:
                print("Monitored chats:")
                for jid in monitored_jids[:5]:  # Show first 5
                    print(f"  - {jid}")
        except Exception as e:
            print(f"❌ Database test failed: {e}")
            return False
            
        print("\n🎉 All systems working!")
        return True

    def test_notifications(self) -> bool:
        """Run notification-only diagnostics."""
        print("🔔 Testing notification delivery...")
        ok = self.notifier.test_notifications()
        if ok:
            print("✅ Notification test passed")
        else:
            print("❌ Notification test failed")
        return ok
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display"""
        try:
            if timestamp.isdigit():
                dt = datetime.fromtimestamp(int(timestamp))
                return dt.strftime("%d/%m/%Y %H:%M")
            return timestamp
        except:
            return timestamp

def main():
    parser = argparse.ArgumentParser(description='WhatsApp Task Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Scan command
    subparsers.add_parser('scan', help='Scan for new tasks')
    
    # List command  
    subparsers.add_parser('list', help='List pending tasks')
    
    # Done command
    done_parser = subparsers.add_parser('done', help='Mark task as completed')
    done_parser.add_argument('task_id', type=int, help='Task ID to mark as done')
    
    # Watch command
    subparsers.add_parser('watch', help='Run in daemon mode')
    
    # Test command
    subparsers.add_parser('test', help='Test system components')
    subparsers.add_parser('notify-test', help='Test notification delivery only')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = WhatsAppTaskManager()
    
    try:
        if args.command == 'scan':
            manager.scan_for_tasks()
        elif args.command == 'list':
            manager.list_tasks()
        elif args.command == 'done':
            manager.mark_task_done(args.task_id)
        elif args.command == 'watch':
            manager.watch_mode()
        elif args.command == 'test':
            if not manager.test_system():
                sys.exit(1)
        elif args.command == 'notify-test':
            if not manager.test_notifications():
                sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
