#!/usr/bin/env bash
# GitMind Setup — run once: bash setup.sh
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"

echo ""
echo "╔═══════════════════════════════════════╗"
echo "║   ⚡ GitMind Setup                    ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# Python check
if ! command -v python3 &>/dev/null; then
    echo "❌  Python 3 not found."
    echo "    macOS:  brew install python3"
    echo "    Ubuntu: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi
echo "✅  Python $(python3 --version | cut -d' ' -f2) found"

# Virtualenv
echo "📦  Creating virtual environment..."
python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install -q --upgrade pip
echo "📦  Installing packages (this takes ~1 min)..."
pip install -q -r "$DIR/requirements.txt"
echo "✅  Packages installed"

# Dirs
mkdir -p "$DIR/data" "$DIR/logs"

# Launcher
LAUNCHER="$DIR/gitmind.sh"
cat > "$LAUNCHER" << LAUNCHER_EOF
#!/usr/bin/env bash
source "$VENV/bin/activate"
cd "$DIR"
python3 main.py "\$@"
LAUNCHER_EOF
chmod +x "$LAUNCHER"

# Global command (optional)
GLOBAL_BIN="/usr/local/bin/gitmind"
if [ -w "/usr/local/bin" ]; then
    ln -sf "$LAUNCHER" "$GLOBAL_BIN" 2>/dev/null && echo "✅  'gitmind' command installed globally"
else
    echo "ℹ️   Run with: ./gitmind.sh  (or add to PATH manually)"
fi

# ── STARTUP ─────────────────────────────────────────────────
echo ""
echo "⚙️   Set up auto-start?"
echo "    [1] Add to ~/.zshrc  (runs when terminal opens)"
echo "    [2] Add to ~/.bashrc (runs when terminal opens)"
echo "    [3] macOS Login Item (runs silently on boot, shows notification)"
echo "    [4] Skip"
echo ""
read -p "    Choice [1-4]: " SC

case $SC in
  1)
    RCFILE="$HOME/.zshrc"
    if ! grep -q "gitmind" "$RCFILE" 2>/dev/null; then
        printf '\n# GitMind — auto-start\nalias gitmind="%s"\n%s\n' "$LAUNCHER" "$LAUNCHER" >> "$RCFILE"
        echo "✅  Added to ~/.zshrc"
    else echo "ℹ️   Already in ~/.zshrc"; fi ;;
  2)
    RCFILE="$HOME/.bashrc"
    if ! grep -q "gitmind" "$RCFILE" 2>/dev/null; then
        printf '\n# GitMind — auto-start\nalias gitmind="%s"\n%s\n' "$LAUNCHER" "$LAUNCHER" >> "$RCFILE"
        echo "✅  Added to ~/.bashrc"
    else echo "ℹ️   Already in ~/.bashrc"; fi ;;
  3)
    # macOS: notification only on boot, full UI when terminal opens
    PLIST="$HOME/Library/LaunchAgents/com.gitmind.plist"
    cat > "$PLIST" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.gitmind</string>
  <key>ProgramArguments</key><array>
    <string>$LAUNCHER</string><string>--notify</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DIR/logs/boot.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/boot_err.log</string>
</dict></plist>
PLIST_EOF
    launchctl load "$PLIST" 2>/dev/null && echo "✅  macOS Login Item created" || echo "ℹ️   Run: launchctl load $PLIST"
    # Also add to .zshrc for full UI on terminal open
    RCFILE="$HOME/.zshrc"
    [ ! -f "$RCFILE" ] && touch "$RCFILE"
    if ! grep -q "gitmind" "$RCFILE"; then
        printf '\n# GitMind\nalias gitmind="%s"\n%s\n' "$LAUNCHER" "$LAUNCHER" >> "$RCFILE"
        echo "✅  Also added to ~/.zshrc for terminal UI"
    fi ;;
  *) echo "⏭️   Skipped — run manually: ./gitmind.sh" ;;
esac

echo ""
echo "╔═══════════════════════════════════════╗"
echo "║   ✅ Done! Run: ./gitmind.sh          ║"
echo "╚═══════════════════════════════════════╝"
echo ""
echo "  GitMind will guide you through setup on first run."
echo "  You just need a free Groq API key:"
echo "  → https://console.groq.com"
echo ""
