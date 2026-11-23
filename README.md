# Solution Econocell

Interactive 3D viewer for one Econocell room: BricsCAD FBX → Blender (PBR materials) →
GLB → static `<model-viewer>` site with per-wall show/hide toggles.

## Status
| Step | State |
|------|-------|
| Scaffold, textures (L592, 888, WHITE, FLOOR) | done |
| Build `blend_files/solution_econocell.blend` | done — ready for phase-2 visual check |
| GLB `web/models/solution_econocell.glb` (~4.5 MB) | exported from the fresh build |
| Web viewer: wall toggles, per-unit furniture toggles, toe-kick toggle, hardware + rail finishes | done, tested in headless Chrome |

## Materials
See `docs/solution_econocell_material_spec.md` — L592 (most furniture), 888 black
(5/8" reception toe kicks), WHITE (countertops, bookcase lower cabinets), FLOOR tile.

## Commands
```
python scripts/gen_solid_pbr.py WHITE --rgb 238 238 234
"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --background --factory-startup \
    --python scripts/build_econocell.py -- fbx/solution_econocell.fbx blend_files/solution_econocell.blend
"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --background --factory-startup \
    --python scripts/export_glb.py -- blend_files/solution_econocell.blend web/models/solution_econocell.glb
python scripts/gen_web.py && python scripts/gen_thumbs.py
python -m http.server 8787 -d web
```
Hosting: static, no build step — Cloudflare Pages / Netlify / Render configs included
(see `../ECP_Offices_2026/README.md` for the host comparison).
