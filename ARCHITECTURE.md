# Turn2Law Document Generation Engine
## System Architecture & Technical Workflow

---

## 1. Overview

The Turn2Law Document Generation Engine is a modular, AI-assisted legal document generation platform that transforms structured user inputs and uploaded documents into professionally drafted, branded legal PDFs.

**The engine supports:**

- Multi-format document extraction (PDF, DOCX, images)
- AI-powered document classification via Google Gemini
- Schema-based field validation
- Dynamic `{{placeholder}}` replacement with LaTeX escaping
- Professionally drafted Indian-law legal templates
- Pixel-perfect Turn2Law branding on every page
- Multi-page legal documents with repeating brand headers and footers
- Two-pass XeLaTeX rendering
- Reusable template architecture with shared layout components

---

## 2. High-Level Workflow

```
USER
 │
 ▼
Upload Document / Select Template
 │
 ▼
┌──────────────────────────────────┐
│  Document Input Layer            │
│  PDF / DOCX / Image              │
└──────────────────────────────────┘
 │
 ▼
┌──────────────────────────────────┐
│  Extraction Engine               │
│  • PyMuPDF     (PDF)             │
│  • python-docx (DOCX)            │
│  • Tesseract   (Images / OCR)    │
└──────────────────────────────────┘
 │
 ▼
Extracted Plain Text
 │
 ▼
┌──────────────────────────────────┐
│  AI Classification Engine        │
│  Google Gemini 2.5 Flash         │
│  (skippable via generate_direct) │
└──────────────────────────────────┘
 │
 ▼
Detected Document Type
 │
 ▼
┌──────────────────────────────────┐
│  Schema Validation Engine        │
│  schema.py                       │
│  Required / optional fields      │
└──────────────────────────────────┘
 │
 ├── Required fields missing? ──► Ask user / raise ValueError
 │
 ▼
Final Structured Data Object  {field: value, ...}
 │
 ▼
┌──────────────────────────────────┐
│  Template Selection Engine       │
│  TEMPLATE_MAP in app.py          │
└──────────────────────────────────┘
 │
 ▼
Load Shared Brand Components
 │
 ▼
┌──────────────────────────────────┐
│  Layout Engine (layouts/)        │
│  • Header decoration             │
│  • Footer decoration             │
│  • Watermark                     │
│  • Typography (Montserrat/Garet) │
│  • Page geometry                 │
│  • Colour palette                │
└──────────────────────────────────┘
 │
 ▼
Load Selected Document Template
 │
 ▼
Replace Dynamic {{Placeholders}}  +  LaTeX escaping  +  optional field cleanup
 │
 ▼
┌──────────────────────────────────┐
│  XeLaTeX Rendering Engine        │
│  utils/latex_writer.py           │
│  Two-pass compilation            │
│  Pass 1: layout + TikZ coords    │
│  Pass 2: overlays finalised      │
└──────────────────────────────────┘
 │
 ▼
Production Quality PDF
 │
 ▼
Output Directory  (docgen/output.pdf)
```

---

## 3. Folder Responsibilities

```
docgen/
│
├── app.py
│      Main workflow controller.
│      Responsible for:
│      • Coordinating the complete pipeline
│      • Calling extraction, classification, validation
│      • Selecting template and triggering generation
│      • Exposing generate_document() (with Gemini classification)
│        and generate_direct() (direct, no API key required)
│      • Returning the final PDF path
│
├── config.py
│      Global configuration.
│      Contains:
│      • Gemini API key loading from .env
│      • Model name (gemini-2.5-flash)
│
├── schema.py
│      Validation Layer.
│      Defines per document type:
│      • required fields (must be non-empty)
│      • optional fields (silently omitted if empty)
│      Any field not supplied is replaced with ""
│      so \ifthenelse guards in templates work correctly.
│
├── classifier/
│      AI Layer.
│      Responsible ONLY for:
│        Extracted Text
│          ↓
│        Gemini 2.5 Flash
│          ↓
│        Document Type string
│      No rendering logic.
│      Includes retry logic with exponential backoff.
│
├── extractors/
│      Extraction Layer.
│        PDF   → PyMuPDF
│        DOCX  → python-docx
│        Image → Tesseract OCR
│        Output: Plain text string
│
├── generators/
│      Business Logic Layer.
│      Responsible for:
│      • Building Gemini prompts for document generation
│      • Prompt templates per document type
│
├── layouts/
│      Turn2Law Design System — Reusable brand components.
│      Contains:
│      • brand_preamble.tex       Fonts, geometry, colours, background layer
│      • brand_preamble_rendered.tex  Auto-generated at compile time
│      • signature_block.tex      Reusable signatory block
│      Every legal template \inputs brand_preamble.
│      The onboarding template uses it inline.
│
├── templates/
│      Contains ONLY document bodies.
│      Each file represents one document type.
│      ─────────────────────────────────────
│      onboarding_template.tex     Employee onboarding
│      nda_template.tex            Non-Disclosure Agreement
│      offer_letter_template.tex   Job Offer Letter
│      contract_template.tex       Service Contract
│      mou_template.tex            Memorandum of Understanding
│      ip_agreement_template.tex   IP Assignment Agreement
│
├── images/
│      Brand assets.
│      sample_asset_0_xref_36.jpeg   Turn2Law logo (header + watermark)
│      sample_asset_1_xref_47.jpeg   Founder signature
│      header_decoration.png         Top bar — extracted from reference PDF at 288dpi
│      footer_decoration.png         Bottom bar — extracted from reference PDF at 288dpi
│                                    Contains email icon, E-MAIL label, address.
│                                    Do NOT draw these separately in TikZ.
│      watermark_logo_n.png          N symbol with baked opacity
│
├── fonts/
│      Montserrat-Regular-Full.ttf   Body text
│      Montserrat-Bold-Full.ttf      Headings and bold
│      Garet-Regular.ttf             Footer email address
│      Garet-Bold.ttf                Footer E-MAIL label
│
├── utils/
│      Infrastructure layer.
│      latex_writer.py
│        • Injects absolute paths (images, fonts, layouts)
│        • Renders brand_preamble_rendered.tex
│        • LaTeX-escapes all user values
│        • Cleans up unused optional {{placeholders}}
│        • Runs XeLaTeX — two passes
│        • Copies compiled PDF to destination
│        • Surfaces compilation errors with log snippet
│
│      pdf_writer.py    ReportLab fallback (plain text → PDF)
│      file_utils.py    Multi-format text extraction dispatcher
│      retry.py         Exponential backoff for Gemini API calls
│
└── output/             Generated PDFs land here (default: docgen/output.pdf)
```

---

## 4. Supported Document Types

| Document | Purpose | Multi-page | Compiler |
|----------|---------|-----------|---------|
| Onboarding Letter | Employee onboarding | No (single page) | XeLaTeX |
| NDA | Non-Disclosure Agreement | Yes | XeLaTeX |
| Offer Letter | Employment offer | Yes | XeLaTeX |
| Contract | Service agreement | Yes | XeLaTeX |
| MOU | Business collaboration | Yes | XeLaTeX |
| IP Agreement | Intellectual property assignment | Yes | XeLaTeX |

---

## 5. Document Generation Workflow (Detailed)

```
1.  User selects document type  or  uploads reference document
        ↓
2.  If reference document uploaded:
      Extraction Engine → Plain text
        ↓
      Gemini Classification → Document type string
        ↓
    If document type already known:
      Skip directly to step 4
        ↓
3.  Schema loaded from schema.py
        ↓
4.  Required field check
      Missing fields? → ValueError (caller must supply them)
        ↓
5.  Optional fields filled with "" for missing keys
        ↓
6.  Structured data dictionary built  { "Name": "Arjun Mehta", ... }
        ↓
7.  TEMPLATE_MAP lookup → template .tex path selected
        ↓
8.  latex_writer.render_latex() called:
        ↓
9.  Absolute path injection:
      IMAGES_DIR_PLACEHOLDER   → docgen/images/
      FONTS_DIR_PLACEHOLDER    → docgen/fonts/
      LAYOUTS_DIR_PLACEHOLDER  → docgen/layouts/
        ↓
10. brand_preamble_rendered.tex written with injected paths
        ↓
11. {{Placeholder}} substitution with LaTeX-escaped values
        ↓
12. Remaining {{FIELD}} placeholders (optional, not supplied) → ""
        ↓
13. Rendered .tex written to templates/ directory
        ↓
14. XeLaTeX Pass 1:
      Page layout computed
      TikZ node coordinates written to .aux file
        ↓
15. XeLaTeX Pass 2:
      TikZ overlays resolved from .aux
      Header/footer PNG layers rendered on every page
        ↓
16. Compiled PDF copied to docgen/output.pdf
        ↓
17. Path returned to caller
```

---

## 6. Template Composition

Every document is assembled from reusable building blocks:

```
┌───────────────────────────────────┐
│  Brand Header                     │  ← header_decoration.png (288dpi extract)
│  Turn2Law logo                    │  ← sample_asset_0_xref_36.jpeg
├───────────────────────────────────┤
│  Document Title                   │  ← template-specific
├───────────────────────────────────┤
│  Metadata (Date, Parties, Ref)    │  ← template-specific
├───────────────────────────────────┤
│  Dynamic Legal Body               │  ← template-specific clauses
│  • Definitions                    │
│  • Obligations                    │
│  • Confidentiality                │
│  • Term and Termination           │
│  • Dispute Resolution             │
│  • Governing Law                  │
├───────────────────────────────────┤
│  Signature Block                  │  ← signature_block.tex / inline
├───────────────────────────────────┤
│  Brand Footer                     │  ← footer_decoration.png (288dpi extract)
│  Email icon + label + address     │  ← baked into footer_decoration.png
└───────────────────────────────────┘
```

---

## 7. Placeholder Lifecycle

```
User Input (Python dict)
        ↓
Schema Validation
  required fields present?
  optional fields defaulted to ""?
        ↓
_escape_latex(value)
  \  →  \textbackslash{}
  &  →  \&
  %  →  \%
  $  →  \$
  #  →  \#
  _  →  \_
  {  →  \{
  }  →  \}
  ~  →  \textasciitilde{}
  ^  →  \textasciicircum{}
        ↓
tex.replace("{{FieldName}}", escaped_value)
        ↓
re.sub(r"\{\{[A-Za-z_]+\}\}", "", tex)
  (removes any remaining unfilled optional placeholders)
        ↓
Written to .tex file
        ↓
XeLaTeX compiles → PDF
```

---

## 8. Branding System

Every document shares the same brand identity. Only the document body changes.

| Component | Source | Applied via |
|-----------|--------|------------|
| Header decoration | `header_decoration.png` | `\AddToShipoutPictureBG` in brand_preamble |
| Footer decoration | `footer_decoration.png` | `\AddToShipoutPictureBG` in brand_preamble |
| Turn2Law logo | `sample_asset_0_xref_36.jpeg` | TikZ node, top-left every page |
| Watermark | `sample_asset_0_xref_36.jpeg` | TikZ node at 10% opacity, right-centre |
| Primary font | `Montserrat-Regular/Bold-Full.ttf` | fontspec `\setmainfont` |
| Footer font | `Garet-Regular/Bold.ttf` | fontspec `\newfontfamily\garetfont` |
| Gold colour | `#FFBD58` | `\definecolor{refgold}` |
| Charcoal colour | `#2A2A2A` | `\definecolor{refcharcoal}` |
| Dark gold accent | `#B87C20` | `\definecolor{refdarkgold}` |
| Page size | 595.5 × 842.25 pt | `\usepackage[geometry]` |

**Critical rule:** `footer_decoration.png` already contains the email icon, E-MAIL label, and turntwolaw@gmail.com rendered from the reference PDF. Do NOT draw these elements separately in TikZ — doing so causes double-rendering overlap.

---

## 9. Legal Drafting Standards

All templates are drafted to Indian jurisdiction and include, where applicable:

**Governing legislation:**
- Indian Contract Act, 1872
- Arbitration and Conciliation Act, 1996
- Companies Act, 2013
- Copyright Act, 1957 (IP Agreement)

**Standard clause structure:**
- Definitions
- Purpose / Scope
- Obligations
- Confidentiality
- Term and Survival
- Payment Terms (where applicable)
- Intellectual Property
- Limitation of Liability
- Indemnification
- Force Majeure (Contract)
- Dispute Resolution (arbitration, seat = Jurisdiction field)
- Governing Law
- Entire Agreement
- Amendment
- Severability
- No Partnership / Independent Contractor
- Signatures + Witness section

---

## 10. Adding a New Document Type

```
Step 1 — schema.py
  Add entry:
  "My_Doc_Type": {
      "required": ["Field1", "Field2", ...],
      "optional": ["OptField1", ...],
  }

Step 2 — templates/my_doc_type_template.tex
  Start with:
    \documentclass[10pt]{article}
    \input{LAYOUTS_DIR_PLACEHOLDERbrand_preamble}
  Keep the \input line — this gives the template the full
  brand identity automatically (header, footer, watermark,
  fonts, geometry, colours).
  Write only the document body below \begin{document}.
  Use {{Field1}}, {{Field2}} as placeholders.
  Use \ifthenelse{\equal{{{OptField1}}}{}}{}{clause text}
  for optional clauses.

Step 3 — app.py TEMPLATE_MAP
  Add:
  "My_Doc_Type": _t("my_doc_type_template.tex"),

Step 4 — app.py SAMPLES
  Add sample inputs for testing.

Step 5 — classifier/classify.py ALLOWED_TYPES
  Add "My_Doc_Type" to the tuple if AI classification is needed.

Step 6 — Test
  Set DOC_TYPE = "My_Doc_Type" in app.py
  Run: python app.py
  Verify output.pdf
```

---

## 11. End-to-End Pipeline Summary

```
Upload File / Select Template
        ↓
Extraction Engine (PyMuPDF / python-docx / Tesseract)
        ↓
AI Classification (Gemini 2.5 Flash)  [optional — skippable]
        ↓
Schema Validation (schema.py)
        ↓
User Input Collection / Field Filling
        ↓
Template Selection (TEMPLATE_MAP)
        ↓
Shared Layout + Branding (brand_preamble.tex)
        ↓
Placeholder Injection + LaTeX Escaping
        ↓
XeLaTeX Two-Pass Rendering (utils/latex_writer.py)
  Pass 1 → layout + TikZ coordinate recording
  Pass 2 → overlays + background layers finalised
        ↓
Production PDF  (595.5 × 842.25 pt, fonts embedded)
        ↓
docgen/output.pdf
```

---

## 12. Tech Stack Reference

| Layer | Technology |
|-------|-----------|
| Language | Python 3.8+ |
| AI Classification | Google Gemini 2.5 Flash (`google-genai`) |
| PDF Extraction | PyMuPDF (fitz) |
| DOCX Extraction | python-docx |
| Image OCR | pytesseract + Pillow |
| PDF Compilation | XeLaTeX (MiKTeX on Windows) |
| Font Loading | fontspec (XeLaTeX package) |
| Absolute Layout | textpos (LaTeX package) |
| Background Layers | eso-pic + tikz (LaTeX packages) |
| Conditional Clauses | ifthen (LaTeX package) |
| Tables | tabularx, array (LaTeX packages) |
| Body Fonts | Montserrat Regular + Bold (TTF) |
| Footer Fonts | Garet Regular + Bold (TTF) |
| Config | python-dotenv |
| Version Control | Git + GitHub |

---

*Last updated: July 2026*
