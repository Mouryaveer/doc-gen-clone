# coding: utf-8
"""
app.py - Turn2Law document generation system.

Workflow:
  1. Extract text from input document (PDF / DOCX / image).
  2. Classify document type using Google Gemini.
  3. Validate user-supplied fields against the document schema.
  4. Render the appropriate LaTeX template and compile to PDF.
  5. (Optional) Digitally sign the PDF with a PKCS#12 certificate.
"""

import os
import logging

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


def _t(name):
    return os.path.join(_HERE, "templates", name)


TEMPLATE_MAP = {
    "Onboarding_Letter": _t("onboarding_template.tex"),
    "NDA":               _t("nda_template.tex"),
    "Offer_Letter":      _t("offer_letter_template.tex"),
    "Contract":          _t("contract_template.tex"),
    "MOU":               _t("mou_template.tex"),
    "IP_Agreement":      _t("ip_agreement_template.tex"),
}


# ===========================================================================
#  Validation
# ===========================================================================

def validate_inputs(doc_type, user_inputs):
    schema = DOCUMENT_SCHEMAS.get(doc_type)
    if not schema:
        raise ValueError(f"Unsupported document type: {doc_type}")
    missing = [
        f for f in schema["required"]
        if f not in user_inputs or not user_inputs[f]
    ]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


# ===========================================================================
#  Generation - with Gemini classification
# ===========================================================================

def generate_document(file_path, user_inputs, output_name="output"):
    """
    Generate a PDF from file_path populated with user_inputs.
    Returns (doc_type, pdf_path).
    """
    if not os.path.isabs(file_path):
        file_path = os.path.join(_HERE, file_path)

    extracted_text = extract_text(file_path)
    doc_type = classify_document(extracted_text)
    validate_inputs(doc_type, user_inputs)

    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type}")

    output_tex = os.path.join(_HERE, f"{output_name}.tex")
    output_pdf = os.path.join(_HERE, f"{output_name}.pdf")

    render_latex(template_path, output_tex, output_pdf, user_inputs)
    return doc_type, output_pdf


# ===========================================================================
#  Generation - direct (skips Gemini)
# ===========================================================================

def generate_direct(doc_type, user_inputs, output_name="output"):
    """
    Generate a PDF directly by doc_type - skips Gemini classification.
    Returns the absolute path to the generated PDF.
    """
    validate_inputs(doc_type, user_inputs)

    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type}")

    output_tex = os.path.join(_HERE, f"{output_name}.tex")
    output_pdf = os.path.join(_HERE, f"{output_name}.pdf")

    render_latex(template_path, output_tex, output_pdf, user_inputs)
    return output_pdf


# ===========================================================================
#  Digital signature integration
# ===========================================================================

def sign_generated_pdf(
    pdf_path,
    cert_path,
    password,
    signer_name,
    output_pdf=None,
    reason=None,
    location=None,
    contact=None,
    visible=True,
):
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


def generate_with_branding(doc_type, user_inputs, brand_profile, output_name="output"):
    """
    Generate a PDF using a custom or Turn2Law brand profile.

    Parameters
    ----------
    doc_type      : document type key (e.g. "NDA", "Offer_Letter")
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
        raise ValueError(f"No template found for document type: {doc_type}")
    preamble_path = resolve_preamble(brand_profile)
    output_tex = os.path.join(_HERE, f"{output_name}.tex")
    output_pdf = os.path.join(_HERE, f"{output_name}.pdf")
    render_latex(template_path, output_tex, output_pdf, user_inputs,
                 preamble_path=preamble_path)
    return output_pdf


def make_custom_profile(profile_id, name, header_image_path,
                        footer_image_path=None,
                        watermark_image_path=None,
                        logo_image_path=None):
    """
    Construct and save a custom BrandProfile.

    Parameters
    ----------
    profile_id          : unique slug (e.g. "my_company")
    name                : human-readable label (e.g. "My Company Ltd")
    header_image_path   : required path to letterhead PNG
    footer_image_path   : optional footer PNG
    watermark_image_path: optional watermark PNG
    logo_image_path     : optional logo PNG

    Returns
    -------
    The saved BrandProfile.
    """
    from branding.models import BrandProfile, BrandMode
    from branding.asset_manager import save_profile
    profile = BrandProfile(
        profile_id           = profile_id,
        name                 = name,
        mode                 = BrandMode.CUSTOM,
        header_image_path    = os.path.abspath(header_image_path),
        footer_image_path    = os.path.abspath(footer_image_path) if footer_image_path else None,
        watermark_image_path = os.path.abspath(watermark_image_path) if watermark_image_path else None,
        logo_image_path      = os.path.abspath(logo_image_path) if logo_image_path else None,
    )
    save_profile(profile)
    return profile


# ===========================================================================
#  Generation + Signing combined
# ===========================================================================

def generate_and_sign(
    doc_type,
    user_inputs,
    cert_path,
    password,
    signer_name,
    output_name="output",
    reason=None,
    location=None,
    contact=None,
    visible=True,
):
    """
    Generate a document AND sign it in one call.
    Returns (unsigned_pdf_path, signed_pdf_path).
    """
    unsigned_pdf = generate_direct(doc_type, user_inputs, output_name)
    signed_pdf = sign_generated_pdf(
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


# ===========================================================================
#  Quick-run entry point
#  Edit DOC_TYPE, the matching SAMPLES block, and the three CERT_ lines below.
# ===========================================================================
if __name__ == "__main__":

    # -----------------------------------------------------------------------
    # CHANGE 1: pick the document type you want to generate
    # -----------------------------------------------------------------------
    DOC_TYPE = "Onboarding_Letter"

    SAMPLES = {
        "Onboarding_Letter": {
            "Employee_Name": "Mourya Veer",
            "Emp_ID":        "T2L-AI-041",
            "Role":          "AIML Intern",
            "Joining_Date":  "20 July 2026",
            "Document_Date": "30 June 2026",
        },
        "NDA": {
            "Name":        "Arjun Mehta",
            "Company":     "Nexus Innovations Pvt. Ltd., Bengaluru",
            "Date":        "10 July 2026",
            "Term":        "two (2) years",
            "Jurisdiction": "Chennai, Tamil Nadu",
            "Confidential_Info_Description": "Technical architecture of the AI-powered contract review module.",
            "Governing_Law": "",
        },
        "Offer_Letter": {
            "Name":        "Priya Sharma",
            "Company":     "42 Lake View Apartments, Koramangala, Bengaluru - 560034",
            "Position":    "Legal Associate",
            "Start_Date":  "1 August 2026",
            "Salary":      "INR 6,00,000",
            "Manager_Name":   "Yash Phoghat",
            "Response_Date":  "20 July 2026",
            "HR_Manager":     "Yash Phoghat",
            "Benefits_Description": "Health insurance, flexible work-from-home policy, and professional development allowance of INR 10,000 per annum.",
        },
        "Contract": {
            "Client_Name":            "Ravi Constructions Pvt. Ltd.",
            "Company":                "Plot 12, MIDC, Pune - 411019",
            "Contract_Creation_Date": "10 July 2026",
            "Service_Description":    "End-to-end legal documentation services including drafting of vendor agreements, compliance advisory, and contract review for the Client's ongoing infrastructure projects.",
            "Payment_Amount":         "INR 1,50,000 (Rupees One Lakh Fifty Thousand only)",
            "Start_Date":             "15 July 2026",
            "End_Date":               "14 January 2027",
            "Payment_Schedule":       "50% advance upon execution of this Agreement; 50% upon completion of all deliverables.",
            "Termination_Clause":     "",
        },
        "MOU": {
            "PartyA_Name":  "EFFIVIA TURN2LAW LEGAL PRIVATE LIMITED",
            "PartyB_Name":  "IIT Madras Incubation Cell, Chennai",
            "Date":         "10 July 2026",
            "Purpose":      "Collaboration on legal technology research, co-development of AI-powered legal tools for startups, and joint awareness programs for student entrepreneurs.",
            "Term":         "one (1) year",
            "Jurisdiction": "Chennai, Tamil Nadu",
            "Confidentiality": "Each Party shall treat all shared research data and technical methodologies as strictly confidential.",
            "Termination_Clause": "",
            "Governing_Law": "",
        },
        "IP_Agreement": {
            "Name":         "Siddharth Nair",
            "Company":      "Freelance Software Consultant, Hyderabad",
            "Date":         "10 July 2026",
            "Term":         "the duration of the Assignor's engagement with Turn2Law and three (3) years thereafter",
            "Jurisdiction": "Chennai, Tamil Nadu",
            "IP_Description": "All code, algorithms, and technical documentation relating to the AI contract analysis engine developed under the consultancy engagement commencing July 2026.",
            "Governing_Law": "",
        },
    }

    # Generate unsigned PDF
    inputs   = SAMPLES[DOC_TYPE]
    pdf_path = generate_direct(DOC_TYPE, inputs, output_name="output")
    print(f"Document type : {DOC_TYPE}")
    print(f"Unsigned PDF  : {pdf_path}")

    # -----------------------------------------------------------------------
    # CHANGE 2: fill in your certificate path, password, and name
    # -----------------------------------------------------------------------
    CERT_PATH   = r"C:\Users\moury\Coding\Turn2Law\documentGeneration-master-1\documentGeneration-master\docgen\my_cert.pfx"
    CERT_PASS   = "123456"
    SIGNER_NAME = "Akshay Kumar"

    try:
        signed = sign_generated_pdf(
            pdf_path    = pdf_path,
            cert_path   = CERT_PATH,
            password    = CERT_PASS,
            signer_name = SIGNER_NAME,
            reason      = "Digitally approved by Turn2Law",
            location    = "Chennai, India",
            contact     = "turntwolaw@gmail.com",
            visible     = True,
        )
        print(f"Signed PDF    : {signed}")
    except Exception as e:
        print(f"Signing failed: {e}")

    # -----------------------------------------------------------------------
    # CHANGE 3 (optional): use custom branding instead of Turn2Law branding
    # Replace HEADER_PNG with your own letterhead PNG (>=595px wide, <=150px tall).
    # A test header (600x80px gold bar) is provided at docgen/test_header.png.
    # -----------------------------------------------------------------------
    HEADER_PNG    = r"C:\Users\moury\Downloads\motioncomm_header.png"
    FOOTER_PNG    = r"C:\Users\moury\Downloads\motioncomm_footer.png"
    WATERMARK_PNG = r"C:\Users\moury\Downloads\motioncomm_watermark.png"

    try:
        # Delete any cached profile so changes to assets are picked up
        import shutil as _shutil
        _profile_cache = os.path.join(_HERE, "branding", "profiles", "motioncomm")
        if os.path.exists(_profile_cache):
            _shutil.rmtree(_profile_cache)

        brand = make_custom_profile(
            profile_id           = "motioncomm",
            name                 = "MotionComm",
            header_image_path    = HEADER_PNG,
            footer_image_path    = FOOTER_PNG,
            watermark_image_path = WATERMARK_PNG,
        )
        branded_pdf = generate_with_branding(
            DOC_TYPE, inputs, brand, output_name="output_branded"
        )
        print(f"Branded PDF   : {branded_pdf}")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"Branding failed: {e}")
