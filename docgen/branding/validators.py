# coding: utf-8
"""
validators.py -- PNG asset validation for the Turn2Law Branding Engine.

Public API:
    validate_asset(path, image_type) -> ValidationResult
"""

from __future__ import annotations

import os

from PIL import Image, UnidentifiedImageError

from .config import CONFIG
from .exceptions import BrandAssetValidationError, BrandProfileError
from .models import ValidationResult

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'

_VALID_IMAGE_TYPES = ("header", "footer", "watermark", "logo")
_MAX_HEADER_HEIGHT_PX = 150
_MAX_FOOTER_HEIGHT_PX = 120


def validate_asset(path: str, image_type: str) -> ValidationResult:
    """
    Validate a PNG asset file before it is processed into a brand profile.

    Parameters
    ----------
    path       : Absolute or relative path to the PNG file.
    image_type : One of "header", "footer", "watermark", "logo".

    Returns
    -------
    ValidationResult on success.

    Raises
    ------
    BrandProfileError          -- image_type is not a recognised value.
    BrandAssetValidationError  -- any validation constraint is violated.
    """
    # Step 1 — validate image_type
    if image_type not in _VALID_IMAGE_TYPES:
        raise BrandProfileError(
            f"Unknown image_type {image_type!r}. "
            f"Must be one of: {_VALID_IMAGE_TYPES}"
        )

    # Step 2 — PNG magic bytes (first 8 bytes)
    try:
        with open(path, "rb") as fh:
            header_bytes = fh.read(8)
    except OSError as exc:
        raise BrandAssetValidationError(
            f"file_unreadable: cannot open {path!r}: {exc}"
        ) from exc

    if header_bytes != _PNG_MAGIC:
        observed_hex = header_bytes.hex() if header_bytes else "(empty)"
        raise BrandAssetValidationError(
            f"not_png: file {path!r} does not start with PNG magic bytes "
            f"(observed first 8 bytes: {observed_hex})"
        )

    # Step 3 — open with Pillow to read dimensions
    try:
        with Image.open(path) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise BrandAssetValidationError(
            f"file_unreadable: Pillow cannot open {path!r}: {exc}"
        ) from exc
    except Exception as exc:
        raise BrandAssetValidationError(
            f"file_unreadable: unexpected error reading {path!r}: {exc}"
        ) from exc

    # Step 4 — minimum width (only enforced for header and footer — full-page-width assets)
    if image_type in ("header", "footer") and width < CONFIG.min_header_width_px:
        raise BrandAssetValidationError(
            f"width_below_minimum: image width {width}px is less than "
            f"minimum {CONFIG.min_header_width_px}px (file: {path!r})"
        )

    # Step 5 — minimum height
    if height < 1:
        raise BrandAssetValidationError(
            f"height_below_minimum: image height {height}px must be at least 1px "
            f"(file: {path!r})"
        )

    # Step 6 — per-type height caps
    if image_type == "header" and height > _MAX_HEADER_HEIGHT_PX:
        raise BrandAssetValidationError(
            f"height_exceeds_maximum: header image height {height}px exceeds "
            f"maximum {_MAX_HEADER_HEIGHT_PX}px (file: {path!r})"
        )
    if image_type == "footer" and height > _MAX_FOOTER_HEIGHT_PX:
        raise BrandAssetValidationError(
            f"height_exceeds_maximum: footer image height {height}px exceeds "
            f"maximum {_MAX_FOOTER_HEIGHT_PX}px (file: {path!r})"
        )

    # Step 7 — file size
    try:
        file_size = os.path.getsize(path)
    except OSError as exc:
        raise BrandAssetValidationError(
            f"file_unreadable: cannot stat {path!r}: {exc}"
        ) from exc

    if file_size > CONFIG.max_asset_bytes:
        raise BrandAssetValidationError(
            f"file_too_large: file size {file_size} bytes exceeds maximum "
            f"{CONFIG.max_asset_bytes} bytes (file: {path!r})"
        )

    # Step 8 — return result
    return ValidationResult(
        width_px=width,
        height_px=height,
        file_size_bytes=file_size,
    )
