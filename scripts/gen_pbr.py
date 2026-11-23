"""
Generate web-ready PBR maps (base color, roughness, normal) from a flat-lit
Uniboard laminate photo.

Usage:
  python scripts/gen_pbr.py <input.png> <name> [--outdir textures]
                            [--width 1024] [--normal-strength 1.0]
                            [--rough-base 0.52] [--rough-var 0.12]

Outputs (in outdir):
  <name>_basecolor.jpg     sRGB albedo, downscaled
  <name>_roughness.png     grayscale, satin melamine band + grain micro-variation
  <name>_normal.png        tangent-space normal (OpenGL / glTF +Y-up), from grain
"""
import argparse, os, numpy as np
from PIL import Image, ImageFilter

def load_rgb(path):
    return Image.open(path).convert("RGB")

def luminance(arr):
    # arr float [0,1] HxWx3
    return arr[..., 0]*0.299 + arr[..., 1]*0.587 + arr[..., 2]*0.114

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("name")
    ap.add_argument("--outdir", default="textures")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--aux-width", type=int, default=0, help="downscale roughness/normal to this width (0=same as base)")
    ap.add_argument("--normal-strength", type=float, default=1.0)
    ap.add_argument("--rough-base", type=float, default=0.52)
    ap.add_argument("--rough-var", type=float, default=0.12)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    src = load_rgb(a.input)
    w0, h0 = src.size
    h = round(a.width * h0 / w0)
    base = src.resize((a.width, h), Image.LANCZOS)
    base_arr = np.asarray(base, np.float32) / 255.0

    # ---- base color ----
    bc_path = os.path.join(a.outdir, f"{a.name}_basecolor.jpg")
    base.save(bc_path, quality=92)

    lum = luminance(base_arr)  # [0,1]

    # ---- roughness: satin band, darker grain -> slightly rougher ----
    lmin, lmax = np.percentile(lum, 2), np.percentile(lum, 98)
    ln = np.clip((lum - lmin) / max(1e-6, (lmax - lmin)), 0, 1)
    rough = a.rough_base + (1.0 - ln) * a.rough_var          # darker => rougher
    rough = np.clip(rough, 0, 1)
    rough_img = Image.fromarray((rough * 255).astype(np.uint8), "L")
    aux_w = a.aux_width or a.width
    if aux_w < a.width:
        rough_img = rough_img.resize((aux_w, round(aux_w*h/a.width)), Image.LANCZOS)
    rough_img.save(os.path.join(a.outdir, f"{a.name}_roughness.png"))

    # ---- normal map from grain height (height = luminance) ----
    # denoise a touch so photo grain doesn't become high-freq noise
    height_img = Image.fromarray((lum * 255).astype(np.uint8), "L").filter(
        ImageFilter.GaussianBlur(0.6))
    H = np.asarray(height_img, np.float32) / 255.0
    # gradients; scale by strength. dark grooves are lower -> invert so grooves recess
    gy, gx = np.gradient(H)
    s = a.normal_strength * 4.0
    nx = -gx * s
    ny = -gy * s
    nz = np.ones_like(H)
    length = np.sqrt(nx*nx + ny*ny + nz*nz)
    nx, ny, nz = nx/length, ny/length, nz/length
    # OpenGL / glTF convention: +X right, +Y up, +Z out
    normal = np.stack([(nx*0.5+0.5), (ny*0.5+0.5), (nz*0.5+0.5)], axis=-1)
    normal_img = Image.fromarray((normal*255).astype(np.uint8), "RGB")
    if aux_w < a.width:
        normal_img = normal_img.resize((aux_w, round(aux_w*h/a.width)), Image.LANCZOS)
    normal_img.save(os.path.join(a.outdir, f"{a.name}_normal.png"))

    print(f"{a.name}: src {w0}x{h0} -> maps {a.width}x{h}")
    for suf in ("basecolor.jpg", "roughness.png", "normal.png"):
        p = os.path.join(a.outdir, f"{a.name}_{suf}")
        print(f"  {os.path.getsize(p)//1024:6d} KB  {p}")

if __name__ == "__main__":
    main()
