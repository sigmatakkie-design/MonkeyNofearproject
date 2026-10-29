"""Shared helpers for the MONKEY NO FEAR level generators (Blender 4.2+ / bpy module).

Conventions (see Docs/LEVEL_MARKERS.md):
  * meters, Z up; markers are empties named MK_* whose local -Y axis is their "forward"
  * level geometry uses catalog material names only (Docs/ASSET_SPEC.md §2)
  * geometry name prefixes: NOCOL_, COLONLY_, NOCLIMB_, WATER_, UNSTABLE_, ZONE_<Area>_<prio>, KILL_, GAUNTVIEW
"""
import bpy, bmesh, math, os, json
from mathutils import Vector, Matrix, Euler

# preview colours for the catalog materials (Unity uses the real textures)
PREVIEW = {
    'MNF_ConcreteWall': (0.33, 0.33, 0.32), 'MNF_ConcreteFloor': (0.22, 0.22, 0.22), 'MNF_MetalGrate': (0.25, 0.26, 0.27),
    'MNF_MetalDiamond': (0.38, 0.38, 0.4), 'MNF_MetalRusted': (0.35, 0.2, 0.12), 'MNF_MetalPainted_Green': (0.2, 0.3, 0.2),
    'MNF_MetalPainted_Gray': (0.35, 0.36, 0.37), 'MNF_MetalPainted_Yellow': (0.7, 0.55, 0.1), 'MNF_MetalPainted_Red': (0.5, 0.1, 0.08),
    'MNF_Hazard': (0.75, 0.6, 0.05), 'MNF_WoodPlanks': (0.35, 0.25, 0.16), 'MNF_WoodBeam': (0.3, 0.22, 0.14), 'MNF_WoodRotten': (0.2, 0.15, 0.1),
    'MNF_Terrain': (0.18, 0.16, 0.12), 'MNF_RockDry_Tri': (0.3, 0.29, 0.27), 'MNF_RockWet_Tri': (0.15, 0.15, 0.15), 'MNF_RockMine_Tri': (0.22, 0.19, 0.16),
    'MNF_Water': (0.03, 0.05, 0.05), 'MNF_Mud': (0.15, 0.11, 0.08), 'MNF_RockDry': (0.3, 0.29, 0.27), 'MNF_Rubber': (0.05, 0.05, 0.05),
    'MNF_Signs': (0.6, 0.6, 0.5), 'MNF_BulbWarm': (1.0, 0.7, 0.4),
}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    c = PREVIEW.get(name, (0.4, 0.4, 0.4))
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*c, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.8
        if name.startswith('MNF_Bulb'):
            bsdf.inputs['Emission Color'].default_value = (*c, 1.0)
            bsdf.inputs['Emission Strength'].default_value = 3.0
    return m


def collection(name):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


# ---------------------------------------------------------------------------------------------- geometry
class Geo:
    """Accumulates quads/triangles per material; box-projected world-space UVs (tile meters)."""

    def __init__(self, tile=2.0):
        self.verts, self.faces, self.mats, self.uvs = [], [], [], []
        self.matnames = []
        self.tile = tile

    def _mi(self, mat):
        if mat not in self.matnames:
            self.matnames.append(mat)
        return self.matnames.index(mat)

    def face(self, pts, mat, tile=None):
        tile = tile or self.tile
        pts = [Vector(p) for p in pts]
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-9:
            return
        n.normalize()
        ax = max(range(3), key=lambda i: abs(n[i]))
        base = len(self.verts)
        uv = []
        for p in pts:
            if ax == 0:
                u, v = p.y * (1 if n.x > 0 else -1), p.z
            elif ax == 1:
                u, v = p.x * (-1 if n.y > 0 else 1), p.z
            else:
                u, v = p.x, p.y * (1 if n.z > 0 else -1)
            uv.append((u / tile, v / tile))
        self.verts += [tuple(p) for p in pts]
        self.faces.append(tuple(range(base, base + len(pts))))
        self.mats.append(self._mi(mat))
        self.uvs.append(uv)

    def box(self, mn, mx, mat, faces='all', tile=None, inward=False):
        """Axis-aligned box. faces: string with any of 'xXyYzZ' (lowercase = min side) or 'all'."""
        x0, y0, z0 = mn
        x1, y1, z1 = mx
        if faces == 'all':
            faces = 'xXyYzZ'
        quads = {
            'x': [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)],
            'X': [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
            'y': [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            'Y': [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)],
            'z': [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
            'Z': [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
        }
        for f in faces:
            q = quads[f]
            self.face(list(reversed(q)) if inward else q, mat, tile)

    def quad(self, a, b, c, d, mat, tile=None):
        self.face([a, b, c, d], mat, tile)

    def slab(self, corners_bottom, thickness, mat, tile=None):
        """Extruded convex quad (4 points, counter-clockwise from above) upward by thickness."""
        b = [Vector(p) for p in corners_bottom]
        t = [p + Vector((0, 0, thickness)) for p in b]
        self.face([t[0], t[1], t[2], t[3]], mat, tile)
        self.face([b[3], b[2], b[1], b[0]], mat, tile)
        for i in range(4):
            j = (i + 1) % 4
            self.face([b[i], b[j], t[j], t[i]], mat, tile)

    def cylinder(self, a, b, r, mat, seg=10, caps=True, tile=None):
        a, b = Vector(a), Vector(b)
        axis = (b - a)
        if axis.length < 1e-6:
            return
        axis.normalize()
        up = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
        s = axis.cross(up).normalized()
        t = axis.cross(s).normalized()
        ring_a = [a + (s * math.cos(i * 2 * math.pi / seg) + t * math.sin(i * 2 * math.pi / seg)) * r for i in range(seg)]
        ring_b = [p + (b - a) for p in ring_a]
        for i in range(seg):
            j = (i + 1) % seg
            self.face([ring_a[i], ring_a[j], ring_b[j], ring_b[i]], mat, tile)
        if caps:
            self.face(list(reversed(ring_a)), mat, tile)
            self.face(ring_b, mat, tile)

    def build(self, name, coll=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        me.update()
        uvl = me.uv_layers.new(name='UVMap')
        li = 0
        for pi, poly in enumerate(me.polygons):
            for k, loop in enumerate(poly.loop_indices):
                uvl.data[loop].uv = self.uvs[pi][k]
        for mname in self.matnames:
            me.materials.append(material(mname))
        for pi, poly in enumerate(me.polygons):
            poly.material_index = self.mats[pi]
        ob = bpy.data.objects.new(name, me)
        (coll or bpy.context.scene.collection).objects.link(ob)
        return ob


def merge_by_distance(ob, dist=0.0005):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(ob.data)
    bm.free()


def zone_box(name, mn, mx, coll=None):
    g = Geo()
    g.box(mn, mx, 'MNF_ConcreteWall')
    ob = g.build(name, coll)
    ob.display_type = 'WIRE'
    ob.hide_render = True
    return ob


# ---------------------------------------------------------------------------------------------- markers
def yaw_from_forward(fwd):
    """Empty rotation (Z yaw) so that its local -Y axis points along fwd (2D)."""
    fx, fy = fwd[0], fwd[1]
    return math.atan2(fx, -fy)


def marker(name, loc, forward=(0, -1, 0), coll=None, scale=1.0, pitch=0.0):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'ARROWS'
    e.empty_display_size = 0.5
    e.location = loc
    e.rotation_euler = Euler((pitch, 0.0, yaw_from_forward(forward)), 'XYZ')
    if scale != 1.0:
        e.scale = (scale, scale, scale)
    (coll or bpy.context.scene.collection).objects.link(e)
    return e


def fwd_from_yaw_deg(deg):
    r = math.radians(deg)
    return (math.sin(r), -math.cos(r), 0.0)


# ---------------------------------------------------------------------------------------------- export / preview
def export_fbx(path, objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.hide_set(False)
        o.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'},
                             apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', bake_space_transform=False,
                             use_mesh_modifiers=True, mesh_smooth_type='FACE', use_tspace=True, add_leaf_bones=False,
                             bake_anim=False, path_mode='STRIP', colors_type='LINEAR')


def render_preview(path, cam_loc, target, lens=24, res=(960, 540), samples=16, sun=True, world=0.25, extra_lights=()):
    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.cycles.samples = samples
    scn.cycles.device = 'CPU'
    try:
        scn.cycles.use_denoising = True
    except Exception:
        pass
    scn.render.resolution_x, scn.render.resolution_y = res
    if not scn.world:
        scn.world = bpy.data.worlds.new('W')
    scn.world.use_nodes = True
    bg = scn.world.node_tree.nodes['Background']
    bg.inputs[0].default_value = (0.5, 0.55, 0.65, 1)
    bg.inputs[1].default_value = world
    cam = bpy.data.objects.get('PreviewCam')
    if not cam:
        cam = bpy.data.objects.new('PreviewCam', bpy.data.cameras.new('PreviewCam'))
        scn.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.clip_end = 2000
    cam.location = cam_loc
    cam.rotation_euler = (Vector(target) - Vector(cam_loc)).to_track_quat('-Z', 'Y').to_euler()
    scn.camera = cam
    made = []
    if sun and not bpy.data.objects.get('PreviewSun'):
        s = bpy.data.objects.new('PreviewSun', bpy.data.lights.new('PreviewSun', 'SUN'))
        s.data.energy = 3.0
        s.rotation_euler = (math.radians(50), 0, math.radians(30))
        scn.collection.objects.link(s)
    for i, (loc, energy) in enumerate(extra_lights):
        l = bpy.data.objects.new(f'PrevLamp{i}', bpy.data.lights.new(f'PrevLamp{i}', 'POINT'))
        l.data.energy = energy
        l.location = loc
        scn.collection.objects.link(l)
        made.append(l)
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for l in made:
        bpy.data.objects.remove(l)


def write_report(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=1)


# ---------------------------------------------------------------------------------------------- preview dressing
_KIT_CACHE = {}


def load_kits(props_dir, kits=('Kit_Forest', 'Kit_Mine', 'Kit_Bunker', 'Kit_Deposits', 'Kit_Tools')):
    """Imports prop kits into hidden collections (one collection per top-level kit object) for previews."""
    lib = collection('_PreviewLib')
    lib.hide_render = False
    for kit in kits:
        path = os.path.join(props_dir, kit + '.fbx')
        if not os.path.exists(path):
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            for c in list(o.users_collection):
                c.objects.unlink(o)
        for top in [o for o in new if o.parent is None]:
            col = bpy.data.collections.new('LIB_' + top.name)
            lib.children.link(col)
            for o in [top] + list(top.children_recursive):
                if o.name.startswith('COL_'):
                    continue
                col.objects.link(o)
            _KIT_CACHE[top.name.split('.')[0]] = col
    tex_dir = os.path.join(os.path.dirname(os.path.dirname(props_dir)), 'Textures')
    for img in bpy.data.images:
        if img.filepath and not os.path.exists(bpy.path.abspath(img.filepath)):
            cand = os.path.join(tex_dir, os.path.basename(img.filepath))
            if os.path.exists(cand):
                img.filepath = cand
                img.reload()
    lib.hide_viewport = True
    bpy.context.view_layer.layer_collection.children['_PreviewLib'].exclude = True
    return _KIT_CACHE


def dress_preview(markers, station_map=None):
    """Instances kit props at MK_PROP_* / MK_STATION_* markers (preview renders only, never exported)."""
    station_map = station_map or {}
    made = []
    for m in markers:
        n = m.name.split('.')[0]
        key = None
        if n.startswith('MK_PROP_'):
            key = n[len('MK_PROP_'):]
        elif n.startswith('MK_STATION_'):
            key = station_map.get(n[len('MK_STATION_'):])
        elif n.startswith('MK_ORE_'):
            key = 'Deposit_Iron'
        if not key or key not in _KIT_CACHE:
            continue
        inst = bpy.data.objects.new('PREV_' + key, None)
        inst.instance_type = 'COLLECTION'
        inst.instance_collection = _KIT_CACHE[key]
        inst.matrix_world = m.matrix_world.copy()
        bpy.context.scene.collection.objects.link(inst)
        made.append(inst)
    return made
