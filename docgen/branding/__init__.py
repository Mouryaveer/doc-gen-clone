# coding: utf-8
"""
branding -- Turn2Law Branding Engine public API.

Usage:
    from branding import BrandProfile, BrandMode, resolve_preamble
    from branding import save_profile, load_profile, list_profiles, delete_profile
"""

from .models import BrandMode, BrandProfile, ValidationResult, LayoutParameters
from .exceptions import (
    BrandingEngineError,
    BrandProfileError,
    BrandAssetValidationError,
    BrandAssetProcessingError,
    BrandProfileNotFoundError,
)

# These are imported lazily to avoid circular imports; they will be
# available once the respective modules are created in later tasks.
def resolve_preamble(profile: "BrandProfile") -> str:
    from .branding_engine import resolve_preamble as _resolve
    return _resolve(profile)

def save_profile(profile: "BrandProfile") -> None:
    from .asset_manager import save_profile as _save
    return _save(profile)

def load_profile(profile_id: str) -> "BrandProfile":
    from .asset_manager import load_profile as _load
    return _load(profile_id)

def list_profiles() -> "list[BrandProfile]":
    from .asset_manager import list_profiles as _list
    return _list()

def delete_profile(profile_id: str) -> None:
    from .asset_manager import delete_profile as _delete
    return _delete(profile_id)

__all__ = [
    "BrandMode",
    "BrandProfile",
    "ValidationResult",
    "LayoutParameters",
    "BrandingEngineError",
    "BrandProfileError",
    "BrandAssetValidationError",
    "BrandAssetProcessingError",
    "BrandProfileNotFoundError",
    "resolve_preamble",
    "save_profile",
    "load_profile",
    "list_profiles",
    "delete_profile",
]
