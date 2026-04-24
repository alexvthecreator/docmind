#!/usr/bin/env python3
"""
make_dmg_bg.py — Generate the DocMind DMG window background.

Produces two PNGs in docs/:
  - dmg_background.png      — 520×340 (non-Retina)
  - dmg_background@2x.png   — 1040×680 (Retina)

The Retina variant is what modern Macs actually display; create-dmg
picks the right one automatically via the @2x filename convention.

Layout (matches create_dmg.sh icon positions):
  - Icons at x=130 (DocMind) and x=390 (Applications), y=170
  - Gold arrow between them pointing DocMind → Applications
  - "Drag DocMind into Applications" caption below the arrow
  - Soft cream-to-beige gradient background in the DocMind palette

Run:
    python3 make_dmg_bg.py
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


# DocMind design tokens (see DocMind.py)
CREAM_LIGHT = (243, 233, 217)   # #f3e9d9
CREAM_DARKER = (235, 216, 190)  # #ebd8be
GOLD = (201, 168, 118)          # #c9a876 — COLOR_ACCENT
GOLD_DIM = (167, 136, 88)       # #a78858
ESPRESSO = (26, 22, 19)         # #1a1613 — COLOR_BG
TEXT_DIM = (138, 127, 112)      # #8a7f70 — COLOR_TEXT_DIM

# Window & icon coords (must match create_dmg.sh)
BASE_WIDTH = 520
BASE_HEIGHT = 340
ICON_LEFT_X = 130
ICON_RIGHT_X = 390
ICON_Y = 170
ICON_HALF = 48  # icon size 96 → half = 48

# Fonts worth trying on macOS in preference order
MAC_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _load_font(size_px: int) -> ImageFont.ImageFont:
    """Try a chain of system fonts; fall back to PIL's default bitmap."""
    for path in MAC_FONT_PATHS:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size_px)
            except Exception:
                continue
    # Pillow 10+ accepts size in load_default; earlier versions give a
    # fixed tiny bitmap font (which is still legible, just plain).
    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:
        return ImageFont.load_default()


def draw_vertical_gradient(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    top_rgb: tuple[int, int, int],
    bottom_rgb: tuple[int, int, int],
) -> None:
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top_rgb[0] * (1 - t) + bottom_rgb[0] * t)
        g = int(top_rgb[1] * (1 - t) + bottom_rgb[1] * t)
        b = int(top_rgb[2] * (1 - t) + bottom_rgb[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_drag_arrow(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    scale: int,
) -> None:
    """Gold curved arrow with a dashed motion trail.

    Arcs gently upward through a control point above the midpoint — the
    visual metaphor is a hand sweeping the DocMind icon across the window
    toward the Applications folder. The first ~15% of the path is drawn as
    dashes (motion trail); the rest is a solid shaft capped by a triangular
    arrowhead.
    """
    s = scale
    shaft_thickness = max(3, 4 * s)

    # Quadratic-bezier control point: mid-x, lifted upward by arc_height
    mid_x = (x0 + x1) / 2
    arc_height = 26 * s
    cx, cy = mid_x, (y0 + y1) / 2 - arc_height

    # Sample the curve
    N = 56
    pts: list[tuple[float, float]] = []
    for i in range(N + 1):
        t = i / N
        mt = 1 - t
        bx = mt * mt * x0 + 2 * mt * t * cx + t * t * x1
        by = mt * mt * y0 + 2 * mt * t * cy + t * t * y1
        pts.append((bx, by))

    # First ~18% of the path: dashed motion trail (skip every other segment)
    dash_end = max(2, int(N * 0.18))

    for i in range(N):
        if i < dash_end and i % 2 == 1:
            continue  # gap in the dashed portion
        draw.line([pts[i], pts[i + 1]], fill=GOLD, width=shaft_thickness)

    # Arrowhead — use direction from a point a few steps back for smoothness
    p_tip = pts[-1]
    p_back = pts[-5]
    dx = p_tip[0] - p_back[0]
    dy = p_tip[1] - p_back[1]
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / length, dy / length
    # Perpendicular unit vector
    px_, py_ = -uy, ux

    head_len = 16 * s
    head_half_w = 9 * s
    base_x = p_tip[0] - ux * head_len
    base_y = p_tip[1] - uy * head_len
    left = (base_x + px_ * head_half_w, base_y + py_ * head_half_w)
    right = (base_x - px_ * head_half_w, base_y - py_ * head_half_w)
    draw.polygon([p_tip, left, right], fill=GOLD)


def render(scale: int) -> Image.Image:
    """Render the background at the given scale (1 for 1x, 2 for Retina)."""
    s = scale
    W = BASE_WIDTH * s
    H = BASE_HEIGHT * s

    img = Image.new("RGB", (W, H), CREAM_LIGHT)
    draw = ImageDraw.Draw(img)

    # Soft cream-to-beige gradient
    draw_vertical_gradient(draw, W, H, CREAM_LIGHT, CREAM_DARKER)

    # ── Drag-motion arrow between icon slots ────────────────────────────
    # Curved path from DocMind toward the Applications folder, arcing
    # gently upward. A short dashed trail at the start conveys drag motion;
    # a solid triangular arrowhead lands at the destination.
    arrow_y = ICON_Y * s
    arrow_start_x = (ICON_LEFT_X + ICON_HALF + 14) * s
    arrow_end_x = (ICON_RIGHT_X - ICON_HALF - 14) * s
    _draw_drag_arrow(draw, arrow_start_x, arrow_y, arrow_end_x, arrow_y, s)

    # ── Caption under the arrow ─────────────────────────────────────────
    caption = "Drag DocMind into Applications"
    caption_font = _load_font(13 * s)
    try:
        bbox = draw.textbbox((0, 0), caption, font=caption_font)
        text_w = bbox[2] - bbox[0]
    except Exception:
        text_w, _ = draw.textsize(caption, font=caption_font)
    draw.text(
        ((W - text_w) // 2, arrow_y + 42 * s),
        caption,
        fill=TEXT_DIM,
        font=caption_font,
    )

    # ── "DocMind" wordmark at the top ──────────────────────────────────
    title_font = _load_font(18 * s)
    title = "DocMind"
    try:
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = bbox[2] - bbox[0]
    except Exception:
        title_w, _ = draw.textsize(title, font=title_font)
    draw.text(
        ((W - title_w) // 2, 36 * s),
        title,
        fill=ESPRESSO,
        font=title_font,
    )

    subtitle = "Feed your LLM the documents that matter"
    subtitle_font = _load_font(10 * s)
    try:
        bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        sub_w = bbox[2] - bbox[0]
    except Exception:
        sub_w, _ = draw.textsize(subtitle, font=subtitle_font)
    draw.text(
        ((W - sub_w) // 2, 62 * s),
        subtitle,
        fill=TEXT_DIM,
        font=subtitle_font,
    )

    return img


def main() -> int:
    docs = Path(__file__).resolve().parent / "docs"
    docs.mkdir(exist_ok=True)

    img_1x = render(scale=1)
    img_1x.save(docs / "dmg_background.png", "PNG")
    print(f"  ✓ {docs / 'dmg_background.png'} ({BASE_WIDTH}×{BASE_HEIGHT})")

    img_2x = render(scale=2)
    img_2x.save(docs / "dmg_background@2x.png", "PNG")
    print(
        f"  ✓ {docs / 'dmg_background@2x.png'} "
        f"({BASE_WIDTH * 2}×{BASE_HEIGHT * 2})"
    )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
