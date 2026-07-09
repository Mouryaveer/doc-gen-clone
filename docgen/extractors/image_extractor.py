import pytesseract
from PIL import Image

def extract_image_text(path):
    return pytesseract.image_to_string(Image.open(path))
