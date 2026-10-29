#!/bin/bash
# Build meet-transcriber .pkg installer.
# Bundles: bundled Python 3.12, slim venv (jinja2/soundfile/sqlite-utils/python-dateutil),
#          app code, templates, launchd plist, bin wrapper, voz-cli + who-cli binaries.
# Voz + Who models auto-download on first run (no HF_TOKEN needed at build time).
# Prereqs: uv installed, Xcode CLI tools.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="${VERSION:-1.0}"
BUILD_DIR="$REPO_ROOT/build"
PAYLOAD="$BUILD_DIR/payload"
APP_ROOT="$PAYLOAD/usr/local/opt/meet-transcriber"

echo "==> Clean build dir"
rm -rf "$BUILD_DIR"
mkdir -p "$APP_ROOT"

# ─── 1. Build Swift CLIs (voz-cli + who-cli) ──────────────────────────────
echo "==> Building Swift CLIs"
for wrapper in swift-voz-wrapper swift-who-wrapper; do
    cli_name="${wrapper#swift-}"; cli_name="${cli_name%-wrapper}-cli"
    (cd "$REPO_ROOT/$wrapper" && swift build -c release)
    echo "    built $cli_name"
done

# ─── 2. Fetch python-build-standalone 3.12 (aarch64) ──────────────────────
PBS_VERSION="20250311"   # pin a known-good indygreg release
PBS_FILE="cpython-3.12.9+${PBS_VERSION}-aarch64-apple-darwin-install_only.tar.gz"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_VERSION}/${PBS_FILE}"

echo "==> Fetching python-build-standalone"
if [ ! -f "$BUILD_DIR/$PBS_FILE" ]; then
    curl -L -o "$BUILD_DIR/$PBS_FILE" "$PBS_URL"
fi
mkdir -p "$APP_ROOT/python"
tar xzf "$BUILD_DIR/$PBS_FILE" -C "$APP_ROOT/python" --strip-components=1
PYTHON="$APP_ROOT/python/bin/python3.12"
"$PYTHON" --version

# ─── 3. Create venv using bundled python, install deps ────────────────────
echo "==> Building venv"
"$PYTHON" -m venv "$APP_ROOT/venv"
"$APP_ROOT/venv/bin/pip" install --upgrade pip
"$APP_ROOT/venv/bin/pip" install -e "$REPO_ROOT"

# ─── 4. Copy app assets ───────────────────────────────────────────────────
echo "==> Copying app assets"
cp -R "$REPO_ROOT/src/meet_transcriber" "$APP_ROOT/app_src"
cp -R "$REPO_ROOT/templates" "$APP_ROOT/templates"
cp -R "$REPO_ROOT/launchd" "$APP_ROOT/launchd"
mkdir -p "$APP_ROOT/bin"
cp "$REPO_ROOT/bin/meet-transcriber" "$APP_ROOT/bin/meet-transcriber"
cp "$REPO_ROOT/swift-voz-wrapper/.build/release/voz-cli" "$APP_ROOT/bin/voz-cli"
cp "$REPO_ROOT/swift-who-wrapper/.build/release/who-cli" "$APP_ROOT/bin/who-cli"
chmod +x "$APP_ROOT/bin"/*

# ─── 5. pkgbuild → component .pkg ─────────────────────────────────────────
echo "==> pkgbuild"
pkgbuild \
    --root "$PAYLOAD" \
    --identifier sk.lbstudio.meet-transcriber \
    --version "$VERSION" \
    --scripts "$REPO_ROOT/pkg/scripts" \
    --install-location / \
    "$BUILD_DIR/meet-transcriber.component.pkg"

# ─── 6. productbuild → distribution .pkg with UI ──────────────────────────
echo "==> productbuild"
cp "$REPO_ROOT/pkg/welcome.txt" "$BUILD_DIR/welcome.txt"
productbuild \
    --distribution "$REPO_ROOT/pkg/distribution.xml" \
    --package-path "$BUILD_DIR" \
    --resources "$BUILD_DIR" \
    "$BUILD_DIR/meet-transcriber-v${VERSION}.pkg"

echo
echo "DONE: $BUILD_DIR/meet-transcriber-v${VERSION}.pkg"
du -sh "$BUILD_DIR/meet-transcriber-v${VERSION}.pkg"
echo
echo "Note: Voz (~467 MB) + Who (~81 MB) models auto-download on first run."
echo "Upload to NAS and share link with colleagues."
