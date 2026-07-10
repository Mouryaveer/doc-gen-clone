"""
app.py — Turn2Law document generation system.

Workflow:
  1. Extract text from input document (PDF / DOCX / image).
  2. Classify document type using Google Gemini.
  3. Validate user-supplied fields against the document schema.
  4. Render the appropriate LaTeX template and compile to PDF.
"""

import os

from utils.file_utils import extract_text
from classifier.classify import classify_document
from schema import DOCUMENT_SCHEMAS
from utils.latex_writer import render_latex

_HERE = os.path.dirname(os.path.abspath(__file__))

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


def validate_inputs(doc_type: str, user_inputs: dict) -> None:
    schema = DOCUMENT_SCHEMAS.get(doc_type)
    if not schema:
        raise ValueError(f"Unsupported document type: {doc_type}")
    missing = [
        f for f in schema["required"]
        if f not in user_inputs or not user_inputs[f]
    ]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


def generate_document(
    file_path: str,
    user_inputs: dict,
    output_name: str = "output",
) -> tuple[str, str]:
    """
    Generate a PDF from *file_path* populated with *user_inputs*.

    Parameters
    ----------
    file_path   : path to the input reference document
    user_inputs : dict of field values matching the document schema
    output_name : base name for the output files (default "output")

    Returns
    -------
    (doc_type, pdf_path)
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


def generate_direct(doc_type: str, user_inputs: dict, output_name: str = "output") -> str:
    """
    Generate a PDF directly by doc_type — skips Gemini classification.
    Useful for API / web integration where the document type is already known.

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


# =============================================================================
#  Quick-run entry point — edit DOC_TYPE and user_inputs to test any template
# =============================================================================
if __name__ == "__main__":

    DOC_TYPE = "MOU"   # change to test other templates

    SAMPLES = {
        "Onboarding_Letter": {
            "Employee_Name": "Vikas Reddy",
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

    inputs = SAMPLES[DOC_TYPE]
    pdf_path = generate_direct(DOC_TYPE, inputs, output_name="output")
    print(f"Document type : {DOC_TYPE}")
    print(f"Saved as      : {pdf_path}")
