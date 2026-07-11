# Turn2Law Document Generation Engine

A full-stack legal document generation platform. It takes structured inputs, renders professionally drafted Indian-jurisdiction PDFs via XeLaTeX, supports multi-tenant branding, and applies cryptographic digital signatures — all accessible through a browser-based 9-step wizard.

---

## What it does

1. **Select** a document type (NDA, Offer Letter, Contract, MOU, IP Agreement, Onboarding Letter)
2. **Fill** fields via a dynamic form, or upload a PDF/DOCX/image and let Gemini classify and pre-fill
3. **Choose branding** — Turn2Law standard letterhead or upload your own company assets
4. **Generate** a production-quality PDF rendered by XeLaTeX (two-pass, fonts embedded)
5. **Preview** the PDF in the browser
6. **Sign** with a PKCS#12 digital signature certificate (.pfx / .p12)
7. **Download** the unsigned or signed PDF

---

## Project structure

```
documentGeneration-master/
│
├── docgen/                        ← Python backend package
│   ├── api.py                     ← FastAPI web server (all HTTP endpoints)
│   ├── app.py                     ← Core workflow controller (generation, signing, branding)
│   ├── schema.py                  ← Field definitions for all document types
│   ├── config.py                  ← Environment config (Gemini API key, model name)
│   │
│   ├── classifier/                ← Gemini 2.5 Flash document type classifier
│   ├── extractors/                ← Text extraction (PyMuPDF, python-docx, Tesseract)
│   ├── generators/                ← Gemini prompt builders (future expansion)
│   │
│   ├── branding/                  ← Multi-tenant branding engine
│   │   ├── __init__.py            ← Public API (resolve_preamble, save/load/list/delete_profile)
│   │   ├── branding_engine.py     ← Orchestrator: validate → process → layout → preamble
│   │   ├── validators.py          ← PNG asset validation (dimensions, file size, magic bytes)
│   │   ├── image_processor.py     ← Transparent border trimming via Pillow
│   │   ├── layout_builder.py      ← Margin computation + XeLaTeX preamble generation
│   │   ├── asset_manager.py       ← Profile persistence (JSON on disk)
│   │   ├── models.py              ← BrandProfile, BrandMode, LayoutParameters dataclasses
│   │   ├── config.py              ← BrandingConfig (env vars: BRAND_PROFILES_DIR etc.)
│   │   ├── exceptions.py          ← BrandingEngineError hierarchy
│   │   └── profiles/              ← Saved brand profiles (gitignored)
│   │
│   ├── digital_signature/         ← PKCS#12 PDF signing via pyHanko
│   │   ├── signer.py              ← Top-level sign_pdf_file() entry point
│   │   ├── pdf_signer.py          ← pyHanko integration (CMS signature, visible stamp)
│   │   ├── certificate_loader.py  ← .pfx/.p12 loading → CertificateBundle
│   │   ├── certificate_validator.py← Expiry + key usage checks
│   │   ├── metadata.py            ← SignatureMetadata dataclass
│   │   ├── signature_config.py    ← Field name, digest algorithm constants
│   │   ├── timestamp.py           ← Optional TSA client
│   │   └── verification.py        ← Post-signing verification helpers
│   │
│   ├── utils/
│   │   ├── latex_writer.py        ← Placeholder injection, path resolution, XeLaTeX runner
│   │   ├── file_utils.py          ← Multi-format extraction dispatcher
│   │   ├── pdf_writer.py          ← ReportLab fallback (plain text → PDF)
│   │   └── retry.py               ← Exponential backoff for Gemini calls
│   │
│   ├── templates/                 ← XeLaTeX document body templates (one per doc type)
│   ├── layouts/                   ← Shared brand preamble (fonts, geometry, header/footer)
│   ├── images/                    ← Turn2Law brand assets (header, footer, watermark PNGs)
│   ├── fonts/                     ← Montserrat + Garet TTF files
│   ├── generated_docs/            ← API-generated PDFs (gitignored)
│   └── .env                       ← GEMINI_API_KEY (not committed)
│
├── turn2law-site-main/            ← Frontend (vanilla HTML/CSS/JS)
│   ├── docengine-app.html         ← 9-step document generation wizard (SPA)
│   ├── docengine.html             ← Marketing/product page (links to the app)
│   ├── index.html                 ← Main website homepage
│   ├── introspector.html          ← Introspector product page
│   ├── legal-services.html        ← Legal services product page
│   ├── resources.html             ← Resources hub
│   ├── login.html / signup.html   ← Auth pages (stubbed)
│   └── turn2law-logo.png          ← Logo asset
│
└── ARCHITECTURE.md                ← Detailed technical architecture reference
```

---

## Quick start

### Prerequisites

- Python 3.11+
- MiKTeX (Windows) or TeX Live (Linux/macOS) with XeLaTeX
- Tesseract OCR (for image extraction)
- A Gemini API key (free tier works)

### 1. Install dependencies

```powershell
# From the project root
.venv\Scripts\activate          # Windows
# or: source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
# or if no requirements.txt:
pip install fastapi "uvicorn[standard]" python-multipart pillow pyhanko \
    google-genai pymupdf python-docx pytesseract python-dotenv cryptography
```

### 2. Configure environment

```powershell
# docgen/.env
GEMINI_API_KEY=your_key_here
```

Get a free key at [aistudio.google.com](https://aistudio.google.com).

### 3. Start the API server

```powershell
cd docgen
..\.venv\Scripts\python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Server starts at `http://localhost:8000`.  
Interactive API docs at `http://localhost:8000/docs`.

### 4. Open the frontend

Open `turn2law-site-main/docengine-app.html` in a browser.  
No build step required — plain HTML.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/templates` | List all document types with field metadata |
| GET | `/api/schema/{doc_type}` | Field schema for one document type |
| POST | `/api/generate` | Generate a PDF (JSON body) |
| POST | `/api/generate-with-branding` | Generate with custom brand assets (multipart) |
| POST | `/api/classify` | Classify an uploaded file via Gemini |
| POST | `/api/sign` | Digitally sign a generated PDF (multipart) |
| GET | `/api/preview/{doc_id}` | Check if a generated PDF exists |
| POST | `/api/validate-cert` | Validate a PKCS#12 certificate |
| GET | `/files/{filename}` | Download a generated PDF |

### Generate example

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

Returns: `{"success": true, "doc_id": "abc123", "pdf_url": "/files/abc123.pdf"}`

---

## Document types and fields

| Document | Required fields | Optional fields |
|----------|----------------|-----------------|
| Onboarding Letter | Employee_Name, Emp_ID, Role, Joining_Date, Document_Date | — |
| NDA | Name, Company, Date, Term, Jurisdiction | Confidential_Info_Description, Governing_Law |
| Offer Letter | Name, Company, Position, Start_Date, Salary | Manager_Name, Response_Date, HR_Manager, Benefits_Description |
| Contract | Client_Name, Company, Contract_Creation_Date, Service_Description, Payment_Amount, Start_Date, End_Date | Payment_Schedule, Termination_Clause |
| MOU | PartyA_Name, PartyB_Name, Date, Purpose, Term, Jurisdiction | Confidentiality, Termination_Clause, Governing_Law |
| IP Agreement | Name, Company, Date, Term, Jurisdiction | IP_Description, Governing_Law |

---

## Custom branding

Upload your own company assets to replace the Turn2Law letterhead:

```python
from app import make_custom_profile, generate_with_branding

brand = make_custom_profile(
    profile_id        = "acme_corp",
    name              = "ACME Corp",
    header_image_path = "/path/to/header.png",   # ≥595px wide, ≤150px tall, PNG
    footer_image_path = "/path/to/footer.png",   # optional, ≤120px tall
    watermark_image_path = "/path/to/wm.png",    # optional
    logo_image_path   = "/path/to/logo.png",     # optional
)

pdf = generate_with_branding("NDA", fields, brand)
```

Profiles are persisted in `docgen/branding/profiles/` and reused on subsequent calls.  
Asset constraints are validated (PNG magic bytes, minimum width 595px, file size < 5MB).

---

## Digital signature

The system uses **CMS/PAdES digital signatures** via pyHanko and PKCS#12 certificates.

```python
from app import sign_generated_pdf

signed = sign_generated_pdf(
    pdf_path    = "output.pdf",
    cert_path   = "my_cert.pfx",
    password    = "password",
    signer_name = "Mourya Veer",
    reason      = "Digitally approved",
    location    = "Chennai, India",
    contact     = "contact@company.com",
    visible     = True,   # embeds a visible stamp on the last page
)
```

**Generate a test certificate:**
```powershell
.venv\Scripts\python docgen\make_test_cert.py
# Output: docgen/my_cert.pfx  (password: 123456)
```

For production use a **Class 3 DSC** from eMudhra, nCode, or Sify (MCA-approved CAs for India).

---

## Run without the API (direct Python)

```powershell
cd docgen
..\\.venv\Scripts\python app.py
```

Edit `DOC_TYPE` and `SAMPLES` at the bottom of `app.py` to choose the document. Outputs `docgen/output.pdf` and `docgen/output_signed.pdf`.

---

## Adding a new document type

1. Add entry to `docgen/schema.py` with `required` and `optional` field lists
2. Create `docgen/templates/my_doc_template.tex` (start with `\input{LAYOUTS_DIR_PLACEHOLDERbrand_preamble}`)
3. Add to `TEMPLATE_MAP` in `docgen/app.py`
4. Add `"My_Doc_Type"` to `ALLOWED_TYPES` in `docgen/classifier/classify.py`
5. The API picks it up automatically — no changes to `api.py` needed

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Required for AI classification |
| `BRAND_PROFILES_DIR` | `docgen/branding/profiles/` | Where brand profiles are stored |
| `BRAND_MAX_ASSET_BYTES` | `5242880` (5 MB) | Max PNG upload size |
| `BRAND_MIN_HEADER_WIDTH_PX` | `595` | Minimum header image width |
| `BRAND_ASSET_DPI` | `96` | DPI used for px→pt margin conversion |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Web framework | FastAPI + Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| AI classification | Google Gemini 2.5 Flash |
| PDF compilation | XeLaTeX (MiKTeX / TeX Live) |
| PDF signing | pyHanko (CMS/PAdES) |
| Image processing | Pillow |
| PDF extraction | PyMuPDF |
| DOCX extraction | python-docx |
| OCR | pytesseract |
| Fonts | Montserrat, Garet (TTF via fontspec) |
| Config | python-dotenv |

---

## Legal notice

Turn2Law is a technology platform, not a law firm. Documents generated by this system are not legal advice. For high-stakes or court-facing documents, review with qualified counsel before use.

---

*Effivia Turn2Law Legal Pvt. Ltd. · CIN: U63110DL2025PTC443434*
