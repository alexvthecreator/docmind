#!/usr/bin/env bash
# create_dmg.sh — wrap dist/DocMind.app in a styled .dmg installer.
#
# Produces dist/DocMind-<VERSION>.dmg with a visual layout:
#
#     ┌─────────────────────────────────┐
#     │                                 │
#     │   [DocMind]    ──→   [Apps]     │
#     │                                 │
#     └─────────────────────────────────┘
#
# The user mounts the DMG, drags the DocMind icon over the Applications
# shortcut, ejects. That's the whole install.
#
# Prereq:
#     brew install create-dmg
#
# Usage:
#     ./create_dmg.sh            # uses VERSION=1.0.0
#     ./create_dmg.sh 1.2.3      # override version

set -euo pipefail

VERSION="${1:-1.0.0}"
APP_DIR="dist/DocMind.app"
DMG_OUT="dist/DocMind-${VERSION}.dmg"
ICON_FILE="DocMind.icns"
BG_FILE="docs/dmg_background.png"

if ! command -v create-dmg >/dev/null 2>&1; then
  echo "ERROR: create-dmg not on PATH. Run: brew install create-dmg" >&2
  exit 2
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "ERROR: $APP_DIR not found." >&2
  echo "Run: python3 build_app.py py2app && python3 bundle_binaries.py" >&2
  exit 2
fi

# create-dmg refuses to overwrite; remove the old one first.
rm -f "$DMG_OUT"

VOLICON_ARGS=()
if [[ -f "$ICON_FILE" ]]; then
  VOLICON_ARGS=(--volicon "$ICON_FILE")
else
  echo "  note: $ICON_FILE not found — DMG will use the default volume icon."
fi

BG_ARGS=()
if [[ -f "$BG_FILE" ]]; then
  BG_ARGS=(--background "$BG_FILE")
else
  echo "  note: $BG_FILE not found — DMG will use the plain default background."
fi

echo "Packaging $APP_DIR → $DMG_OUT (version $VERSION)…"
# ${arr[@]+"${arr[@]}"} is the bash idiom for safely expanding a possibly-empty
# array under `set -u`: it expands to nothing when the array has no elements,
# and to the full array when it does.
create-dmg \
  --volname "DocMind" \
  ${VOLICON_ARGS[@]+"${VOLICON_ARGS[@]}"} \
  ${BG_ARGS[@]+"${BG_ARGS[@]}"} \
  --window-size 520 340 \
  --icon-size 96 \
  --icon "DocMind.app" 130 170 \
  --hide-extension "DocMind.app" \
  --app-drop-link 390 170 \
  "$DMG_OUT" \
  "$APP_DIR"

echo ""
echo "✓ $DMG_OUT"
ls -lh "$DMG_OUT"
