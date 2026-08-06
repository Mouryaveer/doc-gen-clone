# Design Document — Branding Engine

## Overview

The Branding Engine is a self-contained Python package (`docgen/branding/`) that slots between `app.py` and `latex_writer.py`. It accepts a `BrandProfile` describing which branding mode to use, and returns the absolute path to the correct LaTeX preamble file. The rest of the pipeline — template rendering and XeLaTeX compilation — is unchanged.

The two modes are strictly separated:
- **`turn2law`** — zero processing; the existing `brand_preamble.tex` path is returned immediately.
- **`custom`** — PNG assets are validated, processed, layout is computed from image dimensions, and a fresh `brand_preamble.tex` is generated for that profile.

---

## Architecture

### Module Structure

```
docgen/
  branding/
    __init__.py          # Public API: BrandProfile, BrandMode, resolve_preamble,
                         #             save_profile, load_profile, list_profiles,
                         #             delete_profile
    branding_engine.py   # resolve_preamble() — top-level orchestrator
    asset_manager.py     # save/load/list/delete BrandProfile JSON records
    image_processor.py   # Pillow-based transparent-border trim + PNG save
    validators.py        # PNG magic-byte check, dimension/size rules
    layout_builder.py    # px→pt conversion, LayoutParameters, .tex generation
    config.py            # BrandingConfig dataclass (env-var backed)
    exceptions.py        # BrandingEngineError hierarchy
```

All other `docgen/` modules remain untouched. No template file is modified.

---

## Data Models

### `BrandMode` (enum)

```python
class BrandMode(str, Enum):
    TURN2LAW = "turn2law"
    CUSTOM   = "custom"
```

### `BrandProfile` (dataclass)

```python
@dataclass(frozen=True)
class BrandProfile:
    profile_id:           str                    # non-empty, URL-safe slug
    name:                 str                    # human-readable label
    mode:                 BrandMode
    header_image_path:    Optional[str] = None   # required when mode=custom
    footer_image_path:    Optional[str] = None
    watermark_image_path: Optional[str] = None
    logo_image_path:      Optional[str] = None
    created_at:           datetime = field(
                              default_factory=lambda: datetime.now(timezone.utc)
                          )
```

Validation of `header_image_path` when `mode=custom` happens in `branding_engine.py`, not in `__post_init__`, so that error messages are always `BrandProfileError` instances (not `ValueError`).

### `ValidationResult` (dataclass)

```python
@dataclass
class ValidationResult:
    width_px:      int
    height_px:     int
    file_size_bytes: int
```

### `LayoutParameters` (dataclass)

```python
@dataclass
class LayoutParameters:
    top_margin_pt:    float
    bottom_margin_pt: float
    left_margin_pt:   float   # always 42.0
    right_margin_pt:  float   # always 32.0
    header_height_pt: float   # 0.0 when no header image
    footer_height_pt: float   # 0.0 when no footer image
```

---

## Components and Interfaces

### `branding_engine.py`
- **`resolve_preamble(profile: BrandProfile) -> str`** — top-level entry point; returns absolute path to the correct preamble `.tex` file.

### `asset_manager.py`
- **`save_profile(profile: BrandProfile) -> None`**
- **`load_profile(profile_id: str) -> BrandProfile`**
- **`list_profiles() -> list[BrandProfile]`**
- **`delete_profile(profile_id: str) -> None`**

### `validators.py`
- **`validate_asset(path: str, image_type: str) -> ValidationResult`** — raises `BrandAssetValidationError` on failure.

### `image_processor.py`
- **`process_image(src_path: str, dest_path: str) -> tuple[int, int]`** — returns `(width_px, height_px)` of the output.

### `layout_builder.py`
- **`compute_layout(header_h_px: int | None, footer_h_px: int | None, dpi: float) -> LayoutParameters`**
- **`generate_preamble(profile: BrandProfile, layout: LayoutParameters, dest_path: str) -> str`** — returns absolute path of written `.tex` file.

### `config.py`
- **`BrandingConfig`** (frozen dataclass) — singleton `CONFIG` instance read from env vars at import.

### `exceptions.py`
- `BrandingEngineError` → `BrandProfileError`, `BrandAssetValidationError`, `BrandAssetProcessingError`, `BrandProfileNotFoundError`.

---

## Component Design

### `config.py` — `BrandingConfig`

Reads four environment variables at import time and exposes them as a frozen dataclass. Raises `BrandProfileError` immediately if any env var has an invalid value.

```python
@dataclass(frozen=True)
class BrandingConfig:
    profiles_dir:         str    # BRAND_PROFILES_DIR or <docgen_root>/branding/profiles
    max_asset_bytes:      int    # BRAND_MAX_ASSET_BYTES or 5_242_880
    min_header_width_px:  int    # BRAND_MIN_HEADER_WIDTH_PX or 595
    asset_dpi:            float  # BRAND_ASSET_DPI or 96.0

CONFIG = BrandingConfig(...)   # singleton, instantiated at import
```

`docgen_root` is computed as `Path(__file__).parent.parent.parent` (three levels up from `docgen/branding/config.py` reaches the project root).

---

### `exceptions.py`

```
BrandingEngineError
  BrandProfileError            — invalid mode, missing required field, tampered preamble
  BrandAssetValidationError    — PNG fails format/dimension/size check
  BrandAssetProcessingError    — Pillow cannot process the image
  BrandProfileNotFoundError    — profile_id not in Profiles_Store
```

---

### `validators.py` — `validate_asset(path, image_type)`

**Responsibility:** Enforce format, dimension, and file-size rules before any image is processed.

**Algorithm:**
1. Read first 8 bytes; compare to PNG magic `b'\x89PNG\r\n\x1a\n'`. Raise `BrandAssetValidationError("not_png", ...)` on mismatch.
2. Open with Pillow to read width/height.
3. Check `width >= config.min_header_width_px` and `height >= 1`.
4. If `image_type == "header"`: check `height <= 150`.
5. If `image_type == "footer"`: check `height <= 120`.
6. Check `file_size <= config.max_asset_bytes`.
7. Return `ValidationResult(width, height, file_size)`.

Any Pillow `UnidentifiedImageError` or `OSError` → `BrandAssetValidationError("file_unreadable", ...)`.

---

### `image_processor.py` — `process_image(src_path, dest_path) -> tuple[int, int]`

**Responsibility:** Trim transparent borders and save a clean PNG.

**Algorithm:**
1. Open with Pillow; convert to RGBA.
2. Extract alpha channel as a NumPy array (or use Pillow `getbbox` on the alpha band).
3. Use `Image.getbbox()` on the alpha channel to find the bounding box of non-zero pixels.
4. If `bbox` is `None` (all pixels transparent): raise `BrandAssetProcessingError("all_transparent", path)`.
5. Crop to bbox. Save as PNG (lossless) to `dest_path`.
6. Return `(cropped.width, cropped.height)`.

Any `OSError` or Pillow exception → `BrandAssetProcessingError(path, exc)`.

---

### `layout_builder.py`

#### `compute_layout(header_h_px, footer_h_px, dpi) -> LayoutParameters`

```python
def compute_layout(header_h_px, footer_h_px, dpi):
    header_pt = header_h_px * 72 / dpi if header_h_px else 0.0
    footer_pt = footer_h_px * 72 / dpi if footer_h_px else 0.0
    top    = max(74.0, header_pt + 16.0)
    bottom = max(66.0, footer_pt + 16.0)
    return LayoutParameters(
        top_margin_pt    = top,
        bottom_margin_pt = bottom,
        left_margin_pt   = 42.0,
        right_margin_pt  = 32.0,
        header_height_pt = header_pt,
        footer_height_pt = footer_pt,
    )
```

#### `generate_preamble(profile, layout, dest_path) -> str`

Writes a `.tex` file to `dest_path` using a string template. The generated file:
- Has the same `\usepackage{fontspec}`, Montserrat/Garet font declarations, and utility packages as `brand_preamble.tex`.
- Uses `FONTS_DIR_PLACEHOLDER` (so `latex_writer` can inject the fonts path at render time).
- Has `\usepackage[geometry]{...}` with values from `LayoutParameters`.
- Has `\AddToShipoutPictureBG{...}` containing only the asset nodes that are present in the profile.
- Writes image paths as absolute POSIX paths — no placeholders.

**Image path handling:** All profile image paths are stored as absolute paths. When writing the `.tex`, convert with `Path(p).as_posix()`.

**Static safety check:** After writing, scan the file text for the strings `header_decoration`, `footer_decoration`, `sample_asset_0_xref_36`, `watermark_logo_n`. If any are found, delete the file and raise `BrandProfileError`.

---

### `asset_manager.py`

| Method | Behaviour |
|--------|-----------|
| `save_profile(profile)` | Creates `{profiles_dir}/{profile_id}/` if needed; writes `profile.json` (overwrites if exists). |
| `load_profile(profile_id)` | Reads `profile.json`; raises `BrandProfileNotFoundError` if missing. |
| `list_profiles()` | Reads all `profile.json` files; returns list sorted by `created_at` descending. |
| `delete_profile(profile_id)` | `shutil.rmtree` on the profile subdirectory; raises `BrandProfileNotFoundError` if missing. |

**JSON serialisation:** `BrandProfile` is converted to a plain dict; `created_at` is serialised as `isoformat()`. On load, `created_at` is parsed with `datetime.fromisoformat()` and forced to UTC if naive.

---

### `branding_engine.py` — `resolve_preamble(profile) -> str`

This is the single entry point called by `app.py`.

```
resolve_preamble(profile)
  │
  ├─ mode == turn2law ──► return abs path to docgen/layouts/brand_preamble.tex
  │                        (after SHA-256 integrity check — Req 10.6)
  │
  └─ mode == custom
       │
       ├─ Validate profile fields (header_image_path non-empty, file exists)
       │
       ├─ Check cache: {profiles_dir}/{profile_id}/brand_preamble.tex exists?
       │     YES ──► return cached path
       │
       └─ NO — run pipeline:
             1. validate_asset(header_image_path, "header")
             2. validate_asset(footer_image_path, "footer")   [if present]
             3. validate_asset(watermark_image_path, "watermark") [if present]
             4. validate_asset(logo_image_path, "logo")       [if present]
             5. process_image(header → profiles_dir/id/header.png)
             6. process_image(footer → footer.png)  [if present]
             7. process_image(watermark → watermark.png) [if present]
             8. process_image(logo → logo.png) [if present]
             9. compute_layout(header_h_px, footer_h_px, config.asset_dpi)
            10. generate_preamble(profile, layout, profiles_dir/id/brand_preamble.tex)
            11. xelatex -draftmode pre-check (Req 9.8)
            12. return preamble path
            
            On any exception: delete all files written in steps 5-10, re-raise.
```

**SHA-256 integrity check (turn2law path):** At the first call with `mode=turn2law`, read and hash `brand_preamble.tex`. Store the hash in a module-level variable. On subsequent calls, re-hash and compare; raise `BrandProfileError("turn2law_preamble_modified")` on mismatch.

---

## Integration with `latex_writer.py`

`latex_writer.py` is **not modified**. The integration point is in `app.py`.

Current `generate_direct` call:
```python
render_latex(template_path, output_tex, output_pdf, user_inputs)
```

New call with branding:
```python
from branding import resolve_preamble

preamble_path = resolve_preamble(brand_profile)
render_latex(template_path, output_tex, output_pdf, user_inputs,
             preamble_path=preamble_path)
```

`latex_writer.render_latex` gains one **optional** keyword argument `preamble_path=None`. When provided, the `\input{LAYOUTS_DIR_PLACEHOLDERbrand_preamble}` substitution uses the stem of `preamble_path` instead of the default `brand_preamble`. When `None`, existing behaviour is unchanged.

> This is the only change to `latex_writer.py` — adding one optional parameter with a `None` default keeps the existing signature fully backward-compatible.

---

## File Layout After Implementation

```
docgen/
  branding/
    __init__.py
    branding_engine.py
    asset_manager.py
    image_processor.py
    validators.py
    layout_builder.py
    config.py
    exceptions.py
    profiles/               # created at runtime, gitignored
      turn2law/             # built-in profile (mode=turn2law, no assets)
      <profile_id>/
        profile.json
        brand_preamble.tex  # generated preamble
        header.png          # processed asset copies
        footer.png
        watermark.png
        logo.png
  utils/
    latex_writer.py         # +1 optional param preamble_path=None
  app.py                    # +resolve_preamble call, +generate_with_branding()
```

---

## Sequence Diagram — Custom Branding First Call

```
app.py
  │
  ├─ build BrandProfile(mode=custom, header_image_path=..., ...)
  │
  ├─ resolve_preamble(profile)
  │     │
  │     ├─ validate_asset(header, "header")     ← validators.py
  │     ├─ validate_asset(footer, "footer")     ← validators.py
  │     ├─ process_image(header → header.png)   ← image_processor.py
  │     ├─ process_image(footer → footer.png)   ← image_processor.py
  │     ├─ compute_layout(h_px, f_px, dpi)      ← layout_builder.py
  │     ├─ generate_preamble(profile, layout)   ← layout_builder.py
  │     ├─ xelatex -draftmode (syntax check)
  │     └─ return /profiles/<id>/brand_preamble.tex
  │
  ├─ render_latex(template, tex, pdf, inputs,
  │               preamble_path=/profiles/<id>/brand_preamble.tex)
  │     │
  │     ├─ read template
  │     ├─ inject FONTS_DIR_PLACEHOLDER in preamble
  │     ├─ substitute {{FIELD}} tokens
  │     ├─ xelatex pass 1
  │     └─ xelatex pass 2
  │
  └─ return pdf_path
```

---

## Error Handling Summary

| Situation | Exception raised | Cleanup |
|-----------|-----------------|---------|
| Header image not PNG | `BrandAssetValidationError` | Nothing written yet |
| Header too tall (>150 px) | `BrandAssetValidationError` | Nothing written yet |
| Image fully transparent | `BrandAssetProcessingError` | Partial file deleted |
| Preamble contains Turn2Law asset name | `BrandProfileError` | Preamble file deleted |
| XeLaTeX draftmode fails | `BrandProfileError` | Preamble file deleted |
| Profile not found | `BrandProfileNotFoundError` | N/A |
| turn2law preamble tampered | `BrandProfileError` | Nothing written |
| XeLaTeX fails during render | `RuntimeError` (from latex_writer) | Not wrapped |

---

## `app.py` Changes

Two new public functions are added. Existing functions are unchanged.

```python
def generate_with_branding(doc_type, user_inputs, brand_profile,
                           output_name="output"):
    """
    Generate a PDF using the specified brand profile.
    Replaces generate_direct() when custom branding is needed.
    Returns the absolute path to the generated PDF.
    """
    from branding import resolve_preamble
    validate_inputs(doc_type, user_inputs)
    template_path = TEMPLATE_MAP[doc_type]
    preamble_path = resolve_preamble(brand_profile)
    output_tex = os.path.join(_HERE, f"{output_name}.tex")
    output_pdf = os.path.join(_HERE, f"{output_name}.pdf")
    render_latex(template_path, output_tex, output_pdf, user_inputs,
                 preamble_path=preamble_path)
    return output_pdf


def make_custom_profile(profile_id, name,
                        header_image_path,
                        footer_image_path=None,
                        watermark_image_path=None,
                        logo_image_path=None):
    """
    Convenience: construct and save a custom BrandProfile.
    Returns the saved BrandProfile.
    """
    from branding import BrandProfile, BrandMode, save_profile
    profile = BrandProfile(
        profile_id=profile_id,
        name=name,
        mode=BrandMode.CUSTOM,
        header_image_path=header_image_path,
        footer_image_path=footer_image_path,
        watermark_image_path=watermark_image_path,
        logo_image_path=logo_image_path,
    )
    save_profile(profile)
    return profile
```

---

## Correctness Properties

### Property 1: Idempotency
Calling `resolve_preamble` twice with the same custom profile returns the same path both times without re-running the pipeline (cache hit on second call).

**Validates: Requirements 8.3**

### Property 2: Turn2Law Isolation
When `mode=turn2law`, zero files are written to the Profiles_Store and the existing `brand_preamble.tex` is returned unmodified.

**Validates: Requirements 6.1, 6.2, 6.3**

### Property 3: Atomic Writes
If any step in the custom pipeline raises an exception, all files written to the Profiles_Store during that call are deleted before the exception propagates.

**Validates: Requirements 10.4**

### Property 4: No Template Mutation
No `.tex` file in `docgen/templates/` or `docgen/layouts/` is ever written, read for mutation, or deleted by the Branding Engine.

**Validates: Requirements 8.5**

### Property 5: No Turn2Law Asset Leakage
The static name check in `generate_preamble` guarantees none of the strings `header_decoration`, `footer_decoration`, `sample_asset_0_xref_36`, or `watermark_logo_n` appear in any custom-mode generated preamble file.

**Validates: Requirements 9.7**

---

## Error Handling

| Situation | Exception | Cleanup action |
|-----------|-----------|---------------|
| Header image not PNG | `BrandAssetValidationError` | No files written yet |
| Image width < 595 px | `BrandAssetValidationError` | No files written yet |
| Header height > 150 px | `BrandAssetValidationError` | No files written yet |
| File > 5 MB | `BrandAssetValidationError` | No files written yet |
| Image fully transparent | `BrandAssetProcessingError` | Partial output file deleted |
| Pillow open failure | `BrandAssetProcessingError` | No output written |
| Preamble contains Turn2Law name | `BrandProfileError` | Preamble file deleted |
| XeLaTeX draftmode non-zero | `BrandProfileError` | Preamble file deleted |
| Profile not found | `BrandProfileNotFoundError` | N/A |
| turn2law preamble tampered | `BrandProfileError` | Nothing written |
| XeLaTeX render failure | `RuntimeError` (from latex_writer) | Not wrapped, propagates as-is |
| Invalid env var at import | `BrandProfileError` | Process exits at startup |

---

## Testing Strategy

### Unit tests (`docgen/branding/tests/`)

| Test file | Covers |
|-----------|--------|
| `test_validators.py` | PNG magic byte rejection, min-width, height caps per type, file-size limit, clean `ValidationResult` return |
| `test_image_processor.py` | Transparent border trim, no-op on fully-opaque image, all-transparent raises, corrupt file raises |
| `test_layout_builder.py` | `pt = px * 72 / dpi` formula, `max(74, h+16)` and `max(66, f+16)` margin rules, zero-image defaults |
| `test_preamble_generation.py` | Generated `.tex` contains correct geometry values, correct image paths, no Turn2Law names, FONTS_DIR_PLACEHOLDER present |
| `test_asset_manager.py` | Save/load round-trip, overwrite, list sort order, delete removes directory, missing-id raises |
| `test_branding_engine.py` | Turn2Law passthrough returns correct path, custom pipeline end-to-end with test PNG, cache hit skips pipeline, error cleanup leaves no partial files |

### Integration tests

- Generate all 6 document types with a minimal custom profile (1 px header PNG) and verify XeLaTeX exits 0.
- Verify that `generate_direct()` (no branding argument) continues to produce identical output to before this feature.

### Test assets

A `docgen/branding/tests/fixtures/` directory holds minimal synthetic PNGs (600×58 px header, 600×40 px footer, 200×200 px watermark/logo) used by all unit and integration tests. These are committed to version control.

---

## Requirements Traceability

| Requirement | Satisfied by |
|-------------|-------------|
| R1 — BrandProfile model | `BrandProfile` dataclass in `__init__.py` / `branding_engine.py` |
| R2 — PNG validation | `validators.py` → `validate_asset()` |
| R3 — Image processing | `image_processor.py` → `process_image()` |
| R4 — Layout computation | `layout_builder.py` → `compute_layout()` |
| R5 — Preamble generation | `layout_builder.py` → `generate_preamble()` |
| R6 — Turn2Law passthrough | `branding_engine.py` → `resolve_preamble()` mode branch |
| R7 — Profile persistence | `asset_manager.py` |
| R8 — Integration | `branding_engine.py` + `latex_writer.py` `preamble_path` param |
| R9 — All 6 doc types | Generated preamble uses same packages as `brand_preamble.tex`; draftmode pre-check |
| R10 — Errors | `exceptions.py` + atomic cleanup in `resolve_preamble()` |
| R11 — Configuration | `config.py` → `BrandingConfig` |
