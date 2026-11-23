/* ECP Offices 2026 — viewer page logic.
   Each room page is a thin shell: <body data-room="<key>" data-root="..">.
   Everything else (model path, per-wall toggles, exposure) is driven from here.

   Wall toggles work on the live three.js scene graph that <model-viewer> builds:
   model-viewer has no public per-node visibility API, and every wall shares one
   material so the material-level API cannot address them individually. The scene
   hangs off the element under a private symbol, found by DESCRIPTION — 4.x uses
   Symbol("scene"), not the registered Symbol.for("scene") that older snippets use,
   so Symbol.for() would silently return undefined. model-viewer.min.js is vendored
   and version-pinned (4.3.1) in assets/, so this handle cannot shift underfoot.
   The named Wall_* nodes come straight from export_glb.py, which deliberately never
   joins the Walls collection. */
(function () {
  const body = document.body;
  const ROOT = body.dataset.root || ".";
  const KEY  = body.dataset.room;

  // Draco decoders are vendored under assets/ so the site needs no CDN at runtime
  // (the GLBs are Draco-compressed by export_glb.py).
  const MV = customElements.get("model-viewer");
  if (MV) MV.dracoDecoderLocation = ROOT + "/assets/draco/";

  const mv = document.querySelector("model-viewer");
  mv.src = ROOT + "/models/" + KEY + ".glb";

  const groupsEl = document.getElementById("groups");
  const actionsEl = document.getElementById("actions");

  // Node buckets: walls get one toggle each, the rest of the shell is grouped.
  const WALL_RE = /^Wall(_|$)/i;
  const SHELL = [
    [/^Doors?$|^DoorFrames?$/i, "Doors & frames"],
    [/^Window_/i,               "Windows"],
    [/^Glass$/i,                "Glass"],
    [/^Structure$/i,            "Floor & ceiling"],
  ];

  const sym = desc => Object.getOwnPropertySymbols(mv).find(s => s.description === desc);

  /* Repainting after a toggle. model-viewer renders on demand, so changing
     node.visible does nothing visible until something else triggers a frame —
     which is why edits only appeared once you clicked back into the scene.
     getOwnPropertySymbols() finds INSTANCE fields only, so the private
     needsRender METHOD (which lives on the prototype) was never found and the
     call silently did nothing. The scene object itself exposes queueRender(). */
  let scene = null;
  const invalidate = () => { if (scene) scene.queueRender(); };
  const prettyWall = n => (n.replace(/^Wall_?/i, "").replace(/_/g, " ").trim() || "Wall");

  function collect() {
    const k = sym("scene");
    scene = (k && mv[k]) || null;
    if (!scene) console.warn("[ecp] model-viewer scene handle not found — wall toggles disabled");
    const walls = [], shell = new Map();
    if (!scene) return { walls, shell };
    scene.traverse(o => {
      if (!o.name) return;
      // skip a node whose ancestor already matched, so we toggle the top node once
      for (let p = o.parent; p; p = p.parent) if (p.name && (WALL_RE.test(p.name) ||
          SHELL.some(([re]) => re.test(p.name)))) return;
      if (WALL_RE.test(o.name)) { walls.push(o); return; }
      const hit = SHELL.find(([re]) => re.test(o.name));
      if (hit) { const k = hit[1]; if (!shell.has(k)) shell.set(k, []); shell.get(k).push(o); }
    });
    walls.sort((a, b) => a.name.localeCompare(b.name));
    return { walls, shell };
  }

  function row(label, nodes) {
    const el = document.createElement("label");
    el.className = "row";
    el.innerHTML = '<input type="checkbox" checked><span></span>';
    el.querySelector("span").textContent = label;
    const box = el.querySelector("input");
    box.addEventListener("change", () => {
      nodes.forEach(n => { n.visible = box.checked; });
      invalidate();
    });
    el._set = v => { if (box.checked !== v) { box.checked = v; nodes.forEach(n => n.visible = v); } };
    return el;
  }

  function section(title, rows) {
    const h = document.createElement("h2"); h.textContent = title;
    const d = document.createElement("div"); d.className = "rows";
    rows.forEach(r => d.appendChild(r));
    groupsEl.appendChild(h); groupsEl.appendChild(d);
  }

  /* Auto-hide: a room is a closed box, so head-on it just reads as a blank shell.
     Hide whichever walls sit between the camera and the room centre, recomputed as
     you orbit — the same trick a floor-plan viewer uses. Wall centres come from the
     geometry bounding boxes; the camera direction from model-viewer's public orbit.
     Any manual click switches this off so the checkboxes stay honest. */
  function autoHider(wallRows, walls, openingRows) {
    if (!walls.length) return null;
    const V3 = walls[0].position.constructor;
    const ctr = mv.getBoundingBoxCenter();
    const dirs = walls.map(w => {
      const c = new V3();
      w.traverse(n => { if (n.geometry) { n.geometry.computeBoundingBox(); n.geometry.boundingBox.getCenter(c); n.localToWorld(c); } });
      return new V3(c.x - ctr.x, 0, c.z - ctr.z).normalize();
    });
    let last = "";
    return () => {
      const o = mv.getCameraOrbit();               // theta = azimuth, phi from +Y
      const sp = Math.sin(o.phi);
      const cam = new V3(sp * Math.sin(o.theta), 0, sp * Math.cos(o.theta)).normalize();
      const state = dirs.map(d => d.dot(cam) < 0.30);   // false = wall is in front of us
      const keyStr = state.join("");
      if (keyStr === last) return;
      last = keyStr;
      state.forEach((vis, i) => wallRows[i]._set(vis));
      // doors, frames and glazing are openings IN the walls: with their host wall gone
      // they hang in mid-air and block the casework, so they follow the walls.
      const anyHidden = state.some(v => !v);
      openingRows.forEach(r => r._set(!anyHidden));
      invalidate();
    };
  }

  mv.addEventListener("load", () => {
    groupsEl.innerHTML = ""; actionsEl.innerHTML = "";
    const { walls, shell } = collect();
    const wallRows = walls.map(w => row(prettyWall(w.name), [w]));

    if (wallRows.length) {
      section("Walls", wallRows);
      const mk = (text, vis) => {
        const b = document.createElement("button");
        b.textContent = text;
        b.addEventListener("click", () => { wallRows.forEach(r => r._set(vis)); invalidate(); });
        return b;
      };
      actionsEl.appendChild(mk("Hide all", false));
      actionsEl.appendChild(mk("Show all", true));
    } else {
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent = "Casework-only export — this model has no walls.";
      groupsEl.appendChild(document.createElement("h2")).textContent = "Walls";
      groupsEl.appendChild(p);
    }

    const shellRows = [...shell].map(([label, nodes]) => [label, row(label, nodes)]);
    if (shellRows.length) section("Elements", shellRows.map(([, r]) => r));
    const OPENINGS = /doors|windows|glass/i;      // wall openings, not furniture
    const openingRows = shellRows.filter(([l]) => OPENINGS.test(l)).map(([, r]) => r);

    const auto = document.getElementById("auto"), autoRow = document.getElementById("auto-row");
    const tick = autoHider(wallRows, walls, openingRows);
    if (!tick) { if (autoRow) autoRow.style.display = "none"; }
    else {
      const run = () => { if (auto.checked) tick(); };
      mv.addEventListener("camera-change", run);
      auto.addEventListener("change", run);
      wallRows.concat(openingRows).forEach(r =>
        r.addEventListener("click", () => { auto.checked = false; }));
      actionsEl.addEventListener("click", () => { auto.checked = false; });
      run();
    }

    // deep link: rooms/<key>.html?walls=off|on opens with every wall hidden/shown,
    // which is how you send a client straight to the casework (or to the full room).
    const want = new URLSearchParams(location.search).get("walls");
    if (want === "off" || want === "on") {
      if (auto) auto.checked = false;
      wallRows.forEach(r => r._set(want === "on")); invalidate();
    }
    // model-viewer frames the model to the WIDER axis, which on a tall phone screen
    // leaves it stranded in the middle with big empty margins. Pull the camera in.
    if (matchMedia("(max-width:820px)").matches && innerHeight > innerWidth)
      mv.cameraOrbit = "auto auto 78%";

    window.ECP_VIEW = { walls: walls.map(w => w.name), shell: [...shell.keys()] };
  });

  // exposure: the GLBs carry no lights by design, so give the client a little control
  const exp = document.getElementById("exposure"), expVal = document.getElementById("exposure-val");
  if (exp) exp.addEventListener("input", () => {
    mv.exposure = Number(exp.value);      // a string here is silently ignored
    if (expVal) expVal.textContent = Number(exp.value).toFixed(2);
    invalidate();
  });

  const spin = document.getElementById("spin");
  if (spin) spin.addEventListener("change", () => {
    if (spin.checked) mv.setAttribute("auto-rotate", ""); else mv.removeAttribute("auto-rotate");
  });

  /* On a phone the options panel would cover the model, so it starts collapsed
     there and opens on tap. The breakpoint must match site.css. */
  const panel = document.getElementById("panel"), head = document.getElementById("panel-toggle");
  if (panel && head) {
    const small = () => matchMedia("(max-width:820px), (max-height:520px)").matches;
    const setOpen = open => {
      panel.classList.toggle("collapsed", !open);
      head.setAttribute("aria-expanded", String(open));
    };
    setOpen(!small());
    head.addEventListener("click", () => setOpen(panel.classList.contains("collapsed")));
    matchMedia("(max-width:820px), (max-height:520px)").addEventListener("change", e => setOpen(!e.matches));
  }

  const hint = document.querySelector(".hint");
  if (hint) mv.addEventListener("camera-change", function once() {
    hint.style.opacity = 0; mv.removeEventListener("camera-change", once);
  });
})();
