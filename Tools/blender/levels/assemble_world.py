"""Unity-equivalent world assembly for validation (Blender 4.2+/5.x or the bpy module).

    python assemble_world.py -- <project_root> [--level Bunker,Forest,Mine] [--views] [--audit] [--backface]
                                [--focus x,y,z,tx,ty,tz] [--blend out.blend]

Re-imports the *exported* level FBX files (not the generator scenes), instances the *exported* kit FBX objects at the
MK_* markers exactly the way Scripts/Editor/LevelAssembler.cs + PrefabFactory*.cs do in Unity (including the
hand-placed station parts: gate panels/buttons/lever/beacons, terminal keypad, sell buttons, elevator controls), uses
the real texture sets with the shipping look (point-filtered, low-res, distance fog per area) and then

  --views     renders the player-eye views listed in VIEWS to Docs/previews/assembly/<level>_<view>.png
  --backface  renders the same views with Workbench back-face culling (as Unity draws them) over a magenta world:
              any magenta inside a surface is a hole the player would see (inside-out or missing geometry)
  --audit     writes Docs/previews/assembly/<level>_audit.txt: floating / sunk / wall-gap props, prop-vs-level and
              prop-vs-prop intersections, duplicate placements, coplanar same-facing faces (z-fighting)

Unity <-> Blender: Unity local (x, y, z) = Blender local (-x, z, -y); Blender -Y is Unity +Z (forward).
"""
import bpy
import bmesh
import math
import os
import re
import sys
import time
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ROOT = ARGV[0] if ARGV and not ARGV[0].startswith('--') else os.path.join(HERE, '..', '..', '..')
ART = os.path.join(ROOT, 'Assets', 'MonkeyNoFear', 'Art')
TEX = os.path.join(ART, 'Textures')
OUT = os.path.join(ROOT, 'Docs', 'previews', 'assembly')


def opt(name, default=None):
    if name in ARGV:
        i = ARGV.index(name)
        return ARGV[i + 1] if i + 1 < len(ARGV) and not ARGV[i + 1].startswith('--') else True
    return default


# ============================================================================== Unity convention helpers
M_B2U = Matrix(((-1, 0, 0), (0, 0, 1), (0, -1, 0)))      # Blender local -> Unity local
M_U2B = M_B2U.inverted()


def U(x, y, z):
    """Unity-local point/direction -> Blender-local."""
    return M_U2B @ Vector((x, y, z))


def u_look(fwd, up=(0, 1, 0)):
    """Quaternion.LookRotation(fwd, up) given in Unity-local vectors -> Blender 3x3 rotation."""
    f = Vector(fwd).normalized()
    u = Vector(up)
    r = u.cross(f)
    if r.length < 1e-6:
        r = Vector((0, 1, 0)).cross(f) if abs(f.y) < 0.9 else Vector((1, 0, 0))
    r.normalize()
    u = f.cross(r)
    ru = Matrix((r, u, f)).transposed()             # columns = right, up, forward (Unity)
    return M_U2B @ ru @ M_B2U


def u_euler(x, y, z):
    """Quaternion.Euler(x, y, z) (Unity, applied Z, X, Y) -> Blender 3x3 rotation."""
    rx, ry, rz = (Matrix.Rotation(math.radians(a), 3, ax) for a, ax in ((x, 'X'), (y, 'Y'), (z, 'Z')))
    return M_U2B @ (ry @ rx @ rz) @ M_B2U


def trs(loc, rot3=None, scale=1.0):
    m = (rot3 or Matrix.Identity(3)).to_4x4()
    m = m @ Matrix.Diagonal((scale, scale, scale, 1.0))
    m.translation = Vector(loc)
    return m


# Blender's FBX importer puts its Y-up -> Z-up fix into every imported object's world matrix (world = intended @ G)
G_INV = Matrix.Rotation(-math.pi / 2, 4, 'X')


def clean(n):
    """Blender's .NNN duplicate suffix only (marker arguments contain dots: MK_SIGN_0_0.6_0.6)."""
    return re.sub(r'\.\d{3}$', '', n)


# ============================================================================== materials (MaterialFactory catalog)
LOOK = {'tex': int(opt('--tex', 128)), 'closest': True, 'normal': 0.5}
_IMG = {}


def image(set_name, suffix='_A', non_color=False):
    key = (set_name, suffix)
    if key in _IMG:
        return _IMG[key]
    path = os.path.join(TEX, f'{set_name}{suffix}.png')
    if not os.path.exists(path):
        path = os.path.join(ART, 'Models', 'Player', f'{set_name}.png')     # player_fur / player_face
    if not os.path.exists(path):
        _IMG[key] = None
        return None
    img = bpy.data.images.load(path, check_existing=True)
    n = LOOK['tex'] * (2 if set_name.endswith('atlas') else 1)
    if img.size[0] > n:
        img.scale(n, max(1, int(n * img.size[1] / img.size[0])))
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    _IMG[key] = img
    return img


def parse_catalog():
    src = open(os.path.join(ROOT, 'Assets', 'MonkeyNoFear', 'Scripts', 'Editor', 'MaterialFactory.cs')).read()
    cat = {}
    for m in re.finditer(r'D\("(MNF_\w+)",\s*Kind\.(\w+)(?:,\s*"(\w+)")?\)(?:\.tint\s*=\s*new Color\(([^)]*)\))?', src):
        tint = tuple(float(v.strip().rstrip('f')) for v in m.group(4).split(',')) if m.group(4) else None
        cat[m.group(1)] = dict(kind=m.group(2), set=m.group(3), tint=tint)
    for w in ('Crate', 'Planks', 'Rotten', 'Beam', 'Handle'):
        cat['MNF_Wood' + w] = dict(kind='Std', set='wood_' + w.lower(), tint=None)
    for f in re.findall(r'"(\w+):(\w+)"', src):
        cat['MNF_' + f[0]] = dict(kind='Std', set=f[1], tint=None)
    for m in re.finditer(r'(Flat|Emissive)\("(MNF_\w+)",\s*new Color\(([^)]*)\),\s*([\d.]+)f\)', src):
        col = tuple(float(v.strip().rstrip('f')) for v in m.group(3).split(','))
        cat[m.group(2)] = dict(kind=m.group(1), set=None, tint=col, strength=float(m.group(4)))
    cat.setdefault('MNF_Crystal', {})['emission'] = ((0.35, 0.85, 1.0), 1.6)
    cat.setdefault('MNF_Anomalous', {})['emission'] = ((1.0, 0.22, 0.12), 1.4)
    for n, c in (('MNF_Screen', ((0.04, 0.12, 0.05), 1.0)),):
        cat.setdefault(n, dict(kind='Emissive', set=None, tint=(0.01, 0.03, 0.015)))['emission'] = c
    return cat


CATALOG = {}
_MATS = {}


def _tex_node(nt, img, vec=None, box=False):
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = img
    t.interpolation = 'Closest' if LOOK['closest'] else 'Linear'
    if box:
        t.projection = 'BOX'
        t.projection_blend = 0.25
    if vec is not None:
        nt.links.new(vec, t.inputs['Vector'])
    return t


def mnf_material(name):
    base = clean(name)
    if base in _MATS:
        return _MATS[base]
    d = CATALOG.get(base, dict(kind='Std', set=None, tint=(0.5, 0.5, 0.5)))
    m = bpy.data.materials.new('PREV_' + base)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.8
    kind, s = d.get('kind', 'Std'), d.get('set')
    tint = d.get('tint')
    col_out = None
    if kind in ('Flat', 'Emissive') and not s:
        tint = tint or (0.1, 0.1, 0.1)
        bsdf.inputs['Base Color'].default_value = (*tint[:3], 1)
        if kind == 'Emissive':
            bsdf.inputs['Emission Color'].default_value = (*tint[:3], 1)
            bsdf.inputs['Emission Strength'].default_value = d.get('strength', 2.0) * 2.0
    elif kind == 'Terrain':
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(geo.outputs['Position'], sep.inputs[0])
        comb = nt.nodes.new('ShaderNodeCombineXYZ')
        for i, a in enumerate('XY'):
            mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.25
            nt.links.new(sep.outputs[a], mul.inputs[0]); nt.links.new(mul.outputs[0], comb.inputs[i])
        layers = [_tex_node(nt, image(n), comb.outputs[0]) for n in ('forest_floor', 'mud', 'moss', 'rock_dry')]
        vc = nt.nodes.new('ShaderNodeVertexColor')
        sepc = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(vc.outputs['Color'], sepc.inputs[0])
        cur = layers[0].outputs['Color']
        # like MNF/TerrainBlend: rock is triplanar (box projected) and also comes in on steep slopes
        rock_box = _tex_node(nt, image('rock_dry'), None, box=True)
        sc = nt.nodes.new('ShaderNodeVectorMath'); sc.operation = 'SCALE'; sc.inputs['Scale'].default_value = 0.25
        nt.links.new(geo.outputs['Position'], sc.inputs[0]); nt.links.new(sc.outputs[0], rock_box.inputs['Vector'])
        layers[3] = rock_box
        sepn = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(geo.outputs['Normal'], sepn.inputs[0])
        steep = nt.nodes.new('ShaderNodeMapRange'); steep.inputs['From Min'].default_value = 0.8; steep.inputs['From Max'].default_value = 0.6
        nt.links.new(sepn.outputs['Z'], steep.inputs['Value'])
        mx_ = nt.nodes.new('ShaderNodeMath'); mx_.operation = 'MAXIMUM'
        nt.links.new(sepc.outputs['Blue'], mx_.inputs[0]); nt.links.new(steep.outputs['Result'], mx_.inputs[1])
        rock_fac = mx_.outputs[0]
        for lay, ch in zip(layers[1:], ('Red', 'Green', 'Blue')):
            mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
            nt.links.new(rock_fac if ch == 'Blue' else sepc.outputs[ch], mix.inputs['Factor'])
            nt.links.new(cur, mix.inputs[6]); nt.links.new(lay.outputs['Color'], mix.inputs[7])
            cur = mix.outputs[2]
        col_out = cur
    elif s:
        img = image(s)
        if img:
            vec = None
            if kind == 'Tri':
                geo = nt.nodes.new('ShaderNodeNewGeometry')
                sc = nt.nodes.new('ShaderNodeVectorMath'); sc.operation = 'SCALE'; sc.inputs['Scale'].default_value = 1 / 3.0
                nt.links.new(geo.outputs['Position'], sc.inputs[0])
                vec = sc.outputs[0]
            t = _tex_node(nt, img, vec, box=(kind == 'Tri'))
            col_out = t.outputs['Color']
            if tint:
                mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
                mix.inputs['Factor'].default_value = 1.0
                nt.links.new(col_out, mix.inputs[6]); mix.inputs[7].default_value = (*tint[:3], 1)
                col_out = mix.outputs[2]
            if kind in ('Foliage', 'Cutout', 'Decal'):
                nt.links.new(t.outputs['Alpha'], bsdf.inputs['Alpha'])
            nimg = image(s, '_N', non_color=True)
            if nimg and LOOK['normal'] > 0 and kind != 'Tri':
                tn = _tex_node(nt, nimg, vec)
                nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = LOOK['normal']
                nt.links.new(tn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        elif tint:
            bsdf.inputs['Base Color'].default_value = (*tint[:3], 1)
    if col_out is not None:
        nt.links.new(col_out, bsdf.inputs['Base Color'])
    if 'emission' in d:
        c, k = d['emission']
        bsdf.inputs['Emission Color'].default_value = (*c, 1)
        bsdf.inputs['Emission Strength'].default_value = k * 1.5
    if kind == 'Water':
        bsdf.inputs['Base Color'].default_value = (0.02, 0.04, 0.04, 1)
        bsdf.inputs['Roughness'].default_value = 0.05
    if kind == 'Fade':
        bsdf.inputs['Alpha'].default_value = 0.3
    if base.startswith('MNF_Metal'):
        bsdf.inputs['Metallic'].default_value = 0.4
        bsdf.inputs['Roughness'].default_value = 0.55
    add_fog(m)
    m['mnf_kind'] = kind
    _MATS[base] = m
    return m


FOG = {'density': 0.0, 'color': (0.2, 0.3, 0.3)}


def add_fog(m):
    """Unity ExponentialSquared fog applied per surface: mix toward the fog colour by 1 - exp(-(density*d)^2)."""
    nt = m.node_tree
    out = nt.nodes.get('Material Output')
    src = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].links else None
    if src is None:
        return
    # Unity's trilight ambient reaches every surface (Cycles' world light would not get inside the bunker/mine)
    bsdf = nt.nodes.get('Principled BSDF')
    if bsdf and FOG.get('ambient'):
        bc = bsdf.inputs['Base Color']
        mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1.0
        if bc.links:
            nt.links.new(bc.links[0].from_socket, mul.inputs[6])
        else:
            mul.inputs[6].default_value = bc.default_value
        mul.inputs[7].default_value = (*FOG['ambient'], 1)
        aem = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(mul.outputs[2], aem.inputs['Color'])
        add = nt.nodes.new('ShaderNodeAddShader')
        nt.links.new(src, add.inputs[0]); nt.links.new(aem.outputs[0], add.inputs[1])
        src = add.outputs[0]
    cam = nt.nodes.new('ShaderNodeCameraData')
    a = nt.nodes.new('ShaderNodeMath'); a.operation = 'MULTIPLY'; a.inputs[1].default_value = FOG['density']; a.name = 'FOG_density'
    nt.links.new(cam.outputs['View Distance'], a.inputs[0])
    sq = nt.nodes.new('ShaderNodeMath'); sq.operation = 'MULTIPLY'
    nt.links.new(a.outputs[0], sq.inputs[0]); nt.links.new(a.outputs[0], sq.inputs[1])
    ex = nt.nodes.new('ShaderNodeMath'); ex.operation = 'EXPONENT'
    neg = nt.nodes.new('ShaderNodeMath'); neg.operation = 'MULTIPLY'; neg.inputs[1].default_value = -1.0
    nt.links.new(sq.outputs[0], neg.inputs[0]); nt.links.new(neg.outputs[0], ex.inputs[0])
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(ex.outputs[0], inv.inputs[1])
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*FOG['color'], 1)
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.name = 'FOG_mix'
    nt.links.new(inv.outputs[0], mix.inputs[0])
    nt.links.new(src, mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    final = mix.outputs[0]
    if bsdf and bsdf.inputs['Alpha'].links:
        # cutout cards: fog/ambient emission only where the card is opaque
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        amix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(bsdf.inputs['Alpha'].links[0].from_socket, amix.inputs[0])
        nt.links.new(tr.outputs[0], amix.inputs[1]); nt.links.new(final, amix.inputs[2])
        final = amix.outputs[0]
    nt.links.new(final, out.inputs['Surface'])


def remap_materials(objs):
    for o in objs:
        if o.type != 'MESH':
            continue
        for slot in o.material_slots:
            if slot.material and not slot.material.name.startswith('PREV_'):
                slot.material = mnf_material(slot.material.name)


# ============================================================================== kit library
KIT = {}        # name -> collection (render meshes)
KITCOL = {}     # name -> list of (local matrix, mesh) collider helpers
KITSOCK = {}    # name -> {helper name: local matrix}
KITBOUNDS = {}  # name -> (min, max) local render bounds


def bake_world(objs):
    """Bake each mesh's world matrix into its data (object space == world space), so box/triplanar projections
    behave like Unity's world-space triplanar shader. Hierarchy-derived data must be read before calling this."""
    done = set()
    for o in objs:
        if o.type != 'MESH' or o.data in done:
            continue
        mw = o.matrix_world.copy()
        o.parent = None
        o.data.transform(mw)
        o.matrix_world = Matrix.Identity(4)
        done.add(o.data)


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def load_kits():
    lib = bpy.data.collections.new('_Lib')
    bpy.context.scene.collection.children.link(lib)
    for kit in ('Kit_Bunker', 'Kit_Forest', 'Kit_Mine', 'Kit_Deposits', 'Kit_Tools'):
        new = import_fbx(os.path.join(ART, 'Models', 'Props', kit + '.fbx'))
        remap_materials(new)
        for o in new:
            for c in list(o.users_collection):
                c.objects.unlink(o)
        for top in [o for o in new if o.parent is None]:
            name = clean(top.name)
            col = bpy.data.collections.new('LIB_' + name)
            lib.children.link(col)
            # kit tops sit at the Blender origin; the importer's axis fix lives in their world matrix, so world
            # matrices *are* the kit-local Blender transforms
            inv = Matrix.Identity(4)
            KITCOL[name], KITSOCK[name] = [], {}
            mn, mx = Vector((1e9,) * 3), Vector((-1e9,) * 3)
            for o in [top] + list(top.children_recursive):
                on = clean(o.name).split('~')[0]
                local = inv @ o.matrix_world
                if on.startswith('COL_'):
                    KITCOL[name].append((on, local, o))
                    continue
                if o.type == 'EMPTY' or on.startswith('SOCKET_') or on in ('TIP', 'GRIP', 'GRIP2', 'LIGHT'):
                    KITSOCK[name][on] = local @ G_INV
                if o.type == 'MESH':
                    col.objects.link(o)
                    for v in o.bound_box:
                        p = local @ Vector(v)
                        mn = Vector(map(min, mn, p)); mx = Vector(map(max, mx, p))
            KIT[name] = col
            KITBOUNDS[name] = (mn, mx)
            bake_world(list(col.objects))
    bpy.context.view_layer.layer_collection.children['_Lib'].exclude = True


# ============================================================================== placement
PLACED = []     # dict(name, key, matrix, kind, src)
WORLD = None


def place(key, matrix, src='', kind=None):
    if key not in KIT:
        PLACED.append(dict(key=key, matrix=matrix, kind='missing', src=src, obj=None))
        return None
    e = bpy.data.objects.new('I_' + key, None)
    e.instance_type = 'COLLECTION'
    e.instance_collection = KIT[key]
    e.matrix_world = matrix
    WORLD.objects.link(e)
    mn, mx = KITBOUNDS[key]
    if kind is None:
        if key in WALL_FORCE:
            kind = 'wall'
        elif key in CEILING_FORCE:
            kind = 'ceiling'
        elif key.startswith(SPAN):
            kind = 'span'
        elif key.startswith('Rail_'):
            kind = 'floor'
        elif mx.y < 0.02 and mn.y < -0.02 and (mx.z - mn.z) < 3.5 and key not in WALL_EXCEPT:
            kind = 'wall'
        elif mx.z < 0.05:
            kind = 'ceiling'
        else:
            kind = 'floor'
    PLACED.append(dict(key=key, matrix=matrix, kind=kind, src=src, obj=e))
    return e


WALL_EXCEPT = {'LooseRockWall', 'Rail_Straight', 'Rail_Curve', 'Rail_End'}
level_is_cave = False
SPAN = ('Bridge_Broken', 'FallenTree', 'Walkway', 'Log')   # rest on their two ends
CEILING_FORCE = {'LampString', 'CampLantern', 'FluorescentFixture'}
WALL_FORCE = {'CableBundle', 'PipeRun', 'PosterBoard'}   # thin wall pieces whose bounds poke slightly behind the pivot


def box(name, center, size, mat, parent_m=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(mnf_material(mat))
    o.matrix_world = (parent_m or Matrix.Identity(4)) @ trs(center)
    WORLD.objects.link(o)
    PLACED.append(dict(key=name, matrix=o.matrix_world.copy(), kind='part', src=name, obj=o))
    return o


def quad(name, matrix, w, h, mat, cell=None, grid=4):
    me = bpy.data.meshes.new(name)
    # faces local -Y (the marker's forward), centred on the marker
    # seen from the front (from -Y) Blender +X is the viewer's right, like PrefabFactory.AtlasQuad's -X in Unity
    me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    if cell is not None:
        r, c = divmod(cell, grid)
        u0, v0 = c / grid, 1 - (r + 1) / grid
        for li, (u, v) in zip(range(4), [(0, 0), (1, 0), (1, 1), (0, 1)]):
            uv.data[li].uv = (u0 + u / grid, v0 + v / grid)
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(mnf_material(mat))
    o.matrix_world = matrix
    WORLD.objects.link(o)
    PLACED.append(dict(key=name, matrix=matrix.copy(), kind='quad', src=name, obj=o))
    return o


def light(loc, color, rng, intensity, kind='POINT'):
    l = bpy.data.lights.new('L', kind)
    l.color = color
    l.energy = intensity * rng * rng * 3.0
    l.shadow_soft_size = 0.15
    o = bpy.data.objects.new('L', l)
    o.location = loc
    WORLD.objects.link(o)
    return o


def button(parent, pos_u, out_u, body, cap):
    """PrefabFactory.MakeButton with wallMounted=true: kit model forward (+Z) along `outward`."""
    o = Vector(out_u).normalized()
    label_up = (0, 0, -1) if abs(o.y) > 0.8 else (0, 1, 0)
    rot = u_look(out_u, label_up)
    m = parent @ trs(U(*pos_u), rot)
    place(body, m, 'button', 'part')
    sock = KITSOCK.get(body, {}).get('SOCKET_Cap')
    place(cap, m @ (sock if sock else Matrix.Identity(4)), 'button', 'part')


def lever(parent, pos_u, out_u):
    m = parent @ trs(U(*pos_u), u_look(out_u))
    place('Lever_Base', m, 'lever', 'part')
    sock = KITSOCK.get('Lever_Base', {}).get('SOCKET_Handle', Matrix.Identity(4))
    place('Lever_Handle', m @ sock @ trs((0, 0, 0), Matrix.Rotation(math.radians(-50), 3, 'X')), 'lever', 'part')


def station(name, m):
    k = {'Bed': 'Bunkbed', 'Gate': 'SecurityGate_Frame'}.get(name, name)
    place(k, m, 'MK_STATION_' + name, 'floor' if name not in ('ToolRack', 'Dispenser') else 'wall')
    if name == 'Gate':
        place('SecurityGate_Bars', m, 'gate', 'part')
        for x in (-1.75, 1.75):
            for z in (-0.28, 0.28):
                place('WarningBeacon', m @ trs(U(x, 3.0, z), u_look((0, 0, 1) if z > 0 else (0, 0, -1))), 'gate', 'part')
        for pos, d, size, pn in (((2.35, 1.25, -0.18), (0, 0, -1), (0.45, 0.6, 0.05), 'PanelInside'),
                                 ((-1.98, 1.25, 1.4), (1, 0, 0), (0.05, 0.6, 0.45), 'PanelOutside')):
            box('Gate_' + pn, U(*pos), (size[0], size[2], size[1]), 'MNF_MetalPainted_Yellow', m)
            base = Vector(pos) + Vector(d) * 0.03
            button(m, base + Vector((0, 0.13, 0)), d, 'BigButton_Body', 'BigButton_Cap')
            button(m, base - Vector((0, 0.15, 0)), d, 'BigButton_Body', 'BigButton_Cap')
        lever(m, (-2.35, 1.3, -0.15), (0, 0, -1))
    elif name == 'Terminal':
        box('KeypadPlate', U(0, 0.94, 0.36), (0.78, 0.26, 0.04), 'MNF_MetalPainted_Gray', m)
        for i in range(6):
            button(m, (-0.3 + i * 0.12, 0.96, 0.34), (0, 1, 0), 'TerminalButton_Body', 'TerminalButton_Cap')
    elif name == 'SellMachine':
        for x in (-0.3, 0.3):
            button(m, (x, 0.62, 0.51), (0, 0, 1), 'BigButton_Body', 'BigButton_Cap')
    elif name == 'Bed':
        mn, mx = KITBOUNDS['Bunkbed']
        ex = (mx.x - mn.x) / 2
        button(m, (ex + 0.02, 0.9, 0), (1, 0, 0), 'BigButton_Body', 'BigButton_Cap')
    elif name == 'ToolRack':
        for i, tool in enumerate(('Pickaxe_T1', 'Flashlight', 'Spear')):
            s = KITSOCK['ToolRack'].get(f'SOCKET_{i}')
            if s:
                place(tool, m @ s @ trs((0, 0, 0), u_euler(0, 90, 0)), 'rack', 'part')


ORE = {'Shallow': 'Iron', 'Mid': 'Copper', 'Deep': 'Crystal', 'Anomalous': 'Anomalous'}
ITEM = {'food_can': 'FoodCan', 'glowstick': 'Glowstick', 'medkit': 'Medkit', 'miner_tag': 'MinerTag', 'flare': 'Flare',
        'battery': 'Battery', 'rope': 'RopeCoil'}
FIXTURE = {'Fluor': 'FluorescentFixture', 'FluorBad': 'FluorescentFixture', 'Cage': 'CageLamp', 'Emergency': 'EmergencyLight',
           'Red': 'EmergencyLight', 'MineLamp': 'MineLamp', 'MineLampDim': 'MineLamp', 'String': 'LampString', 'Camp': 'CampLantern'}
LIGHTS = {'Fluor': ((0.82, 0.9, 1), 9, 1.3, (0, 0, -0.25)), 'FluorBad': ((0.82, 0.9, 1), 9, 0.9, (0, 0, -0.25)),
          'Cage': ((1, 0.75, 0.45), 6, 1.0, (0, -0.15, 0)), 'Emergency': ((1, 0.08, 0.05), 8, 1.5, (0, -0.12, 0)),
          'Red': ((1, 0.1, 0.06), 6, 0.6, (0, -0.12, 0)), 'MineLamp': ((1, 0.68, 0.38), 7.5, 1.0, (0, -0.18, 0)),
          'MineLampDim': ((1, 0.68, 0.38), 5, 0.55, (0, -0.18, 0)), 'Crystal': ((0.4, 0.85, 1), 6, 0.6, (0, 0, 0)),
          'Spot': ((1, 0.85, 0.65), 12, 1.6, (0, 0, 0))}


def assemble(level):
    global WORLD
    WORLD = bpy.data.collections.new('W_' + level)
    bpy.context.scene.collection.children.link(WORLD)
    objs = import_fbx(os.path.join(ART, 'Models', 'Levels', level + '.fbx'))
    remap_materials(objs)
    geo, markers, elev = [], [], {}
    for o in objs:
        n = clean(o.name)
        if o.type == 'MESH' and n.startswith(('ZONE_', 'KILL_', 'GAUNTVIEW')) or (o.type == 'MESH' and 'COLONLY_' in n):
            o.hide_render = True
            continue
        if o.type == 'MESH':
            geo.append(o)
        elif n.startswith('MK_'):
            markers.append((n, o))
            o.hide_render = True
    bake_world(geo)
    for n, o in markers:
        p = n.split('_')
        t, a1 = p[1], (p[2] if len(p) > 2 else '')
        m = o.matrix_world @ G_INV
        if t == 'PROP':
            place(n[len('MK_PROP_'):], m, n)
        elif t == 'STATION':
            station(a1, m)
        elif t == 'ORE':
            dep = 'Deposit_' + ORE.get(a1, 'Iron') + ('_Wall' if n.endswith('_Wall') else '')
            place(dep if dep in KIT else dep.replace('_Wall', ''), m, n, 'wall' if n.endswith('_Wall') else 'floor')
        elif t == 'LIGHT':
            fx = FIXTURE.get(a1)
            if fx:
                place(fx, m, n)
            if a1 == 'String':
                for i in range(2):
                    light(m @ U(-1 + i * 2, -0.3, 0), (1, 0.7, 0.4), 6, 0.7)
            elif a1 in LIGHTS:
                c, r, k, off = LIGHTS[a1]
                light(m @ Vector(off) if fx else m.translation, c, r, k)
        elif t == 'FKNEST':
            place('Nest', m, n)
        elif t == 'BORER' and a1 == 'HOLE':
            place('LooseRockWall' if n.endswith('_Plug') else 'BorerHole', m, n, 'part')
        elif t == 'EVENT':
            ev = n[len('MK_EVENT_'):]
            k = {'MinecartNudge': 'Minecart', 'WallScratch': 'ScratchedPlate', 'LightTurnsOn': 'MineLamp', 'PARecording': 'PA_Speaker'}.get(ev)
            if k:
                place(k, m, n)
        elif t == 'SIGN':
            w = float(p[3]) if len(p) > 3 else 0.6
            h = float(p[4]) if len(p) > 4 else 0.6
            quad(n, m @ trs(U(0, 0, 0.02)), w, h, 'MNF_Signs', int(a1) if a1.isdigit() else 0)
        elif t == 'DECAL':
            s = float(p[3]) if len(p) > 3 else 0.8
            quad(n, m @ trs(U(0, 0, 0.01)), s, s, 'MNF_Decals', int(a1) if a1.isdigit() else 0)
        elif t == 'ITEM':
            k = ITEM.get(n[len('MK_ITEM_'):])
            if k:
                place(k, m, n, 'item')
        elif t == 'LORE':
            place('LoreTape' if n.endswith('_Tape') else 'Clipboard', m, n, 'item')
        elif t == 'ELEV':
            elev[a1] = m
        elif t == 'ROPE':
            ln = float(a1) if a1.replace('.', '').isdigit() else 8.0
            box(n, m.translation - Vector((0, 0, ln / 2)), (0.04, 0.04, ln), 'MNF_Rope')
    if 'Top' in elev:
        top = elev['Top']
        place('Elevator_Platform', top, 'elevator', 'part')
        box('ElevControlBox', U(1.4, 1.05, 0.9), (0.1, 0.3, 0.4), 'MNF_MetalPainted_Yellow', top)
        button(top, (1.35, 1.1, 0.9), (-1, 0, 0), 'BigButton_Body', 'BigButton_Cap')
        for k in ('CallTop', 'CallBottom'):
            if k in elev:
                button(elev[k], (0, 0, 0), (0, 0, 1), 'BigButton_Body', 'BigButton_Cap')
        if 'Breaker' in elev:
            lever(elev['Breaker'], (0, 0, 0), (0, 0, 1))
    return geo


# ============================================================================== look: world, fog, cameras
AREA_LOOK = {   # mirrors DataFactory.BuildAtmospheres: ambient (~trilight equator), strength, fog colour, fog half-distance
    'Bunker': ((0.45, 0.47, 0.5), 1.0, (0.6, 0.64, 0.68), math.sqrt(math.log(2)) / 0.006),
    'Forest': ((0.22, 0.3, 0.3), 1.0, (0.21, 0.33, 0.32), math.sqrt(math.log(2)) / 0.026),
    'Mine': ((0.13, 0.2, 0.2), 1.0, (0.05, 0.1, 0.1), math.sqrt(math.log(2)) / 0.03),
}


def setup_look(level, backface=False):
    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.cycles.samples = int(opt('--samples', 12))
    scn.cycles.use_denoising = True
    scn.cycles.max_bounces = 3
    scn.render.resolution_x, scn.render.resolution_y = 960, 540
    amb, k, fog, half = AREA_LOOK[level]
    if not scn.world:
        scn.world = bpy.data.worlds.new('W')
    scn.world.use_nodes = True
    bg = scn.world.node_tree.nodes['Background']
    bg.inputs[0].default_value = (*fog, 1)
    bg.inputs[1].default_value = k
    for m in _MATS.values():
        d = m.node_tree.nodes.get('FOG_density')
        if d:
            d.inputs[1].default_value = 0.0 if backface else FOG['density']
    if backface:
        bg.inputs[0].default_value = (1, 0, 1, 1)
        bg.inputs[1].default_value = 1.0
        scn.cycles.transparent_max_bounces = 16


def backface_materials(on):
    for m in list(_MATS.values()):
        nt = m.node_tree
        out = nt.nodes.get('Material Output')
        if on:
            if m.get('mnf_kind') in ('Foliage', 'Decal', 'Fade', 'Cutout'):
                continue       # rendered two-sided / blended in Unity
            geo = nt.nodes.new('ShaderNodeNewGeometry'); geo.name = 'BF_geo'
            # Unity culls back faces: render them transparent; whatever then shows the magenta world behind a
            # surface is a hole the player would see (inside-out or missing faces)
            em = nt.nodes.new('ShaderNodeBsdfTransparent'); em.name = 'BF_em'
            mixs = nt.nodes.new('ShaderNodeMixShader'); mixs.name = 'BF_mix'
            fog = nt.nodes.get('FOG_mix')
            target = fog.inputs[1] if fog else out.inputs['Surface']
            src = target.links[0].from_socket
            nt.links.new(geo.outputs['Backfacing'], mixs.inputs[0])
            nt.links.new(src, mixs.inputs[1])
            nt.links.new(em.outputs[0], mixs.inputs[2])
            nt.links.new(mixs.outputs[0], target)


def render(path, cam, target, lens=16):
    scn = bpy.context.scene
    co = bpy.data.objects.get('AsmCam')
    if not co:
        co = bpy.data.objects.new('AsmCam', bpy.data.cameras.new('AsmCam'))
        scn.collection.objects.link(co)
    co.data.lens = lens
    co.data.clip_start = 0.03
    co.data.clip_end = 400
    co.location = cam
    co.rotation_euler = (Vector(target) - Vector(cam)).to_track_quat('-Z', 'Y').to_euler()
    scn.camera = co
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)


EYE = 1.25   # monkey eye height above the floor
VIEWS = {
    'Bunker': {
        'hall_from_bed': ((-6.5, -10.5, -10 + EYE + 0.6), (2, 3, -10 + 1.0)),
        'gate_inside': ((0.5, -2.5, -10 + EYE), (0.5, 4.2, -10 + 1.3)),
        'workbench': ((-4.4, 0.6, -10 + EYE), (-5.4, 3.6, -10 + 1.0)),
        'terminal': ((-6.4, 2.2, -10 + EYE + 0.2), (-6.65, 3.45, -10 + 0.9)),
        'sell_storage': ((3.0, -0.5, -10 + EYE), (7.5, 0.2, -10 + 1.1)),
        'gate_corridor': ((0.6, 10.0, -10 + 1.2 + EYE), (0.0, 4.3, -10 + 1.4)),
        'corridor_up': ((0.0, 6.0, -10 + EYE), (0.0, 30.0, -4.0)),
        'bunks': ((-9.2, -3.2, -10 + EYE + 0.4), (-15.5, -8.0, -10 + 0.8)),
        'mess': ((3.6, -3.4, -10 + EYE + 0.3), (-0.5, -8.0, -10 + 0.6)),
        'gate_beacon': ((-0.9, 5.4, -10 + 2.7), (-1.75, 4.4, -10 + 3.0)),
        'generator': ((9.5, -4.0, -10 + EYE), (12.5, -7.0, -10 + 0.8)),
    },
    'Forest': {
        'portal_exit': ((0.0, 47.0, 1.5 + EYE), (0.0, 80.0, 1.5)),
        'back_at_portal': ((0.0, 66.0, 2.0 + EYE), (0.0, 46.0, 1.5)),
        'camp': ((-28.0, 88.0, 3.0), (-38.0, 100.0, 1.0)),
        'river_ford': ((62.0, 108.0, 2.5), (72.0, 128.0, 0.5)),
        'mine_approach': ((25.0, 205.0, 4.0), (25.0, 232.0, 4.0)),
        'mine_mouth': ((25.0, 226.0, 4.6), (25.0, 240.0, 3.6)),
        'watchtower_deck': ((-46.9, 186.4, 14.6), (-47.7, 187.3, 12.3)),
        'fallen_tree': ((-46.0, 96.0, 2.2), (-40.0, 102.0, 0.5)),
        'edge_west_high': ((-112.0, 120.0, 22.0), (-150.0, 120.0, 22.0)),
        'edge_south_high': ((30.0, -28.0, 22.0), (30.0, -62.0, 20.0)),
        'edge_north_high': ((-60.0, 215.0, 30.0), (-60.0, 245.0, 32.0)),
        'edge_west': ((-130.0, 120.0, 4.0), (-160.0, 120.0, 4.0)),
        'edge_east': ((130.0, 80.0, 4.0), (160.0, 80.0, 4.0)),
        'edge_south': ((40.0, -40.0, 4.0), (40.0, -70.0, 4.0)),
    },
    'Forest+Mine': {
        'junction_out': ((25.0, 224.0, 4.0 + EYE), (25.0, 245.0, 3.6)),
        'junction_in': ((25.0, 244.0, 3.3 + EYE), (25.0, 222.0, 5.0)),
    },
    'Mine': {
        'entrance_in': ((25.0, 236.0, 4.0 + EYE), (25.0, 265.0, 2.0)),
        'entrance_out': ((25.0, 252.0, 3.0 + EYE), (25.0, 232.0, 4.5)),
        'hall': ((16.0, 270.0, 1.0 + EYE + 1.0), (32.0, 282.0, 1.5)),
        'lift_top': ((12.0, 282.0, 1.0 + EYE), (5.0, 282.0, 1.5)),
        'gallery': ((20.0, 293.5, -25 + EYE), (-8.0, 297.0, -25 + 1.3)),
        'grind': ((62.0, 327.0, -25 + EYE + 1.0), (78.0, 338.0, -24.0)),
        'flood': ((40.0, 285.0, -25 + EYE), (60.0, 274.0, -25.5)),
        'chasm': ((40.0, 397.5, -55 + EYE), (36.0, 428.0, -82.0)),
        'pit_bridge': ((12.0, 368.0, -55 + EYE), (-10.0, 370.0, -56.0)),
        'deep_hub': ((40.0, 358.0, -55 + EYE), (40.0, 372.0, -54.0)),
    },
}


# ============================================================================== audits
def world_bvh(objs, depsgraph):
    verts, polys = [], []
    for o in objs:
        ev = o.evaluated_get(depsgraph)
        me = ev.to_mesh()
        mw = o.matrix_world
        off = len(verts)
        verts.extend(mw @ v.co for v in me.vertices)
        polys.extend([off + i for i in p.vertices] for p in me.polygons)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None, verts, polys


def instance_mesh(rec, colliders=False):
    """World-space (verts, polys) of a placed instance: render meshes, or the COL_ helpers."""
    verts, polys = [], []
    if rec['kind'] in ('part', 'quad') and rec['obj'] is not None and rec['obj'].type == 'MESH':
        o = rec['obj']
        verts = [o.matrix_world @ v.co for v in o.data.vertices]
        polys = [list(p.vertices) for p in o.data.polygons]
        return verts, polys
    key = rec['key']
    if key not in KIT:
        return verts, polys
    srcs = [(l, o) for (_, l, o) in KITCOL.get(key, [])] if colliders else []
    if colliders and not srcs:
        return verts, polys
    if not colliders:
        top = None
        for o in KIT[key].objects:
            srcs.append((None, o))
    for local, o in srcs:
        if o.type != 'MESH':
            continue
        if local is None:
            # render meshes: their world matrix inside the library is relative to the kit top at the origin
            local = o.matrix_world
        mw = rec['matrix'] @ local
        off = len(verts)
        verts.extend(mw @ v.co for v in o.data.vertices)
        polys.extend([off + i for i in p.vertices] for p in o.data.polygons)
    return verts, polys


SKIP_INTERSECT = ('Fence', 'SignPost', 'WarningBoard', 'Tent', 'Campfire', 'Tree_', 'Rock_', 'Boulder', 'CliffChunk', 'Bush', 'Fern', 'GrassTuft', 'Mushroom', 'Stump', 'Log',
                  'FallenTree', 'Rail_', 'RubblePile', 'LooseRockWall', 'BorerHole', 'Deposit_', 'Nest', 'Burrow',
                  'MineEntrance', 'Bridge_Broken', 'Cabin_Ruin', 'Watchtower', 'Minecart_Abandoned')
EMBED_OK = ('SupportFrame_Broken', 'Tree_', 'Rock_', 'Boulder', 'CliffChunk', 'Stump', 'FallenTree', 'Log', 'RubblePile', 'Deposit_', 'Nest',
            'Burrow', 'MineEntrance', 'Bridge_Broken', 'Cabin_Ruin', 'Watchtower', 'Minecart_Abandoned', 'Fence', 'SignPost',
            'WarningBoard', 'Tent', 'Campfire', 'BorerHole', 'LooseRockWall', 'Bush', 'Fern', 'GrassTuft', 'Mushroom')


def audit(level, geo, path):
    global level_is_cave
    level_is_cave = 'Mine' in level or 'Bunker' in level
    t0 = time.time()
    dg = bpy.context.evaluated_depsgraph_get()
    lvl_bvh, lvl_v, lvl_p = world_bvh([g for g in geo if not clean(g.name).startswith(('WATER_', 'NOCOL_DECAL'))], dg)
    lines = [f'# {level} assembly audit ({len(PLACED)} placed parts, {len(lvl_p)} level polys)', '']
    issues = {'missing': [], 'float': [], 'sunk': [], 'wallgap': [], 'embedded': [], 'dupe': [], 'overlap': [], 'coplanar': [], 'level_x': [], 'sign': []}

    # all other placed instances as one BVH for support checks (props standing on props)
    prop_bvh_data = [instance_mesh(r) for r in PLACED]

    def ray(origin, d, dist, skip=-1):
        best = None
        h = lvl_bvh.ray_cast(origin, d, dist) if lvl_bvh else (None,)
        if h[0] is not None:
            best = h[3]
        return best

    for i, r in enumerate(PLACED):
        key, m, kind = r['key'], r['matrix'], r['kind']
        if kind == 'missing':
            issues['missing'].append(f"{r['src']}: no kit object '{key}'")
            continue
        if key not in KITBOUNDS:
            continue
        mn, mx = KITBOUNDS[key]
        loc = m.translation
        if kind in ('floor', 'item'):
            # five points on the footprint, cast down from 0.6 m above the base
            pts = [Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))]
            for fx in (0.25, 0.75):
                for fy in (0.25, 0.75):
                    pts.append(Vector((mn.x + (mx.x - mn.x) * fx, mn.y + (mx.y - mn.y) * fy, mn.z)))
            gaps = []
            # start above the prop so sunk props still find their ground, but inside caves stay under the ceiling
            up = min((mx.z - mn.z) + 0.5, 1.2) if level_is_cave else (mx.z - mn.z) + 0.5
            for p in pts:
                w = m @ p
                d = ray(w + Vector((0, 0, up)), Vector((0, 0, -1)), up + 30.0)
                gaps.append(None if d is None else d - up)
            # stacked on another placed prop? (crates on crates, radio on a table, ...)
            valid = [g for g in gaps if g is not None]
            if not valid:
                issues['float'].append(f"{key} @ {tuple(round(c, 2) for c in loc)} ({r['src']}): no ground below")
                continue
            if min(valid) > 0.06 and not on_other_prop(i, m, mn, prop_bvh_data):
                issues['float'].append(f"{key} @ {tuple(round(c, 2) for c in loc)} ({r['src']}): floats {min(valid):.2f} m")
            tol = (1.6 if key.startswith(('Boulder', 'CliffChunk', 'MineEntrance', 'Rock_')) else 0.7) if key.startswith(EMBED_OK) else 0.12
            if max(valid) < -tol:
                issues['sunk'].append(f"{key} @ {tuple(round(c, 2) for c in loc)} ({r['src']}): base {-max(valid):.2f} m below ground")
        elif kind == 'span':
            # the two ends (10 % in from each end of the long axis) must touch something
            long_x = (mx.x - mn.x) >= (mx.y - mn.y)
            ends = []
            for f in (0.1, 0.9):
                p = Vector((mn.x + (mx.x - mn.x) * f, (mn.y + mx.y) / 2, mn.z)) if long_x else Vector(((mn.x + mx.x) / 2, mn.y + (mx.y - mn.y) * f, mn.z))
                w = m @ p
                d = ray(w + Vector((0, 0, 3.0)), Vector((0, 0, -1)), 40.0)
                ends.append(None if d is None else d - 3.0)
            if any(g is None or g > 0.25 for g in ends):
                issues['float'].append(f"{key} @ {tuple(round(c, 2) for c in loc)} ({r['src']}): span ends gap {[None if g is None else round(g, 2) for g in ends]}")
        elif kind == 'wall':
            fwd = (m.to_3x3() @ Vector((0, -1, 0))).normalized()
            centre = m @ Vector(((mn.x + mx.x) / 2, 0, (mn.z + mx.z) / 2))
            d = ray(centre + fwd * 0.25, -fwd, 1.0)
            near = local_bvh(loc, 2.0, prop_bvh_data, skip=r)
            if near:
                h = near.ray_cast(centre + fwd * 0.25, -fwd, 1.0)
                if h[0] is not None and (d is None or h[3] < d):
                    d = h[3]
            gap = None if d is None else d - 0.25
            if gap is None or gap > 0.05:
                issues['wallgap'].append(f"{key} @ {tuple(round(c, 2) for c in loc)} ({r['src']}): " + ('no wall behind' if gap is None else f'{gap:.2f} m off the wall'))
            elif gap < -0.08 and not key.startswith(EMBED_OK):
                issues['embedded'].append(f"{key} @ {tuple(round(c, 2) for c in loc)} ({r['src']}): {-gap:.2f} m inside the wall")

    # signs/decals: every corner must sit on a surface (no overhang into air, no corner buried in a side wall)
    for r in PLACED:
        if r['kind'] != 'quad':
            continue
        o = r['obj']
        fwd = (r['matrix'].to_3x3() @ Vector((0, -1, 0))).normalized()
        bad = []
        near = local_bvh(r['matrix'].translation, 3.0, prop_bvh_data, skip=r)
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            d = ray(w + fwd * 0.15, -fwd, 0.3)
            if near:
                h = near.ray_cast(w + fwd * 0.15, -fwd, 0.3)
                if h[0] is not None and (d is None or h[3] < d):
                    d = h[3]
            if d is None or d > 0.15 + 0.05:
                bad.append('overhangs')
            elif d < 0.15 - 0.004:
                bad.append('buried')
        if bad:
            issues['sign'].append(f"{r['src']} @ {tuple(round(c, 2) for c in r['matrix'].translation)}: corners {sorted(set(bad))} ({len(bad)}/4)")

    # duplicates: same kit object at (almost) the same transform
    seen = {}
    for r in PLACED:
        if r['kind'] == 'missing' or r['obj'] is None:
            continue
        k = (r['key'], tuple(round(c * 10) for c in r['matrix'].translation))
        if k in seen:
            issues['dupe'].append(f"{r['key']} twice @ {tuple(round(c, 2) for c in r['matrix'].translation)} ({seen[k]} / {r['src']})")
        seen[k] = r['src']

    # prop vs level geometry: render-mesh triangles crossing level triangles
    if lvl_bvh:
        for i, r in enumerate(PLACED):
            if r['kind'] in ('missing', 'quad') or r['key'].startswith(SKIP_INTERSECT) or r['src'] in ('button', 'lever'):
                continue
            v, p = prop_bvh_data[i]
            if not p:
                continue
            # lift 2 cm off the mounting surface: resting contact is not an intersection
            m3 = r['matrix'].to_3x3()
            lift = {'floor': Vector((0, 0, 0.02)), 'ceiling': Vector((0, 0, -0.02))}.get(r['kind'], m3 @ Vector((0, -0.02, 0)))
            b = BVHTree.FromPolygons([Vector(x) + lift for x in v], p)
            n = len(b.overlap(lvl_bvh))
            if n > (12 if r['kind'] == 'wall' else 4):
                c = sum((Vector(x) for x in v), Vector()) / len(v)
                issues['level_x'].append(f"{r['key']} @ {tuple(round(x, 2) for x in c)} ({r['src']}): {n} triangle pairs cross level geometry")

    # prop vs prop (collider helpers when available, else render meshes); bbox prefilter on a grid
    boxes = []
    for i, r in enumerate(PLACED):
        if r['kind'] in ('missing', 'quad') or r['src'] in ('button', 'lever'):
            continue
        if r['key'].startswith(('Bush', 'Fern', 'GrassTuft', 'Mushroom', 'Rock_', 'Rail_')):
            continue
        v, p = instance_mesh(r, colliders=True)
        if not p:
            v, p = prop_bvh_data[i]
        if not p:
            continue
        mn_ = Vector(map(min, *v)) if len(v) > 1 else Vector(v[0]); mx_ = Vector(map(max, *v)) if len(v) > 1 else Vector(v[0])
        boxes.append((i, mn_, mx_, v, p))
    cell = {}
    for b in boxes:
        k = (int(b[1].x // 8), int(b[1].y // 8))
        cell.setdefault(k, []).append(b)
    checked = set()
    for (cx, cy), lst in cell.items():
        neigh = [b for dx in (-1, 0, 1) for dy in (-1, 0, 1) for b in cell.get((cx + dx, cy + dy), [])]
        for a in lst:
            for b in neigh:
                if a[0] >= b[0] or (a[0], b[0]) in checked:
                    continue
                checked.add((a[0], b[0]))
                if any(a[2][j] < b[1][j] or b[2][j] < a[1][j] for j in range(3)):
                    continue
                ra, rb = PLACED[a[0]], PLACED[b[0]]
                if ra['src'] == rb['src'] and ra['kind'] == 'part':
                    continue
                ta, tb = BVHTree.FromPolygons(a[3], a[4]), BVHTree.FromPolygons(b[3], b[4])
                n = len(ta.overlap(tb))
                if n:
                    both_nature = ra['key'].startswith(EMBED_OK) and rb['key'].startswith(EMBED_OK)
                    if both_nature and n < 40:
                        continue
                    c = (a[1] + a[2]) / 2
                    issues['overlap'].append(f"{ra['key']} x {rb['key']} @ {tuple(round(x, 2) for x in c)} ({n} pairs)")

    # coplanar same-facing faces of different objects (z-fighting); level geometry + quads + boxes
    planes = {}
    def add_faces(tag, verts, polys, mats=None):
        for pi, poly in enumerate(polys):
            if len(poly) < 3:
                continue
            a, b, c = (Vector(verts[poly[0]]), Vector(verts[poly[1]]), Vector(verts[poly[2]]))
            n = (b - a).cross(c - a)
            if n.length < 1e-8:
                continue
            area = n.length
            n.normalize()
            d = n.dot(a)
            k = (round(n.x, 2), round(n.y, 2), round(n.z, 2), round(d * 200))
            planes.setdefault(k, []).append((tag, [Vector(verts[i]) for i in poly], n, area, mats[pi] if mats else ''))
    for g in geo:
        if clean(g.name).startswith(('WATER_', 'NOCOL_')) and level != 'Bunker':
            continue
        me = g.data
        mw = g.matrix_world
        mnames = [clean(ms.material.name) if ms.material else '' for ms in g.material_slots]
        add_faces(clean(g.name), [mw @ v.co for v in me.vertices], [list(p.vertices) for p in me.polygons],
                  [mnames[p.material_index] if p.material_index < len(mnames) else '' for p in me.polygons])
    for i, r in enumerate(PLACED):
        if r['kind'] in ('quad', 'part') and r['obj'] is not None and r['obj'].type == 'MESH':
            add_faces(r['src'], *prop_bvh_data[i])
    for k, faces in planes.items():
        if len(faces) < 2 or len(faces) > 400:
            continue
        for x in range(len(faces)):
            for y in range(x + 1, len(faces)):
                fa, fb = faces[x], faces[y]
                # same mesh counts too (the level shells are single meshes); edge-sharing faces have no overlap area.
                # Same mesh + same material = same world-space UVs and texels: overlapping, but cannot flicker.
                if fa[0] == fb[0] and fa[4] == fb[4]:
                    continue
                if overlap_2d(fa[1], fb[1], fa[2]):
                    c = sum(fa[1], Vector()) / len(fa[1])
                    issues['coplanar'].append(f"{fa[0]}:{fa[4]} / {fb[0]}:{fb[4]} @ {tuple(round(v, 2) for v in c)} normal {tuple(round(v, 2) for v in fa[2])}")
    seen_c = []
    for s in issues['coplanar']:
        if s not in seen_c:
            seen_c.append(s)
    issues['coplanar'] = seen_c

    for k, v in issues.items():
        lines.append(f'## {k}: {len(v)}')
        lines.extend('  ' + s for s in v[:200])
        lines.append('')
    lines.append(f'(audit {time.time() - t0:.1f}s)')
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    print('\n'.join(f'{k}: {len(v)}' for k, v in issues.items()))
    return issues


def local_bvh(centre, radius, data, skip=None):
    verts, polys = [], []
    for j, (v, p) in enumerate(data):
        r = PLACED[j]
        if r is skip or not p or (r['matrix'].translation - centre).length > radius + 6.0:
            continue
        off = len(verts)
        verts.extend(v)
        polys.extend([off + i for i in poly] for poly in p)
    return BVHTree.FromPolygons(verts, polys) if polys else None


def on_other_prop(i, m, mn, data):
    w = m @ Vector((0, 0, mn.z))
    for j, (v, p) in enumerate(data):
        if j == i or not p:
            continue
        r = PLACED[j]
        if (r['matrix'].translation - w).length > 4.0:
            continue
        t = BVHTree.FromPolygons(v, p)
        h = t.ray_cast(w + Vector((0, 0, 0.05)), Vector((0, 0, -1)), 0.2)
        if h[0] is not None:
            return True
    return False


def overlap_2d(pa, pb, n):
    """Do two coplanar convex polygons overlap with positive area? (separating axis in the plane)"""
    ax = n.orthogonal().normalized()
    ay = n.cross(ax)
    A = [(p.dot(ax), p.dot(ay)) for p in pa]
    B = [(p.dot(ax), p.dot(ay)) for p in pb]
    for poly in (A, B):
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            nx, ny = y2 - y1, x1 - x2
            pa_ = [nx * x + ny * y for x, y in A]
            pb_ = [nx * x + ny * y for x, y in B]
            if max(pa_) <= min(pb_) + 1e-4 or max(pb_) <= min(pa_) + 1e-4:
                return False
    return True


# ============================================================================== main
def main():
    levels = (opt('--level') or 'Bunker,Forest,Mine').split(',')
    os.makedirs(OUT, exist_ok=True)
    CATALOG.update(parse_catalog())
    for level in levels:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        KIT.clear(); KITCOL.clear(); KITSOCK.clear(); KITBOUNDS.clear(); PLACED.clear(); _MATS.clear(); _IMG.clear()
        t0 = time.time()
        look = level.split('+')[0]
        _amb, _k, fogc, half = AREA_LOOK[look]
        FOG['color'] = fogc
        FOG['ambient'] = tuple(c * _k for c in _amb)
        FOG['density'] = math.sqrt(math.log(2.0)) / half
        load_kits()
        geo = []
        for part in level.split('+'):
            geo += assemble(part)
        print(f'{level}: {len(geo)} level meshes, {len(PLACED)} placed parts ({time.time() - t0:.1f}s)')
        if opt('--audit'):
            audit(level, geo, os.path.join(OUT, f'{level}_audit.txt'))
        views = dict(VIEWS.get(level, VIEWS.get(look, {})))
        if opt('--only'):
            views = {k: v for k, v in views.items() if k in opt('--only').split(',')}
        if opt('--focus'):
            f = [float(x) for x in opt('--focus').split(',')]
            views = {'focus': ((f[0], f[1], f[2]), (f[3], f[4], f[5]))}
        if opt('--views'):
            setup_look(look)
            for vn, (cam, tgt) in views.items():
                render(os.path.join(OUT, f'{level}_{vn}.png'), cam, tgt)
        if opt('--backface'):
            # Workbench rasterises with real back-face culling (exactly Unity's Cull Back, including coincident
            # double-sided copies). Needs EGL (Mesa llvmpipe is fine: EGL_PLATFORM=surfaceless).
            scn = bpy.context.scene
            scn.render.engine = 'BLENDER_WORKBENCH'
            sh = scn.display.shading
            sh.show_backface_culling = True
            sh.color_type = 'TEXTURE'
            sh.light = 'STUDIO'
            if not scn.world:
                scn.world = bpy.data.worlds.new('W')
            scn.world.color = (1, 0, 1)
            for vn, (cam, tgt) in views.items():
                render(os.path.join(OUT, f'{level}_{vn}_culled.png'), cam, tgt)
        if opt('--blend'):
            bpy.ops.wm.save_as_mainfile(filepath=opt('--blend').replace('{level}', level))


if __name__ == '__main__':
    main()
