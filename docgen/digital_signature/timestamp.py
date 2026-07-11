"""
timestamp.py — RFC 3161 Timestamp Authority (TSA) integration.

Design
------
* Sends a TimeStampReq to the configured TSA URL.
* Returns the raw DER-encoded TimeStampResp token.
* pyHanko's signing layer accepts this token directly.
* If the TSA is unavailable and timestamp is optional, we degrade gracefully
  and log a warning.  If timestamps are mandatory, we raise
  TimestampUnavailableError.

Configuration keys (signature_config.py)
-----------------------------------------
  TIMESTAMP_URL              : TSA endpoint URL
  TIMESTAMP_ENABLED          : bool — skip entirely when False
  TIMESTAMP_TIMEOUT_SECONDS  : HTTP timeout
"""

from __future__ import annotations

import logging
from typing import Optional

from .signature_config import (
    TIMESTAMP_URL,
    TIMESTAMP_ENABLED,
    TIMESTAMP_TIMEOUT_SECONDS,
)
from .exceptions import TimestampUnavailableError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_timestamp_url() -> Optional[str]:
    """
    Return the configured TSA URL if timestamping is enabled, else None.
    pyHanko accepts None as "no timestamp".
    """
    if not TIMESTAMP_ENABLED:
        logger.debug("Timestamping disabled — skipping TSA request.")
        return None

    if not TIMESTAMP_URL:
        logger.warning("TIMESTAMP_ENABLED is True but TIMESTAMP_URL is not set.")
        return None

    logger.info("RFC 3161 timestamp will be requested from: %s", TIMESTAMP_URL)
    return TIMESTAMP_URL


def build_pyhanko_tsa_client():
    """
    Build and return a pyHanko HTTPTimeStamper client, or None if timestamps
    are disabled.

    The client is used in pdf_signer.py and passed to pyHanko's signer.
    """
    url = get_timestamp_url()
    if url is None:
        return None

    try:
        from pyhanko_certvalidator import CertValidationPolicy
        from pyhanko.sign.timestamps import HTTPTimeStamper
        client = HTTPTimeStamper(url, timeout=TIMESTAMP_TIMEOUT_SECONDS)
        logger.info("TSA client created for: %s", url)
        return client
    except ImportError:
        logger.warning(
            "pyhanko_certvalidator not installed — timestamp client unavailable."
        )
        return None
    except Exception as exc:
        logger.warning("Failed to create TSA client: %s", exc)
        if TIMESTAMP_ENABLED:
            raise TimestampUnavailableError(
                f"Could not initialise timestamp client for {url}: {exc}"
            ) from exc
        return None
