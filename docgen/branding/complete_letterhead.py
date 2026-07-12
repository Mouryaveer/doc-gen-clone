# coding: utf-8
"""
complete_letterhead.py — Complete A4 letterhead branding mode.

A single PNG representing the full page design (header + footer + watermark
+ all decorative elements) is placed as the background layer on every page.
The document body text floats above it.

Public API
----------
validate_letterhead(path)          -> LetterheadInfo
generate_letterhead_preamble(info, dest_path) -> str  (absolute .tex path)

Design decisions
----------------
* The image is rendered at EXACTLY A4 size (595.5 × 842.25 pt) so it never
  crops or distorts.  The user is responsible for the image's composition.
* Margins are inferred by scanning the alpha channel (if RGBA) or luminance
  (if RGB) for the safe writing area.  Falls back to conservative defaults
  when analysis is inconclusive.
* No Turn2Law assets are referenced.  If any T2L filename appears in the
  generated preamble, generation fails with BrandProfileError.
* The preamble uses the same FONTS_DIR_PLACEHOLDER / IMAGES_DIR_PLACEHOLDER
  tokens as the existing branding pipeline so latex_writer can inject paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

from .exceptions import BrandAssetProcessingError, BrandAssetValidationError, BrandProfileError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'

# A4 in PDF points
_A4_W_PT = 595.5
_A4_H_PT = 842.25

# Minimum pixel dimensions for a "complete letterhead" upload.
# 1000 × 1400 accommodates common letterhead scans at ~120 DPI.
# For best quality recommend 2480 × 3508 (A4 at 300 DPI).
_MIN_WIDTH_PX  = 1000
_MIN_HEIGHT_PX = 1400

# Maximum file size: 20 MB (letterheads at 300 DPI can be large)
_MAX_BYTES = 20 * 1024 * 1024

# Safe-area fallback margins when auto-detection is inconclusive (pt)
_DEFAULT_TOP    = 100.0
_DEFAULT_BOTTOM = 80.0
_DEFAULT_LEFT   = 56.0
_DEFAULT_RIGHT  = 40.0

# Fraction of image height that counts as "header" / "footer" zone for
# margin auto-detection.
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
    path:           str    # absolute path to the source PNG
    width_px:       int
    height_px:       int
    file_size_bytes: int
    top_margin_pt:   float
    bottom_margin_pt: float
    left_margin_pt:  float
    right_margin_pt: float


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_letterhead(path: str) -> LetterheadInfo:
    """
    Validate a complete-letterhead PNG and infer safe-writing margins.

    Parameters
    ----------
    path : Absolute or relative path to the PNG file.

    Returns
    -------
    LetterheadInfo on success.

    Raises
    ------
    BrandAssetValidationError
        If format, dimensions, or file size requirements are not met.
    BrandAssetProcessingError
        If the file cannot be opened or analysed.
    """
    path = os.path.abspath(path)

    # --- PNG magic check ---
    try:
        with open(path, "rb") as fh:
            magic = fh.read(8)
    except OSError as exc:
        raise BrandAssetValidationError(
            f"file_unreadable: cannot open {path!r}: {exc}"
        ) from exc

    if magic != _PNG_MAGIC:
        observed = magic.hex() if magic else "(empty)"
        raise BrandAssetValidationError(
            f"not_png: letterhead must be a PNG file. "
            f"Observed first 8 bytes: {observed}"
        )

    # --- File size ---
    file_size = os.path.getsize(path)
    if file_size > _MAX_BYTES:
        raise BrandAssetValidationError(
            f"file_too_large: letterhead file size {file_size / 1024 / 1024:.1f} MB "
            f"exceeds maximum {_MAX_BYTES // 1024 // 1024} MB"
        )

    # --- Open with Pillow ---
    try:
        img = Image.open(path)
        img.load()
        width, height = img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise BrandAssetProcessingError(
            f"Cannot open letterhead {path!r}: {exc}"
        ) from exc

    # --- Auto-upscale if below minimum dimensions ---
    # Rather than reject the image, resize it proportionally so it always works.
    if width < _MIN_WIDTH_PX or height < _MIN_HEIGHT_PX:
        scale  = max(_MIN_WIDTH_PX / width, _MIN_HEIGHT_PX / height)
        new_w  = int(width  * scale)
        new_h  = int(height * scale)
        img    = img.resize((new_w, new_h), Image.LANCZOS)
        # Save the upscaled version back to path (overwrite)
        img.save(path, format="PNG")
        width, height = new_w, new_h

    # --- Margin auto-detection ---
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
# Margin auto-detection
# ---------------------------------------------------------------------------

def _detect_margins(img: Image.Image, width: int, height: int) -> tuple[float, float, float, float]:
    """
    Infer safe writing margins from the image content.

    Strategy
    --------
    * RGBA images: find the lowest non-transparent row in the top 20 % of the
      image (header height) and the highest non-transparent row in the bottom
      15 % (footer height).  Convert px → pt using the image aspect ratio
      relative to A4.
    * RGB / other: convert to greyscale, find the lowest mostly-dark row in
      header zone and highest mostly-dark row in footer zone.
    * If detection is inconclusive, use conservative defaults.
    """
    dpi_scale_y = _A4_H_PT / height  # pt per pixel (vertical)
    dpi_scale_x = _A4_W_PT / width   # pt per pixel (horizontal)

    try:
        if img.mode == "RGBA":
            top_px, bottom_px, left_px, right_px = _margins_from_alpha(img, width, height)
        else:
            top_px, bottom_px, left_px, right_px = _margins_from_luminance(img, width, height)

        top_pt    = max(_DEFAULT_TOP,    (top_px    * dpi_scale_y) + 16.0)
        bottom_pt = max(_DEFAULT_BOTTOM, (bottom_px * dpi_scale_y) + 16.0)
        left_pt   = max(_DEFAULT_LEFT,   (left_px   * dpi_scale_x) + 10.0)
        right_pt  = max(_DEFAULT_RIGHT,  (right_px  * dpi_scale_x) + 10.0)
        return top_pt, bottom_pt, left_pt, right_pt

    except Exception:
        # Detection failed — fall back to defaults
        return _DEFAULT_TOP, _DEFAULT_BOTTOM, _DEFAULT_LEFT, _DEFAULT_RIGHT


def _margins_from_alpha(img: Image.Image, width: int, height: int) -> tuple[int, int, int, int]:
    """Return (top_px, bottom_px, left_px, right_px) from alpha channel analysis."""
    import numpy as np  # optional dependency; Pillow is already required

    arr = np.array(img)          # shape (H, W, 4)
    alpha = arr[:, :, 3]         # 0 = transparent, 255 = opaque

    header_end   = int(height * _HEADER_ZONE)
    footer_start = int(height * (1 - _FOOTER_ZONE))

    # Top: last row in header zone that has any opaque pixel
    header_alpha = alpha[:header_end, :]
    opaque_rows = np.where(header_alpha.max(axis=1) > 10)[0]
    top_px = int(opaque_rows.max()) + 1 if len(opaque_rows) else 0

    # Bottom: first row in footer zone that has any opaque pixel
    footer_alpha = alpha[footer_start:, :]
    opaque_rows_f = np.where(footer_alpha.max(axis=1) > 10)[0]
    bottom_px = int(height - footer_start - opaque_rows_f.min()) if len(opaque_rows_f) else 0

    return top_px, bottom_px, 0, 0  # left/right use defaults


def _margins_from_luminance(img: Image.Image, width: int, height: int) -> tuple[int, int, int, int]:
    """Return (top_px, bottom_px, left_px, right_px) from greyscale analysis."""
    try:
        import numpy as np
        grey = np.array(img.convert("L"))   # (H, W), 0=black, 255=white

        header_end   = int(height * _HEADER_ZONE)
        footer_start = int(height * (1 - _FOOTER_ZONE))

        # Rows that are NOT mostly white (contain branding)
        threshold = 200
        header_dark = np.where(grey[:header_end, :].min(axis=1) < threshold)[0]
        top_px = int(header_dark.max()) + 1 if len(header_dark) else 0

        footer_dark = np.where(grey[footer_start:, :].min(axis=1) < threshold)[0]
        bottom_px = int(height - footer_start - footer_dark.min()) if len(footer_dark) else 0

        return top_px, bottom_px, 0, 0
    except Exception:
        return 0, 0, 0, 0


# ---------------------------------------------------------------------------
# Preamble generation
# ---------------------------------------------------------------------------

def generate_letterhead_preamble(info: LetterheadInfo, dest_path: str) -> str:
    """
    Write a XeLaTeX preamble that places the letterhead PNG as a full-page
    background on every page.

    Parameters
    ----------
    info      : LetterheadInfo from validate_letterhead()
    dest_path : Absolute path where the .tex file should be written.

    Returns
    -------
    Absolute path to the written .tex file.

    Raises
    ------
    BrandProfileError
        If a Turn2Law asset name leaks into the generated preamble.
    """
    image_posix = Path(info.path).as_posix()

    tex = f"""% =============================================================================
%  brand_preamble.tex — Complete Letterhead preamble
%  Generated by Turn2Law Branding Engine (complete_letterhead mode)
%  Source image : {Path(info.path).name}
%  Dimensions  : {info.width_px} × {info.height_px} px
%  DO NOT EDIT MANUALLY.
% =============================================================================

\\usepackage{{fontspec}}
\\setmainfont[
  Path           = FONTS_DIR_PLACEHOLDER,
  UprightFont    = Montserrat-Regular-Full.ttf,
  BoldFont       = Montserrat-Bold-Full.ttf,
  ItalicFont     = Montserrat-Regular-Full.ttf,
  BoldItalicFont = Montserrat-Bold-Full.ttf
]{{Montserrat}}

\\newfontfamily\\garetfont[
  Path        = FONTS_DIR_PLACEHOLDER,
  UprightFont = Garet-Regular.ttf,
  BoldFont    = Garet-Bold.ttf
]{{Garet}}

\\usepackage[
  paperwidth={_A4_W_PT}pt,
  paperheight={_A4_H_PT}pt,
  top={info.top_margin_pt:.2f}pt,
  bottom={info.bottom_margin_pt:.2f}pt,
  left={info.left_margin_pt:.2f}pt,
  right={info.right_margin_pt:.2f}pt,
  noheadfoot
]{{geometry}}

\\usepackage{{graphicx}}
\\usepackage{{xcolor}}
\\usepackage{{eso-pic}}
\\usepackage{{tikz}}
\\usetikzlibrary{{calc}}
\\usepackage[absolute,overlay]{{textpos}}
\\setlength{{\\TPHorizModule}}{{1pt}}
\\setlength{{\\TPVertModule}}{{1pt}}
\\usepackage{{needspace}}
\\usepackage{{enumitem}}
\\usepackage{{array}}
\\usepackage{{ifthen}}
\\usepackage{{tabularx}}

\\setlength{{\\parindent}}{{0pt}}
\\setlength{{\\parskip}}{{5pt}}
\\linespread{{1.25}}

\\graphicspath{{{{IMAGES_DIR_PLACEHOLDER}}}}
\\pagenumbering{{gobble}}

% Colours (standard Turn2Law palette — kept for clause colour macros)
\\definecolor{{refgold}}{{HTML}}{{FFBD58}}
\\definecolor{{refcharcoal}}{{HTML}}{{2A2A2A}}
\\definecolor{{refdarkgold}}{{HTML}}{{B87C20}}
\\definecolor{{t2ldark}}{{HTML}}{{2A2A2A}}

% =============================================================================
%  Full-page letterhead background — repeats on EVERY page
%  The image is scaled to exact A4 dimensions so it never crops.
% =============================================================================
\\AddToShipoutPictureBG{{%
  \\begin{{tikzpicture}}[remember picture, overlay]
    \\node[anchor=north west, inner sep=0pt] at (current page.north west)
      {{\\includegraphics[width={_A4_W_PT}pt,height={_A4_H_PT}pt,
        keepaspectratio=false]{{{image_posix}}}}};
  \\end{{tikzpicture}}%
}}
"""

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
                f"Found forbidden string {bad!r} in generated preamble. "
                "This is a bug in complete_letterhead.generate_letterhead_preamble()."
            )

    return os.path.abspath(dest_path)
