from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def save_text_as_pdf(text, output_path):
    doc = SimpleDocTemplate(output_path)
    styles = getSampleStyleSheet()
    elements = []

    for line in text.split("\n"):
        if line.strip() == "":
            elements.append(Spacer(1, 10))
        else:
            elements.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                                      styles["Normal"]))

    doc.build(elements)
