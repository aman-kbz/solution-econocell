"""
PART 3 of the Blender workflow: open the hand-edited .blend and export the GLB.
Joins each furniture collection into a single clean node (preserving your UV
edits) but keeps each Wall separate for the website's per-wall toggles.

  blender --background --factory-startup --python scripts/export_glb.py -- \
      blender/administration.blend web/models/administration.glb
"""
import bpy, sys, os

argv = sys.argv[sys.argv.index("--")+1:]
BLEND = argv[0]
OUT   = argv[1] if len(argv) > 1 else "web/models/administration.glb"

bpy.ops.wm.open_mainfile(filepath=os.path.abspath(BLEND))

# --- 1. exactly ONE UV layer per mesh, and it is the one Blender renders ----------
# These meshes carry two UV layers: the CAD one from the FBX import and the 'UVMap'
# build_scene computes. glTF gives the material TEXCOORD_0, so the layer ORDER decides
# what the website shows — and join() unions the layer sets of everything it merges,
# zeroing the layer a given panel doesn't have. That mismatch is what made some panels
# come out with the original CAD grain.
#
# KEEP THE ACTIVE_RENDER LAYER, whatever it is called. That is the layer Blender
# textures with, so it is the one the human saw and hand-corrected in phase 2 —
# which is NOT necessarily 'UVMap': planar_uv creates 'UVMap' but never makes it
# active_render, so on these rooms the CAD layer is the live one. Renaming the keeper
# to a single common name is what makes the later join safe.
UVNAME = "UVMap"
def unify_uvs():
    dropped = 0
    for me in bpy.data.meshes:
        if not me.uv_layers: continue
        keep = next((l for l in me.uv_layers if l.active_render), me.uv_layers[0])
        for l in [l for l in me.uv_layers if l != keep]:
            me.uv_layers.remove(l); dropped += 1
        keep.name = UVNAME                      # safe: it is now the only layer
        keep.active = keep.active_render = True
    return dropped
print(f"@@@ unified UVs, dropped {unify_uvs()} non-rendering layers")

# --- 2. respect what the human hid ------------------------------------------------
# Hiding an object in Blender (eye / monitor / camera icon) is how you take a bad
# handle or a duplicate out of the model; it must not come back on the website.
_hidden = [o for o in bpy.data.objects
           if o.type == 'MESH' and (o.hide_render or o.hide_viewport or o.hide_get())]
for o in _hidden: bpy.data.objects.remove(o)
if _hidden: print(f"@@@ skipped {len(_hidden)} hidden objects:", [o.name for o in _hidden][:10])

# --- 3. adopt loose meshes left in the scene root ---------------------------------
# Objects duplicated by hand (Handle_3.001 etc.) land in the scene root, outside any
# collection, so they would escape the join and export as stray one-off nodes.
for o in list(bpy.context.scene.collection.objects):
    if o.type != 'MESH': continue
    stem = o.name.split(".")[0].rstrip("0123456789_")
    target = next((c for c in bpy.data.collections
                   if c.name.rstrip("s").lower() == stem.rstrip("s").lower()), None)
    if target:
        bpy.context.scene.collection.objects.unlink(o); target.objects.link(o)
        print(f"@@@ adopted loose {o.name} -> {target.name}")

# Join each furniture collection into one object (keeps UV edits); NEVER join Walls.
KEEP_SEPARATE = {"Walls"}
for c in list(bpy.data.collections):
    if c.name in KEEP_SEPARATE: continue
    meshes = [o for o in c.objects if o.type == 'MESH']
    if not meshes: continue
    if len(meshes) == 1:                        # nothing to join; name it after the unit
        meshes[0].name = c.name; continue
    for o in bpy.data.objects: o.select_set(False)
    bpy.context.view_layer.objects.active = meshes[0]
    for o in meshes: o.select_set(True)
    bpy.ops.object.join()
    bpy.context.view_layer.objects.active.name = c.name

unify_uvs()                       # joins can re-add a layer; the last word is ours
_bad = [me.name for me in bpy.data.meshes
        if [l.name for l in me.uv_layers] not in ([], [UVNAME])]
if _bad: print("@@@ WARNING unexpected UV layers on:", _bad)

meshes=[o for o in bpy.data.objects if o.type=='MESH']
print("@@@ export nodes:", sorted(o.name for o in meshes))

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
for o in bpy.data.objects: o.select_set(o.type=='MESH')
DRACO = "--no-draco" not in sys.argv
bpy.ops.export_scene.gltf(
    filepath=os.path.abspath(OUT), export_format='GLB', use_selection=True,
    export_apply=True, export_yup=True, export_texcoords=True, export_normals=True,
    export_materials='EXPORT', export_image_format='AUTO',
    export_draco_mesh_compression_enable=DRACO,
    export_draco_mesh_compression_level=6,
    export_draco_position_quantization=14,
    export_draco_normal_quantization=10,
    export_draco_texcoord_quantization=12)
print("@@@ EXPORTED", OUT, os.path.getsize(OUT)//1024, "KB")
