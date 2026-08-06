# coding: utf-8
"""
api.py — Turn2Law Document Generation Engine — FastAPI web server.

Run from the docgen/ directory:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Endpoints
---------
GET  /api/templates               → list all document types
GET  /api/schema/{doc_type}       → field schema for one type
POST /api/generate                → generate PDF (JSON body)
POST /api/generate-with-branding  → generate with custom assets (multipart)
POST /api/generate-with-letterhead → generate with full-page letterhead (multipart)
POST /api/classify                → classify uploaded document
POST /api/sign                    → digitally sign a generated PDF (multipart)
GET  /api/preview/{doc_id}        → check existence of generated PDF
POST /api/validate-cert           → validate a PKCS#12 certificate (multipart)

Static files served at /files/<filename>.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_HERE, "generated_docs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(
    title="Turn2Law Document Generation API",
    description="Production API for generating, signing, and classifying legal documents.",
    version="1.0.0",
)

# CORS: allow_credentials must be False when allow_origins=["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/files", StaticFiles(directory=OUTPUT_DIR), name="files")

# Serve the frontend SPA at /app — must be mounted AFTER /files and all /api routes
# so API routes take priority. The mount is added at the bottom of the file after
# all routes are registered (see end of file).

# ---------------------------------------------------------------------------
# Document metadata
# ---------------------------------------------------------------------------
_TEMPLATE_META: Dict[str, Dict[str, str]] = {
    "Onboarding_Letter": {"name": "Onboarding Letter",         "description": "Employee welcome and joining documentation",          "icon": "user-plus"},
    "NDA":               {"name": "Non-Disclosure Agreement",  "description": "Protect confidential information between parties",    "icon": "shield"},
    "Offer_Letter":      {"name": "Offer Letter",              "description": "Formal employment offer with compensation details",   "icon": "briefcase"},
    "Contract":          {"name": "Service Contract",          "description": "B2B service agreement with payment terms",           "icon": "file-text"},
    "MOU":               {"name": "Memorandum of Understanding","description": "Business collaboration framework",                   "icon": "handshake"},
    "IP_Agreement":      {"name": "IP Assignment Agreement",   "description": "Intellectual property transfer and assignment",      "icon": "cpu"},
}

# ---------------------------------------------------------------------------
# Field-level metadata
# ---------------------------------------------------------------------------
FIELD_META: Dict[str, Dict[str, str]] = {
    "Employee_Name":               {"label": "Employee Name",                  "placeholder": "Full legal name of the employee",           "type": "text"},
    "Emp_ID":                      {"label": "Employee ID",                    "placeholder": "e.g. T2L-AI-041",                           "type": "text"},
    "Role":                        {"label": "Job Role / Designation",         "placeholder": "e.g. Software Engineer",                    "type": "text"},
    "Joining_Date":                {"label": "Date of Joining",                "placeholder": "e.g. 1 August 2026",                        "type": "text"},
    "Document_Date":               {"label": "Document Date",                  "placeholder": "e.g. 10 July 2026",                         "type": "text"},
    "Name":                        {"label": "Party Name",                     "placeholder": "Full name of the party",                    "type": "text"},
    "Company":                     {"label": "Company / Address",              "placeholder": "Company name and address",                  "type": "text"},
    "Date":                        {"label": "Effective Date",                 "placeholder": "e.g. 10 July 2026",                         "type": "text"},
    "Term":                        {"label": "Duration / Term",                "placeholder": "e.g. two (2) years",                        "type": "text"},
    "Jurisdiction":                {"label": "Jurisdiction",                   "placeholder": "City and State, e.g. Chennai, Tamil Nadu",  "type": "text"},
    "Confidential_Info_Description":{"label":"Confidential Information Description","placeholder":"Describe the confidential information","type":"textarea"},
    "Governing_Law":               {"label": "Governing Law Note",             "placeholder": "Additional governing law clause (optional)","type": "textarea"},
    "Position":                    {"label": "Position / Title",               "placeholder": "Job title being offered",                   "type": "text"},
    "Start_Date":                  {"label": "Start Date",                     "placeholder": "e.g. 1 August 2026",                        "type": "text"},
    "Salary":                      {"label": "Salary / CTC",                   "placeholder": "e.g. INR 6,00,000 per annum",               "type": "text"},
    "Manager_Name":                {"label": "Reporting Manager",              "placeholder": "Name of the reporting manager",             "type": "text"},
    "Response_Date":               {"label": "Offer Response Deadline",        "placeholder": "Date by which offer must be accepted",      "type": "text"},
    "HR_Manager":                  {"label": "HR Manager Name",                "placeholder": "Name of the HR contact",                    "type": "text"},
    "Benefits_Description":        {"label": "Benefits Description",           "placeholder": "Describe additional benefits",              "type": "textarea"},
    "Client_Name":                 {"label": "Client Name",                    "placeholder": "Full name of the client",                   "type": "text"},
    "Contract_Creation_Date":      {"label": "Contract Date",                  "placeholder": "e.g. 10 July 2026",                         "type": "text"},
    "Service_Description":         {"label": "Service Description",            "placeholder": "Describe the services to be provided",      "type": "textarea"},
    "Payment_Amount":              {"label": "Payment Amount",                 "placeholder": "e.g. INR 1,50,000",                         "type": "text"},
    "End_Date":                    {"label": "End Date",                       "placeholder": "e.g. 14 January 2027",                      "type": "text"},
    "Payment_Schedule":            {"label": "Payment Schedule",               "placeholder": "Describe payment milestones",               "type": "textarea"},
    "Termination_Clause":          {"label": "Termination Clause",             "placeholder": "Additional termination terms (optional)",   "type": "textarea"},
    "PartyA_Name":                 {"label": "Party A Name",                   "placeholder": "First party full name",                     "type": "text"},
    "PartyB_Name":                 {"label": "Party B Name",                   "placeholder": "Second party full name",                    "type": "text"},
    "Purpose":                     {"label": "Purpose / Scope",                "placeholder": "Describe the collaboration purpose",        "type": "textarea"},
    "Confidentiality":             {"label": "Confidentiality Clause",         "placeholder": "Custom confidentiality terms",              "type": "textarea"},
    "IP_Description":              {"label": "IP Description",                 "placeholder": "Describe the intellectual property",        "type": "textarea"},
}


def _field_meta(key: str) -> Dict[str, str]:
    if key in FIELD_META:
        return {"key": key, **FIELD_META[key]}
    return {"key": key, "label": key.replace("_", " "), "placeholder": f"Enter {key.replace('_',' ').lower()}", "type": "text"}


def _new_doc_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Turn2Law default company profile (injected when branding_mode='turn2law')
# Plain text — latex_writer handles & → \& escaping for CP_* keys.
# ---------------------------------------------------------------------------
_T2L_DEFAULTS: Dict[str, str] = {
    "CP_Company_Name":    "EFFIVIA TURN2LAW LEGAL PRIVATE LIMITED",
    "CP_Signatory_Name":  "Yash Phoghat",
    "CP_Designation":     "Founder & CEO",
    "CP_Company_Address": "Block 5, DEI Innovation Hub, SRMIST, Kattankulathur, Chennai - 603203, Tamil Nadu, India",
    "CP_Company_Email":   "turntwolaw@gmail.com",
    "CP_Company_Phone":   "",
    "CP_Company_Website": "www.turn2law.com",
    "CP_Signature_Image": "sample_asset_1_xref_47",
    "CP_Title_Suffix":    " - Turn2Law",
}

# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    doc_type: str
    fields: Dict[str, Any]
    output_name: Optional[str] = None
    company_profile: Optional[Dict[str, str]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/templates", summary="List all available document templates")
def list_templates() -> List[Dict[str, Any]]:
    from schema import DOCUMENT_SCHEMAS
    result: List[Dict[str, Any]] = []
    for doc_type, schema in DOCUMENT_SCHEMAS.items():
        meta = _TEMPLATE_META.get(doc_type, {})
        result.append({
            "id": doc_type,
            "name": meta.get("name", doc_type),
            "description": meta.get("description", ""),
            "icon": meta.get("icon", "file"),
            "required_fields": schema["required"],
            "optional_fields": schema["optional"],
        })
    return result


@app.get("/api/schema/{doc_type}", summary="Get field schema for a document type")
def get_schema(doc_type: str) -> Dict[str, Any]:
    from schema import DOCUMENT_SCHEMAS
    schema = DOCUMENT_SCHEMAS.get(doc_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Unknown document type: {doc_type!r}")
    return {
        "doc_type": doc_type,
        "required": [_field_meta(k) for k in schema["required"]],
        "optional": [_field_meta(k) for k in schema["optional"]],
    }


@app.post("/api/generate", summary="Generate a PDF document")
def generate(body: GenerateRequest) -> JSONResponse:
    doc_id = _new_doc_id()
    output_pdf_path = os.path.join(OUTPUT_DIR, f"{doc_id}.pdf")
    output_tex_path = os.path.join(OUTPUT_DIR, f"{doc_id}.tex")
    try:
        cp_json = json.dumps(body.company_profile) if body.company_profile else None
        merged = _merge_company_profile(body.fields, cp_json, branding_mode="turn2law")
        _generate_direct_to(
            doc_type=body.doc_type,
            user_inputs=merged,
            output_tex=output_tex_path,
            output_pdf=output_pdf_path,
        )
        _silent_remove(output_tex_path)
        return JSONResponse({"success": True, "doc_id": doc_id, "pdf_url": f"/files/{doc_id}.pdf", "doc_type": body.doc_type})
    except ValueError as exc:
        logger.warning("Validation error generating %s: %s", body.doc_type, exc)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error generating %s", body.doc_type)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@app.post("/api/generate-with-branding", summary="Generate a branded PDF document")
async def generate_with_branding_endpoint(
    doc_type: str = Form(...),
    fields_json: str = Form(...),
    profile_id: str = Form(...),
    profile_name: str = Form(...),
    company_profile_json: Optional[str] = Form(None),
    header_image: Optional[UploadFile] = File(None),
    footer_image: Optional[UploadFile] = File(None),
    watermark_image: Optional[UploadFile] = File(None),
    logo_image: Optional[UploadFile] = File(None),
    signature_image: Optional[UploadFile] = File(None),
) -> JSONResponse:
    from app import make_custom_profile
    doc_id  = _new_doc_id()
    tmp_dir = tempfile.mkdtemp(prefix="t2l_brand_")
    try:
        user_inputs: Dict[str, Any] = json.loads(fields_json)

        async def _save(upload: Optional[UploadFile], name: str) -> Optional[str]:
            if not upload or not upload.filename:
                return None
            ext  = os.path.splitext(upload.filename)[1] or ".png"
            dest = os.path.join(tmp_dir, f"{name}{ext}")
            with open(dest, "wb") as fh:
                fh.write(await upload.read())
            return dest

        header_path    = await _save(header_image,    "header")
        footer_path    = await _save(footer_image,    "footer")
        watermark_path = await _save(watermark_image, "watermark")
        logo_path      = await _save(logo_image,      "logo")
        sig_path       = await _save(signature_image, "signature")

        if not header_path:
            return JSONResponse({"success": False, "error": "header_image is required for custom branding."}, status_code=400)

        # Always clear stale preamble cache — tmp uploads have different absolute paths each time
        from branding.config import CONFIG as _BC
        _stale = os.path.join(_BC.profiles_dir, profile_id, "brand_preamble.tex")
        _silent_remove(_stale)

        merged = _merge_company_profile(user_inputs, company_profile_json, branding_mode="custom", sig_image_path=sig_path)
        brand  = make_custom_profile(
            profile_id=profile_id, name=profile_name,
            header_image_path=header_path, footer_image_path=footer_path,
            watermark_image_path=watermark_path, logo_image_path=logo_path,
        )

        output_pdf_path = os.path.join(OUTPUT_DIR, f"{doc_id}.pdf")
        output_tex_path = os.path.join(OUTPUT_DIR, f"{doc_id}.tex")
        _generate_with_branding_to(doc_type=doc_type, user_inputs=merged, brand_profile=brand, output_tex=output_tex_path, output_pdf=output_pdf_path)
        _silent_remove(output_tex_path)
        return JSONResponse({"success": True, "doc_id": doc_id, "pdf_url": f"/files/{doc_id}.pdf", "doc_type": doc_type})
    except ValueError as exc:
        logger.warning("Validation error in branding endpoint: %s", exc)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error in branding endpoint")
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/generate-with-letterhead", summary="Generate a PDF with a complete letterhead PNG")
async def generate_with_letterhead_endpoint(
    doc_type: str = Form(...),
    fields_json: str = Form(...),
    profile_id: str = Form(...),
    profile_name: str = Form(...),
    company_profile_json: Optional[str] = Form(None),
    letterhead_image: UploadFile = File(...),
    signature_image: Optional[UploadFile] = File(None),
) -> JSONResponse:
    from branding.complete_letterhead import validate_letterhead, generate_letterhead_preamble, LetterheadInfo
    from branding.models import BrandMode, BrandProfile
    from branding.asset_manager import save_profile as _save_profile
    from branding.config import CONFIG as _BC
    doc_id  = _new_doc_id()
    tmp_dir = tempfile.mkdtemp(prefix="t2l_lh_")
    try:
        user_inputs: Dict[str, Any] = json.loads(fields_json)

        lh_ext  = os.path.splitext(letterhead_image.filename or "lh.png")[1] or ".png"
        lh_path = os.path.join(tmp_dir, f"letterhead{lh_ext}")
        with open(lh_path, "wb") as fh:
            fh.write(await letterhead_image.read())

        sig_path: Optional[str] = None
        if signature_image and signature_image.filename:
            sig_ext  = os.path.splitext(signature_image.filename)[1] or ".png"
            sig_path = os.path.join(tmp_dir, f"signature{sig_ext}")
            with open(sig_path, "wb") as fh:
                fh.write(await signature_image.read())

        merged   = _merge_company_profile(user_inputs, company_profile_json, branding_mode="letterhead", sig_image_path=sig_path)
        info     = validate_letterhead(lh_path)

        profile_dir = os.path.join(_BC.profiles_dir, profile_id)
        os.makedirs(profile_dir, exist_ok=True)
        _silent_remove(os.path.join(profile_dir, "brand_preamble.tex"))  # clear cache

        lh_dest = os.path.join(profile_dir, "letterhead.png")
        shutil.copy2(lh_path, lh_dest)

        persistent_info = LetterheadInfo(
            path=lh_dest, width_px=info.width_px, height_px=info.height_px,
            file_size_bytes=info.file_size_bytes,
            top_margin_pt=info.top_margin_pt, bottom_margin_pt=info.bottom_margin_pt,
            left_margin_pt=info.left_margin_pt, right_margin_pt=info.right_margin_pt,
        )
        preamble_dest = os.path.join(profile_dir, "brand_preamble.tex")
        generate_letterhead_preamble(persistent_info, preamble_dest)

        profile = BrandProfile(profile_id=profile_id, name=profile_name, mode=BrandMode.LETTERHEAD, letterhead_image_path=lh_dest)
        _save_profile(profile)

        output_pdf_path = os.path.join(OUTPUT_DIR, f"{doc_id}.pdf")
        output_tex_path = os.path.join(OUTPUT_DIR, f"{doc_id}.tex")
        _generate_with_branding_to(doc_type=doc_type, user_inputs=merged, brand_profile=profile, output_tex=output_tex_path, output_pdf=output_pdf_path)
        _silent_remove(output_tex_path)

        return JSONResponse({
            "success": True, "doc_id": doc_id, "pdf_url": f"/files/{doc_id}.pdf", "doc_type": doc_type,
            "letterhead_info": {
                "width_px": info.width_px, "height_px": info.height_px,
                "top_margin_pt": round(info.top_margin_pt, 1), "bottom_margin_pt": round(info.bottom_margin_pt, 1),
                "left_margin_pt": round(info.left_margin_pt, 1), "right_margin_pt": round(info.right_margin_pt, 1),
            },
        })
    except ValueError as exc:
        logger.warning("Validation error in letterhead endpoint: %s", exc)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error in letterhead endpoint")
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/classify", summary="Classify an uploaded document")
async def classify(
    file: UploadFile = File(..., description="PDF, DOCX, or image file to classify"),
) -> JSONResponse:
    from classifier.classify import classify_document
    from utils.file_utils import extract_text
    tmp_dir = tempfile.mkdtemp(prefix="t2l_classify_")
    try:
        original_name = file.filename or "upload"
        tmp_path = os.path.join(tmp_dir, original_name)
        with open(tmp_path, "wb") as fh:
            fh.write(await file.read())
        text     = extract_text(tmp_path)
        doc_type = classify_document(text)
        confidence = "high" if len(text) > 200 else "low"
        return JSONResponse({"doc_type": doc_type, "confidence": confidence})
    except ValueError as exc:
        logger.warning("Classification error: %s", exc)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error during classification")
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/sign", summary="Digitally sign a generated PDF")
async def sign(
    doc_id:        str        = Form(...),
    cert_password: str        = Form(...),
    signer_name:   str        = Form(...),
    reason:        Optional[str] = Form(None),
    location:      Optional[str] = Form(None),
    contact:       Optional[str] = Form(None),
    visible:       bool       = Form(True),
    cert_file:     UploadFile = File(...),
) -> JSONResponse:
    import asyncio
    import functools
    from app import sign_generated_pdf

    source_pdf = os.path.join(OUTPUT_DIR, f"{doc_id}.pdf")
    if not os.path.isfile(source_pdf):
        return JSONResponse({"success": False, "error": f"Document {doc_id!r} not found."}, status_code=404)

    tmp_dir = tempfile.mkdtemp(prefix="t2l_sign_")
    try:
        cert_name = cert_file.filename or "cert.pfx"
        cert_path = os.path.join(tmp_dir, cert_name)
        with open(cert_path, "wb") as fh:
            fh.write(await cert_file.read())

        output_signed = os.path.join(OUTPUT_DIR, f"{doc_id}_signed.pdf")
        # pyHanko calls asyncio.run() internally — must run in thread with no active loop
        loop     = asyncio.get_running_loop()
        sign_fn  = functools.partial(
            sign_generated_pdf,
            pdf_path=source_pdf, cert_path=cert_path, password=cert_password,
            signer_name=signer_name, output_pdf=output_signed,
            reason=reason, location=location, contact=contact, visible=visible,
        )
        await loop.run_in_executor(None, sign_fn)
        return JSONResponse({"success": True, "doc_id": doc_id, "signed_pdf_url": f"/files/{doc_id}_signed.pdf"})
    except ValueError as exc:
        logger.warning("Validation error during signing: %s", exc)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error during signing")
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/api/preview/{doc_id}", summary="Check existence of a generated PDF")
def preview(doc_id: str) -> JSONResponse:
    pdf_path    = os.path.join(OUTPUT_DIR, f"{doc_id}.pdf")
    signed_path = os.path.join(OUTPUT_DIR, f"{doc_id}_signed.pdf")
    if not os.path.isfile(pdf_path):
        return JSONResponse({"exists": False, "pdf_url": None, "signed_url": None}, status_code=404)
    return JSONResponse({
        "exists":     True,
        "pdf_url":    f"/files/{doc_id}.pdf",
        "signed_url": f"/files/{doc_id}_signed.pdf" if os.path.isfile(signed_path) else None,
    })


@app.post("/api/validate-cert", summary="Validate a PKCS#12 certificate")
async def validate_cert(
    cert_file:     UploadFile = File(...),
    cert_password: str        = Form(...),
) -> JSONResponse:
    import asyncio
    import functools
    from digital_signature.certificate_loader import load_certificate
    from digital_signature.certificate_validator import validate_certificate

    tmp_dir = tempfile.mkdtemp(prefix="t2l_cert_")
    try:
        cert_name = cert_file.filename or "cert.pfx"
        cert_path = os.path.join(tmp_dir, cert_name)
        with open(cert_path, "wb") as fh:
            fh.write(await cert_file.read())

        loop    = asyncio.get_running_loop()
        load_fn = functools.partial(load_certificate, cert_path, cert_password)
        bundle  = await loop.run_in_executor(None, load_fn)

        # Also run validation checks in the executor
        validate_fn = functools.partial(validate_certificate, bundle)
        await loop.run_in_executor(None, validate_fn)

        cert = bundle.certificate
        try:
            expires_dt = cert.not_valid_after_utc          # cryptography >= 42
        except AttributeError:
            expires_dt = cert.not_valid_after              # older versions
        expires_str = expires_dt.strftime("%d %B %Y")

        subject = bundle.subject_cn
        issuer  = bundle.issuer_cn
        bundle.dispose()

        return JSONResponse({"valid": True, "subject": subject, "issuer": issuer, "expires": expires_str})
    except Exception as exc:
        logger.warning("Certificate validation failed: %s", exc)
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=400)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _merge_company_profile(
    user_inputs: Dict[str, Any],
    company_profile_json: Optional[str],
    branding_mode: str = "turn2law",
    sig_image_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merge CP_* company-profile tokens into user_inputs.

    Priority (highest → lowest):
      1. customer values from company_profile_json
      2. Turn2Law defaults   (only when branding_mode == 'turn2law')
      3. empty-string fallback (so \\ifthenelse guards in templates work)
    """
    merged: Dict[str, Any] = dict(user_inputs)

    cp: Dict[str, str] = {}
    if company_profile_json:
        try:
            cp = json.loads(company_profile_json)
        except (json.JSONDecodeError, ValueError):
            cp = {}

    if branding_mode == "turn2law":
        base: Dict[str, str] = dict(_T2L_DEFAULTS)
    else:
        # White-label / custom / letterhead — blank slate; no T2L branding
        base = {k: "" for k in _T2L_DEFAULTS}

    # Customer values override the base
    base.update({k: v for k, v in cp.items() if v is not None})

    # Signature image: copy PNG to shared images/ dir; store only the stem
    _IMAGES_DIR = os.path.join(_HERE, "images")
    os.makedirs(_IMAGES_DIR, exist_ok=True)

    if sig_image_path and os.path.isfile(sig_image_path):
        stem = os.path.splitext(os.path.basename(sig_image_path))[0]
        dest = os.path.join(_IMAGES_DIR, stem + ".png")
        if not os.path.exists(dest):
            shutil.copy2(sig_image_path, dest)
        base["CP_Signature_Image"] = stem
    elif branding_mode != "turn2law":
        base.setdefault("CP_Signature_Image", "")

    # Inject all CP_ keys; do not overwrite keys already in user_inputs
    for key, val in base.items():
        merged.setdefault(key, val)

    return merged


def _generate_direct_to(
    doc_type: str,
    user_inputs: Dict[str, Any],
    output_tex: str,
    output_pdf: str,
) -> str:
    """generate_direct variant that writes to caller-specified paths."""
    from app import validate_inputs, TEMPLATE_MAP
    from utils.latex_writer import render_latex
    validate_inputs(doc_type, user_inputs)
    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type!r}")
    render_latex(template_path, output_tex, output_pdf, user_inputs)
    return output_pdf


def _generate_with_branding_to(
    doc_type: str,
    user_inputs: Dict[str, Any],
    brand_profile: Any,
    output_tex: str,
    output_pdf: str,
) -> str:
    """generate_with_branding variant that writes to caller-specified paths."""
    from app import validate_inputs, TEMPLATE_MAP
    from branding import resolve_preamble
    from utils.latex_writer import render_latex
    validate_inputs(doc_type, user_inputs)
    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type!r}")
    preamble_path = resolve_preamble(brand_profile)
    render_latex(template_path, output_tex, output_pdf, user_inputs, preamble_path=preamble_path)
    return output_pdf


def _silent_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Mount frontend AFTER all API routes so /api/* takes priority
_FRONTEND_DIR = os.path.normpath(os.path.join(_HERE, "..", "turn2law-site-main"))
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
    logger.info("Frontend mounted at /app from %s", _FRONTEND_DIR)
else:
    logger.warning("Frontend directory not found at %s — /app not mounted", _FRONTEND_DIR)

@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect / → /app/docengine-app.html for convenience."""
    return RedirectResponse(url="/app/docengine-app.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
