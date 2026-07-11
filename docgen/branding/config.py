# coding: utf-8
"""
config.py -- Configuration singleton for the Turn2Law Branding Engine.

All tunable values are read from environment variables at import time.
Import CONFIG from this module to access all settings.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from .exceptions import BrandProfileError

# The default profiles directory lives inside docgen/branding/profiles/
_BRANDING_DIR = Path(__file__).parent  # docgen/branding/


def _read_int_env(var: str, default: int) -> int:
    raw = os.environ.get(var)
    if raw is None:
        return default
    try:
        val = int(raw)
        if val <= 0:
            raise ValueError
        return val
    except (ValueError, TypeError):
        raise BrandProfileError(
            f"Environment variable {var}={raw!r} cannot be parsed as a positive integer."
        )


def _read_float_env(var: str, default: float) -> float:
    raw = os.environ.get(var)
    if raw is None:
        return default
    try:
        val = float(raw)
        if val <= 0:
            raise ValueError
        return val
    except (ValueError, TypeError):
        raise BrandProfileError(
            f"Environment variable {var}={raw!r} cannot be parsed as a positive number."
        )


@dataclass(frozen=True)
class BrandingConfig:
    profiles_dir: str
    max_asset_bytes: int
    min_header_width_px: int
    asset_dpi: float


def _build_config() -> BrandingConfig:
    profiles_dir = os.environ.get(
        "BRAND_PROFILES_DIR",
        str(_BRANDING_DIR / "profiles"),
    )
    max_asset_bytes = _read_int_env("BRAND_MAX_ASSET_BYTES", 5_242_880)
    min_header_width_px = _read_int_env("BRAND_MIN_HEADER_WIDTH_PX", 595)
    asset_dpi = _read_float_env("BRAND_ASSET_DPI", 96.0)
    return BrandingConfig(
        profiles_dir=profiles_dir,
        max_asset_bytes=max_asset_bytes,
        min_header_width_px=min_header_width_px,
        asset_dpi=asset_dpi,
    )


CONFIG: BrandingConfig = _build_config()
