#!/usr/bin/env python3
"""
DocMind — feed your LLM the documents that matter.

A minimal desktop app for turning PDFs into clean Markdown ready for
LLM reference material. Drag a folder in, click Extract, watch progress,
done.

Built on PySide6 (Qt for Python). The extraction engine lives in
extract_v4 and is imported directly.
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path
from dataclasses import dataclass

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QMimeData
from PySide6.QtGui import (
    QFont, QPalette, QColor, QDragEnterEvent, QDropEvent,
    QIcon, QPixmap, QPainter, QPen, QBrush,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QTextEdit, QFileDialog,
    QFrame, QSizePolicy, QScrollArea, QCheckBox,
)

# Import the extraction engine. extract_v4.py must sit next to this file.
try:
    import extract_v4
except ImportError:
    print("ERROR: extract_v4.py must be in the same folder as DocMind.py")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS
# ═══════════════════════════════════════════════════════════════════════════

COLOR_BG = "#1a1613"
COLOR_SURFACE = "#24201d"
COLOR_BORDER = "#3a332d"
COLOR_ACCENT = "#c9a876"
COLOR_ACCENT_HOVER = "#d9b98a"
COLOR_TEXT = "#f0e6d6"
COLOR_TEXT_DIM = "#8a7f70"
COLOR_SUCCESS = "#8fb573"
COLOR_WARNING = "#d4a04a"
COLOR_ERROR = "#c97560"
COLOR_DROP_ACTIVE = "#3a2f22"


# ═══════════════════════════════════════════════════════════════════════════
# WORKER THREAD
# ═══════════════════════════════════════════════════════════════════════════

SUPPORTED_EXTENSIONS = (".pdf", ".epub")
_STOP_SENTINEL = "__docmind_stopped__"


def _format_eta(seconds: float) -> str:
    """Compact ETA string: '42s', '3m 12s', '1h 5m', '…' if unknown."""
    if seconds is None or seconds < 0 or seconds != seconds:
        return "…"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    return f"{s // 3600}h {(s % 3600) // 60}m"


def collect_files(sources: list[Path]) -> list[Path]:
    """Flatten a mix of files and folders into a sorted list of PDFs/EPUBs.

    Folders are expanded one level deep (non-recursive) — matching the
    original folder-drop behaviour. Duplicate paths are de-duplicated.
    """
    seen: set[Path] = set()
    out: list[Path] = []
    for s in sources:
        s = Path(s)
        if s.is_file() and s.suffix.lower() in SUPPORTED_EXTENSIONS:
            if s not in seen:
                seen.add(s)
                out.append(s)
        elif s.is_dir():
            for child in sorted(s.iterdir()):
                if (child.is_file()
                        and child.suffix.lower() in SUPPORTED_EXTENSIONS
                        and child not in seen):
                    seen.add(child)
                    out.append(child)
    return out


class ExtractionWorker(QThread):
    """Background extraction runner with per-page progress and EPUB support.

    Signals
    -------
    file_started(filename)
        About to process this file.
    file_progress(filename, pages_done, total_pages, eta_str)
        Per-page tick during PDF extraction. EPUB emits one 0/1 then 1/1 tick.
    file_finished(filename, pages_extracted, total_pages, word_count,
                  avg_score, grade, reason)
        File completed (or failed). `reason` is the human-readable note
        from BookResult.reason; empty string for failures.
    progress(overall_pct, status_text)
        Overall run progress across all files.
    finished_all(summary_text)
        All files finished.
    error(message)
        Fatal error — run aborted.
    """

    file_started = Signal(str)
    file_progress = Signal(str, int, int, str)
    file_finished = Signal(str, int, int, int, float, str, str)
    progress = Signal(int, str)
    finished_all = Signal(str)
    error = Signal(str)

    def __init__(self, files: list[Path], output_folder: Path,
                 force_ocr: bool = False):
        super().__init__()
        self.files = list(files)
        self.output_folder = output_folder
        self.force_ocr = force_ocr
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        try:
            self.output_folder.mkdir(parents=True, exist_ok=True)

            if not self.files:
                self.error.emit("No PDF or EPUB files to process.")
                return

            self.progress.emit(
                0,
                f"Found {len(self.files)} "
                f"file{'s' if len(self.files) != 1 else ''}",
            )

            results = []
            run_start = time.monotonic()

            for i, f in enumerate(self.files):
                if self._stopped:
                    self.progress.emit(0, "Stopped.")
                    return

                self.file_started.emit(f.name)
                overall_pct = int(100 * i / len(self.files))
                self.progress.emit(
                    overall_pct,
                    f"[{i + 1}/{len(self.files)}] {f.name[:60]}",
                )

                try:
                    result = self._process_one(f)

                    if result.pages_extracted > 0:
                        out_path = self.output_folder / extract_v4.slugify(
                            f.name
                        )
                        extract_v4.write_markdown(result, out_path)

                    total = result.pages_extracted + result.pages_skipped
                    grade = self._score_to_grade(
                        result.avg_page_score, result.pages_extracted
                    )
                    self.file_finished.emit(
                        f.name,
                        result.pages_extracted,
                        total,
                        result.word_count,
                        result.avg_page_score,
                        grade,
                        result.reason or "",
                    )
                    results.append({
                        "file": f.name,
                        "out": extract_v4.slugify(f.name),
                        "pages_extracted": result.pages_extracted,
                        "pages_skipped": result.pages_skipped,
                        "pages_via_text": result.pages_via_text,
                        "pages_via_ocr": result.pages_via_ocr,
                        "word_count": result.word_count,
                        "avg_score": result.avg_page_score,
                        "warnings": result.warnings_,
                        "issues": result.issues,
                        "ocr_errors": list(result.ocr_errors),
                        "reason": result.reason,
                    })

                except _StoppedError:
                    self.progress.emit(0, "Stopped.")
                    return
                except Exception as e:
                    reason = f"Failed: {type(e).__name__}: {e}"
                    self.file_finished.emit(
                        f.name, 0, 0, 0, 0.0, "FAILED", reason
                    )
                    results.append({
                        "file": f.name,
                        "issues": [str(e)],
                        "word_count": 0,
                    })

            self.progress.emit(100, "Finishing up...")
            extract_v4.write_qc_report(
                self.output_folder / "_QC_REPORT.md", results
            )

            elapsed = time.monotonic() - run_start
            summary = self._build_summary(results, elapsed)
            self.finished_all.emit(summary)

        except Exception as e:
            self.error.emit(f"{e}\n\n{traceback.format_exc()}")

    def _process_one(self, f: Path):
        """Dispatch to PDF or EPUB extraction with per-page callback."""
        suffix = f.suffix.lower()
        if suffix == ".epub":
            # EPUB has no page-level granularity; two ticks are enough
            # for the progress bar to show motion.
            self.file_progress.emit(f.name, 0, 1, "…")
            result = extract_v4.extract_epub(f)
            self.file_progress.emit(f.name, 1, 1, "0s")
            return result
        if suffix == ".pdf":
            # Per-file ETA state, closed-over by the callback
            eta_state = {"t_start": None, "smoothed_rate": None}

            def cb(pages_done: int, total_pages: int):
                if self._stopped:
                    raise _StoppedError()
                now = time.monotonic()
                if eta_state["t_start"] is None:
                    eta_state["t_start"] = now
                    eta_str = "…"
                else:
                    elapsed = max(0.001, now - eta_state["t_start"])
                    raw_rate = pages_done / elapsed
                    prev = eta_state["smoothed_rate"]
                    smoothed = (
                        raw_rate
                        if prev is None
                        else 0.25 * raw_rate + 0.75 * prev
                    )
                    eta_state["smoothed_rate"] = smoothed
                    remaining = max(0, total_pages - pages_done)
                    eta_seconds = (
                        remaining / smoothed if smoothed > 0 else 0
                    )
                    eta_str = _format_eta(eta_seconds)
                self.file_progress.emit(
                    f.name, pages_done, total_pages, eta_str
                )

            return extract_v4.extract_pdf(
                f,
                force_ocr=self.force_ocr,
                verbose=False,
                progress_callback=cb,
            )
        raise ValueError(f"Unsupported file type: {suffix}")

    @staticmethod
    def _score_to_grade(score: float, pages: int) -> str:
        if pages == 0:
            return "FAILED"
        if score >= 60:
            return "GOOD"
        if score >= 40:
            return "REVIEW"
        return "POOR"

    @staticmethod
    def _build_summary(results: list, elapsed: float) -> str:
        good = sum(
            1 for r in results
            if r.get("avg_score", 0) >= 60 and not r.get("issues")
        )
        review = sum(
            1 for r in results
            if 40 <= r.get("avg_score", 0) < 60 and not r.get("issues")
        )
        poor = sum(
            1 for r in results
            if r.get("avg_score", 0) < 40 or r.get("issues")
        )
        total_words = sum(r.get("word_count", 0) for r in results)
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        return (
            f"Done in {mins}m {secs}s.\n\n"
            f"✓ {good} good   ⚠ {review} review   ✗ {poor} failed\n"
            f"{total_words:,} words extracted total."
        )


class _StoppedError(Exception):
    """Raised by the page callback to unwind out of extract_pdf."""


# ═══════════════════════════════════════════════════════════════════════════
# DROP ZONE
# ═══════════════════════════════════════════════════════════════════════════

class DropZone(QLabel):
    folder_dropped = Signal(Path)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(280)
        self.setWordWrap(True)
        self._set_idle()

    def _set_idle(self):
        self.setText(
            "📄\n\n"
            "Drop a folder of PDFs here\n\n"
            "or click to browse\n\n"
            "\n"
            "PDF files only"
        )
        self.setStyleSheet(self._style(active=False))

    def _set_active(self):
        self.setText("📥\n\nRelease to load these PDFs")
        self.setStyleSheet(self._style(active=True))

    def _set_loaded(self, folder: Path, count: int):
        plural = "s" if count != 1 else ""
        self.setText(
            f"✓\n\n"
            f"{folder.name}\n"
            f"{count} PDF{plural} ready\n\n"
            f"Click to choose a different folder"
        )
        self.setStyleSheet(self._style(active=False, loaded=True))

    def _style(self, active=False, loaded=False):
        if active:
            border = COLOR_ACCENT
            bg = COLOR_DROP_ACTIVE
        elif loaded:
            border = COLOR_ACCENT
            bg = COLOR_SURFACE
        else:
            border = COLOR_BORDER
            bg = COLOR_SURFACE
        return f"""
            QLabel {{
                background-color: {bg};
                border: 2px dashed {border};
                border-radius: 16px;
                color: {COLOR_TEXT};
                font-size: 16px;
                padding: 40px;
            }}
        """

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile():
                path = Path(urls[0].toLocalFile())
                if path.is_dir():
                    event.acceptProposedAction()
                    self._set_active()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_idle()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            if path.is_dir():
                self.folder_dropped.emit(path)
                event.acceptProposedAction()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            folder = QFileDialog.getExistingDirectory(
                self, "Choose a folder of PDFs", str(Path.home())
            )
            if folder:
                self.folder_dropped.emit(Path(folder))


# ═══════════════════════════════════════════════════════════════════════════
# FILE ROW
# ═══════════════════════════════════════════════════════════════════════════

class FileRow(QFrame):
    """One row per file in the progress list.

    Layout (vertical):
        top row   : [icon]  [filename] ............... [stats]
        bar row   :         [==thin progress bar==] [ETA]
        bottom    :         [italic reason / error message]
    """

    STATUS_WAITING = "waiting"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self.status = self.STATUS_WAITING

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
            }}
            QFrame > QLabel,
            QFrame > QProgressBar {{ border: none; background: transparent; }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(10)

        self.icon_label = QLabel("○")
        self.icon_label.setFixedWidth(24)
        self.icon_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: 18px; border: none;"
        )

        self.name_label = QLabel(filename)
        self.name_label.setStyleSheet(
            f"color: {COLOR_TEXT}; font-size: 13px; border: none;"
        )
        self.name_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: 12px; border: none;"
        )
        self.stats_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top.addWidget(self.icon_label)
        top.addWidget(self.name_label)
        top.addWidget(self.stats_label)
        outer.addLayout(top)

        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(34, 0, 0, 0)
        bar_row.setSpacing(8)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setRange(0, 1000)  # finer resolution than 0–100
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: 11px; border: none;"
        )
        self.eta_label.setFixedWidth(90)
        self.eta_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.eta_label.setVisible(False)
        bar_row.addWidget(self.progress_bar, stretch=1)
        bar_row.addWidget(self.eta_label)
        outer.addLayout(bar_row)

        self.reason_label = QLabel("")
        self.reason_label.setWordWrap(True)
        self.reason_label.setContentsMargins(34, 0, 0, 0)
        self.reason_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: 11px; "
            "font-style: italic; border: none;"
        )
        self.reason_label.setVisible(False)
        outer.addWidget(self.reason_label)

    def set_running(self):
        self.status = self.STATUS_RUNNING
        self.icon_label.setText("◐")
        self.icon_label.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-size: 18px; border: none;"
        )
        self.stats_label.setText("starting...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.eta_label.setText("…")
        self.eta_label.setVisible(True)
        self.reason_label.setVisible(False)

    def set_progress(self, pages_done: int, total_pages: int, eta_str: str):
        if self.status != self.STATUS_RUNNING:
            self.set_running()
        if total_pages > 0:
            self.progress_bar.setValue(
                int(1000 * pages_done / total_pages)
            )
        self.stats_label.setText(
            f"{pages_done}/{total_pages} pages"
        )
        self.eta_label.setText(f"ETA {eta_str}")

    def set_done(self, pages: int, total_pages: int, words: int,
                 score: float, grade: str, reason: str = ""):
        if grade == "FAILED":
            self.status = self.STATUS_FAILED
            self.icon_label.setText("✗")
            self.icon_label.setStyleSheet(
                f"color: {COLOR_ERROR}; font-size: 18px; border: none;"
            )
            self.progress_bar.setVisible(False)
            self.eta_label.setVisible(False)
            self.stats_label.setText("failed")
            if reason:
                self.reason_label.setText(reason)
                self.reason_label.setStyleSheet(
                    f"color: {COLOR_ERROR}; font-size: 11px; "
                    "font-style: italic; border: none;"
                )
                self.reason_label.setVisible(True)
            return

        self.status = self.STATUS_DONE
        self.icon_label.setText("●")
        if grade == "GOOD":
            color = COLOR_SUCCESS
        elif grade == "REVIEW":
            color = COLOR_WARNING
        else:
            color = COLOR_ERROR
        self.icon_label.setStyleSheet(
            f"color: {color}; font-size: 18px; border: none;"
        )
        self.progress_bar.setValue(1000)
        self.eta_label.setText("done")
        self.stats_label.setText(
            f"{pages}/{total_pages} pages  ·  "
            f"{words:,} words  ·  {score:.0f}/100"
        )
        if reason:
            self.reason_label.setText(reason)
            self.reason_label.setStyleSheet(
                f"color: {COLOR_TEXT_DIM}; font-size: 11px; "
                "font-style: italic; border: none;"
            )
            self.reason_label.setVisible(True)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════

class DocMindWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.source_folder: Path | None = None
        self.worker: ExtractionWorker | None = None
        self.file_rows: dict[str, FileRow] = {}

        self.setWindowTitle("DocMind")
        self.setMinimumSize(720, 620)
        self.resize(800, 720)
        self._apply_theme()
        self._build_ui()

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {COLOR_BG}; }}
            QWidget {{
                background-color: {COLOR_BG};
                color: {COLOR_TEXT};
                font-family: -apple-system, "SF Pro Text", "Helvetica Neue";
            }}
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: {COLOR_BG};
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
                font-size: 15px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {COLOR_ACCENT_HOVER}; }}
            QPushButton:disabled {{
                background-color: {COLOR_BORDER};
                color: {COLOR_TEXT_DIM};
            }}
            QPushButton#secondary {{
                background-color: transparent;
                color: {COLOR_TEXT_DIM};
                border: 1px solid {COLOR_BORDER};
            }}
            QPushButton#secondary:hover {{
                color: {COLOR_TEXT};
                border-color: {COLOR_ACCENT};
            }}
            QProgressBar {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
                height: 8px;
                text-align: center;
                color: transparent;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_ACCENT};
                border-radius: 7px;
            }}
            QScrollArea {{ background-color: transparent; border: none; }}
            QScrollBar:vertical {{
                background: {COLOR_BG};
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {COLOR_BORDER};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QCheckBox {{
                color: {COLOR_TEXT_DIM};
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                background: {COLOR_SURFACE};
            }}
            QCheckBox::indicator:checked {{
                background: {COLOR_ACCENT};
                border-color: {COLOR_ACCENT};
            }}
        """)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("DocMind")
        title.setFont(QFont("-apple-system", 28, QFont.Bold))
        title.setStyleSheet(f"color: {COLOR_TEXT};")
        subtitle = QLabel("Feed your LLM the documents that matter")
        subtitle.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 14px;")
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        self.drop_zone = DropZone()
        self.drop_zone.folder_dropped.connect(self._on_folder_selected)
        layout.addWidget(self.drop_zone)

        options_layout = QHBoxLayout()
        self.force_ocr_check = QCheckBox(
            "Force OCR on every page (slower, for poor-quality scans)"
        )
        options_layout.addWidget(self.force_ocr_check)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)
        self.extract_btn = QPushButton("Extract")
        self.extract_btn.setEnabled(False)
        self.extract_btn.clicked.connect(self._on_extract_clicked)
        self.extract_btn.setMinimumHeight(44)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("secondary")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.stop_btn.setMinimumHeight(44)
        action_layout.addWidget(self.extract_btn, stretch=1)
        action_layout.addWidget(self.stop_btn)
        layout.addLayout(action_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: 12px;"
        )
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        self.file_list_scroll = QScrollArea()
        self.file_list_scroll.setWidgetResizable(True)
        self.file_list_scroll.setVisible(False)
        self.file_list_widget = QWidget()
        self.file_list_layout = QVBoxLayout(self.file_list_widget)
        self.file_list_layout.setSpacing(6)
        self.file_list_layout.setContentsMargins(0, 0, 0, 0)
        self.file_list_layout.addStretch()
        self.file_list_scroll.setWidget(self.file_list_widget)
        layout.addWidget(self.file_list_scroll, stretch=1)

        self.finished_label = QLabel("")
        self.finished_label.setWordWrap(True)
        self.finished_label.setAlignment(Qt.AlignCenter)
        self.finished_label.setStyleSheet(f"""
            background-color: {COLOR_SURFACE};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 20px;
            color: {COLOR_TEXT};
            font-size: 14px;
        """)
        self.finished_label.setVisible(False)
        layout.addWidget(self.finished_label)

        self.reveal_btn = QPushButton("Show in Finder")
        self.reveal_btn.setObjectName("secondary")
        self.reveal_btn.clicked.connect(self._reveal_output)
        self.reveal_btn.setVisible(False)
        layout.addWidget(self.reveal_btn)

    def _on_folder_selected(self, folder: Path):
        self.source_folder = folder
        count = sum(
            1 for f in folder.iterdir()
            if f.suffix.lower() == ".pdf"
        )
        self.drop_zone._set_loaded(folder, count)
        self.extract_btn.setEnabled(count > 0)
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        self.file_list_scroll.setVisible(False)
        self.finished_label.setVisible(False)
        self.reveal_btn.setVisible(False)
        self._clear_file_list()

    def _clear_file_list(self):
        for row in self.file_rows.values():
            row.deleteLater()
        self.file_rows.clear()

    def _on_extract_clicked(self):
        if not self.source_folder:
            return
        output_folder = self.source_folder / "extracted"

        files = collect_files([self.source_folder])
        if not files:
            self.status_label.setText(
                "No PDF or EPUB files found in that folder."
            )
            self.status_label.setVisible(True)
            return

        self._clear_file_list()
        for f in files:
            row = FileRow(f.name)
            self.file_rows[f.name] = row
            self.file_list_layout.insertWidget(
                self.file_list_layout.count() - 1, row
            )

        self.extract_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Starting...")
        self.file_list_scroll.setVisible(True)
        self.finished_label.setVisible(False)
        self.reveal_btn.setVisible(False)
        self.force_ocr_check.setEnabled(False)

        self.worker = ExtractionWorker(
            files,
            output_folder,
            force_ocr=self.force_ocr_check.isChecked(),
        )
        self.worker.file_started.connect(self._on_file_started)
        self.worker.file_progress.connect(self._on_file_progress)
        self.worker.file_finished.connect(self._on_file_finished)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_all.connect(self._on_finished_all)
        self.worker.error.connect(self._on_error)
        self.output_folder = output_folder
        self.worker.start()

    def _on_stop_clicked(self):
        if self.worker:
            self.worker.stop()
            self.status_label.setText("Stopping after current file...")

    def _on_file_started(self, filename: str):
        row = self.file_rows.get(filename)
        if row:
            row.set_running()

    def _on_file_progress(self, filename: str, pages_done: int,
                          total_pages: int, eta_str: str):
        row = self.file_rows.get(filename)
        if row:
            row.set_progress(pages_done, total_pages, eta_str)

    def _on_file_finished(self, filename: str, pages: int, total: int,
                          words: int, score: float, grade: str,
                          reason: str):
        row = self.file_rows.get(filename)
        if row:
            row.set_done(pages, total, words, score, grade, reason)

    def _on_progress(self, pct: int, text: str):
        self.progress_bar.setValue(pct)
        self.status_label.setText(text)

    def _on_finished_all(self, summary: str):
        self.extract_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.force_ocr_check.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_label.setVisible(False)
        self.finished_label.setText(summary)
        self.finished_label.setVisible(True)
        self.reveal_btn.setVisible(True)

    def _on_error(self, msg: str):
        self.extract_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self.force_ocr_check.setEnabled(True)
        self.status_label.setText(f"Error: {msg.splitlines()[0]}")

    def _reveal_output(self):
        if hasattr(self, "output_folder") and self.output_folder.exists():
            import subprocess
            subprocess.run(["open", str(self.output_folder)])


# ═══════════════════════════════════════════════════════════════════════════
# ICON — stack of document pages with a cream orb above, feeding down
# ═══════════════════════════════════════════════════════════════════════════

def make_icon() -> QIcon:
    """Programmatically draw a document-stack-and-orb icon."""
    size = 512
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    # Rounded espresso background
    p.setBrush(QBrush(QColor(COLOR_BG)))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, size, size, 110, 110)

    cream = QColor("#f0e6d6")
    gold = QColor(COLOR_ACCENT)
    gold_dim = QColor("#a78858")
    gold_mid = QColor("#b8966a")

    cx = size // 2
    cy = int(size * 0.62)
    page_w = int(size * 0.40)
    page_h = int(size * 0.46)

    # Back page (leans left, darker)
    p.save()
    p.translate(cx, cy)
    p.rotate(-9)
    p.setBrush(QBrush(gold_dim))
    p.setPen(QPen(gold_dim, 4))
    p.drawRoundedRect(-page_w // 2, -page_h // 2, page_w, page_h, 12, 12)
    p.restore()

    # Middle page (leans right, medium)
    p.save()
    p.translate(cx + 18, cy - 8)
    p.rotate(6)
    p.setBrush(QBrush(gold_mid))
    p.setPen(QPen(gold_mid, 4))
    p.drawRoundedRect(-page_w // 2, -page_h // 2, page_w, page_h, 12, 12)
    p.restore()

    # Front page (upright, brightest, with "text" lines)
    p.save()
    p.translate(cx - 10, cy + 12)
    p.setBrush(QBrush(gold))
    p.setPen(QPen(gold, 4))
    p.drawRoundedRect(-page_w // 2, -page_h // 2, page_w, page_h, 12, 12)
    # Lines of "text" in the dark BG color
    p.setPen(QPen(QColor(COLOR_BG), 7, Qt.SolidLine, Qt.RoundCap))
    line_y = -page_h // 2 + 38
    line_offsets = [
        (28, 30), (28, 65), (28, 30), (28, 85), (28, 45),
    ]
    for left_margin, right_margin in line_offsets:
        p.drawLine(
            -page_w // 2 + left_margin, line_y,
             page_w // 2 - right_margin, line_y,
        )
        line_y += 30
    p.restore()

    # Cream "mind" orb above
    p.setBrush(QBrush(cream))
    p.setPen(Qt.NoPen)
    orb_r = int(size * 0.055)
    orb_cy = int(size * 0.195)
    p.drawEllipse(cx - orb_r, orb_cy - orb_r, orb_r * 2, orb_r * 2)

    # Three rays from orb down toward the stack
    p.setPen(QPen(cream, 6, Qt.SolidLine, Qt.RoundCap))
    ray_start_y = orb_cy + orb_r + 8
    ray_end_y = int(size * 0.35)
    for dx in (-int(size * 0.08), 0, int(size * 0.08)):
        p.drawLine(cx + dx, ray_start_y, cx + dx // 2, ray_end_y)

    p.end()
    return QIcon(pix)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DocMind")
    app.setOrganizationName("DocMind")
    icon = make_icon()
    app.setWindowIcon(icon)
    win = DocMindWindow()
    win.setWindowIcon(icon)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
