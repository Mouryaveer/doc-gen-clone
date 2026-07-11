# coding: utf-8
"""
image_processor.py -- PNG image processing for the Turn2Law Branding Engine.

Trims transparent borders from PNG assets and saves clean copies to the
Profiles Store.

Public API:
    process_image(src_path, dest_path) -> tuple[int, int]
"""

from __future__ import annotations

import os

from PIL import Image

from .exceptions import BrandAssetProcessingError


def process_image(src_path: str, dest_path: str) -> tuple[int, int]:
    """
    Trim fully-transparent border pixels from a PNG image and save the result.

    A "transparent border" is any row or column at the edge of the image where
    every pixel has alpha == 0.

    Parameters
    ----------
    src_path  : Path to the source PNG file.
    dest_path : Absolute path where the processed PNG will be saved.
                The parent directory is created if it does not exist.

    Returns
    -------
    (width_px, height_px) of the output (cropped) image.

    Raises
    ------
    BrandAssetProcessingError
        - If the entire image is transparent (bbox is None after trim).
        - If any OSError or Pillow exception occurs during open/save.
    """
    try:
        img = Image.open(src_path).convert("RGBA")
    except Exception as exc:
        raise BrandAssetProcessingError(
            f"Cannot open image {src_path!r}: {type(exc).__name__}: {exc}"
        ) from exc

    try:
        # Split into channels; get just the alpha channel
        r, g, b, alpha = img.split()

        # getbbox() on the alpha channel returns the bounding box of
        # non-zero (non-transparent) pixels: (left, top, right, bottom)
        bbox = alpha.getbbox()
    except Exception as exc:
        raise BrandAssetProcessingError(
            f"Cannot analyse alpha channel of {src_path!r}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if bbox is None:
        raise BrandAssetProcessingError(
            f"all_transparent: every pixel in {src_path!r} has alpha=0. "
            "Cannot use a fully-transparent image as a brand asset."
        )

    try:
        cropped = img.crop(bbox)
    except Exception as exc:
        raise BrandAssetProcessingError(
            f"Cannot crop {src_path!r} to bbox {bbox}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    # Ensure the destination directory exists
    dest_dir = os.path.dirname(os.path.abspath(dest_path))
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    try:
        cropped.save(dest_path, format="PNG", optimize=False, compress_level=1)
    except Exception as exc:
        raise BrandAssetProcessingError(
            f"Cannot save processed image to {dest_path!r}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    return (cropped.width, cropped.height)
