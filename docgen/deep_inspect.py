"""Deep inspect: measure actual pixel darkness of N strokes in reference"""
import fitz
from PIL import Image, ImageStat

def render_page(path, dpi=300):
    doc = fitz.open(path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img

ref = render_page("sample.pdf", 300)
scale = 300/72

# Sample specific spots in the reference where the N strokes should be:
# N left vertical stroke: x~=100-120pt, y~=270-560pt
# N diagonal: x~=130-200pt, y~=280-520pt
# N right vertical: x~=200-220pt, y~=270-560pt

def sample_point(img, x_pt, y_pt, radius_pt=5):
    x = int(x_pt * scale)
    y = int(y_pt * scale)
    r = int(radius_pt * scale)
    crop = img.crop((max(0,x-r), max(0,y-r), x+r, y+r))
    return round(ImageStat.Stat(crop.convert("L")).mean[0], 1)

print("Sampling reference PDF at N stroke locations:")
print(f"  Left stroke top    (105, 290): {sample_point(ref, 105, 290)}")
print(f"  Left stroke mid    (105, 400): {sample_point(ref, 105, 400)}")
print(f"  Left stroke bot    (105, 530): {sample_point(ref, 105, 530)}")
print(f"  Diagonal mid       (160, 390): {sample_point(ref, 160, 390)}")
print(f"  Right stroke top   (215, 290): {sample_point(ref, 215, 290)}")
print(f"  Right stroke bot   (215, 530): {sample_point(ref, 215, 530)}")
print(f"  White area (clear) (300, 200): {sample_point(ref, 300, 200)}")
print(f"  White area (clear) (400, 150): {sample_point(ref, 400, 150)}")
print()

# Render just the watermark xref=36 region at low scale to understand its opacity
doc = fitz.open("sample.pdf")
page = doc[0]
# Check PDF graphics state opacity for the large logo placement
annots = list(page.annots())
print(f"Annotations: {len(annots)}")

# Check xobject transparency via direct PDF inspection
# Look at the extended graphics state
raw_page = doc.xref_stream(page.xref)
if raw_page:
    content = raw_page.decode("latin-1", errors="replace")
    # Find any 'gs' (graphics state) or 'ca'/'CA' (opacity) operators near the image
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if any(kw in line for kw in ["gs", "/ca", "/CA", "Do", "BDC", "BMC"]):
            ctx = lines[max(0,i-2):i+3]
            print(f"  Line {i}: {line!r}  context: {ctx}")
doc.close()
