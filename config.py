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
MONITORED_NUMBERS = [s.strip() for s in _monitored.split(",") if s.strip()]

_monitored_keywords = os.getenv("MONITORED_GROUP_KEYWORDS", "")
MONITORED_GROUP_KEYWORDS = [s.strip() for s in _monitored_keywords.split(",") if s.strip()]

# Polling interval in seconds (for daemon mode)
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))

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
