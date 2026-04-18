#!/usr/bin/env python3
"""
build_app.py — Package DocMind into a double-clickable macOS .app bundle.

Uses py2app to build a real .app that:
- Double-clicks to launch like any native Mac app
- Has a custom icon in the Dock
- Can live in /Applications or on your desktop
- Bundles Python + PySide6 + extract_v4 inside (no external Python needed)

REQUIREMENTS:
    pip3 install py2app --break-system-packages

USAGE:
    python3 build_app.py py2app

    Then move dist/DocMind.app wherever you want it.

NOTES:
- Tesseract and poppler are NOT bundled (that's an Apple-signing rabbit
  hole). The app shells out to the system-installed binaries. Your users
  will need `brew install tesseract poppler` just like you did.
- The first launch will hit Gatekeeper (unsigned app). Right-click the
  app, choose Open, approve it once. After that it opens normally.
"""

import os
from setuptools import setup

APP_NAME = "DocMind"
MAIN_SCRIPT = "DocMind.py"

OPTIONS = {
    "argv_emulation": False,
    "includes": [
        "extract_v4",
        "fitz",
        "pdfplumber",
        "pytesseract",
        "pdf2image",
        "PIL",
        "cv2",
        "numpy",
        "ebooklib",
        "bs4",
    ],
    "packages": ["PySide6"],
    "plist": {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": "com.docmind.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHumanReadableCopyright": "DocMind — feed your LLM the documents that matter",
    },
    "iconfile": "DocMind.icns" if os.path.exists("DocMind.icns") else None,
}

setup(
    name=APP_NAME,
    app=[MAIN_SCRIPT],
    options={"py2app": {k: v for k, v in OPTIONS.items() if v is not None}},
    setup_requires=["py2app"],
)
