"""
Presentation renders (Cycles, GPU) straight from the editable .blend.

  blender --background --python scripts/render_beauty.py -- blend_files/solution_econocell.blend renders [--samples 256] [--only reception_1] [--pct 30]

Writes renders/<group>_<view>.png. Finishes are the presentation defaults: black toe
kicks, Black handles + locks, Chrome rails, L592 bookcase fillers.
  * product shots: one unit (or all bookcases) on a seamless light studio backdrop
  * room shots: the whole room — cutaways from above and eye-level interiors
The .blend is NOT modified (nothing is saved).
"""
import bpy, sys, os, math, mathutils
V = mathutils.Vector

argv = sys.argv[sys.argv.index("--")+1:]
BLEND, OUT = argv[0], argv[1]
SAMPLES = int(argv[argv.index("--samples")+1]) if "--samples" in argv else 256
ONLY = argv[argv.index("--only")+1] if "--only" in argv else None
RES = (2400, 1500)
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=os.path.abspath(BLEND))
sc = bpy.context.scene

# ---------------- engine ----------------
sc.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = (d.type == 'OPTIX')
    sc.cycles.device = 'GPU'
except Exception:
    sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.denoiser = 'OPTIX' if sc.cycles.device == 'GPU' else 'OPENIMAGEDENOISE'
sc.cycles.max_bounces = 8; sc.cycles.transparent_max_bounces = 16
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = int(argv[argv.index("--pct")+1]) if "--pct" in argv else 100
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_depth = '8'
sc.view_settings.view_transform = argv[argv.index('--view')+1] if '--view' in argv else 'AgX'
sc.view_settings.look = argv[argv.index('--look')+1] if '--look' in argv else 'None'
# exposures picked so L592 renders at its swatch tone (measured: texture mean 120/96/70)
EXP_STUDIO   = float(argv[argv.index("--exposure")+1]) if "--exposure" in argv else -1.0
EXP_INTERIOR = EXP_STUDIO + 0.3
sc.render.film_transparent = False

# ---------------- presentation finishes ----------------
def bsdf(mat): return next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
def set_metal(name, rgb, metal, rough):
    m = bpy.data.materials.get(name)
    if not m: return
    b = bsdf(m); b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
set_metal("Hardware_Metal", (0.020, 0.020, 0.020), 0.50, 0.45)   # Black
set_metal("Rail_Metal",     (0.950, 0.950, 0.950), 1.00, 0.05)   # Chrome
for c in bpy.data.collections:                                    # fillers: L592 only
    if c.name.endswith("__filler_White"):
        for o in c.objects: o.hide_render = True

# ---------------- lighting ----------------
HDRI = os.path.join(os.path.dirname(bpy.app.binary_path), "4.5", "datafiles",
                    "studiolights", "world", "interior.exr")
def make_world(strength, bg_rgb=None):
    """HDRI for light + reflections. With bg_rgb, camera rays see a flat colour instead
    (seamless studio backdrop); otherwise they see the HDRI blurred to a soft sky."""
    w = bpy.data.worlds.new("RenderWorld"); w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(HDRI, check_existing=True)
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    if bg_rgb is None:
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    else:
        flat = nt.nodes.new('ShaderNodeBackground'); flat.inputs['Color'].default_value = (*bg_rgb, 1)
        flat.inputs['Strength'].default_value = 1.0
        lp = nt.nodes.new('ShaderNodeLightPath'); mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        nt.links.new(bg.outputs['Background'], mix.inputs[1]); nt.links.new(flat.outputs['Background'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return w

def light(name, kind, loc, rot, energy, size=None, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = color
    if size is not None:
        if kind == 'AREA': ld.size = size
        elif kind == 'SUN': ld.angle = size
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o)
    o.location = loc; o.rotation_euler = [math.radians(a) for a in rot]
    return o

# studio backdrop: big plane, same colour the camera sees as background -> seamless
BACK_RGB = (0.80, 0.79, 0.77)
bm = bpy.data.materials.new("Studio_Backdrop"); bm.use_nodes = True
b = bsdf(bm); b.inputs['Base Color'].default_value = (*BACK_RGB, 1); b.inputs['Roughness'].default_value = 0.85
bpy.ops.mesh.primitive_plane_add(size=80, location=(4, 5, -0.021))
backdrop = bpy.context.active_object; backdrop.name = "Studio_Backdrop"; backdrop.data.materials.append(bm)

KEY  = light("Key",  'AREA', (0, 0, 0), (0, 0, 0), 900, 3.0)
FILL = light("Fill", 'AREA', (0, 0, 0), (0, 0, 0), 250, 4.0)
SUN  = light("Sun",  'SUN',  (0, 0, 5), (52, 0, 155), 3.5, math.radians(2.5))

# ---------------- scene helpers ----------------
MESHES = [o for o in bpy.data.objects if o.type == 'MESH' and o is not backdrop]
BASE_HIDDEN = {o.name for o in MESHES if o.hide_render}       # white fillers stay hidden
def coll_of(o): return o.users_collection[0].name if o.users_collection else ""
def show(pred):
    for o in MESHES: o.hide_render = (o.name in BASE_HIDDEN) or not pred(o)
def bbox(objs):
    mn = V((1e9,)*3); mx = V((-1e9,)*3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ V(c)
            mn = V([min(mn[i], w[i]) for i in range(3)]); mx = V([max(mx[i], w[i]) for i in range(3)])
    return mn, mx

cam_data = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_data)
sc.collection.objects.link(cam); sc.camera = cam
cam_data.sensor_width = 36

def aim(loc, target, lens):
    cam.location = V(loc); d = V(target) - V(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); cam_data.lens = lens
    cam_data.clip_start = 0.02; cam_data.clip_end = 200

def frame(objs, azim, elev, lens=50, fill=0.80, lift=0.0):
    """Camera on a sphere around the objects' bbox: azim = compass direction the camera
    looks FROM (deg, 0 = from +X/east, 90 = from +Y/north), elev = deg above horizon.
    Distance is solved so the bbox fits `fill` of the frame's limiting dimension."""
    mn, mx = bbox(objs); c = (mn + mx) / 2; c.z += lift
    r = (mx - mn).length / 2
    fov_h = 2 * math.atan(cam_data.sensor_width / 2 / lens)
    fov_v = 2 * math.atan(cam_data.sensor_width * RES[1] / RES[0] / 2 / lens)
    dist = r / math.sin(min(fov_h, fov_v) / 2) * fill
    a, e = math.radians(azim), math.radians(elev)
    d = V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
    aim(c + d * dist, c, lens)
    return c, d

def place_lights(c, d, studio=True):
    """Key light 50 deg to the camera's left and above, fill on the right."""
    yaw = math.atan2(d.y, d.x)
    for L, off, dist, h in ((KEY, math.radians(50), 4.5, 3.5), (FILL, math.radians(-70), 5.5, 1.8)):
        p = c + V((math.cos(yaw + off) * dist, math.sin(yaw + off) * dist, h))
        L.location = p; L.rotation_euler = (c - p).to_track_quat('-Z', 'Y').to_euler()
        L.hide_render = not studio

def render(name):
    if ONLY and not name.startswith(ONLY): return
    sc.render.filepath = os.path.abspath(os.path.join(OUT, f"{name}.png"))
    bpy.ops.render.render(write_still=True)
    print("@@@ wrote", sc.render.filepath)

# ---------------- product shots ----------------
STUDIO = make_world(0.9, BACK_RGB)
PRODUCTS = {
    # name: (collection prefix, [(view, azim, elev, lens, fill)])  -- azim: 270 = from south
    "reception_1": ("Unit_Reception_1", [
        ("front",         270, 12, 50, 0.85), ("front_left", 235, 20, 50, 0.85),
        ("front_right",   305, 20, 50, 0.85), ("back_staff",   60, 25, 50, 0.85),
        ("back_straight",  90, 18, 50, 0.85), ("top",         250, 55, 50, 0.85)]),
    "reception_2": ("Unit_Reception_2", [
        ("front",           0, 12, 50, 0.85), ("front_left",   35, 20, 50, 0.85),
        ("front_right",   325, 20, 50, 0.85), ("back_staff",  210, 25, 50, 0.85),
        ("back_straight", 180, 18, 50, 0.85), ("top",          20, 55, 50, 0.85)]),
    "bookcases": ("Unit_Bookcase_", [
        ("front",           0, 8,  50, 0.80), ("front_left",   40, 15, 50, 0.85),
        ("front_right",   320, 15, 50, 0.85), ("high",         20, 35, 50, 0.85)]),
}
def studio_mode():
    """Floor = shadow catcher on a transparent film; finish_renders() composites onto
    one flat backdrop colour, so there is no visible horizon line."""
    sc.world = STUDIO; backdrop.hide_render = False; backdrop.is_shadow_catcher = True
    sc.render.film_transparent = True; sc.view_settings.exposure = EXP_STUDIO
def interior_mode():
    sc.world = ROOMW; backdrop.hide_render = False; backdrop.is_shadow_catcher = False
    sc.render.film_transparent = False; sc.view_settings.exposure = EXP_INTERIOR
studio_mode(); SUN.hide_render = True
for prod, (prefix, views) in PRODUCTS.items():
    show(lambda o, p=prefix: coll_of(o).startswith(p))
    objs = [o for o in MESHES if not o.hide_render]
    for view, az, el, lens, fill in views:
        c, d = frame(objs, az, el, lens, fill); place_lights(c, d)
        render(f"{prod}_{view}")

# product details (tight crops)
show(lambda o: coll_of(o).startswith("Unit_Reception_1"))
aim((5.55, 8.75, 1.05), (5.55, 7.70, 0.62), 50); place_lights(V((5.55, 7.7, 0.6)), V((0, 1, 0.4)).normalized())
render("reception_1_detail_drawers")
aim((4.4, 6.05, 0.75), (3.75, 7.10, 0.55), 50); place_lights(V((3.7, 7.1, 0.5)), V((-0.5, -1, 0.2)).normalized())
render("reception_1_detail_slats")
show(lambda o: coll_of(o).startswith("Unit_Bookcase_"))
aim((1.55, 3.55, 1.55), (0.40, 3.10, 1.30), 50); place_lights(V((0.4, 3.1, 1.3)), V((1, 0.3, 0.2)).normalized())
render("bookcases_detail_rails")
aim((2.05, 5.25, 1.05), (0.45, 4.45, 0.55), 40); place_lights(V((0.45, 4.45, 0.55)), V((1, 0.5, 0.3)).normalized())
render("bookcases_detail_cabinet")

# ---------------- room shots ----------------
# HDRI lights the room; camera rays (also through the glass) see a soft flat exterior
ROOMW = make_world(1.1, (0.86, 0.87, 0.89))
KEY.hide_render = FILL.hide_render = True; SUN.hide_render = False
everything = lambda o: True
no_front = lambda *walls: (lambda o: coll_of(o) != "Walls" or o.name not in walls)

# cutaways from above: model-on-a-table look, same seamless backdrop as the products
studio_mode()
show(no_front("Wall_South", "Wall_East"))
aim((10.6, -3.6, 7.6), (3.9, 5.2, 0.3), 30); render("room_cutaway_southeast")
show(no_front("Wall_South", "Wall_West"))
aim((-3.4, -3.2, 7.4), (4.0, 5.2, 0.3), 30); render("room_cutaway_southwest")
show(no_front("Wall_East", "Wall_East_Rear", "Wall_North"))
aim((12.0, 11.5, 7.0), (3.8, 4.6, 0.3), 30); render("room_cutaway_northeast")
show(everything)
aim((3.95, 5.04, 17.5), (3.95, 5.04, 0.0), 30); render("room_plan_top")

# eye-level interiors: all walls on, grey ground outside the storefront
interior_mode()
gm = bpy.data.materials.new("Exterior_Ground"); gm.use_nodes = True
g = bsdf(gm); g.inputs['Base Color'].default_value = (0.42, 0.42, 0.42, 1); g.inputs['Roughness'].default_value = 0.9
backdrop.data.materials.clear(); backdrop.data.materials.append(gm)
show(everything)
aim((7.30, 0.55, 1.60), (2.6, 6.4, 0.95), 22); render("room_interior_entrance_corner")
aim((4.60, 0.50, 1.60), (4.30, 7.50, 0.95), 24); render("room_interior_from_doors")
aim((7.20, 9.00, 1.65), (2.2, 2.4, 0.90), 22);  render("room_interior_behind_reception")
aim((3.70, 2.10, 1.55), (0.30, 5.30, 1.05), 24); render("room_interior_bookcases")
aim((1.00, 8.90, 1.65), (5.0, 2.5, 0.95), 22);  render("room_interior_northwest")
print("@@@ DONE")
