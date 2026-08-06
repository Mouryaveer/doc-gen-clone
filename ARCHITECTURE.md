# Turn2Law Document Generation Engine — Architecture Reference

*Last updated: August 2026 — post-production-audit release*

---

## 1. System Overview

The Turn2Law Document Generation Engine is a full-stack legal document platform
with three distinct layers:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Vanilla HTML/CSS/JS | 9-step wizard SPA served by FastAPI at `/app/` |
| **API Server** | FastAPI + Uvicorn | HTTP bridge; mounts frontend + generated_docs |
| **Backend Engine** | Python 3.11+ | PDF generation, branding, signing, classification |

The frontend is served by the same FastAPI process that handles all API calls —
eliminating CORS issues entirely. Open `http://localhost:8000` to access the app.

---

## 2. High-Level Request Flow

```
Browser (http://localhost:8000/app/docengine-app.html)
        │
        │  Same-origin HTTP/JSON or multipart/form-data
        ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI Server  (docgen/api.py)   :8000                │
│                                                         │
│  GET  /                    → redirect to /app/          │
│  GET  /app/*               → frontend static files      │
│  GET  /files/*             → generated PDFs             │
│  GET  /api/templates                                    │
│  GET  /api/schema/{doc_type}                            │
│  POST /api/generate                                     │
│  POST /api/generate-with-branding                       │
│  POST /api/generate-with-letterhead                     │
│  POST /api/classify                                     │
│  POST /api/sign                                         │
│  POST /api/validate-cert                                │
│  GET  /api/preview/{doc_id}                             │
└──────────────┬──────────────────────────────────────────┘
               │
       ┌───────┴──────────────────────────────────────┐
       │                                              │
       ▼                                              ▼
┌─────────────────────┐           ┌───────────────────────────┐
│  Document Pipeline  │           │  Branding Engine          │
│  (docgen/app.py)    │           │  (docgen/branding/)       │
│                     │           │                           │
│  validate_inputs()  │           │  resolve_preamble()       │
│  classify_document()│           │  validate_asset()         │
│  render_latex()     │           │  process_image()          │
│  sign_generated_pdf()│          │  compute_layout()         │
│  make_custom_profile()          │  generate_preamble()      │
└─────────────────────┘           │  validate_letterhead()    │
                                  └───────────────────────────┘
```

---

## 3. Component Map

```
documentGeneration-master/
│
├── docgen/                          ← Entire backend lives here
│   ├── api.py                       ← FastAPI app (9 API endpoints + /app + /files mounts)
│   ├── app.py                       ← Core Python library (no HTTP; importable)
│   ├── schema.py                    ← Field definitions for all 6 document types
│   ├── config.py                    ← GEMINI_API_KEY + MODEL_NAME from docgen/.env
│   │
│   ├── classifier/
│   │   └── classify.py              ← Gemini 2.5 Flash → doc type label (with retry)
│   │
│   ├── extractors/
│   │   ├── pdf_extractor.py         ← PyMuPDF text extraction
│   │   ├── docx_extractor.py        ← python-docx paragraph extraction
│   │   └── image_extractor.py       ← pytesseract OCR
│   │
│   ├── branding/
│   │   ├── __init__.py              ← Public API: BrandProfile, resolve_preamble, CRUD
│   │   ├── branding_engine.py       ← Orchestrator: TURN2LAW / CUSTOM / LETTERHEAD branches
│   │   ├── complete_letterhead.py   ← Full-page A4 PNG background mode (LetterheadInfo)
│   │   ├── validators.py            ← PNG magic bytes, min dimensions, file size
│   │   ├── image_processor.py       ← Alpha-channel trim via Pillow getbbox()
│   │   ├── layout_builder.py        ← px→pt margins, generate_preamble() XeLaTeX
│   │   ├── asset_manager.py         ← save / load / list / delete BrandProfile JSON
│   │   ├── models.py                ← BrandProfile, BrandMode(TURN2LAW/CUSTOM/LETTERHEAD)
│   │   ├── config.py                ← BrandingConfig frozen dataclass + CONFIG singleton
│   │   ├── exceptions.py            ← BrandingEngineError hierarchy (5 classes)
│   │   └── profiles/                ← Runtime profile store (gitignored)
│   │
│   ├── digital_signature/
│   │   ├── __init__.py              ← Public API exports
│   │   ├── signer.py                ← sign_pdf_file() / sign_document() facade
│   │   ├── pdf_signer.py            ← pyHanko: SimpleSigner, PdfSigner, CMS blob
│   │   ├── certificate_loader.py    ← .pfx/.p12 → CertificateBundle (key+cert+chain)
│   │   ├── certificate_validator.py ← Expiry, KeyUsage, EKU, algorithm checks
│   │   ├── metadata.py              ← SignatureMetadata dataclass
│   │   ├── signature_config.py      ← All tunable constants (field name, digest alg)
│   │   ├── timestamp.py             ← RFC 3161 TSA client (disabled by default)
│   │   ├── verification.py          ← Post-sign signature verification
│   │   ├── exceptions.py            ← DigitalSignatureError hierarchy (14 classes)
│   │   └── utils.py                 ← assert_valid_pdf, hash_file, sanitise_text
│   │
│   ├── utils/
│   │   ├── latex_writer.py          ← render_latex(): path injection, escaping, 2-pass XeLaTeX
│   │   ├── file_utils.py            ← extract_text() dispatcher (pdf/docx/image)
│   │   ├── pdf_writer.py            ← ReportLab plain-text fallback
│   │   └── retry.py                 ← Exponential backoff for Gemini API calls
│   │
│   ├── templates/                   ← XeLaTeX document bodies (6 .tex files)
│   ├── layouts/                     ← brand_preamble.tex shared preamble
│   ├── images/                      ← Turn2Law brand PNGs
│   ├── fonts/                       ← Montserrat + Garet TTF
│   ├── generated_docs/              ← API output directory (gitignored)
│   └── make_test_cert.py            ← Generate a self-signed test .pfx
│
└── turn2law-site-main/              ← Frontend (served by FastAPI at /app/)
    ├── docengine-app.html           ← 9-step document wizard SPA
    ├── docengine.html               ← Product page
    └── ...                          ← Other site pages
```

---

## 4. Document Generation Pipeline

```
User input (doc_type + field dict)
        │
        ▼
1. validate_inputs(doc_type, fields)
   └── Reads DOCUMENT_SCHEMAS; raises ValueError if required field empty
        │
        ▼
2. TEMPLATE_MAP lookup → absolute .tex file path
        │
        ▼
3. resolve_preamble(brand_profile)          [branded generation only]
   ├── TURN2LAW  → returns docgen/layouts/brand_preamble.tex (SHA-256 integrity check)
   ├── CUSTOM    → validate assets → process images → compute layout
   │               → generate brand_preamble.tex → xelatex draftmode check → cache
   └── LETTERHEAD → validate PNG → auto-detect margins → generate preamble → cache
        │
        ▼
4. render_latex(template_path, output_tex, output_pdf, fields, preamble_path)
   │
   ├── a. Read template .tex
   ├── b. Inject absolute paths (IMAGES / FONTS / LAYOUTS DIR placeholders)
   ├── c. Render brand_preamble_rendered.tex into work dir (T2L mode)
   ├── d. Custom preamble swap (if preamble_path provided):
   │      - Strip template preamble before \begin{document}
   │      - Replace with custom brand preamble (fonts/images injected)
   │      - Substitute T2L asset names in body with profile PNGs or \mbox{}
   ├── e. LaTeX-escape all field values (char-by-char, no double-escaping)
   │      CP_* keys: only & → \& (preserves other chars)
   │      CP_Signature_Image: no escaping (filename)
   ├── f. Replace {{FIELD}} tokens; clear remaining optional tokens
   ├── g. Write rendered .tex to work_dir (template directory)
   ├── h. XeLaTeX Pass 1 (layout + TikZ coordinate recording)
   └── i. XeLaTeX Pass 2 (TikZ overlays + eso-pic background finalised)
           PDF copied to output_pdf destination
        │
        ▼
5. PDF written to docgen/generated_docs/{doc_id}.pdf
```

---

## 5. Branding Engine

### 5a. Turn2Law mode (default)

```
resolve_preamble(BrandProfile(mode=TURN2LAW))
  │
  ├── First call:  SHA-256 hash of brand_preamble.tex → store in _t2l_preamble_hash
  ├── Later calls: re-hash + compare → raise BrandProfileError if modified
  └── Return absolute path to docgen/layouts/brand_preamble.tex
```

### 5b. Custom mode

```
resolve_preamble(BrandProfile(mode=CUSTOM, header_image_path=...))
  │
  ├── Validate header_image_path set + file exists
  ├── Cache check: profiles/{id}/brand_preamble.tex exists? → return immediately
  └── Full pipeline (atomic cleanup on any failure):
        1. validate_asset()  — PNG magic, dimensions, file size
        2. process_image()   — alpha-channel trim → save to profiles/{id}/
        3. compute_layout()  — px * 72 / dpi → max(74, h+16) top, max(66, h+16) bottom
        4. generate_preamble() — .tex with TikZ nodes + T2L asset name safety check
        5. xelatex -draftmode — syntax pre-check (skip on MiKTeX nag / not on PATH)
        6. save_profile()    — write profile.json to profiles/{id}/
        7. Return preamble path
```

### 5c. Letterhead mode (complete A4 PNG)

```
resolve_preamble(BrandProfile(mode=LETTERHEAD, letterhead_image_path=...))
  │
  ├── Validate PNG format + file size (max 20 MB)
  ├── Auto-upscale if below 1000×1400 px
  ├── Auto-detect safe margins from alpha/luminance row scan (pure Pillow, no numpy)
  │     Falls back to conservative defaults if detection inconclusive
  ├── generate_letterhead_preamble() → full-page TikZ node (595.5 × 842.25 pt)
  ├── T2L asset name safety check
  └── Return preamble path
```

### 5d. Profile directory layout

```
docgen/branding/profiles/
└── {profile_id}/
    ├── profile.json          ← serialised BrandProfile (ISO 8601 timestamps)
    ├── header.png            ← processed asset (alpha-trimmed)
    ├── footer.png            ← optional
    ├── watermark.png         ← optional
    ├── logo.png              ← optional
    ├── letterhead.png        ← complete letterhead mode only
    └── brand_preamble.tex    ← generated preamble (cached)
```

---

## 6. Digital Signature Pipeline

```
User: .pfx path + password + signer metadata
        │
        ▼
certificate_loader.load_certificate(cert_path, password)
  • Opens PKCS#12 with cryptography.hazmat.primitives.serialization.pkcs12
  • Extracts: private_key, certificate (x509), chain certs
  • Returns CertificateBundle — call .dispose() after use
        │
        ▼
certificate_validator.validate_certificate(bundle)
  • _check_expiry()     — not_valid_before ≤ now ≤ not_valid_after
  • _check_key_usage()  — KeyUsage.digitalSignature == True (absent = permissive)
  • _check_algorithm()  — MD5/MD2 rejected; SHA-1 warned; SHA-256+ accepted
  • _check_chain()      — warns if no intermediates (full path-building: future)
        │
        ▼
pdf_signer.sign_pdf(input_pdf, output_pdf, bundle, metadata, cert_path, password)
  │
  ├── SimpleSigner.load_pkcs12(pfx_file, passphrase)
  ├── PdfSignatureMetadata(field_name, md_algorithm="sha256", name, reason, ...)
  ├── IncrementalPdfFileWriter(BytesIO(pdf_bytes))  — original bytes untouched
  ├── SigFieldSpec + TextStampStyle (visible=True):
  │     "Digitally signed by %(signer)s"
  │     "Date: %(ts)s"
  │     "Reason: ..." / "Location: ..."
  │     background_opacity=0.0  — no tint/watermark in the stamp box
  └── PdfSigner.sign_pdf() → write CMS blob to output
        │
        ▼
output_signed.pdf  — Adobe Acrobat / pyHanko verify OK
```

### asyncio conflict fix

pyHanko calls `asyncio.run()` internally. FastAPI `async def` endpoints already
have a running event loop. Both `/api/sign` and `/api/validate-cert` offload the
blocking call to a thread-pool executor:

```python
loop = asyncio.get_running_loop()
await loop.run_in_executor(None, functools.partial(sign_generated_pdf, ...))
```

Each thread spawned by the executor starts with no active event loop, so
pyHanko's `asyncio.run()` works correctly.

---

## 7. API Server (api.py)

### Key design decisions

- **Frontend served by FastAPI**: `app.mount("/app", StaticFiles(...))` eliminates
  all CORS issues when the browser opens `http://localhost:8000`.
- **Root redirect**: `GET /` → `307 /app/docengine-app.html` for convenience.
- **CORS**: `allow_origins=["*"]` with `allow_credentials=False` — the wildcard
  requires credentials to be False per browser spec.
- **Output isolation**: Generated PDFs go to `docgen/generated_docs/` (never to
  the templates directory). The `.tex` intermediate is cleaned up after compile.
- **Thread executor**: Signing and cert-validation run in `run_in_executor` to
  avoid the pyHanko asyncio conflict.

### Company profile injection (`_merge_company_profile`)

Priority (highest → lowest):

1. Customer values from `company_profile_json` form field
2. Turn2Law defaults (only when `branding_mode == "turn2law"`)
3. Empty string fallback (so `\ifthenelse{\equal{...}{}}` guards in templates work)

Signature image: copied to `docgen/images/` so XeLaTeX's `\graphicspath` can
find it; only the filename stem is stored in `CP_Signature_Image`.

---

## 8. Frontend (docengine-app.html)

### State management

```javascript
const state = {
  currentStep:      1,           // 1–9
  selectedDocType:  null,        // "NDA"
  inputMethod:      'form',      // 'form' | 'pdf' | 'docx' | 'image'
  formData:         {},          // {field_key: value}
  schemaRequired:   [],          // [{key, label, placeholder, type}]
  schemaOptional:   [],
  brandingMode:     'turn2law',  // 'turn2law' | 'letterhead' | 'custom'
  brandAssets:      {},          // {header: File, footer: File, ...}
  brandProfileId:   null,
  brandProfileName: null,
  letterheadFile:   null,        // File — complete letterhead PNG
  companyProfile:   {},          // {CP_Company_Name, CP_Signatory_Name, ...}
  signatureFile:    null,        // File — customer signature PNG
  docId:            null,        // 12-char hex from /api/generate
  pdfUrl:           null,        // "/files/{docId}.pdf"
  signedPdfUrl:     null,
  signerName:       null,
  certFile:         null,        // File
  certValidated:    false,
  generatedAt:      null,
};
```

### API base URL detection

```javascript
const API = (() => {
  if (window.location.protocol === 'file:') return 'http://localhost:8000';
  return '';  // same-origin when served through FastAPI
})();
```

### Step flow

| Step | Panel | API call | Auto-triggered |
|------|-------|----------|----------------|
| 1 | Select document type | `GET /api/templates` | Page load |
| 2 | Input method | `POST /api/classify` (file upload) | On file select |
| 3 | Fill form | `GET /api/schema/{doc_type}` | On step entry (once) |
| 4 | Branding | — | — |
| 5 | Review | — | On step entry |
| 6 | Generate | `POST /api/generate*` | On step entry (auto) |
| 7 | Preview | `GET /files/{docId}.pdf` | iframe src set |
| 8 | Sign | `POST /api/validate-cert` → `POST /api/sign` | On button click |
| 9 | Download | `GET /files/{docId}.pdf` | On button click |

### Security fixes applied

- Toast messages escaped via `_escHtml()` before innerHTML injection (XSS prevention)
- `callGenerateAPI()` validates required files before network call (null guard)
- `resetApp()` fully clears all form fields, file inputs, signature previews, and state
- `goToStep(6)` resets the generation timeline UI on every entry (re-generate shows clean state)
- Mobile progress strip uses `aria-disabled` instead of `disabled` on future steps

---

## 9. Template System

### LaTeX placeholder lifecycle

```
{{Employee_Name}} in .tex
        ↓
_escape_latex("Mourya Veer")       → "Mourya Veer"       (no special chars)
_escape_latex("50% equity")        → "50\% equity"
_escape_latex("Founder & CEO")     → "Founder \& CEO"    (CP_* key — amp-only)
_escape_latex("price $100")        → "price \$100"
_escape_latex("a\\b")              → "a\textbackslash{}b"
        ↓
tex.replace("{{Employee_Name}}", "Mourya Veer")
        ↓
re.sub(r"\{\{[A-Za-z_]+\}\}", "", tex)  → clears any unfilled optional tokens
        ↓
XeLaTeX pass 1 + pass 2 → PDF
```

### Critical template rule

`\noindent{{FIELD}}` is invalid — after substitution it becomes `\noindentValue`
(single undefined command). Always use `\noindent {{FIELD}}` (space before) or
wrap in a group: `\noindent\textbf{{{FIELD}}}`.

### Adding a new document type

```
1. schema.py        → add "My_Type": { "required": [...], "optional": [...] }
2. templates/       → my_type_template.tex
                      \documentclass[10pt]{article}
                      \input{LAYOUTS_DIR_PLACEHOLDERbrand_preamble}
                      \begin{document}
                      ... {{Field}} placeholders ...
                      \end{document}
3. app.py           → TEMPLATE_MAP["My_Type"] = _t("my_type_template.tex")
4. classify.py      → add "My_Type" to ALLOWED_TYPES
5. api.py           → add to _TEMPLATE_META and FIELD_META
```

---

## 10. Supported Document Types

| Key | Name | Required | Optional | Multi-page |
|-----|------|----------|----------|-----------|
| `Onboarding_Letter` | Onboarding Letter | 5 | 9 (CP_*) | No |
| `NDA` | Non-Disclosure Agreement | 5 | 11 | Yes |
| `Offer_Letter` | Offer Letter | 5 | 13 | Yes |
| `Contract` | Service Contract | 7 | 11 | Yes |
| `MOU` | Memorandum of Understanding | 6 | 12 | Yes |
| `IP_Agreement` | IP Assignment Agreement | 5 | 11 | Yes |

All use Indian jurisdiction (Indian Contract Act, 1872).  
Arbitration defaults to seat at the `Jurisdiction` field value.

---

## 11. Branding System — Page Layout

```
595.5 pt (A4 width)
┌─────────────────────────────────────────────────────────────┐
│  header asset (full width, height = header_height_pt)       │ ← TikZ north-west
│  logo (optional, top-left, 200pt wide)                      │ ← TikZ north-west + offset
├─────────────────────────────────────────────────────────────┤ top = max(74, header_pt+16)
│                                                             │
│                  DOCUMENT BODY                              │ left=42pt  right=32pt
│                                                             │
│  [watermark: centred at 297.75pt, 421.13pt, opacity 10%]   │
│                                                             │
├─────────────────────────────────────────────────────────────┤ bottom = max(66, footer_pt+16)
│  footer asset (full width, height = footer_height_pt)       │ ← TikZ south-west
└─────────────────────────────────────────────────────────────┘
842.25 pt (A4 height)
```

`\AddToShipoutPictureBG` (without `*`) applies to **every page** automatically.

Letterhead mode places a single full-page image: `width=595.5pt, height=842.25pt,
keepaspectratio=false` — the user is responsible for the image composition.

---

## 12. AI Classification

```
File (PDF / DOCX / image)
        │
extract_text(path)           ← PyMuPDF / python-docx / pytesseract
        │
Plain text (first 3000 chars)
        │
classify_document(text)
  ├── Build prompt: "Classify into one of: [NDA, Offer_Letter, Contract, MOU, ...]"
  ├── call_gemini_with_retry() — exponential back-off on 503 / UNAVAILABLE
  └── _normalize(response.text) → exact ALLOWED_TYPES label or ValueError
        │
doc_type string  e.g. "NDA"
```

Classification is **optional** — `generate_direct(doc_type, fields)` skips it
entirely when the type is already known (the most common case).

---

## 13. Error Handling

### Backend

Every endpoint returns a consistent shape on failure:

```json
{ "success": false, "error": "human-readable message" }
```

HTTP status codes: `400` validation, `404` not found, `500` server error.

No stack traces are ever returned to the client. All exceptions are logged
server-side with full tracebacks via `logger.exception()`.

### Exception hierarchies

```
BrandingEngineError
  ├── BrandProfileError
  ├── BrandAssetValidationError
  ├── BrandAssetProcessingError
  └── BrandProfileNotFoundError

DigitalSignatureError
  ├── CertificateNotFoundError
  ├── InvalidCertificateError
  ├── CertificateExpiredError
  ├── IncorrectPasswordError
  ├── PrivateKeyMissingError
  ├── InvalidKeyUsageError
  ├── UnsupportedAlgorithmError
  ├── UnsupportedCertificateFormatError
  ├── CertificateChainError
  ├── SigningFailedError
  ├── TimestampUnavailableError
  ├── PDFIntegrityError
  ├── VerificationError
  └── SignatureNotFoundError
```

---

## 14. Security Properties

| Property | Implementation |
|----------|---------------|
| Private key never serialised | `CertificateBundle.dispose()` clears reference immediately after signing |
| Password cleared from request | `SigningRequest.password = ""` in `finally` block |
| No stack traces to client | All exceptions caught; only message string returned |
| LaTeX injection prevention | `_escape_latex()` escapes all 10 special LaTeX characters char-by-char |
| XSS prevention (frontend) | `_escHtml()` escapes all user/API content before `innerHTML` |
| T2L asset leakage prevention | Generated custom preambles scanned for forbidden T2L asset names |
| Directory traversal | `os.path.abspath()` normalises all file paths before use |
| File type validation | PNG magic bytes (`\x89PNG\r\n\x1a\n`) checked before Pillow opens |
| Certificate expiry | `validate_certificate()` checks `not_valid_after` against `datetime.now(UTC)` |
| Temp file cleanup | All `tempfile.mkdtemp` dirs removed in `finally` blocks |

---

## 15. Running the Server

```powershell
# From the docgen/ directory
cd C:\...\documentGeneration-master\docgen

# Start (no auto-reload — prevents socket exhaustion during development)
..\.venv\Scripts\python -m uvicorn api:app --host 0.0.0.0 --port 8000

# Or with auto-reload for active development
..\.venv\Scripts\python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

| URL | Purpose |
|-----|---------|
| `http://localhost:8000` | App (auto-redirects to wizard) |
| `http://localhost:8000/app/docengine-app.html` | Direct wizard URL |
| `http://localhost:8000/docs` | Interactive Swagger UI |
| `http://localhost:8000/openapi.json` | OpenAPI schema |

---

*Effivia Turn2Law Legal Pvt. Ltd. · CIN: U63110DL2025PTC443434*
