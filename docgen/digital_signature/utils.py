"""
utils.py — Internal utility helpers for the Digital Signature Engine.

Functions here must NOT reference pyhanko or cryptography directly —
that dependency belongs in the dedicated modules.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import timezone
from typing import Optional

from .signature_config import DIGEST_ALGORITHM, SUPPORTED_DIGEST_ALGORITHMS
from .exceptions import PDFIntegrityError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def ensure_file_exists(path: str, label: str = "File") -> None:
    """Raise PDFIntegrityError if *path* does not exist or is not a file."""
    if not os.path.isfile(path):
        raise PDFIntegrityError(f"{label} not found: {path}")


def build_output_path(input_pdf: str, suffix: str = "_signed") -> str:
    """
    Derive a *_signed.pdf* path next to the original.

    >>> build_output_path("/tmp/offer.pdf")
    '/tmp/offer_signed.pdf'
    """
    base, ext = os.path.splitext(input_pdf)
    return f"{base}{suffix}{ext or '.pdf'}"


# ---------------------------------------------------------------------------
# PDF integrity check (lightweight)
# ---------------------------------------------------------------------------

def assert_valid_pdf(path: str) -> None:
    """
    Check the first 5 bytes for the %PDF- magic number.
    Raises PDFIntegrityError on failure.
    """
    ensure_file_exists(path, "PDF file")
    with open(path, "rb") as fh:
        header = fh.read(5)
    if header != b"%PDF-":
        raise PDFIntegrityError(
            f"File does not appear to be a valid PDF (bad magic bytes): {path}"
        )


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_file(path: str, algorithm: str = DIGEST_ALGORITHM) -> bytes:
    """
    Return the raw digest bytes of the entire file.

    Parameters
    ----------
    path      : absolute path to file
    algorithm : digest name accepted by hashlib (sha256, sha384, sha512)
    """
    _validate_digest_algorithm(algorithm)
    h = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    digest = h.digest()
    logger.debug("File hash (%s): %s  →  %s", algorithm, path, digest.hex())
    return digest


def hash_bytes(data: bytes, algorithm: str = DIGEST_ALGORITHM) -> bytes:
    """Return the raw digest of an in-memory byte string."""
    _validate_digest_algorithm(algorithm)
    return hashlib.new(algorithm, data).digest()


def _validate_digest_algorithm(algorithm: str) -> None:
    if algorithm.lower() not in SUPPORTED_DIGEST_ALGORITHMS:
        raise ValueError(
            f"Unsupported digest algorithm '{algorithm}'. "
            f"Choose from: {SUPPORTED_DIGEST_ALGORITHMS}"
        )


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def utc_now_string() -> str:
    """Return the current UTC time as a human-readable string."""
    from datetime import datetime
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------

def sanitise_text(value: Optional[str]) -> str:
    """
    Strip characters that are illegal in PDF strings and return a clean value.
    Returns empty string for None / blank input.
    """
    if not value:
        return ""
    # Remove ASCII control characters except TAB/LF/CR
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value).strip()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def redact(secret: str) -> str:
    """
    Return a redacted placeholder — used in log messages to avoid leaking
    passwords or key material.
    """
    return "***REDACTED***"
