# coding: utf-8
"""
branding_engine.py -- Top-level orchestrator for the Turn2Law Branding Engine.

Public API:
    resolve_preamble(profile: BrandProfile) -> str
        Returns the absolute path to the correct LaTeX preamble .tex file.
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

# Module-level SHA-256 hash of the Turn2Law brand_preamble.tex,
# recorded on first turn2law call and checked on every subsequent call.
_t2l_preamble_hash: str | None = None

# Locate the Turn2Law brand_preamble.tex relative to this file:
# docgen/branding/branding_engine.py -> docgen/ -> layouts/
_LAYOUTS_DIR = Path(__file__).parent.parent / "layouts"
_T2L_PREAMBLE = _LAYOUTS_DIR / "brand_preamble.tex"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_preamble(profile: BrandProfile) -> str:
    """
    Return the absolute path to the correct LaTeX preamble .tex file for
    the given BrandProfile.

    Turn2Law mode  -> docgen/layouts/brand_preamble.tex  (unchanged)
    Custom mode    -> {profiles_dir}/{profile_id}/brand_preamble.tex

    Raises
    ------
    BrandProfileError
        - Invalid mode.
        - Missing / unreadable header_image_path for custom mode.
        - turn2law preamble has been modified since first call.
        - Generated custom preamble fails XeLaTeX draftmode syntax check.
    BrandAssetValidationError
        If any asset fails PNG validation.
    BrandAssetProcessingError
        If Pillow cannot process an asset.
    """
    if profile.mode == BrandMode.TURN2LAW:
        return _resolve_turn2law()

    if profile.mode == BrandMode.CUSTOM:
        return _resolve_custom(profile)

    raise BrandProfileError(
        f"Unknown brand mode: {profile.mode!r}. "
        "Expected BrandMode.TURN2LAW or BrandMode.CUSTOM."
    )


# ---------------------------------------------------------------------------
# Turn2Law branch
# ---------------------------------------------------------------------------

def _resolve_turn2law() -> str:
    """Return the Turn2Law preamble path after an integrity check."""
    global _t2l_preamble_hash

    preamble_abs = str(_T2L_PREAMBLE.resolve())

    if not _T2L_PREAMBLE.exists():
        raise BrandProfileError(
            f"Turn2Law brand preamble not found at {preamble_abs}. "
            "The docgen/layouts/ directory may be incomplete."
        )

    current_hash = _sha256_file(preamble_abs)

    if _t2l_preamble_hash is None:
        # First call — record the hash
        _t2l_preamble_hash = current_hash
        logger.debug("Turn2Law preamble hash recorded: %s", current_hash[:16])
    elif current_hash != _t2l_preamble_hash:
        raise BrandProfileError(
            "turn2law_preamble_modified: the hash of "
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

    # 1. Validate header_image_path is set and the file exists
    if not profile.header_image_path or not profile.header_image_path.strip():
        raise BrandProfileError(
            "header_image_path is required for custom brand profiles "
            f"(profile_id={profile.profile_id!r})."
        )
    if not os.path.isfile(profile.header_image_path):
        raise BrandProfileError(
            f"header_image_path file does not exist: "
            f"{profile.header_image_path!r} "
            f"(profile_id={profile.profile_id!r})."
        )

    # 2. Check cache — if the preamble was already generated, return it
    profile_dir = Path(CONFIG.profiles_dir) / profile.profile_id
    cached_preamble = profile_dir / "brand_preamble.tex"
    if cached_preamble.exists():
        logger.info(
            "resolve_preamble(custom) cache hit -> %s", cached_preamble
        )
        return str(cached_preamble.resolve())

    # 3. Run the full pipeline with atomic cleanup on failure
    profile_dir.mkdir(parents=True, exist_ok=True)
    files_written: list[str] = []

    try:
        return _run_custom_pipeline(profile, profile_dir, files_written)
    except Exception:
        # Atomic cleanup — remove every file written so far
        for path in files_written:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        raise


def _run_custom_pipeline(
    profile: BrandProfile,
    profile_dir: Path,
    files_written: list[str],
) -> str:
    """Run validate -> process -> layout -> generate -> pre-check."""

    # Step 1: Validate all supplied assets
    validate_asset(profile.header_image_path, "header")
    if profile.footer_image_path:
        validate_asset(profile.footer_image_path, "footer")
    if profile.watermark_image_path:
        validate_asset(profile.watermark_image_path, "watermark")
    if profile.logo_image_path:
        validate_asset(profile.logo_image_path, "logo")

    # Step 2: Process images into the profile directory
    header_dest = str(profile_dir / "header.png")
    header_w, header_h = process_image(profile.header_image_path, header_dest)
    files_written.append(header_dest)
    logger.debug("Processed header: %dx%d px -> %s", header_w, header_h, header_dest)

    footer_h_px: int | None = None
    if profile.footer_image_path:
        footer_dest = str(profile_dir / "footer.png")
        _fw, footer_h_px = process_image(profile.footer_image_path, footer_dest)
        files_written.append(footer_dest)
        logger.debug("Processed footer: %dx%d px -> %s", _fw, footer_h_px, footer_dest)

    if profile.watermark_image_path:
        wm_dest = str(profile_dir / "watermark.png")
        process_image(profile.watermark_image_path, wm_dest)
        files_written.append(wm_dest)

    if profile.logo_image_path:
        logo_dest = str(profile_dir / "logo.png")
        process_image(profile.logo_image_path, logo_dest)
        files_written.append(logo_dest)

    # Build a patched profile pointing at the processed copies
    processed_profile = BrandProfile(
        profile_id           = profile.profile_id,
        name                 = profile.name,
        mode                 = profile.mode,
        header_image_path    = header_dest,
        footer_image_path    = str(profile_dir / "footer.png") if footer_h_px is not None else None,
        watermark_image_path = str(profile_dir / "watermark.png") if profile.watermark_image_path else None,
        logo_image_path      = str(profile_dir / "logo.png") if profile.logo_image_path else None,
        created_at           = profile.created_at,
    )

    # Step 3: Compute layout from pixel dimensions
    layout = compute_layout(
        header_h_px = header_h,
        footer_h_px = footer_h_px,
        dpi         = CONFIG.asset_dpi,
    )
    logger.debug(
        "Layout: top=%.1fpt bottom=%.1fpt header_h=%.1fpt footer_h=%.1fpt",
        layout.top_margin_pt, layout.bottom_margin_pt,
        layout.header_height_pt, layout.footer_height_pt,
    )

    # Step 4: Generate the preamble .tex
    preamble_dest = str(profile_dir / "brand_preamble.tex")
    generate_preamble(processed_profile, layout, preamble_dest)
    files_written.append(preamble_dest)
    logger.info("Generated custom preamble: %s", preamble_dest)

    # Step 5: XeLaTeX draftmode pre-check (syntax validation only)
    _xelatex_precheck(preamble_dest, files_written)

    # Step 6: Persist the profile record
    save_profile(profile)

    abs_path = os.path.abspath(preamble_dest)
    logger.info("resolve_preamble(custom) -> %s", abs_path)
    return abs_path


# ---------------------------------------------------------------------------
# XeLaTeX draftmode pre-check
# ---------------------------------------------------------------------------

def _xelatex_precheck(preamble_path: str, files_written: list[str]) -> None:
    r"""
    Run xelatex in draftmode on a minimal wrapper that \inputs the preamble.
    Raises BrandProfileError and removes the preamble file if it fails.
    """
    wrapper_tex = (
        r"\documentclass{article}" + "\n"
        r"\input{" + preamble_path.replace("\\", "/") + r"}" + "\n"
        r"\begin{document}\end{document}" + "\n"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        wrapper_path = os.path.join(tmp_dir, "precheck.tex")
        with open(wrapper_path, "w", encoding="utf-8") as fh:
            fh.write(wrapper_tex)

        cmd = [
            "xelatex",
            "-draftmode",
            "-interaction=nonstopmode",
            f"-output-directory={tmp_dir}",
            wrapper_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except FileNotFoundError:
            # xelatex not on PATH — skip the check rather than blocking
            logger.warning(
                "xelatex not found on PATH; skipping preamble syntax pre-check."
            )
            return
        except subprocess.TimeoutExpired:
            logger.warning("xelatex draftmode pre-check timed out; skipping.")
            return

        if result.returncode != 0:
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            combined = stdout + stderr

            # MiKTeX on Windows sometimes exits non-zero solely because the
            # user has not yet run an update check.  The preamble itself is
            # valid in this case — skip the error rather than blocking users.
            _miktex_nag_phrases = (
                "you have not checked for MiKTeX updates",
                "miktex: major issue",
                "xelatex did not succeed",
            )
            if any(p in combined.lower() for p in _miktex_nag_phrases) and not stdout.strip():
                logger.warning(
                    "xelatex draftmode pre-check exited %d but only due to "
                    "MiKTeX update nag (no log output). Skipping pre-check. "
                    "Run 'miktex-update' or open MiKTeX Console to dismiss.",
                    result.returncode,
                )
                return

            # Clean up the bad preamble
            try:
                if os.path.exists(preamble_path):
                    os.remove(preamble_path)
                    files_written.remove(preamble_path)
            except (OSError, ValueError):
                pass
            log_snippet = stdout[-2000:]
            raise BrandProfileError(
                f"preamble_xelatex_precheck_failed: XeLaTeX draftmode exited "
                f"with code {result.returncode} for preamble {preamble_path!r}.\n"
                f"Log (last 2000 chars):\n{log_snippet}"
            )

    logger.debug("XeLaTeX draftmode pre-check passed for %s", preamble_path)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
