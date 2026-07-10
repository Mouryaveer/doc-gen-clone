# Turn2Law — Document Generation System

Production-quality, AI-powered document generation. Extracts text from input files, classifies them using Google Gemini, validates required fields, and compiles professionally drafted PDFs from XeLaTeX templates — all on official Turn2Law branded letterhead.

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Project Structure](#project-structure)
3. [Installation](#installation)
4. [How to Run](#how-to-run)
5. [Generating Each Document Type](#generating-each-document-type)
6. [Supported Document Types and Fields](#supported-document-types-and-fields)
7. [Layout and Design System](#layout-and-design-system)
8. [Rendering Pipeline](#rendering-pipeline)
9. [Template Architecture](#template-architecture)
10. [Audit Findings and Fixes](#audit-findings-and-fixes)
11. [Adding a New Template](#adding-a-new-template)
12. [Error Reference](#error-reference)

---

## How It Works

```
Input PDF / DOCX / Image
        ↓
  Text Extraction      PyMuPDF · python-docx · Tesseract OCR
        ↓
  AI Classification    Google Gemini 2.5 Flash  (skippable via generate_direct)
        ↓
  Schema Validation    schema.py
        ↓
  Template Rendering   {{placeholder}} substitution + LaTeX escaping
        ↓
  XeLaTeX × 2 passes   TikZ overlays require two passes
        ↓
  output.pdf
```

---

## Project Structure

```
documentGeneration-master/
├── readme.md
└── docgen/
    ├── app.py                        Main entry point
    ├── config.py                     Gemini API key + model name
    ├── schema.py                     Required/optional fields per document type
    ├── requirements.txt
    │
    ├── layouts/                      Shared brand components
    │   ├── brand_preamble.tex        Fonts, geometry, colours, background layer
    │   ├── brand_preamble_rendered.tex  Auto-generated at compile time
    │   └── signature_block.tex       Reusable signatory block
    │
    ├── templates/
    │   ├── onboarding_template.tex   Employee onboarding letter
    │   ├── nda_template.tex          Non-Disclosure Agreement
    │   ├── offer_letter_template.tex Job Offer Letter
    │   ├── contract_template.tex     Service Contract
    │   ├── mou_template.tex          Memorandum of Understanding
    │   └── ip_agreement_template.tex IP Assignment Agreement
    │
    ├── fonts/
    │   ├── Montserrat-Regular-Full.ttf
    │   ├── Montserrat-Bold-Full.ttf
    │   ├── Garet-Regular.ttf
    │   └── Garet-Bold.ttf
    │
    ├── images/
    │   ├── sample_asset_0_xref_36.jpeg    Turn2Law logo
    │   ├── sample_asset_1_xref_47.jpeg    Founder signature
    │   ├── header_decoration.png          Top bar (extracted from reference PDF)
    │   ├── footer_decoration.png          Bottom bar with email (extracted from reference PDF)
    │   └── watermark_logo_n.png           N watermark asset
    │
    ├── extractors/
    ├── classifier/
    ├── generators/
    └── utils/
        ├── latex_writer.py           Template renderer + two-pass XeLaTeX compiler
        ├── pdf_writer.py
        ├── file_utils.py
        └── retry.py
```

---

## Installation

### Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.8+ | Runtime | [python.org](https://python.org) |
| MiKTeX (Windows) | XeLaTeX compiler | [miktex.org/download](https://miktex.org/download) |
| Tesseract OCR | Image text extraction | [tesseract-ocr](https://github.com/tesseract-ocr/tesseract) |

During MiKTeX setup set **"Install missing packages on-the-fly"** to **Yes**.

### Python dependencies

```cmd
.venv\Scripts\pip install -r docgen\requirements.txt
```

### API key

Create `docgen\.env`:

```
GEMINI_API_KEY=your_key_here
```

> The API key is only needed when using `generate_document()` (the Gemini classification route).
> `generate_direct()` skips classification entirely and works without an API key.

---

## How to Run

```cmd
cd docgen
..\\.venv\Scripts\python app.py
```

Output: `docgen\output.pdf`

---

## Generating Each Document Type

Open `docgen\app.py` and edit the two sections at the very bottom.

### Step 1 — Set the document type

```python
DOC_TYPE = "NDA"   # change to any supported type
```

Supported values:

| Value | Document |
|-------|---------|
| `"Onboarding_Letter"` | Employee onboarding letter |
| `"NDA"` | Non-Disclosure Agreement |
| `"Offer_Letter"` | Job Offer Letter |
| `"Contract"` | Service Contract |
| `"MOU"` | Memorandum of Understanding |
| `"IP_Agreement"` | IP Assignment Agreement |

### Step 2 — Fill in the fields

Find the matching block in `SAMPLES` and replace the values:

---

#### Onboarding Letter

```python
DOC_TYPE = "Onboarding_Letter"

"Onboarding_Letter": {
    "Employee_Name": "Rahul Verma",
    "Emp_ID":        "T2L-AI-042",
    "Role":          "Software Engineer",
    "Joining_Date":  "1 August 2026",
    "Document_Date": "15 July 2026",
},
```

---

#### NDA

```python
DOC_TYPE = "NDA"

"NDA": {
    "Name":        "Arjun Mehta",
    "Company":     "Nexus Tech Pvt. Ltd., Bengaluru",
    "Date":        "15 July 2026",
    "Term":        "two (2) years",
    "Jurisdiction": "Chennai, Tamil Nadu",
    "Confidential_Info_Description": "AI contract review module architecture.",
    "Governing_Law": "",
},
```

---

#### Offer Letter

```python
DOC_TYPE = "Offer_Letter"

"Offer_Letter": {
    "Name":        "Priya Sharma",
    "Company":     "42 Lake View Apartments, Bengaluru - 560034",
    "Position":    "Legal Associate",
    "Start_Date":  "1 August 2026",
    "Salary":      "INR 6,00,000 per annum",
    "Manager_Name":   "Yash Phoghat",
    "Response_Date":  "25 July 2026",
    "HR_Manager":     "Yash Phoghat",
    "Benefits_Description": "Health insurance and INR 10,000 annual learning budget.",
},
```

---

#### Service Contract

```python
DOC_TYPE = "Contract"

"Contract": {
    "Client_Name":            "Ravi Constructions Pvt. Ltd.",
    "Company":                "Plot 12, MIDC, Pune - 411019",
    "Contract_Creation_Date": "15 July 2026",
    "Service_Description":    "Legal documentation and compliance advisory services.",
    "Payment_Amount":         "INR 1,50,000",
    "Start_Date":             "20 July 2026",
    "End_Date":               "19 January 2027",
    "Payment_Schedule":       "50% on signing, 50% on completion.",
    "Termination_Clause":     "",
},
```

---

#### MOU

```python
DOC_TYPE = "MOU"

"MOU": {
    "PartyA_Name":  "EFFIVIA TURN2LAW LEGAL PRIVATE LIMITED",
    "PartyB_Name":  "IIT Madras Incubation Cell, Chennai",
    "Date":         "15 July 2026",
    "Purpose":      "Joint development of AI-powered legal tools for student startups.",
    "Term":         "one (1) year",
    "Jurisdiction": "Chennai, Tamil Nadu",
    "Confidentiality": "All shared research data shall be treated as strictly confidential.",
    "Termination_Clause": "",
    "Governing_Law":      "",
},
```

---

#### IP Agreement

```python
DOC_TYPE = "IP_Agreement"

"IP_Agreement": {
    "Name":         "Siddharth Nair",
    "Company":      "Freelance Consultant, Hyderabad",
    "Date":         "15 July 2026",
    "Term":         "duration of engagement and three (3) years thereafter",
    "Jurisdiction": "Chennai, Tamil Nadu",
    "IP_Description": "All code relating to the AI contract analysis engine.",
    "Governing_Law":  "",
},
```

### Step 3 — Save and run

```cmd
..\\.venv\Scripts\python app.py
```

PDF saved at `docgen\output.pdf`.

> **Custom output filename:** Change `output_name="output"` in the `generate_direct(...)` call to any name, e.g. `output_name="nda_arjun_mehta"`. The file saves as `nda_arjun_mehta.pdf`.

> **Optional fields:** Fields set to `""` are silently skipped — the relevant clause adjusts automatically.

---

## Supported Document Types and Fields

### Onboarding Letter

| Field | Required | Description |
|-------|----------|-------------|
| `Employee_Name` | ✓ | Full name of the employee |
| `Emp_ID` | ✓ | Employee ID code |
| `Role` | ✓ | Job title |
| `Joining_Date` | ✓ | Date of joining |
| `Document_Date` | ✓ | Date the letter is issued |

### NDA

| Field | Required | Description |
|-------|----------|-------------|
| `Name` | ✓ | Receiving party's name |
| `Company` | ✓ | Receiving party's company/address |
| `Date` | ✓ | Effective date |
| `Term` | ✓ | Duration e.g. `"two (2) years"` |
| `Jurisdiction` | ✓ | Governing court/arbitration seat |
| `Confidential_Info_Description` | optional | Specific confidential info description |
| `Governing_Law` | optional | Additional governing law note |

### Offer Letter

| Field | Required | Description |
|-------|----------|-------------|
| `Name` | ✓ | Candidate's full name |
| `Company` | ✓ | Candidate's address/current company |
| `Position` | ✓ | Job title being offered |
| `Start_Date` | ✓ | Date of joining |
| `Salary` | ✓ | Fixed annual CTC |
| `Manager_Name` | optional | Reporting manager |
| `Response_Date` | optional | Offer acceptance deadline |
| `HR_Manager` | optional | HR contact name |
| `Benefits_Description` | optional | Additional benefits |

### Service Contract

| Field | Required | Description |
|-------|----------|-------------|
| `Client_Name` | ✓ | Name of the client |
| `Company` | ✓ | Client's company/address |
| `Contract_Creation_Date` | ✓ | Effective date |
| `Service_Description` | ✓ | Scope of services |
| `Payment_Amount` | ✓ | Total contract value |
| `Start_Date` | ✓ | Service period start |
| `End_Date` | ✓ | Service period end |
| `Payment_Schedule` | optional | Milestone payment details |
| `Termination_Clause` | optional | Additional termination terms |

### MOU

| Field | Required | Description |
|-------|----------|-------------|
| `PartyA_Name` | ✓ | First party |
| `PartyB_Name` | ✓ | Second party |
| `Date` | ✓ | Effective date |
| `Purpose` | ✓ | Collaboration purpose |
| `Term` | ✓ | Duration |
| `Jurisdiction` | ✓ | Governing jurisdiction |
| `Confidentiality` | optional | Custom confidentiality clause |
| `Termination_Clause` | optional | Additional termination terms |
| `Governing_Law` | optional | Additional governing law note |

### IP Agreement

| Field | Required | Description |
|-------|----------|-------------|
| `Name` | ✓ | Assignor's name |
| `Company` | ✓ | Assignor's company/address |
| `Date` | ✓ | Effective date |
| `Term` | ✓ | Duration of assignment obligations |
| `Jurisdiction` | ✓ | Governing jurisdiction |
| `IP_Description` | optional | Specific description of assigned IP |
| `Governing_Law` | optional | Additional governing law note |

---

## Layout and Design System

### Shared preamble — `layouts/brand_preamble.tex`

Every legal template (`\input`s this file). It provides:

- **Fonts:** Montserrat (body) + Garet (footer labels) via XeLaTeX fontspec
- **Geometry:** `top=74pt, bottom=66pt, left=42pt, right=32pt` — clears the header and footer decoration bars on every page
- **Brand background** (repeats on every page via `\AddToShipoutPictureBG`):
  - `header_decoration.png` — extracted from reference PDF at 288dpi, placed full-width at page top
  - `footer_decoration.png` — extracted from reference PDF at 288dpi, placed full-width at page bottom. Contains the email icon, E-MAIL label, and turntwolaw@gmail.com — **do not draw these separately**
  - Turn2Law logo — placed in the header area on every page
  - Watermark — full logo at 10% opacity covering the right-centre of the page

### Brand colours

| Name | Hex | Usage |
|------|-----|-------|
| `refgold` | `#FFBD58` | Primary gold |
| `refcharcoal` | `#2A2A2A` | Near-black |
| `refdarkgold` | `#B87C20` | Dark gold accent |

### Fonts

| Font | File | Usage |
|------|------|-------|
| Montserrat Regular | `Montserrat-Regular-Full.ttf` | All body text |
| Montserrat Bold | `Montserrat-Bold-Full.ttf` | Headings, bold elements |
| Garet Regular | `Garet-Regular.ttf` | Footer email address |
| Garet Bold | `Garet-Bold.ttf` | Footer E-MAIL label |

---

## Rendering Pipeline

### `utils/latex_writer.py`

1. Resolves all paths to absolute
2. Sets `work_dir` = template directory
3. Injects absolute paths by replacing:
   - `IMAGES_DIR_PLACEHOLDER` → `docgen/images/`
   - `FONTS_DIR_PLACEHOLDER` → `docgen/fonts/`
   - `LAYOUTS_DIR_PLACEHOLDER` → `docgen/layouts/`
4. Renders `brand_preamble_rendered.tex` with injected paths (used by `\input` in legal templates)
5. LaTeX-escapes all user field values
6. Replaces any remaining `{{FIELD}}` placeholders (optional fields not provided) with empty string
7. Runs XeLaTeX — **two passes** (required for TikZ `remember picture, overlay`)
8. Copies compiled PDF to destination

### LaTeX escape map

| Character | Output |
|-----------|--------|
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

---

## Template Architecture

### Onboarding Letter (`onboarding_template.tex`)

- Single-page, absolute positioning via `textpos`
- Zero-margin geometry — every element has a hard coordinate from the reference PDF
- Background uses `\AddToShipoutPictureBG*` (single page)
- All coordinates measured from `sample.pdf` via PyMuPDF
- Text y-positions = PyMuPDF bbox y0 + 4.4pt (ascender correction)

### Legal documents (NDA, Offer Letter, Contract, MOU, IP Agreement)

- Multi-page, normal LaTeX text flow
- All `\input{brand_preamble_rendered}` for shared brand layer
- Geometry: `top=74pt, bottom=66pt` clears header/footer decorations
- Background uses `\AddToShipoutPictureBG` (repeats on every page)
- Professionally drafted clauses under Indian Contract Act, 1872
- `\ifthenelse` guards on all optional fields — clause is silently omitted if field is empty

### Legal content standards

All legal templates are drafted to Indian jurisdiction with:
- Indian Contract Act, 1872
- Arbitration and Conciliation Act, 1996
- Copyright Act, 1957 (IP Agreement)
- Companies Act, 2013 (company references)
- Seat of arbitration: as specified in `Jurisdiction` field (default Chennai, Tamil Nadu)

---

## Audit Findings and Fixes (Onboarding Letter)

| Issue | Original | Fixed |
|-------|----------|-------|
| Wrong font | Nimbus Sans (helvet) | Montserrat extracted from reference PDF |
| Wrong body font size | 14.4pt (\large) | 13pt measured from reference |
| Wrong colours | #E1A84A gold, #232323 charcoal | #FFBD58, #2A2A2A measured from paths |
| Page background tinted | #F4F4F4 fill | White (no fill) |
| Watermark was text | TikZ text node | Full logo image at 10% opacity |
| Header shapes | TikZ rectangles | PNG extracted from reference PDF |
| Footer shapes | TikZ rectangles | PNG extracted from reference PDF |
| Email double-render | Drawn in both PNG and TikZ | Removed TikZ — PNG handles everything |
| Floating layout | \vspace + \noindent | Absolute textpos for every element |
| Single pdflatex pass | 1 pass | 2 XeLaTeX passes |
| No image path resolution | Relative \graphicspath | Absolute path injected at render time |
| No LaTeX escaping | Raw substitution | Full 10-char escape map |

---

## Adding a New Template

1. Add fields to `schema.py`
2. Copy an existing template as a starting point
3. Keep `\input{LAYOUTS_DIR_PLACEHOLDERbrand_preamble}` — this gives the new template the same brand identity automatically
4. Add to `TEMPLATE_MAP` in `app.py`:

```python
TEMPLATE_MAP = {
    ...
    "My_New_Doc": _t("my_new_doc_template.tex"),
}
```

5. Add sample inputs to `SAMPLES` in `app.py`
6. Set `DOC_TYPE = "My_New_Doc"` and run

---

## Error Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `ValueError: Missing required fields` | Required field absent from inputs | Supply all required fields per schema |
| `ValueError: No template found` | Type not in `TEMPLATE_MAP` | Add template and register it |
| `RuntimeError: xelatex pass N failed` | LaTeX compile error | Read embedded log — common: missing image, bad character |
| `FileNotFoundError: xelatex` | MiKTeX not installed | Install MiKTeX, verify with `xelatex --version` |
| `RuntimeError: Gemini unavailable` | API quota or outage | Retry — 5-attempt backoff runs automatically. Use `generate_direct()` to bypass |
| `ValueError: Unsupported file type` | Input not PDF/DOCX/image | Convert to supported format |

---

## Security Notes

- User values are LaTeX-escaped before insertion — injection is prevented
- `.env` is in `.gitignore` — API keys are never committed
- `generate_direct()` needs no API key — safe for offline use
- Add `-no-shell-escape` to the XeLaTeX command in `_run_xelatex()` in production to prevent `\write18` shell execution

---

*Last updated: July 2026*
