#!/bin/bash
# Run once before docker-compose up to initialise the brain directory.
set -e

echo "Setting up 2ND Brain..."

# Config
if [ ! -f config.py ]; then
  cp config.example.py config.py
  echo ""
  echo "✓ config.py created — open it and fill in your tokens and API keys, then run this script again."
  exit 0
fi

# Create brain folders inside the Docker volume
docker run --rm -v 2nd-brain_brain-data:/brain alpine \
  mkdir -p /brain/raw /brain/wiki /brain/archive /brain/insights /brain/user /brain/guest_chats

echo "✓ Brain directory structure created"
echo ""
echo "Next steps:"
echo "  1. docker-compose up -d          # start the bots"
echo "  2. docker-compose logs -f        # watch the logs"
echo "  3. Open Cowork, run onboarding"
