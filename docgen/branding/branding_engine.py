# coding: utf-8
"""
branding_engine.py — Top-level orchestrator for the Turn2Law Branding Engine.

Public API
----------
resolve_preamble(profile: BrandProfile) -> str
    Returns the absolute path to the correct LaTeX preamble .tex file.

Modes
-----
TURN2LAW   — returns docgen/layouts/brand_preamble.tex (integrity-checked).
CUSTOM     — validates assets, processes images, generates preamble, caches.
LETTERHEAD — validates full-page PNG, generates preamble, caches.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from .asset_manager import save_profile
from .config import CONFIG
from .exceptions import BrandProfileError, BrandAssetValidationError
from .image_processor import process_image
from .layout_builder import compute_layout, generate_preamble
from .models import BrandMode, BrandProfile
from .validators import validate_asset

logger = logging.getLogger(__name__)

# Module-level SHA-256 hash of Turn2Law brand_preamble.tex,
# recorded on the first call and verified on every subsequent call.
_t2l_preamble_hash: str | None = None

_LAYOUTS_DIR  = Path(__file__).parent.parent / "layouts"
_T2L_PREAMBLE = _LAYOUTS_DIR / "brand_preamble.tex"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_preamble(profile: BrandProfile) -> str:
    """
    Return the absolute path to the correct LaTeX preamble for *profile*.

    Raises BrandProfileError, BrandAssetValidationError, or
    BrandAssetProcessingError on failure.
    """
    if profile.mode == BrandMode.TURN2LAW:
        return _resolve_turn2law()

    if profile.mode == BrandMode.CUSTOM:
        return _resolve_custom(profile)

    if profile.mode == BrandMode.LETTERHEAD:
        return _resolve_letterhead(profile)

    raise BrandProfileError(
        f"Unknown brand mode: {profile.mode!r}. "
        f"Expected one of: {[m.value for m in BrandMode]}"
    )


# ---------------------------------------------------------------------------
# Turn2Law branch
# ---------------------------------------------------------------------------

def _resolve_turn2law() -> str:
    """Return the Turn2Law preamble path after an SHA-256 integrity check."""
    global _t2l_preamble_hash

    preamble_abs = str(_T2L_PREAMBLE.resolve())

    if not _T2L_PREAMBLE.exists():
        raise BrandProfileError(
            f"Turn2Law brand preamble not found at {preamble_abs}. "
            "The docgen/layouts/ directory may be incomplete."
        )

    current_hash = _sha256_file(preamble_abs)

    if _t2l_preamble_hash is None:
        _t2l_preamble_hash = current_hash
        logger.debug("Turn2Law preamble hash recorded: %.16s…", current_hash)
    elif current_hash != _t2l_preamble_hash:
        raise BrandProfileError(
            "turn2law_preamble_modified: the SHA-256 hash of "
            "docgen/layouts/brand_preamble.tex has changed since startup. "
            "Do not modify this file while the application is running."
        )

    logger.info("resolve_preamble(turn2law) -> %s", preamble_abs)
    return preamble_abs


# ---------------------------------------------------------------------------
# Custom branch
# ---------------------------------------------------------------------------

def _resolve_custom(profile: BrandProfile) -> str:
    """Validate, process, and generate a custom brand preamble."""

    # Validate required header path
    if not profile.header_image_path or not profile.header_image_path.strip():
        raise BrandProfileError(
            f"header_image_path is required for custom brand profiles "
            f"(profile_id={profile.profile_id!r})."
        )
    if not os.path.isfile(profile.header_image_path):
        raise BrandProfileError(
            f"header_image_path does not exist: {profile.header_image_path!r} "
            f"(profile_id={profile.profile_id!r})."
        )

    profile_dir     = Path(CONFIG.profiles_dir) / profile.profile_id
    cached_preamble = profile_dir / "brand_preamble.tex"

    # Cache hit: return existing preamble
    if cached_preamble.exists():
        logger.info("resolve_preamble(custom) cache hit -> %s", cached_preamble)
        return str(cached_preamble.resolve())

    # Cache miss: run the full pipeline with atomic cleanup on any failure
    profile_dir.mkdir(parents=True, exist_ok=True)
    files_written: list[str] = []

    try:
        return _run_custom_pipeline(profile, profile_dir, files_written)
    except Exception:
        _cleanup(files_written)
        raise


def _run_custom_pipeline(
    profile:       BrandProfile,
    profile_dir:   Path,
    files_written: list[str],
) -> str:
    """validate → process → layout → generate → xelatex pre-check → save."""

    # Step 1 — Validate all supplied assets
    validate_asset(profile.header_image_path, "header")
    if profile.footer_image_path:
        validate_asset(profile.footer_image_path, "footer")
    if profile.watermark_image_path:
        validate_asset(profile.watermark_image_path, "watermark")
    if profile.logo_image_path:
        validate_asset(profile.logo_image_path, "logo")

    # Step 2 — Process images into the profile directory
    header_dest          = str(profile_dir / "header.png")
    header_w, header_h   = process_image(profile.header_image_path, header_dest)
    files_written.append(header_dest)

    footer_h_px: int | None = None
    if profile.footer_image_path:
        footer_dest     = str(profile_dir / "footer.png")
        _, footer_h_px  = process_image(profile.footer_image_path, footer_dest)
        files_written.append(footer_dest)

    if profile.watermark_image_path:
        wm_dest = str(profile_dir / "watermark.png")
        process_image(profile.watermark_image_path, wm_dest)
        files_written.append(wm_dest)

    if profile.logo_image_path:
        logo_dest = str(profile_dir / "logo.png")
        process_image(profile.logo_image_path, logo_dest)
        files_written.append(logo_dest)

    # Build a patched profile pointing at the processed copies
    processed = BrandProfile(
        profile_id           = profile.profile_id,
        name                 = profile.name,
        mode                 = profile.mode,
        header_image_path    = header_dest,
        footer_image_path    = str(profile_dir / "footer.png")    if footer_h_px is not None else None,
        watermark_image_path = str(profile_dir / "watermark.png") if profile.watermark_image_path else None,
        logo_image_path      = str(profile_dir / "logo.png")      if profile.logo_image_path else None,
        created_at           = profile.created_at,
    )

    # Step 3 — Compute layout
    layout = compute_layout(
        header_h_px = header_h,
        footer_h_px = footer_h_px,
        dpi         = CONFIG.asset_dpi,
    )

    # Step 4 — Generate preamble
    preamble_dest = str(profile_dir / "brand_preamble.tex")
    generate_preamble(processed, layout, preamble_dest)
    files_written.append(preamble_dest)

    # Step 5 — XeLaTeX draftmode syntax check
    _xelatex_precheck(preamble_dest, files_written)

    # Step 6 — Persist profile JSON
    save_profile(profile)

    abs_path = os.path.abspath(preamble_dest)
    logger.info("resolve_preamble(custom) -> %s", abs_path)
    return abs_path


# ---------------------------------------------------------------------------
# Letterhead branch
# ---------------------------------------------------------------------------

def _resolve_letterhead(profile: BrandProfile) -> str:
    """Validate the letterhead PNG and generate a full-page-background preamble."""
    from .complete_letterhead import validate_letterhead, generate_letterhead_preamble

    if not profile.letterhead_image_path or not profile.letterhead_image_path.strip():
        raise BrandProfileError(
            f"letterhead_image_path is required for letterhead branding "
            f"(profile_id={profile.profile_id!r})."
        )
    if not os.path.isfile(profile.letterhead_image_path):
        raise BrandProfileError(
            f"letterhead_image_path does not exist: {profile.letterhead_image_path!r} "
            f"(profile_id={profile.profile_id!r})."
        )

    profile_dir     = Path(CONFIG.profiles_dir) / profile.profile_id
    cached_preamble = profile_dir / "brand_preamble.tex"

    if cached_preamble.exists():
        logger.info("resolve_preamble(letterhead) cache hit -> %s", cached_preamble)
        return str(cached_preamble.resolve())

    profile_dir.mkdir(parents=True, exist_ok=True)
    preamble_dest = str(cached_preamble)

    try:
        info = validate_letterhead(profile.letterhead_image_path)
        generate_letterhead_preamble(info, preamble_dest)
        save_profile(profile)
    except Exception:
        try:
            if os.path.exists(preamble_dest):
                os.remove(preamble_dest)
        except OSError:
            pass
        raise

    abs_path = os.path.abspath(preamble_dest)
    logger.info("resolve_preamble(letterhead) -> %s", abs_path)
    return abs_path


# ---------------------------------------------------------------------------
# XeLaTeX draftmode pre-check
# ---------------------------------------------------------------------------

def _xelatex_precheck(preamble_path: str, files_written: list[str]) -> None:
    r"""
    Run xelatex -draftmode on a minimal wrapper that \inputs the preamble.
    Raises BrandProfileError and removes the preamble if the check fails.
    Silently skips if xelatex is not on PATH or if MiKTeX nags about updates.
    """
    wrapper = (
        r"\documentclass{article}" + "\n"
        r"\input{" + preamble_path.replace("\\", "/") + r"}" + "\n"
        r"\begin{document}\end{document}" + "\n"
    )

    with tempfile.TemporaryDirectory() as tmp:
        tex_file = os.path.join(tmp, "precheck.tex")
        with open(tex_file, "w", encoding="utf-8") as fh:
            fh.write(wrapper)

        cmd = [
            "xelatex", "-draftmode",
            "-interaction=nonstopmode",
            f"-output-directory={tmp}",
            tex_file,
        ]
        try:
            res = subprocess.run(
                cmd, cwd=tmp,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=60,
            )
        except FileNotFoundError:
            logger.warning("xelatex not on PATH — skipping preamble syntax pre-check.")
            return
        except subprocess.TimeoutExpired:
            logger.warning("xelatex pre-check timed out — skipping.")
            return

        if res.returncode != 0:
            combined = (res.stdout or "") + (res.stderr or "")
            # MiKTeX update nag — not a real error
            _nag = ("you have not checked for miktex updates", "miktex: major issue")
            if any(p in combined.lower() for p in _nag) and not res.stdout.strip():
                logger.warning(
                    "xelatex pre-check exited %d due to MiKTeX update nag — skipping.",
                    res.returncode,
                )
                return

            # Real error — clean up and raise
            _cleanup([preamble_path])
            try:
                files_written.remove(preamble_path)
            except ValueError:
                pass

            raise BrandProfileError(
                f"preamble_xelatex_precheck_failed: XeLaTeX draftmode exited "
                f"{res.returncode} for {preamble_path!r}.\n"
                f"Log (last 2000 chars):\n{res.stdout[-2000:]}"
            )

    logger.debug("XeLaTeX pre-check passed for %s", preamble_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _cleanup(paths: list[str]) -> None:
    """Remove files silently — used for atomic failure cleanup."""
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
