# Requirements Document

## Introduction

The Branding Engine extends the Turn2Law document generation system to support multi-tenant branding. Today every document produced by the system carries hardcoded Turn2Law assets (header decoration, footer decoration, logo, and watermark) embedded in a shared `brand_preamble.tex` file. The Branding Engine introduces a `BrandProfile` abstraction that selects between two modes — **turn2law** (current behaviour, fully preserved) and **custom** (caller-supplied PNG assets). The engine validates and processes uploaded images, computes document margins from image dimensions, and generates a per-profile `brand_preamble` LaTeX file. Named profiles are persisted on disk so they can be reused across document generation calls. All six document templates (Onboarding Letter, NDA, Offer Letter, Contract, MOU, IP Agreement) continue to work unchanged in both modes.

---

## Glossary

- **Branding_Engine**: The new `docgen/branding/` Python package that owns brand-mode selection, asset lifecycle, image processing, margin computation, and LaTeX preamble generation.
- **BrandProfile**: A named configuration object that records the brand mode, asset file paths, and computed layout parameters for a single branding identity.
- **Brand_Mode**: An enumerated value — either `turn2law` or `custom` — that determines which asset set is used when generating a document.
- **Asset_Manager**: The component responsible for storing, retrieving, and deleting brand profile records and their associated processed image files.
- **Image_Processor**: The component responsible for validating and normalising uploaded PNG files prior to use in a brand profile.
- **Layout_Builder**: The component responsible for computing LaTeX geometry parameters (margins, image placement coordinates) from processed image dimensions, and for generating the `brand_preamble` LaTeX source.
- **Validator**: The component that enforces format, resolution, and file-size constraints on candidate brand asset images.
- **Header_Image**: A PNG supplied by the caller that replaces the Turn2Law `header_decoration.png` across the full page width.
- **Footer_Image**: A PNG supplied by the caller that replaces the Turn2Law `footer_decoration.png` across the full page width.
- **Watermark_Image**: A PNG supplied by the caller that replaces the Turn2Law `watermark_logo_n.png` centred on the page body.
- **Logo_Image**: A PNG supplied by the caller that replaces the Turn2Law logo (`sample_asset_0_xref_36.jpeg`) placed in the top-left of every page.
- **Brand_Preamble**: A XeLaTeX source file (`brand_preamble.tex`) that is `\input`-ed by every document template to apply background decorations, fonts, and geometry.
- **Profiles_Store**: The directory on disk (configurable, defaulting to `docgen/branding/profiles/`) where serialised `BrandProfile` records and processed images are persisted.
- **A4_Page**: A page of width 595.5 pt and height 842.25 pt, as used by all existing document templates.
- **latex_writer**: The existing `docgen/utils/latex_writer.py` module that renders templates and compiles them with XeLaTeX.
- **LAYOUTS_DIR_PLACEHOLDER**: A token replaced at render time by `latex_writer` with the absolute path to `docgen/layouts/`.
- **FONTS_DIR_PLACEHOLDER**: A token in generated preamble `.tex` files that `latex_writer` replaces at render time with the absolute path to `docgen/fonts/`.
- **docgen_root**: The directory that contains the `docgen` package, i.e. the parent of the `docgen/` folder.

---

## Requirements

### Requirement 1: BrandProfile Data Model

**User Story:** As a developer integrating the Branding Engine, I want a well-defined `BrandProfile` data structure, so that I can pass branding intent to the engine in a single, self-describing object.

#### Acceptance Criteria

1. THE Branding_Engine SHALL define a `BrandProfile` dataclass (or equivalent immutable structure) with the following fields: `profile_id` (non-empty str), `name` (non-empty str), `mode` (Brand_Mode), `header_image_path` (Optional[str]), `footer_image_path` (Optional[str]), `watermark_image_path` (Optional[str]), `logo_image_path` (Optional[str]), and `created_at` (timezone-aware UTC datetime).
2. IF `mode` is `turn2law`, THE Branding_Engine SHALL allow `header_image_path`, `footer_image_path`, `watermark_image_path`, and `logo_image_path` to be `None`.
3. IF `mode` is `custom` and `header_image_path` is `None` or an empty string or refers to a file that does not exist, THEN THE Branding_Engine SHALL raise a `BrandProfileError` with a message identifying the invalid field.
4. IF `mode` is `custom`, THE Branding_Engine SHALL allow `footer_image_path`, `watermark_image_path`, and `logo_image_path` to be `None`; their corresponding preamble placement blocks SHALL be omitted from the generated Brand_Preamble.
5. THE Branding_Engine SHALL reject any `BrandProfile` where `mode` is neither `turn2law` nor `custom` by raising a `BrandProfileError`.

---

### Requirement 2: PNG Asset Validation

**User Story:** As an operator uploading custom brand assets, I want the system to reject unsuitable images immediately, so that I never discover a bad asset only after attempting document generation.

#### Acceptance Criteria

1. WHEN an image file is submitted for validation, THE Validator SHALL confirm the file is PNG format by reading the first 8 bytes and comparing them to the PNG magic signature `\x89PNG\r\n\x1a\n` (hex: `89 50 4E 47 0D 0A 1A 0A`); a file that does not match SHALL be rejected regardless of its filename extension.
2. WHEN an image file is submitted for validation, THE Validator SHALL confirm the image width is at least 595 pixels and the image height is at least 1 pixel.
3. WHEN a Header_Image (image_type `"header"`) is submitted for validation, THE Validator SHALL confirm the image height does not exceed 150 pixels.
4. WHEN a Footer_Image (image_type `"footer"`) is submitted for validation, THE Validator SHALL confirm the image height does not exceed 120 pixels.
5. WHEN any image file is submitted for validation, THE Validator SHALL confirm the file size does not exceed the value of `BrandingConfig.max_asset_bytes`.
6. IF any single validation constraint is violated, THEN THE Validator SHALL raise a `BrandAssetValidationError` whose message identifies the first violated constraint by name (e.g. `"height_exceeds_maximum"`) and includes the observed value; if the file cannot be read or parsed for any reason including corruption, the constraint name SHALL be `"file_unreadable"`.
7. WHEN validation succeeds, THE Validator SHALL return a `ValidationResult` containing the image width in pixels, height in pixels, and file size in bytes.
8. THE Validator SHALL accept exactly the following values for `image_type`: `"header"`, `"footer"`, `"watermark"`, `"logo"`; any other value SHALL raise a `BrandProfileError`.

---

### Requirement 3: Image Processing and Normalisation

**User Story:** As an operator, I want uploaded images to be automatically trimmed and normalised, so that transparent borders do not create unwanted gaps in the document layout.

#### Acceptance Criteria

1. WHEN a PNG image is processed, THE Image_Processor SHALL trim pixel rows and columns from all four edges where every pixel in that row or column has an alpha channel value of exactly 0.
2. WHEN a PNG image is processed, THE Image_Processor SHALL preserve the aspect ratio of the cropped image content without stretching or padding.
3. WHEN a PNG image is processed, THE Image_Processor SHALL save the result as a lossless PNG file to a caller-specified path within the Profiles_Store.
4. IF a PNG image has no border pixels where every pixel in a row or column has alpha equal to 0, THEN THE Image_Processor SHALL produce an output file whose pixel dimensions are identical to the input.
5. WHEN a PNG image is processed, THE Image_Processor SHALL return the pixel width and height of the resulting output file as a tuple `(width, height)`.
6. IF image processing fails for any reason, including a corrupt or unreadable file, THEN THE Image_Processor SHALL raise a `BrandAssetProcessingError` whose message includes the file path and the exception type or OS error code; silent failure or returning partial results is not permitted.
7. IF after trimming the image content area would be zero pixels in width or height (i.e. the entire image is transparent), THEN THE Image_Processor SHALL raise a `BrandAssetProcessingError` with constraint name `"all_transparent"` rather than saving a zero-dimension file.

---

### Requirement 4: Layout Computation

**User Story:** As a developer, I want the Layout_Builder to automatically derive correct LaTeX geometry from the processed image dimensions, so that document body text is never obscured by header or footer decorations.

#### Acceptance Criteria

1. WHEN computing layout from a processed Header_Image, THE Layout_Builder SHALL convert the image's pixel height to points using the formula `pt = px * 72 / BrandingConfig.asset_dpi`.
2. WHEN computing layout from a processed Header_Image, THE Layout_Builder SHALL set the top margin to `max(74, header_height_pt + 16)` points.
3. WHEN no Header_Image is provided for a custom profile, THE Layout_Builder SHALL use a top margin of 74 pt and a `header_height_pt` of 0 pt in the returned `LayoutParameters`.
4. WHEN computing layout from a processed Footer_Image, THE Layout_Builder SHALL convert the image's pixel height to points using the formula `pt = px * 72 / BrandingConfig.asset_dpi`.
5. WHEN computing layout from a processed Footer_Image, THE Layout_Builder SHALL set the bottom margin to `max(66, footer_height_pt + 16)` points.
6. WHEN no Footer_Image is provided for a custom profile, THE Layout_Builder SHALL use a bottom margin of 66 pt.
7. THE Layout_Builder SHALL use a left margin of 42 pt and a right margin of 32 pt for all custom profiles regardless of asset dimensions.
8. THE Layout_Builder SHALL produce a `LayoutParameters` object containing `top_margin_pt`, `bottom_margin_pt`, `left_margin_pt`, `right_margin_pt`, `header_height_pt`, and `footer_height_pt`; when no footer image is provided `footer_height_pt` SHALL be 0 pt.

---

### Requirement 5: Brand Preamble Generation

**User Story:** As a developer, I want the Layout_Builder to emit a valid XeLaTeX preamble file for a custom brand profile, so that document templates can `\input` it without any template modifications.

#### Acceptance Criteria

1. WHEN generating a custom Brand_Preamble, THE Layout_Builder SHALL produce a `.tex` file containing `\usepackage{geometry}` configured with the `top`, `bottom`, `left`, and `right` values from the computed `LayoutParameters`.
2. WHEN generating a custom Brand_Preamble, THE Layout_Builder SHALL include an `\AddToShipoutPictureBG` block that places the Header_Image with its anchor at `(current page.north west)+(0pt, 0pt)`, at a rendered width of 595.5 pt and height equal to `header_height_pt`.
3. WHEN a Footer_Image is present in the BrandProfile, THE Layout_Builder SHALL include within the `\AddToShipoutPictureBG` block a placement of the Footer_Image with its anchor at `(current page.south west)+(0pt, 0pt)`, at a rendered width of 595.5 pt and height equal to `footer_height_pt`.
4. WHEN a Watermark_Image is present in the BrandProfile, THE Layout_Builder SHALL include within the `\AddToShipoutPictureBG` block a placement of the Watermark_Image centred at A4 page coordinates (297.75 pt, 421.13 pt) with `opacity=0.10`.
5. WHEN a Logo_Image is present in the BrandProfile, THE Layout_Builder SHALL include within the `\AddToShipoutPictureBG` block a placement of the Logo_Image with its anchor at `(current page.north west)+(28.49pt, -32.59pt)`.
6. THE Layout_Builder SHALL include font declarations for Montserrat (body) and Garet (footer labels) using `FONTS_DIR_PLACEHOLDER` as the font directory token, so that `latex_writer` can substitute the absolute path at render time.
7. WHEN generating a custom Brand_Preamble, THE Layout_Builder SHALL write image `\includegraphics` paths as absolute POSIX-style paths (forward slashes only) pointing to the processed PNG files in the Profiles_Store; no placeholder tokens SHALL be used for image paths.
8. THE Layout_Builder SHALL write the generated Brand_Preamble `.tex` file to `{Profiles_Store}/{profile_id}/brand_preamble.tex` and return that absolute path.

---

### Requirement 6: Turn2Law Mode Passthrough

**User Story:** As a developer calling the Branding Engine with `mode=turn2law`, I want the engine to return the path to the existing `brand_preamble.tex` unchanged, so that current document generation behaviour is fully preserved.

#### Acceptance Criteria

1. WHEN the Branding_Engine is called with a BrandProfile where `mode` is `turn2law`, THE Branding_Engine SHALL return the absolute path to the existing `docgen/layouts/brand_preamble.tex` file without reading, modifying, or copying it.
2. WHEN the Branding_Engine is called with a BrandProfile where `mode` is `turn2law`, THE Branding_Engine SHALL not invoke the Validator, Image_Processor, or Layout_Builder, and SHALL not check for the existence of any image files.
3. WHEN the Branding_Engine is called with a BrandProfile where `mode` is `turn2law`, THE Branding_Engine SHALL not write, create, or delete any files in the Profiles_Store.

---

### Requirement 7: Profile Persistence

**User Story:** As an operator, I want to save a named brand profile once and reuse it for all future document generation calls, so that I do not have to re-upload and re-validate assets on every request.

#### Acceptance Criteria

1. WHEN a BrandProfile is saved, THE Asset_Manager SHALL write a JSON file to `{Profiles_Store}/{profile_id}/profile.json` containing all scalar and path fields of the BrandProfile, with `created_at` serialised as an ISO 8601 UTC string.
2. WHEN a BrandProfile is loaded by `profile_id`, THE Asset_Manager SHALL read `{Profiles_Store}/{profile_id}/profile.json`, deserialise it, and return a `BrandProfile` object with field types matching those specified in Requirement 1.
3. WHEN a `profile_id` that has no corresponding subdirectory in the Profiles_Store is requested, THE Asset_Manager SHALL raise a `BrandProfileNotFoundError` with a message that includes the requested `profile_id`.
4. THE Asset_Manager SHALL provide a `list_profiles()` method that returns all saved `BrandProfile` objects sorted by `created_at` descending; if no profiles exist it SHALL return an empty list.
5. WHEN a BrandProfile is deleted by `profile_id`, THE Asset_Manager SHALL recursively remove the entire `{Profiles_Store}/{profile_id}/` subdirectory including all processed image files and the generated preamble file.
6. IF the Profiles_Store directory does not exist when any Asset_Manager method is first called, THEN THE Asset_Manager SHALL create it (including any missing intermediate directories) before performing the requested operation.
7. WHEN `save_profile` is called with a `profile_id` that already has a subdirectory in the Profiles_Store, THE Asset_Manager SHALL overwrite the existing `profile.json` without raising an error and without deleting processed image files.

---

### Requirement 8: End-to-End Integration with latex_writer

**User Story:** As a developer generating a document, I want to pass a BrandProfile alongside the existing `render_latex` call, so that the correct brand preamble is selected without modifying any document template.

#### Acceptance Criteria

1. THE Branding_Engine SHALL expose a `resolve_preamble(profile: BrandProfile) -> str` function that returns the absolute path to the correct Brand_Preamble `.tex` file for the given profile.
2. WHEN `resolve_preamble` is called with a `turn2law` profile, THE Branding_Engine SHALL return the absolute path to `docgen/layouts/brand_preamble.tex`.
3. WHEN `resolve_preamble` is called with a `custom` profile and `{Profiles_Store}/{profile_id}/brand_preamble.tex` already exists on disk, THE Branding_Engine SHALL return that path without re-running validation, processing, or layout computation.
4. WHEN `resolve_preamble` is called with a `custom` profile and no `brand_preamble.tex` exists for that profile, THE Branding_Engine SHALL execute the full pipeline (validate assets, process images, compute layout, generate preamble) and return the resulting path.
5. THE Branding_Engine SHALL NOT write to or read from any existing document template `.tex` file in `docgen/templates/`.
6. THE Branding_Engine SHALL NOT alter the function signature of `render_latex` in `docgen/utils/latex_writer.py`.
7. THE stem of the Brand_Preamble filename returned by `resolve_preamble` SHALL be usable as a drop-in replacement for `brand_preamble` in the `\input{LAYOUTS_DIR_PLACEHOLDERbrand_preamble}` token that `latex_writer` substitutes at render time.

---

### Requirement 9: Multi-Document-Type Compatibility

**User Story:** As a document generation operator, I want all six document types to produce correctly branded output in both modes, so that no template requires a custom branding workaround.

#### Acceptance Criteria

1. WHEN `render_latex` is called with the Onboarding_Letter template and a resolved custom Brand_Preamble path, THE system SHALL complete both XeLaTeX passes without a non-zero exit code.
2. WHEN `render_latex` is called with the NDA template and a resolved custom Brand_Preamble path, THE system SHALL complete both XeLaTeX passes without a non-zero exit code.
3. WHEN `render_latex` is called with the Offer_Letter template and a resolved custom Brand_Preamble path, THE system SHALL complete both XeLaTeX passes without a non-zero exit code.
4. WHEN `render_latex` is called with the Contract template and a resolved custom Brand_Preamble path, THE system SHALL complete both XeLaTeX passes without a non-zero exit code.
5. WHEN `render_latex` is called with the MOU template and a resolved custom Brand_Preamble path, THE system SHALL complete both XeLaTeX passes without a non-zero exit code.
6. WHEN `render_latex` is called with the IP_Agreement template and a resolved custom Brand_Preamble path, THE system SHALL complete both XeLaTeX passes without a non-zero exit code.
7. THE Branding_Engine SHALL verify, using static analysis of the generated Brand_Preamble `.tex` content before invoking XeLaTeX, that the file contains no references to Turn2Law-specific image filenames (`header_decoration`, `footer_decoration`, `sample_asset_0_xref_36`, `watermark_logo_n`).
8. WHEN `resolve_preamble` is called for a custom profile, THE Branding_Engine SHALL perform a XeLaTeX syntax pre-check on the generated preamble file using `xelatex -draftmode` before returning the path; IF the pre-check exits with a non-zero code THEN THE Branding_Engine SHALL raise a `BrandProfileError` and remove the partially-generated preamble file.

---

### Requirement 10: Error Handling and Reporting

**User Story:** As a developer or operator, I want descriptive errors from the Branding Engine, so that I can quickly diagnose and correct invalid inputs or misconfigured profiles.

#### Acceptance Criteria

1. THE Branding_Engine SHALL define a base exception class `BrandingEngineError` from which all other engine-specific exceptions inherit.
2. THE Branding_Engine SHALL define the following subclasses of `BrandingEngineError`: `BrandProfileError` (invalid profile configuration or mode), `BrandAssetValidationError` (asset fails a validation constraint), `BrandAssetProcessingError` (image cannot be processed), and `BrandProfileNotFoundError` (requested profile_id does not exist).
3. WHEN a `BrandAssetValidationError` is raised, its message SHALL include both the name of the violated constraint and the measured or observed value that caused the violation.
4. WHEN any operation writes files to the Profiles_Store and an exception is raised before the operation completes, THE Branding_Engine SHALL delete all files written to the Profiles_Store during that operation before re-raising the exception.
5. WHEN a XeLaTeX compilation error occurs during document rendering, THE Branding_Engine SHALL allow the `RuntimeError` raised by `latex_writer` to propagate to the caller without catching or wrapping it in a `BrandingEngineError`.
6. WHEN `resolve_preamble` is called with a `turn2law` profile and the SHA-256 hash of `docgen/layouts/brand_preamble.tex` does not match the hash recorded at application startup, THE Branding_Engine SHALL raise a `BrandProfileError` with message `"turn2law_preamble_modified"` and SHALL NOT return the altered path.

---

### Requirement 11: Configuration

**User Story:** As a system administrator, I want the Branding Engine's storage location and default constraints to be configurable without modifying source code, so that I can adapt the engine to different deployment environments.

#### Acceptance Criteria

1. THE Branding_Engine SHALL read the Profiles_Store path from the environment variable `BRAND_PROFILES_DIR`; IF the variable is not set, THE Branding_Engine SHALL default to `{docgen_root}/branding/profiles/` where `docgen_root` is the parent directory of the `docgen/` package folder.
2. THE Branding_Engine SHALL read the maximum permitted asset file size in bytes from the environment variable `BRAND_MAX_ASSET_BYTES`; IF not set, THE Branding_Engine SHALL default to `5242880` (5 MB); IF the variable is set to a value that cannot be parsed as a positive integer, THE Branding_Engine SHALL raise a `BrandProfileError` at import time with a message identifying the invalid value.
3. THE Branding_Engine SHALL read the minimum header image width in pixels from the environment variable `BRAND_MIN_HEADER_WIDTH_PX`; IF not set, THE Branding_Engine SHALL default to `595`; IF the variable is set to a value that cannot be parsed as a positive integer, THE Branding_Engine SHALL raise a `BrandProfileError` at import time.
4. THE Branding_Engine SHALL read the assumed source image DPI from the environment variable `BRAND_ASSET_DPI`; IF not set, THE Branding_Engine SHALL default to `96`; this value SHALL be passed to the Layout_Builder for use in the `pt = px * 72 / dpi` formula; IF the variable is set to a value that cannot be parsed as a positive number, THE Branding_Engine SHALL raise a `BrandProfileError` at import time.
5. THE Branding_Engine SHALL expose all resolved configuration values through a `BrandingConfig` dataclass defined in `docgen/branding/config.py`; this dataclass SHALL be instantiated exactly once at module import time and all Branding_Engine components SHALL read from this single instance.
