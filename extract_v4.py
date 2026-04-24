#!/usr/bin/env python3
"""
Book → Markdown Extractor — V4
==============================
LLM-training-grade text extraction. Optimizes for SEMANTIC FIDELITY —
the words on the page are what the author actually wrote, with maximum
accuracy on cheap scanned books.

Design principles (set by user):
- Quality over speed. Runtime doesn't matter; accuracy does.
- Output is LLM training/reference material. Clean readable text wins
  over preserved layout. Structure is a bonus, not a requirement.
- Cheap scanned PDFs (OceanOfPDF-style) are the primary target.

Quality strategy (per page, per book):
1. Try text extraction via PyMuPDF.
2. Rasterize the page at 300 DPI + preprocess with OpenCV (deskew,
   denoise, adaptive threshold) + run Tesseract OCR with LSTM engine.
3. Score both outputs against a quality model (common-word ratio,
   garbage-char ratio, word-length distribution).
4. Keep the winning output per page.
5. Apply conservative dictionary correction (doesn't touch proper
   nouns or words already in the dictionary).
6. PUA/ligature recovery, encoding normalization, garbage stripping.
7. Emit per-book Markdown + a detailed QC report.

Falls back gracefully for EPUBs (no OCR needed, just HTML→text).

SETUP:
    brew install tesseract poppler
    pip3 install pymupdf pdfplumber pytesseract pdf2image Pillow \\
                 opencv-python ebooklib beautifulsoup4 \\
                 --break-system-packages

USAGE:
    python3 extract_v4.py <source_folder> [--output <out_folder>]
                         [--force-ocr] [--skip-existing] [--workers N]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import io
import os
import re
import sys
import traceback
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

warnings.filterwarnings("ignore")

# ─── DEPENDENCY CHECK ────────────────────────────────────────────────────────

MISSING = []
try:
    import fitz  # PyMuPDF
except ImportError:
    MISSING.append("pymupdf")
try:
    import pytesseract
    from pdf2image import convert_from_path
    pytesseract.get_tesseract_version()
except Exception:
    MISSING.append("pytesseract/pdf2image/tesseract-binary")
try:
    from PIL import Image
except ImportError:
    MISSING.append("Pillow")
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    HAS_EPUB = True
except ImportError:
    HAS_EPUB = False


# ─── ENGLISH DICTIONARY (for quality scoring & correction) ──────────────────

# Top ~500 most common English words. Used for quality scoring (page has
# text if common-word ratio is high) and as a whitelist (words here are
# never "corrected" by the dictionary pass).
COMMON_WORDS = frozenset("""
the be to of and a in that have i it for not on with he as you do at this but his
by from they we say her she or an will my one all would there their what so up out
if about who get which go me when make can like time no just him know take people
into year your good some could them see other than then now look only come its over
think also back after use two how our work first well way even new want because any
these give day most us is was are were been being has had having does did doing get
got gets gotten know knows knew known make makes made making say says said saying
see sees saw seen think thinks thought want wants wanted wanting look looks looked
looking come comes came coming take takes took taken go goes went gone use uses used
using find finds found ask asks asked working seem seems seemed feel feels felt
try tries tried trying leave leaves left call calls called
more less than through during before after above below between both each every other
same here there when where why how what who whom whose which that this those these
very really quite rather too much many few little
into onto upon around about toward against without within across along
always never often sometimes usually rarely already still yet once
always every never nothing something anything everything nobody somebody anybody everybody
business company customer customers market marketing sale sales sell selling seller
buyer buyers product products service services money price prices cost costs profit
profits profitable loss losses value values offer offers ad ads advertising advertisement
advertisements campaign campaigns copy headline headlines story stories message
letter letters book books page pages chapter chapters article articles
client clients prospect prospects lead leads list lists audience audiences media
order orders buying purchase purchases result results response responses
test tests testing tested strategy strategies plan plans planning target targets
promote promotion promotions promotional market markets marketing
yes no maybe please thank thanks sorry hello hi hey okay right wrong true false
write writes wrote written read reads reading send sends sent sending
man men woman women child children person people
world life work day days week weeks month months year years home house family
mind body head hand hands eye eyes word words name names thing things
""".split())


# ─── ENCODING NORMALIZATION ──────────────────────────────────────────────────

PUA_LIGATURE_MAP = {
    "\uE000": "fi", "\uE001": "fl", "\uE002": "ff", "\uE003": "ffi",
    "\uE004": "ffl", "\uE005": "ft", "\uE006": "st", "\uE007": "ct",
    "\uE062": "Th", "\uE0BB": "Th",
    "\uE09D": "ft", "\uE117": "ft",
}

UNICODE_LIGATURE_MAP = {
    "\uFB00": "ff", "\uFB01": "fi", "\uFB02": "fl",
    "\uFB03": "ffi", "\uFB04": "ffl", "\uFB05": "st", "\uFB06": "st",
}

# Control chars and odd Windows-1252 mismappings that commonly appear.
CONTROL_REPLACEMENTS = {
    "\u00A0": " ", "\u00AD": "", "\uFEFF": "",
    "\u2028": "\n", "\u2029": "\n\n",
    "\uF0B7": "•", "\uF0A7": "•", "\uF0D8": "•", "\uF020": " ",
    "\u2018": "'", "\u2019": "'",
    "\u201C": '"', "\u201D": '"',
    "\u2013": "-", "\u2014": "—",
    "\u2026": "...",
    "\u0091": "'", "\u0092": "'", "\u0093": '"', "\u0094": '"',
    "\u0096": "-", "\u0097": "—", "\u0085": "...",
}

# Words in the dictionary whitelist stay as-is. Everything else is eligible
# for correction if the OCR-error pattern is confident.
OCR_CORRECTION_PATTERNS = [
    # Common systematic Tesseract errors on low-quality scans.
    # Applied only to tokens NOT in COMMON_WORDS and where the result IS.
    (re.compile(r"\brn"), "m"),     # "rnoney" → "money"
    (re.compile(r"rn\b"), "m"),     # "charrn" → "charm"
    (re.compile(r"\bcl"), "d"),     # "clog" stays "clog" only if in dict
    (re.compile(r"1"), "l"),        # when surrounded by letters
    (re.compile(r"0"), "o"),        # when surrounded by letters
]


def normalize_encoding(text: str) -> str:
    """Apply all deterministic character-level fixes."""
    for k, v in PUA_LIGATURE_MAP.items():
        text = text.replace(k, v)
    for k, v in UNICODE_LIGATURE_MAP.items():
        text = text.replace(k, v)
    for k, v in CONTROL_REPLACEMENTS.items():
        text = text.replace(k, v)
    text = re.sub(r"\(cid:\d+\)", "", text)
    return text


def is_garbage_char(c: str) -> bool:
    """True only if a character is unambiguous garbage."""
    cp = ord(c)
    if cp < 128:
        return False
    if 0xE000 <= cp <= 0xF8FF:
        return True  # PUA — should have been mapped, anything left is garbage
    if 0xD800 <= cp <= 0xDFFF:
        return True  # surrogates
    if cp < 0x20 and c not in ("\t", "\n", "\r"):
        return True
    if 0xFFF0 <= cp <= 0xFFFF:
        return True
    return False


def strip_garbage_chars(text: str) -> str:
    return "".join(c for c in text if not is_garbage_char(c))


# ─── QUALITY SCORING ─────────────────────────────────────────────────────────

@dataclass
class QualityScore:
    """How good is this extracted text? Higher is better."""
    score: float
    word_count: int
    common_word_ratio: float
    garbage_ratio: float
    avg_word_length: float
    reason: str = ""

    def __lt__(self, other):
        return self.score < other.score


def score_text_quality(text: str) -> QualityScore:
    """Return a 0-100 quality score for extracted text.

    Used to compare two extractions of the same page (text extraction vs
    OCR) and pick the better one. Also used as a reject filter for
    garbage pages.

    Scoring factors:
    - common_word_ratio: fraction of tokens that are common English words.
      Real English prose scores 0.25–0.50. Garbled OCR scores <0.05.
    - garbage_ratio: fraction of non-ASCII garbage characters.
    - avg_word_length: real prose averages 4.5–5.5. Garbled OCR is
      either very low (single chars) or very high (merged-together
      junk).
    - word_count: more words generally means more signal.
    """
    if not text or not text.strip():
        return QualityScore(0.0, 0, 0.0, 1.0, 0.0, "empty")

    stripped = text.strip()
    tokens = stripped.split()
    word_count = len(tokens)
    if word_count == 0:
        return QualityScore(0.0, 0, 0.0, 1.0, 0.0, "no tokens")

    alpha_tokens = [
        re.sub(r"[^a-zA-Z]", "", t).lower() for t in tokens
    ]
    alpha_tokens = [t for t in alpha_tokens if t]

    if not alpha_tokens:
        return QualityScore(0.0, word_count, 0.0, 1.0, 0.0, "no alpha tokens")

    common_hits = sum(1 for t in alpha_tokens if t in COMMON_WORDS)
    common_ratio = common_hits / len(alpha_tokens)

    garbage_count = sum(1 for c in text if is_garbage_char(c))
    garbage_ratio = garbage_count / max(len(text), 1)

    avg_len = sum(len(t) for t in alpha_tokens) / len(alpha_tokens)

    # Weighted composite score
    #   common_ratio: strongest single signal, weight 60
    #   avg_word_length: penalty for extreme values, weight 20
    #   garbage_ratio: direct penalty, weight 20
    #   word_count: logarithmic bonus, up to 20

    length_penalty = 1.0
    if avg_len < 2.5 or avg_len > 9:
        length_penalty = 0.3
    elif avg_len < 3 or avg_len > 7:
        length_penalty = 0.7

    count_bonus = min(20, 5 * (word_count / 50))

    score = (
        60 * common_ratio
        + 20 * length_penalty
        - 100 * garbage_ratio
        + count_bonus
    )

    # E2: scrambled-ligature / broken-CMap detector.
    # Real English always has >15% common words OR average word length >3.
    # When both are low across 30+ tokens, it's almost certainly scrambled
    # text from a broken ToUnicode CMap — demote the score so OCR wins.
    if common_ratio < 0.15 and avg_len < 3.0 and word_count > 30:
        score = score * 0.1

    score = max(0.0, min(100.0, score))

    return QualityScore(
        score=score,
        word_count=word_count,
        common_word_ratio=common_ratio,
        garbage_ratio=garbage_ratio,
        avg_word_length=avg_len,
    )


# ─── PDF TEXT EXTRACTION ─────────────────────────────────────────────────────

def extract_page_text_pymupdf(doc, page_idx: int) -> str:
    """Best available in-PDF text extraction for a page."""
    try:
        page = doc[page_idx]
        # The "text" mode returns clean reading-order text with hyphenation
        # handled. Better than "dict" or "blocks" for this use case.
        return page.get_text("text") or ""
    except Exception:
        return ""


# ─── IMAGE PREPROCESSING FOR OCR ─────────────────────────────────────────────

def preprocess_for_ocr(pil_image: "Image.Image") -> "Image.Image":
    """Apply OpenCV preprocessing to maximize OCR accuracy on scanned pages.

    Steps (in order):
    1. Convert to grayscale
    2. Deskew (correct rotation up to ±15°)
    3. Denoise (fast non-local means)
    4. Adaptive threshold (handles uneven lighting / yellowed pages)

    Returns: a PIL image ready for Tesseract.
    """
    if not HAS_CV2:
        return pil_image

    # PIL RGB → numpy BGR
    arr = np.array(pil_image)
    if arr.ndim == 3:
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    else:
        gray = arr

    # Deskew via minimum area rect of all non-white pixels
    try:
        inverted = cv2.bitwise_not(gray)
        _, binary = cv2.threshold(
            inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) > 1000:  # enough ink to estimate skew reliably
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            if abs(angle) > 0.5 and abs(angle) < 15:
                h, w = gray.shape
                M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
                gray = cv2.warpAffine(
                    gray, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )
    except Exception:
        pass

    # Denoise (mild — too aggressive destroys small letters)
    try:
        gray = cv2.fastNlMeansDenoising(gray, None, h=10,
                                         templateWindowSize=7,
                                         searchWindowSize=21)
    except Exception:
        pass

    # Adaptive threshold — best for uneven lighting / yellowed book pages
    try:
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 10,
        )
        return Image.fromarray(thresh)
    except Exception:
        return Image.fromarray(gray)


def detect_page_segmentation_mode(pil_image: "Image.Image") -> int:
    """Pick the right Tesseract PSM for this page.

    PSM 6 — assume uniform block of text (dense body pages)
    PSM 3 — automatic (default, mixed content, title pages)
    PSM 4 — single column of variable-size text (chapter starts)

    Heuristic: if the page has multiple distinct text regions at very
    different sizes, use PSM 3. Otherwise PSM 6.
    """
    if not HAS_CV2:
        return 6
    try:
        arr = np.array(pil_image.convert("L"))
        _, binary = cv2.threshold(
            arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        # Morphological close to merge characters into text blocks
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(
            closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return 6
        heights = [cv2.boundingRect(c)[3] for c in contours]
        heights = [h for h in heights if h > 5]  # filter noise
        if len(heights) < 3:
            return 3
        # If heights are very uniform → body page → PSM 6
        median_h = sorted(heights)[len(heights) // 2]
        uniform = sum(
            1 for h in heights if median_h * 0.7 <= h <= median_h * 1.3
        )
        if uniform / len(heights) > 0.8:
            return 6
        return 3
    except Exception:
        return 6


def ocr_page(pil_image: "Image.Image") -> str:
    """Run Tesseract OCR on a preprocessed page image."""
    preprocessed = preprocess_for_ocr(pil_image)
    psm = detect_page_segmentation_mode(preprocessed)
    config = f"--oem 1 --psm {psm}"
    try:
        return pytesseract.image_to_string(
            preprocessed, lang="eng", config=config
        )
    except Exception:
        return ""


# ─── PDF → PAGE IMAGES (streaming) ───────────────────────────────────────────

def pdf_page_to_image(doc, page_idx: int, dpi: int = 300) -> "Image.Image":
    """Rasterize a single PDF page to a PIL image at the given DPI.

    Uses PyMuPDF directly so we don't need to invoke poppler via pdf2image
    per-page (much faster, and streams one page at a time without holding
    the whole book in RAM).
    """
    page = doc[page_idx]
    # fitz's Matrix(zoom, zoom). 300 DPI with 72 DPI base = zoom 300/72
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    # Convert pix → PIL
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


# ─── CONSERVATIVE DICTIONARY CORRECTION ──────────────────────────────────────

def conservative_ocr_corrections(text: str) -> str:
    """Apply systematic OCR-error fixes only when the correction is
    unambiguously better.

    Rule: if a word contains an OCR-error pattern AND the word after
    correction is in COMMON_WORDS AND the word before correction is not,
    we correct. This protects proper nouns (Bejakovic, Scientology,
    MADLeadFlow) and unusual-but-legitimate words.
    """
    def fix_word(word: str) -> str:
        if not word or not word[0].isalpha():
            return word
        clean = word.lower().strip(".,;:!?\"'()-")
        if clean in COMMON_WORDS:
            return word  # already correct
        if len(clean) > 25:
            return word  # likely garbage, not a mistaken word

        for pattern, replacement in [
            (re.compile(r"rn"), "m"),
            (re.compile(r"cl"), "d"),
            (re.compile(r"vv"), "w"),
            (re.compile(r"0"), "o"),
            (re.compile(r"1"), "l"),
        ]:
            candidate = pattern.sub(replacement, clean)
            if candidate != clean and candidate in COMMON_WORDS:
                # Preserve original capitalization pattern
                if word.isupper():
                    return candidate.upper() + word[len(clean):]
                if word[0].isupper():
                    return candidate.capitalize() + word[len(clean):]
                return candidate + word[len(clean):]
        return word

    return re.sub(r"\S+", lambda m: fix_word(m.group(0)), text)


# ─── PAGE-LEVEL EXTRACTION ORCHESTRATION ─────────────────────────────────────

@dataclass
class PageResult:
    page_num: int
    method: str                    # "text", "ocr", or "none"
    text: str
    score: QualityScore
    text_score: QualityScore | None = None
    ocr_score: QualityScore | None = None
    ocr_error: str | None = None   # set when OCR was attempted and threw


def extract_page(
    doc, page_idx: int, force_ocr: bool = False,
    min_text_score_for_skip_ocr: float = 45.0,
) -> PageResult:
    """Extract a single page. Runs text extraction + OCR, picks the better.

    Args:
        doc: Open fitz Document
        page_idx: 0-indexed page number
        force_ocr: If True, run OCR even when text extraction looks good.
        min_text_score_for_skip_ocr: If text extraction scores above this,
            don't bother with OCR (saves time on clean PDFs). Set to 999
            to force both always.

    Returns: PageResult with the winning text.
    """
    page_num = page_idx + 1

    # Step 1: text extraction
    raw_text = extract_page_text_pymupdf(doc, page_idx)
    text_normalized = normalize_encoding(raw_text)
    text_score = score_text_quality(text_normalized)

    # Step 2: decide whether to run OCR
    run_ocr = force_ocr or text_score.score < min_text_score_for_skip_ocr

    if not run_ocr:
        return PageResult(
            page_num=page_num,
            method="text",
            text=text_normalized,
            score=text_score,
            text_score=text_score,
            ocr_score=None,
        )

    # Step 3: OCR
    ocr_error: str | None = None
    try:
        image = pdf_page_to_image(doc, page_idx, dpi=300)
        ocr_raw = ocr_page(image)
        ocr_normalized = normalize_encoding(ocr_raw)
        ocr_score = score_text_quality(ocr_normalized)
    except Exception as e:
        # E1: surface the exception instead of swallowing it silently
        ocr_error = f"{type(e).__name__}: {e}"
        ocr_normalized = ""
        ocr_score = QualityScore(
            0.0, 0, 0.0, 1.0, 0.0, f"ocr exception: {type(e).__name__}"
        )

    # Step 4: pick the winner
    # E3: decision rule hardening — if the text layer has near-zero real English
    # (broken ToUnicode CMap, scrambled ligatures) and OCR looks plausible,
    # OCR wins regardless of raw score margin.
    if (
        text_score.common_word_ratio < 0.10
        and ocr_score.common_word_ratio > 0.30
        and ocr_normalized.strip()
    ):
        return PageResult(
            page_num=page_num,
            method="ocr",
            text=ocr_normalized,
            score=ocr_score,
            text_score=text_score,
            ocr_score=ocr_score,
            ocr_error=ocr_error,
        )

    if ocr_score.score > text_score.score + 5:
        # OCR won by a meaningful margin
        return PageResult(
            page_num=page_num,
            method="ocr",
            text=ocr_normalized,
            score=ocr_score,
            text_score=text_score,
            ocr_score=ocr_score,
            ocr_error=ocr_error,
        )
    elif text_score.score > 0:
        return PageResult(
            page_num=page_num,
            method="text",
            text=text_normalized,
            score=text_score,
            text_score=text_score,
            ocr_score=ocr_score,
            ocr_error=ocr_error,
        )
    elif ocr_score.score > 0:
        return PageResult(
            page_num=page_num,
            method="ocr",
            text=ocr_normalized,
            score=ocr_score,
            text_score=text_score,
            ocr_score=ocr_score,
            ocr_error=ocr_error,
        )
    else:
        return PageResult(
            page_num=page_num,
            method="none",
            text="",
            score=text_score,
            ocr_error=ocr_error,
        )


# ─── RUNNING HEADER/FOOTER STRIPPING ─────────────────────────────────────────

def detect_running_boilerplate(pages: list[PageResult], min_pages: int = 20) -> set[str]:
    """Find lines that repeat on many pages — these are running
    headers/footers or edition boilerplate."""
    if len(pages) < min_pages:
        return set()

    counter = Counter()
    sampled = 0
    for p in pages:
        sampled += 1
        seen_on_page = set()
        for line in p.text.split("\n"):
            t = line.strip()
            if 3 <= len(t) <= 80 and t not in seen_on_page:
                counter[t] += 1
                seen_on_page.add(t)
    threshold = max(5, sampled // 5)  # appears on ≥ 20% of pages
    return {t for t, c in counter.items() if c >= threshold}


def strip_boilerplate_and_page_numbers(text: str, boilerplate: set[str]) -> str:
    """Remove running boilerplate and standalone page-number lines."""
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped in boilerplate:
            continue
        if re.match(r"^\d{1,4}$", stripped):
            continue
        out.append(line)
    return "\n".join(out)


# ─── BOOK-LEVEL ASSEMBLY ─────────────────────────────────────────────────────

@dataclass
class BookResult:
    path: Path
    pages_extracted: int = 0
    pages_skipped: int = 0
    pages_via_text: int = 0
    pages_via_ocr: int = 0
    avg_page_score: float = 0.0
    word_count: int = 0
    markdown: str = ""
    issues: list[str] = field(default_factory=list)
    warnings_: list[str] = field(default_factory=list)
    ocr_errors: list[str] = field(default_factory=list)  # "p{N}: {ExcType}: {msg}"
    reason: str = ""


def extract_pdf(
    pdf_path: Path,
    force_ocr: bool = False,
    verbose: bool = True,
    progress_prefix: str = "",
) -> BookResult:
    """Extract an entire PDF to clean Markdown for LLM consumption."""
    result = BookResult(path=pdf_path)

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        result.issues.append(f"Failed to open PDF: {e}")
        return result

    page_results: list[PageResult] = []
    n_pages = doc.page_count

    for idx in range(n_pages):
        try:
            pr = extract_page(doc, idx, force_ocr=force_ocr)
        except Exception as e:
            pr = PageResult(
                page_num=idx + 1,
                method="none",
                text="",
                score=QualityScore(0, 0, 0, 1, 0, f"exception: {e}"),
            )
        page_results.append(pr)
        if verbose and (idx + 1) % 25 == 0:
            print(
                f"    {progress_prefix}page {idx + 1}/{n_pages} "
                f"(last: {pr.method}, score {pr.score.score:.0f})",
                file=sys.stderr,
            )

    doc.close()

    # Collect OCR exception reports from individual pages
    for pr in page_results:
        if pr.ocr_error:
            result.ocr_errors.append(f"p{pr.page_num}: {pr.ocr_error}")

    # Strip running boilerplate across all pages
    boilerplate = detect_running_boilerplate(page_results)

    # Assemble markdown
    chunks = []
    scores = []
    for pr in page_results:
        if pr.method == "none" or pr.score.score < 15:
            result.pages_skipped += 1
            chunks.append(f"<!-- Page {pr.page_num}: skipped ({pr.score.reason or 'low quality'}) -->")
            continue
        cleaned = strip_boilerplate_and_page_numbers(pr.text, boilerplate)
        cleaned = conservative_ocr_corrections(cleaned)
        cleaned = strip_garbage_chars(cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if not cleaned.split():
            result.pages_skipped += 1
            continue
        chunks.append(f"<!-- Page {pr.page_num} ({pr.method}, score={pr.score.score:.0f}) -->\n{cleaned}")
        result.pages_extracted += 1
        if pr.method == "text":
            result.pages_via_text += 1
        elif pr.method == "ocr":
            result.pages_via_ocr += 1
        scores.append(pr.score.score)

    result.markdown = "\n\n".join(chunks)
    result.word_count = sum(
        score_text_quality(c).word_count for c in chunks if "skipped" not in c[:80]
    )
    result.avg_page_score = sum(scores) / len(scores) if scores else 0

    if result.avg_page_score < 40 and result.pages_extracted > 0:
        result.warnings_.append(
            f"Average page quality score {result.avg_page_score:.0f}/100 — review output"
        )
    if result.pages_skipped > result.pages_extracted:
        result.warnings_.append(
            f"More pages skipped ({result.pages_skipped}) than extracted "
            f"({result.pages_extracted})"
        )

    return result


# ─── EPUB ────────────────────────────────────────────────────────────────────

def extract_epub(epub_path: Path) -> BookResult:
    result = BookResult(path=epub_path)
    if not HAS_EPUB:
        result.issues.append("ebooklib not installed")
        return result
    try:
        book = epub.read_epub(str(epub_path), options={"ignore_ncx": True})
    except Exception as e:
        result.issues.append(f"EPUB read failed: {e}")
        return result

    chunks = []
    chapter_num = 0
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        chapter_num += 1
        try:
            content = item.get_content().decode("utf-8", errors="replace")
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["script", "style", "nav"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            text = "\n".join(lines)
            text = normalize_encoding(text)
            sc = score_text_quality(text)
            if sc.word_count < 10:
                result.pages_skipped += 1
                continue
            chunks.append(f"<!-- Chapter {chapter_num} -->\n{text.strip()}")
            result.pages_extracted += 1
        except Exception:
            result.pages_skipped += 1

    result.markdown = "\n\n".join(chunks)
    result.word_count = sum(score_text_quality(c).word_count for c in chunks)
    result.pages_via_text = result.pages_extracted  # all text for EPUBs
    return result


# ─── I/O ──────────────────────────────────────────────────────────────────────

def slugify(filename: str) -> str:
    name = Path(filename).stem.lower()
    name = re.sub(r"[\(\)\[\]{}]", "", name)
    name = re.sub(r"[^a-z0-9\s\-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"-+", "-", name)
    return name + ".md"


def write_markdown(book: BookResult, out_path: Path) -> None:
    header = [
        f"# {book.path.stem}",
        "",
        f"> Source: `{book.path.name}`",
        f"> Pages extracted: {book.pages_extracted} "
        f"(text: {book.pages_via_text}, OCR: {book.pages_via_ocr}) "
        f"| Pages skipped: {book.pages_skipped}",
        f"> Words: {book.word_count:,} "
        f"| Avg page quality score: {book.avg_page_score:.0f}/100",
    ]
    if book.warnings_:
        header.append("> Warnings: " + "; ".join(book.warnings_))
    header.extend(["", "---", "", ""])
    out_path.write_text("\n".join(header) + book.markdown, encoding="utf-8")


# ─── BATCH ORCHESTRATION ─────────────────────────────────────────────────────

def process_one_book(
    source_path: Path,
    out_dir: Path,
    force_ocr: bool,
    skip_existing: bool,
) -> dict:
    """Worker function, safe for ProcessPoolExecutor."""
    slug = slugify(source_path.name)
    out_path = out_dir / slug

    if skip_existing and out_path.exists() and out_path.stat().st_size > 1000:
        return {
            "file": source_path.name,
            "out": slug,
            "skipped_existing": True,
            "word_count": 0,
        }

    if source_path.suffix.lower() == ".epub":
        book = extract_epub(source_path)
    else:
        book = extract_pdf(source_path, force_ocr=force_ocr, verbose=False)

    if book.pages_extracted == 0:
        return {
            "file": source_path.name,
            "out": None,
            "issues": book.issues,
            "word_count": 0,
        }

    write_markdown(book, out_path)
    return {
        "file": source_path.name,
        "out": slug,
        "pages_extracted": book.pages_extracted,
        "pages_skipped": book.pages_skipped,
        "pages_via_text": book.pages_via_text,
        "pages_via_ocr": book.pages_via_ocr,
        "word_count": book.word_count,
        "avg_score": book.avg_page_score,
        "warnings": book.warnings_,
        "issues": book.issues,
        "ocr_errors": book.ocr_errors,
        "reason": book.reason,
    }


def extract_all(
    source_folder: Path,
    out_dir: Path,
    force_ocr: bool,
    skip_existing: bool,
    workers: int,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    supported = [".pdf", ".epub"]
    files = sorted(
        f for f in source_folder.iterdir()
        if f.suffix.lower() in supported
    )
    if not files:
        print(f"No .pdf or .epub files found in {source_folder}", file=sys.stderr)
        return

    print(f"📚 Found {len(files)} books in {source_folder}", file=sys.stderr)
    print(f"📁 Output: {out_dir}", file=sys.stderr)
    print(f"⚙️  Workers: {workers} | Force OCR: {force_ocr} | Skip existing: {skip_existing}",
          file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    results = []
    if workers > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as exe:
            futures = {
                exe.submit(
                    process_one_book, f, out_dir, force_ocr, skip_existing
                ): f
                for f in files
            }
            for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
                f = futures[fut]
                try:
                    r = fut.result()
                except Exception as e:
                    r = {"file": f.name, "issues": [f"worker crashed: {e}"],
                         "word_count": 0}
                results.append(r)
                _log_result(i, len(files), r)
    else:
        for i, f in enumerate(files, 1):
            r = process_one_book(f, out_dir, force_ocr, skip_existing)
            results.append(r)
            _log_result(i, len(files), r)

    write_qc_report(out_dir / "_QC_REPORT.md", results)


def _log_result(i: int, total: int, r: dict) -> None:
    if r.get("skipped_existing"):
        tag = "⏭  exists"
    elif r.get("issues"):
        tag = "❌ " + "; ".join(r["issues"])[:60]
    else:
        score = r.get("avg_score", 0)
        grade = "✅" if score >= 60 else ("⚠️ " if score >= 40 else "❌")
        tag = (
            f"{grade} pages={r.get('pages_extracted', 0)}"
            f" (text={r.get('pages_via_text', 0)}, ocr={r.get('pages_via_ocr', 0)})"
            f" words={r.get('word_count', 0):,}"
            f" score={score:.0f}"
        )
    print(f"[{i}/{total}] {r['file'][:48]:<48} {tag}", file=sys.stderr)


def write_qc_report(path: Path, results: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Extraction QC Report\n\n")
        f.write(f"_Generated by extract_v4 · {len(results)} books_\n\n")
        f.write("| # | File | Pages | Text | OCR | Skipped | Words | Score | Grade | Notes |\n")
        f.write("|---|------|-------|------|-----|---------|-------|-------|-------|-------|\n")
        for n, r in enumerate(results, 1):
            if r.get("skipped_existing"):
                f.write(f"| {n} | {r['file'][:40]} | — | — | — | — | — | — | ⏭ exists | skipped |\n")
                continue
            if r.get("issues"):
                f.write(f"| {n} | {r['file'][:40]} | 0 | 0 | 0 | 0 | 0 | 0 | ❌ FAILED | "
                        f"{'; '.join(r['issues'])[:60]} |\n")
                continue
            score = r.get("avg_score", 0)
            grade = "✅ GOOD" if score >= 60 else ("⚠️ REVIEW" if score >= 40 else "❌ POOR")
            note_parts = list(r.get("warnings", []))
            if r.get("reason"):
                note_parts.append(r["reason"])
            if r.get("ocr_errors"):
                note_parts.append(f"{len(r['ocr_errors'])} OCR errors")
            notes = "; ".join(note_parts) or "—"
            f.write(
                f"| {n} | {r['file'][:40]} | {r.get('pages_extracted', 0)} | "
                f"{r.get('pages_via_text', 0)} | {r.get('pages_via_ocr', 0)} | "
                f"{r.get('pages_skipped', 0)} | {r.get('word_count', 0):,} | "
                f"{score:.0f} | {grade} | {notes} |\n"
            )

        # Per-book OCR-error detail appendix (only if any book had errors)
        books_with_ocr_errors = [r for r in results if r.get("ocr_errors")]
        if books_with_ocr_errors:
            f.write("\n---\n\n## OCR exceptions (detail)\n\n")
            for r in books_with_ocr_errors:
                f.write(f"### {r['file']}\n\n")
                for err in r["ocr_errors"][:50]:
                    f.write(f"- {err}\n")
                if len(r["ocr_errors"]) > 50:
                    f.write(f"- … and {len(r['ocr_errors']) - 50} more\n")
                f.write("\n")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main() -> int:
    if MISSING:
        print("Missing required libraries:", file=sys.stderr)
        for m in MISSING:
            print(f"  - {m}", file=sys.stderr)
        print("\nInstall with:", file=sys.stderr)
        print("  brew install tesseract poppler", file=sys.stderr)
        print("  pip3 install pymupdf pdfplumber pytesseract pdf2image "
              "Pillow opencv-python ebooklib beautifulsoup4 "
              "--break-system-packages", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(
        description="LLM-training-grade book extractor.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", type=Path, nargs="?",
                        help="Folder containing PDFs/EPUBs")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Output folder (default: <source>/extracted)")
    parser.add_argument("--force-ocr", action="store_true",
                        help="Run OCR even on pages with clean embedded text "
                             "(kept anyway if OCR scores higher)")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip books whose output already exists (default on)")
    parser.add_argument("--no-skip-existing", dest="skip_existing",
                        action="store_false")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                        help="Parallel worker processes (default: CPU count - 1)")
    args = parser.parse_args()

    if args.source is None:
        src = input("Path to book folder: ").strip().strip("'\"")
        args.source = Path(src).expanduser()
    else:
        args.source = args.source.expanduser()

    if not args.source.is_dir():
        print(f"Not a directory: {args.source}", file=sys.stderr)
        return 1

    out_dir = args.output or (args.source / "extracted")
    extract_all(
        args.source, out_dir,
        force_ocr=args.force_ocr,
        skip_existing=args.skip_existing,
        workers=args.workers,
    )
    print(f"\n✓ Done. QC report: {out_dir / '_QC_REPORT.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
