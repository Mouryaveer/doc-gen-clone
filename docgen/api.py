# coding: utf-8
"""
api.py — Turn2Law Document Generation Engine — FastAPI web server.

Run from the docgen/ directory:
    python api.py
    # or
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Endpoints
---------
GET  /api/templates               → list all document types with metadata
GET  /api/schema/{doc_type}       → field-level schema for one doc type
POST /api/generate                → generate a PDF (JSON body)
POST /api/generate-with-branding  → generate with custom brand (multipart)
POST /api/classify                → classify an uploaded document
POST /api/sign                    → digitally sign a generated PDF (multipart)
GET  /api/preview/{doc_id}        → check existence of a generated PDF
POST /api/validate-cert           → validate a PKCS#12 certificate (multipart)

Static files (generated PDFs) are served at /files/<filename>.
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
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_HERE, "generated_docs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Turn2Law Document Generation API",
    description="Production API for generating, signing, and classifying legal documents.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated PDFs at /files/<filename>
app.mount("/files", StaticFiles(directory=OUTPUT_DIR), name="files")

# ---------------------------------------------------------------------------
# Document metadata — displayed on the template listing page
# ---------------------------------------------------------------------------
_TEMPLATE_META: Dict[str, Dict[str, str]] = {
    "Onboarding_Letter": {
        "name": "Onboarding Letter",
        "description": "Employee welcome and joining documentation",
        "icon": "user-plus",
    },
    "NDA": {
        "name": "Non-Disclosure Agreement",
        "description": "Protect confidential information between parties",
        "icon": "shield",
    },
    "Offer_Letter": {
        "name": "Offer Letter",
        "description": "Formal employment offer with compensation details",
        "icon": "briefcase",
    },
    "Contract": {
        "name": "Service Contract",
        "description": "B2B service agreement with payment terms",
        "icon": "file-text",
    },
    "MOU": {
        "name": "Memorandum of Understanding",
        "description": "Business collaboration framework",
        "icon": "handshake",
    },
    "IP_Agreement": {
        "name": "IP Assignment Agreement",
        "description": "Intellectual property transfer and assignment",
        "icon": "cpu",
    },
}

# ---------------------------------------------------------------------------
# Field-level metadata — human-readable labels, placeholders, input type hints
# ---------------------------------------------------------------------------
FIELD_META: Dict[str, Dict[str, str]] = {
    "Employee_Name": {
        "label": "Employee Name",
        "placeholder": "Full legal name of the employee",
        "type": "text",
    },
    "Emp_ID": {
        "label": "Employee ID",
        "placeholder": "e.g. T2L-AI-041",
        "type": "text",
    },
    "Role": {
        "label": "Job Role / Designation",
        "placeholder": "e.g. Software Engineer",
        "type": "text",
    },
    "Joining_Date": {
        "label": "Date of Joining",
        "placeholder": "e.g. 1 August 2026",
        "type": "text",
    },
    "Document_Date": {
        "label": "Document Date",
        "placeholder": "e.g. 10 July 2026",
        "type": "text",
    },
    "Name": {
        "label": "Party Name",
        "placeholder": "Full name of the party",
        "type": "text",
    },
    "Company": {
        "label": "Company / Address",
        "placeholder": "Company name and address",
        "type": "text",
    },
    "Date": {
        "label": "Effective Date",
        "placeholder": "e.g. 10 July 2026",
        "type": "text",
    },
    "Term": {
        "label": "Duration / Term",
        "placeholder": "e.g. two (2) years",
        "type": "text",
    },
    "Jurisdiction": {
        "label": "Jurisdiction",
        "placeholder": "City and State, e.g. Chennai, Tamil Nadu",
        "type": "text",
    },
    "Confidential_Info_Description": {
        "label": "Confidential Information Description",
        "placeholder": "Describe the confidential information",
        "type": "textarea",
    },
    "Governing_Law": {
        "label": "Governing Law Note",
        "placeholder": "Additional governing law clause (optional)",
        "type": "textarea",
    },
    "Position": {
        "label": "Position / Title",
        "placeholder": "Job title being offered",
        "type": "text",
    },
    "Start_Date": {
        "label": "Start Date",
        "placeholder": "e.g. 1 August 2026",
        "type": "text",
    },
    "Salary": {
        "label": "Salary / CTC",
        "placeholder": "e.g. INR 6,00,000 per annum",
        "type": "text",
    },
    "Manager_Name": {
        "label": "Reporting Manager",
        "placeholder": "Name of the reporting manager",
        "type": "text",
    },
    "Response_Date": {
        "label": "Offer Response Deadline",
        "placeholder": "Date by which offer must be accepted",
        "type": "text",
    },
    "HR_Manager": {
        "label": "HR Manager Name",
        "placeholder": "Name of the HR contact",
        "type": "text",
    },
    "Benefits_Description": {
        "label": "Benefits Description",
        "placeholder": "Describe additional benefits",
        "type": "textarea",
    },
    "Client_Name": {
        "label": "Client Name",
        "placeholder": "Full name of the client",
        "type": "text",
    },
    "Contract_Creation_Date": {
        "label": "Contract Date",
        "placeholder": "e.g. 10 July 2026",
        "type": "text",
    },
    "Service_Description": {
        "label": "Service Description",
        "placeholder": "Describe the services to be provided",
        "type": "textarea",
    },
    "Payment_Amount": {
        "label": "Payment Amount",
        "placeholder": "e.g. INR 1,50,000",
        "type": "text",
    },
    "End_Date": {
        "label": "End Date",
        "placeholder": "e.g. 14 January 2027",
        "type": "text",
    },
    "Payment_Schedule": {
        "label": "Payment Schedule",
        "placeholder": "Describe payment milestones",
        "type": "textarea",
    },
    "Termination_Clause": {
        "label": "Termination Clause",
        "placeholder": "Additional termination terms (optional)",
        "type": "textarea",
    },
    "PartyA_Name": {
        "label": "Party A Name",
        "placeholder": "First party full name",
        "type": "text",
    },
    "PartyB_Name": {
        "label": "Party B Name",
        "placeholder": "Second party full name",
        "type": "text",
    },
    "Purpose": {
        "label": "Purpose / Scope",
        "placeholder": "Describe the collaboration purpose",
        "type": "textarea",
    },
    "Confidentiality": {
        "label": "Confidentiality Clause",
        "placeholder": "Custom confidentiality terms",
        "type": "textarea",
    },
    "IP_Description": {
        "label": "IP Description",
        "placeholder": "Describe the intellectual property being assigned",
        "type": "textarea",
    },
}


def _field_meta(key: str) -> Dict[str, str]:
    """Return metadata for a field key, falling back to a sensible default."""
    if key in FIELD_META:
        return {"key": key, **FIELD_META[key]}
    # Auto-generate label from snake_case key
    return {
        "key": key,
        "label": key.replace("_", " "),
        "placeholder": f"Enter {key.replace('_', ' ').lower()}",
        "type": "text",
    }


def _new_doc_id() -> str:
    """Generate a short, URL-safe document ID."""
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """Body for POST /api/generate."""

    doc_type: str
    fields: Dict[str, Any]
    output_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/templates", summary="List all available document templates")
def list_templates() -> List[Dict[str, Any]]:
    """
    Return metadata for every supported document type including required and
    optional field lists and a display icon identifier.
    """
    from schema import DOCUMENT_SCHEMAS  # local import keeps startup fast

    result: List[Dict[str, Any]] = []
    for doc_type, schema in DOCUMENT_SCHEMAS.items():
        meta = _TEMPLATE_META.get(doc_type, {})
        result.append(
            {
                "id": doc_type,
                "name": meta.get("name", doc_type),
                "description": meta.get("description", ""),
                "icon": meta.get("icon", "file"),
                "required_fields": schema["required"],
                "optional_fields": schema["optional"],
            }
        )
    return result


@app.get("/api/schema/{doc_type}", summary="Get field schema for a document type")
def get_schema(doc_type: str) -> Dict[str, Any]:
    """
    Return rich field metadata (label, placeholder, input type) for all
    required and optional fields of the requested document type.
    """
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
    """
    Generate a PDF for the given document type and field values.

    The PDF is written to OUTPUT_DIR and served via /files/<doc_id>.pdf.
    """
    from app import generate_direct  # noqa: PLC0415 — intentional local import

    doc_id = _new_doc_id()
    output_pdf_path = os.path.join(OUTPUT_DIR, f"{doc_id}.pdf")
    output_tex_path = os.path.join(OUTPUT_DIR, f"{doc_id}.tex")

    try:
        # generate_direct writes to _HERE by default; we need to redirect output
        # by temporarily patching the output paths via a wrapper approach.
        # We call generate_direct then move the file if it landed in _HERE.
        pdf_path = _generate_direct_to(
            doc_type=body.doc_type,
            user_inputs=body.fields,
            output_tex=output_tex_path,
            output_pdf=output_pdf_path,
        )

        # Clean up the .tex intermediate if it exists in OUTPUT_DIR
        _silent_remove(output_tex_path)

        return JSONResponse(
            {
                "success": True,
                "doc_id": doc_id,
                "pdf_url": f"/files/{doc_id}.pdf",
                "doc_type": body.doc_type,
            }
        )
    except ValueError as exc:
        logger.warning("Validation error generating %s: %s", body.doc_type, exc)
        return JSONResponse(
            {"success": False, "error": str(exc)},
            status_code=400,
        )
    except Exception as exc:
        logger.exception("Unexpected error generating %s", body.doc_type)
        return JSONResponse(
            {"success": False, "error": str(exc)},
            status_code=500,
        )


@app.post("/api/generate-with-branding", summary="Generate a branded PDF document")
async def generate_with_branding_endpoint(
    doc_type: str = Form(...),
    fields_json: str = Form(...),
    profile_id: str = Form(...),
    profile_name: str = Form(...),
    header_image: Optional[UploadFile] = File(None),
    footer_image: Optional[UploadFile] = File(None),
    watermark_image: Optional[UploadFile] = File(None),
    logo_image: Optional[UploadFile] = File(None),
) -> JSONResponse:
    """
    Generate a PDF with a custom brand profile.

    Accepts multipart/form-data with optional image uploads for header,
    footer, watermark, and logo.  Returns the same shape as /api/generate.
    """
    from app import generate_with_branding, make_custom_profile

    doc_id = _new_doc_id()
    tmp_dir = tempfile.mkdtemp(prefix="t2l_brand_")

    try:
        user_inputs: Dict[str, Any] = json.loads(fields_json)

        # Save uploaded images to temp directory
        async def _save_upload(upload: Optional[UploadFile], name: str) -> Optional[str]:
            if upload is None or not upload.filename:
                return None
            ext = os.path.splitext(upload.filename)[1] or ".png"
            dest = os.path.join(tmp_dir, f"{name}{ext}")
            content = await upload.read()
            with open(dest, "wb") as fh:
                fh.write(content)
            return dest

        header_path = await _save_upload(header_image, "header")
        footer_path = await _save_upload(footer_image, "footer")
        watermark_path = await _save_upload(watermark_image, "watermark")
        logo_path = await _save_upload(logo_image, "logo")

        if not header_path:
            return JSONResponse(
                {"success": False, "error": "header_image is required for branding."},
                status_code=400,
            )

        # Build brand profile
        brand_profile = make_custom_profile(
            profile_id=profile_id,
            name=profile_name,
            header_image_path=header_path,
            footer_image_path=footer_path,
            watermark_image_path=watermark_path,
            logo_image_path=logo_path,
        )

        output_pdf_path = os.path.join(OUTPUT_DIR, f"{doc_id}.pdf")
        output_tex_path = os.path.join(OUTPUT_DIR, f"{doc_id}.tex")

        _generate_with_branding_to(
            doc_type=doc_type,
            user_inputs=user_inputs,
            brand_profile=brand_profile,
            output_tex=output_tex_path,
            output_pdf=output_pdf_path,
        )

        _silent_remove(output_tex_path)

        return JSONResponse(
            {
                "success": True,
                "doc_id": doc_id,
                "pdf_url": f"/files/{doc_id}.pdf",
                "doc_type": doc_type,
            }
        )
    except ValueError as exc:
        logger.warning("Validation error in branding endpoint: %s", exc)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error in branding endpoint")
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/classify", summary="Classify an uploaded document")
async def classify(
    file: UploadFile = File(..., description="PDF, DOCX, or image file to classify"),
) -> JSONResponse:
    """
    Extract text from the uploaded file and classify it into one of the
    supported document types using the Gemini-powered classifier.

    Returns the predicted doc_type and a confidence label.
    """
    from classifier.classify import classify_document
    from utils.file_utils import extract_text

    tmp_dir = tempfile.mkdtemp(prefix="t2l_classify_")
    try:
        # Persist the upload so extract_text can read it from disk
        original_name = file.filename or "upload"
        tmp_path = os.path.join(tmp_dir, original_name)
        content = await file.read()
        with open(tmp_path, "wb") as fh:
            fh.write(content)

        text = extract_text(tmp_path)
        doc_type = classify_document(text)

        # Simple heuristic confidence: if text is long enough the model had
        # plenty of signal; short extracts are low confidence.
        confidence = "high" if len(text) > 200 else "low"

        return JSONResponse({"doc_type": doc_type, "confidence": confidence})
    except ValueError as exc:
        logger.warning("Classification validation error: %s", exc)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error during classification")
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/sign", summary="Digitally sign a generated PDF")
async def sign(
    doc_id: str = Form(..., description="Document ID returned by /api/generate"),
    cert_password: str = Form(..., description="Password for the PKCS#12 certificate"),
    signer_name: str = Form(..., description="Full name of the signer"),
    reason: Optional[str] = Form(None, description="Reason for signing"),
    location: Optional[str] = Form(None, description="Geographic location of the signer"),
    contact: Optional[str] = Form(None, description="Contact email or phone of the signer"),
    visible: bool = Form(True, description="Whether to embed a visible signature stamp"),
    cert_file: UploadFile = File(..., description=".pfx or .p12 certificate file"),
) -> JSONResponse:
    """
    Digitally sign a previously generated PDF using a PKCS#12 certificate.

    pyHanko internally calls asyncio.run(), which cannot be called from a
    running event loop.  We therefore offload the entire signing operation
    to a thread-pool executor so it runs in a plain thread without an
    active event loop.

    The signed PDF is saved alongside the original as {doc_id}_signed.pdf
    and served at /files/{doc_id}_signed.pdf.
    """
    import asyncio
    import functools
    from app import sign_generated_pdf

    source_pdf = os.path.join(OUTPUT_DIR, f"{doc_id}.pdf")
    if not os.path.isfile(source_pdf):
        return JSONResponse(
            {"success": False, "error": f"Document {doc_id!r} not found. Generate it first."},
            status_code=404,
        )

    tmp_dir = tempfile.mkdtemp(prefix="t2l_sign_")
    try:
        # Save certificate to a temp file (must happen in the async context)
        cert_name = cert_file.filename or "cert.pfx"
        cert_path = os.path.join(tmp_dir, cert_name)
        cert_bytes = await cert_file.read()
        with open(cert_path, "wb") as fh:
            fh.write(cert_bytes)

        output_signed = os.path.join(OUTPUT_DIR, f"{doc_id}_signed.pdf")

        # Run the blocking pyHanko signing call in a thread-pool executor.
        # This gives the thread its own (non-running) context so asyncio.run()
        # inside pyHanko works correctly.
        loop = asyncio.get_event_loop()
        sign_fn = functools.partial(
            sign_generated_pdf,
            pdf_path=source_pdf,
            cert_path=cert_path,
            password=cert_password,
            signer_name=signer_name,
            output_pdf=output_signed,
            reason=reason,
            location=location,
            contact=contact,
            visible=visible,
        )
        await loop.run_in_executor(None, sign_fn)

        return JSONResponse(
            {
                "success": True,
                "doc_id": doc_id,
                "signed_pdf_url": f"/files/{doc_id}_signed.pdf",
            }
        )
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
    """
    Check whether a generated PDF (and optionally a signed variant) exist
    and return their URLs.
    """
    pdf_path = os.path.join(OUTPUT_DIR, f"{doc_id}.pdf")
    signed_path = os.path.join(OUTPUT_DIR, f"{doc_id}_signed.pdf")

    if not os.path.isfile(pdf_path):
        return JSONResponse(
            {"exists": False, "pdf_url": None, "signed_url": None},
            status_code=404,
        )

    return JSONResponse(
        {
            "exists": True,
            "pdf_url": f"/files/{doc_id}.pdf",
            "signed_url": f"/files/{doc_id}_signed.pdf" if os.path.isfile(signed_path) else None,
        }
    )


@app.post("/api/validate-cert", summary="Validate a PKCS#12 certificate")
async def validate_cert(
    cert_file: UploadFile = File(..., description=".pfx or .p12 certificate file"),
    cert_password: str = Form(..., description="Certificate password"),
) -> JSONResponse:
    """
    Load and validate the uploaded PKCS#12 certificate.

    Runs in a thread executor to avoid asyncio.run() conflicts with
    pyHanko internals.  Returns subject CN, issuer CN, and expiry date.
    """
    import asyncio
    import functools
    from digital_signature.certificate_loader import load_certificate

    tmp_dir = tempfile.mkdtemp(prefix="t2l_cert_")
    try:
        cert_name = cert_file.filename or "cert.pfx"
        cert_path = os.path.join(tmp_dir, cert_name)
        cert_bytes = await cert_file.read()
        with open(cert_path, "wb") as fh:
            fh.write(cert_bytes)

        # Run blocking cert load in a thread to avoid event-loop conflict
        loop = asyncio.get_event_loop()
        load_fn = functools.partial(load_certificate, cert_path, cert_password)
        bundle = await loop.run_in_executor(None, load_fn)

        # Extract expiry — handle both aware and naïve datetimes
        cert = bundle.certificate
        try:
            expires_dt = cert.not_valid_after_utc  # type: ignore[attr-defined]
        except AttributeError:
            expires_dt = cert.not_valid_after  # type: ignore[attr-defined]

        expires_str = expires_dt.strftime("%d %B %Y")

        subject = bundle.subject_cn
        issuer = bundle.issuer_cn
        bundle.dispose()

        return JSONResponse(
            {
                "valid": True,
                "subject": subject,
                "issuer": issuer,
                "expires": expires_str,
            }
        )
    except Exception as exc:
        logger.warning("Certificate validation failed: %s", exc)
        return JSONResponse(
            {"valid": False, "error": str(exc)},
            status_code=400,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Internal helpers — output-path redirection
# ---------------------------------------------------------------------------


def _generate_direct_to(
    doc_type: str,
    user_inputs: Dict[str, Any],
    output_tex: str,
    output_pdf: str,
) -> str:
    """
    Variant of app.generate_direct that writes to caller-specified paths
    rather than defaulting to _HERE.

    This avoids polluting the package directory with generated files.
    """
    from app import validate_inputs, TEMPLATE_MAP
    from utils.latex_writer import render_latex

    validate_inputs(doc_type, user_inputs)
    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type}")

    render_latex(template_path, output_tex, output_pdf, user_inputs)
    return output_pdf


def _generate_with_branding_to(
    doc_type: str,
    user_inputs: Dict[str, Any],
    brand_profile: Any,
    output_tex: str,
    output_pdf: str,
) -> str:
    """
    Variant of app.generate_with_branding that writes to caller-specified paths.
    """
    from app import validate_inputs, TEMPLATE_MAP
    from branding import resolve_preamble
    from utils.latex_writer import render_latex

    validate_inputs(doc_type, user_inputs)
    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type}")

    preamble_path = resolve_preamble(brand_profile)
    render_latex(template_path, output_tex, output_pdf, user_inputs, preamble_path=preamble_path)
    return output_pdf


def _silent_remove(path: str) -> None:
    """Remove a file without raising if it doesn't exist."""
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
