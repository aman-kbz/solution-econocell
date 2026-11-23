# Solution Econocell

Interactive 3D web viewer for a **single Econocell room**. Same pipeline as the sister
project `../ECP_Offices_2026` (reference implementation — read its CLAUDE.md and the
skill below before changing anything): BricsCAD FBX → Blender (PBR laminates, segment,
grain, handle swap, recenter) → editable `.blend` → human phase-2 check → Draco GLB →
static `<model-viewer>` site with per-wall toggles.

## The room — `solution_econocell`
`fbx/solution_econocell.fbx` (2,243 meshes, tiny vs ECP) → `blend_files/solution_econocell.blend`
→ `web/models/solution_econocell.glb` (~4.5 MB) → `web/rooms/solution_econocell.html`.
Spec: `docs/solution_econocell_material_spec.md`.

**This room uses its own builder, `scripts/build_econocell.py`, not `build_scene.py`.**
In this export `Material0` is the WALLS (roomlib assumes Material0 = glass), and the
furniture (2 slatted receptions, 4 bookcases) isn't drawer casework, so classification
is explicit by geometry + position in the recentred room. `build_scene.py`/`roomlib.py`
are kept from the skill for reference only.

## Pipeline
```
python scripts/import_pbr.py "materials/_x/TAFISA_…L592(K)" L592          # client PBR → textures/
python scripts/import_pbr.py "materials/_x/UNIBOARD_…ECLIPSE" 888 --width 512 --aux-width 256
python scripts/gen_solid_pbr.py WHITE --rgb 238 238 234
python scripts/gen_tile_pbr.py FLOOR --rgb 172 170 165 --grout 128 126 122 --grout-mm 4
blender --background --factory-startup --python scripts/build_econocell.py -- fbx/solution_econocell.fbx blend_files/solution_econocell.blend
#   phase 2: hand-edit the .blend in Blender 4.5 (do NOT re-run the build after editing)
blender --background --factory-startup --python scripts/export_glb.py -- blend_files/solution_econocell.blend web/models/solution_econocell.glb
python scripts/gen_web.py && python scripts/gen_thumbs.py
```

## Web contract (build_econocell.py ↔ viewer.js)
- `Wall_*` nodes → per-wall checkboxes + auto-hide (storefront glazing is inside its wall).
- `Unit_<Name>` → one Furniture checkbox each; `Unit_<Name>__toekick` follows its unit AND
  the "Black toe kicks" checkbox.
- `Unit_<Name>__filler_L592` / `__filler_White`: bookcase fillers in both finishes; the
  "Bookcase fillers" radio shows one (`?filler=white`). Both overlap in the .blend — expected.
- Materials `Hardware_Metal` and `Rail_Metal` are re-tinted by name (radio buttons,
  `?hw=` / `?rail=` deep links). Renaming either breaks the finish switcher.
- Glass is alpha-BLEND, not transmission (transmission renders milky-white in model-viewer).

## Lessons from this room
- Panel edges: per-face UVs. Main faces use the panel grain frame; edge faces run grain
  along the edge. A single planar projection smears the texture across the thickness.
- Edgeband look: Bevel modifier 1.5 mm × 2 segments, angle-limited, `harden_normals`,
  applied before UVs; skip panels >2000 faces (CAD-grooved ones).
- Floor/wall albedo must be noticeably darker than it looks in a swatch: model-viewer's
  neutral environment + exposure 1.1 washes light greys to white.

## Tooling
- Blender **4.5 LTS** headless: `"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --background --factory-startup --python scripts/<x>.py -- <args>`
- Python + Pillow + numpy for texture work.

## Conventions
- Never hand-edit GLBs, `web/rooms/*.html` or `web/assets/rooms.js` (generated).
- Raw FBX, source material images and `blend_files/` are gitignored (local only).
- Full pitfall list (segmentation, grain, UV layers, web toggles, hosting):
  `.claude/skills/fbx-room-pipeline/SKILL.md`.
