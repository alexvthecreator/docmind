#!/bin/bash
#
# install.sh — One-shot installer for DocMind.
#
# This script:
#   1. Checks for Homebrew, installs if missing
#   2. Installs tesseract and poppler via brew
#   3. Installs all Python dependencies
#   4. Generates the app icon
#   5. Builds DocMind.app
#   6. Moves it to ~/Applications
#
# USAGE:
#   cd /path/to/docmind
#   chmod +x install.sh
#   ./install.sh
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "╔════════════════════════════════════════╗"
echo "║        DocMind — Installer            ║"
echo "╚════════════════════════════════════════╝"
echo ""

# ─── Homebrew ──
if ! command -v brew &> /dev/null; then
    echo "→ Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "✓ Homebrew found"
fi

# ─── System tools ──
echo ""
echo "→ Installing tesseract and poppler (for OCR)..."
brew list tesseract &>/dev/null || brew install tesseract
brew list poppler &>/dev/null || brew install poppler
echo "✓ System tools ready"

# ─── Python deps ──
echo ""
echo "→ Installing Python libraries..."
pip3 install --quiet --break-system-packages \
    PySide6 \
    pymupdf \
    pdfplumber \
    pytesseract \
    pdf2image \
    Pillow \
    opencv-python \
    ebooklib \
    beautifulsoup4 \
    py2app
echo "✓ Python libraries ready"

# ─── Icon ──
echo ""
echo "→ Generating app icon..."
python3 make_icon.py
echo "✓ Icon ready"

# ─── Build app ──
echo ""
echo "→ Building DocMind.app (this takes a minute or two)..."
rm -rf build dist
python3 build_app.py py2app --quiet

if [ ! -d "dist/DocMind.app" ]; then
    echo "✗ Build failed. Check the output above."
    exit 1
fi

# ─── Install to ~/Applications ──
echo ""
mkdir -p ~/Applications
if [ -d ~/Applications/DocMind.app ]; then
    echo "→ Replacing existing ~/Applications/DocMind.app..."
    rm -rf ~/Applications/DocMind.app
fi
cp -R dist/DocMind.app ~/Applications/
echo "✓ Installed to ~/Applications/DocMind.app"

# ─── Clean up build artifacts ──
rm -rf build dist

echo ""
echo "╔════════════════════════════════════════╗"
echo "║            ✓  Done!                    ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "DocMind.app is in ~/Applications"
echo ""
echo "FIRST LAUNCH:"
echo "   macOS Gatekeeper will block unsigned apps on the first try."
echo "   Right-click DocMind.app → Open → Open anyway."
echo "   You only need to do this once."
echo ""
echo "   Or from Terminal:"
echo "     open ~/Applications/DocMind.app"
echo ""
