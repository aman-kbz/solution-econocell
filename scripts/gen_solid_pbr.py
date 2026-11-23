"""
Generate web PBR maps for a SOLID-colour (no grain) laminate, e.g. the white
melamine we have no client scan for. Output matches gen_pbr.py's naming, so
build_scene.py's laminate() picks it up like any scanned laminate.

Usage:
  python scripts/gen_solid_pbr.py WHITE --rgb 238 238 234
  python scripts/gen_solid_pbr.py WHITE --rgb 240 240 236 --rough 0.55 --stipple 0.35

Outputs (in outdir), 1:2 aspect like a 48x96 sheet (TILE_U/V in build_scene):
  <name>_basecolor.jpg   flat sRGB colour + faint low-frequency mottling
  <name>_roughness.png   satin band + micro variation
  <name>_normal.png      very fine stipple (melamine "softex"-style texture)
All maps tile seamlessly (noise is built in the frequency domain, so it is periodic).
"""
import argparse, os, numpy as np
from PIL import Image

def periodic_noise(h, w, lo, hi, rng):
    """Tileable band-pass noise, normalised to [-1, 1]. lo/hi = cycles per image width."""
    fy = np.fft.fftfreq(h)[:, None] * h * (w / h)   # same cycles/width scale on both axes
    fx = np.fft.fftfreq(w)[None, :] * w
    f = np.sqrt(fx * fx + fy * fy)
    mask = (f >= lo) & (f <= hi)
    spec = (rng.standard_normal((h, w)) + 1j * rng.standard_normal((h, w))) * mask
    n = np.real(np.fft.ifft2(spec))
    return n / (np.abs(n).max() + 1e-9)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--rgb", type=int, nargs=3, default=[238, 238, 234], help="sRGB 0-255")
    ap.add_argument("--outdir", default="textures")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--aux-width", type=int, default=512)
    ap.add_argument("--mottle", type=float, default=2.0, help="base colour variation, in 0-255 levels")
    ap.add_argument("--rough", type=float, default=0.55)
    ap.add_argument("--rough-var", type=float, default=0.04)
    ap.add_argument("--stipple", type=float, default=0.35, help="normal-map strength")
    ap.add_argument("--seed", type=int, default=592)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    w, h = a.width, a.width * 2

    # base colour: flat + barely-there mottling so large panels don't read as CG-flat
    mot = periodic_noise(h, w, 2, 12, rng)
    base = np.clip(np.array(a.rgb, np.float32)[None, None, :] + mot[..., None] * a.mottle, 0, 255)
    Image.fromarray(base.astype(np.uint8), "RGB").save(
        os.path.join(a.outdir, f"{a.name}_basecolor.jpg"), quality=92)

    aw, ah = a.aux_width, a.aux_width * 2
    # roughness
    rn = periodic_noise(ah, aw, 4, 60, rng)
    rough = np.clip(a.rough + rn * a.rough_var, 0, 1)
    Image.fromarray((rough * 255).astype(np.uint8), "L").save(
        os.path.join(a.outdir, f"{a.name}_roughness.png"))

    # normal: fine stipple height field -> tangent-space normal (OpenGL / glTF +Y up)
    H = periodic_noise(ah, aw, 60, 220, rng)
    gy = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) * 0.5     # wrap-around gradient keeps it tileable
    gx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) * 0.5
    nx, ny, nz = -gx * a.stipple, gy * a.stipple, np.ones_like(H)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    nrm = np.stack([nx / L, ny / L, nz / L], -1) * 0.5 + 0.5
    Image.fromarray((nrm * 255).astype(np.uint8), "RGB").save(
        os.path.join(a.outdir, f"{a.name}_normal.png"))

    print(f"{a.name}: rgb {a.rgb} -> base {w}x{h}, aux {aw}x{ah}")
    for suf in ("basecolor.jpg", "roughness.png", "normal.png"):
        p = os.path.join(a.outdir, f"{a.name}_{suf}")
        print(f"  {os.path.getsize(p)//1024:6d} KB  {p}")

if __name__ == "__main__":
    main()
