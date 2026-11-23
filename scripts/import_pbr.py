"""
Normalise a manufacturer PBR pack (e.g. the Tafisa / Uniboard EEVEE downloads) into
the pipeline's naming: textures/<CODE>_{basecolor.jpg,roughness.png,normal.png}.

  python scripts/import_pbr.py <pack_dir> <CODE> [--width 1024] [--aux-width 512]

The pack's own *Displacement* map is skipped (glTF / model-viewer cannot use it).
Normal maps from these packs are authored for Blender = OpenGL (+Y up) = what glTF
expects, so they are only resized, never flipped. Physical tile size comes from the
pack's 'Product metadata.txt' and must be mirrored in build_econocell.py's TILE table.
"""
import argparse, glob, os
from PIL import Image

def find(d, key):
    hits = [p for p in glob.glob(os.path.join(d, "*")) if key.lower() in os.path.basename(p).lower()]
    if not hits: raise SystemExit(f"no *{key}* map in {d}")
    return hits[0]

ap = argparse.ArgumentParser()
ap.add_argument("pack"); ap.add_argument("code")
ap.add_argument("--outdir", default="textures")
ap.add_argument("--width", type=int, default=1024)
ap.add_argument("--aux-width", type=int, default=512)
a = ap.parse_args(); os.makedirs(a.outdir, exist_ok=True)

def fit(im, w): return im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)
fit(Image.open(find(a.pack, "Base_Color")).convert("RGB"), a.width).save(
    os.path.join(a.outdir, f"{a.code}_basecolor.jpg"), quality=90)
fit(Image.open(find(a.pack, "Roughness")).convert("L"), a.aux_width).save(
    os.path.join(a.outdir, f"{a.code}_roughness.png"))
fit(Image.open(find(a.pack, "Normal")).convert("RGB"), a.aux_width).save(
    os.path.join(a.outdir, f"{a.code}_normal.png"))
for s in ("basecolor.jpg", "roughness.png", "normal.png"):
    p = os.path.join(a.outdir, f"{a.code}_{s}")
    im = Image.open(p); print(f"{p}: {im.size} {os.path.getsize(p)//1024} KB")
