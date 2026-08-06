# coding: utf-8
"""
certificate_validator.py — Pre-signing certificate validation.

Checks performed (independently configurable via signature_config.py):
  1. Certificate not yet expired and validity window has started.
  2. KeyUsage extension permits digitalSignature (absent = permissive).
  3. Signature algorithm is not deprecated (MD5, MD2 rejected; SHA-1 warned).
  4. Basic chain check (warns if no intermediates; full path-building
     requires a trust-store — out of scope here).

All checks raise domain-specific exceptions so callers can surface clear
user-facing messages without exposing stack traces.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from cryptography import x509
from cryptography.x509.extensions import ExtensionNotFound
from cryptography.x509.oid import ExtendedKeyUsageOID

from .certificate_loader import CertificateBundle
from .exceptions import (
    CertificateExpiredError,
    CertificateChainError,
    InvalidCertificateError,
    InvalidKeyUsageError,
    UnsupportedAlgorithmError,
)
from .signature_config import (
    VALIDATION_CHECK_CHAIN,
    VALIDATION_CHECK_EXPIRY,
    VALIDATION_CHECK_KEY_USAGE,
)

logger = logging.getLogger(__name__)

# OIDs rejected as deprecated (MD5 / MD2)
_DEPRECATED_OIDS = frozenset({
    "1.2.840.113549.1.1.4",   # md5WithRSAEncryption
    "1.2.840.113549.1.1.2",   # md2WithRSAEncryption
})

# OID → short name map for readable log output
_OID_NAMES: dict[str, str] = {
    "1.2.840.113549.1.1.11": "sha256WithRSAEncryption",
    "1.2.840.113549.1.1.12": "sha384WithRSAEncryption",
    "1.2.840.113549.1.1.13": "sha512WithRSAEncryption",
    "1.2.840.10045.4.3.2":   "ecdsa-with-SHA256",
    "1.2.840.10045.4.3.3":   "ecdsa-with-SHA384",
    "1.2.840.10045.4.3.4":   "ecdsa-with-SHA512",
    "1.2.840.113549.1.1.5":  "sha1WithRSAEncryption",   # weak — warn only
    "1.2.840.113549.1.1.4":  "md5WithRSAEncryption",    # rejected
    "1.2.840.113549.1.1.2":  "md2WithRSAEncryption",    # rejected
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_certificate(bundle: CertificateBundle) -> None:
    """
    Run all configured validation checks against *bundle*.

    Raises a domain-specific subclass of DigitalSignatureError on failure.
    Returns None on success.
    """
    logger.info("Validating certificate — CN: %s", bundle.subject_cn)

    if VALIDATION_CHECK_EXPIRY:
        _check_expiry(bundle)

    if VALIDATION_CHECK_KEY_USAGE:
        _check_key_usage(bundle)

    _check_algorithm(bundle)

    if VALIDATION_CHECK_CHAIN:
        _check_chain(bundle)

    logger.info("Certificate validation passed — CN: %s", bundle.subject_cn)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_expiry(bundle: CertificateBundle) -> None:
    """Raise CertificateExpiredError if the validity window has closed."""
    cert = bundle.certificate
    now  = datetime.now(tz=timezone.utc)

    # cryptography >= 42 exposes timezone-aware properties directly;
    # older versions return naive UTC datetimes.
    not_before = _aware(
        cert.not_valid_before_utc if hasattr(cert, "not_valid_before_utc")
        else cert.not_valid_before
    )
    not_after = _aware(
        cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc")
        else cert.not_valid_after
    )

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
        "Certificate validity OK: %s → %s",
        not_before.strftime("%Y-%m-%d"),
        not_after.strftime("%Y-%m-%d"),
    )


def _check_key_usage(bundle: CertificateBundle) -> None:
    """
    Verify the certificate is permitted to perform digital signatures.

    Absence of KeyUsage is treated as permissive (common for self-signed
    development certificates).
    """
    cert = bundle.certificate

    # --- KeyUsage ---------------------------------------------------------
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not ku.digital_signature:
            raise InvalidKeyUsageError(
                "The certificate's KeyUsage extension does not include "
                "'digitalSignature'. This certificate cannot be used for signing."
            )
        logger.debug("KeyUsage.digitalSignature = True")
    except ExtensionNotFound:
        logger.debug("No KeyUsage extension — treating as permitted (common for self-signed certs).")

    # --- ExtendedKeyUsage (advisory) --------------------------------------
    _ACCEPTABLE_EKU = {
        ExtendedKeyUsageOID.EMAIL_PROTECTION.dotted_string,
        ExtendedKeyUsageOID.CODE_SIGNING.dotted_string,
        "1.3.6.1.4.1.311.10.3.12",    # Microsoft Document Signing
        "1.2.840.113583.1.1.5",         # Adobe Authentic Documents Trust
        "1.3.6.1.5.5.7.3.4",            # emailProtection (dotted)
    }
    try:
        eku      = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        eku_oids = {u.dotted_string for u in eku}
        if not eku_oids.intersection(_ACCEPTABLE_EKU):
            logger.warning(
                "Certificate EKU %s does not include a document-signing OID. "
                "Signature may not be trusted by strict PDF viewers.",
                eku_oids,
            )
    except ExtensionNotFound:
        logger.debug("No ExtendedKeyUsage extension — continuing.")


def _check_algorithm(bundle: CertificateBundle) -> None:
    """Raise UnsupportedAlgorithmError for MD5/MD2; warn for SHA-1."""
    oid        = bundle.certificate.signature_algorithm_oid.dotted_string
    short_name = _OID_NAMES.get(oid, oid)

    if oid in _DEPRECATED_OIDS:
        raise UnsupportedAlgorithmError(
            f"Certificate uses deprecated algorithm '{short_name}'. "
            "Please obtain a certificate signed with SHA-256 or stronger."
        )

    if oid == "1.2.840.113549.1.1.5":  # sha1WithRSAEncryption
        logger.warning(
            "Certificate uses SHA-1 with RSA (%s). "
            "This algorithm is weak and may be rejected by strict validators. "
            "Consider renewing with SHA-256.",
            short_name,
        )
    else:
        logger.debug("Signature algorithm OK: %s (%s)", short_name, oid)


def _check_chain(bundle: CertificateBundle) -> None:
    """Warn if no intermediate CA chain is present in the bundle."""
    if not bundle.chain:
        logger.warning(
            "No intermediate CA chain found in the PKCS#12 bundle. "
            "The signature may appear as 'Unverified' in strict PDF viewers. "
            "Include the full chain when exporting your .pfx file."
        )
    else:
        logger.debug("Intermediate chain: %d certificate(s) present.", len(bundle.chain))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (assume UTC if naive)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
