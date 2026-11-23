"""Render one menu thumbnail per room GLB (web/assets/thumbs/<key with / -> __>.jpg).

  python scripts/gen_thumbs.py              # all rooms in gen_web.ROOMS
  python scripts/gen_thumbs.py Infirmerie   # just one

Drives Blender headless with scripts/render_glb.py (EEVEE, walls hidden so the card
shows the casework, not a grey box), then downscales to a 800x600 JPEG. Re-run after
re-exporting a GLB; the menu falls back to a placeholder glyph if a thumb is missing.
"""
import os, subprocess, sys, glob
from PIL import Image

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
OUTDIR = os.path.join(ROOT, "web", "assets", "thumbs")
TMP    = os.path.join(ROOT, "_tmp_thumb")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from gen_web import ROOMS

def render(key):
    glb = os.path.join(ROOT, "web", "models", *key.split("/")) + ".glb"
    if not os.path.exists(glb):
        print("!! missing", glb); return False
    for f in glob.glob(TMP + "_*.png"): os.remove(f)
    subprocess.run([BLENDER, "--background", "--factory-startup",
                    "--python", os.path.join(ROOT, "scripts", "render_glb.py"),
                    "--", glb, "_tmp_thumb", "--hidewalls"],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    src = TMP + "_a.png"
    if not os.path.exists(src): print("!! no render for", key); return False
    im = Image.open(src).convert("RGB")
    w, h = im.size                                   # 1500x1000 -> crop to 4:3
    nw = int(h * 4 / 3)
    im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h)).resize((800, 600), Image.LANCZOS)
    os.makedirs(OUTDIR, exist_ok=True)
    dst = os.path.join(OUTDIR, key.replace("/", "__") + ".jpg")
    im.save(dst, quality=82, optimize=True)
    print("wrote", os.path.relpath(dst, ROOT).replace("\\", "/"),
          f"({os.path.getsize(dst)//1024} KB)")
    for f in glob.glob(TMP + "_*.png"): os.remove(f)
    return True

if __name__ == "__main__":
    want = sys.argv[1:]
    for key, _title in ROOMS:
        if not want or key in want or key.split("/")[-1] in want:
            print("--", key); render(key)
