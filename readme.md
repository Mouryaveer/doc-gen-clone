# Turn2Law Document Generation Engine

A full-stack legal document generation platform. Takes structured inputs, renders
professionally drafted Indian-jurisdiction PDFs via XeLaTeX, supports multi-tenant
branding in three modes, and applies cryptographic PKCS#12 digital signatures —
all accessible through a browser-based 9-step wizard served directly by the API server.

---

## What it does

1. **Select** a document type (NDA, Offer Letter, Service Contract, MOU, IP Agreement, Onboarding Letter)
2. **Fill** fields via a dynamic form, or upload a PDF / DOCX / image and let Gemini classify and pre-fill
3. **Choose branding** — Turn2Law standard, a single complete letterhead PNG, or granular header/footer/logo/watermark assets
4. **Generate** a production-quality PDF rendered by XeLaTeX (two-pass, fonts embedded, brand assets on every page)
5. **Preview** the PDF in the browser (served from the same origin — no CORS issues)
6. **Sign** with a PKCS#12 digital certificate (.pfx / .p12) — visible stamp, CMS/PAdES incremental update
7. **Download** the unsigned or signed PDF

---

## Quick start

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | Tested on 3.11, 3.12, 3.14 |
| MiKTeX (Windows) or TeX Live (Linux/macOS) | Must include XeLaTeX |
| Tesseract OCR binary | Required only for image → text extraction |
| Google Gemini API key | Free tier sufficient; only used for document classification |

### 1. Install Python dependencies

```powershell
# From the project root (activate your venv first)
.venv\Scripts\Activate.ps1

pip install fastapi "uvicorn[standard]" python-multipart pillow pyhanko==0.25.1 `
    google-genai pymupdf python-docx pytesseract python-dotenv `
    cryptography==43.0.3 pyhanko-certvalidator==0.26.4
```

Or install from the requirements file:

```powershell
pip install -r docgen/requirements.txt
```

### 2. Configure environment

Create `docgen/.env`:

```
GEMINI_API_KEY=your_key_here
```

Get a free key at [aistudio.google.com](https://aistudio.google.com).  
Without this key, document classification (Step 2 file upload) will fail.
Direct generation (Step 2 → Fill Form) works without it.

### 3. Start the server

```powershell
cd docgen
..\.venv\Scripts\python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open the app

**Always use the server URL — do not open the HTML file directly from disk.**

```
http://localhost:8000
```

This auto-redirects to `http://localhost:8000/app/docengine-app.html`.

The frontend is served as static files by FastAPI, so all API calls are same-origin
and there are no CORS restrictions.

Interactive API docs: `http://localhost:8000/docs`

---

## Project structure

```
documentGeneration-master/
│
├── docgen/                          ← Entire Python backend
│   ├── api.py                       ← FastAPI server — all HTTP endpoints + frontend mount
│   ├── app.py                       ← Core workflow: generate, sign, brand, validate
│   ├── schema.py                    ← Required/optional field definitions per doc type
│   ├── config.py                    ← GEMINI_API_KEY + MODEL_NAME from docgen/.env
│   │
│   ├── classifier/
│   │   └── classify.py              ← Gemini 2.5 Flash: text → doc type label
│   │
│   ├── extractors/
│   │   ├── pdf_extractor.py         ← PyMuPDF text extraction
│   │   ├── docx_extractor.py        ← python-docx paragraph extraction
│   │   └── image_extractor.py       ← pytesseract OCR
│   │
│   ├── branding/                    ← Multi-tenant branding engine
│   │   ├── __init__.py              ← Public API (resolve_preamble, profile CRUD)
│   │   ├── branding_engine.py       ← Orchestrator: turn2law / custom / letterhead branches
│   │   ├── complete_letterhead.py   ← Full-page A4 PNG background mode
│   │   ├── validators.py            ← PNG magic bytes, dimensions, file size
│   │   ├── image_processor.py       ← Alpha-channel transparent border trim (Pillow)
│   │   ├── layout_builder.py        ← px→pt margins + XeLaTeX preamble generation
│   │   ├── asset_manager.py         ← Profile JSON persistence on disk
│   │   ├── models.py                ← BrandProfile, BrandMode (TURN2LAW/CUSTOM/LETTERHEAD)
│   │   ├── config.py                ← BrandingConfig singleton (env-var backed)
│   │   ├── exceptions.py            ← BrandingEngineError hierarchy
│   │   └── profiles/                ← Runtime brand profile store (gitignored)
│   │
│   ├── digital_signature/           ← PKCS#12 / CMS / PAdES signing
│   │   ├── __init__.py              ← Public API exports
│   │   ├── signer.py                ← sign_pdf_file() / sign_document() facade
│   │   ├── pdf_signer.py            ← pyHanko: SimpleSigner, PdfSigner, incremental update
│   │   ├── certificate_loader.py    ← .pfx/.p12 → CertificateBundle (key + cert + chain)
│   │   ├── certificate_validator.py ← Expiry, KeyUsage, algorithm, chain checks
│   │   ├── metadata.py              ← SignatureMetadata dataclass
│   │   ├── signature_config.py      ← DIGEST_ALGORITHM, field name, VisibleSignatureConfig
│   │   ├── timestamp.py             ← RFC 3161 TSA client (disabled by default)
│   │   ├── verification.py          ← Post-sign signature verification helpers
│   │   ├── exceptions.py            ← DigitalSignatureError hierarchy (14 classes)
│   │   └── utils.py                 ← File helpers, PDF magic check, sanitisation
│   │
│   ├── utils/
│   │   ├── latex_writer.py          ← Template render + path injection + 2-pass XeLaTeX
│   │   ├── file_utils.py            ← extract_text() dispatcher (pdf/docx/image)
│   │   ├── pdf_writer.py            ← ReportLab plain-text fallback
│   │   └── retry.py                 ← Exponential backoff for Gemini API calls
│   │
│   ├── templates/                   ← XeLaTeX document body templates (6 files)
│   ├── layouts/                     ← brand_preamble.tex — shared fonts/geometry/assets
│   ├── images/                      ← Turn2Law brand PNGs (header, footer, watermark, logo)
│   ├── fonts/                       ← Montserrat + Garet TTF files
│   ├── generated_docs/              ← API output directory (gitignored)
│   ├── make_test_cert.py            ← Generate a self-signed test .pfx certificate
│   └── .env                         ← GEMINI_API_KEY (gitignored)
│
├── turn2law-site-main/              ← Frontend (vanilla HTML/CSS/JS, no build step)
│   ├── docengine-app.html           ← 9-step document wizard SPA (served via /app/)
│   ├── docengine.html               ← Product marketing page
│   ├── index.html                   ← Main Turn2Law website
│   ├── introspector.html            ← Introspector product page
│   ├── legal-services.html          ← Legal services page
│   ├── resources.html               ← Resources hub
│   ├── login.html / signup.html     ← Auth pages (stubbed)
│   └── turn2law-logo.png
│
├── ARCHITECTURE.md                  ← Detailed technical reference
├── SYSTEM_WORKFLOW.md               ← End-to-end pipeline diagram
└── .gitignore
```

---

## API endpoints

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/api/templates` | — | All doc types with field lists and icons |
| `GET` | `/api/schema/{doc_type}` | — | Rich field metadata (label, placeholder, type) |
| `POST` | `/api/generate` | JSON | `{success, doc_id, pdf_url, doc_type}` |
| `POST` | `/api/generate-with-branding` | multipart | `{success, doc_id, pdf_url, doc_type}` |
| `POST` | `/api/generate-with-letterhead` | multipart | `{success, doc_id, pdf_url, letterhead_info}` |
| `POST` | `/api/classify` | multipart (file) | `{doc_type, confidence}` |
| `POST` | `/api/sign` | multipart | `{success, doc_id, signed_pdf_url}` |
| `GET` | `/api/preview/{doc_id}` | — | `{exists, pdf_url, signed_url}` |
| `POST` | `/api/validate-cert` | multipart | `{valid, subject, issuer, expires}` |
| `GET` | `/files/{filename}` | — | PDF bytes |
| `GET` | `/app/*` | — | Frontend static files |
| `GET` | `/` | — | Redirect → `/app/docengine-app.html` |

All error responses follow: `{"success": false, "error": "human-readable message"}`  
HTTP status: `400` validation, `404` not found, `500` server error.

### Generate example (Turn2Law branding)

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "doc_type": "NDA",
    "fields": {
      "Name": "Arjun Mehta",
      "Company": "Nexus Innovations Pvt. Ltd., Bengaluru",
      "Date": "10 July 2026",
      "Term": "two (2) years",
      "Jurisdiction": "Chennai, Tamil Nadu"
    }
  }'
```

Response: `{"success": true, "doc_id": "abc123def456", "pdf_url": "/files/abc123def456.pdf", "doc_type": "NDA"}`

---

## Document types and fields

| Document | Required fields | Optional fields |
|----------|----------------|-----------------|
| Onboarding Letter | Employee_Name, Emp_ID, Role, Joining_Date, Document_Date | — |
| NDA | Name, Company, Date, Term, Jurisdiction | Confidential_Info_Description, Governing_Law |
| Offer Letter | Name, Company, Position, Start_Date, Salary | Manager_Name, Response_Date, HR_Manager, Benefits_Description |
| Service Contract | Client_Name, Company, Contract_Creation_Date, Service_Description, Payment_Amount, Start_Date, End_Date | Payment_Schedule, Termination_Clause |
| MOU | PartyA_Name, PartyB_Name, Date, Purpose, Term, Jurisdiction | Confidentiality, Termination_Clause, Governing_Law |
| IP Agreement | Name, Company, Date, Term, Jurisdiction | IP_Description, Governing_Law |

All templates use Indian jurisdiction. Arbitration seat defaults to the `Jurisdiction` field.  
All CP_* company-profile fields (name, signatory, designation, address, email, etc.) are optional and injected automatically from the branding step.

---

## Branding modes

### Mode 1 — Turn2Law default

No uploads needed. Turn2Law letterhead, gold/charcoal colour scheme, Montserrat + Garet fonts.

### Mode 2 — Complete Letterhead (recommended for white-label)

Upload one A4 PNG containing your full page design. The engine:
- Validates PNG format (magic bytes check)
- Auto-upscales if below 1000×1400 px
- Auto-detects safe writing margins from alpha/luminance analysis
- Places the image as a full-page background on every page

```python
# Via API
POST /api/generate-with-letterhead
  letterhead_image: File (PNG, max 20 MB)
  doc_type: str
  fields_json: str (JSON)
  company_profile_json: str (JSON, optional)
  signature_image: File (PNG, optional)
```

### Mode 3 — Advanced Custom

Provide individual header, footer, watermark, and logo PNGs.  
Constraints: header ≥595px wide, ≤150px tall; footer ≤120px tall; max 5 MB each.

```python
from app import make_custom_profile, generate_with_branding

brand = make_custom_profile(
    profile_id           = "acme_corp",
    name                 = "ACME Legal Solutions",
    header_image_path    = "/path/to/header.png",
    footer_image_path    = "/path/to/footer.png",   # optional
    watermark_image_path = "/path/to/wm.png",       # optional
    logo_image_path      = "/path/to/logo.png",     # optional
)
pdf = generate_with_branding("NDA", fields, brand)
```

Profiles are cached in `docgen/branding/profiles/`. Regenerate by deleting the profile directory.

---

## Digital signature

Signing uses **CMS/PAdES incremental PDF updates** via pyHanko. The original bytes are
untouched — the signature appends to the file, keeping the original hash valid.

```python
from app import sign_generated_pdf

signed = sign_generated_pdf(
    pdf_path    = "output.pdf",
    cert_path   = "my_cert.pfx",
    password    = "password",
    signer_name = "Mourya Veer",
    reason      = "Digitally approved",
    location    = "Chennai, India",
    visible     = True,   # embeds visible stamp on last page
)
```

**Visible stamp appearance:**
```
┌─────────────────────────────────────────────┐
│  Digitally signed by MOURYA VEER            │
│  Date: 2026.08.06 14:30:00 +00'00'          │
│  Reason: Digitally approved                 │
│  Location: Chennai, India                   │
└─────────────────────────────────────────────┘
```

**Generate a test certificate (self-signed, for development only):**

```powershell
.venv\Scripts\python docgen\make_test_cert.py
# Creates: docgen/my_cert.pfx   Password: 123456
```

For production use a **Class 3 DSC** from eMudhra, nCode, or Sify (MCA-approved CAs).

### asyncio note

pyHanko calls `asyncio.run()` internally. Both `/api/sign` and `/api/validate-cert`
run the signing function in a thread-pool executor (`loop.run_in_executor`) so the
blocking call gets its own thread with no active event loop — avoiding the
`RuntimeError: asyncio.run() cannot be called from a running event loop` error.

---

## Run without the API (direct Python)

```powershell
cd docgen
..\.venv\Scripts\python app.py
```

Edit `DOC_TYPE`, `COMPANY_PROFILE`, and `CERT_PATH` at the bottom of `app.py`.  
Outputs `docgen/output.pdf` (and `docgen/output_signed.pdf` if a cert is configured).

---

## Adding a new document type

| Step | File | Action |
|------|------|--------|
| 1 | `docgen/schema.py` | Add entry with `required` and `optional` field lists |
| 2 | `docgen/templates/my_doc_template.tex` | Write XeLaTeX body; start with `\input{LAYOUTS_DIR_PLACEHOLDERbrand_preamble}` |
| 3 | `docgen/app.py` | Add to `TEMPLATE_MAP` |
| 4 | `docgen/classifier/classify.py` | Add to `ALLOWED_TYPES` tuple |
| 5 | `docgen/api.py` | Add to `_TEMPLATE_META` and `FIELD_META` |

The API picks up the new type automatically — no endpoint changes needed.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GEMINI_API_KEY` | — | Google Gemini AI key (required for classification) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model override |
| `BRAND_PROFILES_DIR` | `docgen/branding/profiles/` | Profile storage location |
| `BRAND_MAX_ASSET_BYTES` | `5242880` (5 MB) | Max PNG asset upload size |
| `BRAND_MIN_HEADER_WIDTH_PX` | `595` | Minimum header/footer image width |
| `BRAND_ASSET_DPI` | `96` | DPI for px → pt margin conversion |
| `RFC3161_TSA_URL` | `http://timestamp.digicert.com` | Timestamp authority (disabled by default) |

---

## Tech stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Web framework | FastAPI + Uvicorn | 0.139+ |
| Frontend | Vanilla HTML/CSS/JS | No build step |
| AI classification | Google Gemini 2.5 Flash | `google-genai` SDK |
| PDF compilation | XeLaTeX | MiKTeX / TeX Live |
| PDF signing | pyHanko | 0.25.1 |
| Certificate handling | cryptography | 43.0.3 |
| Certificate validation | pyhanko-certvalidator | 0.26.4 |
| Image processing | Pillow | Any modern |
| PDF extraction | PyMuPDF | Any modern |
| DOCX extraction | python-docx | Any modern |
| OCR | pytesseract + Tesseract | Tesseract 5+ |
| Config | python-dotenv | Any modern |
| Fonts (PDF) | Montserrat + Garet | TTF via XeLaTeX fontspec |

---

## Windows socket exhaustion (WinError 10055)

If you see `OSError: [WinError 10055]` after restarting the server multiple times,
Windows has exhausted its socket buffer from `TIME_WAIT` connections. Fix:

```powershell
# Run as Administrator
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" `
    -Name "TcpTimedWaitDelay" -Value 30 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" `
    -Name "MaxUserPort" -Value 65534 -Type DWord -Force
```

Then wait 30 seconds before restarting. Avoid using `--reload` during rapid iteration;
restart manually instead.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Failed to fetch" / "Could not load templates" | Opening HTML as `file://` | Open `http://localhost:8000` instead |
| `xelatex: command not found` | MiKTeX/TeX Live not installed or not on PATH | Install MiKTeX and add to PATH |
| `GEMINI_API_KEY is not set` | Missing `.env` file | Create `docgen/.env` with your key |
| `Certificate expired` | Test cert is past its validity | Run `make_test_cert.py` to generate a fresh one |
| `[WinError 10055]` | Windows socket exhaustion | See "Windows socket exhaustion" section above |
| PDF blank / wrong layout | Brand preamble cache stale | Delete `docgen/branding/profiles/<id>/brand_preamble.tex` |
| `RuntimeError: asyncio.run()` | Signing called outside thread executor | Only use `/api/sign`; never call `sign_generated_pdf` from an async endpoint directly |

---

## Legal notice

Turn2Law is a technology platform, not a law firm. Documents generated by this system
are not legal advice. For high-stakes or court-facing documents, review with qualified
counsel before use.

---

*Effivia Turn2Law Legal Pvt. Ltd. · CIN: U63110DL2025PTC443434*
