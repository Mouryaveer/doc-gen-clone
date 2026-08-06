# coding: utf-8
"""
complete_letterhead.py — Complete A4 letterhead branding mode.

A single PNG representing the full page design (header + footer + watermark
+ all decorative elements) is placed as the background layer on every page.
The document body text floats above it with auto-detected safe margins.

Public API
----------
validate_letterhead(path)                     -> LetterheadInfo
generate_letterhead_preamble(info, dest_path) -> str  (absolute .tex path)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .exceptions import (
    BrandAssetProcessingError,
    BrandAssetValidationError,
    BrandProfileError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'

# A4 in PDF points (matches all templates)
_A4_W_PT = 595.5
_A4_H_PT = 842.25

# Minimum pixel dimensions for a complete-letterhead PNG.
# 1000×1400 covers scans at ~120 DPI; recommend 2480×3508 (300 DPI).
_MIN_WIDTH_PX  = 1000
_MIN_HEIGHT_PX = 1400

# Maximum file size: 20 MB
_MAX_BYTES = 20 * 1024 * 1024

# Conservative default margins (pt) used when auto-detection is inconclusive
_DEFAULT_TOP    = 100.0
_DEFAULT_BOTTOM =  80.0
_DEFAULT_LEFT   =  56.0
_DEFAULT_RIGHT  =  40.0

# Fraction of image height treated as header / footer zone
_HEADER_ZONE = 0.20   # top 20 %
_FOOTER_ZONE = 0.15   # bottom 15 %

# T2L asset names that must never appear in a letterhead preamble
_T2L_ASSET_NAMES = (
    "header_decoration",
    "footer_decoration",
    "sample_asset_0_xref_36",
    "watermark_logo_n",
)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class LetterheadInfo:
    """Validated letterhead metadata returned by validate_letterhead()."""
    path:             str
    width_px:         int
    height_px:        int
    file_size_bytes:  int
    top_margin_pt:    float
    bottom_margin_pt: float
    left_margin_pt:   float
    right_margin_pt:  float


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_letterhead(path: str) -> LetterheadInfo:
    """
    Validate a complete-letterhead PNG and infer safe writing margins.

    Returns LetterheadInfo on success.
    Raises BrandAssetValidationError or BrandAssetProcessingError on failure.
    """
    path = os.path.abspath(path)

    # PNG magic check
    try:
        with open(path, "rb") as fh:
            magic = fh.read(8)
    except OSError as exc:
        raise BrandAssetValidationError(
            f"file_unreadable: cannot open {path!r}: {exc}"
        ) from exc

    if magic != _PNG_MAGIC:
        raise BrandAssetValidationError(
            f"not_png: letterhead must be a PNG file. "
            f"Observed first 8 bytes: {(magic or b'').hex()}"
        )

    # File size
    file_size = os.path.getsize(path)
    if file_size > _MAX_BYTES:
        raise BrandAssetValidationError(
            f"file_too_large: {file_size / 1024 / 1024:.1f} MB exceeds "
            f"maximum {_MAX_BYTES // 1024 // 1024} MB"
        )

    # Open with Pillow
    try:
        img = Image.open(path)
        img.load()
        width, height = img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise BrandAssetProcessingError(
            f"Cannot open letterhead {path!r}: {exc}"
        ) from exc

    # Auto-upscale if below minimum dimensions (preserves aspect ratio)
    if width < _MIN_WIDTH_PX or height < _MIN_HEIGHT_PX:
        scale  = max(_MIN_WIDTH_PX / width, _MIN_HEIGHT_PX / height)
        new_w  = round(width  * scale)
        new_h  = round(height * scale)
        logger.info(
            "Letterhead auto-upscaled: %dx%d → %dx%d px", width, height, new_w, new_h
        )
        img    = img.resize((new_w, new_h), Image.LANCZOS)
        img.save(path, format="PNG")
        width, height = new_w, new_h

    top, bottom, left, right = _detect_margins(img, width, height)

    return LetterheadInfo(
        path             = path,
        width_px         = width,
        height_px        = height,
        file_size_bytes  = file_size,
        top_margin_pt    = top,
        bottom_margin_pt = bottom,
        left_margin_pt   = left,
        right_margin_pt  = right,
    )


# ---------------------------------------------------------------------------
# Margin auto-detection  (pure-Pillow, no numpy dependency)
# ---------------------------------------------------------------------------

def _detect_margins(
    img: Image.Image, width: int, height: int
) -> tuple[float, float, float, float]:
    """Detect safe writing margins from the image content."""
    dpi_y = _A4_H_PT / height
    dpi_x = _A4_W_PT / width

    try:
        top_px, bottom_px = _scan_header_footer(img, width, height)
        top_pt    = max(_DEFAULT_TOP,    top_px    * dpi_y + 16.0)
        bottom_pt = max(_DEFAULT_BOTTOM, bottom_px * dpi_y + 16.0)
        return top_pt, bottom_pt, _DEFAULT_LEFT, _DEFAULT_RIGHT
    except Exception as exc:
        logger.warning("Margin detection failed (%s) — using defaults.", exc)
        return _DEFAULT_TOP, _DEFAULT_BOTTOM, _DEFAULT_LEFT, _DEFAULT_RIGHT


def _scan_header_footer(
    img: Image.Image, width: int, height: int
) -> tuple[int, int]:
    """
    Return (header_height_px, footer_height_px) by scanning pixel rows.

    Strategy
    --------
    * For RGBA: a row is "content" if any pixel has alpha > 10.
    * For RGB / other: convert to greyscale; a row is "content" if any
      pixel is darker than 200 (i.e. not blank white).
    * Header height = last content row inside the top HEADER_ZONE.
    * Footer height = number of content rows inside the bottom FOOTER_ZONE.
    """
    header_end   = int(height * _HEADER_ZONE)
    footer_start = int(height * (1.0 - _FOOTER_ZONE))

    if img.mode == "RGBA":
        r, g, b, alpha = img.split()
        data = alpha
        threshold = 10

        def row_has_content(row_idx: int, channel: Image.Image) -> bool:
            row_data = channel.crop((0, row_idx, width, row_idx + 1)).getdata()
            return any(v > threshold for v in row_data)

    else:
        data      = img.convert("L")
        threshold = 200

        def row_has_content(row_idx: int, channel: Image.Image) -> bool:  # type: ignore[misc]
            row_data = channel.crop((0, row_idx, width, row_idx + 1)).getdata()
            return any(v < threshold for v in row_data)

    # Header: find the lowest content row in the top zone
    header_px = 0
    for row in range(header_end - 1, -1, -1):
        if row_has_content(row, data):
            header_px = row + 1
            break

    # Footer: find the highest content row in the bottom zone
    footer_px = 0
    for row in range(footer_start, height):
        if row_has_content(row, data):
            footer_px = height - row
            break

    return header_px, footer_px


# ---------------------------------------------------------------------------
# Preamble generation
# ---------------------------------------------------------------------------

def generate_letterhead_preamble(info: LetterheadInfo, dest_path: str) -> str:
    """
    Write a XeLaTeX preamble that places the letterhead PNG as a full-page
    background (595.5 × 842.25 pt) on every page.

    Returns the absolute path to the written .tex file.
    Raises BrandProfileError if a T2L asset name leaks into the output.
    """
    image_posix = Path(info.path).as_posix()

    tex = (
        "% =============================================================================\n"
        "%  brand_preamble.tex — Complete Letterhead mode\n"
        f"%  Generated by Turn2Law Branding Engine\n"
        f"%  Source : {Path(info.path).name}  ({info.width_px}×{info.height_px} px)\n"
        "%  DO NOT EDIT MANUALLY.\n"
        "% =============================================================================\n"
        "\n"
        "\\usepackage{fontspec}\n"
        "\\setmainfont[\n"
        "  Path           = FONTS_DIR_PLACEHOLDER,\n"
        "  UprightFont    = Montserrat-Regular-Full.ttf,\n"
        "  BoldFont       = Montserrat-Bold-Full.ttf,\n"
        "  ItalicFont     = Montserrat-Regular-Full.ttf,\n"
        "  BoldItalicFont = Montserrat-Bold-Full.ttf\n"
        "]{Montserrat}\n"
        "\n"
        "\\newfontfamily\\garetfont[\n"
        "  Path        = FONTS_DIR_PLACEHOLDER,\n"
        "  UprightFont = Garet-Regular.ttf,\n"
        "  BoldFont    = Garet-Bold.ttf\n"
        "]{Garet}\n"
        "\n"
        f"\\usepackage[\n"
        f"  paperwidth={_A4_W_PT}pt,\n"
        f"  paperheight={_A4_H_PT}pt,\n"
        f"  top={info.top_margin_pt:.2f}pt,\n"
        f"  bottom={info.bottom_margin_pt:.2f}pt,\n"
        f"  left={info.left_margin_pt:.2f}pt,\n"
        f"  right={info.right_margin_pt:.2f}pt,\n"
        "  noheadfoot\n"
        "]{geometry}\n"
        "\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{xcolor}\n"
        "\\usepackage{eso-pic}\n"
        "\\usepackage{tikz}\n"
        "\\usetikzlibrary{calc}\n"
        "\\usepackage[absolute,overlay]{textpos}\n"
        "\\setlength{\\TPHorizModule}{1pt}\n"
        "\\setlength{\\TPVertModule}{1pt}\n"
        "\\usepackage{needspace}\n"
        "\\usepackage{enumitem}\n"
        "\\usepackage{array}\n"
        "\\usepackage{ifthen}\n"
        "\\usepackage{tabularx}\n"
        "\n"
        "\\setlength{\\parindent}{0pt}\n"
        "\\setlength{\\parskip}{5pt}\n"
        "\\linespread{1.25}\n"
        "\n"
        "\\graphicspath{{IMAGES_DIR_PLACEHOLDER}}\n"
        "\\pagenumbering{gobble}\n"
        "\n"
        "\\definecolor{refgold}{HTML}{FFBD58}\n"
        "\\definecolor{refcharcoal}{HTML}{2A2A2A}\n"
        "\\definecolor{refdarkgold}{HTML}{B87C20}\n"
        "\\definecolor{t2ldark}{HTML}{2A2A2A}\n"
        "\n"
        "% Full-page letterhead background — repeats on every page\n"
        "\\AddToShipoutPictureBG{%\n"
        "  \\begin{tikzpicture}[remember picture, overlay]\n"
        "    \\node[anchor=north west, inner sep=0pt] at (current page.north west)\n"
        f"      {{\\includegraphics[width={_A4_W_PT}pt,height={_A4_H_PT}pt,\n"
        f"        keepaspectratio=false]{{{image_posix}}}}};\n"
        "  \\end{tikzpicture}%\n"
        "}\n"
    )

    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as fh:
        fh.write(tex)

    # Safety: T2L asset names must never appear in a custom preamble
    for bad in _T2L_ASSET_NAMES:
        if bad in tex:
            try:
                os.remove(dest_path)
            except OSError:
                pass
            raise BrandProfileError(
                f"t2l_asset_leaked_into_letterhead_preamble: "
                f"Found forbidden string {bad!r} in generated preamble."
            )

    logger.info("Letterhead preamble written: %s", dest_path)
    return os.path.abspath(dest_path)
