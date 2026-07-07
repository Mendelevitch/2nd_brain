#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BRAIN_DIR="$HOME/brain"
CLAUDE_DIR="$BRAIN_DIR/_Claude"

echo "================================"
echo "  2ND Brain — update"
echo "================================"
echo ""

# ── 1. Pull latest code ───────────────────────────────────────
echo "→ Pulling latest code from GitHub..."
git -C "$REPO_DIR" pull --ff-only
echo ""

# ── 2. Install any new dependencies ──────────────────────────
echo "→ Checking dependencies..."
pip3 install -q python-telegram-bot[job-queue] openai anthropic numpy \
             newspaper3k lxml_html_clean yt-dlp \
             "markitdown[all]" --break-system-packages
echo "   ✓ dependencies up to date"
echo ""

# ── 3. Copy updated bot files and prompts ────────────────────
echo "→ Updating bot files..."
cp "$REPO_DIR/chat_bot.py" "$CLAUDE_DIR/chat_bot.py"
cp "$REPO_DIR/save_bot.py" "$CLAUDE_DIR/save_bot.py"
echo "   ✓ bot files updated"

echo "→ Updating prompts..."
mkdir -p "$BRAIN_DIR/prompts"
for f in "$REPO_DIR/prompts/"*.md; do
    fname="$(basename "$f")"
    cp "$f" "$BRAIN_DIR/prompts/$fname"
    echo "   ✓ prompts/$fname"
done
echo ""

# ── 4. Restart services ───────────────────────────────────────
echo "→ Restarting bots..."
sudo systemctl restart brain-bot
sudo systemctl restart mind-bot
sleep 2

BRAIN_STATUS=$(systemctl is-active brain-bot)
MIND_STATUS=$(systemctl is-active mind-bot)

if [ "$BRAIN_STATUS" = "active" ] && [ "$MIND_STATUS" = "active" ]; then
    echo "   ✓ both bots running"
else
    echo "   ⚠ brain-bot: $BRAIN_STATUS"
    echo "   ⚠ mind-bot:  $MIND_STATUS"
    echo ""
    echo "Check logs with:"
    echo "  sudo journalctl -u brain-bot -n 30"
    echo "  sudo journalctl -u mind-bot -n 30"
    exit 1
fi

echo ""
echo "================================"
echo "  ✓ Update complete"
echo "================================"
echo ""
echo "What's new in this update — check:"
echo "  https://github.com/Mendelevitch/2nd_brain/commits/master"
echo ""
