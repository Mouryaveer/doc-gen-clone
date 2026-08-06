# Implementation Plan: Branding Engine

## Overview

Build the `docgen/branding/` package that enables multi-tenant branding. The implementation follows a bottom-up dependency order: exceptions and config first, then data models, then individual components (validators, image processor, layout builder, asset manager), then the top-level orchestrator, and finally integration with `latex_writer.py` and `app.py`.

## Tasks

- [x] 1. Create exceptions.py and config.py
  - Create `docgen/branding/exceptions.py` with the full exception hierarchy: `BrandingEngineError` base class and subclasses `BrandProfileError`, `BrandAssetValidationError`, `BrandAssetProcessingError`, `BrandProfileNotFoundError`
  - Create `docgen/branding/config.py` with `BrandingConfig` frozen dataclass reading four env vars (`BRAND_PROFILES_DIR`, `BRAND_MAX_ASSET_BYTES`, `BRAND_MIN_HEADER_WIDTH_PX`, `BRAND_ASSET_DPI`) with defaults (`<docgen_root>/branding/profiles/`, `5242880`, `595`, `96.0`); compute `docgen_root = Path(__file__).parent.parent.parent`; raise `BrandProfileError` at import if any env var cannot be parsed; expose module-level singleton `CONFIG`
  - _Requirements: R10.1, R10.2, R11.1–R11.5_

- [x] 2. Create BrandProfile data model and __init__.py
  - Define `BrandMode(str, Enum)` with `TURN2LAW = "turn2law"` and `CUSTOM = "custom"`
  - Define `BrandProfile` frozen dataclass: `profile_id` (str), `name` (str), `mode` (BrandMode), `header_image_path` (Optional[str]=None), `footer_image_path` (Optional[str]=None), `watermark_image_path` (Optional[str]=None), `logo_image_path` (Optional[str]=None), `created_at` (datetime defaulting to `datetime.now(timezone.utc)`)
  - Define `ValidationResult` dataclass: `width_px` (int), `height_px` (int), `file_size_bytes` (int)
  - Define `LayoutParameters` dataclass: `top_margin_pt`, `bottom_margin_pt`, `left_margin_pt`, `right_margin_pt`, `header_height_pt`, `footer_height_pt` (all float)
  - Create `docgen/branding/__init__.py` that re-exports `BrandMode`, `BrandProfile`, `ValidationResult`, `LayoutParameters`, all exceptions, and the functions `resolve_preamble`, `save_profile`, `load_profile`, `list_profiles`, `delete_profile`
  - _Requirements: R1.1–R1.5_

- [x] 3. Create validators.py
  - Create `docgen/branding/validators.py`
  - Implement `validate_asset(path: str, image_type: str) -> ValidationResult`
  - Step 1: check `image_type` is one of `"header"`, `"footer"`, `"watermark"`, `"logo"` — raise `BrandProfileError` otherwise
  - Step 2: open file in binary mode, read first 8 bytes, compare to PNG magic `b'\x89PNG\r\n\x1a\n'` — raise `BrandAssetValidationError("not_png", ...)` on mismatch
  - Step 3: open with Pillow, read width/height; catch `OSError`/`UnidentifiedImageError` → `BrandAssetValidationError("file_unreadable", ...)`
  - Step 4: check `width >= CONFIG.min_header_width_px` — raise `BrandAssetValidationError("width_below_minimum", observed=width)` if not
  - Step 5: check `height >= 1` — raise `BrandAssetValidationError("height_below_minimum", observed=height)` if not
  - Step 6: if `image_type == "header"` check `height <= 150`; if `image_type == "footer"` check `height <= 120` — raise `BrandAssetValidationError("height_exceeds_maximum", observed=height)` if violated
  - Step 7: check `os.path.getsize(path) <= CONFIG.max_asset_bytes` — raise `BrandAssetValidationError("file_too_large", ...)` if not
  - Step 8: return `ValidationResult(width_px=width, height_px=height, file_size_bytes=file_size)`
  - _Requirements: R2.1–R2.8_

- [x] 4. Create image_processor.py
  - Create `docgen/branding/image_processor.py`
  - Implement `process_image(src_path: str, dest_path: str) -> tuple[int, int]`
  - Open `src_path` with Pillow, convert to RGBA
  - Split to get alpha channel; call `alpha.getbbox()` to find bounding box of non-zero alpha pixels
  - If `bbox is None`: raise `BrandAssetProcessingError(f"all_transparent: {src_path}")`
  - Crop RGBA image to `bbox`; ensure `dest_path` parent directory exists
  - Save cropped image to `dest_path` as PNG (lossless)
  - Return `(cropped.width, cropped.height)`
  - Catch any `OSError` or Pillow exception (other than explicit raises above) → re-raise as `BrandAssetProcessingError` with message including `src_path` and exception details
  - _Requirements: R3.1–R3.7_

- [x] 5. Create layout_builder.py
  - Create `docgen/branding/layout_builder.py`
  - Implement `compute_layout(header_h_px: int | None, footer_h_px: int | None, dpi: float) -> LayoutParameters`: `header_pt = header_h_px * 72 / dpi if header_h_px else 0.0`; `footer_pt = footer_h_px * 72 / dpi if footer_h_px else 0.0`; `top = max(74.0, header_pt + 16.0)`; `bottom = max(66.0, footer_pt + 16.0)`; return `LayoutParameters(top, bottom, 42.0, 32.0, header_pt, footer_pt)`
  - Implement `generate_preamble(profile: BrandProfile, layout: LayoutParameters, dest_path: str) -> str`
  - Build LaTeX string containing: `\usepackage{fontspec}` with Montserrat/Garet using `FONTS_DIR_PLACEHOLDER`; same utility packages as `brand_preamble.tex` (`graphicx`, `xcolor`, `eso-pic`, `tikz`, `textpos`, `needspace`, `enumitem`, `array`, `ifthen`, `tabularx`); `\usepackage[geometry]` with `top=<top>pt,bottom=<bottom>pt,left=42pt,right=32pt,noheadfoot`; `\graphicspath{{IMAGES_DIR_PLACEHOLDER}}`; `\pagenumbering{gobble}`; brand colour definitions; `\AddToShipoutPictureBG` block with only the asset nodes present in the profile (header required; footer/watermark/logo conditional)
  - Write image paths as absolute POSIX paths (`Path(p).as_posix()`)
  - Ensure `dest_path` parent exists; write UTF-8 to `dest_path`
  - After writing: scan text for Turn2Law asset names (`header_decoration`, `footer_decoration`, `sample_asset_0_xref_36`, `watermark_logo_n`); if found delete file and raise `BrandProfileError`
  - Return `os.path.abspath(dest_path)`
  - _Requirements: R4.1–R4.8, R5.1–R5.8, R9.7_

- [x] 6. Create asset_manager.py
  - Create `docgen/branding/asset_manager.py`
  - Implement `save_profile(profile: BrandProfile) -> None`: create `{CONFIG.profiles_dir}/{profile.profile_id}/`; serialise to dict with `created_at` as `isoformat()` and `mode` as `.value`; write to `profile.json` (overwrite)
  - Implement `load_profile(profile_id: str) -> BrandProfile`: raise `BrandProfileNotFoundError(f"Profile not found: {profile_id}")` if `profile.json` missing; parse JSON; attach UTC to naive `created_at`; return `BrandProfile(mode=BrandMode(data["mode"]), ...)`
  - Implement `list_profiles() -> list[BrandProfile]`: ensure profiles dir exists; load all `profile.json` files; sort by `created_at` descending; return list (empty if none)
  - Implement `delete_profile(profile_id: str) -> None`: raise `BrandProfileNotFoundError` if subdirectory missing; `shutil.rmtree` the subdirectory
  - _Requirements: R7.1–R7.7_

- [x] 7. Create branding_engine.py
  - Create `docgen/branding/branding_engine.py`
  - Module-level `_t2l_preamble_hash: str | None = None`
  - Implement `resolve_preamble(profile: BrandProfile) -> str`
  - **Turn2Law branch**: compute absolute path to `docgen/layouts/brand_preamble.tex`; hash with SHA-256; store on first call; on subsequent calls re-hash and raise `BrandProfileError("turn2law_preamble_modified")` if hash differs; return path
  - **Custom branch**: (a) validate `header_image_path` is non-empty and file exists — raise `BrandProfileError` if not; (b) check cache at `{CONFIG.profiles_dir}/{profile_id}/brand_preamble.tex` — return if exists; (c) initialise `files_written = []`; wrap steps d–j in try/except that on any exception deletes every path in `files_written` then re-raises; (d) `validate_asset` all present asset paths; (e) `process_image` each asset to profile dir (`header.png`, `footer.png`, `watermark.png`, `logo.png`), append to `files_written`, record pixel heights; (f) `compute_layout`; (g) `generate_preamble` to `{profile_dir}/brand_preamble.tex`, append to `files_written`; (h) run `xelatex -draftmode -interaction=nonstopmode` on preamble in a temp dir; if exit != 0 delete preamble and raise `BrandProfileError`; (i) return absolute preamble path
  - **Invalid mode**: raise `BrandProfileError(f"Unknown brand mode: {profile.mode}")`
  - _Requirements: R1.3–R1.5, R6.1–R6.3, R8.1–R8.4, R9.8, R10.4, R10.6_

- [x] 8. Update latex_writer.py to accept preamble_path
  - Open `docgen/utils/latex_writer.py`
  - Add `preamble_path: str | None = None` as the last parameter of `render_latex()`
  - After the existing `LAYOUTS_DIR_PLACEHOLDER` substitution block, add logic: if `preamble_path is not None`, use `re.sub` to replace `\input{...brand_preamble...}` with `\input{<preamble_dir><stem>}` where `preamble_dir` is the absolute POSIX directory of `preamble_path` and `stem` is the filename without extension
  - When `preamble_path is None`, make no change to existing behaviour (backward-compatible)
  - _Requirements: R8.6, R8.7_

- [x] 9. Update app.py with branding API
  - Open `docgen/app.py`
  - Add function `generate_with_branding(doc_type, user_inputs, brand_profile, output_name="output")` that calls `resolve_preamble(brand_profile)` then `render_latex(..., preamble_path=preamble_path)` and returns the pdf path
  - Add function `make_custom_profile(profile_id, name, header_image_path, footer_image_path=None, watermark_image_path=None, logo_image_path=None)` that constructs a `BrandProfile` with `mode=BrandMode.CUSTOM`, converts all paths to absolute, calls `save_profile`, and returns the profile
  - Add a commented-out usage example in the `__main__` block showing how to use `make_custom_profile` and `generate_with_branding`
  - Do not modify any existing function
  - _Requirements: R8.1–R8.6_

- [x] 10. Create test fixtures and verify full import chain
  - Create `docgen/branding/tests/__init__.py` (empty)
  - Create `docgen/branding/tests/fixtures/` directory
  - Create `docgen/branding/tests/create_fixtures.py` that uses Pillow to generate and save: `header_600x58.png` (600×58 RGBA, opaque content, 10 px transparent border), `footer_600x40.png` (600×40 RGBA, opaque), `watermark_200x200.png` (200×200 RGBA semi-transparent), `logo_200x80.png` (200×80 RGBA opaque), `not_a_png.jpg` (small JPEG), `all_transparent_600x58.png` (600×58 RGBA all-zero alpha)
  - Run `create_fixtures.py` to populate the fixtures directory
  - Verify `python -c "from branding import BrandProfile, BrandMode, resolve_preamble, save_profile, load_profile, list_profiles, delete_profile"` exits 0 from the `docgen/` directory
  - Verify `python -c "from branding.config import CONFIG; assert CONFIG.max_asset_bytes == 5242880"` exits 0
  - _Requirements: All (smoke-test of the complete module)_

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": [1] },
    { "wave": 2, "tasks": [2] },
    { "wave": 3, "tasks": [3, 4, 5, 6, 8] },
    { "wave": 4, "tasks": [7] },
    { "wave": 5, "tasks": [9] },
    { "wave": 6, "tasks": [10] }
  ]
}
```

- Wave 1: exceptions + config (no dependencies)
- Wave 2: data models + `__init__.py` (depends on Task 1)
- Wave 3: validators, image processor, layout builder, asset manager, and `latex_writer.py` update (all depend on Task 1/2 only, none depend on each other — parallel)
- Wave 4: `branding_engine.py` orchestrator (depends on Tasks 3, 4, 5, 6, 7 as all components must exist)
- Wave 5: `app.py` API additions (depends on Tasks 7, 8)
- Wave 6: test fixtures and smoke test (depends on everything)

## Notes

- No existing `.tex` template file is modified. The `\input{...brand_preamble}` token in templates is already present; `latex_writer.py` substitutes the path at render time.
- The `profiles/` directory is created at runtime and should be added to `.gitignore`.
- The `xelatex -draftmode` pre-check in Task 7 requires MiKTeX/XeLaTeX to be installed — the same requirement as the rest of the system.
- All image paths stored in `BrandProfile` and written to `profile.json` are absolute paths resolved at profile creation time.
