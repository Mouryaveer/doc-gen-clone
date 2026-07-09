# Turn2Law — Document Generation System

A production-quality, AI-powered document generation and classification system.
Extracts text from input documents, classifies them using Google Gemini, validates
required fields, and compiles pixel-faithful PDFs from LaTeX templates.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [What Was Built and Changed](#what-was-built-and-changed)
3. [Project Structure](#project-structure)
4. [Layout Engine](#layout-engine)
5. [Rendering Pipeline — Detailed](#rendering-pipeline--detailed)
6. [Template Architecture](#template-architecture)
7. [Audit Findings and Fixes](#audit-findings-and-fixes)
8. [LaTeX Escaping and Security](#latex-escaping-and-security)
9. [Supported Document Types](#supported-document-types)
10. [Installation](#installation)
11. [How to Run](#how-to-run)
12. [Customising Employee Data](#customising-employee-data)
13. [Adding a New Document Type](#adding-a-new-document-type)
14. [Error Reference](#error-reference)
15. [Future Enhancements](#future-enhancements)

---

## Project Overview

Turn2Law generates branded, print-quality onboarding letters (and future
document types) as PDFs. The workflow is:

```
Input PDF/DOCX/Image
        ↓
  Text Extraction  (PyMuPDF / python-docx / Tesseract)
        ↓
  AI Classification  (Google Gemini 2.5 Flash)
        ↓
  Schema Validation
        ↓
  LaTeX Template Rendering  (placeholder substitution + LaTeX escaping)
        ↓
  Two-pass pdflatex compilation
        ↓
  output.pdf
```

---

## What Was Built and Changed

This section documents every file that was created or refactored, and the
exact reason for each change.

### New Files Created

| File | What it is |
|------|-----------|
| `docgen/layout/layout.py` | Shared page geometry, margins, colours, decorative bar coordinates, watermark settings, and all vertical spacing values |
| `docgen/layout/typography.py` | Font package selection, global line spread, font-size command names, bullet list settings |
| `docgen/layout/assets.py` | Registry of every image asset: filename, render dimensions, and what each image represents |
| `docgen/layout/__init__.py` | Re-exports all constants so templates import from a single `layout` package |

### Files Refactored

| File | What changed |
|------|-------------|
| `docgen/utils/latex_writer.py` | Complete rewrite — see detailed breakdown below |
| `docgen/templates/onboarding_template.tex` | Complete rewrite — see detailed breakdown below |
| `docgen/app.py` | `_HERE` anchor, absolute template paths, absolute output paths |

---

## Project Structure

```
documentGeneration-master/
├── readme.md                         ← this file
└── docgen/
    ├── app.py                        ← main entry point
    ├── config.py                     ← Gemini API key, model name
    ├── schema.py                     ← required/optional fields per doc type
    ├── requirements.txt
    │
    ├── layout/                       ← Layout engine (design system)
    │   ├── __init__.py
    │   ├── layout.py                 ← geometry, colours, bar coords, spacing
    │   ├── typography.py             ← font, line-spread, sizes, list settings
    │   └── assets.py                 ← image filenames and render dimensions
    │
    ├── templates/
    │   └── onboarding_template.tex   ← onboarding letter (fully refactored)
    │
    ├── images/                       ← brand assets from the reference PDF
    │   ├── sample_asset_0_xref_36.jpeg       ← Turn2Law logo (header)
    │   ├── sample_asset_1_xref_47.jpeg       ← email envelope icon (footer)
    │   ├── sample_asset_2_xref_36.jpeg       ← reserved
    │   ├── sample_asset_3_xref_63.jpeg       ← reserved
    │   └── 2df383ea-...-1_171_229_2316_191.jpg  ← founder signature
    │
    ├── extractors/
    │   ├── pdf_extractor.py
    │   ├── docx_extractor.py
    │   └── image_extractor.py
    │
    ├── classifier/
    │   └── classify.py
    │
    ├── generators/
    │   └── generate.py
    │
    └── utils/
        ├── latex_writer.py           ← refactored rendering + compilation
        ├── pdf_writer.py             ← ReportLab fallback (unchanged)
        ├── file_utils.py
        └── retry.py
```

---

## Layout Engine

All design constants are defined once in `docgen/layout/` and never
duplicated in any `.tex` file. This makes future templates (Offer Letter,
NDA, Contract, MOU) automatically consistent without copy-pasting numbers.

### `layout/layout.py`

```
Page geometry
  PAGE_WIDTH_MM   = 210     A4 width
  PAGE_HEIGHT_MM  = 297     A4 height
  MARGIN_TOP_MM   = 28      accounts for gold bar (4pt) + band (26pt) + breathing room
  MARGIN_BOTTOM_MM = 25     accounts for footer band (22pt) + rule + email line
  MARGIN_LEFT_MM  = 13.5
  MARGIN_RIGHT_MM = 13.5

Brand colours (hex, no #)
  COLOR_GOLD      = E1A84A   Turn2Law gold
  COLOR_CHARCOAL  = 232323   near-black
  COLOR_BG        = F4F4F4   off-white page background

Top decorative bar coordinates (in pt from left edge)
  Thin gold strip:           full width, 4pt tall
  Charcoal parallelogram:    top edge 205→309, bottom edge 221→285
  Gold parallelogram:        top edge 335→510, bottom edge 358→487

Bottom decorative bar coordinates
  Thin gold strip:           full width, 4pt tall
  Left charcoal wedge:       bottom 0→34, top 0→26
  Left gold band:            bottom 34→178, top 49→156
  Right charcoal band:       bottom 274→338, top 255→319

Right-side diagonal stripes (background layer)
  6 white triangle slivers at opacity 0.35
  Apex positions as fractions of page width/height:
  (0.95, 0.20) (0.83, 0.27) (0.71, 0.34)
  (0.58, 0.41) (0.45, 0.48) (0.32, 0.55)
  Each stripe is 18pt wide

Watermark
  Text:     TURN2LAW
  Opacity:  0.04   (barely visible — matches reference)
  Rotation: 45°
  Font:     72pt bold

Vertical spacing (all values in em)
  After logo:           0.9
  After title:          0.35
  After date/ID line:   1.0
  After employee name:  0.28
  After intro para:     0.88
  After body para:      0.78
  Before pos. title:    0.88
  After pos. title:     0.28
  After bullets:        0.65
  After closing para:   0.88
  After "Best Regards": 0.28
  After signature img:  0.22
  After footer rule:    0.35
```

### `layout/typography.py`

```
Font package:   helvet  (Helvetica approximation for pdflatex)
Font family:    \sfdefault  (sans-serif throughout)
Line spread:    1.13  (relaxed leading matching the reference)

Font size commands used per element:
  Title:            \fontsize{22}{26}  (22pt, 26pt baseline skip)
  Date / Emp ID:    \large
  Employee name:    \LARGE\bfseries
  Body text:        \large
  Section heading:  \LARGE\bfseries
  Footer:           \small

Bullet list settings:
  leftmargin:  1.25em
  itemsep:     0.20em
  topsep:      0.15em
  parsep:      0pt
```

### `layout/assets.py`

```
Logo
  Filename:  sample_asset_0_xref_36
  Height:    1.22cm

Founder signature
  Filename:  2df383ea-bab3-42c5-bff0-3b02e82627a7-1_171_229_2316_191
  Width:     2.6cm

Email icon (footer)
  Filename:  sample_asset_1_xref_47
  Height:    0.40cm  (inline, baseline-aligned)
```

---

## Rendering Pipeline — Detailed

### `utils/latex_writer.py` — full breakdown

#### `render_latex(template_path, output_tex, output_pdf, values)`

1. **Resolve all paths to absolute** — `os.path.abspath()` on all three
   path arguments so the function works regardless of the Python process cwd.

2. **Set `work_dir` = template's own directory** — pdflatex is invoked
   with `-output-directory=<work_dir>` and `cwd=<work_dir>`. This is the
   critical fix that makes `\graphicspath` and other relative paths work.

3. **Inject absolute images path** — Before writing the rendered `.tex`,
   the literal string `\graphicspath{{./images/}}` is replaced with
   `\graphicspath{{<absolute/path/to/docgen/images/>}}`. This resolves the
   original bug where images failed to load whenever Python was invoked
   from any directory other than `docgen/`.

4. **LaTeX-escape all user values** — Every value in the `values` dict is
   passed through `_escape_latex()` before being substituted into the
   template. This prevents characters like `&`, `#`, `_`, `$`, `%` from
   breaking the LaTeX compiler or causing injection.

5. **Write rendered `.tex` next to the template** — Keeps all compilation
   artifacts (`.aux`, `.log`, `.pdf`) in `templates/` so they don't
   scatter into the Python cwd.

6. **Two pdflatex passes**:
   - Pass 1: LaTeX lays out the page, TikZ records node coordinates into
     `.aux`. `eso-pic` background is registered.
   - Pass 2: TikZ reads `.aux` coordinates back. `remember picture, overlay`
     decorations (the top and bottom bars) are now correctly positioned.
     A single pass produces undefined overlay positions on the first compile.

7. **`-halt-on-error` flag** — pdflatex stops immediately on the first
   error. Without this, pdflatex can produce a corrupt PDF and still exit 0.

8. **Error surfacing** — If pdflatex exits non-zero, the last 3000
   characters of the stdout log are embedded in the raised `RuntimeError`.
   This makes debugging compilation errors fast without hunting for `.log` files.

9. **Copy compiled PDF to `output_pdf`** — The caller specifies where they
   want the PDF. `shutil.copy2` moves it there from `templates/` after
   successful compilation.

#### `_run_pdflatex(tex_path, work_dir, pass_num)`

Internal function. Builds the pdflatex command list, runs it with
`subprocess.run(capture_output=True)`, checks the return code, and raises
`RuntimeError` with the log snippet on failure.

#### `_escape_latex(value)`

Escapes the following characters in order (backslash first to avoid
double-escaping):

| Character | LaTeX replacement |
|-----------|------------------|
| `\` | `\textbackslash{}` |
| `&` | `\&` |
| `%` | `\%` |
| `$` | `\$` |
| `#` | `\#` |
| `_` | `\_` |
| `{` | `\{` |
| `}` | `\}` |
| `~` | `\textasciitilde{}` |
| `^` | `\textasciicircum{}` |

The backslash sentinel trick (`\x00BACKSLASH\x00`) prevents the
replacement from double-escaping itself when it processes subsequent
characters in the string.

---

## Template Architecture

### `templates/onboarding_template.tex` — package-by-package breakdown

#### Packages and why each was chosen

| Package | Reason |
|---------|--------|
| `inputenc` (utf8) | Correct handling of non-ASCII characters in the source |
| `fontenc` (T1) | Proper hyphenation and glyph access for European characters |
| `helvet` | Helvetica approximation — closest sans-serif match to the reference font in pdflatex |
| `microtype` | Protrusion and expansion for improved kerning, line-break quality, and character spacing with zero visual overhead |
| `geometry` | Precise A4 margins: top 28mm, bottom 25mm, left/right 13.5mm |
| `graphicx` | `\includegraphics` for logo, signature, and email icon |
| `xcolor` | Named colours (`turngold`, `turncharcoal`, `turnbg`) |
| `eso-pic` | Background and foreground layers painted outside the text flow |
| `tikz` + `calc` library | Vector drawing of decorative bars and watermark |
| `enumitem` | Fine-grained bullet list control (itemsep, topsep, parsep, leftmargin) |
| `textpos` | Available for absolute mm-precise positioning (signature block, future use) |
| `parskip` | Suppresses LaTeX's default paragraph indent; explicit `\vspace` controls all spacing |
| `needspace` | Prevents the signature block from being split across pages |

#### Document layers (rendering order)

```
Layer 1 — Background (AddToShipoutPictureBG*)
  ├── Solid F4F4F4 off-white fill covering the full page
  ├── 6 white diagonal triangle stripes (bottom-right quadrant, opacity 0.35)
  └── TURN2LAW watermark (opacity 0.04, 45°, centred)

Layer 2 — Text flow (normal LaTeX body)
  ├── Logo (1.22cm height)
  ├── Title "Onboarding Letter -- Turn2Law" (22pt bold)
  ├── Date and Emp ID (\large)
  ├── Employee name (\LARGE bold)
  ├── Joining statement (\large, role in bold)
  ├── Body paragraph 1 (\large)
  ├── Body paragraph 2 (\large)
  ├── "Position Details" heading (\LARGE bold)
  ├── Bullet list: Role / Location / Joining Date
  ├── Closing paragraph (\large)
  ├── "Best Regards" + signature image (2.6cm wide)
  ├── Founder name + title (\large bold)
  └── Footer: \vfill → rule → email icon + address

Layer 3 — Foreground (AddToShipoutPictureFG*)
  ├── Top gold strip (full width, 4pt)
  ├── Top charcoal parallelogram
  ├── Top gold parallelogram
  ├── Bottom gold strip (full width, 4pt)
  ├── Bottom left charcoal wedge
  ├── Bottom left gold band
  └── Bottom right charcoal band
```

#### Placeholder tokens

All dynamic fields use `{{FIELD_NAME}}` syntax. `latex_writer.py` replaces
them via simple string substitution after LaTeX-escaping the values.

| Token | Content |
|-------|---------|
| `{{Employee_Name}}` | Full name — appears 3 times (headline, para 1, para 2) |
| `{{Emp_ID}}` | Employee ID code |
| `{{Role}}` | Job title — appears in joining statement and bullet list |
| `{{Joining_Date}}` | Start date |
| `{{Document_Date}}` | Letter issue date |

---

## Audit Findings and Fixes

This section documents every bug and deficiency found in the original
codebase, and exactly what was done to fix each one.

### `latex_writer.py` — 4 critical bugs

#### Bug 1 — Image paths never resolved
**Original behaviour:** `pdflatex` was called with `subprocess.run(["pdflatex", ..., output_tex])` 
from the Python process cwd. The template used `\graphicspath{{./images/}}`. 
This relative path resolved to wherever you ran Python from — almost never 
`docgen/images/`. All `\includegraphics` calls silently failed or errored.

**Fix:** `work_dir` is set to the template's directory. `\graphicspath{{./images/}}`
is replaced at render time with the absolute path to `docgen/images/` using
`os.path.abspath()`. Image loading now works from any working directory.

#### Bug 2 — Single pdflatex pass
**Original behaviour:** `subprocess.run(["pdflatex", ..., output_tex])` ran once.
TikZ `remember picture, overlay` (used for the decorative bars) writes node
coordinates to `.aux` on pass 1 and reads them on pass 2. On a single pass
the `.aux` doesn't exist yet, so overlay coordinates are undefined and the
decorative bars render incorrectly or not at all.

**Fix:** Two passes — `_run_pdflatex(..., pass_num=1)` then
`_run_pdflatex(..., pass_num=2)`. This is standard LaTeX practice for any
document using TikZ overlays or cross-references.

#### Bug 3 — Silent failure on compilation errors
**Original behaviour:** `subprocess.run(..., check=True)` raised a generic
`CalledProcessError` with no LaTeX context. Finding the actual error required
manually opening the `.log` file.

**Fix:** `capture_output=True` captures stdout (which pdflatex writes its log
to). On non-zero exit, the last 3000 characters of the log are embedded in the
`RuntimeError` message. The `-halt-on-error` flag also stops pdflatex
immediately on the first error rather than continuing and producing a corrupt PDF.

#### Bug 4 — No LaTeX escaping
**Original behaviour:** User-supplied values (employee name, role, etc.) were
substituted directly into the LaTeX source. A value containing `&`, `#`, `_`,
`$`, or `%` would break the compiler. A malicious value could inject arbitrary
LaTeX commands.

**Fix:** `_escape_latex()` sanitises all 10 LaTeX special characters before
substitution. The backslash sentinel trick prevents double-escaping.

---

### `onboarding_template.tex` — 8 issues

#### Issue 1 — `\linespread{1.03}` too tight
**Original:** `\linespread{1.03}` produced compressed text that felt noticeably
denser than the reference document.

**Fix:** Changed to `\linespread{1.13}` — relaxed leading that matches the
reference's comfortable vertical rhythm.

#### Issue 2 — No watermark
**Original:** The template had no watermark. The reference document has a
barely-visible diagonal "TURN2LAW" text centred on the page.

**Fix:** Added a TikZ `\node` in the background layer at `opacity=0.04`,
rotated 45°, 72pt bold, centred at (0.5\paperwidth, 0.5\paperheight).

#### Issue 3 — Crude TikZ email icon
**Original:** The footer email icon was drawn as a `tikzpicture` with a circle
and lines — a rough approximation that looked nothing like the reference icon.

**Fix:** `\IfFileExists{sample_asset_1_xref_47.jpeg}` uses the actual icon
image extracted from the reference PDF (`sample_asset_1_xref_47.jpeg`), which
was sitting unused in `images/`. A cleaner TikZ rectangle-with-flap envelope
serves as fallback if the file is missing.

#### Issue 4 — `\vfill` before signature caused drift
**Original:** `\vfill` was placed before the signature block. On any page
where body text was shorter than expected, the signature floated upward.
On longer content it moved further down. The signature position was
non-deterministic relative to the content.

**Fix:** Removed `\vfill` before the signature. Added `\needspace{5\baselineskip}`
to keep the entire signature block (regards / image / name / title) together
on the same page. The `\vfill` now appears only before the footer rule,
which is the correct placement — it anchors the footer to the bottom of the
text area while keeping the signature immediately below the closing paragraph.

#### Issue 5 — Default paragraph indent
**Original:** LaTeX's default paragraph mode adds first-line indentation.
The reference document uses no paragraph indents — all body text starts
flush left.

**Fix:** Added `\usepackage{parskip}` with `\setlength{\parskip}{0pt}` and
`\setlength{\parindent}{0pt}`. All spacing is now controlled by explicit
`\vspace` commands between sections.

#### Issue 6 — `\graphicspath` relative to wrong directory
**Original:** `\graphicspath{{./images/}}` was relative to wherever pdflatex
ran, which was the template directory (`templates/`). There is no
`templates/images/` folder. This caused all images to fail.

**Fix:** `latex_writer.py` replaces this string with the absolute path to
`docgen/images/` before writing the rendered `.tex` file.

#### Issue 7 — `parsep` not set in bullet list
**Original:** The `itemize` environment did not set `parsep=0pt`. LaTeX's
default `parsep` adds extra vertical space between wrapped lines within a
single bullet item, making multi-line bullets look uneven.

**Fix:** Added `parsep=0pt` to the `enumitem` options. All bullet items now
have consistent internal spacing.

#### Issue 8 — Non-breaking spaces missing in labels
**Original:** "Date:" and "Emp ID:" could break across lines at the colon,
leaving the label on one line and the value on the next.

**Fix:** Used `~` (non-breaking space) between labels and values:
`Date:~{{Document_Date}}` and `Emp~ID:~{{Emp_ID}}`.

---

### `app.py` — path resolution fix

**Original behaviour:** `file_path = "sample.pdf"` and
`output_tex = "output.tex"` were passed as bare relative strings.
If Python was invoked from any directory other than `docgen/`, these
resolved to the wrong locations.

**Fix:** Added `_HERE = os.path.dirname(os.path.abspath(__file__))`.
All paths — template, output `.tex`, output `.pdf`, and input file — are
constructed using `os.path.join(_HERE, ...)` so they are always anchored
to `docgen/` regardless of where the script is invoked from.

`TEMPLATE_MAP` values are also now absolute paths built with `_HERE`,
replacing the previous bare relative strings like `"templates/onboarding_template.tex"`.

---

## LaTeX Escaping and Security

User-supplied values (employee name, role, etc.) are sanitised before
being inserted into the LaTeX source. The `_escape_latex()` function in
`latex_writer.py` handles all 10 LaTeX special characters:

```python
_LATEX_ESCAPE_MAP = [
    ("\\", r"\textbackslash{}"),  # must be first — avoid double-escaping
    ("&",  r"\&"),
    ("%",  r"\%"),
    ("$",  r"\$"),
    ("#",  r"\#"),
    ("_",  r"\_"),
    ("{",  r"\{"),
    ("}",  r"\}"),
    ("~",  r"\textasciitilde{}"),
    ("^",  r"\textasciicircum{}"),
]
```

The backslash is processed first using a sentinel (`\x00BACKSLASH\x00`)
to prevent the replacement string itself from being re-escaped by
subsequent iterations.

This means an employee named `O'Brien & Associates` or a role like
`C++ Developer (Level_3)` will compile correctly without breaking the
template or producing unexpected output.

---

## Supported Document Types

| Type | Required Fields |
|------|----------------|
| `Onboarding_Letter` | Employee_Name, Emp_ID, Role, Joining_Date, Document_Date |
| `Offer_Letter` | Name, Company, Position, Start_Date, Salary |
| `NDA` | Name, Company, Date, Term, Jurisdiction |
| `Contract` | Client_Name, Company, Contract_Creation_Date, Service_Description, Payment_Amount, Start_Date, End_Date |
| `MOU` | PartyA_Name, PartyB_Name, Date, Purpose, Term, Jurisdiction |
| `IP_Agreement` | Name, Company, Date, Term, Jurisdiction |

Only `Onboarding_Letter` has a compiled LaTeX template at this time.
The other types are classified and validated but template files have
not yet been created for them.

---

## Installation

### Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.8+ | Runtime | [python.org](https://python.org) |
| MiKTeX (Windows) | pdflatex compiler | [miktex.org/download](https://miktex.org/download) |
| Tesseract OCR | Image text extraction | [tesseract-ocr](https://github.com/tesseract-ocr/tesseract) |

During MiKTeX installation, set **"Install missing packages on-the-fly"** to
**Yes**. MiKTeX will auto-download any required LaTeX packages on first run.

### Python dependencies

```cmd
.venv\Scripts\pip install -r docgen\requirements.txt
```

Key packages:

| Package | Purpose |
|---------|---------|
| `google-genai` | Gemini AI classification |
| `PyMuPDF` | PDF text extraction |
| `python-docx` | DOCX text extraction |
| `pytesseract` | OCR for image files |
| `Pillow` | Image processing |
| `python-dotenv` | `.env` file loading |
| `reportlab` | ReportLab fallback PDF writer |

### API key

Create `docgen/.env`:

```
GEMINI_API_KEY=your_key_here
```

---

## How to Run

```cmd
cd c:\Users\moury\Coding\Turn2Law\documentGeneration-master-1\documentGeneration-master\docgen
..\\.venv\Scripts\python app.py
```

Output: `docgen\output.pdf`

On first run MiKTeX will download any missing LaTeX packages. This takes
30–60 seconds. Every subsequent run compiles in 2–4 seconds.

---

## Customising Employee Data

Edit the `user_inputs` block at the bottom of `app.py`:

```python
user_inputs = {
    "Employee_Name": "Priya Sharma",
    "Emp_ID":        "T2L-HR-012",
    "Role":          "Legal Associate",
    "Joining_Date":  "15 August 2026",
    "Document_Date": "1 July 2026",
}
```

Then re-run:

```cmd
..\\.venv\Scripts\python app.py
```

Long roles and names wrap gracefully. The layout remains stable.

---

## Adding a New Document Type

Follow these steps to add a new template (e.g. Offer Letter):

### 1. Register the schema in `schema.py`

```python
"Offer_Letter": {
    "required": ["Name", "Company", "Position", "Start_Date", "Salary"],
    "optional": ["Manager_Name", "Response_Date"]
}
```

### 2. Create the template

Copy `templates/onboarding_template.tex` and rename it
`templates/offer_letter_template.tex`.

Keep the entire preamble unchanged (geometry, colours, decorative layers,
fonts, packages). Only replace the document body with the new content and
add the required `{{PLACEHOLDER}}` tokens.

The decorative bars, watermark, background tint, and footer will be
identical across all templates automatically because they live in the
preamble.

### 3. Register the template in `app.py`

```python
TEMPLATE_MAP = {
    "Onboarding_Letter": os.path.join(_HERE, "templates", "onboarding_template.tex"),
    "Offer_Letter":      os.path.join(_HERE, "templates", "offer_letter_template.tex"),
}
```

### 4. Update the classifier (if needed)

`classifier/classify.py` already lists `Offer_Letter` in `ALLOWED_TYPES`.
No change needed for the pre-registered types.

---

## Error Reference

| Error | Cause | Resolution |
|-------|-------|-----------|
| `ValueError: Missing required fields: [...]` | One or more required fields are absent from `user_inputs` | Supply all fields listed in `schema.py` for the doc type |
| `ValueError: No template found for document type: X` | `TEMPLATE_MAP` has no entry for the classified type | Add the template and register it in `TEMPLATE_MAP` |
| `RuntimeError: pdflatex pass N failed (exit 1). --- LaTeX log ---` | LaTeX compilation error | Read the embedded log snippet — it points directly to the failing line. Common causes: missing image file, unsupported character, missing package |
| `FileNotFoundError: pdflatex not found` | MiKTeX / TeX Live not installed or not on PATH | Install MiKTeX and ensure `pdflatex` is accessible from the terminal |
| `RuntimeError: Gemini unavailable after retries` | Gemini API rate limit or outage | The retry logic (exponential backoff, 5 attempts) handles transient failures. If persistent, check API quota |
| `ValueError: Unsupported file type` | Input file is not `.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg` | Convert the input to a supported format |

---

## Future Enhancements

- [ ] LaTeX templates for Offer Letter, NDA, Contract, MOU, IP Agreement
- [ ] Batch generation: accept a CSV of employees, produce one PDF per row
- [ ] REST API endpoint wrapping `generate_document()`
- [ ] XeLaTeX migration for native system font support (Arial / Helvetica Neue)
- [ ] HTML preview output alongside PDF
- [ ] Document versioning: output filename includes employee ID and date
- [ ] Multilingual support: RTL languages (Arabic, Hebrew) via XeLaTeX + bidi

---

## Security Notes

- User values are LaTeX-escaped before substitution — injection is prevented
- The `.env` file is in `.gitignore` — API keys are never committed
- Consider running pdflatex inside a sandboxed Docker container in production
  (LaTeX can execute shell commands via `\write18` if not restricted)
- To disable shell escape: add `-no-shell-escape` to the pdflatex command
  in `_run_pdflatex()` if your MiKTeX config has it enabled by default

---

*Last updated: July 2026*
