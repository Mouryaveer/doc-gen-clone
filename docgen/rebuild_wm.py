"""
rebuild_wm.py — Creates watermark_logo_n.png with correct opacity.

Reference measurements:
  - N stroke at (105, 290): pixel value 165 on white (255) background
  - Effective opacity = (255-165)/255 = 35%
  - The N fades from top (35% opacity) to bottom (0%)
  - The fade is produced by the watermark_bg.jpeg blending, but we can
    replicate it with a gradient alpha mask.

Approach:
  1. Crop N symbol from logo (left 21%, 0-270px)
  2. Apply alpha = stroke_darkness * opacity_factor
  3. Use opacity_factor = 0.35 at top, fading to 0 at bottom
"""
from PIL import Image

logo = Image.open("images/sample_asset_0_xref_36.jpeg").convert("RGBA")
w, h = logo.size

# Crop N symbol only (left 270px to avoid the T in TURN2LAW)
n = logo.crop((0, 0, 270, h)).convert("RGBA")
nw, nh = n.size
print(f"N crop: {nw}x{nh}")

pixels = n.load()
for y in range(nh):
    # Vertical gradient: full opacity at top, fade to 0 at bottom
    # Reference shows N visible from y~=250pt to ~=420pt (170pt range)
    # The logo is placed at 338pt tall, so roughly top 50% is visible
    # Use linear fade: 1.0 at y=0, 0.0 at y=nh*0.75
    fade = max(0.0, 1.0 - (y / (nh * 0.75)))
    max_opacity = 0.35 * fade   # 35% at top, 0% at bottom

    for x in range(nw):
        r, g, b, a = pixels[x, y]
        brightness = (r * 299 + g * 587 + b * 114) // 1000
        # Dark pixels = N strokes
        stroke_strength = 1.0 - brightness / 255.0
        alpha = int(stroke_strength * max_opacity * 255)
        if alpha > 0:
            pixels[x, y] = (42, 42, 42, alpha)
        else:
            pixels[x, y] = (0, 0, 0, 0)

n.save("images/watermark_logo_n.png")
print("Saved images/watermark_logo_n.png")

# Verify
from PIL import ImageStat
alpha_ch = n.split()[3]
print(f"Alpha range: {alpha_ch.getextrema()}")
print(f"Alpha mean: {round(ImageStat.Stat(alpha_ch).mean[0], 1)}")
