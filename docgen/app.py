# coding: utf-8
"""
app.py — Turn2Law document generation core library.

Workflow
--------
1. Extract text from an input document  (PDF / DOCX / image).
2. Classify document type via Google Gemini.
3. Validate user-supplied fields against the document schema.
4. Render the appropriate LaTeX template and compile to PDF (XeLaTeX × 2).
5. Optionally digitally sign the PDF with a PKCS#12 certificate.

All public functions are importable directly; the FastAPI layer in api.py
wraps them behind HTTP endpoints.
"""

from __future__ import annotations

import logging
import os

from utils.file_utils import extract_text
from classifier.classify import classify_document
from schema import DOCUMENT_SCHEMAS
from utils.latex_writer import render_latex

_HERE = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _t(name: str) -> str:
    return os.path.join(_HERE, "templates", name)


TEMPLATE_MAP: dict[str, str] = {
    "Onboarding_Letter": _t("onboarding_template.tex"),
    "NDA":               _t("nda_template.tex"),
    "Offer_Letter":      _t("offer_letter_template.tex"),
    "Contract":          _t("contract_template.tex"),
    "MOU":               _t("mou_template.tex"),
    "IP_Agreement":      _t("ip_agreement_template.tex"),
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_inputs(doc_type: str, user_inputs: dict) -> None:
    """Raise ValueError if any required field is missing or empty."""
    schema = DOCUMENT_SCHEMAS.get(doc_type)
    if not schema:
        raise ValueError(f"Unsupported document type: {doc_type!r}")
    missing = [
        f for f in schema["required"]
        if f not in user_inputs or not str(user_inputs[f]).strip()
    ]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


# ---------------------------------------------------------------------------
# Generation — with Gemini classification
# ---------------------------------------------------------------------------

def generate_document(
    file_path: str,
    user_inputs: dict,
    output_name: str = "output",
) -> tuple[str, str]:
    """
    Generate a PDF from *file_path* populated with *user_inputs*.

    Classifies the document type via Gemini before rendering.
    Returns (doc_type, pdf_path).
    """
    if not os.path.isabs(file_path):
        file_path = os.path.join(_HERE, file_path)

    extracted_text = extract_text(file_path)
    doc_type       = classify_document(extracted_text)
    validate_inputs(doc_type, user_inputs)

    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type!r}")

    output_tex = os.path.join(_HERE, f"{output_name}.tex")
    output_pdf = os.path.join(_HERE, f"{output_name}.pdf")

    render_latex(template_path, output_tex, output_pdf, user_inputs)
    return doc_type, output_pdf


# ---------------------------------------------------------------------------
# Generation — direct (skips Gemini classification)
# ---------------------------------------------------------------------------

def generate_direct(
    doc_type: str,
    user_inputs: dict,
    output_name: str = "output",
) -> str:
    """
    Generate a PDF directly by doc_type, skipping Gemini.
    Returns the absolute path to the generated PDF.
    """
    validate_inputs(doc_type, user_inputs)

    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type!r}")

    output_tex = os.path.join(_HERE, f"{output_name}.tex")
    output_pdf = os.path.join(_HERE, f"{output_name}.pdf")

    render_latex(template_path, output_tex, output_pdf, user_inputs)
    return output_pdf


# ---------------------------------------------------------------------------
# Generation — with branding
# ---------------------------------------------------------------------------

def generate_with_branding(
    doc_type: str,
    user_inputs: dict,
    brand_profile: object,
    output_name: str = "output",
) -> str:
    """
    Generate a PDF using a custom or Turn2Law brand profile.

    Parameters
    ----------
    doc_type      : document type key (e.g. "NDA")
    user_inputs   : dict of field values
    brand_profile : BrandProfile from branding module
    output_name   : base name for output files (default "output")

    Returns
    -------
    Absolute path to the generated PDF.
    """
    from branding import resolve_preamble

    validate_inputs(doc_type, user_inputs)
    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type!r}")

    preamble_path = resolve_preamble(brand_profile)
    output_tex    = os.path.join(_HERE, f"{output_name}.tex")
    output_pdf    = os.path.join(_HERE, f"{output_name}.pdf")

    render_latex(template_path, output_tex, output_pdf, user_inputs,
                 preamble_path=preamble_path)
    return output_pdf


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

def make_custom_profile(
    profile_id: str,
    name: str,
    header_image_path: str,
    footer_image_path: str | None = None,
    watermark_image_path: str | None = None,
    logo_image_path: str | None = None,
) -> object:
    """
    Construct and persist a custom BrandProfile.

    All image paths are resolved to absolute paths before saving so the
    profile remains valid regardless of the Python process working directory.

    Returns the saved BrandProfile.
    """
    from branding.models import BrandProfile, BrandMode
    from branding.asset_manager import save_profile

    def _abs(p: str | None) -> str | None:
        return os.path.abspath(p) if p else None

    profile = BrandProfile(
        profile_id           = profile_id,
        name                 = name,
        mode                 = BrandMode.CUSTOM,
        header_image_path    = _abs(header_image_path),
        footer_image_path    = _abs(footer_image_path),
        watermark_image_path = _abs(watermark_image_path),
        logo_image_path      = _abs(logo_image_path),
    )
    save_profile(profile)
    return profile


# ---------------------------------------------------------------------------
# Digital signature integration
# ---------------------------------------------------------------------------

def sign_generated_pdf(
    pdf_path: str,
    cert_path: str,
    password: str,
    signer_name: str,
    output_pdf: str | None = None,
    reason: str | None = None,
    location: str | None = None,
    contact: str | None = None,
    visible: bool = True,
) -> str:
    """
    Digitally sign a PDF using a .pfx / .p12 certificate.
    Returns the absolute path to the signed PDF.
    """
    from digital_signature.signer import sign_pdf_file

    logger.info("Initiating digital signing for: %s", pdf_path)
    signed_path = sign_pdf_file(
        pdf_path    = pdf_path,
        cert_path   = cert_path,
        password    = password,
        signer_name = signer_name,
        output_pdf  = output_pdf,
        reason      = reason,
        location    = location,
        contact     = contact,
        visible     = visible,
    )
    logger.info("Signed PDF: %s", signed_path)
    return signed_path


# ---------------------------------------------------------------------------
# Combined generation + signing
# ---------------------------------------------------------------------------

def generate_and_sign(
    doc_type: str,
    user_inputs: dict,
    cert_path: str,
    password: str,
    signer_name: str,
    output_name: str = "output",
    reason: str | None = None,
    location: str | None = None,
    contact: str | None = None,
    visible: bool = True,
) -> tuple[str, str]:
    """
    Generate a document AND sign it in one call.
    Returns (unsigned_pdf_path, signed_pdf_path).
    """
    unsigned_pdf = generate_direct(doc_type, user_inputs, output_name)
    signed_pdf   = sign_generated_pdf(
        pdf_path    = unsigned_pdf,
        cert_path   = cert_path,
        password    = password,
        signer_name = signer_name,
        reason      = reason,
        location    = location,
        contact     = contact,
        visible     = visible,
    )
    return unsigned_pdf, signed_pdf


# ---------------------------------------------------------------------------
# Quick-run entry point  (python app.py)
# Edit the variables in this block to test different scenarios.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # ── 1. Choose document type ──────────────────────────────────────────
    DOC_TYPE = "Onboarding_Letter"

    # ── 2. Company profile — CP_* tokens ────────────────────────────────
    #    Set to {} to use Turn2Law defaults (handled by _T2L_DEFAULTS in api.py).
    #    When running app.py directly, supply your own values here.
    COMPANY_PROFILE = {
        "CP_Company_Name":    "SynkSpace Technologies Pvt. Ltd.",
        "CP_Signatory_Name":  "Arjun Mehta",
        "CP_Designation":     "Founder & CEO",
        "CP_Company_Address": "4th Floor, Sector 62, Noida - 201301",
        "CP_Company_Email":   "hello@synkspace.io",
        "CP_Company_Phone":   "+91 98765 43210",
        "CP_Title_Suffix":    "",
        "CP_Signature_Image": "",
    }

    # ── 3. Field values per document type ────────────────────────────────
    SAMPLES: dict[str, dict] = {
        "Onboarding_Letter": {
            "Employee_Name": "Mourya Veer",
            "Emp_ID":        "SS-AI-041",
            "Role":          "AIML Intern",
            "Joining_Date":  "20 July 2026",
            "Document_Date": "30 June 2026",
        },
        "NDA": {
            "Name":         "Arjun Mehta",
            "Company":      "Nexus Innovations Pvt. Ltd., Bengaluru",
            "Date":         "10 July 2026",
            "Term":         "two (2) years",
            "Jurisdiction": "Chennai, Tamil Nadu",
        },
        "Offer_Letter": {
            "Name":       "Priya Sharma",
            "Company":    "42 Lake View Apartments, Koramangala, Bengaluru - 560034",
            "Position":   "Legal Associate",
            "Start_Date": "1 August 2026",
            "Salary":     "INR 6,00,000",
        },
        "Contract": {
            "Client_Name":            "Ravi Constructions Pvt. Ltd.",
            "Company":                "Plot 12, MIDC, Pune - 411019",
            "Contract_Creation_Date": "10 July 2026",
            "Service_Description":    "End-to-end legal documentation services.",
            "Payment_Amount":         "INR 1,50,000",
            "Start_Date":             "15 July 2026",
            "End_Date":               "14 January 2027",
        },
        "MOU": {
            "PartyA_Name":  "SynkSpace Technologies Pvt. Ltd.",
            "PartyB_Name":  "IIT Madras Incubation Cell, Chennai",
            "Date":         "10 July 2026",
            "Purpose":      "Collaboration on legal technology research.",
            "Term":         "one (1) year",
            "Jurisdiction": "Chennai, Tamil Nadu",
        },
        "IP_Agreement": {
            "Name":         "Siddharth Nair",
            "Company":      "Freelance Software Consultant, Hyderabad",
            "Date":         "10 July 2026",
            "Term":         "the duration of the engagement and three (3) years thereafter",
            "Jurisdiction": "Chennai, Tamil Nadu",
        },
    }

    inputs = {**SAMPLES.get(DOC_TYPE, {}), **COMPANY_PROFILE}

    # ── 4. Generate ──────────────────────────────────────────────────────
    try:
        pdf_path = generate_direct(DOC_TYPE, inputs, output_name="output")
        print(f"Document type : {DOC_TYPE}")
        print(f"Unsigned PDF  : {pdf_path}")
    except Exception as e:
        print(f"Generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # ── 5. Sign (optional) ───────────────────────────────────────────────
    #    Point CERT_PATH at your .pfx file and set CERT_PASS + SIGNER_NAME.
    CERT_PATH   = os.path.join(_HERE, "my_cert.pfx")
    CERT_PASS   = "123456"
    SIGNER_NAME = "Arjun Mehta"

    if os.path.isfile(CERT_PATH):
        try:
            signed = sign_generated_pdf(
                pdf_path    = pdf_path,
                cert_path   = CERT_PATH,
                password    = CERT_PASS,
                signer_name = SIGNER_NAME,
                reason      = "Digitally approved",
                location    = "India",
                visible     = True,
            )
            print(f"Signed PDF    : {signed}")
        except Exception as e:
            print(f"Signing failed (non-fatal): {e}", file=sys.stderr)
    else:
        print(f"Certificate not found at {CERT_PATH} — skipping signing.")
