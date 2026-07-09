"""
layout.py — Shared layout constants for the Turn2Law document generation system.

All dimensions are in millimetres unless noted. LaTeX macros consuming
these values must convert accordingly (e.g. \dimexpr <value>mm\relax).

These constants are written into every .tex file at render time by
latex_writer.py, so templates reference symbolic names rather than
magic numbers.
"""

# ---------------------------------------------------------------------------
# Page geometry  (A4: 210 × 297 mm)
# ---------------------------------------------------------------------------
PAGE_WIDTH_MM   = 210.0
PAGE_HEIGHT_MM  = 297.0

MARGIN_TOP_MM    = 28.0   # ~2.8 cm — leaves room for top bar + logo
MARGIN_BOTTOM_MM = 25.0   # ~2.5 cm — leaves room for footer bar
MARGIN_LEFT_MM   = 13.5
MARGIN_RIGHT_MM  = 13.5

# ---------------------------------------------------------------------------
# Brand colours  (hex, no leading #)
# ---------------------------------------------------------------------------
COLOR_GOLD      = "E1A84A"   # Turn2Law gold
COLOR_CHARCOAL  = "232323"   # Near-black
COLOR_BG        = "F4F4F4"   # Light off-white page background

# ---------------------------------------------------------------------------
# Top decorative bar
# ---------------------------------------------------------------------------
TOP_BAR_HEIGHT_PT   = 4      # thin gold strip at very top
TOP_BAND_HEIGHT_PT  = 26     # parallelogram band below strip

# Parallelogram segments (x-start, x-end, in pt from left edge)
# Charcoal block:  205 → 309 (top edge); 221 → 285 (bottom edge)
TOP_CHARCOAL_X1 = 205
TOP_CHARCOAL_X2 = 309
TOP_CHARCOAL_BX1 = 221
TOP_CHARCOAL_BX2 = 285
# Gold block:      335 → 510 (top); 358 → 487 (bottom)
TOP_GOLD_X1  = 335
TOP_GOLD_X2  = 510
TOP_GOLD_BX1 = 358
TOP_GOLD_BX2 = 487

# ---------------------------------------------------------------------------
# Bottom decorative bar
# ---------------------------------------------------------------------------
BOTTOM_BAR_HEIGHT_PT  = 4    # thin gold strip at very bottom
BOTTOM_BAND_HEIGHT_PT = 18   # parallelogram band above strip

# Left charcoal wedge: 0→34 (bottom); 0→26 (top)
BTM_LEFT_CHARCOAL_X2    = 34
BTM_LEFT_CHARCOAL_TOP_X = 26
# Gold band:  34→178 (bottom); 49→156 (top)
BTM_GOLD_X1    = 34
BTM_GOLD_X2    = 178
BTM_GOLD_TOP_X1 = 49
BTM_GOLD_TOP_X2 = 156
# Right charcoal band: 274→338 (bottom); 255→319 (top)
BTM_RIGHT_CHARCOAL_X1     = 274
BTM_RIGHT_CHARCOAL_X2     = 338
BTM_RIGHT_CHARCOAL_TOP_X1 = 255
BTM_RIGHT_CHARCOAL_TOP_X2 = 319

# ---------------------------------------------------------------------------
# Right-side diagonal stripe decorations (background layer)
# Each tuple: (x-fraction-of-width, y-fraction-of-height) of triangle apex
# ---------------------------------------------------------------------------
DIAGONAL_STRIPES = [
    (0.95, 0.20),
    (0.83, 0.27),
    (0.71, 0.34),
    (0.58, 0.41),
    (0.45, 0.48),
    (0.32, 0.55),
]
DIAGONAL_STRIPE_WIDTH_PT = 18    # width of each stripe sliver
DIAGONAL_STRIPE_OPACITY  = 0.35  # white with this opacity

# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------
WATERMARK_TEXT    = "TURN2LAW"
WATERMARK_OPACITY = 0.04        # very subtle — matches reference
WATERMARK_ANGLE   = 45          # degrees counter-clockwise
WATERMARK_FONT_PT = 72

# ---------------------------------------------------------------------------
# Spacing (vertical, in em unless noted)
# ---------------------------------------------------------------------------
SPACE_AFTER_LOGO_EM        = 0.9
SPACE_AFTER_TITLE_EM       = 0.35
SPACE_AFTER_DATELINE_EM    = 1.0
SPACE_AFTER_NAME_EM        = 0.25
SPACE_AFTER_INTRO_EM       = 0.85
SPACE_AFTER_PARA_EM        = 0.75
SPACE_BEFORE_POS_TITLE_EM  = 0.85
SPACE_AFTER_POS_TITLE_EM   = 0.25
SPACE_AFTER_BULLETS_EM     = 0.6
SPACE_AFTER_CLOSING_EM     = 0.85
SPACE_AFTER_REGARDS_EM     = 0.25
SPACE_AFTER_SIGNATURE_EM   = 0.2
SPACE_AFTER_SIGNEE_EM      = 0.0
SPACE_BEFORE_RULE_MM       = 6    # fixed space before footer rule (mm)
SPACE_AFTER_RULE_EM        = 0.35
