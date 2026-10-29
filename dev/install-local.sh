#!/bin/bash
# Dev install: build Swift CLIs, symlink /usr/local/opt/meet-transcriber → repo,
# write bin wrapper, install LaunchAgent plist. No .pkg build loop needed.
#
# Prereqs: uv installed, Xcode CLI tools, macOS 15+.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG_ROOT="/usr/local/opt/meet-transcriber"
BIN="/usr/local/bin/meet-transcriber"
PLIST_SRC="$REPO_ROOT/launchd/sk.lbstudio.meet-transcriber.plist"
PLIST_DST="$HOME/Library/LaunchAgents/sk.lbstudio.meet-transcriber.plist"
LOG_PATH="$HOME/Library/Logs/meet-transcriber/daemon.log"
WATCH_PATH="$HOME/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"

echo "==> Repo: $REPO_ROOT"

# 1. Build Swift CLIs (voz-cli + who-cli) if missing or stale
for wrapper in swift-voz-wrapper swift-who-wrapper; do
    cli_name="${wrapper#swift-}"; cli_name="${cli_name%-wrapper}-cli"
    cli_path="$REPO_ROOT/$wrapper/.build/release/$cli_name"
    src_newer=$(find "$REPO_ROOT/$wrapper/Sources" -type f -newer "$cli_path" 2>/dev/null | head -1 || echo "yes")
    if [ ! -x "$cli_path" ] || [ -n "$src_newer" ]; then
        echo "==> Building $cli_name"
        (cd "$REPO_ROOT/$wrapper" && swift build -c release)
    else
        echo "==> $cli_name already up-to-date"
    fi
done

# 2. venv + deps
if [ ! -d "$REPO_ROOT/.venv" ]; then
    echo "==> Creating venv (Python 3.12)"
    uv venv --python 3.12 "$REPO_ROOT/.venv"
fi
echo "==> Installing Python deps"
VIRTUAL_ENV="$REPO_ROOT/.venv" uv pip install -e "$REPO_ROOT"

# 2. symlink /usr/local/opt/meet-transcriber → repo
sudo mkdir -p /usr/local/opt /usr/local/bin
if [ -e "$PKG_ROOT" ] && [ ! -L "$PKG_ROOT" ]; then
    echo "ERROR: $PKG_ROOT exists and is NOT a symlink. Refusing to touch."
    exit 1
fi
sudo rm -f "$PKG_ROOT"
sudo ln -s "$REPO_ROOT" "$PKG_ROOT"
echo "==> Symlinked $PKG_ROOT → $REPO_ROOT"

# 3. bin wrapper
sudo install -m 0755 "$REPO_ROOT/bin/meet-transcriber" "$BIN"
echo "==> Installed $BIN"

# 4. ffmpeg check
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "WARN: ffmpeg not in PATH. Install: brew install ffmpeg"
fi

# 5. config wizard (interactive) IF no config yet
CFG="$HOME/Library/Application Support/meet-transcriber/config.toml"
if [ ! -f "$CFG" ]; then
    echo "==> Running config wizard (osascript dialogs will pop up)"
    "$BIN" reconfigure
else
    echo "==> Config exists at $CFG — skip wizard. Run 'meet-transcriber reconfigure' to change."
fi

# 6. LaunchAgent plist (substitute paths)
mkdir -p "$(dirname "$PLIST_DST")"
mkdir -p "$(dirname "$LOG_PATH")"
sed -e "s|__WATCH_PATH__|$WATCH_PATH|g" \
    -e "s|__LOG_PATH__|$LOG_PATH|g" \
    "$PLIST_SRC" > "$PLIST_DST"
echo "==> Wrote $PLIST_DST"

# 7. (re)load LaunchAgent
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "==> LaunchAgent loaded"

echo
echo "DONE. Test with:"
echo "  meet-transcriber status"
echo "  meet-transcriber doctor"
echo "  meet-transcriber process '<path-to-m4a>'"
echo
echo "⚠️  POSLEDNÝ KROK — Full Disk Access (jednorazovo):"
echo "    LaunchAgent beží v sandboxe a nemá prístup k Voice Memos folderu."
echo "    1) System Settings → Privacy & Security → Full Disk Access"
echo "    2) Pridaj:"
echo "       /usr/local/bin/meet-transcriber"
echo "       $(readlink "$REPO_ROOT/.venv/bin/python3.12" 2>/dev/null || echo "$REPO_ROOT/.venv/bin/python3.12")"
echo "    3) Reload: launchctl kickstart -k gui/\$(id -u)/sk.lbstudio.meet-transcriber"
echo
echo "    Otvor: open 'x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles'"
