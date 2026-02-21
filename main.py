#!/usr/bin/env python3

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import List

tk = None
ttk = None
messagebox = None

from db_manager import DatabaseManager, DatabaseError
from task_detector import TaskDetector, OllamaError
from notifier import MacNotifier, EmailNotifier
from config import POLL_INTERVAL, LOG_CLEANUP_DAILY, LOG_FILES

class WhatsAppTaskManager:
    def __init__(self):
        self._last_log_cleanup_date = None
        try:
            self.db = DatabaseManager()
            self.detector = TaskDetector()
            self.notifier = MacNotifier()
            self.email_notifier = EmailNotifier()
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
                        
                        # Send notifications
                        self.notifier.send_task_notification(task_data, message, task_id=task_id)
                        self.email_notifier.send_task_notification(task_data, message, task_id=task_id)
                        
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
        self._cleanup_logs_if_due()
        
        try:
            while True:
                try:
                    self._cleanup_logs_if_due()
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

    def _cleanup_logs_if_due(self):
        """Truncate configured log files at most once per day."""
        if not LOG_CLEANUP_DAILY:
            return

        today = datetime.now().date()
        if self._last_log_cleanup_date == today:
            return

        truncated_count = 0
        error_count = 0
        for log_file in LOG_FILES:
            path = Path(log_file)
            if not path.exists():
                continue
            try:
                # Truncate in place so active file descriptors keep writing.
                with path.open("w", encoding="utf-8"):
                    pass
                truncated_count += 1
            except Exception as e:
                error_count += 1
                print(f"⚠️ Failed to truncate log file {path}: {e}")

        self._last_log_cleanup_date = today
        if truncated_count > 0:
            print(f"🧹 Daily log cleanup: cleared {truncated_count} file(s)")
        elif error_count == 0:
            print("🧹 Daily log cleanup: no log files found to clear")
    
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

        # Test email
        print("Testing email notification...")
        if self.email_notifier.test():
            print("✅ Email working")
        else:
            print("❌ Email test failed")
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
        self.root.minsize(980, 560)
        self.tasks_by_id = {}
        self.show_done_var = tk.BooleanVar(value=False)
        self.auto_refresh_var = tk.BooleanVar(value=True)
        self.refresh_interval_var = tk.IntVar(value=30)
        self.search_var = tk.StringVar(value="")
        self.priority_filter_var = tk.StringVar(value="All")
        self.status_filter_var = tk.StringVar(value="Pending")
        self.sort_column = "timestamp"
        self.sort_desc = True
        self._auto_refresh_job = None
        self.sidebar_open = False

        self._setup_styles()
        self._build_ui()
        self.refresh_tasks()
        self._schedule_auto_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(bg="#0b1220")
        font_base = ("Avenir Next", 12)
        font_heading = ("Avenir Next Demi Bold", 13)
        font_title = ("Avenir Next Demi Bold", 18)

        style.configure(".", background="#0b1220", foreground="#dbeafe", font=font_base)
        style.configure("Main.TFrame", background="#0b1220")
        style.configure("Card.TFrame", background="#111a2e", relief="flat")
        style.configure("Title.TLabel", background="#0b1220", foreground="#f8fafc", font=font_title)
        style.configure("Hint.TLabel", background="#0b1220", foreground="#94a3b8", font=("Avenir Next", 11))
        style.configure("Status.TLabel", background="#111a2e", foreground="#93c5fd", font=("Avenir Next Demi Bold", 11))
        style.configure("Section.TLabel", background="#111a2e", foreground="#e2e8f0", font=font_heading)

        style.configure(
            "TButton",
            padding=(10, 7),
            relief="flat",
            borderwidth=0,
            background="#1f2a44",
            foreground="#e2e8f0",
        )
        style.map("TButton", background=[("active", "#273552")])
        style.configure("Primary.TButton", background="#3b82f6", foreground="#f8fafc")
        style.map("Primary.TButton", background=[("active", "#2563eb")])

        style.configure("TCheckbutton", background="#111a2e", foreground="#dbeafe")
        style.map("TCheckbutton", background=[("active", "#111a2e")])

        style.configure(
            "TEntry",
            fieldbackground="#0f172a",
            foreground="#e2e8f0",
            bordercolor="#334155",
            lightcolor="#334155",
            darkcolor="#334155",
            padding=6,
        )
        style.configure(
            "TCombobox",
            fieldbackground="#0f172a",
            background="#0f172a",
            foreground="#e2e8f0",
            padding=4,
        )
        style.configure(
            "TSpinbox",
            fieldbackground="#0f172a",
            background="#0f172a",
            foreground="#e2e8f0",
            padding=4,
        )

        style.configure(
            "Treeview",
            background="#0f172a",
            foreground="#dbeafe",
            fieldbackground="#0f172a",
            bordercolor="#1e293b",
            rowheight=30,
            font=("Avenir Next", 11),
        )
        style.configure(
            "Treeview.Heading",
            background="#17233a",
            foreground="#93c5fd",
            relief="flat",
            font=("Avenir Next Demi Bold", 11),
            padding=(8, 8),
        )
        style.map(
            "Treeview",
            background=[("selected", "#1d4ed8")],
            foreground=[("selected", "#f8fafc")],
        )
        style.map("Treeview.Heading", background=[("active", "#1e2f4d")])

    def _build_ui(self):
        container = ttk.Frame(self.root, padding=14, style="Main.TFrame")
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Task Inbox", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            container,
            text="Capture, triage, and close WhatsApp tasks quickly.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(2, 12))

        controls_card = ttk.Frame(container, padding=12, style="Card.TFrame")
        controls_card.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(controls_card, text="Actions", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        controls = ttk.Frame(controls_card, style="Card.TFrame")
        controls.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(controls, text="Refresh", command=self.refresh_tasks).pack(side=tk.LEFT)
        ttk.Button(controls, text="Scan Now", command=self.scan_now, style="Primary.TButton").pack(side=tk.LEFT, padx=(8, 0))
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
        self.info_btn = ttk.Button(controls, text="ⓘ", command=self._toggle_sidebar)
        self.info_btn.pack(side=tk.RIGHT, padx=(8, 8))
        ttk.Label(controls, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.RIGHT)

        filters_card = ttk.Frame(container, padding=12, style="Card.TFrame")
        filters_card.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(filters_card, text="Filters", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        filters = ttk.Frame(filters_card, style="Card.TFrame")
        filters.pack(fill=tk.X)
        ttk.Label(filters, text="Search:").pack(side=tk.LEFT)
        search_entry = ttk.Entry(filters, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(4, 12))
        search_entry.bind("<KeyRelease>", self._on_filter_change)

        ttk.Label(filters, text="Priority:").pack(side=tk.LEFT)
        priority_filter = ttk.Combobox(
            filters,
            textvariable=self.priority_filter_var,
            values=("All", "alta", "média", "baixa"),
            state="readonly",
            width=10,
        )
        priority_filter.pack(side=tk.LEFT, padx=(4, 12))
        priority_filter.bind("<<ComboboxSelected>>", self._on_filter_change)

        ttk.Label(filters, text="Status:").pack(side=tk.LEFT)
        status_filter = ttk.Combobox(
            filters,
            textvariable=self.status_filter_var,
            values=("Pending", "Done", "All"),
            state="readonly",
            width=10,
        )
        status_filter.pack(side=tk.LEFT, padx=(4, 12))
        status_filter.bind("<<ComboboxSelected>>", self._on_filter_change)

        ttk.Button(filters, text="Clear Filters", command=self._clear_filters).pack(side=tk.LEFT)
        search_entry.focus_set()

        content_frame = ttk.Frame(container, style="Main.TFrame")
        content_frame.pack(fill=tk.BOTH, expand=True)
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=0)
        content_frame.rowconfigure(0, weight=1)

        columns = ("id", "status", "priority", "task", "chat", "sender", "deadline", "timestamp")
        table_card = ttk.Frame(content_frame, padding=10, style="Card.TFrame")
        table_card.grid(row=0, column=0, sticky="nsew")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", height=14)
        self._update_tree_headings()

        self.tree.column("id", width=60, stretch=False, anchor=tk.CENTER)
        self.tree.column("status", width=90, stretch=False, anchor=tk.CENTER)
        self.tree.column("priority", width=90, stretch=False, anchor=tk.CENTER)
        self.tree.column("task", width=300)
        self.tree.column("chat", width=155)
        self.tree.column("sender", width=155)
        self.tree.column("deadline", width=140, stretch=False)
        self.tree.column("timestamp", width=150, stretch=False)

        scroll_y = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.tag_configure("row_even", background="#0f172a")
        self.tree.tag_configure("row_odd", background="#111c30")
        self.tree.tag_configure("done", foreground="#64748b")

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_task_selected)
        self.tree.bind("<Double-1>", self._on_double_click)

        self.sidebar_frame = ttk.Frame(content_frame, padding=10, style="Card.TFrame", width=300)
        self.sidebar_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.sidebar_frame.grid_propagate(False)
        ttk.Label(self.sidebar_frame, text="Task Details", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        self.details = tk.Text(self.sidebar_frame, wrap=tk.WORD)
        self.details.pack(fill=tk.BOTH, expand=True)
        self.details.configure(
            bg="#0f172a",
            fg="#e2e8f0",
            relief=tk.FLAT,
            padx=10,
            pady=10,
            font=("Avenir Next", 11),
            insertbackground="#e2e8f0",
        )
        self.details.configure(state=tk.DISABLED)
        if not self.sidebar_open:
            self.sidebar_frame.grid_remove()

    def refresh_tasks(self):
        selected_before = self._get_selected_task_id()
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        include_completed = self.show_done_var.get() or self.status_filter_var.get() in ("Done", "All")
        tasks = self.manager.db.get_tasks(include_completed=include_completed)
        tasks = self._apply_filters(tasks)
        tasks = self._apply_sort(tasks)
        self.tasks_by_id = {task["id"]: task for task in tasks}

        for index, task in enumerate(tasks):
            row_tags = ["row_even" if index % 2 == 0 else "row_odd"]
            if task.get("completed"):
                row_tags.append("done")
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
                tags=tuple(row_tags),
            )

        total_count = len(tasks)
        done_count = sum(1 for task in tasks if task.get("completed"))
        pending_count = total_count - done_count
        if self.show_done_var.get() or self.status_filter_var.get() in ("Done", "All"):
            self.status_var.set(
                f"Showing {total_count} task{'s' if total_count != 1 else ''}: {pending_count} pending / {done_count} done"
            )
        else:
            self.status_var.set(f"Showing {pending_count} pending task{'s' if pending_count != 1 else ''}")

        if self.focus_task_id and self.focus_task_id in self.tasks_by_id:
            focus_id = str(self.focus_task_id)
            self.tree.selection_set(focus_id)
            self.tree.focus(focus_id)
            self.tree.see(focus_id)
            self._on_task_selected()
            self.focus_task_id = None
        elif selected_before and selected_before in self.tasks_by_id:
            selected_id = str(selected_before)
            self.tree.selection_set(selected_id)
            self.tree.focus(selected_id)
            self.tree.see(selected_id)
            self._on_task_selected()
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

    def _toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open
        if self.sidebar_open:
            self.sidebar_frame.grid()
            self.info_btn.configure(text="✕")
        else:
            self.sidebar_frame.grid_remove()
            self.info_btn.configure(text="ⓘ")

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

    def _on_filter_change(self, _event=None):
        self.refresh_tasks()

    def _clear_filters(self):
        self.search_var.set("")
        self.priority_filter_var.set("All")
        self.status_filter_var.set("Pending")
        self.refresh_tasks()

    def _on_sort_column(self, column_name: str):
        if self.sort_column == column_name:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_column = column_name
            self.sort_desc = column_name in ("id", "timestamp")
        self._update_tree_headings()
        self.refresh_tasks()

    def _update_tree_headings(self):
        labels = {
            "id": "ID",
            "status": "Status",
            "priority": "Priority",
            "task": "Task",
            "chat": "Chat",
            "sender": "Sender",
            "deadline": "Deadline",
            "timestamp": "Created",
        }
        for column_name, label in labels.items():
            direction = ""
            if self.sort_column == column_name:
                direction = " (desc)" if self.sort_desc else " (asc)"
            self.tree.heading(
                column_name,
                text=f"{label}{direction}",
                command=lambda c=column_name: self._on_sort_column(c),
            )

    def _apply_filters(self, tasks):
        query = self.search_var.get().strip().lower()
        priority_filter = self.priority_filter_var.get().strip().lower()
        status_filter = self.status_filter_var.get().strip()

        filtered_tasks = []
        for task in tasks:
            completed = bool(task.get("completed"))
            if status_filter == "Pending" and completed:
                continue
            if status_filter == "Done" and not completed:
                continue
            if priority_filter and priority_filter != "all":
                if str(task.get("priority", "")).strip().lower() != priority_filter:
                    continue
            if query:
                haystack = " ".join(
                    [
                        str(task.get("id", "")),
                        str(task.get("task_description", "")),
                        str(task.get("chat_name", "")),
                        str(task.get("sender", "")),
                        str(task.get("message_content", "")),
                        str(task.get("deadline", "")),
                    ]
                ).lower()
                if query not in haystack:
                    continue
            filtered_tasks.append(task)
        return filtered_tasks

    def _apply_sort(self, tasks):
        priority_order = {"baixa": 1, "média": 2, "media": 2, "alta": 3}
        sort_column = self.sort_column

        def to_epoch(value):
            if value is None:
                return 0
            text = str(value).strip()
            if not text:
                return 0
            if text.isdigit():
                return int(text)
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    return int(datetime.strptime(text, fmt).timestamp())
                except ValueError:
                    continue
            return 0

        def sort_key(task):
            if sort_column == "id":
                return int(task.get("id", 0))
            if sort_column == "status":
                return 1 if task.get("completed") else 0
            if sort_column == "priority":
                raw_priority = str(task.get("priority", "")).strip().lower()
                return priority_order.get(raw_priority, 0)
            if sort_column == "task":
                return str(task.get("task_description", "")).lower()
            if sort_column == "chat":
                return str(task.get("chat_name", "")).lower()
            if sort_column == "sender":
                return str(task.get("sender", "")).lower()
            if sort_column == "deadline":
                return to_epoch(task.get("deadline"))
            return to_epoch(task.get("timestamp"))

        return sorted(tasks, key=sort_key, reverse=self.sort_desc)

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
