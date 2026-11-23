import bpy, sys, re, mathutils
from collections import defaultdict

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=sys.argv[-1])

def root_name(o):
    p=o
    while p.parent is not None:
        p=p.parent
    return p.name

def norm(n):
    n=re.sub(r'\.\d+$','',n)
    n=re.sub(r'_[0-9A-Fa-f]{3,6}$','',n)
    n=re.sub(r'[0-9A-Fa-f]{4,6}$','',n)
    return n.strip()

meshes=[o for o in bpy.data.objects if o.type=='MESH']

# group by normalized ROOT ancestor name
grp=defaultdict(lambda:{'n':0,'f':0,'mn':[1e9]*3,'mx':[-1e9]*3})
for o in meshes:
    key=norm(root_name(o))
    g=grp[key]; g['n']+=1; g['f']+=len(o.data.polygons)
    for c in o.bound_box:
        w=o.matrix_world@mathutils.Vector(c)
        for i in range(3):
            g['mn'][i]=min(g['mn'][i],w[i]); g['mx'][i]=max(g['mx'][i],w[i])

print("\n@@@ GROUPS BY ROOT-EMPTY NAME (normalized) @@@")
print(f"{'objs':>6} {'faces':>8}  {'sizeXxYxZ':>20}  {'zmin..zmax':>14}  name")
for k in sorted(grp,key=lambda x:-grp[x]['f']):
    g=grp[k]
    sz=[g['mx'][i]-g['mn'][i] for i in range(3)]
    print(f"{g['n']:6d} {g['f']:8d}  {sz[0]:5.2f}x{sz[1]:5.2f}x{sz[2]:5.2f}  "
          f"{g['mn'][2]:6.2f}..{g['mx'][2]:5.2f}  {k!r}")

print(f"\n@@@ distinct root groups: {len(grp)} @@@")

# Also: how many meshes are parented to an EMPTY vs unparented
top=defaultdict(int)
for o in meshes:
    top['under_empty' if o.parent else 'unparented']+=1
print("parenting:",dict(top))
