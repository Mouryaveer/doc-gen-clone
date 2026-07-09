"""
typography.py — Font and text-sizing constants for Turn2Law documents.

pdflatex does not support fontspec/system fonts, so we map to the best
available LaTeX equivalents.  The official document uses a sans-serif
face that is visually close to Helvetica Neue / Arial.
helvet (PSNFSS) is the standard pdflatex approximation.

If you migrate to XeLaTeX, swap FONT_MAIN to 'Arial' or 'Helvetica Neue'
and enable fontspec in the template.
"""

# ---------------------------------------------------------------------------
# Body font
# ---------------------------------------------------------------------------
FONT_PACKAGE    = "helvet"          # LaTeX package to load
FONT_FAMILY_CMD = r"\sfdefault"     # \renewcommand{\familydefault}{\sfdefault}

# ---------------------------------------------------------------------------
# Line spacing
# ---------------------------------------------------------------------------
LINE_SPREAD = 1.13      # global \linespread — reference doc has relaxed leading

# ---------------------------------------------------------------------------
# Font sizes  (LaTeX size command name → used in template macros)
# ---------------------------------------------------------------------------
FONT_SIZE_TITLE_PT   = 22   # "Onboarding Letter – Turn2Law"
FONT_SIZE_TITLE_BS   = 26   # baseline skip for title
FONT_SIZE_BODY_PT    = 12   # standard body text (matches \large at 12pt base)
FONT_SIZE_DATELINE   = "large"   # Date / Emp ID line
FONT_SIZE_NAME       = "LARGE"   # Employee name headline
FONT_SIZE_SECTION    = "LARGE"   # "Position Details" heading
FONT_SIZE_FOOTER     = "small"   # Footer email line

# ---------------------------------------------------------------------------
# Paragraph / list settings
# ---------------------------------------------------------------------------
BULLET_LEFT_MARGIN_EM  = 1.2   # \leftmargin for itemize
BULLET_ITEM_SEP_EM     = 0.18  # \itemsep
BULLET_TOP_SEP_EM      = 0.2   # \topsep
