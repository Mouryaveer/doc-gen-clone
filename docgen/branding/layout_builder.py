# coding: utf-8
"""
layout_builder.py — Layout computation and XeLaTeX preamble generation
                    for the Turn2Law custom branding pipeline.

Public API
----------
compute_layout(header_h_px, footer_h_px, dpi)  -> LayoutParameters
generate_preamble(profile, layout, dest_path)  -> str  (absolute .tex path)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path, PurePosixPath
from typing import Optional

from .exceptions import BrandProfileError
from .models import BrandProfile, LayoutParameters

logger = logging.getLogger(__name__)

# T2L asset names that must NEVER appear in a custom preamble
_T2L_ASSET_NAMES = (
    "header_decoration",
    "footer_decoration",
    "sample_asset_0_xref_36",
    "watermark_logo_n",
    "sample_asset_1_xref_47",
    "sample_asset_2_xref_36",
    "sample_asset_3_xref_63",
)


# ---------------------------------------------------------------------------
# Layout computation
# ---------------------------------------------------------------------------

def compute_layout(
    header_h_px: Optional[int],
    footer_h_px: Optional[int],
    dpi: float,
) -> LayoutParameters:
    """
    Convert pixel image heights to PDF points and compute page margins.

    Formulae
    --------
    pt = px * 72 / dpi
    top_margin    = max(74, header_pt + 16)
    bottom_margin = max(66, footer_pt + 16)
    left  = 42 pt  (fixed)
    right = 32 pt  (fixed)
    """
    if dpi <= 0:
        raise ValueError(f"DPI must be positive, got {dpi}")

    header_pt = (header_h_px * 72.0 / dpi) if header_h_px else 0.0
    footer_pt = (footer_h_px * 72.0 / dpi) if footer_h_px else 0.0
    top       = max(74.0, header_pt + 16.0)
    bottom    = max(66.0, footer_pt + 16.0)

    layout = LayoutParameters(
        top_margin_pt    = top,
        bottom_margin_pt = bottom,
        left_margin_pt   = 42.0,
        right_margin_pt  = 32.0,
        header_height_pt = header_pt,
        footer_height_pt = footer_pt,
    )
    logger.debug(
        "Layout computed: top=%.1fpt bottom=%.1fpt header_h=%.1fpt footer_h=%.1fpt",
        top, bottom, header_pt, footer_pt,
    )
    return layout


# ---------------------------------------------------------------------------
# Preamble generation
# ---------------------------------------------------------------------------

def generate_preamble(
    profile:   BrandProfile,
    layout:    LayoutParameters,
    dest_path: str,
) -> str:
    """
    Generate a XeLaTeX preamble .tex file for the given custom brand profile.

    Image paths are written as absolute POSIX-style paths (forward slashes)
    so XeLaTeX can read them cross-platform.

    Returns the absolute path to the written .tex file.
    Raises BrandProfileError if any T2L asset name leaks into the output.
    """

    def _posix(p: Optional[str]) -> str:
        """Convert an OS path to a forward-slash POSIX string, or ''."""
        if not p:
            return ""
        return Path(p).as_posix()

    header_posix    = _posix(profile.header_image_path)
    footer_posix    = _posix(profile.footer_image_path)
    watermark_posix = _posix(profile.watermark_image_path)
    logo_posix      = _posix(profile.logo_image_path)

    # Build TikZ background nodes
    bg_nodes: list[str] = []

    if header_posix:
        bg_nodes.append(
            f"    % Header\n"
            f"    \\node[anchor=north west, inner sep=0pt] at\n"
            f"      ($(current page.north west)+(0pt,0pt)$)\n"
            f"      {{\\includegraphics[width=595.5pt,height={layout.header_height_pt:.4f}pt,"
            f"keepaspectratio=false]{{{header_posix}}}}};"
        )

    if footer_posix and layout.footer_height_pt > 0:
        bg_nodes.append(
            f"    % Footer\n"
            f"    \\node[anchor=south west, inner sep=0pt] at\n"
            f"      ($(current page.south west)+(0pt,0pt)$)\n"
            f"      {{\\includegraphics[width=595.5pt,height={layout.footer_height_pt:.4f}pt,"
            f"keepaspectratio=false]{{{footer_posix}}}}};"
        )

    if watermark_posix:
        bg_nodes.append(
            f"    % Watermark (10% opacity, centred)\n"
            f"    \\node[anchor=center, inner sep=0pt, opacity=0.10] at\n"
            f"      ($(current page.south west)+(297.75pt,421.13pt)$)\n"
            f"      {{\\includegraphics[width=300pt,keepaspectratio=true]{{{watermark_posix}}}}};"
        )

    if logo_posix:
        bg_nodes.append(
            f"    % Logo (top-left)\n"
            f"    \\node[anchor=north west, inner sep=0pt] at\n"
            f"      ($(current page.north west)+(28.49pt,-32.59pt)$)\n"
            f"      {{\\includegraphics[width=200pt,height=53.5pt,"
            f"keepaspectratio=true]{{{logo_posix}}}}};"
        )

    bg_block = "\n".join(bg_nodes) if bg_nodes else "    % No background assets"

    tex = (
        "% =============================================================================\n"
        f"%  brand_preamble.tex — Custom branding for profile: {profile.profile_id}\n"
        "%  Generated by Turn2Law Branding Engine. DO NOT EDIT MANUALLY.\n"
        "%\n"
        "%  PLACEHOLDERS replaced by latex_writer.py at render time:\n"
        "%    FONTS_DIR_PLACEHOLDER   -> absolute path to docgen/fonts/\n"
        "%    IMAGES_DIR_PLACEHOLDER  -> absolute path to docgen/images/\n"
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
        "\\usepackage[\n"
        "  paperwidth=595.5pt,\n"
        "  paperheight=842.25pt,\n"
        f"  top={layout.top_margin_pt:.4f}pt,\n"
        f"  bottom={layout.bottom_margin_pt:.4f}pt,\n"
        f"  left={layout.left_margin_pt:.4f}pt,\n"
        f"  right={layout.right_margin_pt:.4f}pt,\n"
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
        "% Custom brand background — repeats on every page\n"
        "\\AddToShipoutPictureBG{%\n"
        "  \\begin{tikzpicture}[remember picture, overlay, x=1pt, y=1pt]\n"
        f"{bg_block}\n"
        "  \\end{tikzpicture}%\n"
        "}\n"
    )

    # Write file
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as fh:
        fh.write(tex)

    # Safety check: T2L asset names must NOT appear in output
    for bad in _T2L_ASSET_NAMES:
        if bad in tex:
            try:
                os.remove(dest_path)
            except OSError:
                pass
            raise BrandProfileError(
                f"turn2law_asset_leaked_into_custom_preamble: "
                f"Found forbidden string {bad!r} in generated preamble "
                f"for profile {profile.profile_id!r}. "
                "This is a bug in generate_preamble()."
            )

    logger.info("Custom preamble written: %s", dest_path)
    return os.path.abspath(dest_path)
