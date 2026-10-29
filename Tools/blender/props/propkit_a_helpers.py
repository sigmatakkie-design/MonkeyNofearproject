"""propkit_a_helpers.py - shared builders for prop artist A (Kit_Tools, Kit_Deposits, Kit_Bunker).

Pure bpy/bmesh, deterministic (fixed seeds), runs both with the bpy Python module and inside
`blender -b -P`.  Geometry is built as small bmesh "parts" that are merged into a ModelBuilder
(one Blender mesh per exported object, several materials), then finalised with sharp-by-angle
edges, weighted normals and a `UVMap` layer.

Conventions: meters, Blender Z-up, objects face -Y.
"""
import bpy
import bmesh
import math
import os
import random
import re
from mathutils import Vector, Matrix, Euler, noise

PROJECT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
TEX_DIR = os.path.join(PROJECT, "Assets", "MonkeyNoFear", "Art", "Textures")
MODEL_DIR = os.path.join(PROJECT, "Assets", "MonkeyNoFear", "Art", "Models", "Props")
SOURCE_DIR = os.path.join(PROJECT, "SourceArt", "Props")
PREVIEW_DIR = os.path.join(PROJECT, "Docs", "previews", "props")

TAU = math.tau
TILE = [0.4]  # current texture repeat size (m) used when a primitive gets tile=None


def _t(tile):
    return tile if tile else TILE[0]

# --------------------------------------------------------------------------------------------
# Material catalog (ASSET_SPEC §2).  name -> texture set (None = flat colour material)
# --------------------------------------------------------------------------------------------
CATALOG = {
    "MNF_ConcreteWall": "concrete_wall", "MNF_ConcreteFloor": "concrete_floor",
    "MNF_MetalGrate": "metal_grate", "MNF_MetalDiamond": "metal_diamond", "MNF_MetalRusted": "metal_rusted",
    "MNF_MetalPainted_Green": "metal_painted", "MNF_MetalPainted_Gray": "metal_painted",
    "MNF_MetalPainted_Yellow": "metal_painted", "MNF_MetalPainted_Red": "metal_painted",
    "MNF_MetalBare": "metal_bare", "MNF_Hazard": "hazard_stripes", "MNF_Rubber": "rubber",
    "MNF_Plastic_Yellow": "plastic", "MNF_Plastic_Orange": "plastic", "MNF_Plastic_Black": "plastic",
    "MNF_Plastic_Gray": "plastic",
    "MNF_WoodCrate": "wood_crate", "MNF_WoodPlanks": "wood_planks", "MNF_WoodRotten": "wood_rotten",
    "MNF_WoodBeam": "wood_beam", "MNF_WoodHandle": "wood_handle",
    "MNF_BarkPine": "bark_pine", "MNF_BarkDead": "bark_dead",
    "MNF_FoliagePine": "foliage_pine", "MNF_FoliageLeaf": "foliage_leaf", "MNF_Fern": "fern", "MNF_Grass": "grass",
    "MNF_ForestFloor": "forest_floor", "MNF_Mud": "mud", "MNF_Moss": "moss", "MNF_Terrain": None,
    "MNF_RockDry": "rock_dry", "MNF_RockWet": "rock_wet", "MNF_RockMine": "rock_mine",
    "MNF_RockDry_Tri": "rock_dry", "MNF_RockWet_Tri": "rock_wet", "MNF_RockMine_Tri": "rock_mine",
    "MNF_OreIron": "ore_iron", "MNF_OreCopper": "ore_copper", "MNF_Crystal": "crystal",
    "MNF_Blackstone": "blackstone", "MNF_Anomalous": "anomalous",
    "MNF_FurRotten": "fur_rotten", "MNF_SkinDecayed": "skin_decayed", "MNF_FurRabbit": "fur_rabbit",
    "MNF_FurRabbitMangy": "fur_rabbit_mangy", "MNF_FurBoar": "fur_boar", "MNF_FurDark": "fur_dark",
    "MNF_MineralCrust": "mineral_crust", "MNF_MournerSkin": "mourner_skin",
    "MNF_Teeth": None, "MNF_Gums": None, "MNF_Nails": None, "MNF_Flesh": None,
    "MNF_EyeWet": None, "MNF_EyeClouded": None, "MNF_EyeGlint": None, "MNF_MournerGlow": None,
    "MNF_FabricCanvas": "fabric_canvas", "MNF_FabricBlanket": "fabric_blanket",
    "MNF_Glass": None, "MNF_BulbWarm": None, "MNF_BulbCold": None, "MNF_BulbRed": None, "MNF_BulbGreen": None,
    "MNF_Screen": None, "MNF_Rope": "rope", "MNF_Paper": "paper", "MNF_Meat": "meat",
    "MNF_Signs": "signs_atlas", "MNF_Decals": "decals_atlas",
    "MNF_Player_Fur": None, "MNF_Player_Face": None, "MNF_Player_Dark": None,
}

# preview look: base, dark (noise-mixed), metallic, roughness, emission colour, emission strength, kind
_P = {
    "MNF_MetalRusted": ((0.28, 0.12, 0.045), (0.07, 0.045, 0.03), 0.35, 0.85, None, 0, "noise"),
    "MNF_MetalBare": ((0.62, 0.62, 0.64), (0.33, 0.33, 0.34), 1.0, 0.32, None, 0, "noise"),
    "MNF_MetalPainted_Green": ((0.07, 0.16, 0.08), (0.22, 0.22, 0.2), 0.25, 0.6, None, 0, "wear"),
    "MNF_MetalPainted_Gray": ((0.28, 0.29, 0.30), (0.12, 0.11, 0.10), 0.25, 0.6, None, 0, "wear"),
    "MNF_MetalPainted_Yellow": ((0.72, 0.48, 0.04), (0.18, 0.15, 0.12), 0.25, 0.55, None, 0, "wear"),
    "MNF_MetalPainted_Red": ((0.42, 0.04, 0.03), (0.16, 0.12, 0.10), 0.25, 0.55, None, 0, "wear"),
    "MNF_MetalDiamond": ((0.42, 0.42, 0.42), (0.2, 0.2, 0.2), 0.9, 0.45, None, 0, "noise"),
    "MNF_MetalGrate": ((0.3, 0.3, 0.3), (0.12, 0.12, 0.12), 0.9, 0.5, None, 0, "noise"),
    "MNF_Hazard": ((0.75, 0.5, 0.03), (0.02, 0.02, 0.02), 0.2, 0.6, None, 0, "stripes"),
    "MNF_Rubber": ((0.035, 0.035, 0.035), (0.015, 0.015, 0.015), 0.0, 0.8, None, 0, "noise"),
    "MNF_Plastic_Yellow": ((0.78, 0.52, 0.03), (0.45, 0.32, 0.05), 0.0, 0.45, None, 0, "noise"),
    "MNF_Plastic_Orange": ((0.8, 0.22, 0.02), (0.45, 0.12, 0.02), 0.0, 0.45, None, 0, "noise"),
    "MNF_Plastic_Black": ((0.03, 0.03, 0.032), (0.012, 0.012, 0.012), 0.0, 0.5, None, 0, "noise"),
    "MNF_Plastic_Gray": ((0.25, 0.25, 0.24), (0.15, 0.15, 0.14), 0.0, 0.5, None, 0, "noise"),
    "MNF_WoodCrate": ((0.33, 0.21, 0.10), (0.16, 0.10, 0.05), 0.0, 0.8, None, 0, "grain"),
    "MNF_WoodPlanks": ((0.28, 0.19, 0.10), (0.12, 0.08, 0.05), 0.0, 0.8, None, 0, "grain"),
    "MNF_WoodRotten": ((0.16, 0.11, 0.065), (0.06, 0.05, 0.03), 0.0, 0.9, None, 0, "noise"),
    "MNF_WoodBeam": ((0.22, 0.14, 0.07), (0.09, 0.06, 0.035), 0.0, 0.85, None, 0, "grain"),
    "MNF_WoodHandle": ((0.40, 0.25, 0.12), (0.17, 0.10, 0.05), 0.0, 0.6, None, 0, "grain"),
    "MNF_RockDry": ((0.30, 0.28, 0.25), (0.12, 0.11, 0.10), 0.0, 0.9, None, 0, "noise"),
    "MNF_RockWet": ((0.14, 0.14, 0.13), (0.06, 0.06, 0.06), 0.0, 0.4, None, 0, "noise"),
    "MNF_RockMine": ((0.19, 0.17, 0.15), (0.07, 0.065, 0.06), 0.0, 0.85, None, 0, "noise"),
    "MNF_OreIron": ((0.09, 0.085, 0.085), (0.45, 0.42, 0.40), 0.7, 0.45, None, 0, "flecks"),
    "MNF_OreCopper": ((0.42, 0.14, 0.04), (0.08, 0.30, 0.20), 0.5, 0.5, None, 0, "patina"),
    "MNF_Crystal": ((0.35, 0.75, 1.0), (0.1, 0.3, 0.6), 0.0, 0.08, (0.25, 0.75, 1.0), 2.5, "noise"),
    "MNF_Blackstone": ((0.008, 0.008, 0.01), (0.02, 0.02, 0.025), 0.1, 0.06, None, 0, "noise"),
    "MNF_Anomalous": ((0.35, 0.05, 0.25), (0.08, 0.02, 0.06), 0.0, 0.35, (0.9, 0.12, 0.55), 3.0, "noise"),
    "MNF_Flesh": ((0.40, 0.07, 0.06), (0.15, 0.02, 0.03), 0.0, 0.3, None, 0, "noise"),
    "MNF_Meat": ((0.48, 0.10, 0.08), (0.65, 0.5, 0.4), 0.0, 0.35, None, 0, "noise"),
    "MNF_Teeth": ((0.72, 0.64, 0.46), (0.45, 0.38, 0.25), 0.0, 0.5, None, 0, "noise"),
    "MNF_FabricCanvas": ((0.32, 0.27, 0.17), (0.14, 0.12, 0.08), 0.0, 0.95, None, 0, "noise"),
    "MNF_FabricBlanket": ((0.16, 0.19, 0.13), (0.07, 0.08, 0.06), 0.0, 1.0, None, 0, "noise"),
    "MNF_Glass": ((0.8, 0.85, 0.8), (0.6, 0.6, 0.55), 0.0, 0.12, None, 0, "glass"),
    "MNF_BulbWarm": ((1.0, 0.8, 0.5), (1, 1, 1), 0.0, 0.3, (1.0, 0.62, 0.28), 10.0, "flat"),
    "MNF_BulbCold": ((0.9, 0.95, 1.0), (1, 1, 1), 0.0, 0.3, (0.8, 0.9, 1.0), 8.0, "flat"),
    "MNF_BulbRed": ((1.0, 0.1, 0.05), (1, 1, 1), 0.0, 0.3, (1.0, 0.06, 0.02), 8.0, "flat"),
    "MNF_BulbGreen": ((0.3, 1.0, 0.4), (1, 1, 1), 0.0, 0.3, (0.2, 1.0, 0.3), 5.0, "flat"),
    "MNF_Screen": ((0.02, 0.06, 0.03), (1, 1, 1), 0.0, 0.1, (0.08, 0.45, 0.16), 1.5, "flat"),
    "MNF_Rope": ((0.45, 0.37, 0.23), (0.2, 0.16, 0.1), 0.0, 0.95, None, 0, "noise"),
    "MNF_Paper": ((0.74, 0.70, 0.58), (0.45, 0.40, 0.30), 0.0, 0.9, None, 0, "noise"),
}


def tex_path(mat_name, suffix="A"):
    s = CATALOG.get(mat_name)
    if not s:
        return None
    p = os.path.join(TEX_DIR, "%s_%s.png" % (s, suffix))
    return p if os.path.exists(p) else None


TINTED = ("MNF_MetalPainted_", "MNF_Plastic_")


def _img(path, data=False):
    im = bpy.data.images.load(path, check_existing=True)
    if data:
        im.colorspace_settings.name = "Non-Color"
        im.alpha_mode = "CHANNEL_PACKED"
    return im


def _textured(nt, tc, bsdf, name, albedo, tint):
    """Preview node setup from the texture pipeline's sets (A / N / M / E)."""
    L = nt.links
    it = nt.nodes.new("ShaderNodeTexImage")
    it.image = _img(albedo)
    L.new(tc.outputs["UV"], it.inputs[0])
    col = it.outputs[0]
    if name.startswith(TINTED):
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 1.0
        L.new(col, mul.inputs[6])
        mul.inputs[7].default_value = (*[min(1.0, c * 1.25) for c in tint], 1)
        col = mul.outputs[2]
    L.new(col, bsdf.inputs["Base Color"])
    mp = tex_path(name, "M")
    if mp:
        mt = nt.nodes.new("ShaderNodeTexImage")
        mt.image = _img(mp, True)
        L.new(tc.outputs["UV"], mt.inputs[0])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        L.new(mt.outputs[0], sep.inputs[0])
        L.new(sep.outputs[0], bsdf.inputs["Metallic"])
        inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
        L.new(mt.outputs[1], inv.inputs[1])
        L.new(inv.outputs[0], bsdf.inputs["Roughness"])
    npth = tex_path(name, "N")
    if npth:
        ntx = nt.nodes.new("ShaderNodeTexImage")
        ntx.image = _img(npth, True)
        L.new(tc.outputs["UV"], ntx.inputs[0])
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 0.8
        L.new(ntx.outputs[0], nm.inputs["Color"])
        L.new(nm.outputs[0], bsdf.inputs["Normal"])
    ep = tex_path(name, "E")
    if ep:
        et = nt.nodes.new("ShaderNodeTexImage")
        et.image = _img(ep)
        L.new(tc.outputs["UV"], et.inputs[0])
        L.new(et.outputs[0], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 3.0
    if name == "MNF_Glass":
        bsdf.inputs["Transmission Weight"].default_value = 0.9


def get_mat(name):
    """Return (creating if needed) a preview material with a catalog name."""
    if name not in CATALOG:
        raise ValueError("material %r not in catalog" % name)
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    base, dark, metal, rough, ecol, estr, kind = _P.get(name, ((0.4, 0.4, 0.4), (0.2, 0.2, 0.2), 0, 0.6, None, 0, "noise"))
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*base, 1.0)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    img = tex_path(name)
    if img:
        _textured(nt, tc, bsdf, name, img, base)
        if ecol and not tex_path(name, "E"):
            bsdf.inputs["Emission Color"].default_value = (*ecol, 1)
            bsdf.inputs["Emission Strength"].default_value = estr
        return m
    if kind == "flat":
        bsdf.inputs["Base Color"].default_value = (*base, 1)
    else:
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        if kind == "stripes":
            sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(tc.outputs["UV"], sep.inputs[0])
            add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"
            nt.links.new(sep.outputs[0], add.inputs[0]); nt.links.new(sep.outputs[1], add.inputs[1])
            mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 4.0
            nt.links.new(add.outputs[0], mul.inputs[0])
            fr = nt.nodes.new("ShaderNodeMath"); fr.operation = "FRACT"
            nt.links.new(mul.outputs[0], fr.inputs[0])
            ramp.color_ramp.interpolation = "CONSTANT"
            ramp.color_ramp.elements[0].color = (*base, 1)
            ramp.color_ramp.elements[1].position = 0.5
            ramp.color_ramp.elements[1].color = (*dark, 1)
            nt.links.new(fr.outputs[0], ramp.inputs[0])
        else:
            tex = nt.nodes.new("ShaderNodeTexNoise")
            nt.links.new(tc.outputs["Object"], tex.inputs["Vector"])
            tex.inputs["Scale"].default_value = {"grain": 6.0, "flecks": 60.0, "wear": 9.0, "patina": 14.0}.get(kind, 12.0)
            tex.inputs["Detail"].default_value = 6.0
            if kind == "grain":
                mp = nt.nodes.new("ShaderNodeMapping")
                mp.inputs["Scale"].default_value = (12.0, 12.0, 1.5)
                nt.links.new(tc.outputs["Object"], mp.inputs[0])
                nt.links.new(mp.outputs[0], tex.inputs["Vector"])
            e0, e1 = ramp.color_ramp.elements
            if kind in ("flecks",):
                e0.position, e1.position = 0.62, 0.68
            elif kind in ("wear", "patina"):
                e0.position, e1.position = 0.55, 0.62
            else:
                e0.position, e1.position = 0.3, 0.75
            e0.color = (*base, 1)
            e1.color = (*dark, 1)
            nt.links.new(tex.outputs["Fac"], ramp.inputs[0])
        nt.links.new(ramp.outputs[0], bsdf.inputs["Base Color"])
    if kind == "glass":
        bsdf.inputs["Transmission Weight"].default_value = 0.9
        bsdf.inputs["IOR"].default_value = 1.45
    if ecol:
        bsdf.inputs["Emission Color"].default_value = (*ecol, 1)
        bsdf.inputs["Emission Strength"].default_value = estr
    return m


# --------------------------------------------------------------------------------------------
# Small math helpers
# --------------------------------------------------------------------------------------------
def V(*a):
    if len(a) == 1:
        return Vector(a[0])
    return Vector(a)


def xf(loc=(0, 0, 0), rot=(0, 0, 0), scale=None, order="XYZ"):
    """Matrix from location, Euler rotation in degrees and optional (uniform or xyz) scale."""
    m = Euler([math.radians(r) for r in rot], order).to_matrix().to_4x4()
    if scale is not None:
        if isinstance(scale, (int, float)):
            scale = (scale, scale, scale)
        m = m @ Matrix.Diagonal((*scale, 1.0))
    m.translation = Vector(loc)
    return m


def look_rot(direction, up=(0, 0, 1)):
    """Matrix (3x3->4x4) whose local +Z points along `direction`."""
    d = Vector(direction).normalized()
    u = Vector(up)
    if abs(d.dot(u.normalized())) > 0.99:
        u = Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 1, 0))
    x = u.cross(d).normalized()
    y = d.cross(x).normalized()
    m = Matrix((x, y, d)).transposed().to_4x4()
    return m


def place(loc, direction, up=(0, 0, 1), spin=0.0):
    """Transform placing a +Z-built part at `loc` with +Z along `direction`."""
    m = look_rot(direction, up) @ xf(rot=(0, 0, spin))
    m.translation = Vector(loc)
    return m


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def fbm(p, seed=0, octaves=3):
    off = Vector((seed * 17.31 % 97.0, seed * 7.77 % 89.0, seed * 3.13 % 83.0))
    return noise.fractal(Vector(p) + off, 0.6, 2.0, octaves, noise_basis="PERLIN_ORIGINAL")


def nz(p, seed=0):
    off = Vector((seed * 17.31 % 97.0, seed * 7.77 % 89.0, seed * 3.13 % 83.0))
    return noise.noise(Vector(p) + off, noise_basis="PERLIN_ORIGINAL")


# --------------------------------------------------------------------------------------------
# UV helpers (operate on a part bmesh in its local frame)
# --------------------------------------------------------------------------------------------
def uv_layer(bm):
    return bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")


def uv_box(bm, tile=None, offset=(0.0, 0.0)):
    tile = _t(tile)
    uv = uv_layer(bm)
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            if ax == 0:
                u, v = c.y * (1 if n.x > 0 else -1), c.z
            elif ax == 1:
                u, v = c.x * (-1 if n.y > 0 else 1), c.z
            else:
                u, v = c.x, c.y * (1 if n.z > 0 else -1)
            l[uv].uv = (u / tile + offset[0], v / tile + offset[1])


def has_uv(bm):
    return bm.loops.layers.uv.get("UVMap") is not None


# --------------------------------------------------------------------------------------------
# Core primitives (each returns a new bmesh)
# --------------------------------------------------------------------------------------------
def box(sx, sy, sz, bevel=0.0, seg=1, center=(0, 0, 0), edge_filter=None, profile=0.5):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    c = Vector(center)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz)) + c
    if bevel > 0:
        edges = list(bm.edges)
        if edge_filter:
            edges = [e for e in edges if edge_filter((e.verts[1].co - e.verts[0].co).normalized())]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=seg, profile=profile, affect="EDGES",
                        clamp_overlap=True)
    bm.normal_update()
    return bm


def box_mm(mn, mx, bevel=0.0, seg=1, **kw):
    mn, mx = Vector(mn), Vector(mx)
    s = mx - mn
    return box(s.x, s.y, s.z, bevel, seg, center=(mn + mx) / 2, **kw)


def skin(rings, closed=False, cap_start=True, cap_end=True, tile=None, u_scale=None, flat=False):
    """Connect a list of rings (lists of Vectors, equal length, CCW around the path direction).
    A ring of length 1 is a pole.  UVs: u around the ring, v along the path."""
    tile = _t(tile)
    bm = bmesh.new()
    uv = uv_layer(bm)
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    n = max(len(r) for r in rings)
    # v coordinate = cumulative distance between ring centroids
    cents = [sum(r, Vector()) / len(r) for r in rings]
    vs = [0.0]
    for i in range(1, len(rings)):
        vs.append(vs[-1] + (cents[i] - cents[i - 1]).length)
    if closed:
        vs.append(vs[-1] + (cents[0] - cents[-1]).length)
    # u scale from the average ring perimeter
    per = []
    for r in rings:
        if len(r) > 1:
            per.append(sum((r[(k + 1) % len(r)] - r[k]).length for k in range(len(r))))
    perim = (sum(per) / len(per)) if per else 1.0
    us = u_scale if u_scale else perim / tile
    faces = []
    count = len(rings) if closed else len(rings) - 1
    for i in range(count):
        a, b = vr[i], vr[(i + 1) % len(rings)]
        va, vb = vs[i] / tile, vs[i + 1] / tile
        for k in range(n):
            k2 = (k + 1) % n
            ua, ub = k / n * us, (k + 1) / n * us
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                verts = [a[0], b[k2], b[k]]
                uvs = [((ua + ub) / 2, va), (ub, vb), (ua, vb)]
            elif len(b) == 1:
                verts = [a[k], a[k2], b[0]]
                uvs = [(ua, va), (ub, va), ((ua + ub) / 2, vb)]
            else:
                verts = [a[k], a[k2], b[k2], b[k]]
                uvs = [(ua, va), (ub, va), (ub, vb), (ua, vb)]
            try:
                f = bm.faces.new(verts)
            except ValueError:
                continue
            for l, t in zip(f.loops, uvs):
                l[uv].uv = t
            f.smooth = not flat
            faces.append(f)
    caps = []
    if not closed:
        if cap_start and len(vr[0]) > 2:
            try:
                caps.append(bm.faces.new(list(reversed(vr[0]))))
            except ValueError:
                pass
        if cap_end and len(vr[-1]) > 2:
            try:
                caps.append(bm.faces.new(vr[-1]))
            except ValueError:
                pass
    bm.normal_update()
    for f in caps:
        f.smooth = False
        n_ = f.normal
        ax = max(range(3), key=lambda i: abs(n_[i]))
        for l in f.loops:
            c = l.vert.co
            p = [c.y, c.z] if ax == 0 else ([c.x, c.z] if ax == 1 else [c.x, c.y])
            l[uv].uv = (p[0] / tile, p[1] / tile)
    return bm


def circle2d(n, phase=0.0):
    return [(math.cos(TAU * k / n + phase), math.sin(TAU * k / n + phase)) for k in range(n)]


def rrect2d(w, h, r, seg=2):
    """Rounded rectangle outline (CCW), centred, size w x h, corner radius r."""
    pts = []
    r = min(r, w / 2 * 0.999, h / 2 * 0.999)
    corners = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]
    for cx, cy, a0 in corners:
        for s in range(seg + 1):
            a = math.radians(a0 + 90 * s / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def lathe(profile, n=16, tile=None, phase=0.0, flat=False, cap_start=True, cap_end=True, scale_xy=(1, 1)):
    """Revolve [(r, z), ...] (bottom to top for outward normals) about +Z."""
    rings = []
    for r, z in profile:
        if r <= 1e-7:
            rings.append([Vector((0, 0, z))])
        else:
            rings.append([Vector((r * c * scale_xy[0], r * s * scale_xy[1], z)) for c, s in circle2d(n, phase)])
    return skin(rings, cap_start=cap_start, cap_end=cap_end, tile=tile, flat=flat)


def cyl(r, h, n=12, r2=None, bevel=0.0, z0=0.0, tile=None, phase=None, flat=False, caps=True):
    """Cylinder along +Z from z0 to z0+h, optional chamfer on both rims."""
    r2 = r if r2 is None else r2
    if phase is None:
        phase = math.pi / n
    if bevel > 0:
        prof = [(0, z0), (r - bevel, z0), (r, z0 + bevel), (r2, z0 + h - bevel), (r2 - bevel, z0 + h), (0, z0 + h)]
    else:
        prof = [(0, z0), (r, z0), (r2, z0 + h), (0, z0 + h)]
    if not caps:
        prof = prof[1:-1]
    return lathe(prof, n, tile=tile, phase=phase, flat=flat)


def frames(points, up=None, closed=False):
    pts = [Vector(p) for p in points]
    m = len(pts)
    T = []
    for i in range(m):
        if closed:
            t = pts[(i + 1) % m] - pts[i - 1]
        else:
            t = pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)]
        T.append(t.normalized())
    if up is None:
        up = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
    up = Vector(up)
    N0 = (up - T[0] * up.dot(T[0]))
    if N0.length < 1e-6:
        N0 = T[0].orthogonal()
    Ns = [N0.normalized()]
    for i in range(1, m):
        q = T[i - 1].rotation_difference(T[i])
        n_ = q @ Ns[-1]
        n_ = (n_ - T[i] * n_.dot(T[i])).normalized()
        Ns.append(n_)
    return pts, T, Ns


def sweep(points, radius=0.01, n=8, radii=None, scales=None, profile=None, closed=False, caps=True,
          up=None, tile=None, twist=0.0, flat=False, phase=None):
    """Tube along a polyline. profile: list of 2D points (CCW) in units of radius."""
    pts, T, Ns = frames(points, up, closed)
    if profile is None:
        profile = circle2d(n, math.pi / n if phase is None else phase)
    rings = []
    for i, p in enumerate(pts):
        N = Ns[i]
        B = T[i].cross(N)
        r = radii[i] if radii is not None else radius
        sx, sy = scales[i] if scales is not None else (1.0, 1.0)
        a = twist * i
        ca, sa = math.cos(a), math.sin(a)
        ring = []
        for px, py in profile:
            qx, qy = px * ca - py * sa, px * sa + py * ca
            ring.append(p + N * (qx * r * sx) + B * (qy * r * sy))
        rings.append(ring)
    return skin(rings, closed=closed, cap_start=caps, cap_end=caps, tile=tile, flat=flat)


def torus(R, r, nu=16, nv=6, tile=None, scale=(1, 1)):
    pts = [Vector((R * math.cos(TAU * i / nu) * scale[0], R * math.sin(TAU * i / nu) * scale[1], 0)) for i in range(nu)]
    return sweep(pts, r, nv, closed=True, tile=tile, up=(0, 0, 1))


def helix(radius, length, turns, steps_per_turn=10, axis_z0=0.0, phase=0.0, rad_fn=None):
    pts = []
    N = max(2, int(turns * steps_per_turn))
    for i in range(N + 1):
        t = i / N
        a = phase + TAU * turns * t
        r = rad_fn(t) if rad_fn else radius
        pts.append(Vector((r * math.cos(a), r * math.sin(a), axis_z0 + length * t)))
    return pts


def bezier(p0, p1, p2, p3, steps=12):
    p0, p1, p2, p3 = map(Vector, (p0, p1, p2, p3))
    out = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        out.append(p0 * mt ** 3 + p1 * 3 * mt * mt * t + p2 * 3 * mt * t * t + p3 * t ** 3)
    return out


def catenary(a, b, sag, steps=12):
    a, b = Vector(a), Vector(b)
    out = []
    for i in range(steps + 1):
        t = i / steps
        p = a.lerp(b, t)
        p.z -= sag * 4 * t * (1 - t)
        out.append(p)
    return out


def poly_area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def offset_poly(pts, d):
    """Miter-offset a CCW polygon by d (negative = inward)."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e0 = (p1 - p0).normalized()
        e1 = (p2 - p1).normalized()
        n0 = Vector((e0.y, -e0.x))
        n1 = Vector((e1.y, -e1.x))
        m = (n0 + n1)
        if m.length < 1e-6:
            m = n0
        m.normalize()
        cosh = max(0.3, m.dot(n1))
        q = p1 + m * (d / cosh)
        out.append((q.x, q.y))
    return out


def extrude_poly(pts, depth, bevel=0.0, z0=0.0, tile=None, flat=True, bevel_back=True):
    """Extrude a 2D outline along +Z with optional chamfer."""
    pts = list(pts)
    if poly_area(pts) < 0:
        pts.reverse()
    rings = []
    if bevel > 0:
        inner = offset_poly(pts, -bevel)
        if bevel_back:
            rings.append([Vector((x, y, z0)) for x, y in inner])
            rings.append([Vector((x, y, z0 + bevel)) for x, y in pts])
        else:
            rings.append([Vector((x, y, z0)) for x, y in pts])
        rings.append([Vector((x, y, z0 + depth - bevel)) for x, y in pts])
        rings.append([Vector((x, y, z0 + depth)) for x, y in inner])
    else:
        rings = [[Vector((x, y, z0)) for x, y in pts], [Vector((x, y, z0 + depth)) for x, y in pts]]
    return skin(rings, tile=tile, flat=flat)


def blade_poly(pts, thickness, grind=0.012, tile=None):
    """Lens-section blade: sharp outline at z=0, flat faces at +-thickness/2 inset by `grind`."""
    pts = list(pts)
    if poly_area(pts) < 0:
        pts.reverse()
    inner = offset_poly(pts, -grind)
    t = thickness / 2
    rings = [[Vector((x, y, -t)) for x, y in inner], [Vector((x, y, 0)) for x, y in pts],
             [Vector((x, y, t)) for x, y in inner]]
    return skin(rings, tile=tile, flat=True)


def outline_strip(pts, w, z=0.0, tile=None):
    """Flat closed strip (painted outline) along a 2D polygon, width w, facing +Z."""
    pts = list(pts)
    if poly_area(pts) < 0:
        pts.reverse()
    inner = offset_poly(pts, -w)
    bm = bmesh.new()
    uv = uv_layer(bm)
    vo = [bm.verts.new((x, y, z)) for x, y in pts]
    vi = [bm.verts.new((x, y, z)) for x, y in inner]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new([vi[i], vo[i], vo[j], vi[j]])
        f.smooth = False
    uv_box(bm, tile)
    return bm


def quad(w, h, normal="-Y", tile=None):
    """Single flat quad centred at origin, facing `normal`. UV 0..1 (for screens / sign boards)."""
    bm = bmesh.new()
    uv = uv_layer(bm)
    hw, hh = w / 2, h / 2
    if normal == "-Y":
        co = [(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)]
    elif normal == "+Z":
        co = [(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)]
    elif normal == "+Y":
        co = [(hw, 0, -hh), (-hw, 0, -hh), (-hw, 0, hh), (hw, 0, hh)]
    else:
        raise ValueError(normal)
    vs = [bm.verts.new(c) for c in co]
    f = bm.faces.new(vs)
    f.smooth = False
    for l, t in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        l[uv].uv = t
    bm.normal_update()
    return bm


def icosphere(radius=1.0, subdiv=2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    return bm


def uvsphere(radius=1.0, u=12, v=8, scale=(1, 1, 1), tile=None):
    prof = []
    for i in range(v + 1):
        a = -math.pi / 2 + math.pi * i / v
        prof.append((radius * math.cos(a), radius * math.sin(a) * scale[2]))
    bm = lathe(prof, u, tile=tile, scale_xy=(scale[0], scale[1]))
    return bm


def displace(bm, amp=0.1, freq=1.5, seed=0, octaves=3, center=(0, 0, 0), along_normal=True):
    bm.normal_update()
    c = Vector(center)
    for v in bm.verts:
        d = fbm(v.co * freq, seed, octaves)
        n = v.normal if along_normal else (v.co - c).normalized()
        v.co += n * d * amp
    bm.normal_update()


def facet_cut(bm, planes):
    """Project vertices beyond planes (n, d) back onto them -> fractured flat facets."""
    for n, d in planes:
        n = Vector(n).normalized()
        for v in bm.verts:
            s = v.co.dot(n) - d
            if s > 0:
                v.co -= n * s
    bm.normal_update()


def random_planes(rng, count, dist_min, dist_max, z_min=-1.0):
    out = []
    for _ in range(count):
        while True:
            n = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(z_min, 1)))
            if 0.2 < n.length <= 1:
                break
        out.append((n.normalized(), rng.uniform(dist_min, dist_max)))
    return out


def rock(radius=0.5, seed=0, subdiv=2, scale=(1, 1, 1), amp=0.22, freq=1.3, octaves=3, flat_bottom=None,
         facets=0, facet_depth=(0.75, 0.92), squash=0.12):
    """Displaced icosphere rock. flat_bottom: z (after scale) below which the shape is squashed flat."""
    rng = random.Random(seed)
    bm = icosphere(1.0, subdiv)
    for v in bm.verts:
        d = fbm(v.co * freq, seed, octaves)
        v.co *= 1.0 + amp * d
    if facets:
        facet_cut(bm, random_planes(rng, facets, facet_depth[0], facet_depth[1]))
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0] * radius, v.co.y * scale[1] * radius, v.co.z * scale[2] * radius))
    if flat_bottom is not None:
        for v in bm.verts:
            if v.co.z < flat_bottom:
                v.co.z = flat_bottom + (v.co.z - flat_bottom) * squash
    bm.normal_update()
    return bm


def hull(points):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in points]
    res = bmesh.ops.convex_hull(bm, input=vs)
    kill = list({id(g): g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)}.values())
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="VERTS")
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = False
    return bm


def shard(length, width, seed=0, n=12, taper=0.15, bend=0.0, depth_ratio=0.7):
    """Angular obsidian-like shard along +Z from z=0 (base) to the tip."""
    rng = random.Random(seed)
    pts = []
    for i in range(n):
        t = i / (n - 1)
        z = length * (t ** 0.9)
        w = width * (1 - t * (1 - taper))
        a = rng.uniform(0, TAU)
        rr = w * rng.uniform(0.8, 1.0)
        pts.append(Vector((rr * math.cos(a), rr * math.sin(a) * depth_ratio, z)))
    for k in range(4):
        a = TAU * k / 4 + rng.uniform(-0.4, 0.4)
        pts.append(Vector((width * math.cos(a), width * math.sin(a) * depth_ratio, -0.02 * length)))
    tip = Vector((rng.uniform(-0.1, 0.1) * width + bend * length, rng.uniform(-0.1, 0.1) * width, length * 1.04))
    pts.append(tip)
    return hull(pts)


def prism(r, h, sides=6, tip=0.28, taper=0.9, z0=0.0, seed=0, skew=0.0, tile=None):
    """Hexagonal crystal prism along +Z with pyramidal tip."""
    rng = random.Random(seed)
    jit = [rng.uniform(0.9, 1.1) for _ in range(sides)]
    ring = lambda rad, z: [Vector((rad * jit[k] * math.cos(TAU * k / sides), rad * jit[k] * math.sin(TAU * k / sides), z))
                           for k in range(sides)]
    body = h * (1 - tip)
    rings = [ring(r * 1.02, z0 - 0.05 * h), ring(r, z0), ring(r * taper, z0 + body),
             [Vector((skew * r, rng.uniform(-0.15, 0.15) * r, z0 + h))]]
    return skin(rings, tile=tile, flat=True)


def bolt(r=0.008, h=0.005, washer=True, n=6, bevel=False):
    """Hex bolt head (+Z) with an optional washer; base at z=0."""
    bm = cyl(r, h, n=n, bevel=min(h * 0.3, r * 0.2) if bevel else 0.0, z0=0.0 if not washer else h * 0.25, flat=True, phase=0)
    if washer:
        merge_into(bm, cyl(r * 1.35, h * 0.25, n=max(8, n + 2), flat=False))
    return bm


def rivet(r=0.006, h=0.003, n=6):
    prof = [(0, 0), (r, 0), (r * 0.85, h * 0.6), (r * 0.45, h * 0.95), (0, h)]
    return lathe(prof, n, flat=False)


def merge_into(dst, src, matrix=None):
    """Append src bmesh into dst (keeps UVs).  Frees src."""
    uvd = uv_layer(dst)
    uvs = src.loops.layers.uv.get("UVMap")
    m = matrix if matrix is not None else Matrix()
    flip = m.determinant() < 0
    vmap = {}
    for v in src.verts:
        vmap[v] = dst.verts.new(m @ v.co)
    for f in src.faces:
        vs = [vmap[v] for v in f.verts]
        ls = list(f.loops)
        if flip:
            vs.reverse(); ls.reverse()
        try:
            nf = dst.faces.new(vs)
        except ValueError:
            continue
        nf.smooth = f.smooth
        nf.material_index = f.material_index
        if uvs is not None:
            for ld, lsrc in zip(nf.loops, ls):
                ld[uvd].uv = lsrc[uvs].uv
    src.free()
    dst.normal_update()
    return dst


def jitter(bm, amt, seed=0):
    rng = random.Random(seed)
    for v in bm.verts:
        v.co += Vector((rng.uniform(-amt, amt), rng.uniform(-amt, amt), rng.uniform(-amt, amt)))
    bm.normal_update()


def dent(bm, center, radius, depth, direction=None):
    c = Vector(center)
    for v in bm.verts:
        d = (v.co - c).length
        if d < radius:
            f = (1 - d / radius) ** 2
            dirv = Vector(direction) if direction else -(v.normal)
            v.co += dirv.normalized() * depth * f
    bm.normal_update()


def transform(bm, m):
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    if m.determinant() < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.normal_update()
    return bm


def set_flat(bm, flat=True):
    for f in bm.faces:
        f.smooth = not flat
    return bm


# --------------------------------------------------------------------------------------------
# Model builder: merges parts with materials into one mesh object
# --------------------------------------------------------------------------------------------
class MB:
    def __init__(self, tile=0.4):
        self.bm = bmesh.new()
        self.uv = uv_layer(self.bm)
        self.mats = []
        self.tile = tile
        self.groups = {}
        TILE[0] = tile

    def mi(self, name):
        if name not in CATALOG:
            raise ValueError("material %r not in catalog" % name)
        if name not in self.mats:
            self.mats.append(name)
        return self.mats.index(name)

    def add(self, part, mat, m=None, tile=None, uv="auto", flat=None, group=None):
        """Add a part. mat: catalog name or callable(face)->name. uv: 'auto' (keep if present
        else box), 'box' (force box projection in part space)."""
        tile = tile or self.tile
        if uv == "box" or not has_uv(part):
            uv_box(part, tile)
        part.normal_update()
        for f in part.faces:
            name = mat(f) if callable(mat) else mat
            f.material_index = self.mi(name)
            if flat is not None:
                f.smooth = not flat
        if group:
            mm = m if m is not None else Matrix()
            mn, mx = self.groups.get(group, (Vector((1e9,) * 3), Vector((-1e9,) * 3)))
            for v in part.verts:
                p = mm @ v.co
                for i in range(3):
                    mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
            self.groups[group] = (mn, mx)
        merge_into(self.bm, part, m)
        return self

    def gb(self, group, pad=0.0):
        mn, mx = self.groups[group]
        p = Vector((pad, pad, pad))
        return mn - p, mx + p

    def center(self):
        """Move geometry so its bounding-box centre sits at the origin (pivot at centre)."""
        mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
        for v in self.bm.verts:
            for i in range(3):
                mn[i] = min(mn[i], v.co[i]); mx[i] = max(mx[i], v.co[i])
        c = (mn + mx) / 2
        bmesh.ops.translate(self.bm, vec=-c, verts=self.bm.verts)
        for g, (a, b) in self.groups.items():
            self.groups[g] = (a - c, b - c)
        return c

    def transform(self, m):
        bmesh.ops.transform(self.bm, matrix=m, verts=self.bm.verts)
        if m.determinant() < 0:
            bmesh.ops.reverse_faces(self.bm, faces=self.bm.faces)
        self.bm.normal_update()
        return self

    def bounds(self):
        mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
        for v in self.bm.verts:
            for i in range(3):
                mn[i] = min(mn[i], v.co[i]); mx[i] = max(mx[i], v.co[i])
        return mn, mx

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def to_object(self, name, parent=None, pivot=(0, 0, 0), smooth_angle=40.0, weighted=True, collection=None):
        piv = Vector(pivot)
        bm = self.bm
        if piv.length > 0:
            bmesh.ops.translate(bm, vec=-piv, verts=bm.verts)
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for mn in self.mats:
            me.materials.append(get_mat(mn))
        me.validate(clean_customdata=False)
        if smooth_angle is not None:
            me.set_sharp_from_angle(angle=math.radians(smooth_angle))
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        if parent is not None:
            ob.parent = parent
        ob.location = piv
        if weighted and len(me.polygons):
            mod = ob.modifiers.new("WN", "WEIGHTED_NORMAL")
            mod.keep_sharp = True
            mod.weight = 50
            apply_modifiers(ob)
        return ob


def apply_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)


def empty(name, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), size=0.04, collection=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "ARROWS"
    e.empty_display_size = size
    (collection or bpy.context.scene.collection).objects.link(e)
    e.parent = parent
    e.location = Vector(loc)
    e.rotation_euler = Euler([math.radians(r) for r in rot])
    return e


def col_box(name, parent, mn, mx, collection=None):
    """COL_ helper: a plain 8-vertex box mesh (no material)."""
    bm = box_mm(mn, mx)
    uv_box(bm, 1.0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.parent = parent
    ob.display_type = "WIRE"
    ob.hide_render = True
    return ob


def bounds_of(objs, root):
    """Bounds of mesh objects in root's local space."""
    inv = root.matrix_world.inverted()
    mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9))
    found = False
    for o in objs:
        if o.type != "MESH":
            continue
        m = inv @ o.matrix_world
        for v in o.data.vertices:
            p = m @ v.co
            found = True
            for i in range(3):
                mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    if not found:
        return Vector(), Vector()
    return mn, mx


def descendants(ob):
    out = []
    for c in ob.children:
        out.append(c)
        out.extend(descendants(c))
    return out


def clean_name(n):
    return re.sub(r"\.\d{3}$", "", n)


def mesh_tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0


# --------------------------------------------------------------------------------------------
# Kit pipeline: manifest, export, save
# --------------------------------------------------------------------------------------------
def object_record(root, kit, notes=""):
    allc = descendants(root)
    render_meshes = ([root] if root.type == "MESH" else []) + [c for c in allc if c.type == "MESH" and not clean_name(c.name).startswith("COL_")]
    mn, mx = bounds_of(render_meshes, root)
    tris = sum(mesh_tris(o) for o in render_meshes)
    mats = []
    for o in render_meshes:
        for m in o.data.materials:
            if m and m.name not in mats:
                mats.append(m.name)
    inv = root.matrix_world.inverted()
    helpers = {}
    children = []
    colliders = {}
    for c in allc:
        cn = clean_name(c.name)
        children.append(cn)
        if cn.startswith("COL_") and c.type == "MESH":
            cmn, cmx = bounds_of([c], root)
            ctr = (cmn + cmx) / 2
            helpers[cn] = [round(ctr.x, 4), round(ctr.y, 4), round(ctr.z, 4)]
            colliders[cn] = {"min": [round(v, 4) for v in cmn], "max": [round(v, 4) for v in cmx]}
        elif c.type == "EMPTY":
            p = (inv @ c.matrix_world).translation
            helpers[cn] = [round(p.x, 4), round(p.y, 4), round(p.z, 4)]
    return {
        "kit": kit,
        "bounds_min": [round(v, 4) for v in mn],
        "bounds_max": [round(v, 4) for v in mx],
        "bounds_size": [round(mx[i] - mn[i], 4) for i in range(3)],
        "tris": tris,
        "materials": mats,
        "children": children,
        "helpers": helpers,
        "colliders": colliders,
        "child_pivots": {clean_name(c.name): [round(v, 4) for v in (inv @ c.matrix_world).translation]
                         for c in allc if c.type == "MESH" and not clean_name(c.name).startswith("COL_")},
        "notes": notes,
    }


_NAME_PATCHED = False


def _patch_fbx_names():
    """Blender cannot hold two objects called `Base`; the game needs the exact name in every prefab.
    Strip Blender's automatic `.NNN` suffix from FBX Model names at export time."""
    global _NAME_PATCHED
    if _NAME_PATCHED:
        return
    import io_scene_fbx.fbx_utils as fu
    orig = fu.ObjectWrapper.__init__

    def init(self, bdata, armature=None):
        orig(self, bdata, armature)
        self.name = clean_name(self.name)

    fu.ObjectWrapper.__init__ = init
    _NAME_PATCHED = True


def export_fbx(path, roots):
    _patch_fbx_names()
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for r in roots:
        r.location = (0, 0, 0)
        r.select_set(True)
        for c in descendants(r):
            c.select_set(True)
    bpy.context.view_layer.objects.active = roots[0]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"ARMATURE", "MESH", "EMPTY"},
        apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", bake_space_transform=False,
        use_mesh_modifiers=True, mesh_smooth_type="FACE", use_tspace=True, add_leaf_bones=False,
        primary_bone_axis="Y", secondary_bone_axis="X", armature_nodetype="NULL",
        bake_anim=False, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, path_mode="STRIP")


# --------------------------------------------------------------------------------------------
# Surface snapping (veins, crusts following an arbitrary surface)
# --------------------------------------------------------------------------------------------
def bvh_of(bm, matrix=None):
    from mathutils.bvhtree import BVHTree
    if matrix is None:
        return BVHTree.FromBMesh(bm)
    tmp = bm.copy()
    bmesh.ops.transform(tmp, matrix=matrix, verts=tmp.verts)
    t = BVHTree.FromBMesh(tmp)
    tmp.free()
    return t


def snap_points(tree, pts, offset=0.0, ray_from=None):
    """Snap points onto the surface. ray_from: if given, cast a ray from that centre outward through each point
    (keeps paths on the visible outer hull); otherwise nearest-point."""
    out = []
    for p in pts:
        p = Vector(p)
        hit = None
        if ray_from is not None:
            c = Vector(ray_from)
            d = (p - c).normalized()
            far = c + d * 10.0
            loc, n, i, dist = tree.ray_cast(far, -d)
            if loc is not None:
                hit = (loc, n)
        if hit is None:
            loc, n, i, dist = tree.find_nearest(p)
            hit = (loc, n)
        out.append(hit[0] + hit[1] * offset)
    return out


def walk_on_sphere(rng, start_dir, steps, step_ang, wander=0.6, bias=None):
    """Random walk of directions on the unit sphere (for vein paths)."""
    d = Vector(start_dir).normalized()
    t = d.orthogonal().normalized()
    if bias is not None:
        b = Vector(bias)
        b = b - d * b.dot(d)
        if b.length > 1e-5:
            t = b.normalized()
    out = [d.copy()]
    for _ in range(steps):
        ax = d.cross(t).normalized()
        from mathutils import Quaternion
        t = Quaternion(d, rng.uniform(-wander, wander)) @ t
        d = (Quaternion(d.cross(t).normalized(), step_ang) @ d).normalized()
        t = (t - d * t.dot(d)).normalized()
        out.append(d.copy())
    return out


def veins(tree, rng, center, radius, starts, steps=8, step_ang=0.22, r0=0.003, r1=0.001, branch=2, offset_k=0.35,
          bias=None, sides=4):
    """Return list of tube bmeshes for a branching vein network crawling over the surface in `tree`."""
    parts = []
    c = Vector(center)
    for sd in starts:
        trunk = walk_on_sphere(rng, sd, steps, step_ang, 0.5, bias)
        paths = [(trunk, r0, r1)]
        for b in range(branch):
            k = rng.randint(1, max(1, steps - 3))
            br = walk_on_sphere(rng, trunk[k], max(3, steps - k - 1), step_ang * 0.9, 0.9)
            rr = r0 * (1 - k / steps) * 0.8 + r1
            paths.append((br, rr, r1 * 0.7))
        for dirs, ra, rb in paths:
            pts = [c + d * radius * 1.5 for d in dirs]
            pts = snap_points(tree, pts, 0.0, ray_from=c)
            n = len(pts)
            radii = [lerp(ra, rb, i / (n - 1)) for i in range(n)]
            # sink each point by a fraction of its radius so the vein sits in the surface
            tr = []
            for i, p in enumerate(pts):
                dvec = (p - c).normalized()
                tr.append(p + dvec * radii[i] * offset_k)
            parts.append(sweep(tr, 1.0, sides, radii=radii, caps=True))
    return parts


def surface_hit(tree, center, direction, far=20.0):
    """Outermost surface point of `tree` along a ray from `center` in `direction` (cast inward from far away)."""
    c = Vector(center)
    d = Vector(direction).normalized()
    loc, n, i, dist = tree.ray_cast(c + d * far, -d)
    if loc is None:
        loc, n, i, dist = tree.find_nearest(c + d)
    return loc, n


def ridge(points, normals, height, thick, seed=0, jag=0.3, depth=0.03, tile=None, taper_ends=True):
    """Jagged crest standing out of a surface along points (with surface normals)."""
    rng = random.Random(seed)
    pts = [Vector(p) for p in points]
    m = len(pts)
    rings = []
    for i in range(m):
        t = (pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)]).normalized()
        n = Vector(normals[i]).normalized()
        b = t.cross(n).normalized()
        n = b.cross(t).normalized()
        u = i / (m - 1)
        f = math.sin(math.pi * u) ** 0.5 if taper_ends else 1.0
        f = max(f, 0.15)
        h = height * f * (1 + jag * rng.uniform(-1, 1))
        w = thick * (0.45 + 0.55 * f)
        prof = [(-depth, -w / 2), (h * 0.55, -w * 0.42), (h, rng.uniform(-0.12, 0.12) * w), (h * 0.55, w * 0.42), (-depth, w / 2)]
        rings.append([pts[i] + n * px + b * py for px, py in prof])
    return skin(rings, tile=tile, flat=False)


def top_hit(tree, x, y, z_from=10.0):
    """First surface hit straight down from above (x, y)."""
    loc, n, i, dist = tree.ray_cast(Vector((x, y, z_from)), Vector((0, 0, -1)))
    return loc, n
