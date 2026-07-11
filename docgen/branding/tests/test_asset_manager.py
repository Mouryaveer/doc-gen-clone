# coding: utf-8
"""
test_asset_manager.py -- Unit tests for docgen/branding/asset_manager.py

Covers:
  - save_profile / load_profile round-trip
  - overwrite existing profile.json without touching image files
  - list_profiles sort order (created_at descending)
  - delete_profile removes the subdirectory
  - BrandProfileNotFoundError when profile_id is missing
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from docgen.branding.models import BrandMode, BrandProfile
from docgen.branding.exceptions import BrandProfileNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(
    profile_id: str = "test-profile",
    name: str = "Test Profile",
    mode: BrandMode = BrandMode.TURN2LAW,
    created_at: datetime | None = None,
) -> BrandProfile:
    if created_at is None:
        created_at = datetime.now(timezone.utc)
    return BrandProfile(
        profile_id=profile_id,
        name=name,
        mode=mode,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def profiles_dir(tmp_path, monkeypatch):
    """
    Override CONFIG.profiles_dir to use a fresh temp directory per test.
    We patch via monkeypatch so CONFIG stays frozen (we replace the attr on
    the module-level singleton via object.__setattr__ on the frozen dataclass).
    """
    import docgen.branding.config as cfg_mod
    import docgen.branding.asset_manager as am_mod

    new_dir = str(tmp_path / "profiles")
    # BrandingConfig is frozen=True so we use object.__setattr__
    object.__setattr__(cfg_mod.CONFIG, "profiles_dir", new_dir)
    yield Path(new_dir)
    # Restore original value (best-effort; won't matter for tmp_path isolation)
    object.__setattr__(cfg_mod.CONFIG, "profiles_dir", new_dir)


# ---------------------------------------------------------------------------
# save_profile / load_profile round-trip
# ---------------------------------------------------------------------------

class TestSaveAndLoad:
    def test_round_trip_turn2law(self, profiles_dir):
        """A saved TURN2LAW profile is loaded back with identical fields."""
        from docgen.branding.asset_manager import save_profile, load_profile

        original = _make_profile()
        save_profile(original)

        loaded = load_profile(original.profile_id)
        assert loaded.profile_id == original.profile_id
        assert loaded.name == original.name
        assert loaded.mode == BrandMode.TURN2LAW
        assert loaded.header_image_path is None
        assert loaded.created_at.tzinfo is not None  # must be timezone-aware

    def test_round_trip_custom_with_paths(self, profiles_dir):
        """A CUSTOM profile with all image paths survives serialisation."""
        from docgen.branding.asset_manager import save_profile, load_profile

        original = BrandProfile(
            profile_id="custom-1",
            name="Custom One",
            mode=BrandMode.CUSTOM,
            header_image_path="/tmp/header.png",
            footer_image_path="/tmp/footer.png",
            watermark_image_path="/tmp/watermark.png",
            logo_image_path="/tmp/logo.png",
        )
        save_profile(original)
        loaded = load_profile("custom-1")

        assert loaded.mode == BrandMode.CUSTOM
        assert loaded.header_image_path == "/tmp/header.png"
        assert loaded.footer_image_path == "/tmp/footer.png"
        assert loaded.watermark_image_path == "/tmp/watermark.png"
        assert loaded.logo_image_path == "/tmp/logo.png"

    def test_created_at_utc_preserved(self, profiles_dir):
        """created_at round-trips with UTC timezone attached."""
        from docgen.branding.asset_manager import save_profile, load_profile

        ts = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        profile = _make_profile(created_at=ts)
        save_profile(profile)
        loaded = load_profile(profile.profile_id)

        assert loaded.created_at == ts
        assert loaded.created_at.tzinfo == timezone.utc

    def test_naive_created_at_gains_utc(self, profiles_dir, tmp_path):
        """
        If profile.json contains a naive ISO datetime (no timezone offset),
        load_profile must attach UTC.
        """
        from docgen.branding.asset_manager import load_profile

        profile_id = "naive-dt"
        profile_dir = profiles_dir / profile_id
        profile_dir.mkdir(parents=True)
        json_path = profile_dir / "profile.json"
        # Write a naive datetime manually
        data = {
            "profile_id": profile_id,
            "name": "Naive",
            "mode": "turn2law",
            "header_image_path": None,
            "footer_image_path": None,
            "watermark_image_path": None,
            "logo_image_path": None,
            "created_at": "2024-01-01T00:00:00",  # naive — no +00:00
        }
        json_path.write_text(json.dumps(data), encoding="utf-8")

        loaded = load_profile(profile_id)
        assert loaded.created_at.tzinfo is not None
        assert loaded.created_at.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Overwrite behaviour (R7.7)
# ---------------------------------------------------------------------------

class TestOverwrite:
    def test_overwrite_does_not_delete_image_files(self, profiles_dir):
        """
        Calling save_profile for an existing profile_id overwrites profile.json
        but leaves any other files in the directory untouched.
        """
        from docgen.branding.asset_manager import save_profile, load_profile

        profile = _make_profile("overwrite-me")
        save_profile(profile)

        # Simulate a processed image file already in the directory
        img_file = profiles_dir / "overwrite-me" / "header.png"
        img_file.write_bytes(b"fake-png-data")

        # Save again with an updated name
        updated = BrandProfile(
            profile_id="overwrite-me",
            name="Updated Name",
            mode=BrandMode.TURN2LAW,
            created_at=profile.created_at,
        )
        save_profile(updated)

        # The image file must still be there
        assert img_file.exists()
        # The profile name must be updated
        loaded = load_profile("overwrite-me")
        assert loaded.name == "Updated Name"

    def test_profile_json_content_is_valid_json(self, profiles_dir):
        """The written profile.json parses as valid JSON."""
        from docgen.branding.asset_manager import save_profile

        profile = _make_profile("json-check")
        save_profile(profile)

        json_path = profiles_dir / "json-check" / "profile.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["profile_id"] == "json-check"
        assert data["mode"] == "turn2law"


# ---------------------------------------------------------------------------
# list_profiles (R7.4)
# ---------------------------------------------------------------------------

class TestListProfiles:
    def test_empty_list_when_no_profiles(self, profiles_dir):
        """list_profiles returns [] when no profiles have been saved."""
        from docgen.branding.asset_manager import list_profiles

        result = list_profiles()
        assert result == []

    def test_list_returns_all_profiles(self, profiles_dir):
        """list_profiles returns one entry per saved profile."""
        from docgen.branding.asset_manager import save_profile, list_profiles

        p1 = _make_profile("p1", created_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
        p2 = _make_profile("p2", created_at=datetime(2024, 2, 1, tzinfo=timezone.utc))
        save_profile(p1)
        save_profile(p2)

        result = list_profiles()
        assert len(result) == 2

    def test_list_sorted_descending(self, profiles_dir):
        """list_profiles sorts by created_at descending (newest first)."""
        from docgen.branding.asset_manager import save_profile, list_profiles

        older = _make_profile("older", created_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
        newer = _make_profile("newer", created_at=datetime(2024, 6, 1, tzinfo=timezone.utc))
        save_profile(older)
        save_profile(newer)

        result = list_profiles()
        assert result[0].profile_id == "newer"
        assert result[1].profile_id == "older"

    def test_list_creates_profiles_dir_if_missing(self, tmp_path, monkeypatch):
        """list_profiles creates the profiles directory if it doesn't exist."""
        import docgen.branding.config as cfg_mod

        missing_dir = str(tmp_path / "does-not-exist" / "profiles")
        object.__setattr__(cfg_mod.CONFIG, "profiles_dir", missing_dir)
        try:
            from docgen.branding.asset_manager import list_profiles
            result = list_profiles()
            assert result == []
            assert Path(missing_dir).exists()
        finally:
            object.__setattr__(cfg_mod.CONFIG, "profiles_dir", missing_dir)


# ---------------------------------------------------------------------------
# delete_profile (R7.5)
# ---------------------------------------------------------------------------

class TestDeleteProfile:
    def test_delete_removes_directory(self, profiles_dir):
        """delete_profile removes the entire profile subdirectory."""
        from docgen.branding.asset_manager import save_profile, delete_profile

        profile = _make_profile("to-delete")
        save_profile(profile)
        profile_dir = profiles_dir / "to-delete"
        assert profile_dir.exists()

        delete_profile("to-delete")
        assert not profile_dir.exists()

    def test_delete_removes_image_files_too(self, profiles_dir):
        """delete_profile removes image files inside the profile directory."""
        from docgen.branding.asset_manager import save_profile, delete_profile

        profile = _make_profile("img-cleanup")
        save_profile(profile)

        # Plant a fake image file
        img = profiles_dir / "img-cleanup" / "header.png"
        img.write_bytes(b"fake")
        assert img.exists()

        delete_profile("img-cleanup")
        assert not (profiles_dir / "img-cleanup").exists()

    def test_delete_missing_raises(self, profiles_dir):
        """delete_profile raises BrandProfileNotFoundError for unknown IDs."""
        from docgen.branding.asset_manager import delete_profile

        with pytest.raises(BrandProfileNotFoundError, match="nonexistent"):
            delete_profile("nonexistent")


# ---------------------------------------------------------------------------
# load_profile — missing profile (R7.3)
# ---------------------------------------------------------------------------

class TestLoadProfileNotFound:
    def test_load_missing_raises(self, profiles_dir):
        """load_profile raises BrandProfileNotFoundError for unknown IDs."""
        from docgen.branding.asset_manager import load_profile

        with pytest.raises(BrandProfileNotFoundError, match="ghost-profile"):
            load_profile("ghost-profile")

    def test_dir_exists_but_no_json_raises(self, profiles_dir):
        """
        If the profile directory exists but profile.json is absent,
        load_profile still raises BrandProfileNotFoundError.
        """
        from docgen.branding.asset_manager import load_profile

        orphan_dir = profiles_dir / "orphan"
        orphan_dir.mkdir(parents=True, exist_ok=True)
        # No profile.json written

        with pytest.raises(BrandProfileNotFoundError):
            load_profile("orphan")
