"""propkit_b_helpers - shared helpers for the Kit_Forest / Kit_Mine prop generators (artist B).

Runs inside Blender (bpy as a module or `blender -b -P`).  Provides:
  * catalog material creation (preview node setups; only the *name* matters for Unity)
  * MB: a lightweight mesh builder (verts / faces / per-loop UVs / material per face / custom normals)
  * primitives: beams/planks, boxes, cylinders, swept tubes, alpha cards, hull rocks
  * helper objects: COL_* boxes / convex hulls, empties (TIP / SOCKET_*), child meshes with own pivot
  * FBX export with the spec settings (+ duplicate-name handling, see export_kit)
  * manifest writing, tri counting

Child objects that need the *same* name under several top-level objects (COL_Trunk, Board, Bulb ...)
are named "<Name>~<Owner>" inside Blender (Blender names are unique); the exporter strips everything
from "~" so the FBX node is called exactly "<Name>".
"""
import bpy, bmesh, math, random, os, sys, json, re
from mathutils import Vector, Matrix, Euler, Quaternion, noise

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TEX_DIR = os.path.join(ROOT, 'Assets', 'MonkeyNoFear', 'Art', 'Textures')
PROPS_OUT = os.path.join(ROOT, 'Assets', 'MonkeyNoFear', 'Art', 'Models', 'Props')
SRC_OUT = os.path.join(ROOT, 'SourceArt', 'Props')
PREV_OUT = os.path.join(ROOT, 'Docs', 'previews', 'props')
PREVIEW_TEX = os.path.join(SRC_OUT, 'preview_tex')

# --------------------------------------------------------------------------------------------
# Material catalog (spec section 2).  name -> (texture set, preview colour, roughness, metallic, kind)
# kind: std | cut (alpha cutout card) | emit | glass | tri (triplanar) | flat
# --------------------------------------------------------------------------------------------
CATALOG = {
    'MNF_ConcreteWall': ('concrete_wall', (0.30, 0.30, 0.29), 0.9, 0.0, 'std'),
    'MNF_ConcreteFloor': ('concrete_floor', (0.20, 0.20, 0.19), 0.85, 0.0, 'std'),
    'MNF_MetalGrate': ('metal_grate', (0.22, 0.21, 0.20), 0.6, 0.8, 'grate'),
    'MNF_MetalDiamond': ('metal_diamond', (0.35, 0.34, 0.33), 0.5, 0.9, 'std'),
    'MNF_MetalRusted': ('metal_rusted', (0.30, 0.14, 0.06), 0.85, 0.3, 'rust'),
    'MNF_MetalPainted_Green': ('metal_painted', (0.14, 0.24, 0.13), 0.6, 0.2, 'paint'),
    'MNF_MetalPainted_Gray': ('metal_painted', (0.30, 0.31, 0.31), 0.6, 0.2, 'paint'),
    'MNF_MetalPainted_Yellow': ('metal_painted', (0.62, 0.45, 0.06), 0.55, 0.2, 'paint'),
    'MNF_MetalPainted_Red': ('metal_painted', (0.45, 0.06, 0.04), 0.55, 0.2, 'paint'),
    'MNF_MetalBare': ('metal_bare', (0.55, 0.55, 0.55), 0.35, 1.0, 'std'),
    'MNF_Hazard': ('hazard_stripes', (0.6, 0.45, 0.05), 0.6, 0.2, 'hazard'),
    'MNF_Rubber': ('rubber', (0.04, 0.04, 0.04), 0.7, 0.0, 'std'),
    'MNF_Plastic_Yellow': ('plastic', (0.65, 0.48, 0.05), 0.45, 0.0, 'std'),
    'MNF_Plastic_Orange': ('plastic', (0.65, 0.22, 0.03), 0.45, 0.0, 'std'),
    'MNF_Plastic_Black': ('plastic', (0.03, 0.03, 0.03), 0.45, 0.0, 'std'),
    'MNF_Plastic_Gray': ('plastic', (0.25, 0.25, 0.25), 0.45, 0.0, 'std'),
    'MNF_WoodCrate': ('wood_crate', (0.32, 0.22, 0.12), 0.8, 0.0, 'wood'),
    'MNF_WoodPlanks': ('wood_planks', (0.25, 0.19, 0.13), 0.85, 0.0, 'wood'),
    'MNF_WoodRotten': ('wood_rotten', (0.16, 0.12, 0.08), 0.9, 0.0, 'wood'),
    'MNF_WoodBeam': ('wood_beam', (0.24, 0.16, 0.09), 0.85, 0.0, 'wood'),
    'MNF_WoodHandle': ('wood_handle', (0.40, 0.27, 0.15), 0.6, 0.0, 'wood'),
    'MNF_BarkPine': ('bark_pine', (0.13, 0.09, 0.07), 0.9, 0.0, 'bark'),
    'MNF_BarkDead': ('bark_dead', (0.105, 0.095, 0.085), 0.9, 0.0, 'bark'),
    'MNF_FoliagePine': ('foliage_pine', (0.05, 0.09, 0.05), 0.8, 0.0, 'cut'),
    'MNF_FoliageLeaf': ('foliage_leaf', (0.09, 0.12, 0.05), 0.8, 0.0, 'cut'),
    'MNF_Fern': ('fern', (0.08, 0.14, 0.05), 0.8, 0.0, 'cut'),
    'MNF_Grass': ('grass', (0.12, 0.15, 0.06), 0.8, 0.0, 'cut'),
    'MNF_ForestFloor': ('forest_floor', (0.10, 0.08, 0.05), 0.95, 0.0, 'std'),
    'MNF_Mud': ('mud', (0.09, 0.07, 0.05), 0.7, 0.0, 'std'),
    'MNF_Moss': ('moss', (0.10, 0.16, 0.05), 0.95, 0.0, 'std'),
    'MNF_Terrain': ('forest_floor', (0.10, 0.08, 0.05), 0.95, 0.0, 'std'),
    'MNF_RockDry': ('rock_dry', (0.21, 0.2, 0.185), 0.9, 0.0, 'rock'),
    'MNF_RockWet': ('rock_wet', (0.15, 0.15, 0.15), 0.4, 0.0, 'rock'),
    'MNF_RockMine': ('rock_mine', (0.20, 0.18, 0.16), 0.85, 0.0, 'rock'),
    'MNF_RockDry_Tri': ('rock_dry', (0.21, 0.2, 0.185), 0.9, 0.0, 'tri'),
    'MNF_RockWet_Tri': ('rock_wet', (0.15, 0.15, 0.15), 0.4, 0.0, 'tri'),
    'MNF_RockMine_Tri': ('rock_mine', (0.20, 0.18, 0.16), 0.85, 0.0, 'tri'),
    'MNF_OreIron': ('ore_iron', (0.18, 0.16, 0.15), 0.5, 0.6, 'rock'),
    'MNF_OreCopper': ('ore_copper', (0.40, 0.20, 0.10), 0.5, 0.4, 'rock'),
    'MNF_Crystal': ('crystal', (0.3, 0.6, 0.7), 0.1, 0.0, 'emit'),
    'MNF_Blackstone': ('blackstone', (0.02, 0.02, 0.025), 0.15, 0.0, 'std'),
    'MNF_Anomalous': ('anomalous', (0.4, 0.1, 0.5), 0.3, 0.0, 'emit'),
    'MNF_FurRotten': ('fur_rotten', (0.15, 0.12, 0.09), 0.95, 0.0, 'std'),
    'MNF_SkinDecayed': ('skin_decayed', (0.45, 0.40, 0.33), 0.6, 0.0, 'std'),
    'MNF_FurRabbit': ('fur_rabbit', (0.40, 0.35, 0.30), 0.9, 0.0, 'std'),
    'MNF_FurRabbitMangy': ('fur_rabbit_mangy', (0.35, 0.30, 0.25), 0.9, 0.0, 'std'),
    'MNF_FurBoar': ('fur_boar', (0.20, 0.15, 0.10), 0.9, 0.0, 'std'),
    'MNF_FurDark': ('fur_dark', (0.06, 0.05, 0.05), 0.9, 0.0, 'std'),
    'MNF_MineralCrust': ('mineral_crust', (0.3, 0.3, 0.28), 0.8, 0.0, 'std'),
    'MNF_MournerSkin': ('mourner_skin', (0.35, 0.33, 0.3), 0.6, 0.0, 'std'),
    'MNF_Teeth': (None, (0.62, 0.56, 0.42), 0.5, 0.0, 'flat'),
    'MNF_Gums': (None, (0.12, 0.04, 0.04), 0.5, 0.0, 'flat'),
    'MNF_Nails': (None, (0.35, 0.32, 0.26), 0.5, 0.0, 'flat'),
    'MNF_Flesh': (None, (0.35, 0.06, 0.05), 0.3, 0.0, 'flat'),
    'MNF_EyeWet': (None, (0.01, 0.01, 0.01), 0.05, 0.0, 'flat'),
    'MNF_EyeClouded': (None, (0.6, 0.65, 0.7), 0.2, 0.0, 'flat'),
    'MNF_EyeGlint': (None, (1.0, 0.95, 0.8), 0.2, 0.0, 'emit'),
    'MNF_MournerGlow': (None, (0.7, 0.9, 0.2), 0.3, 0.0, 'emit'),
    'MNF_FabricCanvas': ('fabric_canvas', (0.30, 0.27, 0.19), 0.95, 0.0, 'fabric'),
    'MNF_FabricBlanket': ('fabric_blanket', (0.20, 0.14, 0.12), 0.95, 0.0, 'fabric'),
    'MNF_Glass': (None, (0.6, 0.62, 0.55), 0.15, 0.0, 'glass'),
    'MNF_BulbWarm': (None, (1.0, 0.62, 0.28), 0.3, 0.0, 'emit'),
    'MNF_BulbCold': (None, (0.75, 0.88, 1.0), 0.3, 0.0, 'emit'),
    'MNF_BulbRed': (None, (1.0, 0.08, 0.04), 0.3, 0.0, 'emit'),
    'MNF_BulbGreen': (None, (0.25, 1.0, 0.2), 0.3, 0.0, 'emit'),
    'MNF_Screen': (None, (0.05, 0.1, 0.06), 0.1, 0.0, 'flat'),
    'MNF_Rope': ('rope', (0.32, 0.26, 0.17), 0.95, 0.0, 'fabric'),
    'MNF_Paper': ('paper', (0.62, 0.58, 0.48), 0.9, 0.0, 'std'),
    'MNF_Meat': ('meat', (0.4, 0.1, 0.08), 0.5, 0.0, 'std'),
    'MNF_Signs': ('signs_atlas', (0.55, 0.50, 0.40), 0.7, 0.0, 'std'),
    'MNF_Decals': ('decals_atlas', (0.2, 0.2, 0.2), 0.8, 0.0, 'cut'),
    'MNF_Player_Fur': (None, (0.3, 0.2, 0.1), 0.9, 0.0, 'flat'),
    'MNF_Player_Face': (None, (0.5, 0.4, 0.3), 0.6, 0.0, 'flat'),
    'MNF_Player_Dark': (None, (0.05, 0.05, 0.05), 0.6, 0.0, 'flat'),
}

PREVIEW_CARD_TEX = {'MNF_FoliagePine': 'pine_card.png', 'MNF_FoliageLeaf': 'leaf_card.png',
                    'MNF_Fern': 'fern_card.png', 'MNF_Grass': 'grass_card.png'}


def rng(seed):
    return random.Random(seed)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    return sc


def _img(path):
    for im in bpy.data.images:
        if im.filepath and os.path.abspath(bpy.path.abspath(im.filepath)) == os.path.abspath(path):
            return im
    return bpy.data.images.load(path)


def get_mat(name):
    """Return (creating if needed) the catalog material `name` with a preview node setup."""
    if name not in CATALOG:
        raise ValueError('material %s not in catalog' % name)
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    texset, col, rough, metal, kind = CATALOG[name]
    m = bpy.data.materials.new(name)
    m.diffuse_color = (col[0], col[1], col[2], 1.0)
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N.get('Principled BSDF')
    out = N.get('Material Output')
    bsdf.inputs['Base Color'].default_value = (col[0], col[1], col[2], 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    albedo = os.path.join(TEX_DIR, '%s_A.png' % texset) if texset else None
    use_real = albedo is not None and os.path.exists(albedo)
    if kind == 'emit':
        bsdf.inputs['Emission Color'].default_value = (col[0], col[1], col[2], 1)
        bsdf.inputs['Emission Strength'].default_value = 12.0 if name.startswith('MNF_Bulb') else 3.0
        return m
    if kind == 'glass':
        bsdf.inputs['Transmission Weight'].default_value = 0.9
        bsdf.inputs['Roughness'].default_value = 0.25
        bsdf.inputs['Alpha'].default_value = 0.6
        return m
    if kind == 'flat':
        return m
    if kind == 'cut':
        path = albedo if use_real else os.path.join(PREVIEW_TEX, PREVIEW_CARD_TEX.get(name, 'leaf_card.png'))
        if os.path.exists(path):
            tex = N.new('ShaderNodeTexImage')
            tex.image = _img(path)
            L.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
            L.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
            m.surface_render_method = 'DITHERED'
        bsdf.inputs['Subsurface Weight'].default_value = 0.0
        return m
    if use_real:
        tex = N.new('ShaderNodeTexImage')
        tex.image = _img(albedo)
        if kind == 'tri':
            tex.projection = 'BOX'
            tex.projection_blend = 0.3
            tc = N.new('ShaderNodeTexCoord')
            mp = N.new('ShaderNodeMapping')
            mp.inputs['Scale'].default_value = (0.5, 0.5, 0.5)
            L.new(tc.outputs['Object'], mp.inputs['Vector'])
            L.new(mp.outputs['Vector'], tex.inputs['Vector'])
        if kind == 'paint' or texset == 'plastic':
            mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0
            L.new(tex.outputs['Color'], mix.inputs['A'])
            mix.inputs['B'].default_value = (min(1, col[0] * 1.6), min(1, col[1] * 1.6), min(1, col[2] * 1.6), 1)
            L.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
        else:
            L.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        if kind == 'grate':
            L.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
        return m
    # ---- procedural fallback preview ----
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping')
    src = tc.outputs['Object'] if kind == 'tri' else tc.outputs['UV']
    L.new(src, mp.inputs['Vector'])
    sc = {'bark': (14.0, 1.6, 1.0), 'wood': (1.2, 10.0, 1.0), 'rock': (5, 5, 5), 'tri': (1.2, 1.2, 1.2),
          'rust': (6, 6, 6), 'paint': (5, 5, 5), 'fabric': (12, 12, 12), 'hazard': (1, 1, 1),
          'grate': (1, 1, 1)}.get(kind, (4, 4, 4))
    mp.inputs['Scale'].default_value = sc
    nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 3.0
    nz.inputs['Detail'].default_value = 8.0
    nz.inputs['Roughness'].default_value = 0.6
    L.new(mp.outputs['Vector'], nz.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB')
    c0 = [max(0, c * 0.45) for c in col]
    c1 = [min(1, c * (1.2 if kind in ('rock', 'tri') else 1.5)) for c in col]
    if kind == 'rust':
        c0 = (0.08, 0.04, 0.02); c1 = (0.42, 0.2, 0.08)
    if kind == 'paint':
        c0 = (0.18, 0.09, 0.04)
    ramp.color_ramp.elements[0].color = (c0[0], c0[1], c0[2], 1)
    ramp.color_ramp.elements[1].color = (c1[0], c1[1], c1[2], 1)
    if kind == 'paint':
        ramp.color_ramp.elements[0].position = 0.32
        ramp.color_ramp.elements[1].position = 0.38
    else:
        ramp.color_ramp.elements[0].position = 0.25
        ramp.color_ramp.elements[1].position = 0.75
    L.new(nz.outputs['Fac'], ramp.inputs['Fac'])
    if kind == 'hazard':
        wave = N.new('ShaderNodeTexWave')
        wave.wave_profile = 'SAW'
        wave.bands_direction = 'DIAGONAL'
        wave.inputs['Scale'].default_value = 4.0
        L.new(mp.outputs['Vector'], wave.inputs['Vector'])
        mr = N.new('ShaderNodeMath'); mr.operation = 'GREATER_THAN'; mr.inputs[1].default_value = 0.5
        L.new(wave.outputs['Fac'], mr.inputs[0])
        mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
        mix.inputs['A'].default_value = (0.03, 0.03, 0.03, 1)
        mix.inputs['B'].default_value = (0.6, 0.45, 0.04, 1)
        L.new(mr.outputs[0], mix.inputs['Factor'])
        L.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    else:
        L.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    if kind == 'grate':
        br = N.new('ShaderNodeTexBrick')
        br.inputs['Scale'].default_value = 1.0
        br.inputs['Mortar Size'].default_value = 0.02
        mp.inputs['Scale'].default_value = (14, 14, 14)
        L.new(mp.outputs['Vector'], br.inputs['Vector'])
        inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        # brick Fac = 1 at mortar -> mortar is the metal bar
        L.new(br.outputs['Fac'], bsdf.inputs['Alpha'])
        br.inputs['Mortar Size'].default_value = 0.12
        br.inputs['Color1'].default_value = (0, 0, 0, 1)
        m.surface_render_method = 'DITHERED'
    bump = N.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    L.new(nz.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m


# --------------------------------------------------------------------------------------------
# Mesh builder
# --------------------------------------------------------------------------------------------
def _perp(v):
    v = Vector(v).normalized()
    a = Vector((0, 0, 1)) if abs(v.z) < 0.9 else Vector((1, 0, 0))
    return v.cross(a).normalized()


def frame_from(fwd, up_hint=(0, 0, 1)):
    """Matrix 3x3 with columns (side, fwd, up) - local X=side, Y=fwd, Z=up."""
    f = Vector(fwd).normalized()
    u = Vector(up_hint)
    if abs(f.dot(u.normalized())) > 0.98:
        u = Vector((1, 0, 0)) if abs(f.x) < 0.9 else Vector((0, 1, 0))
    s = f.cross(u).normalized()
    u = s.cross(f).normalized()
    return Matrix((s, f, u)).transposed()


def M(loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    """4x4 from location + euler degrees XYZ."""
    r = Euler([math.radians(a) for a in rot], 'XYZ').to_matrix().to_4x4()
    m = Matrix.Translation(Vector(loc)) @ r
    if scale != 1.0:
        m = m @ Matrix.Scale(scale, 4)
    return m


class MB:
    """Mesh builder: accumulate geometry with per-loop UVs, material per face."""

    def __init__(self):
        self.v = []
        self.f = []
        self.uv = []
        self.fm = []
        self.fs = []
        self.cn = []      # per face: list of custom normals or None
        self.mats = []

    def mi(self, name):
        if name not in self.mats:
            get_mat(name)
            self.mats.append(name)
        return self.mats.index(name)

    def av(self, co):
        self.v.append(Vector(co))
        return len(self.v) - 1

    def face(self, idx, uvs, mat, smooth=False, cnorm=None):
        if len(set(idx)) < 3:
            return
        self.f.append(list(idx))
        self.uv.append([tuple(u) for u in uvs])
        self.fm.append(self.mi(mat))
        self.fs.append(smooth)
        self.cn.append(cnorm)

    def tris(self):
        return sum(len(f) - 2 for f in self.f)

    def merge(self, other, mat_matrix=None):
        off = len(self.v)
        mm = mat_matrix or Matrix.Identity(4)
        for co in other.v:
            self.v.append(mm @ co)
        rot = mm.to_3x3()
        for i, f in enumerate(other.f):
            cn = other.cn[i]
            if cn is not None:
                cn = [(rot @ Vector(n)).normalized() for n in cn]
            self.face([j + off for j in f], other.uv[i], other.mats[other.fm[i]], other.fs[i], cn)

    def transform(self, mm, start=0):
        for i in range(start, len(self.v)):
            self.v[i] = mm @ self.v[i]

    def add_bm(self, bm, mm=None, mats=('MNF_WoodBeam',), uv='box', tile=2.0, smooth=False, uv_off=(0, 0)):
        """Append bmesh geometry.  mats: material names indexed by face.material_index.
        uv='box' computes box-projected UVs in the bmesh's local space (before mm)."""
        mm = mm or Matrix.Identity(4)
        bm.verts.index_update()
        base = len(self.v)
        for vt in bm.verts:
            self.v.append(mm @ vt.co)
        uvl = bm.loops.layers.uv.active
        if isinstance(mats, str):
            mats = (mats,)
        for fc in bm.faces:
            idx = [base + l.vert.index for l in fc.loops]
            if uv == 'box' or uvl is None:
                n = fc.normal
                ax = max(range(3), key=lambda k: abs(n[k]))
                uvs = []
                for l in fc.loops:
                    c = l.vert.co
                    if ax == 0:
                        uvs.append((c.y / tile * (1 if n.x > 0 else -1) + uv_off[0], c.z / tile + uv_off[1]))
                    elif ax == 1:
                        uvs.append((c.x / tile * (-1 if n.y > 0 else 1) + uv_off[0], c.z / tile + uv_off[1]))
                    else:
                        uvs.append((c.x / tile + uv_off[0], c.y / tile * (1 if n.z > 0 else -1) + uv_off[1]))
            else:
                uvs = [tuple(l[uvl].uv) for l in fc.loops]
            self.face(idx, uvs, mats[min(fc.material_index, len(mats) - 1)], smooth)

    def to_object(self, name, coll=None, parent=None, loc=(0, 0, 0), sharp_angle=None, shade='auto'):
        me = bpy.data.meshes.new(name)
        verts = [tuple(v) for v in self.v]
        me.from_pydata(verts, [], self.f)
        uvl = me.uv_layers.new(name='UVMap')
        flat = []
        for u in self.uv:
            for c in u:
                flat.extend(c)
        if len(flat) == len(me.loops) * 2:
            uvl.data.foreach_set('uv', flat)
        for mname in self.mats:
            me.materials.append(get_mat(mname))
        if self.f:
            me.polygons.foreach_set('material_index', self.fm)
            me.polygons.foreach_set('use_smooth', self.fs)
        # triangulate n-gons (keeps quads) so FBX can export tangents; ear clipping handles concave caps
        if any(len(f) > 4 for f in self.f):
            bm = bmesh.new()
            bm.from_mesh(me)
            ng = [f for f in bm.faces if len(f.verts) > 4]
            bmesh.ops.triangulate(bm, faces=ng, quad_method='BEAUTY', ngon_method='EAR_CLIP')
            bm.to_mesh(me)
            bm.free()
        if sharp_angle is not None:
            me.set_sharp_from_angle(angle=math.radians(sharp_angle))
        if any(c is not None for c in self.cn):
            vn = [(0.0, 0.0, 0.0)] * len(self.v)
            for i, f in enumerate(self.f):
                cn = self.cn[i]
                if cn is not None:
                    for vi, n in zip(f, cn):
                        vn[vi] = tuple(n)
            me.normals_split_custom_set_from_vertices(vn)
        me.validate(clean_customdata=False)
        me.update()
        ob = bpy.data.objects.new(name, me)
        (coll or bpy.context.scene.collection).objects.link(ob)
        if parent is not None:
            ob.parent = parent
        ob.location = loc
        return ob


# --------------------------------------------------------------------------------------------
# Primitives (all add into an MB)
# --------------------------------------------------------------------------------------------
def add_box(mb, size, mm, mat, bevel=0.0, tile=1.5, jitter=0.0, seed=0, smooth=False, uv_off=(0, 0)):
    """Centered box (sx, sy, sz) transformed by mm, optional chamfer and vertex jitter."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    if bevel > 0:
        b = min(bevel, min(size) * 0.45)
        bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=b, segments=1,
                        affect='EDGES', clamp_overlap=True, profile=0.5)
    if jitter > 0:
        r = rng(seed)
        for v in bm.verts:
            v.co += Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))) * jitter
    bm.normal_update()
    mb.add_bm(bm, mm, mat, 'box', tile, smooth, uv_off)
    bm.free()


def add_beam(mb, p0, p1, w, h, mat, up=(0, 0, 1), chamfer=0.012, segs=1, warp=0.0, jag0=0.0, jag1=0.0,
             seed=0, tile=2.0, twist=0.0, taper=1.0, cap0=True, cap1=True, rough=0.0, uv_shift=None, board=None,
             top_mat=None):
    """Rectangular timber / plank from p0 to p1.  w = width along side axis, h = height along up axis.
    Cross-section is a chamfered rectangle (8 verts) or plain (4).  UV: U runs along the length
    (grain along U), V around the perimeter.  jag0/jag1: splintered broken ends (length of splinters)."""
    r = rng(seed)
    p0 = Vector(p0); p1 = Vector(p1)
    d = p1 - p0
    L = d.length
    if L < 1e-5:
        return
    F = frame_from(d, up)
    side, fwd, upv = F.col[0], F.col[1], F.col[2]
    c = min(chamfer, w * 0.3, h * 0.3)
    hw, hh = w / 2, h / 2
    if c > 0.001:
        prof = [(-hw + c, -hh), (hw - c, -hh), (hw, -hh + c), (hw, hh - c), (hw - c, hh), (-hw + c, hh),
                (-hw, hh - c), (-hw, -hh + c)]
    else:
        prof = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    np_ = len(prof)
    # perimeter coordinate for V
    per = [0.0]
    for i in range(np_):
        a = Vector(prof[i]); b = Vector(prof[(i + 1) % np_])
        per.append(per[-1] + (b - a).length)
    us = uv_shift if uv_shift is not None else (r.random(), r.random())
    tv = tile
    top_i = 4 if np_ == 8 else 2
    if board is not None:
        # map the top (+up) face onto exactly one board row of a plank atlas texture (n boards per repeat along V)
        k, nb = board
        tv = w * nb
        us = (us[0], k / nb - per[top_i] / tv)
    rings = []
    for k in range(segs + 1):
        t = k / segs
        sc = 1.0 + (taper - 1.0) * t
        bend = math.sin(t * math.pi) * warp
        tw = twist * t
        ring = []
        for i, (x, y) in enumerate(prof):
            x2 = x * math.cos(tw) - y * math.sin(tw)
            y2 = x * math.sin(tw) + y * math.cos(tw)
            along = t * L
            if k == 0 and jag0 > 0:
                along += r.uniform(0, jag0)
            if k == segs and jag1 > 0:
                along -= r.uniform(0, jag1)
            rr = 1.0 + (r.uniform(-rough, rough) if rough else 0.0)
            co = p0 + fwd * along + side * (x2 * sc * rr) + upv * (y2 * sc * rr + bend)
            ring.append((mb.av(co), along))
        rings.append(ring)
    for k in range(segs):
        a, b = rings[k], rings[k + 1]
        for i in range(np_):
            j = (i + 1) % np_
            v0 = per[i] / tv + us[1]
            v1 = per[i + 1] / tv + us[1]
            mb.face([a[i][0], a[j][0], b[j][0], b[i][0]],
                    [(a[i][1] / tile + us[0], v0), (a[j][1] / tile + us[0], v1),
                     (b[j][1] / tile + us[0], v1), (b[i][1] / tile + us[0], v0)],
                    top_mat if (top_mat and i == top_i) else mat)
    pr = [Vector(p) for p in prof]
    if cap0:
        ring = rings[0]
        mb.face([ring[i][0] for i in reversed(range(np_))],
                [(pr[i].x / tile, pr[i].y / tile) for i in reversed(range(np_))], mat)
    if cap1:
        ring = rings[-1]
        mb.face([ring[i][0] for i in range(np_)], [(pr[i].x / tile, pr[i].y / tile) for i in range(np_)], mat)


def add_cyl(mb, p0, p1, r0, r1, segs, mat, cap0=True, cap1=True, tile=1.0, urep=1, smooth=True,
            rings=1, noise_amp=0.0, seed=0, up=(0, 0, 1), phase=0.0):
    """Cylinder/cone between p0 and p1."""
    p0 = Vector(p0); p1 = Vector(p1)
    d = p1 - p0
    L = d.length
    F = frame_from(d, up)
    side, fwd, upv = F.col[0], F.col[1], F.col[2]
    off = seed * 7.31
    rr = []
    for k in range(rings + 1):
        t = k / rings
        rad = r0 + (r1 - r0) * t
        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs + phase
            n = 1.0
            if noise_amp:
                n += noise_amp * noise.noise(Vector((math.cos(a) * 1.3 + off, math.sin(a) * 1.3, t * L * 1.5)))
            co = p0 + fwd * (L * t) + (side * math.cos(a) + upv * math.sin(a)) * rad * n
            ring.append(mb.av(co))
        rr.append((ring, t * L))
    for k in range(rings):
        (a, za), (b, zb) = rr[k], rr[k + 1]
        for j in range(segs):
            jn = (j + 1) % segs
            u0 = j / segs * urep; u1 = (j + 1) / segs * urep
            mb.face([a[j], a[jn], b[jn], b[j]], [(u0, za / tile), (u1, za / tile), (u1, zb / tile), (u0, zb / tile)],
                    mat, smooth)
    for cap, (ring, z), rev, rad in ((cap0, rr[0], True, r0), (cap1, rr[-1], False, r1)):
        if not cap or rad <= 1e-4:
            continue
        ids = list(reversed(ring)) if rev else list(ring)
        uvs = []
        for i in ids:
            pv = mb.v[i] - (p0 + fwd * z)
            uvs.append((0.5 + pv.dot(side) / (2 * rad) * 0.5, 0.5 + pv.dot(upv) / (2 * rad) * 0.5))
        mb.face(ids, uvs, mat, False)


def _transport_frames(pts, n0=None):
    tans = []
    for i in range(len(pts)):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i - 1])
        if t.length < 1e-8:
            t = tans[-1] if tans else Vector((0, 0, 1))
        tans.append(t.normalized())
    n = Vector(n0) if n0 is not None else _perp(tans[0])
    n = (n - tans[0] * n.dot(tans[0])).normalized()
    norms = []
    for i, t in enumerate(tans):
        if i > 0:
            q = tans[i - 1].rotation_difference(t)
            n = q @ n
            n = (n - t * n.dot(t)).normalized()
        norms.append(n.copy())
    return tans, norms


def add_tube(mb, pts, radii, segs, mat, tile_v=2.0, urep=1, cap0=False, cap1=True, smooth=True,
             noise_fn=None, apex=False, n0=None, v0=0.0, face_mat_fn=None):
    """Sweep a circle along polyline pts with per-point radii.  noise_fn(i, j, angle) -> radius factor.
    apex=True closes the tip with a single vertex (cone tip).  Returns list of rings (vertex indices)."""
    pts = [Vector(p) for p in pts]
    tans, norms = _transport_frames(pts, n0)
    rings = []
    dirs = []
    vcoord = [v0]
    for i in range(1, len(pts)):
        vcoord.append(vcoord[-1] + (pts[i] - pts[i - 1]).length)
    last = len(pts) - 1
    for i, p in enumerate(pts):
        if apex and i == last:
            rings.append([mb.av(p)])
            continue
        t, n = tans[i], norms[i]
        b = t.cross(n)
        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            dv = n * math.cos(a) + b * math.sin(a)
            f = noise_fn(i, j, a, dv) if noise_fn else 1.0
            ring.append(mb.av(p + dv * radii[i] * f))
        rings.append(ring)
        dirs.append((n, b))
    for i in range(last):
        A, B = rings[i], rings[i + 1]
        va, vb = vcoord[i] / tile_v, vcoord[i + 1] / tile_v
        for j in range(segs):
            jn = (j + 1) % segs
            u0, u1 = j / segs * urep, (j + 1) / segs * urep
            if face_mat_fn:
                nn, bb = dirs[min(i, len(dirs) - 1)]
                am = 2 * math.pi * (j + 0.5) / segs
                m = face_mat_fn(i, j, nn * math.cos(am) + bb * math.sin(am))
            else:
                m = mat
            if len(B) == 1:
                mb.face([A[j], A[jn], B[0]], [(u0, va), (u1, va), ((u0 + u1) / 2, vb)], m, smooth)
            else:
                mb.face([A[j], A[jn], B[jn], B[j]], [(u0, va), (u1, va), (u1, vb), (u0, vb)], m, smooth)
    if cap0 and len(rings[0]) > 2:
        ids = list(reversed(rings[0]))
        mb.face(ids, [(0.5 + 0.5 * math.cos(2 * math.pi * k / segs), 0.5 + 0.5 * math.sin(2 * math.pi * k / segs))
                      for k in reversed(range(segs))], mat, False)
    if cap1 and len(rings[-1]) > 2:
        ids = list(rings[-1])
        mb.face(ids, [(0.5 + 0.5 * math.cos(2 * math.pi * k / segs), 0.5 + 0.5 * math.sin(2 * math.pi * k / segs))
                      for k in range(segs)], mat, False)
    return rings


def add_card(mb, base, up, side, width, height, mat, bend=0.0, segs=2, bend_dir=None, cnormal=None,
             uv_rect=(0, 0, 1, 1), shift=0.0):
    """Alpha card: base point at the bottom centre (V=0), extends `height` along `up`, `width` across `side`.
    bend: tip displacement along bend_dir (default -Z) growing quadratically.  UVs span the full 0..1 rect.
    cnormal: optional normal (or callable(pos)->normal) used as custom split normal."""
    base = Vector(base); up = Vector(up).normalized(); side = Vector(side).normalized()
    bd = Vector(bend_dir) if bend_dir is not None else Vector((0, 0, -1))
    rows = []
    u0, v0, u1, v1 = uv_rect
    for k in range(segs + 1):
        t = k / segs
        c = base + up * (height * t) + bd * (bend * t * t) + side * (shift * t)
        rows.append((mb.av(c - side * width / 2), mb.av(c + side * width / 2), v0 + (v1 - v0) * t))
    for k in range(segs):
        a, b = rows[k], rows[k + 1]
        ids = [a[0], a[1], b[1], b[0]]
        cn = None
        if cnormal is not None:
            cn = [Vector(cnormal(mb.v[i])) if callable(cnormal) else Vector(cnormal) for i in ids]
        mb.face(ids, [(u0, a[2]), (u1, a[2]), (u1, b[2]), (u0, b[2])], mat, True, cn)


def hull_rock(seed, size, npts=34, sharp=0.35, subdiv=1, disp=0.05, flatten_bottom=True, sink=0.1,
              squash=(1, 1, 1), bias_up=0.0, strata=0.0, strata_freq=1.6, front_flat=0.0):
    """Angular weathered rock as a bmesh: convex hull of random points in an ellipsoid, optionally
    subdivided + noise displaced.  Returns bmesh with base at z=-sink*size_z."""
    r = rng(seed)
    sx, sy, sz = size
    pts = []
    for i in range(npts):
        while True:
            p = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1)))
            if p.length <= 1.0:
                break
        # push towards surface for sharper facets
        p = p.normalized() * (p.length ** sharp)
        pts.append(Vector((p.x * sx / 2 * squash[0], p.y * sy / 2 * squash[1], p.z * sz / 2 * squash[2])))
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    # remove interior verts left over
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(6), verts=list(bm.verts), edges=list(bm.edges))
    for _ in range(subdiv):
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=1, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    off = Vector((r.uniform(0, 100), r.uniform(0, 100), r.uniform(0, 100)))
    for v in bm.verts:
        n = noise.noise(v.co * (2.2 / max(size)) * 2 + off)
        n2 = noise.noise(v.co * (6.0 / max(size)) + off * 1.7)
        v.co += v.co.normalized() * (n * disp * max(size) + n2 * disp * 0.35 * max(size))
    if strata:
        so = r.uniform(0, 1)
        for v in bm.verts:
            f = (v.co.z * strata_freq + so) % 1.0
            k = 1.0 + strata * (f - 0.5)
            v.co.x *= k
            v.co.y *= k
    if front_flat:   # flatten the back (+Y) so cliff pieces butt against terrain
        ymax = max(v.co.y for v in bm.verts)
        for v in bm.verts:
            if v.co.y > ymax * (1 - front_flat):
                v.co.y = ymax * (1 - front_flat) + (v.co.y - ymax * (1 - front_flat)) * 0.3
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= zmin
    if flatten_bottom:
        cut = sz * 0.08
        for v in bm.verts:
            if v.co.z < cut:
                v.co.z = cut * 0.4 + v.co.z * 0.6
    for v in bm.verts:
        v.co.z -= sink * sz
    bm.normal_update()
    return bm


def cut_rock(seed, size, cuts=10, depth=(0.1, 0.36), bevel=0.035, subdiv=1, disp=0.02, strata=0.0,
             strata_freq=1.5, sink=0.1, front_flat=0.0, taper_top=0.15, nz_bias=0.25, lowfreq=0.05):
    """Angular fractured rock: a box chopped by random planes (crisp facets), chamfered edges, then
    subdivided + noise for weathering.  Returns bmesh with its base sunk `sink` (fraction of height) below 0."""
    r = rng(seed)
    sx, sy, sz = size
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx; v.co.y *= sy; v.co.z *= sz
        if v.co.z > 0:
            v.co.x *= (1 - taper_top); v.co.y *= (1 - taper_top)
    for c in range(cuts):
        while True:
            n = Vector((r.gauss(0, 1), r.gauss(0, 1), r.gauss(0, 1) + nz_bias))
            if n.length > 1e-3:
                break
        n.normalize()
        if n.z < -0.5:
            n.z = -0.5; n.normalize()
        sup = max(v.co.dot(n) for v in bm.verts)
        d = sup * (1 - r.uniform(*depth))
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=n * d, plane_no=n, clear_outer=True, dist=1e-5)
        edges = [e for e in bm.edges if e.is_boundary]
        if edges:
            bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1), verts=list(bm.verts), edges=list(bm.edges))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel * min(size), segments=1, affect='EDGES',
                        clamp_overlap=True, profile=0.5)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    for _ in range(subdiv):
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=1, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    off = Vector((r.uniform(0, 100), r.uniform(0, 100), r.uniform(0, 100)))
    ms = max(size)
    for v in bm.verts:
        dirv = Vector((v.co.x / sx, v.co.y / sy, v.co.z / sz)).normalized()
        n1 = noise.noise(v.co * (1.6 / ms) + off)
        n2 = noise.noise(v.co * (7.0 / ms) + off * 1.7)
        v.co += dirv * (n1 * lowfreq * ms + n2 * disp * ms)
    if strata:
        so = r.uniform(0, 1)
        for v in bm.verts:
            f = (v.co.z / sz * strata_freq + so) % 1.0
            k = 1.0 + strata * (f - 0.5)
            v.co.x *= k; v.co.y *= k
    if front_flat:
        ymax = max(v.co.y for v in bm.verts)
        lim = ymax * (1 - front_flat)
        for v in bm.verts:
            if v.co.y > lim:
                v.co.y = lim + (v.co.y - lim) * 0.25
    zmin = min(v.co.z for v in bm.verts)
    zmax = max(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= zmin + sink * (zmax - zmin)
    bm.normal_update()
    return bm


def rock_to_mb(mb, bm, mm, mat, moss=None, moss_thresh=0.72, tile=3.0, seed=0, smooth=False, moss_noise=0.25):
    """Add rock bmesh to builder; faces facing up (normal.z > thresh, noisy) get the moss material."""
    mm = mm or Matrix.Identity(4)
    rot = mm.to_3x3()
    off = seed * 3.1
    for f in bm.faces:
        f.material_index = 0
        if moss:
            n = (rot @ f.normal).normalized()
            c = mm @ f.calc_center_median()
            nz = noise.noise(c * 0.9 + Vector((off, 0, 0))) * moss_noise
            if n.z + nz > moss_thresh:
                f.material_index = 1
    # world-space box UV: transform a copy
    bm2 = bm.copy()
    bm2.transform(mm)
    bm2.normal_update()
    mb.add_bm(bm2, None, (mat, moss or mat), 'box', tile, smooth)
    bm2.free()


# --------------------------------------------------------------------------------------------
# Objects & helpers
# --------------------------------------------------------------------------------------------
def kit_collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def child_name(name, owner):
    return '%s~%s' % (name, owner)


def export_name(obname):
    return re.sub(r'(~.*|\.\d{3})$', '', obname)


def col_box(parent, name, bmin, bmax, coll=None):
    """Axis-aligned COL_ box child (in parent space)."""
    bmin = Vector(bmin); bmax = Vector(bmax)
    mb = MB()
    add_box(mb, tuple(bmax - bmin), Matrix.Translation((bmin + bmax) / 2), 'MNF_ConcreteWall')
    ob = _col_from_mb(mb, parent, name, coll)
    return ob


def col_obox(parent, name, center, size, rot_deg, coll=None):
    """Oriented box collider (use a _CONVEX name so the builder makes a convex mesh collider)."""
    mb = MB()
    add_box(mb, size, M(center, rot_deg), 'MNF_ConcreteWall')
    return _col_from_mb(mb, parent, name, coll)


def col_hull(parent, name, points, coll=None):
    bm = bmesh.new()
    for p in points:
        bm.verts.new(Vector(p))
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    # limit to <255 tris for Unity convex colliders
    if len(bm.faces) > 240:
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(10), verts=list(bm.verts), edges=list(bm.edges))
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.normal_update()
    mb = MB()
    mb.add_bm(bm, None, 'MNF_ConcreteWall', 'box', 2.0)
    bm.free()
    return _col_from_mb(mb, parent, name, coll)


def _col_from_mb(mb, parent, name, coll):
    oname = child_name(name, parent.name)
    ob = mb.to_object(oname, coll or parent.users_collection[0], parent=parent)
    ob.data.materials.clear()
    ob.display_type = 'WIRE'
    ob.hide_render = True
    ob['mnf_helper'] = 'COL'
    return ob


def empty(parent, name, loc, rot_deg=(0, 0, 0), size=0.15, coll=None, unique=False):
    oname = name if unique else child_name(name, parent.name)
    e = bpy.data.objects.new(oname, None)
    e.empty_display_type = 'ARROWS'
    e.empty_display_size = size
    (coll or parent.users_collection[0]).objects.link(e)
    e.parent = parent
    e.location = loc
    e.rotation_euler = [math.radians(a) for a in rot_deg]
    e['mnf_helper'] = 'EMPTY'
    return e


def child_mesh(parent, name, mb, pivot, coll=None, sharp_angle=None):
    """Child render mesh with its own pivot (mb built in parent space; geometry re-centred on pivot)."""
    pv = Vector(pivot)
    mb.transform(Matrix.Translation(-pv))
    ob = mb.to_object(child_name(name, parent.name), coll or parent.users_collection[0], parent=parent, loc=pv,
                      sharp_angle=sharp_angle)
    return ob


def descendants(ob):
    out = []
    for c in ob.children:
        out.append(c)
        out.extend(descendants(c))
    return out


def obj_tris(ob, include_cols=False):
    t = 0
    for o in [ob] + descendants(ob):
        if o.type != 'MESH':
            continue
        if not include_cols and export_name(o.name).startswith('COL_'):
            continue
        t += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return t


def obj_bounds(ob):
    """Bounds of render meshes in ob's local space (relative to pivot)."""
    mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9))
    inv = ob.matrix_world.inverted()
    for o in [ob] + descendants(ob):
        if o.type != 'MESH' or export_name(o.name).startswith('COL_'):
            continue
        mw = inv @ o.matrix_world
        for v in o.data.vertices:
            c = mw @ v.co
            for k in range(3):
                mn[k] = min(mn[k], c[k]); mx[k] = max(mx[k], c[k])
    return mn, mx


def obj_materials(ob):
    s = []
    for o in [ob] + descendants(ob):
        if o.type == 'MESH' and not export_name(o.name).startswith('COL_'):
            for m in o.data.materials:
                if m and m.name not in s:
                    s.append(m.name)
    return s


# --------------------------------------------------------------------------------------------
# Export + manifest
# --------------------------------------------------------------------------------------------
def _patch_fbx_names():
    import io_scene_fbx.export_fbx_bin as efb
    if getattr(efb, '_mnf_b_patched', False):
        return
    orig = efb.fbx_name_class

    def patched(name, cls):
        if cls in (b'Model', b'NodeAttribute', b'Geometry'):
            name = re.sub(rb'(~.*|\.\d{3})$', b'', name)
        return orig(name, cls)
    efb.fbx_name_class = patched
    efb._mnf_b_patched = True


def export_kit(tops, path):
    """Export the given top-level objects (+ all children) with the spec FBX settings.
    All top-level objects must be at the world origin with identity rotation/scale."""
    _patch_fbx_names()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for t in tops:
        assert t.location.length < 1e-6 and t.rotation_euler.to_matrix() == Matrix.Identity(3), t.name
        assert tuple(t.scale) == (1, 1, 1), t.name
        for o in [t] + descendants(t):
            o.hide_set(False)
            o.hide_viewport = False
            o.hide_select = False
            o.select_set(True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH', 'EMPTY'},
                             apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y',
                             bake_space_transform=False, use_mesh_modifiers=True, mesh_smooth_type='FACE',
                             use_tspace=True, add_leaf_bones=False, primary_bone_axis='Y',
                             secondary_bone_axis='X', armature_nodetype='NULL', bake_anim=False,
                             bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
                             bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
                             path_mode='STRIP')


def write_manifest(tops, kit, path, notes):
    data = {}
    for t in tops:
        mn, mx = obj_bounds(t)
        kids = [export_name(c.name) for c in descendants(t)
                if c.type == 'MESH' and not export_name(c.name).startswith('COL_')]
        helpers = {}
        for c in descendants(t):
            en = export_name(c.name)
            if c.type == 'EMPTY' or en.startswith('COL_'):
                p = t.matrix_world.inverted() @ c.matrix_world.translation
                if en.startswith('COL_') and c.type == 'MESH':
                    bmn, bmx = obj_bounds_raw(c, t)
                    p = (bmn + bmx) / 2
                helpers[en] = [round(p.x, 3), round(p.y, 3), round(p.z, 3)]
        data[t.name] = {
            'kit': kit,
            'bounds_min': [round(v, 3) for v in mn],
            'bounds_max': [round(v, 3) for v in mx],
            'bounds_size': [round(mx[k] - mn[k], 3) for k in range(3)],
            'tris': obj_tris(t),
            'materials': obj_materials(t),
            'children': kids,
            'helpers': helpers,
            'notes': notes.get(t.name, ''),
        }
    with open(path, 'w') as fh:
        json.dump(data, fh, indent=2)
    return data


def obj_bounds_raw(o, ref):
    inv = ref.matrix_world.inverted() @ o.matrix_world
    cs = [inv @ v.co for v in o.data.vertices]
    mn = Vector([min(c[k] for c in cs) for k in range(3)])
    mx = Vector([max(c[k] for c in cs) for k in range(3)])
    return mn, mx


def args_after_dashdash():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def make_top(mb, name, coll, sharp=None, mount=None):
    ob = mb.to_object(name, coll, sharp_angle=sharp)
    if mount:
        ob['mnf_mount'] = mount
    ob['mnf_top'] = 1
    ob['mnf_order'] = len([o for o in bpy.data.objects if o.get('mnf_top')])
    return ob


def run_kit(kit, builders, notes):
    """CLI entry shared by the kit scripts: [--only A,B] [--blend path] [--noexport]."""
    args = args_after_dashdash()
    only = None
    blend = os.path.join(SRC_OUT, kit + '.blend')
    export = True
    i = 0
    while i < len(args):
        if args[i] == '--only':
            only = args[i + 1].split(','); i += 1
        elif args[i] == '--blend':
            blend = args[i + 1]; i += 1
        elif args[i] == '--noexport':
            export = False
        i += 1
    reset_scene()
    coll = kit_collection(kit)
    tops = []
    for fn in builders:
        if only and fn.__name__ not in only:
            continue
        ob = fn(coll)
        tops.append(ob)
        print('%-24s %6d tris' % (ob.name, obj_tris(ob)), flush=True)
    os.makedirs(os.path.dirname(blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    if export and not only:
        fbx = os.path.join(PROPS_OUT, kit + '.fbx')
        export_kit(tops, fbx)
        write_manifest(tops, kit, os.path.join(PROPS_OUT, 'props_manifest_%s.json' % kit), notes)
        print('exported', fbx)
    return tops
