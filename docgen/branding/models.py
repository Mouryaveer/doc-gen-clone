# coding: utf-8
"""
models.py -- Data models for the Turn2Law Branding Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class BrandMode(str, Enum):
    """Branding mode selector."""
    TURN2LAW   = "turn2law"
    CUSTOM     = "custom"
    LETTERHEAD = "letterhead"   # single full-page PNG background


@dataclass(frozen=True)
class BrandProfile:
    """
    Immutable description of a single branding identity.

    For mode=TURN2LAW all image paths may be None.
    For mode=CUSTOM header_image_path is required; others are optional.
    Validation of required fields happens in branding_engine.resolve_preamble(),
    not here, so all errors are BrandProfileError instances.
    """
    profile_id:           str
    name:                 str
    mode:                 BrandMode
    header_image_path:    Optional[str] = None
    footer_image_path:    Optional[str] = None
    watermark_image_path: Optional[str] = None
    logo_image_path:      Optional[str] = None
    letterhead_image_path: Optional[str] = None   # complete letterhead mode
    created_at:           datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ValidationResult:
    """Result returned by validators.validate_asset() on success."""
    width_px:        int
    height_px:       int
    file_size_bytes: int


@dataclass
class LayoutParameters:
    """
    LaTeX geometry parameters computed from processed image dimensions.
    All values are in PDF points (pt).
    """
    top_margin_pt:    float
    bottom_margin_pt: float
    left_margin_pt:   float   # always 42.0
    right_margin_pt:  float   # always 32.0
    header_height_pt: float   # 0.0 when no header image
    footer_height_pt: float   # 0.0 when no footer image
