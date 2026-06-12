#!/bin/bash
# Watches brain/_Claude/ for file changes and restarts bots automatically
# Run as: sudo systemctl enable --now watch-bots

WATCH_DIR="/mnt/hdd/Misha_pi/brain/_Claude"

echo "Watching $WATCH_DIR for changes..."

inotifywait -m -e close_write -e moved_to --include '.*\.py$' "$WATCH_DIR" | while read dir events file; do
    echo "[$(date)] Changed: $file — restarting services..."
    if [[ "$file" == "brain_bot.py" ]]; then
        systemctl restart brain-bot
        echo "brain-bot restarted"
    elif [[ "$file" == "mind_bot.py" ]]; then
        systemctl restart mind-bot
        echo "mind-bot restarted"
    fi
done
