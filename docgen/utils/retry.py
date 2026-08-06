# coding: utf-8
"""
retry.py — Exponential back-off retry decorator / helper for Gemini API calls.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Errors that indicate a transient overload and warrant a retry
_TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "overloaded", "resource_exhausted")


def call_gemini_with_retry(
    client: Any,
    model: str,
    prompt: str,
    retries: int = 5,
    base_wait: float = 1.0,
) -> Any:
    """
    Call the Gemini generate_content API with exponential back-off.

    Parameters
    ----------
    client    : google.genai.Client instance
    model     : model name string (e.g. "gemini-2.5-flash")
    prompt    : text prompt to send
    retries   : maximum number of attempts before raising
    base_wait : initial wait in seconds (doubles each retry)

    Returns
    -------
    Gemini response object.

    Raises
    ------
    RuntimeError  : Gemini unavailable after all retries.
    Any other exception is re-raised immediately.
    """
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            return client.models.generate_content(
                model    = model,
                contents = prompt,
            )
        except Exception as exc:
            msg = str(exc).upper()
            is_transient = any(m.upper() in msg for m in _TRANSIENT_MARKERS)

            if not is_transient:
                raise   # Non-transient error — surface immediately

            wait = base_wait * (2 ** attempt)
            logger.warning(
                "Gemini transient error (attempt %d/%d): %s — retrying in %.1fs …",
                attempt + 1, retries, exc, wait,
            )
            last_exc = exc
            time.sleep(wait)

    raise RuntimeError(
        f"Gemini unavailable after {retries} retries. Last error: {last_exc}"
    )
