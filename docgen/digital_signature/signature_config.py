"""
signature_config.py — Centralised configuration for the Digital Signature Engine.

All tunable values live here.  Import this module wherever signing parameters
are needed — never hard-code them in business logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Digest / hash algorithms
# ---------------------------------------------------------------------------
DIGEST_ALGORITHM: str = "sha256"          # "sha256" | "sha384" | "sha512"
SUPPORTED_DIGEST_ALGORITHMS: tuple[str, ...] = ("sha256", "sha384", "sha512")

# ---------------------------------------------------------------------------
# Signature embedding mode
# ---------------------------------------------------------------------------
SIGNATURE_FIELD_NAME: str = "Turn2LawSignature"

# ---------------------------------------------------------------------------
# Visible signature appearance
# ---------------------------------------------------------------------------
@dataclass
class VisibleSignatureConfig:
    """Pixel / point coordinates for the visible signature box."""
    page: int   = 0          # 0-indexed page number (last page = -1)
    x1:   float = 36.0       # left edge in points from bottom-left
    y1:   float = 36.0       # bottom edge in points from bottom-left
    x2:   float = 340.0      # right edge
    y2:   float = 100.0      # top edge
    show_date:   bool = True
    show_reason: bool = True
    show_location: bool = True
    # Font sizes for the visible box text (points)
    name_font_size:  float = 18.0
    label_font_size: float = 9.0


DEFAULT_VISIBLE_CONFIG = VisibleSignatureConfig()


# ---------------------------------------------------------------------------
# Timestamp (RFC 3161)
# ---------------------------------------------------------------------------
TIMESTAMP_URL: Optional[str] = os.getenv(
    "RFC3161_TSA_URL",
    "http://timestamp.digicert.com",   # free public TSA — replace in production
)
TIMESTAMP_ENABLED: bool = False        # set True when a reliable TSA is configured
TIMESTAMP_TIMEOUT_SECONDS: int = 10

# ---------------------------------------------------------------------------
# Certificate validation
# ---------------------------------------------------------------------------
VALIDATION_CHECK_EXPIRY:     bool = True
VALIDATION_CHECK_KEY_USAGE:  bool = True
VALIDATION_CHECK_CHAIN:      bool = False   # enable when a trust store is configured

# Supported signature algorithms (OID short names, case-insensitive)
SUPPORTED_SIGNATURE_ALGORITHMS: tuple[str, ...] = (
    "rsassa_pkcs1v15",
    "rsa",
    "ecdsa",
    "dsa",
    "rsassa_pss",
    "ed25519",
    "ed448",
)

# ---------------------------------------------------------------------------
# Supported certificate file extensions
# ---------------------------------------------------------------------------
SUPPORTED_CERT_EXTENSIONS: tuple[str, ...] = (".pfx", ".p12")

# ---------------------------------------------------------------------------
# Output file naming
# ---------------------------------------------------------------------------
SIGNED_SUFFIX: str = "_signed"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = "INFO"
