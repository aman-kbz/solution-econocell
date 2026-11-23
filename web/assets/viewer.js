/* Solution Econocell — viewer page logic.
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
    [/^Floor$/i,                "Floor"],
  ];

  /* Furniture: export_glb.py emits one node per unit, `Unit_<Name>`, plus optional
     parts with a suffix:
       `__toekick`                       black 5/8" toe kicks (shown only when BOTH
                                         the unit and the "Black toe kicks" box are on)
       `__filler_L592` / `__filler_White` the 1/4"-smaller panels sandwiched between
                                         bookcases, exported in both finishes; the
                                         "Bookcase fillers" radio picks which is shown */
  const UNIT_RE = /^Unit_(.+?)(?:__(toekick|filler_L592|filler_White))?$/;
  const prettyUnit = n => n.replace(/_/g, " ");

  /* Finishes: re-tint by MATERIAL NAME through model-viewer's public material API.
     Values are glTF factors (linear colour, metallic, roughness). The names are the
     contract with scripts/build_econocell.py. */
  const FINISHES = [
    { title: "Handles & locks", material: "Hardware_Metal", param: "hw", options: [
      ["black",  "Black",  [0.020, 0.020, 0.020], 0.50, 0.45],
      ["silver", "Silver", [0.800, 0.800, 0.800], 1.00, 0.30],
    ]},
    { title: "Bookcase rails", material: "Rail_Metal", param: "rail", options: [
      ["chrome",       "Chrome",       [0.950, 0.950, 0.950], 1.00, 0.05],
      ["matte-black",  "Matte Black",  [0.020, 0.020, 0.020], 0.30, 0.60],
      ["matte-nickel", "Matte Nickel", [0.660, 0.640, 0.600], 1.00, 0.45],
      ["satin-brass",  "Satin Brass",  [0.780, 0.560, 0.240], 1.00, 0.32],
    ]},
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
    const walls = [], shell = new Map(), units = new Map(), toekicks = [];
    if (!scene) return { walls, shell, units, toekicks };
    scene.traverse(o => {
      if (!o.name) return;
      // skip a node whose ancestor already matched, so we toggle the top node once
      for (let p = o.parent; p; p = p.parent) if (p.name && (WALL_RE.test(p.name) ||
          SHELL.some(([re]) => re.test(p.name)))) return;
      if (WALL_RE.test(o.name)) { walls.push(o); return; }
      const um = UNIT_RE.exec(o.name);
      if (um && !(o.parent && UNIT_RE.test(o.parent.name || ""))) {
        if (!units.has(um[1])) units.set(um[1], []);
        units.get(um[1]).push(o);
        o.userData.part = um[2] || "";
        if (um[2] === "toekick") toekicks.push(o);
        return;
      }
      const hit = SHELL.find(([re]) => re.test(o.name));
      if (hit) { const k = hit[1]; if (!shell.has(k)) shell.set(k, []); shell.get(k).push(o); }
    });
    walls.sort((a, b) => a.name.localeCompare(b.name));
    return { walls, shell, units, toekicks };
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
    const { walls, shell, units, toekicks } = collect();
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
    // ---- furniture: one checkbox per unit + the black toe-kick strips ----
    if (units.size) {
      const unitOn = new Map([...units.keys()].map(k => [k, true]));
      let toeOn = true;
      const fillerOpts = [["L592", "L592"], ["White", "White"]];
      const fillerParam = new URLSearchParams(location.search).get("filler");
      let filler = (fillerOpts.find(([k]) => k.toLowerCase() === (fillerParam || "").toLowerCase()) || fillerOpts[0])[0];
      const apply = () => {
        units.forEach((nodes, k) => nodes.forEach(n => {
          const part = n.userData.part;
          n.visible = unitOn.get(k)
            && (part !== "toekick" || toeOn)
            && (!part.startsWith("filler_") || part === "filler_" + filler);
        }));
        invalidate();
      };
      const check = (label, on) => {
        const el = document.createElement("label");
        el.className = "row";
        el.innerHTML = '<input type="checkbox" checked><span></span>';
        el.querySelector("span").textContent = label;
        el.querySelector("input").addEventListener("change", e => { on(e.target.checked); apply(); });
        return el;
      };
      const keys = [...units.keys()].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
      const rows = keys.map(k => check(prettyUnit(k), v => unitOn.set(k, v)));
      if (toekicks.length) rows.push(check("Black toe kicks", v => { toeOn = v; }));
      section("Furniture", rows);
      const hasFiller = [...units.values()].flat().some(n => n.userData.part.startsWith("filler_"));
      if (hasFiller) {
        section("Bookcase fillers", fillerOpts.map(([k, label]) => {
          const el = document.createElement("label");
          el.className = "row";
          el.innerHTML = '<input type="radio" name="finish-filler"><span></span>';
          el.querySelector("span").textContent = label;
          const r = el.querySelector("input");
          r.checked = k === filler;
          r.addEventListener("change", () => { if (r.checked) { filler = k; apply(); } });
          return el;
        }));
      }
      apply();
    }

    // ---- finishes: radio groups that re-tint a named material ----
    const mats = (mv.model && mv.model.materials) || [];
    const params = new URLSearchParams(location.search);
    FINISHES.forEach((f, gi) => {
      const targets = mats.filter(m => m.name === f.material);
      if (!targets.length) return;
      const set = ([, , rgb, metal, rough]) => {
        targets.forEach(m => {
          const pbr = m.pbrMetallicRoughness;
          pbr.setBaseColorFactor([...rgb, 1]);
          pbr.setMetallicFactor(metal);
          pbr.setRoughnessFactor(rough);
        });
        invalidate();
      };
      const want = params.get(f.param);
      const start = f.options.find(o => o[0] === want) || f.options[0];
      const rows = f.options.map(opt => {
        const el = document.createElement("label");
        el.className = "row";
        el.innerHTML = `<input type="radio" name="finish-${gi}"><span></span>`;
        el.querySelector("span").textContent = opt[1];
        const r = el.querySelector("input");
        r.checked = opt === start;
        r.addEventListener("change", () => { if (r.checked) set(opt); });
        return el;
      });
      section(f.title, rows);
      set(start);
    });

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

    window.ECP_VIEW = { walls: walls.map(w => w.name), shell: [...shell.keys()],
                        units: [...units.keys()], toekicks: toekicks.map(n => n.name),
                        materials: mats.map(m => m.name) };
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

  /* Double-click (double-tap) a surface to make it the orbit/zoom centre. Zoom always
     moves toward the camera TARGET, which starts at the room centre, so without this
     you can't get close to a cabinet on the side without fiddly panning. */
  const focusAt = (x, y) => {
    const r = mv.getBoundingClientRect();
    const hit = mv.positionAndNormalFromPoint(x - r.left, y - r.top);
    if (!hit) return;
    const p = hit.position;
    mv.cameraTarget = `${p.x}m ${p.y}m ${p.z}m`;
    if (spin && spin.checked) { spin.checked = false; mv.removeAttribute("auto-rotate"); }
  };
  mv.addEventListener("dblclick", e => focusAt(e.clientX, e.clientY));
  let lastTap = 0;
  mv.addEventListener("touchend", e => {
    if (e.changedTouches.length !== 1) return;
    const now = Date.now(), t = e.changedTouches[0];
    if (now - lastTap < 300) focusAt(t.clientX, t.clientY);
    lastTap = now;
  });

  const hint = document.querySelector(".hint");
  if (hint) mv.addEventListener("camera-change", function once() {
    hint.style.opacity = 0; mv.removeEventListener("camera-change", once);
  });
})();
