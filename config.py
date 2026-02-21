import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent / ".env")

# WhatsApp MCP database paths
WHATSAPP_MESSAGES_DB = os.getenv("WHATSAPP_MESSAGES_DB", "")
WHATSAPP_CHATS_DB = os.getenv("WHATSAPP_CHATS_DB", "")

# Local tasks database
TASKS_DB = os.getenv("TASKS_DB", "tasks.db")

# Ollama settings
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Monitored contacts and groups (comma-separated in env)
_monitored = os.getenv("MONITORED_NUMBERS", "")

def _normalize_monitored_number(value: str) -> str:
    """Accept plain phone numbers and normalize to WhatsApp JID format."""
    raw = value.strip()
    if not raw:
        return ""
    if "@" in raw:
        return raw

    digits_only = "".join(ch for ch in raw if ch.isdigit())
    if not digits_only:
        return ""
    return f"{digits_only}@s.whatsapp.net"

MONITORED_NUMBERS = []
for _entry in _monitored.split(","):
    _normalized = _normalize_monitored_number(_entry)
    if _normalized:
        MONITORED_NUMBERS.append(_normalized)

_monitored_keywords = os.getenv("MONITORED_GROUP_KEYWORDS", "")
MONITORED_GROUP_KEYWORDS = [s.strip() for s in _monitored_keywords.split(",") if s.strip()]

# Polling interval in seconds (for daemon mode)
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))

# Log housekeeping (daemon/watch mode)
LOG_CLEANUP_DAILY = os.getenv("LOG_CLEANUP_DAILY", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
_log_files = os.getenv(
    "LOG_FILES",
    "/tmp/whatsapp-tasks.log,/tmp/whatsapp-tasks.err.log",
)
LOG_FILES = [entry.strip() for entry in _log_files.split(",") if entry.strip()]

# Email notification settings
MAIL_HOST = os.getenv("MAIL_HOST", "")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_ENCRYPTION = os.getenv("MAIL_ENCRYPTION", "starttls")  # tls, starttls, or none
MAIL_TO = os.getenv("MAIL_TO", "")
MAIL_FROM = os.getenv("MAIL_FROM", "")
# Validate required database files exist
def _validate_databases():
    """Validate that required database files exist and are accessible."""
    missing_dbs = []
    
    if not WHATSAPP_MESSAGES_DB:
        missing_dbs.append("WHATSAPP_MESSAGES_DB environment variable not set")
    elif not os.path.exists(WHATSAPP_MESSAGES_DB):
        missing_dbs.append(f"WhatsApp messages database not found: {WHATSAPP_MESSAGES_DB}")
    elif not os.access(WHATSAPP_MESSAGES_DB, os.R_OK):
        missing_dbs.append(f"WhatsApp messages database not readable: {WHATSAPP_MESSAGES_DB}")
        
    if not WHATSAPP_CHATS_DB:
        missing_dbs.append("WHATSAPP_CHATS_DB environment variable not set")
    elif not os.path.exists(WHATSAPP_CHATS_DB):
        missing_dbs.append(f"WhatsApp chats database not found: {WHATSAPP_CHATS_DB}")
    elif not os.access(WHATSAPP_CHATS_DB, os.R_OK):
        missing_dbs.append(f"WhatsApp chats database not readable: {WHATSAPP_CHATS_DB}")
    
    return missing_dbs

# Validate databases when module is imported (unless running tests)
_db_validation_errors = []
if not os.getenv("SKIP_DB_VALIDATION"):  # Allow tests to skip validation
    _db_validation_errors = _validate_databases()

def get_database_validation_errors():
    """Get any database validation errors found during import."""
    return _db_validation_errors.copy()

# Portuguese task detection prompt
TASK_PROMPT = os.getenv(
    "TASK_PROMPT",
    """Analise esta mensagem do WhatsApp em português brasileiro:

Mensagem: "{message}"
Remetente: {sender}
Data: {timestamp}

Existe uma tarefa, pedido, ou algo que precisa ser feito nesta mensagem?

Responda APENAS em formato JSON:
{{
    "has_task": true/false,
    "task_description": "descrição da tarefa em português",
    "priority": "baixa/média/alta",
    "deadline": "se houver prazo mencionado ou null"
}}

Se não há tarefa, retorne {{"has_task": false}}""",
).replace("\\n", "\n")
