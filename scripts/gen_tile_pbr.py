"""
Generate web PBR maps for a large-format FLOOR TILE (concrete-look porcelain).

  python scripts/gen_tile_pbr.py FLOOR --tile 0.6096 1.2192 --cols 2 --rows 2

One texture covers cols x rows tiles (default 2x2 of 24"x48" = 1.2192 x 2.4384 m), each
tile with its own slight tone shift so the repeat does not read as a grid of clones.
build_econocell.py must use the same physical size (TILE['FLOOR']).
Outputs textures/<name>_{basecolor.jpg,roughness.png,normal.png}; all tile seamlessly.
"""
import argparse, os, numpy as np
from PIL import Image

def periodic_noise(h, w, lo, hi, rng):
    fy = np.fft.fftfreq(h)[:, None] * h * (w / h)
    fx = np.fft.fftfreq(w)[None, :] * w
    f = np.sqrt(fx * fx + fy * fy)
    spec = (rng.standard_normal((h, w)) + 1j * rng.standard_normal((h, w))) * ((f >= lo) & (f <= hi))
    n = np.real(np.fft.ifft2(spec)); return n / (np.abs(n).max() + 1e-9)

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--tile", type=float, nargs=2, default=[0.6096, 1.2192], help="tile W H in metres")
ap.add_argument("--cols", type=int, default=2); ap.add_argument("--rows", type=int, default=2)
ap.add_argument("--rgb", type=int, nargs=3, default=[196, 194, 189], help="sRGB tile colour")
ap.add_argument("--grout", type=int, nargs=3, default=[168, 166, 160])
ap.add_argument("--grout-mm", type=float, default=3.0)
ap.add_argument("--width", type=int, default=1024)
ap.add_argument("--outdir", default="textures")
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args(); os.makedirs(a.outdir, exist_ok=True)
rng = np.random.default_rng(a.seed)
W_m, H_m = a.tile[0] * a.cols, a.tile[1] * a.rows
w = a.width; h = round(w * H_m / W_m); ppm = w / W_m

# per-tile index map + grout mask (grout straddles tile edges, so the texture wraps cleanly)
yy, xx = np.mgrid[0:h, 0:w]
tx = (xx / ppm) / a.tile[0]; ty = (yy / ppm) / a.tile[1]
ci = np.floor(tx).astype(int) % a.cols; ri = np.floor(ty).astype(int) % a.rows
g = a.grout_mm / 1000 / 2
dx = np.minimum(tx % 1, 1 - tx % 1) * a.tile[0]; dy = np.minimum(ty % 1, 1 - ty % 1) * a.tile[1]
edge = np.minimum(dx, dy)                         # metres to nearest tile edge
grout = np.clip((g + 0.0006 - edge) / 0.0012, 0, 1)   # soft 1.2 mm transition

# colour: tile tone shift + cloudy concrete mottle + fine speckle
shift = rng.normal(0, 3.0, (a.rows, a.cols))[ri, ci]
cloud = periodic_noise(h, w, 2, 14, rng) * 7 + periodic_noise(h, w, 14, 80, rng) * 3
speck = periodic_noise(h, w, 150, 400, rng) * 2.5
tile = np.array(a.rgb, float)[None, None] + (shift + cloud + speck)[..., None]
base = tile * (1 - grout[..., None]) + np.array(a.grout, float)[None, None] * grout[..., None]
Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").save(
    os.path.join(a.outdir, f"{a.name}_basecolor.jpg"), quality=90)

# roughness: honed tile ~0.38 with a little cloudiness, grout matte
rough = 0.38 + periodic_noise(h, w, 4, 40, rng) * 0.05
rough = rough * (1 - grout) + 0.85 * grout
aw = w // 2; ah = h // 2
Image.fromarray((np.clip(rough, 0, 1) * 255).astype(np.uint8), "L").resize((aw, ah), Image.LANCZOS).save(
    os.path.join(a.outdir, f"{a.name}_roughness.png"))

# normal: grout recessed (height 0 in grout, 1 on tile) + faint surface texture
H = (1 - grout) * 1.0 + periodic_noise(h, w, 60, 250, rng) * 0.02
gy = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) * 0.5; gx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) * 0.5
s = 2.0; nx, ny, nz = -gx * s, gy * s, np.ones_like(H)
L = np.sqrt(nx * nx + ny * ny + nz * nz)
nrm = np.stack([nx / L, ny / L, nz / L], -1) * 0.5 + 0.5
Image.fromarray((nrm * 255).astype(np.uint8), "RGB").resize((aw, ah), Image.LANCZOS).save(
    os.path.join(a.outdir, f"{a.name}_normal.png"))
print(f"{a.name}: {a.cols}x{a.rows} tiles of {a.tile} m -> {w}x{h}px covering {W_m:.4f} x {H_m:.4f} m")
