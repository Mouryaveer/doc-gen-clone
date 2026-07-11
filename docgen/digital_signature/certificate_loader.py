"""
certificate_loader.py — Load PKCS#12 (.pfx / .p12) certificates.

Responsibilities
----------------
* Accept a filesystem path + password.
* Return a structured CertificateBundle (private key + cert + chain).
* Securely dispose of sensitive material when no longer needed.
* Never log the private key or password.

Future extension points (Phase 2)
----------------------------------
* PKCS#11 hardware token / USB DSC loader
* HSM-backed key loader
* Cloud signing service adapter
All future loaders must implement the same CertificateBundle interface so
the rest of the engine remains unchanged.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509 import Certificate
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes

from .exceptions import (
    CertificateNotFoundError,
    InvalidCertificateError,
    IncorrectPasswordError,
    UnsupportedCertificateFormatError,
    PrivateKeyMissingError,
)
from .signature_config import SUPPORTED_CERT_EXTENSIONS
from .utils import ensure_file_exists, sanitise_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CertificateBundle:
    """
    Holds all cryptographic material extracted from a PKCS#12 bundle.

    Treat this object as short-lived — create it, sign, then call dispose().
    """
    private_key:  PrivateKeyTypes          # never serialised / logged
    certificate:  Certificate              # end-entity cert
    chain:        List[Certificate] = field(default_factory=list)  # intermediates
    friendly_name: Optional[str] = None    # label embedded in .pfx, if any

    # ------------------------------------------------------------------
    # Derived helpers (do not expose sensitive internals)
    # ------------------------------------------------------------------

    @property
    def subject_cn(self) -> str:
        """Common Name from the end-entity certificate subject."""
        try:
            from cryptography.x509.oid import NameOID
            attrs = self.certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            return attrs[0].value if attrs else ""
        except Exception:
            return ""

    @property
    def issuer_cn(self) -> str:
        """Common Name from the issuing CA."""
        try:
            from cryptography.x509.oid import NameOID
            attrs = self.certificate.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
            return attrs[0].value if attrs else ""
        except Exception:
            return ""

    def dispose(self) -> None:
        """
        Attempt to wipe the private key reference from memory.
        Python's GC cannot guarantee immediate collection, but removing the
        reference reduces the window of exposure.
        """
        # Replace reference — actual bytes may linger in CPython's heap until GC
        # For true zeroisation a C extension would be needed (out of scope here).
        object.__setattr__(self, "private_key", None)
        logger.debug("CertificateBundle.dispose() called — key reference released.")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_certificate(cert_path: str, password: str) -> CertificateBundle:
    """
    Load a PKCS#12 certificate bundle from *cert_path*.

    Parameters
    ----------
    cert_path : absolute or relative path to a .pfx / .p12 file
    password  : plaintext password (never stored or logged)

    Returns
    -------
    CertificateBundle

    Raises
    ------
    CertificateNotFoundError        — file missing
    UnsupportedCertificateFormatError — wrong extension
    IncorrectPasswordError          — bad password
    InvalidCertificateError         — malformed PKCS#12 data
    PrivateKeyMissingError          — bundle has no private key
    """
    cert_path = os.path.abspath(cert_path)
    logger.info("Loading certificate: %s", cert_path)

    # 1. File existence
    ensure_file_exists(cert_path, "Certificate file")

    # 2. Extension check
    _, ext = os.path.splitext(cert_path)
    if ext.lower() not in SUPPORTED_CERT_EXTENSIONS:
        raise UnsupportedCertificateFormatError(
            f"Certificate must be one of {SUPPORTED_CERT_EXTENSIONS}, got '{ext}'."
        )

    # 3. Read raw bytes
    with open(cert_path, "rb") as fh:
        p12_data = fh.read()

    # 4. Decode PKCS#12
    try:
        password_bytes = password.encode("utf-8") if isinstance(password, str) else password
        private_key, certificate, chain = pkcs12.load_key_and_certificates(
            p12_data, password_bytes
        )
    except ValueError as exc:
        # cryptography raises ValueError for wrong password
        if "Invalid password" in str(exc) or "mac verify failure" in str(exc).lower() or "PKCS12" in str(exc):
            raise IncorrectPasswordError(
                "The password supplied for the certificate is incorrect."
            ) from exc
        raise InvalidCertificateError(
            f"Failed to parse certificate file: {exc}"
        ) from exc
    except Exception as exc:
        raise InvalidCertificateError(
            f"Unexpected error reading certificate: {exc}"
        ) from exc
    finally:
        # Wipe plaintext password bytes from local scope ASAP
        password_bytes = None  # type: ignore[assignment]

    # 5. Private key must be present
    if private_key is None:
        raise PrivateKeyMissingError(
            "The certificate file does not contain a private key. "
            "Ensure you are using a full .pfx/.p12 bundle, not a public certificate."
        )

    # 6. Certificate must be present
    if certificate is None:
        raise InvalidCertificateError(
            "The PKCS#12 bundle does not contain a certificate."
        )

    bundle = CertificateBundle(
        private_key=private_key,
        certificate=certificate,
        chain=list(chain) if chain else [],
        friendly_name=sanitise_text(None),  # friendly_name not exposed by cryptography API
    )

    logger.info(
        "Certificate loaded — Subject CN: %s | Issuer CN: %s | Chain certs: %d",
        bundle.subject_cn,
        bundle.issuer_cn,
        len(bundle.chain),
    )
    return bundle
