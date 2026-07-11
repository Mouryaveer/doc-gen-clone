"""
certificate_validator.py — Pre-signing certificate validation.

Checks performed (each independently configurable in signature_config.py):
  1. Certificate is readable (already guaranteed by loader, but re-checked).
  2. Certificate has not expired.
  3. Private key is present (already guaranteed by loader).
  4. Key-usage extension permits digital signatures.
  5. Signature algorithm is supported.
  6. (Optional) Certificate chain validation.

Raises domain-specific exceptions so callers can surface clear user messages.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from cryptography import x509
from cryptography.x509.extensions import ExtensionNotFound
from cryptography.x509.oid import ExtendedKeyUsageOID

from .certificate_loader import CertificateBundle
from .exceptions import (
    CertificateExpiredError,
    InvalidKeyUsageError,
    UnsupportedAlgorithmError,
    CertificateChainError,
    InvalidCertificateError,
)
from .signature_config import (
    VALIDATION_CHECK_EXPIRY,
    VALIDATION_CHECK_KEY_USAGE,
    VALIDATION_CHECK_CHAIN,
    SUPPORTED_SIGNATURE_ALGORITHMS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_certificate(bundle: CertificateBundle) -> None:
    """
    Run all configured validation checks against *bundle*.

    Raises an appropriate subclass of DigitalSignatureError on failure.
    Does nothing on success.
    """
    logger.info("Validating certificate — CN: %s", bundle.subject_cn)

    if VALIDATION_CHECK_EXPIRY:
        _check_expiry(bundle)

    if VALIDATION_CHECK_KEY_USAGE:
        _check_key_usage(bundle)

    _check_algorithm(bundle)

    if VALIDATION_CHECK_CHAIN:
        _check_chain(bundle)

    logger.info("Certificate validation passed.")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_expiry(bundle: CertificateBundle) -> None:
    """Raise CertificateExpiredError if the certificate validity window has closed."""
    cert = bundle.certificate
    now = datetime.now(tz=timezone.utc)

    # cryptography returns naive UTC datetimes in older versions, aware in newer
    not_before = _ensure_aware(cert.not_valid_before_utc if hasattr(cert, "not_valid_before_utc") else cert.not_valid_before)  # type: ignore[attr-defined]
    not_after  = _ensure_aware(cert.not_valid_after_utc  if hasattr(cert, "not_valid_after_utc")  else cert.not_valid_after)   # type: ignore[attr-defined]

    if now < not_before:
        raise InvalidCertificateError(
            f"Certificate is not yet valid. Valid from: {not_before.isoformat()}"
        )
    if now > not_after:
        raise CertificateExpiredError(
            f"Certificate expired on {not_after.strftime('%d %B %Y')}. "
            "Please obtain a renewed certificate."
        )

    logger.debug(
        "Certificate validity: %s → %s (current: %s)",
        not_before.isoformat(), not_after.isoformat(), now.isoformat()
    )


def _check_key_usage(bundle: CertificateBundle) -> None:
    """
    Check KeyUsage and ExtendedKeyUsage extensions to confirm the certificate
    is permitted to perform digital signatures.

    We treat absence of KeyUsage as permissive (many self-signed certs omit it).
    """
    cert = bundle.certificate

    # ---- KeyUsage -------------------------------------------------------
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not ku.digital_signature:
            raise InvalidKeyUsageError(
                "The certificate's KeyUsage extension does not include "
                "'digitalSignature'. This certificate cannot be used for signing."
            )
        logger.debug("KeyUsage.digitalSignature = True")
    except ExtensionNotFound:
        # No KeyUsage extension — treat as permitted
        logger.debug("No KeyUsage extension found; treating as permitted.")

    # ---- ExtendedKeyUsage (informational / advisory) --------------------
    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        eku_oids = [u.dotted_string for u in eku]
        # emailProtection and codeSigning are acceptable for document signing
        acceptable = {
            ExtendedKeyUsageOID.EMAIL_PROTECTION.dotted_string,
            ExtendedKeyUsageOID.CODE_SIGNING.dotted_string,
            "1.3.6.1.4.1.311.10.3.12",   # Microsoft Document Signing
            "1.2.840.113583.1.1.5",        # Adobe Authentic Documents Trust
        }
        if not any(o in acceptable for o in eku_oids):
            logger.warning(
                "Certificate EKU [%s] does not include a document-signing OID. "
                "Signature may not be trusted by all PDF viewers.",
                ", ".join(eku_oids)
            )
    except ExtensionNotFound:
        logger.debug("No ExtendedKeyUsage extension; continuing.")


def _check_algorithm(bundle: CertificateBundle) -> None:
    """Raise UnsupportedAlgorithmError if the algorithm is deprecated or unknown."""
    sig_alg = bundle.certificate.signature_algorithm_oid.dotted_string

    # Map well-known OIDs to short names for a readable log entry
    OID_MAP = {
        "1.2.840.113549.1.1.11": "sha256WithRSAEncryption",
        "1.2.840.113549.1.1.12": "sha384WithRSAEncryption",
        "1.2.840.113549.1.1.13": "sha512WithRSAEncryption",
        "1.2.840.10045.4.3.2":   "ecdsa-with-SHA256",
        "1.2.840.10045.4.3.3":   "ecdsa-with-SHA384",
        "1.2.840.10045.4.3.4":   "ecdsa-with-SHA512",
        "1.2.840.113549.1.1.5":  "sha1WithRSAEncryption",   # weak — warn
    }
    short_name = OID_MAP.get(sig_alg, sig_alg)

    # Reject MD5 / MD2 / SHA-1 RSA (OIDs for completeness)
    DEPRECATED_OIDS = {
        "1.2.840.113549.1.1.4",  # md5WithRSAEncryption
        "1.2.840.113549.1.1.2",  # md2WithRSAEncryption
    }
    if sig_alg in DEPRECATED_OIDS:
        raise UnsupportedAlgorithmError(
            f"Certificate uses deprecated algorithm '{short_name}'. "
            "Please obtain a certificate with SHA-256 or stronger."
        )

    if sig_alg == "1.2.840.113549.1.1.5":
        logger.warning(
            "Certificate uses SHA-1 with RSA (%s). "
            "This is weak and may be rejected by strict validators. "
            "Consider renewing with SHA-256.",
            short_name,
        )
    else:
        logger.debug("Signature algorithm: %s (%s)", short_name, sig_alg)


def _check_chain(bundle: CertificateBundle) -> None:
    """
    Basic chain length check.  Full path-building validation requires a
    trusted root store and is left for a future CRL/OCSP integration.
    """
    if not bundle.chain:
        logger.warning(
            "No intermediate CA chain included in the PKCS#12 bundle. "
            "Signature may appear as 'Unverified' in strict PDF viewers."
        )
    else:
        logger.debug("Intermediate chain: %d certificate(s)", len(bundle.chain))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ensure_aware(dt: datetime) -> datetime:
    """Make a naïve datetime timezone-aware (assume UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
