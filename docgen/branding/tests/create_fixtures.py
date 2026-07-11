# coding: utf-8
"""
create_fixtures.py -- Generate test fixture images for the branding engine tests.

Run this script once to populate the fixtures/ directory:
    python docgen/branding/tests/create_fixtures.py

It is safe to re-run: existing fixtures are overwritten.
"""

from __future__ import annotations

import pathlib

from PIL import Image

# Resolve the fixtures directory relative to this file so the script can be
# run from any working directory.
FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def make_fixtures_dir() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def save(img: Image.Image, name: str) -> None:
    path = FIXTURES_DIR / name
    fmt = "JPEG" if name.endswith(".jpg") else "PNG"
    img.save(path, format=fmt)
    print(f"  created {path.relative_to(pathlib.Path(__file__).parent.parent.parent.parent)}")


def create_header_600x58() -> None:
    """600×58 RGBA, transparent 10 px border, opaque coloured inner rectangle."""
    img = Image.new("RGBA", (600, 58), (0, 0, 0, 0))  # fully transparent
    # Draw a solid coloured rectangle in the inner 580×38 region (10 px inset)
    inner = Image.new("RGBA", (580, 38), (70, 130, 180, 255))  # steel blue, fully opaque
    img.paste(inner, (10, 10))
    save(img, "header_600x58.png")


def create_footer_600x40() -> None:
    """600×40 RGBA, fully opaque."""
    img = Image.new("RGBA", (600, 40), (200, 200, 200, 255))  # light grey, opaque
    save(img, "footer_600x40.png")


def create_watermark_200x200() -> None:
    """200×200 RGBA, semi-transparent."""
    img = Image.new("RGBA", (200, 200), (255, 0, 0, 128))  # red, 50 % opacity
    save(img, "watermark_200x200.png")


def create_logo_200x80() -> None:
    """200×80 RGBA, fully opaque."""
    img = Image.new("RGBA", (200, 80), (30, 144, 255, 255))  # dodger blue, opaque
    save(img, "logo_200x80.png")


def create_not_a_png() -> None:
    """Small JPEG file used to test the non-PNG rejection path."""
    img = Image.new("RGB", (10, 10), (255, 128, 0))  # orange
    save(img, "not_a_png.jpg")


def create_all_transparent_600x58() -> None:
    """600×58 RGBA where every pixel has alpha=0."""
    img = Image.new("RGBA", (600, 58), (0, 0, 0, 0))
    save(img, "all_transparent_600x58.png")


def main() -> None:
    print("Creating test fixtures …")
    make_fixtures_dir()
    create_header_600x58()
    create_footer_600x40()
    create_watermark_200x200()
    create_logo_200x80()
    create_not_a_png()
    create_all_transparent_600x58()
    print("Done.")


if __name__ == "__main__":
    main()
