"""Composite the transparent studio renders onto a seamless backdrop.
  python scripts/finish_renders.py renders
Images with an alpha channel (product shots + cutaways, rendered with a shadow-catcher
floor) get a soft warm-grey backdrop with a faint top-to-bottom gradient; opaque
interior renders are left alone."""
import sys, glob, os, numpy as np
from PIL import Image
d = sys.argv[1]
for f in sorted(glob.glob(os.path.join(d, "*.png"))):
    im = Image.open(f)
    if im.mode != "RGBA": continue
    w, h = im.size
    t = np.linspace(0, 1, h)[:, None, None]
    top, bot = np.array([238, 236, 232]), np.array([226, 224, 219])
    bg = (top * (1 - t) + bot * t) * np.ones((1, w, 1))
    bgim = Image.fromarray(bg.astype(np.uint8), "RGB").convert("RGBA")
    bgim.alpha_composite(im)
    bgim.convert("RGB").save(f, optimize=True)
    print("finished", os.path.basename(f))
