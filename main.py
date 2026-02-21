#!/usr/bin/env python3

import sys
import time
import argparse
from datetime import datetime
from typing import List

tk = None
ttk = None
messagebox = None

from db_manager import DatabaseManager, DatabaseError
from task_detector import TaskDetector, OllamaError
from notifier import MacNotifier
from config import POLL_INTERVAL

class WhatsAppTaskManager:
    def __init__(self):
        try:
            self.db = DatabaseManager()
            self.detector = TaskDetector()
            self.notifier = MacNotifier()
        except DatabaseError as e:
            print(f"❌ Database initialization failed: {e}")
            print("💡 Make sure your .env file is configured with valid database paths")
            raise
        
    def scan_for_tasks(self) -> int:
        """Scan for new tasks and return count of tasks found"""
        print("🔍 Scanning for new messages...")
        
        try:
            # Get new unprocessed messages
            messages = self.db.get_new_messages()
        except DatabaseError as e:
            print(f"❌ Failed to get messages: {e}")
            return 0
        
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
                    try:
                        # Save task to database
                        task_id = self.db.save_task(message, task_data)
                        
                        # Send notification
                        self.notifier.send_task_notification(task_data, message, task_id=task_id)
                        
                        tasks_detected += 1
                        print(f"✅ Task #{task_id} detected: {task_data['task_description']}")
                    except DatabaseError as e:
                        print(f"❌ Failed to save task: {e}")
                        # Continue processing other messages
                
                # Mark message as processed regardless of task detection
                try:
                    self.db.mark_message_processed(message['id'])
                except DatabaseError as e:
                    print(f"⚠️ Failed to mark message as processed: {e}")
                    # Continue processing, but this message might be reprocessed later
                
            except Exception as e:
                print(f"❌ Error processing message {message['id']}: {e}")
                # Still mark as processed to avoid reprocessing
                try:
                    self.db.mark_message_processed(message['id'])
                except DatabaseError as e:
                    print(f"⚠️ Failed to mark message as processed: {e}")
                
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

    def mark_task_not_done(self, task_id: int) -> bool:
        """Mark a task as not completed."""
        success = self.db.mark_task_not_completed(task_id)
        if success:
            print(f"↩️ Task #{task_id} marked as not completed!")
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


class TaskManagerGUI:
    def __init__(self, manager: WhatsAppTaskManager, focus_task_id: int = None):
        global tk, ttk, messagebox
        if tk is None or ttk is None or messagebox is None:
            import tkinter as _tk
            from tkinter import ttk as _ttk, messagebox as _messagebox
            tk, ttk, messagebox = _tk, _ttk, _messagebox

        self.manager = manager
        self.focus_task_id = focus_task_id
        self.root = tk.Tk()
        self.root.title("WhatsApp Task Manager")
        self.root.geometry("1100x620")
        self.tasks_by_id = {}
        self.show_done_var = tk.BooleanVar(value=False)
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.refresh_interval_var = tk.IntVar(value=30)
        self._auto_refresh_job = None

        self._build_ui()
        self.refresh_tasks()
        self._schedule_auto_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(container)
        controls.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(controls, text="Refresh", command=self.refresh_tasks).pack(side=tk.LEFT)
        ttk.Button(controls, text="Scan Now", command=self.scan_now).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="Mark Done", command=self.mark_selected_done).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="Mark Not Done", command=self.mark_selected_not_done).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(
            controls,
            text="Show done tasks",
            variable=self.show_done_var,
            command=self.refresh_tasks,
        ).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Checkbutton(
            controls,
            text="Auto refresh",
            variable=self.auto_refresh_var,
            command=self._on_auto_refresh_toggle,
        ).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Label(controls, text="Every (s):").pack(side=tk.LEFT, padx=(8, 0))
        interval_spin = ttk.Spinbox(
            controls,
            from_=3,
            to=300,
            width=5,
            textvariable=self.refresh_interval_var,
            command=self._on_interval_change,
        )
        interval_spin.pack(side=tk.LEFT, padx=(4, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(controls, textvariable=self.status_var).pack(side=tk.RIGHT)

        columns = ("id", "status", "priority", "task", "chat", "sender", "deadline", "timestamp")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=14)
        self.tree.heading("id", text="ID")
        self.tree.heading("status", text="Status")
        self.tree.heading("priority", text="Priority")
        self.tree.heading("task", text="Task")
        self.tree.heading("chat", text="Chat")
        self.tree.heading("sender", text="Sender")
        self.tree.heading("deadline", text="Deadline")
        self.tree.heading("timestamp", text="Created")

        self.tree.column("id", width=60, stretch=False, anchor=tk.CENTER)
        self.tree.column("status", width=90, stretch=False, anchor=tk.CENTER)
        self.tree.column("priority", width=90, stretch=False, anchor=tk.CENTER)
        self.tree.column("task", width=300)
        self.tree.column("chat", width=155)
        self.tree.column("sender", width=155)
        self.tree.column("deadline", width=140, stretch=False)
        self.tree.column("timestamp", width=150, stretch=False)

        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_task_selected)
        self.tree.bind("<Double-1>", self._on_double_click)

        details_frame = ttk.LabelFrame(container, text="Task Details", padding=8)
        details_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.details = tk.Text(details_frame, height=10, wrap=tk.WORD)
        self.details.pack(fill=tk.BOTH, expand=True)
        self.details.configure(state=tk.DISABLED)

    def refresh_tasks(self):
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        tasks = self.manager.db.get_tasks(include_completed=self.show_done_var.get())
        self.tasks_by_id = {task["id"]: task for task in tasks}

        for task in tasks:
            self.tree.insert(
                "",
                tk.END,
                iid=str(task["id"]),
                values=(
                    task["id"],
                    "Done" if task.get("completed") else "Pending",
                    task.get("priority", "média"),
                    task.get("task_description", ""),
                    task.get("chat_name", ""),
                    task.get("sender", ""),
                    task.get("deadline") or "-",
                    self.manager._format_timestamp(str(task.get("timestamp", ""))),
                ),
            )

        total_count = len(tasks)
        done_count = sum(1 for task in tasks if task.get("completed"))
        pending_count = total_count - done_count
        if self.show_done_var.get():
            self.status_var.set(
                f"{pending_count} pending / {done_count} done ({total_count} total)"
            )
        else:
            self.status_var.set(f"{pending_count} pending task{'s' if pending_count != 1 else ''}")

        if self.focus_task_id and self.focus_task_id in self.tasks_by_id:
            focus_id = str(self.focus_task_id)
            self.tree.selection_set(focus_id)
            self.tree.focus(focus_id)
            self.tree.see(focus_id)
            self._on_task_selected()
            self.focus_task_id = None
        elif tasks:
            first_id = str(tasks[0]["id"])
            self.tree.selection_set(first_id)
            self.tree.focus(first_id)
            self._on_task_selected()
        else:
            self._set_details("No pending tasks.")

    def scan_now(self):
        try:
            found = self.manager.scan_for_tasks()
            self.refresh_tasks()
            self.status_var.set(f"Scan complete. {found} new task{'s' if found != 1 else ''} found")
        except Exception as e:
            messagebox.showerror("Scan Failed", str(e))

    def mark_selected_done(self):
        task_id = self._get_selected_task_id()
        if task_id is None:
            messagebox.showinfo("No Selection", "Select a task first.")
            return

        if not self.manager.mark_task_done(task_id):
            messagebox.showerror("Failed", f"Task #{task_id} not found")
            return

        self.refresh_tasks()

    def mark_selected_not_done(self):
        task_id = self._get_selected_task_id()
        if task_id is None:
            messagebox.showinfo("No Selection", "Select a task first.")
            return

        if not self.manager.mark_task_not_done(task_id):
            messagebox.showerror("Failed", f"Task #{task_id} not found")
            return

        self.refresh_tasks()

    def _get_selected_task_id(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _on_double_click(self, _event=None):
        task_id = self._get_selected_task_id()
        if task_id is None:
            return
        task = self.tasks_by_id.get(task_id)
        if not task:
            return
        if task.get("completed"):
            self.mark_selected_not_done()
        else:
            self.mark_selected_done()

    def _on_task_selected(self, _event=None):
        task_id = self._get_selected_task_id()
        if task_id is None:
            self._set_details("No task selected.")
            return

        task = self.tasks_by_id.get(task_id)
        if not task:
            self._set_details("Task details not available.")
            return

        content = "\n".join(
            [
                f"Task #{task['id']}",
                f"Description: {task.get('task_description', '')}",
                f"Priority: {task.get('priority', 'média')}",
                f"Status: {'Done' if task.get('completed') else 'Pending'}",
                f"Chat: {task.get('chat_name', '')}",
                f"Sender: {task.get('sender', '')}",
                f"Deadline: {task.get('deadline') or '-'}",
                f"Message time: {self.manager._format_timestamp(str(task.get('timestamp', '')))}",
                "",
                "Original message:",
                task.get("message_content", ""),
            ]
        )
        self._set_details(content)

    def _set_details(self, text: str):
        self.details.configure(state=tk.NORMAL)
        self.details.delete("1.0", tk.END)
        self.details.insert(tk.END, text)
        self.details.configure(state=tk.DISABLED)

    def run(self):
        self.root.mainloop()

    def _on_auto_refresh_toggle(self):
        if self.auto_refresh_var.get():
            self._schedule_auto_refresh()
        else:
            self._cancel_auto_refresh()

    def _on_interval_change(self):
        if self.auto_refresh_var.get():
            self._schedule_auto_refresh()

    def _schedule_auto_refresh(self):
        self._cancel_auto_refresh()
        if not self.auto_refresh_var.get():
            return
        try:
            interval_seconds = max(3, int(self.refresh_interval_var.get()))
        except Exception:
            interval_seconds = 10
            self.refresh_interval_var.set(interval_seconds)
        self._auto_refresh_job = self.root.after(interval_seconds * 1000, self._auto_refresh_tick)

    def _auto_refresh_tick(self):
        self._auto_refresh_job = None
        self.refresh_tasks()
        self._schedule_auto_refresh()

    def _cancel_auto_refresh(self):
        if self._auto_refresh_job is not None:
            self.root.after_cancel(self._auto_refresh_job)
            self._auto_refresh_job = None

    def _on_close(self):
        self._cancel_auto_refresh()
        self.root.destroy()

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
    gui_parser = subparsers.add_parser('gui', help='Open task manager GUI')
    gui_parser.add_argument('--focus-task', type=int, help='Focus/select a specific task ID')
    
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
        elif args.command == 'gui':
            gui = TaskManagerGUI(manager, focus_task_id=getattr(args, "focus_task", None))
            gui.run()
            
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
