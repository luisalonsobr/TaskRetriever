# WhatsApp Task Manager

Personal note: 
Make no mistake, this is AI SLOP. I leave real coding for paying bills. However it does what I need, I hope it can be useful for those reading this. 

An intelligent task extraction system that monitors your WhatsApp messages and automatically detects tasks, reminders, and action items using local AI processing.

## 🎯 Project Intent

This tool solves the common problem of tasks and reminders getting lost in WhatsApp conversations. Instead of manually tracking what needs to be done across multiple chats, the system:

- **Monitors specific contacts and groups** for new messages
- **Uses local AI** (Ollama + Qwen3 4B) to detect tasks in Portuguese 
- **Sends macOS notifications** when tasks are found
- **Provides a simple CLI** to manage and complete tasks
- **Provides a desktop GUI** to view and click tasks
- **Runs as a background daemon** for continuous monitoring

Perfect for busy professionals who receive work requests, family coordination, or project tasks through WhatsApp.

## 🏗️ Architecture

```
WhatsApp MCP Database → Filter → Local AI → Task Storage → macOS Notifications
                        ↓           ↓            ↓
                   [Contacts]   [Qwen3 4B]   [SQLite]
                   [Groups]     [Portuguese]  [CLI]
```

## 📦 Components

### Core Files
- **`main.py`** - CLI interface and orchestration
- **`db_manager.py`** - Database operations (WhatsApp + task storage)
- **`task_detector.py`** - Ollama AI integration for task detection
- **`notifier.py`** - macOS notification system
- **`config.py`** - Configuration (contacts, groups, prompts)

### Databases
- **WhatsApp MCP DBs** - Source message data (`messages.db`, `whatsapp.db`)
- **Local Tasks DB** - Extracted tasks and processing history (`tasks.db`)

## 🧠 How It Works

### 1. Message Filtering
The system monitors only specified contacts and groups:
- **Direct contacts**: Specific phone numbers 
- **Groups**: Names containing keywords like "XXXX", "ZZZZ"

### 2. AI Task Detection
Messages are analyzed using a local Ollama model (Qwen3 4B) with Portuguese prompts:
```json
{
    "has_task": true,
    "task_description": "Comprar leite hoje",
    "priority": "média", 
    "deadline": "hoje"
}
```

### 3. Task Management
Detected tasks are stored with metadata:
- Original message content and sender
- Chat name and timestamp
- AI-extracted task description
- Priority level and deadlines
- Completion status

### 4. Notifications
macOS notifications display:
- Task description with priority emoji (🔴🟡🟢)
- Sender and chat context
- Deadline information if present
- Clickable for easy task management

## 🚀 Setup & Usage

### Prerequisites
- **Ollama** running with `qwen3:4b` model
- **WhatsApp MCP** bridge running and populating databases
- **Python 3.7+** with `requests` library

### Installation
```bash
git clone <this-repo>
cd task-manager
pip install -r requirements.txt
```

### macOS Auto-Start + GUI Icon
```bash
# Installs login auto-start (background watch) + app icon in ~/Applications
./install_macos_integration.sh

# Remove integration later
./uninstall_macos_integration.sh
```

### Configuration
Edit `config.py` to set:
- Your monitored phone numbers
- Group keywords to watch
- Database paths
- Polling intervals

### Commands
```bash
# Test system components
python main.py test

# Manual task scanning  
python main.py scan

# List pending tasks
python main.py list

# Open desktop GUI task list
python main.py gui

# Mark task as completed
python main.py done <task_id>

# Background daemon mode
python main.py watch

# Or use daemon scripts
./start_daemon.sh    # Start background
./stop_daemon.sh     # Stop background
```

With macOS integration enabled:
- scanning/notifications run automatically on login (LaunchAgent)
- clicking a task notification opens the GUI (focuses that task when available)
- you can open the GUI anytime via `WhatsApp Task Manager.app` (Finder/Spotlight)
- in the GUI, enable `Show done tasks` to review completed items and use `Mark Not Done` to reopen them

## 🔧 Technical Details

### Database Schema

**Tasks Table:**
```sql
- id: Unique task identifier
- message_id: Original WhatsApp message ID  
- chat_jid: WhatsApp chat identifier
- sender: Message sender name
- task_description: AI-extracted task
- priority: baixa/média/alta
- deadline: Extracted deadline or null
- completed: Boolean completion status
```

**Processing Table:**
```sql
- message_id: Processed message tracker
- processed_at: Processing timestamp
```

### AI Integration
- **Model**: Qwen3 4B (lightweight, multilingual)
- **Processing**: Local Ollama API calls
- **Language**: Optimized for Portuguese Brazilian
- **Output**: Structured JSON responses
- **Fallback**: Graceful handling of parsing failures

### Notification System
- **Platform**: macOS native notifications
- **Method**: `terminal-notifier` primary, AppleScript fallback
- **Features**: Priority indicators, sender/chat context, click-to-open GUI
- **Persistence**: Click task notifications to open/focus the desktop task manager

## 🎛️ Configuration Options

### Monitored Contacts
```python
MONITORED_NUMBERS = [
    "YYZZZXXXXXXXXXX",
    "YYZZZXXXXXXXXXX@s.whatsapp.net",
    # Add your contacts here country/area/number   only numbers, no +
    # plain number or full JID are both accepted
]
```

### Group Keywords
```python
MONITORED_GROUP_KEYWORDS = ["XXXX", "ZZZZ"]
# Groups containing these words will be monitored
```

### AI Prompt Customization
The Portuguese task detection prompt can be modified in `config.py` to adjust:
- Task detection sensitivity
- Priority classification criteria
- Deadline extraction patterns
- Response format requirements

## 📊 Workflow Example

1. **Message arrives**: "Oi, lembra de enviar o relatório até sexta-feira"
2. **System filters**: Checks if sender/group is monitored
3. **AI processes**: Extracts task "enviar o relatório" with deadline "sexta-feira"  
4. **Notification sent**: macOS notification with task details
5. **User manages**: Views with `python main.py list`, completes with `python main.py done 1`

## 🔒 Privacy & Security

- **Local processing**: All AI inference runs on your machine
- **No cloud calls**: Messages never leave your system
- **Selective monitoring**: Only specified contacts/groups processed
- **Data retention**: Task history stored locally in SQLite

## 🛠️ Troubleshooting

**Common Issues:**
- **"No such table" errors**: Run `python main.py test` to initialize databases
- **Ollama connection failed**: Ensure Ollama is running with `ollama serve`
- **No notifications**: Check macOS notification permissions
- **No monitored chats**: Verify phone numbers and group names in config

**Logs:**
```bash
tail -f /tmp/whatsapp-tasks.log  # Daemon mode logs
```

## 🔄 Future Enhancements

- Web dashboard for task management
- Integration with task management tools (Todoist, Notion)
- Support for other messaging platforms
- Advanced AI models for better task detection
- Team collaboration features
- Mobile companion app

## 📄 License

This project is for personal/educational use. Ensure compliance with WhatsApp's terms of service when accessing message data.
