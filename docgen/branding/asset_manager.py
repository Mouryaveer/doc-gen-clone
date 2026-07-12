# coding: utf-8
"""
asset_manager.py -- Profile persistence for the Turn2Law Branding Engine.

Profiles are stored on disk as JSON files:
  {profiles_dir}/{profile_id}/profile.json

Public API:
    save_profile(profile)       -> None
    load_profile(profile_id)    -> BrandProfile
    list_profiles()             -> list[BrandProfile]
    delete_profile(profile_id)  -> None
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import CONFIG
from .exceptions import BrandProfileNotFoundError
from .models import BrandMode, BrandProfile


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _profiles_root() -> Path:
    """Return the profiles root directory, creating it if necessary."""
    root = Path(CONFIG.profiles_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _profile_dir(profile_id: str) -> Path:
    return _profiles_root() / profile_id


def _profile_json_path(profile_id: str) -> Path:
    return _profile_dir(profile_id) / "profile.json"


def _profile_to_dict(profile: BrandProfile) -> dict[str, Any]:
    return {
        "profile_id":            profile.profile_id,
        "name":                  profile.name,
        "mode":                  profile.mode.value,
        "header_image_path":     profile.header_image_path,
        "footer_image_path":     profile.footer_image_path,
        "watermark_image_path":  profile.watermark_image_path,
        "logo_image_path":       profile.logo_image_path,
        "letterhead_image_path": profile.letterhead_image_path,
        "created_at":            profile.created_at.isoformat(),
    }


def _dict_to_profile(data: dict[str, Any]) -> BrandProfile:
    created_at_str = data.get("created_at", "")
    if created_at_str:
        dt = datetime.fromisoformat(created_at_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    return BrandProfile(
        profile_id           = data["profile_id"],
        name                 = data["name"],
        mode                 = BrandMode(data["mode"]),
        header_image_path    = data.get("header_image_path"),
        footer_image_path    = data.get("footer_image_path"),
        watermark_image_path = data.get("watermark_image_path"),
        logo_image_path      = data.get("logo_image_path"),
        letterhead_image_path = data.get("letterhead_image_path"),
        created_at           = dt,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_profile(profile: BrandProfile) -> None:
    """
    Persist a BrandProfile to disk.

    Creates the profile subdirectory if it does not exist.
    Overwrites any existing profile.json for the same profile_id.
    """
    profile_dir = _profile_dir(profile.profile_id)
    profile_dir.mkdir(parents=True, exist_ok=True)
    json_path = profile_dir / "profile.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(_profile_to_dict(profile), fh, indent=2, ensure_ascii=False)


def load_profile(profile_id: str) -> BrandProfile:
    """
    Load a BrandProfile from disk by profile_id.

    Raises
    ------
    BrandProfileNotFoundError
        If no profile.json exists for the given profile_id.
    """
    json_path = _profile_json_path(profile_id)
    if not json_path.exists():
        raise BrandProfileNotFoundError(
            f"Profile not found: {profile_id!r} "
            f"(expected at {json_path})"
        )
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return _dict_to_profile(data)


def list_profiles() -> list[BrandProfile]:
    """
    Return all saved BrandProfiles sorted by created_at descending.
    Returns an empty list if no profiles exist.
    """
    root = _profiles_root()
    profiles: list[BrandProfile] = []
    for subdir in root.iterdir():
        if not subdir.is_dir():
            continue
        json_path = subdir / "profile.json"
        if not json_path.exists():
            continue
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            profiles.append(_dict_to_profile(data))
        except Exception:
            # Skip corrupt/unreadable profiles silently — don't crash list
            continue
    profiles.sort(key=lambda p: p.created_at, reverse=True)
    return profiles


def delete_profile(profile_id: str) -> None:
    """
    Delete a profile and all its associated files.

    Raises
    ------
    BrandProfileNotFoundError
        If the profile subdirectory does not exist.
    """
    profile_dir = _profile_dir(profile_id)
    if not profile_dir.exists():
        raise BrandProfileNotFoundError(
            f"Profile not found: {profile_id!r} "
            f"(directory {profile_dir} does not exist)"
        )
    shutil.rmtree(profile_dir)
