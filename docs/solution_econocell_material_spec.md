# Solution Econocell — material spec

Client mapping (2026-11-23). Implemented in `scripts/build_econocell.py`; the web
finish options live in `web/assets/viewer.js` (`FINISHES`).

## Laminates / finishes
| Code | Product | Tile (one texture repeat) | Source |
|------|---------|---------------------------|--------|
| L592 | Tafisa Accroche-Cœur / Kiss Curl L592(K) | 24" × 52" (grain along 52") | `materials/TAFISA_…zip` → `scripts/import_pbr.py` |
| 888  | Uniboard 888 NovaBlack / NovaNoir Eclipse | 47.04" × 96" | `materials/UNIBOARD_…zip` → `scripts/import_pbr.py` |
| WHITE | generated flat white melamine (sRGB 238/238/234) | 48" × 96" | `scripts/gen_solid_pbr.py` |
| FLOOR | generated concrete-look porcelain, 24" × 48" tiles | 2×2 tiles | `scripts/gen_tile_pbr.py --rgb 172 170 165 --grout 128 126 122 --grout-mm 4` |

## Furniture (units = one web checkbox each)
- **Reception 1** (north) and **Reception 2** (centre): L592 slatted front/ends, two
  4-drawer pedestals + centre drawer, knee space.
  - Countertops 1-5/8": **WHITE**.
  - Toe kick strips 5/8" (16 mm): **888 black**, separate node `Unit_Reception_N__toekick`
    with its own "Black toe kicks" checkbox. The 25 mm recessed pedestal toe kicks are L592.
- **Bookcase 1–4** (west wall): L592. Protruding lower 3-door cabinet — doors, shelf,
  divider, top, bottom, back, sides — **WHITE**.

## Grain
- Shelves / tops / bottoms (horizontal plates): along the UNIT's length = the shelf's width
  (Reception 1 runs E-W; Reception 2 and the bookcases run N-S), not the plate's longer side.
- Any panel longer than 60": grain along its length.
- Receptions: every vertical panel parallel to the counter's length is HORIZONTAL — the
  panel behind the slats, knee-space backs, drawer fronts, toe kicks.
- Vertical panels across the length — sides, ends, dividers (incl. Reception 1's 12"
  dividers), slats, bookcase sides/backs: VERTICAL.
- Short rails / toe kicks (< 5" tall) in any orientation: horizontal.
- Panel EDGES: grain runs along the edge, like edgeband.
- All laminate panels: ~2 mm rounded edge (2-segment bevel, hardened normals).
  Panels with >2000 faces (the CAD-grooved panels) are left as modelled.

## Geometry edits vs the FBX
- Centre lock drawer front on both receptions: +5/8" taller, extended UPWARD
  (gap to the countertop ~19 mm -> ~3 mm).
- Bookcase fillers (5 panels, 1/4" smaller than the bookcase sides, sandwiched between
  units and at both ends): exported twice, L592 and WHITE, as
  `Unit_Bookcase_N__filler_L592` / `__filler_White`; the "Bookcase fillers" radio (or
  `?filler=white`) picks one. They hide with their bookcase.

## Hardware (web radio buttons)
- Pulls + cam locks → material `Hardware_Metal`: **Black** (default) / **Silver**.
- Bookcase shoe rails + posts → material `Rail_Metal`: **Chrome** (default) / Matte Black /
  Matte Nickel / Satin Brass.
- Hinges, slides, strikes, catches (inside the cabinets) → fixed grey metal.
- Deep link: `rooms/solution_econocell.html?hw=silver&rail=satin-brass&filler=white`.

## Room shell (finished, not as-photographed — `raw_pngs/` shows construction)
- Walls + trims: warm off-white paint (deliberately darker/warmer than cabinet WHITE).
- Floor: large-format tile slab under the whole footprint (`Floor` node).
- Storefront (south + east): black anodised aluminium, mullion grid (verticals ~1.1 m,
  transoms at 0.65/1.35/2.05 m), glass alpha-blended. The two door leaves (solid boxes in
  the FBX) are rebuilt as narrow-stile black frames with glass; door pulls black.
  Each wall's glazing is joined INTO that wall, so hiding a wall hides its storefront.
