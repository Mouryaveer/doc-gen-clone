# Turn2Law Document Generation Engine — Architecture Reference

*Last updated: July 2026*

---

## 1. System Overview

The Turn2Law Document Generation Engine is a full-stack legal document platform with three distinct layers:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Vanilla HTML/CSS/JS | 9-step wizard SPA in `turn2law-site-main/` |
| **API Server** | FastAPI + Uvicorn | HTTP bridge exposing all backend capabilities |
| **Backend Engine** | Python 3.11 | PDF generation, branding, signing, classification |

The backend does the heavy lifting. The API server is a thin HTTP wrapper. The frontend consumes the API with no server-side rendering.

---

## 2. High-Level Request Flow

```
Browser (docengine-app.html)
        │
        │  HTTP/JSON or multipart/form-data
        ▼
┌─────────────────────────────────────────┐
│  FastAPI Server  (docgen/api.py)        │
│  http://localhost:8000                  │
│                                         │
│  POST /api/generate                     │
│  POST /api/generate-with-branding       │
│  POST /api/classify                     │
│  POST /api/sign                         │
│  POST /api/validate-cert                │
│  GET  /api/templates                    │
│  GET  /api/schema/{doc_type}            │
│  GET  /api/preview/{doc_id}             │
│  GET  /files/{filename}   (static)      │
└──────────────┬──────────────────────────┘
               │  Python function calls
       ┌───────┴────────────────────────────────────────────────┐
       │                                                        │
       ▼                                                        ▼
┌─────────────────────────┐               ┌──────────────────────────────┐
│  Document Pipeline      │               │  Branding Engine             │
│  (docgen/app.py)        │               │  (docgen/branding/)          │
│                         │               │                              │
│  extract_text()         │               │  resolve_preamble()          │
│  classify_document()    │               │  validate_asset()            │
│  validate_inputs()      │               │  process_image()             │
│  render_latex()         │               │  compute_layout()            │
│  sign_generated_pdf()   │               │  generate_preamble()         │
└─────────────────────────┘               └──────────────────────────────┘
```


---

## 3. Component Map

```
documentGeneration-master/
│
├── README.md                      ← Quick start, API reference, usage examples
├── ARCHITECTURE.md                ← This file
│
├── docgen/                        ← Entire backend lives here
│   │
│   ├── api.py                     ← FastAPI app, all 8 endpoints, CORS, static files
│   ├── app.py                     ← Core Python library (no HTTP, importable)
│   ├── schema.py                  ← Field definitions for every document type
│   ├── config.py                  ← Gemini API key + model name from .env
│   │
│   ├── classifier/
│   │   └── classify.py            ← Gemini 2.5 Flash → document type string
│   │
│   ├── extractors/
│   │   ├── pdf_extractor.py       ← PyMuPDF text extraction
│   │   ├── docx_extractor.py      ← python-docx text extraction
│   │   └── image_extractor.py     ← pytesseract OCR
│   │
│   ├── branding/
│   │   ├── __init__.py            ← Public API (lazy imports to avoid circular deps)
│   │   ├── branding_engine.py     ← resolve_preamble() — turn2law or custom branch
│   │   ├── validators.py          ← PNG magic bytes, dimensions, file size checks
│   │   ├── image_processor.py     ← Alpha-channel trim via Pillow getbbox()
│   │   ├── layout_builder.py      ← px→pt conversion, margin formula, .tex generation
│   │   ├── asset_manager.py       ← save/load/list/delete BrandProfile on disk
│   │   ├── models.py              ← BrandProfile, BrandMode, ValidationResult, LayoutParameters
│   │   ├── config.py              ← BrandingConfig frozen dataclass, CONFIG singleton
│   │   ├── exceptions.py          ← BrandingEngineError, BrandProfileError, etc.
│   │   └── profiles/              ← Runtime: one subdir per brand profile (gitignored)
│   │
│   ├── digital_signature/
│   │   ├── signer.py              ← sign_pdf_file() — public entry point
│   │   ├── pdf_signer.py          ← pyHanko: SimpleSigner, PdfSigner, CMS blob
│   │   ├── certificate_loader.py  ← .pfx/.p12 → CertificateBundle (key + cert + chain)
│   │   ├── certificate_validator.py  ← Expiry, key usage, basic chain check
│   │   ├── metadata.py            ← SignatureMetadata (signer, reason, location, time)
│   │   ├── signature_config.py    ← Field name constant, digest algorithm (sha256)
│   │   ├── timestamp.py           ← Optional TSA (RFC 3161) client
│   │   └── verification.py        ← Post-sign verification helpers
│   │
│   ├── utils/
│   │   ├── latex_writer.py        ← render_latex(): path injection, escaping, XeLaTeX runner
│   │   ├── file_utils.py          ← extract_text() dispatcher (pdf/docx/image)
│   │   ├── pdf_writer.py          ← ReportLab plain-text fallback
│   │   └── retry.py               ← Exponential backoff decorator for Gemini calls
│   │
│   ├── templates/                 ← XeLaTeX document bodies (one .tex per doc type)
│   ├── layouts/                   ← brand_preamble.tex — shared fonts/geometry/assets
│   ├── images/                    ← Turn2Law brand PNGs (header, footer, watermark, logo)
│   ├── fonts/                     ← Montserrat + Garet TTF files
│   └── generated_docs/            ← API output directory (gitignored)
│
└── turn2law-site-main/
    ├── docengine-app.html         ← 9-step document wizard (single-page app)
    ├── docengine.html             ← Marketing page for the Doc Engine product
    ├── index.html                 ← Main Turn2Law website
    ├── introspector.html          ← Introspector product page
    ├── legal-services.html        ← Legal services product page
    ├── resources.html             ← Resources hub
    ├── login.html / signup.html   ← Auth pages
    └── turn2law-logo.png
```


---

## 4. Document Generation Pipeline

Every PDF generation call — whether from the API, the app.py `__main__` block, or direct Python import — goes through the same pipeline:

```
User input (doc_type + field dict)
        │
        ▼
1. validate_inputs(doc_type, fields)
   └── Reads DOCUMENT_SCHEMAS from schema.py
   └── Raises ValueError if any required field is empty
        │
        ▼
2. TEMPLATE_MAP lookup
   └── Maps doc_type string → absolute .tex file path
        │
        ▼
3. resolve_preamble(brand_profile)          [only for branded generation]
   └── turn2law mode → returns docgen/layouts/brand_preamble.tex
   └── custom mode   → validates assets → processes images → computes layout
                      → generates brand_preamble.tex → returns its path
        │
        ▼
4. render_latex(template_path, output_tex, output_pdf, fields, preamble_path)
   │
   ├── a. Read template .tex source
   │
   ├── b. Inject absolute paths into placeholders:
   │      IMAGES_DIR_PLACEHOLDER  → docgen/images/
   │      FONTS_DIR_PLACEHOLDER   → docgen/fonts/
   │      LAYOUTS_DIR_PLACEHOLDER → docgen/layouts/
   │
   ├── c. If preamble_path is set (custom branding):
   │      Strip the template's own preamble block (before \begin{document})
   │      Replace it with the custom brand preamble content
   │      Substitute T2L asset filenames in \begin{document} body
   │      with the profile's processed PNG absolute paths
   │
   ├── d. Render FONTS_DIR_PLACEHOLDER inside brand_preamble_rendered.tex
   │
   ├── e. LaTeX-escape all field values (_escape_latex)
   │      \ → \textbackslash{}   & → \&   % → \%   $ → \$
   │      # → \#   _ → \_   { → \{   } → \}
   │
   ├── f. Replace {{FIELD}} tokens with escaped values
   │      Remaining unfilled optional {{FIELD}} tokens → ""
   │
   ├── g. Write rendered .tex to templates/ directory
   │
   ├── h. XeLaTeX Pass 1 (layout + TikZ coordinate recording)
   │      xelatex -interaction=nonstopmode -halt-on-error
   │
   └── i. XeLaTeX Pass 2 (TikZ overlays + eso-pic background finalised)
           └── Compiled PDF copied to output_pdf destination
        │
        ▼
5. PDF written to docgen/generated_docs/{doc_id}.pdf   [API path]
   or docgen/output.pdf                                [direct path]
```


---

## 5. Branding Engine

The branding engine lives entirely in `docgen/branding/` and is the most complex subsystem. It handles two modes:

### 5a. Turn2Law mode (default)

```
resolve_preamble(BrandProfile(mode=TURN2LAW))
        │
        ▼
SHA-256 hash of docgen/layouts/brand_preamble.tex
  First call  → record hash in module-level _t2l_preamble_hash
  Later calls → re-hash and compare; raise BrandProfileError if modified
        │
        ▼
Return absolute path to brand_preamble.tex
(no files written, no images touched)
```

### 5b. Custom mode

```
resolve_preamble(BrandProfile(mode=CUSTOM, header_image_path=...))
        │
        ▼
Check header_image_path is set and file exists
        │
        ▼
Check cache: {profiles_dir}/{profile_id}/brand_preamble.tex exists?
  Yes → return cached path immediately (no reprocessing)
  No  → run full pipeline:
        │
        ▼
Step 1 — validate_asset() for each uploaded image
  • Read first 8 bytes → must equal PNG magic b'\x89PNG\r\n\x1a\n'
  • Open with Pillow → read width/height
  • header/footer: width ≥ 595px (CONFIG.min_header_width_px)
  • watermark/logo: no minimum width (centred assets)
  • header: height ≤ 150px
  • footer: height ≤ 120px
  • file size ≤ CONFIG.max_asset_bytes (default 5 MB)
        │
        ▼
Step 2 — process_image() for each asset
  • Open with Pillow, convert to RGBA
  • alpha.getbbox() → bounding box of non-transparent pixels
  • bbox is None → raise BrandAssetProcessingError("all_transparent")
  • Crop to bbox (removes transparent borders)
  • Save as lossless PNG to {profiles_dir}/{profile_id}/{asset}.png
  • Return (width_px, height_px) of cropped result
        │
        ▼
Step 3 — compute_layout(header_h_px, footer_h_px, dpi)
  • header_pt = header_h_px * 72 / dpi
  • footer_pt = footer_h_px * 72 / dpi
  • top_margin    = max(74.0, header_pt + 16.0)
  • bottom_margin = max(66.0, footer_pt + 16.0)
  • left=42pt, right=32pt (fixed)
  • Returns LayoutParameters dataclass
        │
        ▼
Step 4 — generate_preamble(profile, layout, dest_path)
  • Builds XeLaTeX preamble string with:
      - fontspec: Montserrat (body) + Garet (footer) via FONTS_DIR_PLACEHOLDER
      - geometry: computed margins from LayoutParameters
      - graphicx, xcolor, eso-pic, tikz+calc, textpos, needspace, etc.
      - \AddToShipoutPictureBG block:
          header node (always)        → absolute POSIX path to header.png
          footer node (if present)    → absolute POSIX path to footer.png
          watermark node (if present) → centered, opacity=0.10
          logo node (if present)      → top-left corner
  • Write UTF-8 to {profiles_dir}/{profile_id}/brand_preamble.tex
  • Scan generated text for T2L asset names (header_decoration, etc.)
    → if found: delete file and raise BrandProfileError (safety check)
        │
        ▼
Step 5 — XeLaTeX draftmode pre-check
  • xelatex -draftmode -interaction=nonstopmode on a wrapper .tex
  • Non-zero exit + no stdout → MiKTeX update nag → skip gracefully
  • Non-zero exit + log output → delete preamble + raise BrandProfileError
        │
        ▼
Step 6 — save_profile(profile)
  • Write {profiles_dir}/{profile_id}/profile.json
  • JSON: all scalar fields, created_at as ISO 8601, mode as string value
        │
        ▼
Return absolute path to brand_preamble.tex
```

### 5c. Atomic cleanup

If any step d–f raises an exception, every file appended to `files_written[]` is deleted before re-raising. This prevents partial/corrupt profile directories.

### 5d. BrandProfile persistence layout

```
docgen/branding/profiles/
└── {profile_id}/
    ├── profile.json          ← serialised BrandProfile
    ├── header.png            ← trimmed header asset
    ├── footer.png            ← trimmed footer asset (if provided)
    ├── watermark.png         ← trimmed watermark asset (if provided)
    ├── logo.png              ← trimmed logo asset (if provided)
    └── brand_preamble.tex    ← generated XeLaTeX preamble (cached)
```

### 5e. Configuration env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `BRAND_PROFILES_DIR` | `docgen/branding/profiles/` | Where profiles are stored |
| `BRAND_MAX_ASSET_BYTES` | `5242880` (5 MB) | Max PNG upload size |
| `BRAND_MIN_HEADER_WIDTH_PX` | `595` | Min width for header/footer PNGs |
| `BRAND_ASSET_DPI` | `96` | Source image DPI for px→pt formula |


---

## 6. Digital Signature Pipeline

Signing uses **CMS (Cryptographic Message Syntax) / PAdES** via pyHanko and Python's `cryptography` library.

```
User provides: .pfx file + password + signer metadata
        │
        ▼
certificate_loader.load_certificate(cert_path, password)
  • Opens PKCS#12 with cryptography.hazmat.primitives.serialization.pkcs12
  • Extracts: private_key, certificate (x509), chain certs
  • Returns CertificateBundle(subject_cn, issuer_cn, certificate, private_key)
        │
        ▼
certificate_validator.validate(bundle)
  • Checks not_valid_after > now (not expired)
  • Checks key_usage.digital_signature == True
  • Does NOT verify chain trust (self-signed certs pass)
        │
        ▼
pdf_signer.sign_pdf(input_pdf, output_pdf, bundle, metadata, cert_path, password)
  │
  ├── SimpleSigner.load_pkcs12(pfx_file, passphrase)
  │     pyHanko loads the signing key and cert chain natively
  │
  ├── PdfSignatureMetadata(field_name, md_algorithm="sha256",
  │     name, reason, location, contact_info)
  │
  ├── IncrementalPdfFileWriter(BytesIO(pdf_bytes))
  │     Incremental update = original bytes untouched, signature appended
  │     The hash covers the original content exactly
  │
  ├── SigFieldSpec + VisibleSigSettings (if visible=True)
  │     Places a text stamp on the last page:
  │       "Digitally signed by [name]"
  │       "Date: YYYY.MM.DD HH:MM:SS +00'00'"
  │       "Reason: ..."   "Location: ..."
  │
  └── PdfSigner.sign_pdf(writer, output=output_buf)
        1. Reserve byte range in PDF for CMS blob
        2. SHA-256 hash of everything EXCEPT reserved range
        3. Sign hash with private key → RSA/ECDSA signature bytes
        4. Wrap in CMS (PKCS#7) envelope with certificate chain
        5. Write CMS blob into reserved range
        6. Write final signed bytes to output file
        │
        ▼
output_signed.pdf
  • Any modification after signing invalidates the signature
  • Adobe Acrobat / PDF validators verify by decrypting with public key
    and comparing hashes
```

### asyncio conflict and fix

pyHanko calls `asyncio.run()` internally (for TSA timestamp requests). When called from a FastAPI `async def` endpoint, there is already a running event loop, causing:

```
RuntimeError: asyncio.run() cannot be called from a running event loop
```

**Fix** (`api.py`): both `/api/sign` and `/api/validate-cert` offload to a thread-pool executor:

```python
loop = asyncio.get_event_loop()
sign_fn = functools.partial(sign_generated_pdf, ...)
await loop.run_in_executor(None, sign_fn)
```

`run_in_executor(None, fn)` uses Python's default `ThreadPoolExecutor`. Each thread starts with no active event loop, so pyHanko's `asyncio.run()` works correctly.

### Certificate types

| Type | Trust level | Use case |
|------|------------|---------|
| Self-signed (make_test_cert.py) | None — shows warning in Acrobat | Development / testing |
| Class 2 DSC (MCA-approved CA) | Medium | Internal documents |
| Class 3 DSC (eMudhra, nCode, Sify) | High — chain to root CA | Client-facing, legally enforceable |


---

## 7. API Server (api.py)

The FastAPI server is a thin HTTP adapter over the backend library. It does not contain business logic.

### Endpoint reference

| Method | Path | Auth | Body | Returns |
|--------|------|------|------|---------|
| GET | `/api/templates` | None | — | `[{id, name, description, icon, required_fields, optional_fields}]` |
| GET | `/api/schema/{doc_type}` | None | — | `{doc_type, required:[{key,label,placeholder,type}], optional:[...]}` |
| POST | `/api/generate` | None | JSON | `{success, doc_id, pdf_url, doc_type}` |
| POST | `/api/generate-with-branding` | None | multipart | `{success, doc_id, pdf_url, doc_type}` |
| POST | `/api/classify` | None | multipart (file) | `{doc_type, confidence}` |
| POST | `/api/sign` | None | multipart | `{success, doc_id, signed_pdf_url}` |
| GET | `/api/preview/{doc_id}` | None | — | `{exists, pdf_url, signed_url}` |
| POST | `/api/validate-cert` | None | multipart | `{valid, subject, issuer, expires}` |
| GET | `/files/{filename}` | None | — | PDF bytes (static file) |

### Error shape

All endpoints return a consistent error envelope:
```json
{ "success": false, "error": "human-readable message" }
```
HTTP status: `400` for validation errors, `404` for not found, `500` for server errors.

### Output file handling

Generated PDFs are written to `docgen/generated_docs/` (created at startup).  
Document IDs are 12-character hex strings from `uuid.uuid4().hex[:12]`.

```
generated_docs/
├── abc123def456.pdf          ← unsigned output
└── abc123def456_signed.pdf   ← signed output (after /api/sign)
```

Files are served at `/files/{filename}` via FastAPI's `StaticFiles` mount. The frontend uses these URLs for iframe preview and direct download links.

### CORS

All origins are permitted (`allow_origins=["*"]`). Tighten this in production by listing specific allowed origins.

### Running the server

```powershell
# From docgen/ directory
..\.venv\Scripts\python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Interactive Swagger docs: `http://localhost:8000/docs`  
OpenAPI JSON: `http://localhost:8000/openapi.json`


---

## 8. Frontend Architecture (docengine-app.html)

The frontend is a single 111 KB HTML file with no external JS libraries or build step. All CSS and JS are inline.

### Design system

Identical to all other Turn2Law site pages:
- CSS variables: `--gold: #D8AB5B`, `--gold-deep: #B98F42`, `--navy: #0A1628`, `--ink: #111111`
- Fonts: Inter (body), Poppins (headings), DM Mono (monospace labels) via Google Fonts
- Components: frosted-glass nav, `.btn-gold` / `.btn-ghost`, shadow system, reveal animations

### Application state

A single `state` object holds all wizard data:
```javascript
const state = {
  currentStep: 1,           // 1–9
  selectedDocType: null,    // "NDA"
  selectedDocMeta: null,    // {id, name}
  inputMethod: 'form',      // 'form' | 'pdf' | 'docx' | 'image'
  formData: {},             // {field_key: value}
  schemaRequired: [],       // [{key, label, placeholder, type}]
  schemaOptional: [],
  brandingMode: 'turn2law', // 'turn2law' | 'custom'
  brandAssets: {},          // {header: File, footer: File, ...}
  brandProfileId: null,
  brandProfileName: null,
  docId: null,              // 12-char hex from /api/generate
  pdfUrl: null,             // "/files/{docId}.pdf"
  signedPdfUrl: null,
  signerName: null,
  certFile: null,           // File object
  certValidated: false,
  generatedAt: null,        // ISO timestamp
};
```

### Step flow

| Step | Panel | API call | Entry hook |
|------|-------|----------|-----------|
| 1 | Select document type | `GET /api/templates` | On page load |
| 2 | Input method | `POST /api/classify` (if file upload) | On step entry |
| 3 | Fill form | `GET /api/schema/{doc_type}` | On step entry (once) |
| 4 | Branding picker | None | — |
| 5 | Review & confirm | None | `renderReview()` |
| 6 | Generate | `POST /api/generate` or `/api/generate-with-branding` | Auto-triggered |
| 7 | PDF preview | `GET /files/{docId}.pdf` | iframe src set |
| 8 | Digital signature | `POST /api/validate-cert`, `POST /api/sign` | On button click |
| 9 | Download | `GET /files/{docId}.pdf` or `_signed.pdf` | On button click |

### Key functions

```
loadTemplates()       → fetch /api/templates → render Step 1 cards
loadSchema(docType)   → fetch /api/schema/{doc_type} → render Step 3 form
generateDocument()    → animated timeline → call generate API → goToStep(7)
validateCert()        → POST /api/validate-cert → show result + enable sign button
signDocument()        → POST /api/sign (via run_in_executor) → goToStep(9)
goToStep(n)           → show/hide panels, update sidebar, fire entry hooks
showToast(msg, type)  → top-right notification (success/error/info, 3s auto-dismiss)
saveFormDraft()       → localStorage.setItem (debounced 500ms)
loadFormDraft()       → localStorage.getItem → restore field values
resetApp()            → wipe state, reset all UI, return to Step 1
```

### Responsive breakpoints

| Breakpoint | Layout change |
|-----------|--------------|
| > 1000px | Sidebar visible (280px fixed left), main panel offset |
| ≤ 1000px | Sidebar hidden, horizontal mobile progress strip at top |
| ≤ 680px | All grids collapse to single column |


---

## 9. Template System

### Document body templates

Each `.tex` file in `docgen/templates/` contains only the document body — no branding, no geometry. Branding comes from `brand_preamble.tex` (or a custom equivalent).

```latex
% Pattern for templates that use \input (NDA, Offer Letter, Contract, MOU, IP Agreement)
\documentclass[10pt]{article}
\input{LAYOUTS_DIR_PLACEHOLDERbrand_preamble}
\begin{document}
  % Document body using {{FIELD_NAME}} placeholders
  % Optional clauses guarded by:
  \ifthenelse{\equal{{{OptionalField}}}{}}{}{clause text here}
\end{document}
```

The Onboarding Letter embeds branding assets directly (no `\input`) — it was built before the brand_preamble system and its assets are substituted at the `latex_writer` level.

### Placeholder lifecycle

```
{{Employee_Name}} in .tex
        ↓
_escape_latex("Mourya Veer")  →  "Mourya Veer"  (no special chars here)
_escape_latex("50% equity")   →  "50\% equity"
        ↓
tex.replace("{{Employee_Name}}", "Mourya Veer")
        ↓
re.sub(r"\{\{[A-Za-z_]+\}\}", "", tex)  →  removes any leftover optional placeholders
        ↓
XeLaTeX compiles the clean .tex → PDF
```

### Adding a new document type — checklist

```
1. schema.py
   Add "My_Type": { "required": [...], "optional": [...] }

2. templates/my_type_template.tex
   \documentclass[10pt]{article}
   \input{LAYOUTS_DIR_PLACEHOLDERbrand_preamble}
   \begin{document}
   ... use {{Field}} placeholders ...
   \end{document}

3. app.py → TEMPLATE_MAP
   "My_Type": _t("my_type_template.tex"),

4. classifier/classify.py → ALLOWED_TYPES tuple
   Add "My_Type"

5. api.py → _TEMPLATE_META dict
   "My_Type": {"name": "...", "description": "...", "icon": "..."}

6. api.py → FIELD_META dict
   Add entries for any new field keys

7. Test: python app.py  (set DOC_TYPE = "My_Type")
```

The API picks up the new type automatically — no endpoint changes needed.

---

## 10. Supported Document Types

| Key | Display name | Required fields | Optional fields | Multi-page |
|-----|-------------|-----------------|-----------------|-----------|
| `Onboarding_Letter` | Onboarding Letter | Employee_Name, Emp_ID, Role, Joining_Date, Document_Date | — | No |
| `NDA` | Non-Disclosure Agreement | Name, Company, Date, Term, Jurisdiction | Confidential_Info_Description, Governing_Law | Yes |
| `Offer_Letter` | Offer Letter | Name, Company, Position, Start_Date, Salary | Manager_Name, Response_Date, HR_Manager, Benefits_Description | Yes |
| `Contract` | Service Contract | Client_Name, Company, Contract_Creation_Date, Service_Description, Payment_Amount, Start_Date, End_Date | Payment_Schedule, Termination_Clause | Yes |
| `MOU` | Memorandum of Understanding | PartyA_Name, PartyB_Name, Date, Purpose, Term, Jurisdiction | Confidentiality, Termination_Clause, Governing_Law | Yes |
| `IP_Agreement` | IP Assignment Agreement | Name, Company, Date, Term, Jurisdiction | IP_Description, Governing_Law | Yes |

All templates are drafted to Indian jurisdiction. Dispute resolution clauses default to arbitration with seat at the `Jurisdiction` field value.


---

## 11. Branding System — Page Layout

Every document page is structured as three layers rendered by XeLaTeX:

```
595.5 pt (A4 width)
┌─────────────────────────────────────────────────────────────┐
│  header_decoration.png or custom header.png                 │ ← TikZ node, north-west
│  Turn2Law logo / custom logo.png (top-left)                 │ ← TikZ node, north-west + offset
├─────────────────────────────────────────────────────────────┤  top margin = max(74, header_pt + 16)
│                                                             │
│                   DOCUMENT BODY                             │  left=42pt, right=32pt
│                                                             │
│  [watermark.png centred at 297.75pt, 421.13pt, opacity 10%]│ ← TikZ node, south-west + offset
│                                                             │
├─────────────────────────────────────────────────────────────┤  bottom margin = max(66, footer_pt + 16)
│  footer_decoration.png or custom footer.png                 │ ← TikZ node, south-west
└─────────────────────────────────────────────────────────────┘
842.25 pt (A4 height)
```

`\AddToShipoutPictureBG` makes the asset layer repeat on **every page** automatically.

### Critical rule

`footer_decoration.png` (Turn2Law) already contains the email icon, E-MAIL label, and `turntwolaw@gmail.com` baked in at 288dpi. **Do not** draw these elements separately in TikZ — it causes double-rendering overlap on the footer.

---

## 12. AI Classification

```
File (PDF / DOCX / image)
        │
        ▼
utils/file_utils.extract_text(path)
  PDF   → PyMuPDF (fitz) — extracts all text spans
  DOCX  → python-docx — joins paragraph runs
  Image → pytesseract.image_to_string (Tesseract OCR)
        │
        ▼
Plain text string (first ~4000 chars used)
        │
        ▼
classifier/classify.classify_document(text)
  │
  ├── Builds prompt: "Classify this legal document into one of: [ALLOWED_TYPES]"
  │   ALLOWED_TYPES = (Onboarding_Letter, NDA, Offer_Letter, Contract, MOU, IP_Agreement)
  │
  ├── Calls Gemini 2.5 Flash (google-genai SDK)
  │   With exponential backoff retry (utils/retry.py)
  │
  └── Parses response → returns exact type string or raises ValueError
        │
        ▼
doc_type string  e.g. "NDA"
```

Classification is **optional** — `generate_direct(doc_type, fields)` skips it entirely when the type is already known.

---

## 13. Tech Stack Reference

| Layer | Technology | Version / Notes |
|-------|-----------|----------------|
| Language | Python | 3.11+ |
| Web framework | FastAPI | 0.139+ |
| ASGI server | Uvicorn | 0.51+ |
| AI classification | Google Gemini 2.5 Flash | `google-genai` SDK |
| PDF rendering | XeLaTeX | MiKTeX (Windows) / TeX Live |
| PDF signing | pyHanko | 0.25+ (CMS/PAdES) |
| Certificates | cryptography | PKCS#12 loading |
| Image processing | Pillow | Alpha trim, resize, PNG save |
| PDF extraction | PyMuPDF | `fitz` module |
| DOCX extraction | python-docx | Paragraph text join |
| Image OCR | pytesseract | Wrapper around Tesseract binary |
| HTTP multipart | python-multipart | FastAPI file upload dependency |
| Config | python-dotenv | `.env` file loading |
| Frontend | Vanilla HTML/CSS/JS | No framework, no build step |
| Fonts (PDF) | Montserrat + Garet | TTF via fontspec XeLaTeX package |
| LaTeX packages | geometry, tikz, eso-pic, textpos, fontspec, graphicx, xcolor, tabularx, ifthen, needspace, enumitem | |

---

## 14. Key Design Decisions

**Why XeLaTeX, not ReportLab?**
XeLaTeX provides pixel-perfect typesetting, native TTF font embedding, and absolute coordinate placement for brand assets. ReportLab exists as a fallback (`pdf_writer.py`) but can't reproduce the visual quality of the reference documents.

**Why incremental PDF updates for signing?**
Incremental updates leave the original byte sequence untouched. The SHA-256 hash covers exactly the original content, so the cryptographic proof is sound. A full rewrite would change byte offsets and invalidate any pre-existing annotations or form fields.

**Why cache brand_preamble.tex?**
Generating a custom preamble involves image processing, LaTeX generation, and an optional xelatex draftmode check — roughly 1–3 seconds. Caching by profile_id means repeat calls to `resolve_preamble` for the same company are near-instant.

**Why run signing in a thread executor?**
pyHanko calls `asyncio.run()` internally. FastAPI's `async def` endpoints already run inside an event loop, making a second `asyncio.run()` illegal. `run_in_executor` offloads to a thread with no running loop.

**Why strip the template preamble for custom branding?**
The `.tex` templates embed Turn2Law asset filenames (e.g. `header_decoration`) directly — there is no `\input{brand_preamble}` token to replace at the template level. When custom branding is active, `latex_writer.py` replaces the entire preamble block and substitutes the T2L filenames in the document body with the profile's processed PNG absolute paths.

---

*Effivia Turn2Law Legal Pvt. Ltd. · CIN: U63110DL2025PTC443434*
