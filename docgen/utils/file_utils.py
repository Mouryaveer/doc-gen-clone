from extractors.pdf_extractor import extract_pdf_text
from extractors.docx_extractor import extract_docx_text
from extractors.image_extractor import extract_image_text

def extract_text(path):
    if path.endswith(".pdf"):
        return extract_pdf_text(path)
    elif path.endswith(".docx"):
        return extract_docx_text(path)
    elif path.endswith((".png", ".jpg", ".jpeg")):
        return extract_image_text(path)
    else:
        raise ValueError("Unsupported file type")
