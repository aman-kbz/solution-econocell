import bpy, sys, os, mathutils
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
import roomlib

FBX = sys.argv[sys.argv.index("--")+1]
R = roomlib.Room(FBX)

def info(o):
    mn,mx = roomlib.world_bounds(o)
    d=[mx[i]-mn[i] for i in range(3)]
    par = o.parent.name if o.parent else None
    inshell = o.parent is None
    cat = R.cat.get(o.name,"(hw)") if inshell else "(parented→hardware)"
    return (f"{o.name:16s} parent={str(par):22s} "
            f"dim=({d[0]:.3f},{d[1]:.3f},{d[2]:.3f}) "
            f"pos=({(mn[0]+mx[0])/2:.2f},{(mn[1]+mx[1])/2:.2f},{mn[2]:.2f}..{mx[2]:.2f}) "
            f"cat={cat}")

print("\n@@@ LEG ENTITIES (user-provided) @@@")
targets=["2C12C","2C12D","2C12E"]
for o in bpy.data.objects:
    if o.type=='MESH' and any(t in o.name for t in targets):
        print("  ",info(o))

print("\n@@@ SIBLINGS UNDER SAME PARENT AS 2C12C @@@")
seed=next((o for o in bpy.data.objects if "2C12C" in o.name), None)
if seed and seed.parent:
    for o in bpy.data.objects:
        if o.type=='MESH' and o.parent is seed.parent:
            print("  ",info(o))
elif seed:
    print("   2C12C is UNPARENTED (in shell). cat=",R.cat.get(seed.name))

print("\n@@@ ALL 'wall'-CLASSIFIED MESHES (candidate walls+doors) @@@")
for o in R.shell:
    if R.cat[o.name]=='wall':
        print("  ",info(o))

print("\n@@@ shell cats summary @@@")
from collections import Counter
print("  ",Counter(R.cat.values()))
print("@@@ END @@@")
