import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from config import WHATSAPP_MESSAGES_DB, WHATSAPP_CHATS_DB, TASKS_DB, MONITORED_NUMBERS, MONITORED_GROUP_KEYWORDS

class DatabaseManager:
    def __init__(self):
        self.init_tasks_db()
        
    def init_tasks_db(self):
        """Initialize the tasks database"""
        conn = sqlite3.connect(TASKS_DB)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                chat_jid TEXT,
                chat_name TEXT,
                sender TEXT,
                message_content TEXT,
                task_description TEXT,
                priority TEXT,
                deadline TEXT,
                timestamp TEXT,
                completed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_processed_messages_processed_at
            ON processed_messages(processed_at)
        ''')
        conn.commit()
        conn.close()
        
    def get_monitored_chat_jids(self) -> List[str]:
        """Get JIDs of chats we should monitor"""
        conn = sqlite3.connect(WHATSAPP_MESSAGES_DB)  # chats table is in messages.db
        
        # Get direct message JIDs
        direct_jids = []
        for number in MONITORED_NUMBERS:
            cursor = conn.execute("SELECT jid FROM chats WHERE jid = ?", (number,))
            result = cursor.fetchone()
            if result:
                direct_jids.append(result[0])
        
        # Get group JIDs containing keywords
        group_jids = []
        for keyword in MONITORED_GROUP_KEYWORDS:
            cursor = conn.execute("SELECT jid FROM chats WHERE name LIKE ? AND jid LIKE '%@g.us'", (f"%{keyword}%",))
            results = cursor.fetchall()
            group_jids.extend([row[0] for row in results])
        
        conn.close()
        return direct_jids + group_jids
    
    def get_new_messages(self, last_check_timestamp: Optional[str] = None) -> List[Dict]:
        """Get new unprocessed messages from monitored chats."""
        monitored_jids = self.get_monitored_chat_jids()
        if not monitored_jids:
            return []
            
        conn = sqlite3.connect(WHATSAPP_MESSAGES_DB)
        conn.execute("ATTACH DATABASE ? AS taskdb", (TASKS_DB,))
        
        # Build query for monitored JIDs
        jid_placeholders = ','.join(['?' for _ in monitored_jids])
        # NOTE: We intentionally avoid using processed_at as a scan watermark.
        # It is local wall-clock time and not comparable to message timestamps.
        # Instead, query only unprocessed messages via SQL and process oldest first.
        query = f'''
            SELECT m.id, m.timestamp, m.sender, m.content, m.chat_jid,
                   c.name as chat_name, m.is_from_me
            FROM messages m
            JOIN chats c ON m.chat_jid = c.jid
            LEFT JOIN taskdb.processed_messages p ON p.message_id = m.id
            WHERE m.chat_jid IN ({jid_placeholders})
            AND m.content IS NOT NULL
            AND m.content != ''
            AND p.message_id IS NULL
            ORDER BY m.timestamp ASC
            LIMIT 50
        '''

        params = monitored_jids
        
        cursor = conn.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        messages = []
        for row in results:
            messages.append({
                'id': row[0],
                'timestamp': row[1],
                'sender': row[2],
                'content': row[3],
                'chat_jid': row[4],
                'chat_name': row[5],
                'is_from_me': row[6]
            })

        return messages
    
    def mark_message_processed(self, message_id: str):
        """Mark a message as processed"""
        conn = sqlite3.connect(TASKS_DB)
        conn.execute("INSERT OR IGNORE INTO processed_messages (message_id) VALUES (?)", (message_id,))
        conn.commit()
        conn.close()
    
    def save_task(self, message: Dict, task_data: Dict) -> int:
        """Save a detected task to the database"""
        conn = sqlite3.connect(TASKS_DB)
        cursor = conn.execute('''
            INSERT INTO tasks (
                message_id, chat_jid, chat_name, sender, message_content,
                task_description, priority, deadline, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            message['id'],
            message['chat_jid'],
            message['chat_name'],
            message['sender'],
            message['content'],
            task_data['task_description'],
            task_data.get('priority', 'média'),
            task_data.get('deadline'),
            message['timestamp']
        ))
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id
    
    def get_tasks(self, include_completed: bool = False) -> List[Dict]:
        """Get tasks, optionally including completed ones."""
        conn = sqlite3.connect(TASKS_DB)
        if include_completed:
            cursor = conn.execute('''
            SELECT id, chat_name, sender, task_description, priority, 
                   deadline, timestamp, message_content, completed
            FROM tasks
            ORDER BY created_at DESC
        ''')
        else:
            cursor = conn.execute('''
            SELECT id, chat_name, sender, task_description, priority, 
                   deadline, timestamp, message_content, completed
            FROM tasks 
            WHERE completed = FALSE 
            ORDER BY created_at DESC
        ''')
        results = cursor.fetchall()
        conn.close()
        
        tasks = []
        for row in results:
            tasks.append({
                'id': row[0],
                'chat_name': row[1],
                'sender': row[2],
                'task_description': row[3],
                'priority': row[4],
                'deadline': row[5],
                'timestamp': row[6],
                'message_content': row[7],
                'completed': bool(row[8]),
            })
        return tasks

    def get_pending_tasks(self) -> List[Dict]:
        """Get all pending tasks."""
        return self.get_tasks(include_completed=False)
    
    def mark_task_completed(self, task_id: int) -> bool:
        """Mark a task as completed"""
        conn = sqlite3.connect(TASKS_DB)
        cursor = conn.execute("UPDATE tasks SET completed = TRUE WHERE id = ?", (task_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def mark_task_not_completed(self, task_id: int) -> bool:
        """Mark a task as not completed."""
        conn = sqlite3.connect(TASKS_DB)
        cursor = conn.execute("UPDATE tasks SET completed = FALSE WHERE id = ?", (task_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def get_last_check_timestamp(self) -> Optional[str]:
        """Legacy compatibility: watermark-based scans are no longer used."""
        return None
