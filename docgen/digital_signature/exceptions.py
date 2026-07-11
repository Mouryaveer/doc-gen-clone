"""
exceptions.py — Custom exceptions for the Turn2Law Digital Signature Engine.

All exceptions inherit from DigitalSignatureError so callers can catch the
whole family with a single except clause.
"""


class DigitalSignatureError(Exception):
    """Base exception for every signing-related error."""


class CertificateNotFoundError(DigitalSignatureError):
    """Raised when the certificate file does not exist or is not readable."""


class InvalidCertificateError(DigitalSignatureError):
    """Raised when the certificate file is malformed or cannot be parsed."""


class CertificateExpiredError(DigitalSignatureError):
    """Raised when the certificate's validity period has elapsed."""


class IncorrectPasswordError(DigitalSignatureError):
    """Raised when the supplied password cannot decrypt the PKCS#12 bundle."""


class PrivateKeyMissingError(DigitalSignatureError):
    """Raised when no private key is found inside the PKCS#12 bundle."""


class InvalidKeyUsageError(DigitalSignatureError):
    """Raised when the certificate's key-usage extension forbids digital signatures."""


class UnsupportedAlgorithmError(DigitalSignatureError):
    """Raised when the certificate uses an algorithm not supported by this engine."""


class UnsupportedCertificateFormatError(DigitalSignatureError):
    """Raised when the certificate file format is not .pfx or .p12."""


class CertificateChainError(DigitalSignatureError):
    """Raised when the certificate chain cannot be validated."""


class SigningFailedError(DigitalSignatureError):
    """Raised when the cryptographic signing operation itself fails."""


class TimestampUnavailableError(DigitalSignatureError):
    """Raised when the RFC 3161 timestamp server is unreachable or returns an error."""


class PDFIntegrityError(DigitalSignatureError):
    """Raised when the PDF file is corrupted or unreadable."""


class VerificationError(DigitalSignatureError):
    """Raised when signature verification encounters an unrecoverable error."""


class SignatureNotFoundError(DigitalSignatureError):
    """Raised when a PDF has no embedded digital signature."""
