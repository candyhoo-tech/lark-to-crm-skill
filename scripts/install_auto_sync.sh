#!/bin/bash
# Install auto-sync as a launchd agent on macOS.
# Runs every 10 minutes in the background, even when Claude Code is closed.
#
# Usage:  bash scripts/install_auto_sync.sh
# Uninstall: bash scripts/install_auto_sync.sh uninstall

set -e
LABEL="com.chatdaddy.lark-to-crm"
SKILL_DIR="$HOME/.claude/skills/lark-to-crm"
PLIST_SRC="$SKILL_DIR/launchd/$LABEL.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" == "uninstall" ]; then
    echo "Unloading launchd agent..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    rm -f "$PLIST_DST"
    echo "✅ Uninstalled. Background sync stopped."
    exit 0
fi

if [ ! -f "$SKILL_DIR/config/user.json" ]; then
    echo "❌ Missing $SKILL_DIR/config/user.json — do setup first (TEAMMATE-SETUP.md)"
    exit 1
fi

if [ ! -f "$SKILL_DIR/.state/lark_token.json" ]; then
    echo "❌ Missing Lark OAuth token — run: python3 scripts/oauth_helper.py '<callback_url>'"
    exit 1
fi

echo "Installing launchd agent to $PLIST_DST ..."
mkdir -p "$HOME/Library/LaunchAgents"

# Substitute YOUR_HOME with the real $HOME
sed "s|YOUR_HOME|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"

# Unload if already loaded (for re-install)
launchctl unload "$PLIST_DST" 2>/dev/null || true

launchctl load "$PLIST_DST"
echo "✅ Loaded. First sync will run in <10 seconds."
echo ""
echo "Check status:     launchctl list | grep $LABEL"
echo "View live log:    tail -f $SKILL_DIR/.state/auto-sync.log"
echo "Pending review:   cat $SKILL_DIR/.state/pending-review.json"
echo "Stop + remove:    bash scripts/install_auto_sync.sh uninstall"
