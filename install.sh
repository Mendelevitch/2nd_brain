#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BRAIN_DIR="$HOME/brain"

echo "================================"
echo "  2ND Brain — installer"
echo "================================"
echo ""

# ── 1. Create brain directory structure ──────────────────────
echo "→ Creating brain directory at $BRAIN_DIR..."
mkdir -p "$BRAIN_DIR"/{raw,wiki,archive,insights,user,guest_chats,chats,prompts,skills,_Claude}

# ── 2. Copy bot files ─────────────────────────────────────────
echo "→ Copying bot files..."
cp "$REPO_DIR/save_bot.py" "$BRAIN_DIR/_Claude/"
cp "$REPO_DIR/chat_bot.py" "$BRAIN_DIR/_Claude/"
cp -r "$REPO_DIR/prompts/"* "$BRAIN_DIR/prompts/"
cp "$REPO_DIR/AGENTS.md" "$BRAIN_DIR/_Claude/"
cp "$REPO_DIR/templates/user-model.md" "$BRAIN_DIR/user/user-model.md"
cp "$REPO_DIR/templates/guests.example.json" "$BRAIN_DIR/guests.json"

# ── 3. Install dependencies ───────────────────────────────────
echo "→ Installing Python dependencies..."
pip3 install -q python-telegram-bot[job-queue] openai anthropic \
             newspaper3k lxml_html_clean yt-dlp \
             "markitdown[all]" --break-system-packages

# ── 4. Collect config values ──────────────────────────────────
echo ""
echo "Now I need a few values. Get them from:"
echo "  Telegram tokens → @BotFather (create 2 bots)"
echo "  Your Telegram ID → @userinfobot"
echo "  Anthropic key   → console.anthropic.com/settings/keys"
echo "  OpenAI key      → platform.openai.com/api-keys (optional, for voice)"
echo ""

read -p "SaveBot token (capture bot):  " BRAIN_BOT_TOKEN
read -p "ChatBot token (chat bot):     " MIND_BOT_TOKEN
read -p "Your Telegram user ID:        " OWNER_ID
read -p "Anthropic API key:            " ANTHROPIC_API_KEY
read -p "OpenAI API key (leave empty to skip voice): " OPENAI_API_KEY

# ── 5. Write config.py ────────────────────────────────────────
echo "→ Writing config.py..."
cat > "$BRAIN_DIR/_Claude/config.py" << EOF
BRAIN_BOT_TOKEN   = "$BRAIN_BOT_TOKEN"
MIND_BOT_TOKEN    = "$MIND_BOT_TOKEN"
ANTHROPIC_API_KEY = "$ANTHROPIC_API_KEY"
OPENAI_API_KEY    = "$OPENAI_API_KEY"
OWNER_ID          = $OWNER_ID
BRAIN_DIR         = "$BRAIN_DIR"
NOTION_TOKEN      = ""
NOTION_DB         = ""
EOF

# ── 6. Install systemd services ───────────────────────────────
echo "→ Installing systemd services..."

SERVICE_DIR="/etc/systemd/system"
PYTHON=$(which python3)

cat > /tmp/save-bot.service << EOF
[Unit]
Description=Brain Save Bot
After=network.target

[Service]
ExecStart=$PYTHON $BRAIN_DIR/_Claude/save_bot.py
WorkingDirectory=$BRAIN_DIR/_Claude
Restart=always
RestartSec=5
Environment=PATH=/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin

[Install]
WantedBy=multi-user.target
EOF

cat > /tmp/chat-bot.service << EOF
[Unit]
Description=Brain Chat Bot
After=network.target

[Service]
ExecStart=$PYTHON $BRAIN_DIR/_Claude/chat_bot.py
WorkingDirectory=$BRAIN_DIR/_Claude
Restart=always
RestartSec=5
Environment=PATH=/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/save-bot.service /tmp/chat-bot.service "$SERVICE_DIR/"
sudo systemctl daemon-reload
sudo systemctl enable save-bot chat-bot
sudo systemctl start save-bot chat-bot

# ── 7. Done ───────────────────────────────────────────────────
echo ""
echo "================================"
echo "  Done!"
echo "================================"
echo ""
echo "Both bots are running. Check status:"
echo "  sudo systemctl status save-bot"
echo "  sudo systemctl status chat-bot"
echo ""
echo "Logs:"
echo "  sudo journalctl -u save-bot -f"
echo "  sudo journalctl -u chat-bot -f"
echo ""
echo "Next steps:"
echo "  1. Edit $BRAIN_DIR/user/user-model.md — describe yourself"
echo "  2. Add guests to $BRAIN_DIR/guests.json"
echo "  3. Send a voice message or link to your SaveBot to test"
echo ""
