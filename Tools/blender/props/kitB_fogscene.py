"""kitB_fogscene - moody foggy night render of a small haunted-forest arrangement built from Kit_Forest
(preview only, nothing is exported).  usage: python kitB_fogscene.py -- [out.png] [samples]"""
import bpy, sys, os, math, random
from mathutils import Vector, noise
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import propkit_b_helpers as H

args = H.args_after_dashdash()
OUT = args[0] if args else os.path.join(H.PREV_OUT, 'kitB_forest_fog.png')
SAMPLES = int(args[1]) if len(args) > 1 else 24
bpy.ops.wm.open_mainfile(filepath=os.path.join(H.SRC_OUT, 'Kit_Forest.blend'))
sc = bpy.context.scene
for o in bpy.data.objects:
    o.hide_render = True
coll = bpy.data.collections.new('_fog')
sc.collection.children.link(coll)
R = random.Random(7)


def inst(name, loc, yaw=0.0, scale=1.0, with_children=False):
    src = bpy.data.objects[name]
    o = bpy.data.objects.new(name + '_i', src.data)
    o.location = loc
    o.rotation_euler = (0, 0, math.radians(yaw))
    o.scale = (scale, scale, scale)
    coll.objects.link(o)
    if with_children:
        for c in src.children:
            if c.type == 'MESH' and not H.export_name(c.name).startswith('COL_'):
                cc = bpy.data.objects.new(c.name + '_i', c.data)
                cc.parent = o
                cc.location = c.location
                coll.objects.link(cc)
    return o


# ground
import bmesh
me = bpy.data.meshes.new('fog_ground')
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=60, y_segments=60, size=40)
for v in bm.verts:
    v.co.z = 0.35 * noise.noise(v.co * 0.12) + 0.08 * noise.noise(v.co * 0.6) - 0.05
    if abs(v.co.x) < 1.6:
        v.co.z -= 0.06
uv = bm.loops.layers.uv.new('UVMap')
for f in bm.faces:
    for l in f.loops:
        l[uv].uv = (l.vert.co.x / 2.0, l.vert.co.y / 2.0)
bm.to_mesh(me)
g = bpy.data.objects.new('fog_ground', me)
me.materials.append(H.get_mat('MNF_ForestFloor'))
for p in me.polygons:
    p.use_smooth = True
coll.objects.link(g)

# trees: dense dark conifers + dead trees, leaving a path along +Y
pines = ['Tree_Pine_A', 'Tree_Pine_B', 'Tree_Pine_C']
deads = ['Tree_Dead_A', 'Tree_Dead_B', 'Tree_Dead_C']
placed = []
for k in range(70):
    for _ in range(40):
        x = R.uniform(-24, 24)
        y = R.uniform(2.0, 48)
        if abs(x) < 2.6 + y * 0.03:
            continue
        if y < 6 and abs(x) < 7:          # keep the camera clear
            continue
        if (x - 6) ** 2 + (y - 21) ** 2 < 25:      # cabin clearing
            continue
        if all((x - px) ** 2 + (y - py) ** 2 > 9 for px, py in placed):
            break
    placed.append((x, y))
    name = R.choice(deads) if R.random() < 0.28 else R.choice(pines)
    inst(name, (x, y, -0.05), R.uniform(0, 360), R.uniform(0.85, 1.15))
inst('Tree_Dead_A', (-3.4, 7.5, -0.05), 40, 1.0)
inst('Tree_Gnarled', (4.2, 9.0, -0.05), 200, 1.0)
inst('Tree_Dead_C', (2.9, 4.0, -0.05), 110, 0.95)
inst('Cabin_Ruin', (7.0, 21.0, 0.0), -35)
inst('FallenTree', (-6.0, 13.5, 0.0), 20)
inst('SignPost', (-1.9, 5.5, 0.0), 15, 1.0, with_children=True)
inst('Fence_Broken', (2.6, 15.0, 0.0), 80)
inst('Fence_Section', (2.6, 17.5, 0.0), 82)
inst('Stump', (-2.6, 3.0, 0.0), 0)
for k in range(28):
    nm = R.choice(['Rock_A', 'Rock_B', 'Rock_C', 'Rock_D', 'Rock_E'])
    x = R.uniform(2.4, 16) * (1 if R.random() < 0.5 else -1)
    inst(nm, (x, R.uniform(3.0, 35), 0.0), R.uniform(0, 360), R.uniform(0.7, 1.2))
for k in range(150):
    nm = R.choice(['Fern', 'Fern', 'GrassTuft', 'GrassTuft', 'Bush_A', 'Bush_B'])
    x = R.uniform(-14, 14)
    if abs(x) < 1.1:
        x += 2.2 if x >= 0 else -2.2
    inst(nm, (x, R.uniform(0.5, 30), 0.0), R.uniform(0, 360), R.uniform(0.8, 1.3))
inst('MushroomCluster', (-1.6, 2.6, 0.0), 30)
# lantern hanging from a branch of the near dead tree, warm light at its flame
lant = inst('CampLantern', (-1.75, 7.0, 2.35), 0, 1.0, with_children=True)
add = bpy.data.lights.new('lantern', 'POINT')
add.energy = 35
add.color = (1.0, 0.6, 0.28)
add.shadow_soft_size = 0.05
lo = bpy.data.objects.new('lantern_light', add)
lo.location = (-1.75, 7.0, 2.35 - 0.232)
coll.objects.link(lo)

# moonlight, night sky, volumetric fog
sun = bpy.data.lights.new('moon', 'SUN')
sun.energy = 0.9
sun.color = (0.62, 0.72, 1.0)
sun.angle = math.radians(1.5)
so = bpy.data.objects.new('moon', sun)
so.rotation_euler = (math.radians(58), 0, math.radians(150))
coll.objects.link(so)
w = bpy.data.worlds.new('fog_world')
sc.world = w
bg = w.node_tree.nodes['Background']
bg.inputs['Color'].default_value = (0.012, 0.016, 0.024, 1)
bg.inputs['Strength'].default_value = 1.0
me = bpy.data.meshes.new('fog_domain')
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(70, 80, 26), verts=bm.verts)
bmesh.ops.translate(bm, vec=(0, 22, 12.5), verts=bm.verts)
bm.to_mesh(me)
dom = bpy.data.objects.new('fog_domain', me)
fm = bpy.data.materials.new('_fog_volume')
nt = fm.node_tree
nt.nodes.remove(nt.nodes['Principled BSDF'])
vol = nt.nodes.new('ShaderNodeVolumePrincipled')
vol.inputs['Color'].default_value = (0.55, 0.62, 0.7, 1)
vol.inputs['Anisotropy'].default_value = 0.35
# denser near the ground
tc = nt.nodes.new('ShaderNodeTexCoord')
sep = nt.nodes.new('ShaderNodeSeparateXYZ')
nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
mr = nt.nodes.new('ShaderNodeMapRange')
mr.inputs['From Min'].default_value = 0.0
mr.inputs['From Max'].default_value = 6.0
mr.inputs['To Min'].default_value = 0.11
mr.inputs['To Max'].default_value = 0.03
nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
nt.links.new(mr.outputs['Result'], vol.inputs['Density'])
nt.links.new(vol.outputs['Volume'], nt.nodes['Material Output'].inputs['Volume'])
me.materials.append(fm)
coll.objects.link(dom)

cam = bpy.data.cameras.new('fog_cam')
cam.lens = 24
cam.clip_end = 200
co = bpy.data.objects.new('fog_cam', cam)
co.location = (0.4, -1.5, 1.55)
co.rotation_euler = (math.radians(86), 0, math.radians(-3))
coll.objects.link(co)
sc.camera = co
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4
sc.cycles.transparent_max_bounces = 24
sc.cycles.volume_bounces = 1
sc.cycles.volume_step_rate = 3.0
sc.cycles.volume_max_steps = 200
sc.render.resolution_x, sc.render.resolution_y = 640, 360
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Base Contrast'
sc.view_settings.exposure = 2.0
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('wrote', OUT)
