"""Measure exact watermark visibility in sample.pdf vs output.pdf"""
import fitz
from PIL import Image, ImageStat, ImageEnhance

def render_page(path, dpi=300):
    doc = fitz.open(path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img

ref = render_page("sample.pdf", 300)
gen = render_page("output.pdf", 300)

W_ref, H_ref = ref.size
W_gen, H_gen = gen.size
print(f"REF render: {W_ref}x{H_ref}")
print(f"GEN render: {W_gen}x{H_gen}")

# The N watermark in reference is in the right-center area
# At 300dpi, 1pt = 300/72 = 4.167px
# Reference N area approx: x0=95pt, y0=250pt, w=267pt, h=338pt
# In pixels at 300dpi: x0=395, y0=1042, w=1113, h=1409
scale = 300/72

def crop_region(img, x0_pt, y0_pt, w_pt, h_pt):
    x0 = int(x0_pt * scale)
    y0 = int(y0_pt * scale)
    x1 = min(int((x0_pt + w_pt) * scale), img.width)
    y1 = min(int((y0_pt + h_pt) * scale), img.height)
    return img.crop((x0, y0, x1, y1))

# Sample the N watermark region in both
ref_region = crop_region(ref, 95, 250, 267, 338)
gen_region  = crop_region(gen, 95, 250, 267, 338)

ref_stat = ImageStat.Stat(ref_region.convert("L"))
gen_stat = ImageStat.Stat(gen_region.convert("L"))
print(f"\nN watermark region (95,250,267,338pt):")
print(f"  REF: mean={ref_stat.mean[0]:.2f}  stddev={ref_stat.stddev[0]:.2f}")
print(f"  GEN: mean={gen_stat.mean[0]:.2f}  stddev={gen_stat.stddev[0]:.2f}")

# Save the regions boosted 10x to see what's there
ref_boosted = ImageEnhance.Contrast(ref_region).enhance(10)
gen_boosted = ImageEnhance.Contrast(gen_region).enhance(10)
ref_boosted.save("ref_wm_region.png")
gen_boosted.save("gen_wm_region.png")
print("\nSaved ref_wm_region.png and gen_wm_region.png (10x contrast boost)")

# Also check a wider region in the reference
ref_wide = crop_region(ref, 80, 240, 360, 380)
ref_wide_stat = ImageStat.Stat(ref_wide.convert("L"))
print(f"\nWider N region REF (80,240 to 440,620):")
print(f"  mean={ref_wide_stat.mean[0]:.2f}  stddev={ref_wide_stat.stddev[0]:.2f}  min/max={ref_wide.convert('L').getextrema()}")
