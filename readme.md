# Turn2Law — Document Generation System

An AI-powered document generation and classification system that extracts text from input files, classifies them using Google Gemini, validates required fields, and compiles production-quality PDFs from pixel-faithful LaTeX templates.

The onboarding letter template is a reverse-engineered reproduction of the official Turn2Law reference PDF — same fonts, same colours, same coordinates, same decorative elements — with full dynamic field replacement.

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Project Structure](#project-structure)
3. [Installation](#installation)
4. [How to Run](#how-to-run)
5. [Customising Employee Data](#customising-employee-data)
6. [Supported Document Types](#supported-document-types)
7. [Layout Engine](#layout-engine)
8. [Rendering Pipeline](#rendering-pipeline)
9. [Template Architecture](#template-architecture)
10. [What Was Reverse-Engineered](#what-was-reverse-engineered)
11. [Audit Findings and Fixes](#audit-findings-and-fixes)
12. [LaTeX Escaping and Security](#latex-escaping-and-security)
13. [Adding a New Template](#adding-a-new-template)
14. [Error Reference](#error-reference)

---

## How It Works

```
Input PDF / DOCX / Image
        ↓
  Text Extraction       PyMuPDF · python-docx · Tesseract OCR
        ↓
  AI Classification     Google Gemini 2.5 Flash
        ↓
  Schema Validation     schema.py
        ↓
  Template Rendering    {{placeholder}} substitution + LaTeX escaping
        ↓
  XeLaTeX × 2 passes    TikZ overlays require two passes
        ↓
  output.pdf
```

---

## Project Structure

```
documentGeneration-master/
├── readme.md
└── docgen/
    ├── app.py                    Main entry point
    ├── config.py                 Gemini API key + model name
    ├── schema.py                 Required/optional fields per document type
    ├── requirements.txt
    │
    ├── layout/                   Design system — shared constants
    │   ├── __init__.py
    │   ├── layout.py             Page geometry, colours, bar coords, spacing
    │   ├── typography.py         Font, line-spread, sizes, list settings
    │   └── assets.py             Image filenames and render dimensions
    │
    ├── fonts/                    Fonts extracted from reference PDF + full versions
    │   ├── Montserrat-Regular-Full.ttf
    │   ├── Montserrat-Bold-Full.ttf
    │   ├── Garet-Regular.ttf
    │   └── Garet-Bold.ttf
    │
    ├── templates/
    │   └── onboarding_template.tex   Pixel-faithful onboarding letter
    │
    ├── images/                   Brand assets extracted from reference PDF
    │   ├── sample_asset_0_xref_36.jpeg      Turn2Law logo (header)
    │   ├── sample_asset_1_xref_47.jpeg      Founder signature (square, 80×80pt)
    │   ├── sample_asset_2_xref_36.jpeg      Reserved
    │   ├── sample_asset_3_xref_63.jpeg      Reserved
    │   ├── watermark_bg.jpeg                Background watermark image (1950×1050px)
    │   └── footer_icon_xref47.jpeg          Email icon reference
    │
    ├── extractors/
    │   ├── pdf_extractor.py
    │   ├── docx_extractor.py
    │   └── image_extractor.py
    │
    ├── classifier/
    │   └── classify.py           Gemini-based document type classifier
    │
    ├── generators/
    │   └── generate.py           Prompt builder for Gemini generation
    │
    └── utils/
        ├── latex_writer.py       Template renderer + two-pass XeLaTeX compiler
        ├── pdf_writer.py         ReportLab fallback (plain text → PDF)
        ├── file_utils.py         Format dispatcher
        └── retry.py              Exponential backoff for Gemini API calls
```

---

## Installation

### Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.8+ | Runtime | [python.org](https://python.org) |
| MiKTeX (Windows) | XeLaTeX compiler | [miktex.org/download](https://miktex.org/download) |
| Tesseract OCR | Image text extraction | [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract) |

During MiKTeX setup, set **"Install missing packages on-the-fly"** to **Yes**. MiKTeX will auto-download any required LaTeX packages on first run.

### Python dependencies

```cmd
.venv\Scripts\pip install -r docgen\requirements.txt
```

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
cd docgen
..\\.venv\Scripts\python app.py
```

Output: `docgen\output.pdf`

On first run MiKTeX may download missing LaTeX packages — this takes 30–60 seconds. Every subsequent run takes 2–4 seconds.

---

## Customising Employee Data

Edit the `user_inputs` dict at the bottom of `app.py`:

```python
user_inputs = {
    "Employee_Name": "Priya Sharma",
    "Emp_ID":        "T2L-HR-012",
    "Role":          "Legal Associate",
    "Joining_Date":  "15 August 2026",
    "Document_Date": "1 July 2026",
}
```

Then re-run `python app.py`. Long names and roles wrap gracefully without affecting layout.

---

## Supported Document Types

| Type | Required Fields | Template |
|------|----------------|---------|
| `Onboarding_Letter` | Employee_Name, Emp_ID, Role, Joining_Date, Document_Date | ✓ Complete |
| `Offer_Letter` | Name, Company, Position, Start_Date, Salary | Pending |
| `NDA` | Name, Company, Date, Term, Jurisdiction | Pending |
| `Contract` | Client_Name, Company, Contract_Creation_Date, Service_Description, Payment_Amount, Start_Date, End_Date | Pending |
| `MOU` | PartyA_Name, PartyB_Name, Date, Purpose, Term, Jurisdiction | Pending |
| `IP_Agreement` | Name, Company, Date, Term, Jurisdiction | Pending |

---

## Layout Engine

All design constants live in `docgen/layout/` and are never duplicated in `.tex` files. Any future template imports from this single source.

### `layout/layout.py` — Page geometry, colours, spacing

```
Page size:   595.5 × 842.25 pt  (matches reference PDF MediaBox exactly)

Brand colours (measured from path fills in sample.pdf):
  refgold      #FFBD58   primary gold
  refcharcoal  #2A2A2A   near-black
  refdarkgold  #B87C20   dark gold accent
  Page background: white (no tint)

Top bar shapes (pt from left edge, PyMuPDF coordinates):
  Gold rect:        x [-198.33 → 281.11],  y [-53.77 → 8.03]
  Charcoal rect:    x [240.86  → 725.43],  y [-9.72  → 24.87]
  Gold rect:        x [340.48  → 518.39],  y [-9.70  → 52.10]
  Dark gold rect:   x [498.99  → 537.90],  y [24.88  → 52.10]

Bottom bar shapes:
  Gold rect:        x [259.96  → 775.39],  y [834.51 → 886.92]
  Charcoal rect:    x [-164.98 → 319.60],  y [826.13 → 860.71]
  Gold rect:        x [42.06   → 219.98],  y [798.91 → 860.71]
  Dark gold rect:   x [22.55   → 61.47],   y [798.91 → 826.12]

Watermark (xref=63, 1950×1050px):
  Placed at x=-378.37pt, y=312.83pt (intentionally bleeds off left edge)
  Size: 973.87 × 524.44 pt
```

### `layout/typography.py` — Font and sizing

```
Fonts:
  Body:   Montserrat-Regular / Montserrat-Bold  (full TTFs, 445KB each)
  Footer: Garet-Regular / Garet-Bold  (subset TTFs extracted from reference)
  Engine: XeLaTeX + fontspec

Font sizes (measured from reference PDF):
  Title:             22 pt  (baseline skip 27pt)
  Employee name:     15 pt  (baseline skip 20pt)
  Section heading:   15 pt  (baseline skip 20pt)
  Body text:         13 pt  (baseline skip 18pt)
  Footer labels:      8.424 pt

Line spread: 18/13 = 1.3846  (13pt text, 18pt leading)
```

### `layout/assets.py` — Image registry

```
Logo:
  File:   sample_asset_0_xref_36.jpeg  (1280×340 px)
  Placed: x=28.49pt, y=32.59pt, w=269.35pt, h=72.03pt

Signature:
  File:   sample_asset_1_xref_47.jpeg  (308×308 px — square)
  Placed: x=47.59pt, y=651.43pt, w=80.28pt, h=80.28pt

Watermark:
  File:   watermark_bg.jpeg  (1950×1050 px)
  Placed: x=-378.37pt, y=312.83pt (bottom of image in PDF coords)
```

---

## Rendering Pipeline

### `utils/latex_writer.py` — step by step

**1. Resolve all paths to absolute**
`os.path.abspath()` on all three path arguments (template, output tex, output pdf). Works from any Python cwd.

**2. Set work_dir to the template's directory**
XeLaTeX is invoked with `cwd=work_dir` and `-output-directory=work_dir`. All relative paths inside the template resolve correctly.

**3. Inject absolute paths**
Before writing the rendered `.tex`:
- `IMAGES_DIR_PLACEHOLDER` → absolute path to `docgen/images/`
- `FONTS_DIR_PLACEHOLDER` → absolute path to `docgen/fonts/`

This is how `fontspec` finds Montserrat and Garet regardless of where Python runs from.

**4. LaTeX-escape all user values**
Every value in `user_inputs` passes through `_escape_latex()` before substitution. Prevents `&`, `#`, `_`, `$`, `%` from breaking the compiler.

**5. Write rendered `.tex` next to the template**
Keeps `.aux`, `.log`, and `.pdf` artifacts in `templates/`.

**6. Two XeLaTeX passes**
- Pass 1: page layout, TikZ records node coordinates to `.aux`
- Pass 2: TikZ `remember picture, overlay` reads `.aux` — decorative bars and background render correctly

**7. `-halt-on-error` flag**
XeLaTeX stops on the first error instead of producing a corrupt PDF silently.

**8. Error surfacing**
Non-zero exit code → last 4000 chars of the XeLaTeX log raised as `RuntimeError`. No hunting for `.log` files.

**9. Copy PDF to output_pdf**
`shutil.copy2` moves the compiled PDF from `templates/` to the caller-requested destination.

---

## Template Architecture

### `templates/onboarding_template.tex`

The template is a fixed-layout absolute-positioning document. Every element has a hard coordinate taken directly from the reference PDF. There is no floating layout.

**Compiler:** XeLaTeX (required for `fontspec` — native font loading)

**Packages used:**

| Package | Reason |
|---------|--------|
| `fontspec` | Load Montserrat and Garet TTFs directly by filename |
| `geometry` | Zero-margin page: `top=0 bottom=0 left=0 right=0` — all positions are absolute |
| `graphicx` | `\includegraphics` for logo, signature, watermark |
| `xcolor` | Named colours `refgold`, `refcharcoal`, `refdarkgold` |
| `eso-pic` | Background layer painted before page content |
| `tikz` + `calc` | Drawing decorative bar shapes and bullet dots |
| `textpos` | Absolute mm/pt placement of every text and image block |

**Rendering layers:**

```
Layer 1 — Background (AddToShipoutPictureBG*)
  ├── Watermark image (xref=63, 1950×1050px JPEG, bleeds left)
  ├── Bottom bar: 4 overlapping rectangles (gold, charcoal, gold, dark gold)
  └── Top bar:    4 overlapping rectangles (gold, charcoal, gold, dark gold)

Layer 2 — Content (textpos absolute blocks)
  ├── Logo          28.49, 32.59pt
  ├── Title         42.0,  123.01pt
  ├── Date          42.0,  152.33pt
  ├── Emp ID        42.0,  170.33pt
  ├── Name          42.0,  206.59pt
  ├── Joining stmt  42.0,  226.60pt
  ├── Para 1        42.0,  282.87pt
  ├── Para 2        42.0,  354.90pt
  ├── Pos. heading  42.0,  445.18pt
  ├── Bullet dots   51.0,  468.62 / 486.63 / 540.65pt  (TikZ circles)
  ├── Bullet text   64.09, 465.19 / 483.20 / 537.22pt
  ├── Closing para  42.0,  573.23pt
  ├── Best Regards  42.0,  627.25pt
  ├── Signature img 47.59, 651.43pt  (80.28×80.28pt)
  ├── Founder name  42.0,  717.53pt
  ├── Founder title 42.0,  737.79pt
  ├── Divider rule  41.98, 753.17pt  (521×3pt filled rect)
  ├── Email icon    409.46, 797.25pt  (TikZ: black square + white envelope)
  ├── E-MAIL label  441.96, 802.16pt
  └── Email address 441.96, 815.99pt
```

**Placeholder tokens** (replaced by `latex_writer.py`):

| Token | Field |
|-------|-------|
| `{{Employee_Name}}` | Full name — 3 occurrences |
| `{{Emp_ID}}` | Employee ID |
| `{{Role}}` | Job title — 2 occurrences |
| `{{Joining_Date}}` | Start date |
| `{{Document_Date}}` | Letter issue date |

**Path injection tokens** (replaced by `latex_writer.py` before field substitution):

| Token | Replaced with |
|-------|--------------|
| `FONTS_DIR_PLACEHOLDER` | Absolute path to `docgen/fonts/` |
| `IMAGES_DIR_PLACEHOLDER` | Absolute path to `docgen/images/` |

---

## What Was Reverse-Engineered

The reference PDF (`sample.pdf`) was fully audited using PyMuPDF to extract hard measurements. Every value in the template comes from this audit — nothing was estimated or assumed.

**Measurements extracted:**

| Element | Tool | Data extracted |
|---------|------|---------------|
| Page size | `page.mediabox` | 595.5 × 842.25 pt |
| All text spans | `page.get_text("dict")` | font name, size, x/y bbox, colour, flags |
| All images | `page.get_images()` + `page.get_image_rects()` | xref, placement rect, native pixel size |
| All vector paths | `page.get_drawings()` | fill colour, bounding rect, vertex coordinates |
| Embedded fonts | `doc.get_page_fonts()` + `doc.extract_font()` | font name, TTF bytes |
| Watermark image | `doc.extract_image(63)` | 1950×1050 JPEG, placement rect |
| Signature image | `doc.extract_image(47)` | 308×308 JPEG, placement rect |

**Key discoveries:**

- The watermark is a JPEG image (xref=63), not text — placed at x=-378pt intentionally bleeding off the left edge
- The email icon is a vector drawing (paths 14/15/17) — a filled black square with a white envelope shape inside, not an image
- The divider is a 3pt thick filled black rectangle, not a `\rule` stroke
- The decorative top and bottom bars are groups of overlapping rectangles with three colours each — not parallelograms
- The signature (xref=47) is a square 308×308px image placed at 80.28×80.28pt, overlapping the lower portion of the founder name text

---

## Audit Findings and Fixes

This section documents every bug found in the original codebase and what was done to fix it.

### Bug 1 — Wrong font (most impactful)

**Original:** Template used `\usepackage{helvet}` with `\renewcommand{\familydefault}{\sfdefault}`. This maps to Nimbus Sans L — a different sans-serif with different glyph widths, weight distribution, and spacing. All line breaks, paragraph heights, and column widths differed from the reference.

**Reference fonts (from PDF):** `Montserrat-Regular`, `Montserrat-Bold` (body), `Garet-Regular`, `Garet-Bold` (footer labels).

**Fix:** Switched to XeLaTeX + `fontspec`. Fonts were extracted from the reference PDF as TTF subsets, then replaced with full 445KB Montserrat TTFs downloaded from the official source. Garet subset TTFs are used for the footer (they contain all required glyphs).

### Bug 2 — Wrong font sizes

**Original:** Used `\large` (= 14.4pt in a 12pt document class) for body text. Used `\LARGE` (= 20.7pt) for the employee name and section heading.

**Reference sizes (measured):** Body = 13.0pt, Name/Heading = 15.0pt, Footer = 8.424pt.

**Fix:** Replaced all relative size commands with explicit `\fontsize{13pt}{18pt}`, `\fontsize{15pt}{20pt}`, `\fontsize{22pt}{27pt}`, `\fontsize{8.424pt}{11pt}`.

### Bug 3 — Wrong brand colours

**Original colours (guessed):** Gold `#E1A84A`, Charcoal `#232323`, no dark gold, page tint `#F4F4F4`.

**Correct colours (measured from path fills):**

| Colour | Original | Correct |
|--------|----------|---------|
| Gold | `#E1A84A` | `#FFBD58` |
| Charcoal | `#232323` | `#2A2A2A` |
| Dark gold | missing | `#B87C20` |
| Page background | `#F4F4F4` tint | white (no fill) |

### Bug 4 — Watermark was text, should be an image

**Original:** A TikZ `\node` with `opacity=0.04` rendering "TURN2LAW" as 72pt bold text.

**Reference:** A 1950×1050px JPEG (xref=63) placed at x=-378pt, y=312pt, size 973×524pt. It bleeds off the left edge intentionally and covers the lower-right portion of the page.

**Fix:** Extracted the JPEG from the reference PDF and placed it with exact coordinates.

### Bug 5 — Floating layout instead of absolute positioning

**Original:** All content used `\vspace` + `\noindent` in normal document flow. Position of every element depended on font metrics and line-break decisions. Switching fonts changed every position.

**Fix:** Every element is placed in a `textpos` absolute block with coordinates taken directly from PyMuPDF measurements. No element can drift.

### Bug 6 — +4.4pt textpos correction

**Discovery:** After switching to absolute positioning, all text blocks were 4–6pt too high. PyMuPDF reports glyph bbox y0 at the top of the ascender. LaTeX `textpos` places the block top and then adds internal leading before the first baseline. The measured difference was consistently 4.4pt across all text sizes.

**Fix:** All text block y-coordinates have +4.4pt added (e.g. title: 118.61 → 123.01). Images and vector path blocks use the raw PyMuPDF y-coordinate with no offset.

### Bug 7 — Wrong signature image and size

**Original:** Used `sample_asset_2_xref_36` (a copy of the logo) at 2.5cm width.

**Reference:** `sample_asset_1_xref_47` (308×308px, xref=47) placed at x=47.59, y=651.43, size 80.28×80.28pt (square).

**Fix:** Corrected filename, width, height, and position.

### Bug 8 — Email icon was a crude TikZ approximation

**Original:** A circle + rectangle + diagonal lines — did not resemble the reference icon.

**Reference:** Paths 14, 15, 17 form a 27.37×27.37pt filled black square with a white envelope body rectangle and triangular flap.

**Fix:** Reproduced as TikZ with exact vertex coordinates computed from the path measurement data.

### Bug 9 — Divider rendered as `\rule` stroke

**Original:** `\noindent\rule{\textwidth}{1.1pt}` — a stroked line.

**Reference:** Path 16 — a filled black rectangle 521.03pt wide × 3pt tall at y=753.17pt.

**Fix:** `\color{black}\rule{521.03pt}{3pt}` placed via textpos at exact coordinates.

### Bug 10 — Single pdflatex pass

**Original:** `subprocess.run(["pdflatex", ...])` — one pass only.

**Reference template uses TikZ `remember picture, overlay`** which requires two passes: pass 1 records node coordinates to `.aux`, pass 2 reads them.

**Fix:** Two XeLaTeX passes in `_run_xelatex()`.

### Bug 11 — Image paths never resolved

**Original:** pdflatex ran from the Python process cwd. `\graphicspath{{./images/}}` resolved relative to wherever Python was launched — almost never `docgen/images/`.

**Fix:** Work dir set to `templates/`. `IMAGES_DIR_PLACEHOLDER` replaced with the absolute path to `docgen/images/` before compilation.

### Bug 12 — No LaTeX escaping

**Original:** User values were substituted directly. An employee named `O'Brien & Co.` or a role like `C++ Developer` would break the compiler.

**Fix:** `_escape_latex()` sanitises all 10 LaTeX special characters before substitution.

### Final accuracy (measured)

| Element | Δy (pt) |
|---------|---------|
| Title | 0.0 |
| Date | +0.5 |
| Emp ID | +0.4 |
| Employee name | +0.2 |
| Para 2 | +0.2 |
| Position heading | 0.0 |
| Bullet — Role | -0.2 |
| Bullet — Location | +0.2 |
| Bullet — Date | +0.1 |
| Best Regards | -0.9 |
| Founder name | -1.6 |
| Email label | -1.7 |
| Email address | -1.4 |

Maximum positional delta: **±2pt** across all measured elements (sub-pixel at screen resolution).

---

## LaTeX Escaping and Security

All user-supplied values are sanitised through `_escape_latex()` in `latex_writer.py` before being inserted into the template source.

Escape map (applied in order):

| Character | LaTeX output |
|-----------|-------------|
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

The backslash is processed first using a sentinel (`\x00BACKSLASH\x00`) to prevent double-escaping. An employee name like `O'Brien & Associates (Level_3)` compiles correctly.

**Production note:** Consider running XeLaTeX inside a sandboxed Docker container. LaTeX can execute shell commands via `\write18` if not restricted. Add `-no-shell-escape` to the XeLaTeX command in `_run_xelatex()` to disable this.

---

## Adding a New Template

1. Add required/optional fields to `schema.py`.
2. Copy `templates/onboarding_template.tex` to `templates/<type>_template.tex`.
3. Keep the entire preamble (fontspec, geometry, colours, background layer) unchanged — brand identity is identical across all documents.
4. Replace the content blocks (`\begin{textblock}...`) with the new document's layout.
5. Add the mapping in `app.py`:
   ```python
   TEMPLATE_MAP = {
       "Onboarding_Letter": os.path.join(_HERE, "templates", "onboarding_template.tex"),
       "Offer_Letter":      os.path.join(_HERE, "templates", "offer_letter_template.tex"),
   }
   ```
6. Add the type to `ALLOWED_TYPES` in `classifier/classify.py` if not already present.

---

## Error Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `ValueError: Missing required fields: [...]` | Fields absent from `user_inputs` | Supply all fields listed in `schema.py` for the doc type |
| `ValueError: No template found for document type: X` | Type not in `TEMPLATE_MAP` | Add the template and register it |
| `RuntimeError: xelatex pass N failed (exit 1). --- LaTeX log ---` | XeLaTeX compilation error | Read the embedded log — common causes: missing font file, missing image, bad character in value |
| `FileNotFoundError: xelatex not found` | MiKTeX not installed or not on PATH | Install MiKTeX, verify with `xelatex --version` |
| `RuntimeError: Gemini unavailable after retries` | API rate limit or outage | Retry later — 5-attempt exponential backoff runs automatically |
| `ValueError: Unsupported file type` | Input not `.pdf`, `.docx`, or image | Convert the input to a supported format |

---

*Last updated: July 2026*
