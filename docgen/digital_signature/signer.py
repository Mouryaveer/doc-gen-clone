# coding: utf-8
"""
signer.py — High-level signing facade for the Turn2Law Digital Signature Engine.

This is the ONLY module external callers should import from.
All implementation details (loader, validator, pdf_signer, etc.) are hidden
behind a single clean public API.

Usage
-----
    from digital_signature.signer import sign_document, SigningRequest

    request = SigningRequest(
        pdf_path    = "/path/to/output.pdf",
        cert_path   = "/path/to/certificate.pfx",
        password    = "secret",
        signer_name = "JAGJYOT SINGH",
        reason      = "Approved",
        location    = "Chennai, India",
        visible     = True,
    )
    signed_path = sign_document(request)
    # → "/path/to/output_signed.pdf"
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from .certificate_loader import CertificateBundle, load_certificate
from .certificate_validator import validate_certificate
from .exceptions import DigitalSignatureError, SigningFailedError
from .metadata import SignatureMetadata
from .pdf_signer import sign_pdf
from .signature_config import (
    DEFAULT_VISIBLE_CONFIG,
    SIGNED_SUFFIX,
    VisibleSignatureConfig,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request model  (not frozen so password can be wiped in finally)
# ---------------------------------------------------------------------------

@dataclass
class SigningRequest:
    """
    All inputs needed for a single signing operation.

    password is held in memory only for the duration of the signing call
    and is cleared (set to empty string) in the finally block.
    """
    pdf_path:    str
    cert_path:   str
    password:    str           # sensitive — cleared after use
    signer_name: str

    output_pdf:      Optional[str]            = None
    reason:          Optional[str]            = None
    location:        Optional[str]            = None
    contact:         Optional[str]            = None
    visible:         bool                     = True
    visible_config:  VisibleSignatureConfig   = field(
        default_factory=lambda: VisibleSignatureConfig()
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sign_document(request: SigningRequest) -> str:
    """
    Complete end-to-end signing pipeline.

    Steps
    -----
    1. Load certificate from PKCS#12 bundle.
    2. Validate certificate (expiry, key-usage, algorithm).
    3. Build SignatureMetadata.
    4. Sign PDF (pyHanko incremental update / CMS).
    5. Dispose of key material.
    6. Return absolute path to the signed PDF.

    Raises
    ------
    Any subclass of DigitalSignatureError on failure.
    """
    logger.info("=== Turn2Law Digital Signature Engine — signing started ===")
    logger.info("Input PDF   : %s", os.path.abspath(request.pdf_path))
    logger.info("Certificate : %s", os.path.abspath(request.cert_path))
    logger.info("Signer      : %s", request.signer_name)

    bundle: Optional[CertificateBundle] = None

    try:
        # Step 1 — Load certificate
        logger.info("Step 1/4 — Loading certificate …")
        bundle = load_certificate(request.cert_path, request.password)

        # Step 2 — Validate certificate
        logger.info("Step 2/4 — Validating certificate …")
        validate_certificate(bundle)

        # Step 3 — Build metadata
        logger.info("Step 3/4 — Building signature metadata …")
        metadata = SignatureMetadata(
            signer_name    = request.signer_name,
            reason         = request.reason,
            location       = request.location,
            contact        = request.contact,
            visible        = request.visible,
            visible_config = request.visible_config,
        )

        # Step 4 — Sign PDF
        logger.info("Step 4/4 — Signing PDF …")
        signed_path = sign_pdf(
            input_pdf  = request.pdf_path,
            output_pdf = request.output_pdf,
            bundle     = bundle,
            metadata   = metadata,
            cert_path  = os.path.abspath(request.cert_path),
            password   = request.password,
        )

        logger.info("=== Signing complete: %s ===", signed_path)
        return signed_path

    except DigitalSignatureError:
        raise   # re-raise domain exceptions unchanged

    except Exception as exc:
        logger.exception("Unexpected signing failure.")
        raise SigningFailedError(f"Signing failed: {exc}") from exc

    finally:
        # Always dispose of key material
        if bundle is not None:
            bundle.dispose()
            logger.debug("Key material disposed.")
        # Clear password from request object (dataclass is NOT frozen)
        try:
            request.password = ""
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def sign_pdf_file(
    pdf_path:    str,
    cert_path:   str,
    password:    str,
    signer_name: str,
    output_pdf:  Optional[str] = None,
    reason:      Optional[str] = None,
    location:    Optional[str] = None,
    contact:     Optional[str] = None,
    visible:     bool          = True,
    *,
    page: int   = -1,       # -1 = last page
    x1:   float = 36.0,
    y1:   float = 36.0,
    x2:   float = 340.0,
    y2:   float = 100.0,
) -> str:
    """
    Thin keyword-argument wrapper around sign_document().

    Returns the absolute path to the signed PDF.
    """
    vc  = VisibleSignatureConfig(page=page, x1=x1, y1=y1, x2=x2, y2=y2)
    req = SigningRequest(
        pdf_path       = pdf_path,
        cert_path      = cert_path,
        password       = password,
        signer_name    = signer_name,
        output_pdf     = output_pdf,
        reason         = reason,
        location       = location,
        contact        = contact,
        visible        = visible,
        visible_config = vc,
    )
    return sign_document(req)
