"""
assets.py — Image asset registry for Turn2Law document templates.

All paths are relative to the docgen/images/ directory.
The template uses \graphicspath{{./images/}} so only the bare filename
(without extension) is needed in \includegraphics{}.

Image inventory (identified from the sample PDF via PyMuPDF xref numbers):
  sample_asset_0_xref_36   — Turn2Law logo (header, top-left)
  sample_asset_1_xref_47   — Email envelope icon (footer)
  sample_asset_2_xref_36   — (reserved / secondary logo variant)
  sample_asset_3_xref_63   — (reserved / decorative asset)
  2df383ea-…-1_171_229_2316_191 — Founder signature
"""

# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------
LOGO_FILENAME      = "sample_asset_0_xref_36"   # no extension — LaTeX finds it
LOGO_HEIGHT_CM     = 1.22                        # render height in cm

# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------
SIGNATURE_FILENAME = "2df383ea-bab3-42c5-bff0-3b02e82627a7-1_171_229_2316_191"
SIGNATURE_WIDTH_CM = 2.6

# ---------------------------------------------------------------------------
# Footer email icon
# ---------------------------------------------------------------------------
EMAIL_ICON_FILENAME  = "sample_asset_1_xref_47"
EMAIL_ICON_HEIGHT_CM = 0.38   # small icon, inline with text baseline
