#!/bin/bash
# Watches _Claude/ for file changes and restarts bots automatically
# Run as: sudo systemctl enable --now watch-bots

WATCH_DIR="$(dirname "$(readlink -f "$0")")"

echo "Watching $WATCH_DIR for changes..."

inotifywait -m -e close_write -e moved_to --include '.*\.py$' "$WATCH_DIR" | while read dir events file; do
    echo "[$(date)] Changed: $file — restarting services..."
    if [[ "$file" == "save_bot.py" ]]; then
        systemctl restart save-bot
        echo "save-bot restarted"
    elif [[ "$file" == "chat_bot.py" ]]; then
        systemctl restart chat-bot
        echo "chat-bot restarted"
    fi
done
