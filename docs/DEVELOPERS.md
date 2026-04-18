# Developer Guide

This is the technical side of DocMind for people who want to understand,
modify, or contribute.

## Architecture

DocMind is a thin PySide6 shell around a Python extraction engine.

```
DocMind.app
├── DocMind.py       ← Qt GUI (drop zone, progress, file list)
├── extract_v4.py    ← Extraction engine (PDF → Markdown)
├── build_app.py     ← py2app packaging config
├── make_icon.py     ← Draws the app icon at all sizes
└── install.sh       ← End-to-end installer
```

The GUI calls `extract_v4.extract_pdf()` in a background thread,
emitting Qt signals to update the progress UI.

## The extraction engine

`extract_v4.py` is the interesting part. For each page of each PDF:

1. **Try embedded-text extraction** via PyMuPDF.
2. **Try OCR** if the embedded text scores below 45/100 quality.
3. **Score both outputs** using an English-prose quality model that
   weighs common-word ratio, garbage-character ratio, average word
   length, and word count.
4. **Keep the winner.**

The OCR path:

1. Rasterize the page at 300 DPI using PyMuPDF's `get_pixmap`.
2. Preprocess via OpenCV: grayscale → deskew → denoise → adaptive
   threshold.
3. Auto-detect the right Tesseract PSM (6 for uniform body, 3 for
   mixed layouts) by counting distinct text-block heights.
4. Run Tesseract with `--oem 1` (LSTM engine) and `lang=eng`.

After per-page extraction, the document goes through:

- Encoding normalization (PUA ligatures → real ligatures, Unicode
  ligatures → ASCII equivalents, Windows-1252 weirdness)
- Garbage-character stripping
- Running-header/footer detection and stripping (strings that appear
  on >20% of pages within a 200-page window)
- Conservative dictionary correction (only fixes systematic OCR
  errors like `rn`→`m` when the correction produces a common English
  word AND the original wasn't one — this protects proper nouns and
  domain-specific terms)

The engine also has EPUB support (`extract_epub()`), even though the
app is branded as PDF-focused. If you want to expose that in the UI,
it's a one-line change in `DocMind.py` to include `.epub` in the file
filter.

## Running from source

```bash
# Install dependencies
brew install tesseract poppler
pip3 install pymupdf pdfplumber pytesseract pdf2image Pillow \
             opencv-python ebooklib beautifulsoup4 PySide6 py2app \
             --break-system-packages

# Run the GUI directly (no .app bundle needed)
cd docmind
python3 DocMind.py

# Or run the engine from the command line on a folder
python3 extract_v4.py ~/Downloads/pdfs --force-ocr
```

## Building the .app bundle

```bash
python3 make_icon.py        # generates DocMind.icns
python3 build_app.py py2app # builds dist/DocMind.app
```

Or run `./install.sh` which does everything.

## Customizing the quality model

The scoring lives in `extract_v4.py`'s `score_text_quality()` function.
It returns 0–100 based on four signals:

| Signal | Weight | Why |
|---|---:|---|
| Common-word ratio | 60% | Real prose: 25–50%. Garbled OCR: <5%. |
| Word length | 20% | Real prose: 4.5–5.5 avg. OCR gibberish: extremes. |
| Garbage chars | −20% | Direct penalty for PUA / control chars. |
| Word count | +20% max | Logarithmic bonus. More words = more signal. |

The common-word dictionary is hard-coded in `COMMON_WORDS`. If you're
processing documents in a non-English language, replace this set with
the 500 most common words in your target language and the rest of the
pipeline works unchanged.

## Customizing OCR behavior

The core OCR call is in `ocr_page()`. The defaults:

- 300 DPI rasterization
- OpenCV preprocessing: grayscale, deskew (±15°), denoise, adaptive threshold
- Tesseract OEM 1 (LSTM engine), English, auto-selected PSM

Tunable via the constants at the top of `extract_v4.py`. If you want to
try cloud OCR (Google Vision, Mathpix, Azure Document Intelligence),
add a third candidate in `extract_page()` alongside text and OCR, score
it with the same quality model, and the winner-picking logic handles
the rest.

## Contributing

PRs welcome. Things that would be genuinely useful:

- Windows and Linux installers (the engine is already cross-platform)
- A settings panel in the GUI (DPI, workers, output directory)
- Side-by-side page preview (scan image next to extracted text)
- A per-page "re-OCR this page" button
- Cloud OCR integration (Google Vision, Mathpix)
- Non-English language packs
- Code signing + notarization for a smoother install
- EPUB toggle in the UI

File an issue first if you're planning something big — happy to
discuss the approach.

## License

MIT. See `LICENSE` at the repo root.
