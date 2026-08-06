# coding: utf-8
"""
config.py — Application-level configuration.

Loads environment variables from docgen/.env (if present) via python-dotenv.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

# Load .env located next to this file (docgen/.env)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env_path, override=False)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    logger.warning(
        "GEMINI_API_KEY is not set. "
        "AI classification will fail. "
        "Set it in docgen/.env or as an environment variable."
    )
