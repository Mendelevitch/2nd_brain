#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BRAIN_DIR="$HOME/Brain"

echo "================================"
echo "  2ND Brain — Mac setup"
echo "================================"
echo ""
echo "This creates your local Brain folder and copies prompts."
echo "Brain directory: $BRAIN_DIR"
echo ""
read -p "Continue? [y/N]: " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

# ── 1. Create folder structure ────────────────────────────
echo ""
echo "→ Creating Brain folder structure..."
mkdir -p "$BRAIN_DIR"/{raw,wiki,archive,insights,user,guest_chats,chats,prompts,skills,_Claude}
echo "  Done: $BRAIN_DIR"

# ── 2. Copy prompts ───────────────────────────────────────
echo "→ Copying Cowork prompts..."
cp -r "$REPO_DIR/prompts/"* "$BRAIN_DIR/prompts/"
echo "  Done: $(ls "$BRAIN_DIR/prompts/" | wc -l | tr -d ' ') prompts copied"

# ── 3. Copy templates ─────────────────────────────────────
echo "→ Copying templates..."
cp "$REPO_DIR/templates/user-model.md" "$BRAIN_DIR/user/user-model.md"
cp "$REPO_DIR/templates/build-user-model.md" "$BRAIN_DIR/_Claude/build-user-model.md"
cp "$REPO_DIR/templates/onboarding-cowork.md" "$BRAIN_DIR/_Claude/onboarding-cowork.md"
echo "  Done"

# ── 4. Copy AGENTS.md for Cowork ─────────────────────────
echo "→ Copying AGENTS.md..."
cp "$REPO_DIR/AGENTS.md" "$BRAIN_DIR/_Claude/AGENTS.md"
echo "  Done"

# ── 5. Done ───────────────────────────────────────────────
echo ""
echo "================================"
echo "  Done!"
echo "================================"
echo ""
echo "Your Brain folder is ready at: $BRAIN_DIR"
echo ""
echo "Next steps:"
echo ""
echo "  1. Set up Syncthing to sync with your Pi:"
echo "     See docs/setup-syncthing.md"
echo "     Folders to sync:"
echo "       raw/         ← Pi → Mac  (captures from SaveBot)"
echo "       wiki/        ← Mac → Pi  (your knowledge base)"
echo "       insights/    ← Mac → Pi  (Cowork digests)"
echo "       user/        ← Mac → Pi  (your user model)"
echo "       guest_chats/ ← Pi → Mac  (guest conversations)"
echo ""
echo "  2. Open Cowork and point it at $BRAIN_DIR"
echo ""
echo "  3. Run the onboarding prompt to set up wiki structure:"
echo "     Open $BRAIN_DIR/_Claude/onboarding-cowork.md in Cowork"
echo ""
echo "  4. Build your user model:"
echo "     Open $BRAIN_DIR/_Claude/build-user-model.md in Cowork"
echo ""
