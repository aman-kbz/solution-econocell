---
name: fbx-room-pipeline
description: >
  Scaffold and run the BricsCAD-FBX → Blender → GLB → web pipeline for a new
  client room/furniture project. Use when the user starts a new project that takes
  CAD-exported FBX room(s), applies real laminate/PBR materials in Blender, does a
  human visual-check pass, then exports GLB for a GitHub-Pages <model-viewer> site.
  Triggers: "new room project", "fbx to glb", "bricscad export", "apply materials to
  the cabinets", "3D room viewer for client", "laminate/finish + fbx". Handles full
  rooms and cabinet-only exports. Covers the whole path: scaffold → materials →
  phase-2 handoff → GLB export → generated web viewer with per-wall toggles.
---

# FBX Room Pipeline

Turns raw BricsCAD FBX room exports into an interactive web viewer. Reference
implementation: the `ECP_Offices_2026` project this skill was extracted from.

**Pipeline:** FBX (per room) → generate PBR maps → `build_scene` (segment + material
+ grain + handles + recenter → editable `.blend`) → **human visual check (phase 2)** →
`export_glb` → web `<model-viewer>` site with per-wall toggles.

The reusable engine is in this skill's `scripts/` folder. Step 1 copies it into the
new project. Do NOT rewrite these from scratch — they encode the lessons below.

---

## READ FIRST — hard-won lessons (do not re-learn these)

These are real dead-ends hit while building the reference project. Honor them.

1. **BricsCAD FBX names & materials are JUNK.** Every mesh is `Entity_<hex>`; there's
   usually one gray default material on ~99% of objects. **Never segment by name or
   material.** Segment by **geometry + hierarchy** (`roomlib.py`).

2. **Segment by parenting + geometry:**
   - *Unparented* meshes = the room shell + casework (walls, cabinets, doors, windows).
   - *Parented* meshes = hardware — BUT split them: name-match locks/pulls/knobs/
     castors/slides = droppable hardware; everything else parented (e.g. `A$C...`
     empties) = **furniture components like LEGS that must stay visible**. The naive
     "parented = hardware, hide it" rule wrongly hid the desk legs.
   - Fallback: if there are NO unparented meshes, treat all meshes as shell.

3. **Walls vs doors vs TALL CABINETS — three-way, and thickness is the key.** The naive
   rule "tall + thin + reaches the ceiling = WALL, else DOOR" silently eats tall cabinet
   carcasses, and the damage is invisible until the client opens the .blend:
   - In a **cabinet-only file** the room height IS the cabinet height, so a 2 m cabinet
     side passes `dz > 0.9 * room_height` and becomes a *wall*.
   - In a full room, a 1.8 m cabinet side is tall+thin but short of the ceiling, so it
     becomes a *door* — and then its shelves and top, orphaned from the cluster, fall
     into the leftover bucket and get `fast_merge`d into the `DoorFrames` blob. The
     client cannot separate them again; only a rebuild fixes it.

   Fix (both live in `roomlib.py`):
   - **Thickness gate on walls.** Real walls are ≥100 mm (0.152 m in these exports);
     laminate panels are 16–25 mm and door leaves/jambs 15–45 mm. Require
     `min(dx,dy) >= 0.06` *as well as* full height. Thickness separates walls from panels
     cleanly — nothing else does.
   - **`_absorb_panels()` for the door/cabinet ambiguity.** Thickness can NOT separate a
     cabinet side (25 mm) from a door jamb (25 mm), so decide by attachment: pull a
     'door' back into casework when it is a *face* of a cabinet-sized body (touching on
     all 3 axes, covering ≥50% of the shared span on both long axes). Iterate to a fixed
     point so a back panel reachable only through an already-absorbed side is caught.
   - **Anchor on cabinet-sized bodies, not on any casework.** A door's own head transom
     is short, so it classifies as casework; anchoring on "touches casework" absorbs
     every jamb that touches its own transom and turns whole doorways into cabinets.
     Seed only from clusters with `min(size) > 0.12 and size[2] > 0.25`.

   Keep each wall a SEPARATE named node — the website toggles them individually.
   Verify with a dry run that prints per-category dims + the leftover→DoorFrames list
   **on every room** before rebuilding any of them; the same edit fixes one room and can
   wreck another.

4. **GRAIN DIRECTION — the biggest trap.** Derive a panel's plate axis and grain from
   its **true largest-face NORMAL**, NOT its world-AABB thin-axis. CAD panels can be
   modeled rotated, so the AABB thin-axis lies (this caused pedestal sides to grain
   horizontally while identical code gave the base cabinet correct vertical grain).
   `planar_uv` in `build_scene.py` already does this. Convention: `'vertical'` = grain
   along world-up projected into the panel plane; `'horizontal'` = in-plane horizontal.
   Verify grain with **flat-on elevation renders**, not oblique 3/4 views (foreshortening
   fooled a whole debugging round). Source laminate photos are natively VERTICAL grain.

4b. **TWO UV LAYERS — the grain trap that survives all the way to the website.** The FBX
   import leaves a CAD UV layer on every panel and `planar_uv` ADDS a second one
   ('UVMap'). From then on the two can disagree, and three different things pick a layer:
   - **Blender renders `active_render`** (the camera icon in Object Data ▸ UV Maps).
     `uv_layers.new()` sets `active` but NOT `active_render`, so the CAD layer stays live
     — meaning the human's phase-2 grain fixes go into the **CAD layer**, not 'UVMap'.
   - **glTF gives the material TEXCOORD_0**, i.e. whatever sits at index 0.
   - **`join()` unions the layer sets** of everything it merges, so a panel missing one
     layer gets it back ZEROED. That is why "some panels have the right grain and some
     show the original CAD grain" in one and the same cabinet.

   Rule: at export, **keep the `active_render` layer and delete the rest — do not assume
   it is the one you created** — rename the keeper to one common name so the join is
   safe, and re-run the cleanup AFTER joining. Set `active_render = True` in
   `planar_uv` too, so new builds never split the difference.
   Diagnose from the GLB, not from Blender: `primitives[].attributes` should have exactly
   one `TEXCOORD_*`. Two sets means this bug is live. Then confirm by rendering the
   .blend and the GLB with the SAME camera rig and comparing — that is the only check
   that spans the whole pipeline (`render_glb.py` plus a small open-the-blend twin).

5. **Merging tens of thousands of hardware objects:** `bpy.ops.object.join()` is
   superlinear and hangs at 30–60k objects. Use `fast_merge` (numpy vertex concat +
   `from_pydata` + `batch_remove`) — 61k objects in seconds. It drops UVs/normals, which
   is fine for SOLID-color groups (hardware, legs, doors, frames) only.

6. **FBX import is the real bottleneck** (~11 min for 60k objects, single-threaded, no
   speedup available). **Run per-room builds in PARALLEL** across cores (separate
   headless Blender processes). Don't rebuild a heavy file just for a minor tweak.

7. **No lights in the scene by design** — `<model-viewer>` lights the GLB with its own
   environment. Rendered view in Blender looks black. `build_scene` bakes a soft
   `EditWorld` so editing works; also tell the user to use **Material Preview** mode.
   The world is NOT exported to the GLB.

8. **Keep laminate panels SEPARATE and role-named** (`Cabinet_1__front_1`, `__side_1`,
   `Worktop_1__surface_1`) in per-unit collections so the human can select one panel and
   rotate its grain in phase 2. Merge only solid-color groups. `export_glb` joins each
   furniture collection into one clean node at export (preserving hand edits) but KEEPS
   walls separate.

9. **Handle swaps** (client-specific pull, e.g. Richelieu 3647): detect the wire-pull
   empties, exclude their meshes from the hardware merge, model the new pull to real
   dims, and place one per pull. **Drawer pulls** (longest axis horizontal) → center on
   the drawer front. **Door pulls** (longest axis vertical / Z) → keep original position
   (near the door edge) and run vertical. Center-to-center changes (e.g. 96→160mm) shift
   the empty origin, so center on the FRONT, not the empty. Keep each `Handle_N` a
   separate object for hand-nudging.

10. **Recenter to origin:** BricsCAD exports are offset far from world origin. Shift the
    whole scene so its bounding-box MIN corner sits at (0,0,0), preserving relative
    positions (`build_scene` does this at the end).

11. **Validate at every stage with headless renders.** Workbench FLAT + object colors for
    segmentation/role checks (fast, no lighting); EEVEE for material/texture checks.
    `render_glb.py` has `--focus=<name>` (⚠ hides everything NOT matching that prefix — it
    excluded the `Handles` collection once and made handles look missing), `--bright`,
    `--top`, `--elevX/--elevY`, `--hidewalls`.

12. **Repo hygiene:** raw FBX and 100MB+ source laminate PNGs exceed GitHub's limit —
    gitignore them (kept local). `.blend`s are heavy editable working files — gitignore
    `blend_files/`. Commit the scripts, docs, generated `textures/`, and final `web/**.glb`.
    `.blend`s are texture-packed (`pack_all`) so they're self-contained.

---

## Inputs to gather from the user (ask up front)

- **FBX file(s)** and their location (may be a flat set + subdirs — mirror the structure).
- **Laminate/finish images** (high-res photos) and their **codes/names**.
- **Material mapping**, per furniture element and per panel role. Typical questions:
  - Which laminate on drawer fronts vs carcass sides/backs vs tops/bottoms?
  - Grain direction per role (horizontal/vertical) — and note desks/worktops specifics.
  - Wall finish, door/window-frame "general material", glass appearance.
  - Which hardware to keep/replace; specific handle model + a reference (image/3D/CAD).
- **Per-room specifics:** some files have no walls/windows (cabinet-only) — the scripts
  already handle that; just confirm.

Record the mapping in `docs/<room>_material_spec.md` (template in `references/`).

---

## Workflow

### Step 1 — Scaffold the new project
- `git init`; create dirs: `fbx/`, `materials/`, `scripts/`, `textures/`, `web/models/`,
  `blend_files/`, `docs/validation/`, `assets/`.
- Copy this skill's `scripts/*.py` into the project's `scripts/`.
- Write `.gitignore` (ignore `fbx/*.fbx`, `materials/*.png|jpg|tif`, `blend_files/`,
  `*.blend1`, editor cruft), `CLAUDE.md` (pipeline + source-data facts + lessons pointer),
  `README.md` (room table). Use the reference project's versions as templates.
- Copy the user's FBX into `fbx/` (mirror any subdirs) and laminate images into `materials/`.
- First commit.

### Step 2 — Generate PBR maps
For each laminate: `python scripts/gen_pbr.py "materials/<img>" <CODE> --aux-width 512
[--normal-strength <0.6 light..1.0 strong>]`. Produces `textures/<CODE>_basecolor.jpg`,
`_roughness.png`, `_normal.png`. View a montage to sanity-check. Commit `textures/`.

### Step 3 — Understand the FBX (before trusting segmentation)
Run `inspect_summary.py` (object/material counts), `inspect_hierarchy.py` (root-empty
groups), `inspect_find.py` (locate specific entities). Confirm: how many unparented shell
meshes, what the hardware groups are, whether walls/windows exist. Adjust `roomlib`
thresholds only if a file's geometry differs materially.

### Step 4 — Build editable scenes (PARALLEL)
Per room: `blender --background --factory-startup --python scripts/build_scene.py --
<fbx> <blend_files/...blend>`. Launch all rooms as concurrent background processes.
`build_scene` segments, applies materials + grain per the mapping, swaps handles,
recenters, bakes `EditWorld`, packs textures, saves. Watch for a `Review` collection
(unclassified strays) in the log.
> Edit `build_scene.py`'s material block + `ROLE_GRAIN` map + cluster heuristics to match
> THIS client's spec. Cabinet naming is generic `Cabinet_N` (don't hardcode room-specific
> names across files).

### Step 5 — Validate + get the material mapping
Render color-coded segmentation and cluster views (workbench flat) and labeled cabinet
views so the user can confirm classification and give the G23/H53-style per-role mapping.
Iterate `build_scene` until segmentation + materials look right in headless renders.
Save key renders to `docs/validation/`.

### Step 6 — Phase 2 handoff (HUMAN visual check)
**Pin the Blender version.** Editing in a newer Blender than the pipeline exports with
gets you `File written by newer Blender binary (…), expect loss of data!` on every
export. Agree on one version (4.5 LTS here) and check the export log for that warning.

Hand the user the `blend_files/*.blend`. They open in Blender, use Material Preview,
rotate grain on wrong panels (panels are separate + role-named), nudge overlapping
handles (`Handle_N` in `Handles` collection), repaint glitches, save. Tell them NOT to
re-run `build_scene` after editing (it resets edits from the FBX) unless the client
re-exports the FBX.

13. **The .blend is the human's file — the exporter must obey it, not fight it.** Three
    things the human does in Blender that a naive export throws away or mangles:
    - **Hidden objects** (eye / monitor / camera icon) are how they take a bad handle or
      a duplicate out of the model. `use_selection` exports them anyway — delete
      `hide_render or hide_viewport or hide_get()` objects before exporting.
    - **Hand-duplicated objects land in the scene ROOT**, outside every collection, so
      they escape the per-collection join and export as stray one-off nodes
      (`Handle_3.001`). Adopt loose root meshes into the collection their name implies.
    - **UV layers** — see lesson 4b. Never assume which layer is live; read
      `active_render`.

    And when the human says an edit "didn't come through", do not theorise: dump the
    actual state (per-object UV layers + flags + measured grain direction) from the
    .blend, and read the GLB's JSON chunk. Both times this went wrong, the printout
    named the culprit in one run after a chain of plausible-but-wrong guesses.

### Step 7 — GLB export
`blender --background --factory-startup --python scripts/export_glb.py -- <blend> <glb>`
per finished room. It joins each furniture collection into one clean node (preserving the
phase-2 UV edits), **keeps every `Walls` member separate**, Draco-compresses, writes
`web/models/<room>.glb` (~3 MB). Then:
- **Verify the node names that the web UI depends on** straight out of the GLB, without
  Blender — parse the JSON chunk (`glTF` header → first chunk) and print `nodes[].name`.
  This is the contract between `export_glb.py` and `viewer.js`; check it after every
  export. Expect `Wall_North_1`, `Cabinet_1`, `Doors`, `DoorFrames`, `Window_1`, …
- Re-run `scripts/gen_thumbs.py <room>` so the menu card matches the new GLB.
- Commit the GLB (~3–4 MB each is fine for git; the FBX/blends are not).
- Only re-export rooms the human actually edited — an export takes seconds, but a
  needless `build_scene` rebuild destroys their edits.

### Step 8 — Web hosting (static GitHub-Pages site)
Built in `web/`, deployed by `.github/workflows/pages.yml`. Shape:

```
web/  index.html                 room menu (cards from assets/rooms.js + thumbs)
      rooms/<key>.html           one viewer page per room, MIRRORS the models/ subdirs
      assets/  site.css  viewer.js  rooms.js  logo.png  favicon.svg
               model-viewer.min.js  draco/{wasm_wrapper.js,decoder.wasm,decoder.js}
               thumbs/<key with / -> __>.jpg
      models/<key>.glb
```
- **Generate the pages, don't hand-write N copies:** `scripts/gen_web.py` holds the room
  list and writes both `rooms/**.html` and `assets/rooms.js`. Each page is a thin shell
  (`<body data-room data-root>`); all behaviour lives in one `viewer.js`. Nested rooms get
  `data-root="../.."` — never use site-absolute paths, a project Pages site is served from
  a subpath (`/<repo>/`).
- **Vendor `model-viewer.min.js` AND the Draco decoders** into `assets/` and set
  `ModelViewerElement.dracoDecoderLocation`. The GLBs are Draco-compressed, and
  model-viewer otherwise fetches the decoder from `gstatic.com` at runtime — a CDN
  dependency in the middle of a client demo.
- **Per-wall toggles — the one real trap.** model-viewer has NO public per-node
  visibility API, and every wall shares one material, so the material API can't address
  them individually. Reach the three.js scene through the element's private symbol
  **by description**:
  `Object.getOwnPropertySymbols(mv).find(s => s.description === 'scene')`.
  Widely-copied snippets use `mv[Symbol.for('scene')]` — that is a *registered* symbol and
  returns `undefined` in 4.x, silently leaving dead checkboxes. Same for `needsRender`,
  which you must call to repaint when auto-rotate is off. Version-pin the vendored copy so
  this handle can't shift under you.
- Discover the toggles **at runtime by node-name prefix** (`/^Wall(_|$)/`), never from a
  hardcoded list — then a rename in the .blend (e.g. the client re-labels a mis-classified
  "wall" back to a cabinet side) just drops out of the UI with no code change.
- **Auto-hide near walls** (default on): a closed room reads as a blank box head-on. Hide
  whichever walls sit between camera and room centre, recomputed on `camera-change`
  (`dot(wallDirFromCentre, camDir) > 0.30`); camera direction from the public
  `getCameraOrbit()`, wall centres from geometry bounding boxes, room centre from
  `getBoundingBoxCenter()`. Any manual click switches it off so the checkboxes stay honest.
  Also support `?walls=off|on` deep links.
- **model-viewer renders ON DEMAND.** Setting `node.visible` or `mv.exposure` changes
  nothing on screen until a frame is drawn, so every control must end in a repaint —
  otherwise the UI looks broken and "only works when you click in the scene". The
  repaint is `scene.queueRender()`. Do NOT reach for the element's private
  `needsRender`: `getOwnPropertySymbols()` returns INSTANCE fields only, and that is a
  prototype METHOD, so the lookup returns undefined and the call silently no-ops.
  Also assign `Number(slider.value)` — model-viewer ignores a string.
- Rooms carry **no lights by design**: `environment-image="neutral"`,
  `tone-mapping="neutral"`, `exposure≈1.1`, `shadow-intensity≈0.65`, plus an exposure
  slider — the client's screen is not yours.
- **Phones are how the client will actually open this.** A fixed side panel becomes a
  full-width block that covers the entire model, so below ~820px make it a collapsed
  drawer ("View options") that opens on tap and scrolls inside `max-height:52vh`, with
  bigger tap targets. Pull the camera in (`camera-orbit="auto auto 78%"`) on portrait —
  model-viewer frames to the WIDER axis and strands the model in empty space on a tall
  screen — and size the stage in `dvh` so the collapsing address bar can't clip it.
  Watch CSS specificity when adding the drawer header: a bare `.panel button` rule
  (0,1,1) outranks the new `.panel-head` class (0,1,0) and will quietly override its
  padding. Verify with `Emulation.setDeviceMetricsOverride` at 390×844, not by
  narrowing a desktop window.
- **Pages serves only `/` or `/docs` from a branch**, so publish `web/` via
  `actions/upload-pages-artifact` (`path: web`) + `deploy-pages`; set repo Settings →
  Pages → Source = GitHub Actions once.
- **Check the hosting constraints BEFORE promising GitHub Pages.** On a free account
  Pages requires the repo to be **public** — a non-starter for client work. The site is
  static with no build step, so any static host takes it with the repo private:
  Cloudflare Pages (unlimited bandwidth — the one to pick when every view pulls a 3–4 MB
  GLB), Netlify, or Render. Vercel's Hobby plan is **non-commercial**, so client work
  needs Pro. Ship the config for each (`web/_headers`, `netlify.toml`, `render.yaml`,
  `vercel.json`) so switching host is a dashboard click.
- **Cache headers: split them.** Long/immutable for the vendored `model-viewer` and
  Draco decoders (version-pinned, never change in place); SHORT for `viewer.js` and the
  GLBs, which get re-exported constantly. A stale asset produces the "I fixed it but the
  site shows the old one" report — which already cost a debugging round locally.
- For a client review before deploying, serve `web/` with
  `python -m http.server 8787 --bind 0.0.0.0` and give them `http://<LAN-IP>:8787` —
  they will find the mobile problems immediately. A Windows firewall rule for the port
  may be needed. Tell them to hard-refresh: `http.server` sends caching headers and
  they WILL be looking at the previous `viewer.js`.
- **Test it in a real browser, headless.** `--virtual-time-budget` starves
  `requestAnimationFrame` (~6 ticks in 15 s), so model-viewer never renders and
  `--dump-dom` shows an empty panel — a false failure. Launch Chrome with
  `--remote-debugging-port` and drive CDP (`Runtime.evaluate` + `Page.captureScreenshot`)
  from Node instead; assert on the real page that toggling a checkbox flips
  `node.visible`. Screenshot the result — the toggles passed while the default view was
  still an unusable opaque box.

---

## Script reference (what's in `scripts/`)
- `roomlib.py` — `Room` class: import FBX, classify shell (wall/door/floor/ceiling/glass/
  casework), `_absorb_panels()` (tall cabinet carcass vs door, lesson 3), cluster casework
  into cabinets, split hardware vs components. The brain.
- `gen_pbr.py` — laminate photo → base/roughness/normal maps (web-sized).
- `build_scene.py` — the main builder (materials, grain via face-normal `planar_uv`,
  `fast_merge`, handle swap `make_handle`/`place_handles`, recenter, `EditWorld`, pack+save).
- `export_glb.py` — `.blend` → Draco GLB, walls kept separate.
- `render_glb.py` — headless validation renders (`--focus/--bright/--top/--elevX/--elevY/--hidewalls`).
- `inspect_*.py` — diagnostics for a new/odd FBX.
- `gen_web.py` — room list → `web/rooms/**.html` + `web/assets/rooms.js` (plain python).
- `gen_thumbs.py` — GLB → menu thumbnail via `render_glb.py` + Pillow.

The site's static half lives in this skill's `web/` folder: copy `index.html`,
`assets/site.css`, `assets/viewer.js`, `assets/favicon.svg` into the new project, then
download `model-viewer.min.js` + the matching `draco/` decoders and drop in the client
logo (see Step 8).

Blender: use the installed **4.5 LTS** headless (`blender --background --factory-startup
--python <script> -- <args>`). Python image work uses Pillow + numpy.
