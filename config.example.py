# 2ND Brain — Configuration
# Copy this file to config.py and fill in your values.
# config.py is gitignored and never committed.

# ── Telegram bot tokens ──────────────────────────────────
# Create two bots via @BotFather. Send /newbot, follow prompts.
BRAIN_BOT_TOKEN = ""   # capture bot  (receives voice, photos, links, text)
MIND_BOT_TOKEN  = ""   # chat bot     (conversational interface to your wiki)

# ── API keys ─────────────────────────────────────────────
# Anthropic — https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY = ""

# OpenAI — https://platform.openai.com/api-keys
# Used only for Whisper voice transcription.
# If you don't want voice transcription, leave empty.
OPENAI_API_KEY = ""

# ── Your identity ─────────────────────────────────────────
# Your Telegram user ID — get it from @userinfobot
OWNER_ID = 0

# ── Paths ─────────────────────────────────────────────────
# If running with Docker (docker-compose up), use:
BRAIN_DIR = "/brain"
# If running directly on a Pi or Mac, use the actual path:
# BRAIN_DIR = "/path/to/your/brain"

# ── Ollama / local GPU (optional) ─────────────────────────
# Set these to enable /local mode in the chat bot —
# routes responses to a local Ollama instance instead of Claude.
# Leave unset (or delete these lines) if you don't have a local GPU.
# OLLAMA_HOST  = "192.168.1.100"   # IP of the machine running Ollama
# OLLAMA_PORT  = 11434
# OLLAMA_MODEL = "gemma4:12b"
# WINDOWS_MAC  = ""                 # MAC address for Wake-on-LAN (optional)

