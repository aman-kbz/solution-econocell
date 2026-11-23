"""Import a GLB and render EEVEE preview images to verify materials/textures.
  blender --background --factory-startup --python scripts/render_glb.py -- web/models/administration.glb _tmp_glb
"""
import bpy, sys, math, mathutils

argv=sys.argv[sys.argv.index("--")+1:]
GLB, OUT = argv[0], (argv[1] if len(argv)>1 else "_tmp_glb")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

HIDE_WALLS = "--hidewalls" in sys.argv
if HIDE_WALLS:
    for o in bpy.data.objects:
        if o.type=='MESH' and o.name.startswith("Wall"): o.hide_render=True

FOCUS=None
for a in sys.argv:
    if a.startswith("--focus="): FOCUS=a.split("=",1)[1]
if FOCUS:
    keep=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith(FOCUS)]
    for o in bpy.data.objects:
        if o.type=='MESH' and o not in keep: o.hide_render=True

meshes=[o for o in bpy.data.objects if o.type=='MESH' and not o.hide_render]
mn=[1e9]*3; mx=[-1e9]*3
for o in meshes:
    for c in o.bound_box:
        w=o.matrix_world@mathutils.Vector(c)
        for i in range(3): mn[i]=min(mn[i],w[i]); mx[i]=max(mx[i],w[i])
ctr=mathutils.Vector([(mn[i]+mx[i])/2 for i in range(3)])
size=[mx[i]-mn[i] for i in range(3)]

sc=bpy.context.scene
sc.render.engine='BLENDER_EEVEE_NEXT'
try:
    sc.eevee.use_raytracing=True
    sc.eevee.use_shadows=True
except Exception as e: print("eevee opt:",e)
sc.render.resolution_x=1500; sc.render.resolution_y=1000
sc.render.film_transparent=False

# world lighting
sc.world=bpy.data.worlds.new("W"); sc.world.use_nodes=True
BR = 1.8 if "--bright" in sys.argv else 1.1
bg=sc.world.node_tree.nodes['Background']; bg.inputs['Color'].default_value=(0.9,0.92,0.95,1); bg.inputs['Strength'].default_value=BR

# key sun + fill area
sun=bpy.data.objects.new("Sun", bpy.data.lights.new("Sun",'SUN')); sc.collection.objects.link(sun)
sun.data.energy=3.0; sun.rotation_euler=(math.radians(55),0,math.radians(35))
area=bpy.data.objects.new("Fill", bpy.data.lights.new("Fill",'AREA')); sc.collection.objects.link(area)
area.data.energy=300; area.data.size=4; area.location=ctr+mathutils.Vector((0,0,size[2]+1.5))

tgt=bpy.data.objects.new("t",None); sc.collection.objects.link(tgt); tgt.location=ctr
def cam(n,loc,lens=35):
    cm=bpy.data.cameras.new(n); o=bpy.data.objects.new(n,cm); sc.collection.objects.link(o)
    o.location=loc; cm.lens=lens
    k=o.constraints.new('TRACK_TO'); k.target=tgt; k.track_axis='TRACK_NEGATIVE_Z'; k.up_axis='UP_Y'
    return o
d=max(size[0],size[1])
views=(('a',( d*1.3,-d*1.3,size[2]*0.7)),('b',(-d*1.3, d*1.1,size[2]*0.6)))
if "--top" in sys.argv:
    views=(('top',(0.001,0.0,d*2.2)),)
if "--elevX" in sys.argv:                 # flat-on +X side elevation
    views=(('elevX',(d*3.0,0.0,size[2]*0.5)),)
if "--elevY" in sys.argv:
    views=(('elevY',(0.0,-d*3.0,size[2]*0.5)),)
for tag,loc in views:
    c=cam(tag,ctr+mathutils.Vector(loc), lens=50 if tag=='top' else 35); sc.camera=c
    sc.render.filepath=f"//{OUT}_{tag}.png"; bpy.ops.render.render(write_still=True)
    print("wrote",f"{OUT}_{tag}.png")
print("@@@ DONE size(m)=",[round(s,2) for s in size])
