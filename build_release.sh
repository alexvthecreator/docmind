#!/usr/bin/env bash
# build_release.sh — one-shot builder for DocMind-<VERSION>.dmg.
#
# Pipeline:
#   1. py2app   → dist/DocMind.app (Python + PySide6 + deps)
#   2. bundle   → adds tesseract + dylibs + tessdata to the bundle
#   3. dmg      → wraps the .app in a styled drag-to-Apps installer
#
# Prereqs on the build machine:
#     brew install tesseract leptonica dylibbundler create-dmg
#     pip3 install py2app pymupdf pdfplumber pytesseract pdf2image \
#                  Pillow opencv-python ebooklib beautifulsoup4 \
#                  --break-system-packages
#
# Usage:
#     ./build_release.sh            # VERSION=1.0.0
#     ./build_release.sh 1.2.3      # override version

set -euo pipefail

VERSION="${1:-1.0.0}"

cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " DocMind release build — VERSION $VERSION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "▶ [1/3] py2app — building dist/DocMind.app …"
rm -rf build dist
python3 build_app.py py2app
if [[ ! -d "dist/DocMind.app" ]]; then
  echo "ERROR: py2app did not produce dist/DocMind.app" >&2
  exit 1
fi
echo ""

echo "▶ [2/3] bundle_binaries — baking tesseract + tessdata into the .app …"
python3 bundle_binaries.py --app dist/DocMind.app
echo ""

echo "▶ [3/3] create_dmg — wrapping in a drag-to-Applications DMG …"
./create_dmg.sh "$VERSION"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✓ Release ready: dist/DocMind-${VERSION}.dmg"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
