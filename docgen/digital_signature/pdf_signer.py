"""
pdf_signer.py — Core PDF signing using pyHanko (PAdES / CMS).

This module is the only place that imports pyHanko.  All other modules in
digital_signature/ are pyHanko-agnostic.

Visible signature appearance
-----------------------------
Matches the reference screenshots:

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Digitally signed by JAGJYOT SINGH                                      │
  │  Date: 2026.07.10 16:24:35 +00'00'                                      │
  │  Reason: Approved   Location: Chennai, India                            │
  └─────────────────────────────────────────────────────────────────────────┘

NO cursive / handwritten watermark.  background_opacity=0.0 ensures a clean box.
"""

from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import Optional, Any, Tuple

from .certificate_loader import CertificateBundle
from .metadata import SignatureMetadata
from .timestamp import build_pyhanko_tsa_client
from .exceptions import SigningFailedError, PDFIntegrityError
from .utils import assert_valid_pdf, build_output_path
from .signature_config import DIGEST_ALGORITHM, SIGNATURE_FIELD_NAME

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def sign_pdf(
    input_pdf:  str,
    output_pdf: Optional[str],
    bundle:     CertificateBundle,
    metadata:   SignatureMetadata,
    cert_path:  str = "",
    password:   str = "",
) -> str:
    """
    Sign *input_pdf* and write the result to *output_pdf*.

    Parameters
    ----------
    input_pdf  : absolute path to the unsigned PDF
    output_pdf : destination path; if None, auto-derived as *_signed.pdf
    bundle     : loaded + validated CertificateBundle (used for metadata only)
    metadata   : SignatureMetadata
    cert_path  : path to .pfx/.p12 (passed to pyHanko's native loader)
    password   : certificate password (cleared after use)

    Returns
    -------
    Absolute path to the signed PDF.
    """
    input_pdf = os.path.abspath(input_pdf)
    assert_valid_pdf(input_pdf)

    if output_pdf is None:
        output_pdf = build_output_path(input_pdf)
    output_pdf = os.path.abspath(output_pdf)

    logger.info("Signing PDF: %s  →  %s", input_pdf, output_pdf)

    metadata.stamp_signing_time()
    metadata.certificate_subject = bundle.subject_cn
    metadata.certificate_issuer  = bundle.issuer_cn
    logger.info("Signing metadata: %s", metadata.as_log_dict())

    try:
        _sign_with_pyhanko(input_pdf, output_pdf, metadata, cert_path, password)
    except SigningFailedError:
        raise
    except Exception as exc:
        raise SigningFailedError(f"Signing operation failed unexpectedly: {exc}") from exc
    finally:
        password = ""  # noqa: F841 — clear local copy

    logger.info("Signed PDF saved: %s", output_pdf)
    return output_pdf


# ---------------------------------------------------------------------------
# pyHanko implementation
# ---------------------------------------------------------------------------

def _sign_with_pyhanko(
    input_pdf:  str,
    output_pdf: str,
    metadata:   SignatureMetadata,
    cert_path:  str,
    password:   str,
) -> None:
    """Sign using pyHanko's SimpleSigner.load_pkcs12() + PdfSigner."""

    # ── imports ──────────────────────────────────────────────────────────
    try:
        from pyhanko.sign.signers import SimpleSigner
        from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata, PdfSigner
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.pdf_utils.reader import PdfFileReader
    except ImportError as exc:
        raise SigningFailedError(
            "pyhanko is not installed. Run: pip install pyhanko"
        ) from exc

    # ── Build signer from PKCS#12 ────────────────────────────────────────
    passphrase: Optional[bytes] = None
    try:
        passphrase = password.encode("utf-8") if isinstance(password, str) else password
        signer = SimpleSigner.load_pkcs12(
            pfx_file   = cert_path,
            passphrase = passphrase,
        )
    except Exception as exc:
        raise SigningFailedError(f"SimpleSigner.load_pkcs12 failed: {exc}") from exc
    finally:
        passphrase = None

    # ── Signature metadata ────────────────────────────────────────────────
    sig_meta = PdfSignatureMetadata(
        field_name   = SIGNATURE_FIELD_NAME,
        md_algorithm = DIGEST_ALGORITHM,
        name         = metadata.signer_name or None,
        reason       = metadata.reason or None,
        location     = metadata.location or None,
        contact_info = metadata.contact or None,
        certify      = False,
    )

    # ── TSA client ────────────────────────────────────────────────────────
    tsa_client = build_pyhanko_tsa_client()

    # ── Open PDF ──────────────────────────────────────────────────────────
    try:
        with open(input_pdf, "rb") as fh:
            pdf_bytes = fh.read()
        reader = PdfFileReader(BytesIO(pdf_bytes))
        writer = IncrementalPdfFileWriter(BytesIO(pdf_bytes))
    except Exception as exc:
        raise PDFIntegrityError(f"Cannot open PDF for signing: {exc}") from exc

    # ── Build field spec + stamp style ────────────────────────────────────
    try:
        field_spec, stamp_style = _build_field_spec(metadata, reader)
    except Exception as exc:
        raise SigningFailedError(f"Failed to build signature field spec: {exc}") from exc

    # ── Sign ──────────────────────────────────────────────────────────────
    try:
        output_buf = BytesIO()
        pdf_signer_obj = PdfSigner(
            signature_meta = sig_meta,
            signer         = signer,
            timestamper    = tsa_client,
            stamp_style    = stamp_style,
            new_field_spec = field_spec,
        )
        pdf_signer_obj.sign_pdf(writer, output=output_buf)
    except Exception as exc:
        raise SigningFailedError(f"PdfSigner.sign_pdf failed: {exc}") from exc

    # ── Write output ──────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_pdf) or ".", exist_ok=True)
    with open(output_pdf, "wb") as fh:
        fh.write(output_buf.getvalue())


# ---------------------------------------------------------------------------
# Signature field + appearance builder
# ---------------------------------------------------------------------------

def _build_field_spec(
    metadata: SignatureMetadata,
    reader: Any,
) -> Tuple[Any, Optional[Any]]:
    """
    Return (SigFieldSpec, stamp_style | None).

    Visible appearance — clean box, no cursive watermark:
      Digitally signed by %(signer)s
      Date: %(ts)s
      Reason: ...
      Location: ...
    """
    from pyhanko.sign.fields import SigFieldSpec, VisibleSigSettings
    from pyhanko.stamp import TextStampStyle

    vc = metadata.visible_config

    # ── Page index ────────────────────────────────────────────────────────
    try:
        total_pages = int(reader.trailer["/Root"]["/Pages"]["/Count"])
    except Exception:
        total_pages = 1
    page_index = vc.page if vc.page >= 0 else total_pages + vc.page
    page_index = max(0, min(page_index, total_pages - 1))

    # ── Invisible mode ────────────────────────────────────────────────────
    if not metadata.visible:
        return (
            SigFieldSpec(
                sig_field_name = SIGNATURE_FIELD_NAME,
                on_page        = 0,
                box            = (0, 0, 0, 0),
            ),
            None,
        )

    # ── Stamp text (Adobe Acrobat-style) ──────────────────────────────────
    # %(signer)s  →  signer's Common Name from certificate
    # %(ts)s      →  signing timestamp (formatted by timestamp_format)
    lines = ["Digitally signed by %(signer)s", "Date: %(ts)s"]
    if metadata.reason:
        lines.append(f"Reason: {metadata.reason}")
    if metadata.location:
        lines.append(f"Location: {metadata.location}")

    stamp_style = TextStampStyle(
        stamp_text         = "\n".join(lines),
        timestamp_format   = "%Y.%m.%d %H:%M:%S +00'00'",
        border_width       = 0,    # no rectangle border
        background_opacity = 0.0,  # transparent — eliminates any watermark tint
    )

    vis_settings = VisibleSigSettings(
        rotate_with_page     = True,
        scale_with_page_zoom = True,
    )

    field_spec = SigFieldSpec(
        sig_field_name       = SIGNATURE_FIELD_NAME,
        on_page              = page_index,
        box                  = (vc.x1, vc.y1, vc.x2, vc.y2),
        visible_sig_settings = vis_settings,
    )

    return field_spec, stamp_style
