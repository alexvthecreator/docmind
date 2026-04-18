#!/usr/bin/env python3
"""
make_icon.py — Generate DocMind.icns.

Creates all the size variants macOS expects and packages them into a
.icns file using the iconutil command that ships with macOS.

USAGE:
    python3 make_icon.py
"""

import shutil
import subprocess
from pathlib import Path


def draw_icon_png(size: int, out_path: Path):
    """Draw the DocMind logo at the given size."""
    from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        QApplication([])

    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    # Espresso rounded background
    p.setBrush(QBrush(QColor("#1a1613")))
    p.setPen(Qt.NoPen)
    radius = int(size * 0.22)
    p.drawRoundedRect(0, 0, size, size, radius, radius)

    cream = QColor("#f0e6d6")
    gold = QColor("#c9a876")
    gold_dim = QColor("#a78858")
    gold_mid = QColor("#b8966a")

    cx = size // 2
    cy = int(size * 0.62)
    page_w = int(size * 0.40)
    page_h = int(size * 0.46)
    corner = max(4, int(size * 0.024))

    # Back page — leans left
    p.save()
    p.translate(cx, cy)
    p.rotate(-9)
    p.setBrush(QBrush(gold_dim))
    p.setPen(QPen(gold_dim, max(2, size // 160)))
    p.drawRoundedRect(-page_w // 2, -page_h // 2, page_w, page_h,
                      corner, corner)
    p.restore()

    # Middle page — leans right
    p.save()
    p.translate(cx + int(size * 0.035), cy - int(size * 0.016))
    p.rotate(6)
    p.setBrush(QBrush(gold_mid))
    p.setPen(QPen(gold_mid, max(2, size // 160)))
    p.drawRoundedRect(-page_w // 2, -page_h // 2, page_w, page_h,
                      corner, corner)
    p.restore()

    # Front page — upright, brightest, with text lines
    p.save()
    p.translate(cx - int(size * 0.02), cy + int(size * 0.023))
    p.setBrush(QBrush(gold))
    p.setPen(QPen(gold, max(2, size // 160)))
    p.drawRoundedRect(-page_w // 2, -page_h // 2, page_w, page_h,
                      corner, corner)

    # Text lines
    line_thickness = max(2, int(size * 0.014))
    p.setPen(QPen(QColor("#1a1613"), line_thickness,
                  Qt.SolidLine, Qt.RoundCap))
    line_y = -page_h // 2 + int(size * 0.075)
    line_spacing = int(size * 0.06)
    line_offsets_left = int(size * 0.055)
    line_variations = [
        int(size * 0.058), int(size * 0.127), int(size * 0.058),
        int(size * 0.166), int(size * 0.088),
    ]
    for right_trim in line_variations:
        p.drawLine(
            -page_w // 2 + line_offsets_left, line_y,
             page_w // 2 - right_trim, line_y,
        )
        line_y += line_spacing
    p.restore()

    # Cream orb above
    p.setBrush(QBrush(cream))
    p.setPen(Qt.NoPen)
    orb_r = int(size * 0.055)
    orb_cy = int(size * 0.195)
    p.drawEllipse(cx - orb_r, orb_cy - orb_r, orb_r * 2, orb_r * 2)

    # Three rays from orb down to the stack
    ray_thickness = max(2, int(size * 0.012))
    p.setPen(QPen(cream, ray_thickness, Qt.SolidLine, Qt.RoundCap))
    ray_start_y = orb_cy + orb_r + int(size * 0.016)
    ray_end_y = int(size * 0.35)
    offset = int(size * 0.08)
    for dx in (-offset, 0, offset):
        p.drawLine(cx + dx, ray_start_y, cx + dx // 2, ray_end_y)

    p.end()
    pix.save(str(out_path), "PNG")


def build_icns():
    iconset = Path("DocMind.iconset")
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir()

    sizes = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]

    print("Drawing icon at all required sizes...")
    for size, name in sizes:
        draw_icon_png(size, iconset / name)
        print(f"  {name} ({size}×{size})")

    print("\nPackaging .icns via iconutil...")
    result = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", "DocMind.icns"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"iconutil failed: {result.stderr}")
        print("NOTE: iconutil only exists on macOS.")
        return

    print("\n✓ DocMind.icns created")
    shutil.rmtree(iconset)


if __name__ == "__main__":
    build_icns()
