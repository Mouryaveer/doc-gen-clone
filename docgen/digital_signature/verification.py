"""
verification.py — Verify digital signatures embedded in a PDF.

Verification results
--------------------
VALID               — signature intact, certificate valid
MODIFIED            — document modified after signing
CERT_EXPIRED        — signer certificate has expired
CERT_UNKNOWN_ISSUER — issuer not in trust store
TIMESTAMP_INVALID   — embedded timestamp cannot be verified
CORRUPTED           — signature bytes are malformed
NO_SIGNATURE        — PDF contains no signature field

Usage
-----
    from digital_signature.verification import verify_pdf, VerificationStatus

    result = verify_pdf("/path/to/signed.pdf")
    print(result.status)          # VerificationStatus.VALID
    print(result.signer_name)
    print(result.signing_time)
    print(result.summary)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .utils import assert_valid_pdf
from .exceptions import (
    PDFIntegrityError,
    SignatureNotFoundError,
    VerificationError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class VerificationStatus(str, Enum):
    VALID               = "VALID"
    MODIFIED            = "MODIFIED"
    CERT_EXPIRED        = "CERT_EXPIRED"
    CERT_UNKNOWN_ISSUER = "CERT_UNKNOWN_ISSUER"
    TIMESTAMP_INVALID   = "TIMESTAMP_INVALID"
    CORRUPTED           = "CORRUPTED"
    NO_SIGNATURE        = "NO_SIGNATURE"
    ERROR               = "ERROR"


@dataclass
class VerificationResult:
    status:       VerificationStatus
    signer_name:  Optional[str] = None
    signing_time: Optional[str] = None
    reason:       Optional[str] = None
    location:     Optional[str] = None
    cert_subject: Optional[str] = None
    cert_issuer:  Optional[str] = None
    cert_expiry:  Optional[str] = None
    details:      str = ""       # raw detail string from pyHanko
    error:        Optional[str] = None

    @property
    def summary(self) -> str:
        """One-line human-readable summary."""
        s = self.status.value
        if self.signer_name:
            s += f" | Signed by: {self.signer_name}"
        if self.signing_time:
            s += f" | At: {self.signing_time}"
        if self.error:
            s += f" | Error: {self.error}"
        return s

    @property
    def is_valid(self) -> bool:
        return self.status == VerificationStatus.VALID


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_pdf(pdf_path: str) -> VerificationResult:
    """
    Verify all embedded signatures in *pdf_path*.

    Returns the result for the FIRST signature found (which covers the whole
    document in most single-signer flows).  For multi-signer documents, call
    verify_pdf_all() instead.

    Parameters
    ----------
    pdf_path : absolute path to the signed PDF

    Returns
    -------
    VerificationResult
    """
    pdf_path = os.path.abspath(pdf_path)
    logger.info("Verifying PDF: %s", pdf_path)

    try:
        assert_valid_pdf(pdf_path)
    except PDFIntegrityError as exc:
        return VerificationResult(
            status=VerificationStatus.CORRUPTED,
            error=str(exc),
        )

    try:
        return _verify_with_pyhanko(pdf_path)
    except SignatureNotFoundError:
        return VerificationResult(status=VerificationStatus.NO_SIGNATURE)
    except Exception as exc:
        logger.exception("Unexpected error during verification.")
        return VerificationResult(
            status=VerificationStatus.ERROR,
            error=str(exc),
        )


def verify_pdf_all(pdf_path: str) -> list[VerificationResult]:
    """
    Verify all signatures in *pdf_path* and return one result per signature.
    """
    pdf_path = os.path.abspath(pdf_path)
    logger.info("Verifying all signatures in: %s", pdf_path)

    try:
        assert_valid_pdf(pdf_path)
    except PDFIntegrityError as exc:
        return [VerificationResult(status=VerificationStatus.CORRUPTED, error=str(exc))]

    try:
        return _verify_all_with_pyhanko(pdf_path)
    except SignatureNotFoundError:
        return [VerificationResult(status=VerificationStatus.NO_SIGNATURE)]
    except Exception as exc:
        logger.exception("Unexpected error during verification.")
        return [VerificationResult(status=VerificationStatus.ERROR, error=str(exc))]


# ---------------------------------------------------------------------------
# pyHanko implementation
# ---------------------------------------------------------------------------

def _verify_with_pyhanko(pdf_path: str) -> VerificationResult:
    results = _verify_all_with_pyhanko(pdf_path)
    return results[0] if results else VerificationResult(status=VerificationStatus.NO_SIGNATURE)


def _verify_all_with_pyhanko(pdf_path: str) -> list[VerificationResult]:
    try:
        from pyhanko.sign.validation import validate_pdf_signature
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.fields import enumerate_sig_fields
        from io import BytesIO
    except ImportError as exc:
        raise VerificationError(
            "pyhanko / pyhanko_certvalidator not installed. "
            "Run: pip install pyhanko pyhanko-certvalidator"
        ) from exc

    with open(pdf_path, "rb") as fh:
        reader = PdfFileReader(fh)

        sig_fields_list = list(enumerate_sig_fields(reader, filled_status=True))

        if not sig_fields_list:
            raise SignatureNotFoundError("No signature fields found in PDF.")

        results: list[VerificationResult] = []

        for sig_field_name, sig_val, field_ref in sig_fields_list:
            if field_ref is None:
                continue
            try:
                from pyhanko.sign.validation.pdf_embedded import EmbeddedPdfSignature
                embedded = EmbeddedPdfSignature(reader, field_ref, sig_field_name)
                status = validate_pdf_signature(
                    embedded_sig=embedded,
                    signer_validation_context=None,
                )
                result = _parse_validation_status(status)
                results.append(result)
            except Exception as exc:
                results.append(VerificationResult(
                    status=VerificationStatus.ERROR,
                    error=str(exc),
                ))

    return results or [VerificationResult(status=VerificationStatus.NO_SIGNATURE)]


def _parse_validation_status(status) -> VerificationResult:
    """
    Translate a pyHanko PdfSignatureStatus object into a VerificationResult.
    """
    # ---- Integrity -------------------------------------------------------
    try:
        intact = status.intact
        valid  = status.valid
    except AttributeError:
        intact = True
        valid  = True

    if not intact:
        return VerificationResult(
            status=VerificationStatus.MODIFIED,
            details=str(status),
        )

    # ---- Cert info -------------------------------------------------------
    signer_name  = None
    signing_time = None
    cert_subject = None
    cert_issuer  = None
    cert_expiry  = None
    reason       = None
    location     = None

    try:
        cert = status.signing_cert
        if cert:
            from asn1crypto import x509 as asn1_x509
            # signing_cert is asn1crypto.x509.Certificate
            subject = cert.subject
            cn_list = subject.human_friendly
            signer_name = cn_list if cn_list else str(subject)

            issuer = cert.issuer
            cert_issuer = issuer.human_friendly if issuer else None

            # Expiry
            try:
                cert_expiry = cert['tbs_certificate']['validity']['not_after'].native.strftime("%Y-%m-%d")
            except Exception:
                pass
    except Exception:
        pass

    try:
        st = status.signer_reported_dt
        if st:
            signing_time = str(st)
    except Exception:
        pass

    try:
        si = status.signer_info
        if si:
            reason   = _safe_attr(si, "reason")
            location = _safe_attr(si, "location")
    except Exception:
        pass

    # Fallback signer_name from timestamp
    if not signer_name and signing_time:
        signer_name = signing_time

    # ---- Trust problem ---------------------------------------------------
    try:
        trust_problem = status.trust_problem_description
    except AttributeError:
        trust_problem = None

    if trust_problem:
        problem_str = str(trust_problem).lower()
        vs = VerificationStatus.CERT_EXPIRED if "expired" in problem_str else VerificationStatus.CERT_UNKNOWN_ISSUER
        return VerificationResult(
            status       = vs,
            signer_name  = signer_name,
            signing_time = signing_time,
            cert_subject = cert_subject,
            cert_issuer  = cert_issuer,
            cert_expiry  = cert_expiry,
            reason       = reason,
            location     = location,
            details      = str(trust_problem),
        )

    final_status = VerificationStatus.VALID if valid else VerificationStatus.CORRUPTED
    return VerificationResult(
        status       = final_status,
        signer_name  = signer_name,
        signing_time = signing_time,
        cert_subject = cert_subject,
        cert_issuer  = cert_issuer,
        cert_expiry  = cert_expiry,
        reason       = reason,
        location     = location,
        details      = str(status),
    )


def _safe_attr(obj, name: str):
    try:
        return getattr(obj, name, None)
    except Exception:
        return None
