"""
digital_signature — Turn2Law PDF Digital Signature Engine.

Public API (everything else is internal):

    from digital_signature.signer import sign_document, sign_pdf_file, SigningRequest
    from digital_signature.verification import verify_pdf, verify_pdf_all, VerificationStatus
    from digital_signature.exceptions import DigitalSignatureError   # base class
    from digital_signature.signature_config import VisibleSignatureConfig

Quick start
-----------
    from digital_signature.signer import sign_pdf_file

    signed = sign_pdf_file(
        pdf_path    = "output.pdf",
        cert_path   = "company.pfx",
        password    = "secret",
        signer_name = "JAGJYOT SINGH",
        reason      = "Approved",
        location    = "Chennai, India",
    )
    # → "output_signed.pdf"
"""

from .signer import sign_document, sign_pdf_file, SigningRequest
from .verification import verify_pdf, verify_pdf_all, VerificationStatus, VerificationResult
from .exceptions import (
    DigitalSignatureError,
    CertificateNotFoundError,
    InvalidCertificateError,
    CertificateExpiredError,
    IncorrectPasswordError,
    PrivateKeyMissingError,
    InvalidKeyUsageError,
    UnsupportedAlgorithmError,
    UnsupportedCertificateFormatError,
    SigningFailedError,
    TimestampUnavailableError,
    PDFIntegrityError,
    VerificationError,
    SignatureNotFoundError,
)
from .signature_config import VisibleSignatureConfig, DIGEST_ALGORITHM

__all__ = [
    # High-level API
    "sign_document",
    "sign_pdf_file",
    "SigningRequest",
    "verify_pdf",
    "verify_pdf_all",
    "VerificationStatus",
    "VerificationResult",
    # Config
    "VisibleSignatureConfig",
    "DIGEST_ALGORITHM",
    # Exceptions
    "DigitalSignatureError",
    "CertificateNotFoundError",
    "InvalidCertificateError",
    "CertificateExpiredError",
    "IncorrectPasswordError",
    "PrivateKeyMissingError",
    "InvalidKeyUsageError",
    "UnsupportedAlgorithmError",
    "UnsupportedCertificateFormatError",
    "SigningFailedError",
    "TimestampUnavailableError",
    "PDFIntegrityError",
    "VerificationError",
    "SignatureNotFoundError",
]
