# DocMind

**Turn your PDF and EPUB collection into something your AI can actually read.**

![DocMind screenshot](docs/screenshot.png)

DocMind is a Mac app that converts your PDFs (including the messy scanned
ones) and EPUBs into clean text your AI can use as reference material.

Drag a file or a folder in. Watch the progress bar. Get clean Markdown out.

---

## Why you might want this

You've got PDFs piling up. Research reports, internal documents, manuals,
whitepapers, scanned archives, training materials. You want your AI to know
what's in them — so when you ask a question, it answers from *your*
documents, not from its general training data.

The problem: most PDF-to-text tools give you junk. Especially when the PDF
started life as a scan. The text comes out garbled, pages get skipped, and
what reaches your AI is a mess that wastes tokens and confuses the model.

DocMind was built to fix that. Every page is read two ways — through the
PDF's built-in text AND by actually looking at the page image with OCR — and
whichever comes out cleaner wins. The result is readable text your AI can
actually use.

---

## What it looks like

| Drop a file or folder | Watch it work | Open the results |
|:-:|:-:|:-:|
| ![drop zone](docs/drop.png) | ![progress](docs/running.png) | ![finished](docs/done.png) |

---

## Install it

**You need:** A Mac running macOS 11 or later. No Terminal, no Homebrew, no
Python.

1. **Download the latest DMG** from the [Releases page](../../releases).
2. **Open the DMG.** It mounts as a disk image.
3. **Drag the DocMind icon onto the Applications folder.** That's the whole
   install.
4. **Eject the DMG** (Finder sidebar → the little ⏏ next to DocMind) and
   launch **DocMind** from Applications.

> **First time you open it:** macOS will say *"DocMind cannot be opened
> because Apple cannot check it for malicious software."* This is normal for
> apps not sold through the App Store. Right-click DocMind → **Open** →
> **Open**. You only do this once, per Mac.

Tesseract and its language data are bundled inside the app — nothing else to
install.

---

## How to use it

1. **Open DocMind** from your Applications folder.
2. **Drag one or more PDFs or EPUBs** — or a whole folder — onto the window.
3. Extraction **starts automatically.** Each file gets its own progress bar
   with a live ETA.
4. **Wait.** A small file takes a couple of minutes. A big folder of scanned
   documents can take an hour or more. Your Mac can still be used for other
   things while it runs.
5. When everything finishes you'll see per-book stats and a short reason
   explaining the score (e.g. *"Broken text layer — recovered via OCR on 150
   pages"*). Click **Show in Finder** to open the output folder, or
   **Export for AI…** to package the results for Claude, ChatGPT, Cursor, or
   Gemini CLI.

You'll get one clean Markdown file per source, plus a `_QC_REPORT.md` report
card showing how well each one came out.

---

## What do I do with the files?

The output is plain text in **Markdown**. Any AI can read it. Common uses:

**Feed it to ChatGPT / Claude as reference material.** Drag the files
directly into a new chat and say "answer my questions using these
documents."

**Build a Claude skill, Custom GPT, or Cursor rules file.** Use the
**Export for AI…** button in DocMind — it packages your extracted Markdown
into a folder shaped for your target AI and writes a ready-to-paste
`PROMPT.md` that tells the AI exactly what to do. DocMind does not create
the skill itself; your AI does, using the reference files DocMind has
already pooled.

Supported targets out of the box:
- **Claude Code** (skill via `/skill-creator`)
- **ChatGPT** (Custom GPT knowledge)
- **Cursor** (project rules)
- **Gemini CLI** (extension / `GEMINI.md`)

**Train or fine-tune your own model.** The text is clean enough to use for
training runs if that's your thing.

**Load into a vector database for RAG.** Per-page markers in the output make
chunking trivial.

---

## Options

Inside the app, one checkbox:

**Force OCR on every page** — use this when you're working with really bad
scans. It takes 3–5× longer, but it reads every page by looking at the image
instead of trusting the text the PDF claims to have. Turn it on if a first
extraction came out garbled.

---

## The report card

When DocMind finishes, it saves `_QC_REPORT.md` in your output folder:

| File | Pages | Words | Grade | Notes |
|---|---|---|---|---|
| quarterly-report-q3.pdf | 84 | 19,438 | ✅ Good | Clean embedded text — no OCR needed. |
| technical-specs-v2.pdf | 312 | 89,205 | ✅ Good | Mixed: 68% text, 32% OCR. |
| archived-memo-1987.pdf | 204 | 41,890 | ⚠️ Review | Scanned source — OCR used on every page. |

- ✅ **Good** — ready to use
- ⚠️ **Review** — readable but worth a spot-check
- ❌ **Poor** — re-run with Force OCR on

---

## Questions people ask

**Is this free?** Yes. Forever.

**Does it send my files anywhere?** No. Everything runs on your Mac. Your
documents never leave your computer.

**Does it work on Windows or Linux?** Not yet. The installer is Mac-only.
The underlying engine is Python and would work on other systems with some
adjustments — see `docs/DEVELOPERS.md`.

**Do I need Homebrew or Python?** No. The DMG ships a self-contained app
with tesseract, its libraries, and English + orientation language data all
bundled inside.

**Why does the first launch warn me about the developer?** DocMind isn't
signed with an Apple Developer ID yet (those cost $99/year). Gatekeeper
flags any unsigned app downloaded from the internet. Right-click → **Open**
approves it permanently.

**What if a PDF is DRM-protected or password-locked?** DocMind can't read
those. Unlock the PDF first (Preview or qpdf), then run it through DocMind.

**Can it handle handwritten notes or math equations?** Not well. It's built
for printed text. Math symbols and handwriting come out messy.

**My PDF came out with garbled text. What do I do?** Turn on **Force OCR**
and run it again. That fixes most issues.

**Can I process thousands of PDFs?** Yes. Point it at the folder and leave
it running overnight.

---

## For developers / building from source

Curious how it works, or want to tinker? See
[`docs/DEVELOPERS.md`](docs/DEVELOPERS.md).

The short version: DocMind is a PySide6 desktop app that wraps a Python
extraction engine (`extract_v4.py`). The engine runs text extraction via
PyMuPDF and OCR via Tesseract on every page, scores both for English-prose
quality, and keeps the winner.

**Running from source:**

```bash
# Install system libs
brew install tesseract leptonica

# Install Python deps
pip3 install pymupdf pdfplumber pytesseract pdf2image Pillow \
             opencv-python ebooklib beautifulsoup4 PySide6 \
             --break-system-packages

# Run
python3 DocMind.py
```

Or run the legacy one-shot installer: `./install.sh`.

**Building a DMG locally:**

```bash
brew install tesseract leptonica dylibbundler create-dmg
pip3 install py2app --break-system-packages
./build_release.sh          # produces dist/DocMind-1.0.0.dmg
./build_release.sh 1.2.3    # custom version
```

The DMG build is also run automatically in CI — push a `v*` tag and the
GitHub Actions workflow publishes a DMG to the matching Release.

Contributions welcome. Open an issue or a pull request.

---

## Credits

Built with [PyMuPDF](https://pymupdf.readthedocs.io/),
[Tesseract](https://github.com/tesseract-ocr/tesseract),
[OpenCV](https://opencv.org/), and
[PySide6](https://doc.qt.io/qtforpython/).

Made to help more people give their AI better source material.

---

## License

MIT. Use it, share it, remix it. If you make something cool, tell me.
