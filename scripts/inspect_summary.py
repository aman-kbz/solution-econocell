import bpy, sys
from collections import defaultdict

bpy.ops.wm.read_factory_settings(use_empty=True)
fbx = sys.argv[-1]
bpy.ops.import_scene.fbx(filepath=fbx)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']

print("\n@@@ MATERIALS (name | #objects using | baseColor RGBA) @@@")
usecount = defaultdict(int)
for o in meshes:
    for m in o.data.materials:
        if m: usecount[m.name]+=1
for m in sorted(bpy.data.materials, key=lambda x:-usecount[x.name]):
    base=None
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type=='BSDF_PRINCIPLED':
                base=tuple(round(v,3) for v in n.inputs['Base Color'].default_value)
    print(f"  {usecount[m.name]:6d}  {m.name!r:45s} base={base}")

print("\n@@@ OBJECT NAME PREFIX HISTOGRAM (first token) @@@")
hist=defaultdict(int); tris=defaultdict(int)
for o in meshes:
    key=o.name.split('_')[0].split('.')[0][:28]
    hist[key]+=1
    tris[key]+=len(o.data.polygons)
for k in sorted(hist, key=lambda x:-hist[x])[:60]:
    print(f"  {hist[k]:6d} objs  {tris[k]:9d} faces  {k!r}")

total_faces=sum(len(o.data.polygons) for o in meshes)
total_verts=sum(len(o.data.vertices) for o in meshes)
print(f"\n@@@ TOTALS: meshes={len(meshes)} verts={total_verts} faces={total_faces} materials={len(bpy.data.materials)} @@@")
