"""
app.py — Main entry point for the Turn2Law document generation system.

Workflow:
  1. Extract text from the input document (PDF / DOCX / image).
  2. Classify the document type using Google Gemini.
  3. Validate user-supplied fields against the document schema.
  4. Render the appropriate LaTeX template and compile to PDF.
"""

import os

from utils.file_utils import extract_text
from classifier.classify import classify_document
from schema import DOCUMENT_SCHEMAS
from utils.latex_writer import render_latex

# Absolute path to the docgen/ directory so all relative paths resolve
# correctly regardless of where Python is invoked from.
_HERE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_MAP = {
    "Onboarding_Letter": os.path.join(_HERE, "templates", "onboarding_template.tex"),
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


def generate_document(file_path: str, user_inputs: dict) -> tuple[str, str]:
    """
    Generate a document PDF from *file_path* populated with *user_inputs*.

    Returns
    -------
    (doc_type, pdf_path) : tuple[str, str]
    """
    # Make file_path absolute relative to docgen/ if it is not already
    if not os.path.isabs(file_path):
        file_path = os.path.join(_HERE, file_path)

    extracted_text = extract_text(file_path)
    doc_type = classify_document(extracted_text)
    validate_inputs(doc_type, user_inputs)

    template_path = TEMPLATE_MAP.get(doc_type)
    if not template_path:
        raise ValueError(f"No template found for document type: {doc_type}")

    # Output files live in docgen/ (next to app.py)
    output_tex = os.path.join(_HERE, "output.tex")
    output_pdf = os.path.join(_HERE, "output.pdf")

    render_latex(template_path, output_tex, output_pdf, user_inputs)

    return doc_type, output_pdf


# =============================================================================
#  Quick-run entry point
# =============================================================================
if __name__ == "__main__":
    user_inputs = {
        "Employee_Name": "Rahul Verma",
        "Emp_ID":        "T2L-AI-041",
        "Role":          "Software Engineer Intern",
        "Joining_Date":  "1 July 2026",
        "Document_Date": "10 June 2026",
    }

    doc_type, pdf_path = generate_document("sample.pdf", user_inputs)
    print("Detected :", doc_type)
    print("Saved as :", pdf_path)
