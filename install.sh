#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BRAIN_DIR="$HOME/brain"

echo "================================"
echo "  2ND Brain — installer"
echo "================================"
echo ""
echo "Do you have a Raspberry Pi or a Linux server already?"
echo "  1) Yes — Raspberry Pi or VPS (continue install)"
echo "  2) No  — I need a server first"
echo ""
read -p "Choice [1/2]: " SERVER_CHOICE

if [ "$SERVER_CHOICE" = "2" ]; then
    echo ""
    echo "Get a server in ~2 minutes:"
    echo ""
    echo "  DigitalOcean: https://digitalocean.com"
    echo "    → Create Droplet → Ubuntu 24.04 → Basic → \$6/mo (1GB) or \$12/mo (2GB)"
    echo ""
    echo "  Hetzner (cheaper): https://hetzner.com/cloud"
    echo "    → New Project → Add Server → Ubuntu 24.04 → CX22 (€4/mo)"
    echo ""
    echo "Once your server is running:"
    echo "  ssh root@<your-server-ip>"
    echo "  git clone https://github.com/Mendelevitch/2nd_brain.git"
    echo "  cd 2nd_brain && ./install.sh"
    echo ""
    exit 0
fi

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

# ── 7. Claude Code permissions ───────────────────────────────
echo "→ Configuring Claude Code permissions for brain directory..."
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"

python3 - <<PYEOF
import json, os

path = os.path.expanduser("$CLAUDE_SETTINGS")
brain = "$BRAIN_DIR"

new_rules = [
    f"Read({brain}/**)",
    f"Write({brain}/**)",
    f"Edit({brain}/**)",
    f"Bash(ls {brain}/**)",
    f"Bash(ls -la {brain}/**)",
    f"Bash(find {brain}/**)",
    f"Bash(mv {brain}/**)",
    f"Bash(cp {brain}/**)",
    f"Bash(mkdir -p {brain}/**)",
    f"Bash(cat {brain}/**)",
    f"Bash(grep * {brain}/**)",
]

try:
    with open(path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

settings.setdefault("permissions", {}).setdefault("allow", [])
existing = set(settings["permissions"]["allow"])
for rule in new_rules:
    if rule not in existing:
        settings["permissions"]["allow"].append(rule)

with open(path, "w") as f:
    json.dump(settings, f, indent=2)
print(f"  Permissions written to {path}")
PYEOF

# ── 8. Syncthing (optional) ───────────────────────────────────
echo ""
echo "Syncthing keeps your wiki and raw files in sync with your Mac."
read -p "Set up Syncthing now? [y/N]: " SYNC_CHOICE

if [ "$SYNC_CHOICE" = "y" ] || [ "$SYNC_CHOICE" = "Y" ]; then
    echo "→ Installing Syncthing..."
    sudo apt-get install -y syncthing 2>/dev/null || \
        (curl -s https://syncthing.net/release-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/syncthing-archive-keyring.gpg && \
         echo "deb [signed-by=/usr/share/keyrings/syncthing-archive-keyring.gpg] https://apt.syncthing.net/ syncthing stable" | sudo tee /etc/apt/sources.list.d/syncthing.list && \
         sudo apt-get update -q && sudo apt-get install -y syncthing)

    CURRENT_USER=$(whoami)
    sudo systemctl enable "syncthing@$CURRENT_USER"
    sudo systemctl start "syncthing@$CURRENT_USER"

    sleep 2
    DEVICE_ID=$(syncthing --device-id 2>/dev/null || cat "$HOME/.local/state/syncthing/config.xml" 2>/dev/null | grep -o 'id="[^"]*"' | head -1 | cut -d'"' -f2 || echo "(run: syncthing --device-id)")

    echo ""
    echo "→ Syncthing is running."
    echo ""
    echo "  Your server Device ID:"
    echo "  $DEVICE_ID"
    echo ""
    echo "  Next steps on your Mac:"
    echo "  1. Install Syncthing: brew install syncthing && brew services start syncthing"
    echo "  2. Open http://localhost:8384 — add this server as a remote device"
    echo "  3. Add shared folders — see docs/setup-syncthing.md for the full list"
    echo ""
fi

# ── 9. Done ───────────────────────────────────────────────────
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
if [ "$SYNC_CHOICE" != "y" ] && [ "$SYNC_CHOICE" != "Y" ]; then
    echo "  4. Set up Syncthing later: see docs/setup-syncthing.md"
fi
echo ""
