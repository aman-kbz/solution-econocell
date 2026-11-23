"""
Shared room-analysis core for the ECP pipeline. Imported by the Blender headless
scripts. Classifies a BricsCAD room FBX by geometry/hierarchy and clusters
casework panels into cabinets. Names & materials in the source are junk, so
everything here is geometric.
"""
import bpy, mathutils
from collections import defaultdict

def reset_import(fbx):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)

def world_bounds(o):
    mn = [1e9]*3; mx = [-1e9]*3
    for c in o.bound_box:
        w = o.matrix_world @ mathutils.Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
    return mn, mx

def _glass(o):
    return any((m and m.name == 'Material0') for m in o.data.materials)

class Room:
    def __init__(self, fbx):
        reset_import(fbx)
        self.meshes = [o for o in bpy.data.objects if o.type == 'MESH']
        self.shell  = [o for o in self.meshes if o.parent is None]
        self.hw     = [o for o in self.meshes if o.parent is not None]
        # Some exports parent everything (no unparented shell). Fall back to using
        # every mesh as shell so classification still runs.
        if not self.shell:
            self.shell = list(self.meshes); self.hw = []
        self.bb = {}
        self.RMN = [1e9]*3; self.RMX = [-1e9]*3
        for o in self.shell:
            mn, mx = world_bounds(o); self.bb[o.name] = (mn, mx)
            for i in range(3):
                self.RMN[i] = min(self.RMN[i], mn[i]); self.RMX[i] = max(self.RMX[i], mx[i])
        self.RS = [self.RMX[i]-self.RMN[i] for i in range(3)]
        self.cat = {o.name: self._classify(o) for o in self.shell}
        self.absorbed = self._absorb_panels()
        self.clusters = self._cluster()
        self._mark_windows()
        self.comp_cat = self._classify_components()

    # Parented objects: true hardware (droppable) vs furniture components (e.g. legs, visible)
    HW_PATTERNS = ('LOCK','PULL','KNOB','CASTER','TWINWHEEL','SLIDE','STRIKE',' CAM','HINGE')
    def _root_name(self, o):
        p=o
        while p.parent is not None: p=p.parent
        return p.name
    def _classify_components(self):
        cc={}
        for o in self.hw:
            rn=self._root_name(o).upper()
            cc[o.name] = 'hardware' if any(p in rn for p in self.HW_PATTERNS) else 'component'
        return cc
    def components(self):
        """parented meshes that are furniture components (legs etc.), not hardware"""
        return [o for o in self.hw if self.comp_cat.get(o.name)=='component']
    def hardware(self):
        return [o for o in self.hw if self.comp_cat.get(o.name)=='hardware']

    def _mark_windows(self):
        # a casework cluster mounted off the floor (bottom well above 0) and shallow
        # is a WINDOW (glass+frame), not furniture.
        for c in self.clusters:
            c['kind'] = 'casework'
            # real window = off-floor, shallow, sizeable, AND multi-panel (frame+panes).
            # excludes thin 2-panel door top-frames.
            if (c['mn'][2] > 0.5 and min(c['size']) < 0.30 and max(c['size']) > 0.6
                    and len(c['names']) >= 4):
                c['kind'] = 'window'

    def dims(self, name):
        mn, mx = self.bb[name]; return [mx[i]-mn[i] for i in range(3)]
    def center(self, name):
        mn, mx = self.bb[name]; return [(mn[i]+mx[i])/2 for i in range(3)]

    # A real wall is >=100mm thick in these exports; laminate carcass panels are
    # 16-25mm and door leaves/jambs 15-45mm. Without this gate a tall cabinet side
    # is read as a wall in cabinet-only files (where RS[2] IS the cabinet height).
    WALL_MIN_THICK = 0.06
    PANEL_TOL = 0.02          # tight contact => same piece of furniture

    def _classify(self, o):
        mn, mx = self.bb[o.name]
        dz=mx[2]-mn[2]; dx=mx[0]-mn[0]; dy=mx[1]-mn[1]; cz=(mn[2]+mx[2])/2
        foot=dx*dy
        if _glass(o): return 'glass'
        if dz<0.20 and cz<0.25 and foot>0.25*self.RS[0]*self.RS[1]: return 'floor'
        if dz<0.25 and mn[2]>self.RMX[2]-0.4 and foot>0.25*self.RS[0]*self.RS[1]: return 'ceiling'
        # tall thin vertical element: full-height AND thick => WALL (incl. narrow
        # returns/pilasters); anything else tall-thin => DOOR leaf/frame/jamb,
        # which _absorb_panels() then pulls back if it belongs to a cabinet.
        if dz>1.5 and (dx<0.35 or dy<0.35):
            if dz > 0.9*self.RS[2] and min(dx,dy) >= self.WALL_MIN_THICK: return 'wall'
            return 'door'
        return 'casework'

    def _panel_of(self, n, seed):
        """True if panel `n` is a FACE of cabinet body `seed`: touching on every axis
        and covering >=50% of the shared span on both of its long axes. A door leaf
        that merely abuts a cabinet corner overlaps only a sliver and is rejected."""
        mn,mx=self.bb[n]; t=[mx[i]-mn[i] for i in range(3)]; ax=t.index(min(t))
        for i in range(3):
            lo=max(mn[i],seed['mn'][i]); hi=min(mx[i],seed['mx'][i])
            if hi-lo < -self.PANEL_TOL: return False            # no contact on this axis
            if i==ax: continue                                  # thickness axis
            span=min(t[i], seed['size'][i])
            if span>1e-6 and (hi-lo)/span < 0.5: return False    # sliver contact only
        return True

    def _absorb_panels(self):
        """BricsCAD gives a TALL CABINET carcass the same tall+thin signature as a
        door leaf, so its sides/back get classified 'door' and its shelves are left
        orphaned (they end up merged into the DoorFrames blob). Pull any such panel
        back into casework when it is a face of a cabinet-sized body. Anchoring on
        cabinet-sized bodies (not on any casework) is what keeps REAL doors out: a
        door's own head transom is casework, but it is far too thin to be a cabinet.
        Iterate to a fixed point so a back panel reachable only through an already
        absorbed side is caught too."""
        moved=[]
        while True:
            seeds=[c for c in self._cluster() if min(c['size'])>0.12 and c['size'][2]>0.25]
            new=[o.name for o in self.shell if self.cat[o.name]=='door'
                 and any(self._panel_of(o.name,s) for s in seeds)]
            if not new: return moved
            for n in new: self.cat[n]='casework'
            moved += new

    def _cluster(self, tol=0.06):
        case=[o.name for o in self.shell if self.cat[o.name]=='casework']
        parent={n:n for n in case}
        def find(x):
            while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
            return x
        def ov(a,b):
            ma,xa=self.bb[a]; mb,xb=self.bb[b]
            return all(ma[i]-tol<=xb[i] and mb[i]-tol<=xa[i] for i in range(3))
        for i in range(len(case)):
            for j in range(i+1,len(case)):
                if ov(case[i],case[j]): parent[find(case[i])]=find(case[j])
        groups=defaultdict(list)
        for n in case: groups[find(n)].append(n)
        out=[]
        for g in sorted(groups.values(), key=lambda x:-len(x)):
            mn=[1e9]*3; mx=[-1e9]*3
            for n in g:
                a,b=self.bb[n]
                for i in range(3): mn[i]=min(mn[i],a[i]); mx[i]=max(mx[i],b[i])
            out.append({'names':g,'mn':mn,'mx':mx,
                        'center':[(mn[i]+mx[i])/2 for i in range(3)],
                        'size':[mx[i]-mn[i] for i in range(3)]})
        for i,c in enumerate(out): c['id']=i
        return out

    def walls_by_side(self):
        groups=defaultdict(list)
        cx=(self.RMN[0]+self.RMX[0])/2; cy=(self.RMN[1]+self.RMX[1])/2
        for o in self.shell:
            if self.cat[o.name]!='wall': continue
            d=self.dims(o.name); c=self.center(o.name)
            if d[0]<d[1]:
                groups['W_west' if c[0]<cx else 'W_east'].append(o.name)
            else:
                groups['W_south' if c[1]<cy else 'W_north'].append(o.name)
        return groups
