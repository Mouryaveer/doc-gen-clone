# coding: utf-8
"""
file_utils.py — Text extraction dispatcher.

Supports PDF (PyMuPDF), DOCX (python-docx), and common image formats
(pytesseract OCR).  Raises ValueError for unsupported extensions.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Supported extension sets
_PDF_EXTS   = {".pdf"}
_DOCX_EXTS  = {".docx", ".doc"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


def extract_text(path: str) -> str:
    """
    Extract plain text from *path*.

    Parameters
    ----------
    path : Absolute or relative path to the source file.

    Returns
    -------
    str — extracted text (may be empty for blank/image-only documents).

    Raises
    ------
    ValueError   : Unsupported file extension.
    FileNotFoundError : File does not exist.
    RuntimeError : Extraction library not installed or OCR binary missing.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path!r}")

    ext = os.path.splitext(path)[1].lower()

    if ext in _PDF_EXTS:
        return _extract_pdf(path)
    if ext in _DOCX_EXTS:
        return _extract_docx(path)
    if ext in _IMAGE_EXTS:
        return _extract_image(path)

    raise ValueError(
        f"Unsupported file type: {ext!r}. "
        f"Supported: PDF, DOCX, {', '.join(sorted(_IMAGE_EXTS))}"
    )


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def _extract_pdf(path: str) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError(
            "PyMuPDF is not installed. Run: pip install PyMuPDF"
        )
    text_parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    result = "\n".join(text_parts).strip()
    logger.debug("PDF extracted: %d chars from %s", len(result), path)
    return result


def _extract_docx(path: str) -> str:
    try:
        import docx
    except ImportError:
        raise RuntimeError(
            "python-docx is not installed. Run: pip install python-docx"
        )
    document = docx.Document(path)
    result   = "\n".join(p.text for p in document.paragraphs).strip()
    logger.debug("DOCX extracted: %d chars from %s", len(result), path)
    return result


def _extract_image(path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "pytesseract and/or Pillow are not installed. "
            "Run: pip install pytesseract Pillow  "
            "(also requires Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki)"
        )
    img    = Image.open(path)
    result = pytesseract.image_to_string(img).strip()
    logger.debug("Image OCR extracted: %d chars from %s", len(result), path)
    return result
