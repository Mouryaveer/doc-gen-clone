# coding: utf-8
"""
classify.py — Document type classifier using Google Gemini 2.5 Flash.

Sends the first 3000 characters of extracted text to Gemini and maps the
response to one of the six supported document type labels.  Uses exponential
back-off retry for transient 503/overload errors.
"""

from __future__ import annotations

import logging

from google import genai

from config import GEMINI_API_KEY, MODEL_NAME
from utils.retry import call_gemini_with_retry

logger = logging.getLogger(__name__)

# Single shared client — created once at import time.
# If GEMINI_API_KEY is None/empty the import still succeeds; the error will
# surface at classify time with a clear message.
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. "
                "Create docgen/.env with GEMINI_API_KEY=<your-key>."
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


ALLOWED_TYPES = (
    "NDA",
    "Offer_Letter",
    "Contract",
    "MOU",
    "IP_Agreement",
    "Onboarding_Letter",
)


def _normalize(raw: str) -> str:
    """
    Map the raw Gemini response to a canonical ALLOWED_TYPES label.

    Raises ValueError if no match can be found.
    """
    candidate = (raw or "").strip()

    # Exact match first
    if candidate in ALLOWED_TYPES:
        return candidate

    # Case-insensitive substring match
    lower = candidate.lower()
    for doc_type in ALLOWED_TYPES:
        if doc_type.lower() in lower:
            return doc_type

    raise ValueError(
        f"Gemini returned unrecognised document type: {candidate!r}. "
        f"Expected one of: {ALLOWED_TYPES}"
    )


def classify_document(text: str) -> str:
    """
    Classify *text* into one of the six supported document types.

    Parameters
    ----------
    text : Extracted plain text (first 3000 chars are sent to Gemini).

    Returns
    -------
    str — one of ALLOWED_TYPES.

    Raises
    ------
    ValueError  : Gemini returned an unrecognised label.
    RuntimeError: Gemini unavailable after retries.
    """
    prompt = (
        f"Classify this document into exactly one of:\n"
        f"{', '.join(ALLOWED_TYPES)}.\n\n"
        f"Do NOT return Other.\n"
        f"Choose the closest match.\n"
        f"Return only the label.\n\n"
        f"Document:\n{text[:3000]}"
    )

    client   = _get_client()
    response = call_gemini_with_retry(client, MODEL_NAME, prompt)
    result   = _normalize(response.text)
    logger.info("Classified as: %s", result)
    return result
