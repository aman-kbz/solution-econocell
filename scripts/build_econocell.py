"""
PART 1 (this room): solution_econocell.fbx -> editable blend_files/solution_econocell.blend

  blender --background --factory-startup --python scripts/build_econocell.py -- \
      fbx/solution_econocell.fbx blend_files/solution_econocell.blend

Room-specific builder. The generic build_scene.py/roomlib.py assume Material0 = glass,
but in THIS export Material0 is the walls, and the furniture (2 receptions + 4
bookcases) is not drawer-cabinet casework, so classification is explicit here:
by geometry and by position in the (recentred) room. Room layout, recentred, metres:
  x 0..7.90 (west->east), y 0..10.08 (south storefront -> north), z 0..2.74
  Bookcase_1..4   west wall, x<0.75, 1.22 m units starting y=2.10/3.40/4.69/5.99
  Reception_1     north, y>6.9, x 3.5..7.5      Reception_2  centre, x 1.5..2.5
Client spec (docs/solution_econocell_material_spec.md):
  * L592 everywhere, grain: horizontal parts + drawer fronts + toe kicks HORIZONTAL,
    vertical panels VERTICAL.
  * 5/8" (16 mm) toe-kick strips of both receptions = 888 black, own toggle node.
  * 1-5/8" countertops on both receptions = WHITE.
  * Bookcase protruding lower 3-door cabinet (doors, shelf, top, bottom, back, sides) = WHITE.
  * Pulls + locks -> material 'Hardware_Metal' (web: Black / Silver).
  * Bookcase rails + holders -> material 'Rail_Metal' (web: Chrome / Matte Black /
    Matte Nickel / Satin Brass).
  * Finished shell: white painted drywall, large-format tile floor, black aluminium
    storefront (mullion grid + narrow-stile glass doors, as in raw_pngs/).
Node contract with web/assets/viewer.js:
  Wall_*                   one per wall, storefront glazing/doors joined INTO its wall
  Unit_<Name>              one per furniture unit (checkbox each)
  Unit_<Name>__toekick     black 16 mm toe kick (follows its unit AND the toe-kick box)
  Floor
"""
import bpy, bmesh, sys, os, mathutils
from collections import Counter, defaultdict

argv  = sys.argv[sys.argv.index("--")+1:]
FBX   = argv[0]
BLEND = argv[1]
TEX   = os.path.join(os.getcwd(), "textures")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.abspath(FBX))
V = mathutils.Vector

# ---------------- recentre FIRST so every rule below is in room coordinates ----------
def wbb(o):
    ws=[o.matrix_world@V(c) for c in o.bound_box]
    return V([min(w[i] for w in ws) for i in range(3)]), V([max(w[i] for w in ws) for i in range(3)])
_mn=V((1e9,1e9,1e9))
for o in bpy.data.objects:
    if o.type=='MESH':
        a,_=wbb(o); _mn=V([min(_mn[i],a[i]) for i in range(3)])
_T=mathutils.Matrix.Translation(-_mn)
for o in bpy.data.objects:
    if o.parent is None: o.matrix_world=_T@o.matrix_world
bpy.context.view_layer.update()
print(f"@@@ recentred by {[round(v,3) for v in _mn]}")

# ---------------- materials ----------------
# physical size (m) one texture repeat covers: U = image width, V = image height
TILE = {"L592": (0.6096, 1.3208),      # Tafisa pack: 24" x 52" (grain along the 52")
        "888":  (1.1948, 2.4384),      # Uniboard pack: 47.04" x 96"
        "WHITE":(1.2192, 2.4384),      # generated, 48" x 96" sheet
        "FLOOR":(1.2192, 2.4384)}      # generated, 2x2 tiles of 24" x 48"
def _img(path, cs):
    im=bpy.data.images.load(path, check_existing=True); im.colorspace_settings.name=cs; return im
def textured(name, stem):
    m=bpy.data.materials.new(name); m.use_nodes=True; nt=m.node_tree; nt.nodes.clear()
    out=nt.nodes.new('ShaderNodeOutputMaterial'); b=nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    tb=nt.nodes.new('ShaderNodeTexImage'); tb.image=_img(f"{TEX}/{stem}_basecolor.jpg",'sRGB')
    nt.links.new(tb.outputs['Color'], b.inputs['Base Color'])
    tr=nt.nodes.new('ShaderNodeTexImage'); tr.image=_img(f"{TEX}/{stem}_roughness.png",'Non-Color')
    nt.links.new(tr.outputs['Color'], b.inputs['Roughness'])
    tn=nt.nodes.new('ShaderNodeTexImage'); tn.image=_img(f"{TEX}/{stem}_normal.png",'Non-Color')
    nm=nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], b.inputs['Normal']); b.inputs['Metallic'].default_value=0.0
    m["tile"]=stem
    return m
def solid(name, base, metal, rough, transmission=0.0, ior=1.45):
    m=bpy.data.materials.new(name); m.use_nodes=True
    b=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value=(*base,1.0)
    b.inputs['Metallic'].default_value=metal; b.inputs['Roughness'].default_value=rough
    b.inputs['IOR'].default_value=ior
    if transmission: b.inputs['Transmission Weight'].default_value=transmission
    m.diffuse_color=(*base,1.0)
    return m
def glass(name):
    """Alpha-blended, not transmission: model-viewer's transmission pass has nothing
    behind a storefront to refract and renders the panes milky-white. A low-alpha
    blend reads as clear glass, keeps env reflections, and is cheap on phones."""
    m=solid(name, (0.80,0.88,0.88), 0.0, 0.04)
    b=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    b.inputs['Alpha'].default_value=0.18
    m.surface_render_method='BLENDED'; m.use_backface_culling=False
    return m
M = {
 "L592":   textured("L592", "L592"),
 "888":    textured("888_Black", "888"),
 "WHITE":  textured("White", "WHITE"),
 "FLOOR":  textured("Floor_Tile", "FLOOR"),
 # names below are the web contract: viewer.js re-tints these two by material name
 "HW":     solid("Hardware_Metal", (0.03,0.03,0.03), 1.0, 0.45),          # default Black
 "RAIL":   solid("Rail_Metal",     (0.90,0.90,0.92), 1.0, 0.08),          # default Chrome
 "HIDDEN": solid("Hardware_Hidden",(0.55,0.55,0.56), 1.0, 0.40),          # hinges/slides/strikes
 "ALU":    solid("Storefront_Black",(0.018,0.018,0.02), 0.6, 0.38),       # black anodised
 "GLASS":  glass("Glass_Clear"),
 "WALL":   solid("Wall_Paint_OffWhite",(0.78,0.745,0.68), 0.0, 0.92),  # warm off-white, distinct from cabinet WHITE
}

# ---------------- helpers ----------------
def size(o): a,b=wbb(o); return b-a
def ctr(o):  a,b=wbb(o); return (a+b)/2
def set_mat(o, m): o.data.materials.clear(); o.data.materials.append(m)
def coll(name):
    c=bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if name not in [ch.name for ch in bpy.context.scene.collection.children]:
        bpy.context.scene.collection.children.link(c)
    return c
def to_coll(o, name):
    for uc in list(o.users_collection): uc.objects.unlink(o)
    coll(name).objects.link(o)
def unparent(o):
    mw=o.matrix_world.copy(); o.parent=None; o.matrix_world=mw
def face_normal(o):
    best=max(o.data.polygons, key=lambda p:p.area)
    return (o.matrix_world.to_3x3()@best.normal).normalized()

LONG_PANEL = 1.524      # 60": anything longer runs its grain along its length
EDGE_R = 0.0015          # ~2 mm edgeband with a small radius (bevel width, 2 segments)
BEVEL_MAX_FACES = 2000   # fluted/grooved CAD panels already carry their own detail

def round_edges(o):
    """Soften every hard panel edge: 2-segment bevel, hardened normals so the big flat
    faces stay flat-shaded and only the radius catches the light."""
    if len(o.data.polygons) > BEVEL_MAX_FACES: return
    for p in o.data.polygons: p.use_smooth = True
    m = o.modifiers.new("Edgeband", 'BEVEL')
    m.width = EDGE_R; m.segments = 2; m.limit_method = 'ANGLE'
    m.angle_limit = 0.6981   # 40 deg: real corners only, not tessellation
    m.use_clamp_overlap = True; m.harden_normals = True
    with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o]):
        bpy.ops.object.modifier_apply(modifier=m.name)

def planar_uv(o, grain, along=None, bevel=True):
    """Real-scale per-FACE UVs. The grain (texture V, natively vertical in every source)
    follows a world direction chosen from the panel's TRUE largest-face normal (robust
    to rotated CAD panels). grain: 'vertical' | 'horizontal'; horizontal plates always
    run the grain along their LONG axis.
    Faces are mapped one by one: the two big faces use the panel frame; the thin EDGE
    faces (and the bevel strips) run the grain ALONG THE EDGE, like a printed edgeband,
    instead of the smeared streaks a single planar projection leaves on the thickness."""
    if bevel: round_edges(o)
    me=o.data; m=me.materials[0]; tu,tv=TILE[m["tile"]]
    for l in [l.name for l in me.uv_layers]: me.uv_layers.remove(me.uv_layers[l])
    n=face_normal(o); Z=V((0,0,1))
    if abs(n.z)>0.7:
        # plates run with the UNIT's length (a shelf's width), not with whichever side
        # happens to be longer -- unless the plate itself is over 60" in one direction
        s=size(o); longX = s.x>=s.y
        if along is not None and max(s.x,s.y) <= LONG_PANEL:
            longX = abs(along.x) > abs(along.y)
        Vv=V((1,0,0)) if longX else V((0,1,0))
    elif grain=='vertical':
        Vv=(Z-Z.dot(n)*n).normalized()
    else:
        Vv=n.cross(Z).normalized()
    Uu=n.cross(Vv).normalized()
    lay=me.uv_layers.new(name='UVMap'); lay.active=lay.active_render=True
    mw=o.matrix_world; nm=mw.to_3x3()
    for poly in me.polygons:
        fn=(nm@poly.normal).normalized()
        if abs(fn.dot(n))>0.7:                     # main face (or nearly)
            U,Vg=Uu,Vv
        else:                                      # edge / bevel strip
            Vg=n.cross(fn)                         # direction running along the edge
            if Vg.length<1e-6: U,Vg=Uu,Vv
            else:
                Vg.normalize()
                if Vg.dot(Vv)<0: Vg=-Vg            # keep grain flow consistent
                U=fn.cross(Vg).normalized()
        for li in poly.loop_indices:
            co=mw@me.vertices[me.loops[li].vertex_index].co
            lay.data[li].uv=(co.dot(U)/tu, co.dot(Vg)/tv)

def world_uv(o, tile):
    """Top-down planar UV in world metres (floor)."""
    me=o.data; tu,tv=TILE[tile]
    for l in [l.name for l in me.uv_layers]: me.uv_layers.remove(me.uv_layers[l])
    lay=me.uv_layers.new(name='UVMap'); lay.active=lay.active_render=True
    for poly in me.polygons:
        for li in poly.loop_indices:
            co=o.matrix_world@me.vertices[me.loops[li].vertex_index].co
            lay.data[li].uv=(co.x/tu, co.y/tv)

def box(name, mn, mx, mat, cname):
    me=bpy.data.meshes.new(name); bm=bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co=V([mn[i]+(v.co[i]+0.5)*(mx[i]-mn[i]) for i in range(3)])
    bm.to_mesh(me); bm.free()
    o=bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    set_mat(o, mat); to_coll(o, cname); return o

def _alive(o):
    try: return o.name in bpy.data.objects
    except ReferenceError: return False
def join(objs, name):
    objs=[o for o in objs if o and _alive(o)]
    if not objs: return None
    for o in bpy.data.objects: o.select_set(False)
    for o in objs:
        unparent(o); o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
    if len(objs)>1: bpy.ops.object.join()
    o=bpy.context.view_layer.objects.active; o.name=name; o.data.name=name
    return o

# ---------------- regions ----------------
BK_SPLIT=[3.3595, 4.655, 5.95]            # midpoints between adjacent bookcase units
def unit_of(p):
    if p.x<0.9 and 1.9<p.y<7.4:   return f"Bookcase_{1+sum(p.y>b for b in BK_SPLIT)}"
    if p.y>6.9 and 3.5<p.x<7.6:   return "Reception_1"
    if 1.5<p.x<2.5 and 3.2<p.y<6.0: return "Reception_2"
    return None
def storefront_side(p):
    if p.y<0.35: return "South"
    if p.x>7.6 and p.y<5.8: return "East"
    return None

meshes=[o for o in bpy.data.objects if o.type=='MESH']
def root(o):
    while o.parent: o=o.parent
    return o.name.upper()
def matname(o): return o.data.materials[0].name if o.data.materials else ""

# ---------------- 1. drop flat CAD junk (zero-height 2D symbols on the floor) --------
junk=[o for o in meshes if o.parent is None and size(o).z<1e-4]
print(f"@@@ dropped {len(junk)} zero-height junk meshes")
bpy.data.batch_remove(junk)
meshes=[o for o in bpy.data.objects if o.type=='MESH']

# ---------------- 2. walls (Material0 in this export) ----------------
WALLS=defaultdict(list)
for o in [o for o in meshes if o.parent is None and matname(o)=='Material0']:
    c=ctr(o); s=size(o)
    if c.y>9.0:                 side="North"
    elif s.x<s.y:               side="West" if c.x<1 else ("East" if c.x>7.6 else "East_Rear")
    elif c.y<1.0:               side="South"
    else:                       side="East_Rear"          # short return joining the jog
    set_mat(o, M["WALL"]); WALLS[side].append(o)

# ---------------- 3. storefront: frames black, glass clear, doors rebuilt ----------
SF=defaultdict(list); DOORS=[]; GLASS=[]
for o in [o for o in meshes if o.parent is None and matname(o)!='Material0']:
    side=storefront_side(ctr(o))
    if not side: continue
    s=size(o); thin=min(s)
    if matname(o)=='Material2':                         # glass panes
        set_mat(o, M["GLASS"]); GLASS.append((side,o)); SF[side].append(o)
    elif abs(s.x-0.861)<0.01 and abs(s.y-0.044)<0.01:   # solid door-leaf boxes
        DOORS.append(o)
    elif thin<0.0175:                                   # 15 mm interior trim -> painted
        set_mat(o, M["WALL"]); SF[side].append(o)
    else:
        set_mat(o, M["ALU"]); SF[side].append(o)
# door pulls on the glass doors ("Oval Knob" blocks) -> black, part of the south wall
for o in [o for o in meshes if o.parent is not None and 'OVAL KNOB' in root(o)]:
    set_mat(o, M["ALU"]); SF["South"].append(o)

# mullion grid like the real storefront (raw_pngs/): verticals ~1.1 m apart and
# three transoms. Face 45 mm, depth 100 mm, centred on the glass plane.
MW, MD, TRANSOMS = 0.045, 0.100, (0.65, 1.35, 2.05)
for i,(side,g) in enumerate(GLASS):
    a,b=wbb(g)
    along=0 if (b.x-a.x)>(b.y-a.y) else 1; across=1-along
    mid=(a[across]+b[across])/2; L=b[along]-a[along]; nb=max(1,round(L/1.15))
    def piece(lo, hi, zlo, zhi, k):
        mn=[0,0,0]; mx=[0,0,0]
        mn[along],mx[along]=lo,hi; mn[across],mx[across]=mid-MD/2,mid+MD/2
        mn[2],mx[2]=zlo,zhi
        SF[side].append(box(f"Mullion_{side}_{i}_{k}", mn, mx, M["ALU"], "Walls"))
    for k in range(1,nb):
        p=a[along]+L*k/nb; piece(p-MW/2, p+MW/2, a.z, b.z, f"v{k}")
    for k,z in enumerate(TRANSOMS):
        piece(a[along], b[along], z-MW/2, z+MW/2, f"t{k}")

# glass doors: replace each solid leaf with a narrow-stile black frame around glass
STILE, TOP, BOT = 0.060, 0.080, 0.110
for j,d in enumerate(DOORS):
    a,b=wbb(d); my=(a.y+b.y)/2
    def dpart(x0,x1,z0,z1,mat,yy=None,k=""):
        y0,y1=(a.y,b.y) if yy is None else yy
        SF["South"].append(box(f"Door_{j}_{k}", (x0,y0,z0), (x1,y1,z1), mat, "Walls"))
    dpart(a.x, a.x+STILE, a.z, b.z, M["ALU"], k="sl")
    dpart(b.x-STILE, b.x, a.z, b.z, M["ALU"], k="sr")
    dpart(a.x+STILE, b.x-STILE, b.z-TOP, b.z, M["ALU"], k="rt")
    dpart(a.x+STILE, b.x-STILE, a.z, a.z+BOT, M["ALU"], k="rb")
    gp=box(f"Door_{j}_glass", (a.x+STILE, my-0.005, a.z+BOT), (b.x-STILE, my+0.005, b.z-TOP), M["GLASS"], "Walls")
    SF["South"].append(gp)

# each wall carries its own openings, so hiding a wall on the web hides its glazing
for side,objs in WALLS.items():
    w=join(objs+SF.get(side,[]), f"Wall_{side}"); to_coll(w, "Walls")
_door_names=[d.name for d in DOORS]
bpy.data.batch_remove(DOORS)
print("@@@ walls:", sorted(WALLS), "| storefront doors rebuilt:", _door_names)

# ---------------- 4. furniture ----------------
units=defaultdict(list); toekicks=defaultdict(list); review=[]
fillers=defaultdict(list); fillers_w=defaultdict(list)
GROWN=[]                               # bboxes of the centre fronts BEFORE they grew
def on_front(p, bb, tol=0.05):
    a,b=bb; return all(a[i]-tol<=p[i]<=b[i]+tol for i in range(3))
# length direction of each unit (Reception_1 runs east-west, Reception_2 and the bookcases north-south)
UNIT_AXIS={"Reception_1": V((1,0,0)), "Reception_2": V((0,1,0))}
CENTER_FRONT_GROW = 0.015875          # 5/8": centre lock fronts grow UP into the gap
def extend_top(o, d):
    """Move the top face of a panel up by d (world Z), keeping the bottom where it is."""
    a,b=wbb(o); mid=(a.z+b.z)/2; inv=o.matrix_world.inverted(); mw=o.matrix_world
    for v in o.data.vertices:
        w=mw@v.co
        if w.z>mid: v.co=inv@V((w.x,w.y,w.z+d))
    o.data.update()
grain_log=Counter()
for o in [o for o in bpy.data.objects if o.type=='MESH' and o.parent is None
          and not o.name.startswith(("Wall_","Mullion_","Door_"))
          and o.users_collection[0].name!="Walls"]:
    u=unit_of(ctr(o))
    if not u: review.append(o); continue
    s=size(o); mat=matname(o); horiz_plate=s.z<min(s.x,s.y)
    if mat=='Material4':                                  # thin metal strips
        set_mat(o, M["RAIL"] if u.startswith("Bookcase") else M["HIDDEN"])
        units[u].append(o); continue
    if u.startswith("Reception") and min(s.x,s.y)<0.0175 and s.z<0.13 and o.location is not None \
            and wbb(o)[0].z<0.03:                          # 5/8" toe-kick strip -> black
        set_mat(o, M["888"]); planar_uv(o,'horizontal'); toekicks[u].append(o)
        grain_log["toekick_black"]+=1; continue
    if u.startswith("Reception") and horiz_plate and 0.035<s.z<0.045 and wbb(o)[0].z>0.8:
        set_mat(o, M["WHITE"]); planar_uv(o,'horizontal'); units[u].append(o)  # countertop
        grain_log["countertop_white"]+=1; continue
    if u.startswith("Bookcase") and mat=='Material6':      # protruding 3-door cabinet
        set_mat(o, M["WHITE"]); planar_uv(o,'vertical'); units[u].append(o)
        grain_log["bookcase_lower_white"]+=1; continue
    if u.startswith("Bookcase") and 0.370<max(s.x,s.y)<0.378 and 2.12<s.z<2.13:
        # 1/4"-smaller filler sandwiched between bookcase sides: exported TWICE (L592 and
        # WHITE) so the web page can pick one with a radio button
        set_mat(o, M["L592"]); planar_uv(o,'vertical'); fillers[u].append(o)
        w=o.copy(); w.data=o.data.copy(); bpy.context.scene.collection.objects.link(w)
        set_mat(w, M["WHITE"]); planar_uv(w,'vertical', bevel=False); fillers_w[u].append(w)
        grain_log["bookcase_filler_x2"]+=1; continue
    set_mat(o, M["L592"])
    L=UNIT_AXIS.get(u, V((0,1,0)))
    if horiz_plate:
        planar_uv(o,'horizontal', along=L); grain_log["L592_plate"]+=1
    else:
        h=s.z; w=max(s.x,s.y); n=face_normal(o)
        parallel = abs(n.dot(L)) < 0.3          # panel plane runs along the unit's length
        if u.startswith("Reception") and parallel and 0.16<h<0.19 and 0.58<w<0.63                 and wbb(o)[0].z>0.7:
            GROWN.append(wbb(o)); extend_top(o, CENTER_FRONT_GROW); grain_log["center_front_grown"]+=1
        if w > LONG_PANEL:                                   g='horizontal'  # >60": with length
        elif u.startswith("Reception") and parallel and w >= 0.15: g='horizontal'  # backs, fronts
        elif h < 0.13:                                       g='horizontal'  # toe kicks, rails
        else:                                                g='vertical'    # sides, dividers, slats
        planar_uv(o, g); grain_log[f"L592_vert_panel_{g[0].upper()}"]+=1
    units[u].append(o)

# hardware (parented blocks)
hw_log=Counter()
for o in [o for o in bpy.data.objects if o.type=='MESH' and o.parent is not None]:
    r=root(o); u=unit_of(ctr(o))
    if not u: review.append(o); continue
    if 'SHOERAIL' in r:                                   m=M["RAIL"]; k="rail_post"
    elif 'PULL' in r:                                     m=M["HW"];   k="pull"
    elif 'LOCK' in r and 'STRIKE' not in r:               m=M["HW"];   k="lock"
    else:                                                 m=M["HIDDEN"]; k="hidden"
    set_mat(o, m); unparent(o); units[u].append(o); hw_log[k]+=1
    # the lock cylinder + cam ride on the grown centre fronts: move them up with the
    # front so they keep the same distance from its (new) top edge. Strikes are fixed
    # under the countertop and stay put.
    if k=="lock" and any(on_front(ctr(o), bb) for bb in GROWN):
        o.matrix_world = mathutils.Matrix.Translation((0,0,CENTER_FRONT_GROW)) @ o.matrix_world
        hw_log["lock_moved_up"]+=1
print("@@@ grain/material roles:", dict(grain_log))
print("@@@ hardware:", dict(hw_log))

for u,objs in units.items():
    for o in objs: to_coll(o, f"Unit_{u}")
for u,objs in toekicks.items():
    for o in objs: to_coll(o, f"Unit_{u}__toekick")
for u,objs in fillers.items():
    for o in objs: to_coll(o, f"Unit_{u}__filler_L592")
for u,objs in fillers_w.items():
    for o in objs: to_coll(o, f"Unit_{u}__filler_White")
print("@@@ units:", {u:len(v) for u,v in sorted(units.items())},
      "| toekicks:", {u:len(v) for u,v in toekicks.items()},
      "| fillers:", {u:len(v) for u,v in fillers.items()})

# ---------------- 5. floor: large-format tile slab under the whole footprint ----------
xs=[];ys=[]
for o in bpy.data.objects:
    if o.type=='MESH': a,b=wbb(o); xs+= [a.x,b.x]; ys+=[a.y,b.y]
fl=box("Floor", (min(xs),min(ys),-0.02), (max(xs),max(ys),0.0), M["FLOOR"], "Floor")
world_uv(fl, "FLOOR")

# ---------------- leftovers ----------------
for o in review:
    if o.name in bpy.data.objects:
        to_coll(o, "Review")
if review: print(f"@@@ {len(review)} unclassified -> Review:", [(o.name, [round(v,2) for v in ctr(o)]) for o in review][:20])

# empties left from the FBX hierarchy
bpy.data.batch_remove([o for o in bpy.data.objects if o.type=='EMPTY'])
for c in list(bpy.data.collections):
    if not c.objects and not c.children: bpy.data.collections.remove(c)

# soft world for Rendered view while hand-editing (NOT exported)
w=bpy.data.worlds.new("EditWorld"); w.use_nodes=True
bg=w.node_tree.nodes['Background']; bg.inputs['Color'].default_value=(0.85,0.86,0.90,1)
bg.inputs['Strength'].default_value=1.3; bpy.context.scene.world=w

print("@@@ collections:", sorted((c.name, len(c.objects)) for c in bpy.data.collections))
os.makedirs(os.path.dirname(os.path.abspath(BLEND)), exist_ok=True)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(BLEND))
print("@@@ SAVED", BLEND)
