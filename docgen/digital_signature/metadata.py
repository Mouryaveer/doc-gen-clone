"""
metadata.py — Signature metadata model.

SignatureMetadata is passed through the entire signing pipeline.
All fields that end up in the PDF signature dictionary or visible annotation
are stored here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .signature_config import DIGEST_ALGORITHM, VisibleSignatureConfig, DEFAULT_VISIBLE_CONFIG
from .utils import sanitise_text, utc_now_string


@dataclass
class SignatureMetadata:
    """
    All user-supplied and derived fields that describe a signing operation.

    Mandatory
    ---------
    signer_name : Display name shown in the visible signature box and in the
                  PDF signature dictionary (e.g. "JAGJYOT SINGH").

    Optional
    --------
    reason   : e.g. "Approved", "I am the author of this document"
    location : e.g. "Chennai, India"
    contact  : e.g. signer's email address
    """
    # -- User-supplied ------------------------------------------------
    signer_name: str
    reason:   Optional[str] = None
    location: Optional[str] = None
    contact:  Optional[str] = None

    # -- Derived at signing time (filled in by pdf_signer.py) ---------
    signing_time:        Optional[datetime] = field(default=None, init=False)
    certificate_subject: Optional[str]      = field(default=None, init=False)
    certificate_issuer:  Optional[str]      = field(default=None, init=False)
    digest_algorithm:    str                = field(default=DIGEST_ALGORITHM, init=False)
    signing_algorithm:   Optional[str]      = field(default=None, init=False)

    # -- Appearance ---------------------------------------------------
    visible: bool = True                          # draw visible signature box?
    visible_config: VisibleSignatureConfig = field(
        default_factory=lambda: VisibleSignatureConfig()
    )

    # -----------------------------------------------------------------

    def __post_init__(self) -> None:
        self.signer_name = sanitise_text(self.signer_name) or "Unknown Signer"
        self.reason   = sanitise_text(self.reason)   or None
        self.location = sanitise_text(self.location) or None
        self.contact  = sanitise_text(self.contact)  or None

    def stamp_signing_time(self) -> None:
        """Record the current UTC moment as the signing time."""
        self.signing_time = datetime.now(tz=timezone.utc)

    @property
    def signing_time_str(self) -> str:
        """Human-readable signing timestamp, or empty string if not yet set."""
        if self.signing_time is None:
            return ""
        # Format: 2026.07.10 16:24:35 +05'30'  (matches the PDF viewer display)
        return self.signing_time.strftime("%Y.%m.%d %H:%M:%S +00'00'")

    def as_log_dict(self) -> dict:
        """
        Safe dict for logging — deliberately excludes any cryptographic secrets.
        """
        return {
            "signer_name":        self.signer_name,
            "reason":             self.reason,
            "location":           self.location,
            "contact":            self.contact,
            "signing_time":       self.signing_time_str,
            "certificate_subject": self.certificate_subject,
            "certificate_issuer":  self.certificate_issuer,
            "digest_algorithm":    self.digest_algorithm,
            "signing_algorithm":   self.signing_algorithm,
            "visible":             self.visible,
        }
