"""
MONKEY NO FEAR - shared creature toolkit (Blender 5.0, headless-safe).

Pipeline used by every creature script:
  1. Field (signed distance field) built from tapered capsules / ellipsoids with smooth unions and
     smooth subtractions  ->  marching cubes  ->  sculpt-like noise displacement  ->  smoothing  ->
     decimation to the triangle budget.
  2. Region based material assignment (nearest tagged primitive + noise patch rules).
  3. Detail parts (teeth, nails, eyes, tendons, growths, tufts...) built as explicit geometry with
     explicit rigid bone weights (or weights copied from the nearest skin vertex).
  4. Armature with the exact spec bone names, automatic (bone heat) weights for the skin, rigid
     overrides for jaws / eyes, join into ONE skinned mesh.
  5. Procedural clip authoring: poses are dicts of world-axis Euler offsets per bone, hips offsets,
     analytic two-bone IK targets (planted feet / hands) with FK/IK blending, baked every frame.
  6. Deformation sanity check (edge stretch over every clip), .blend save, FBX export with the spec
     settings, Cycles previews (turnaround, fog silhouette, contact sheet).

Conventions: metres, Z up, creatures face -Y, .L side is +X. 30 fps. Loop clips: frame 0 == frame N.
Rotation authoring (pose 'r' entries) is in ARMATURE axes, applied about the bone head relative to
the parent (i.e. "rotate this bone about world X by 20 deg as if the parent were at rest"):
  +X rotation tilts an upward-pointing bone FORWARD (toward -Y) and swings a downward bone BACKWARD.
  +Z rotation yaws a forward-pointing bone toward the creature's LEFT (+X).
  +Y rotation leans an upward-pointing bone toward the creature's LEFT (+X).
All randomness is seeded -> deterministic and re-runnable.
"""
import bpy
import bmesh
import math
import os
import sys
import json
import time
import subprocess
import numpy as np
from mathutils import Vector, Matrix, Quaternion, Euler
from mathutils.kdtree import KDTree

# --------------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FBX_DIR = os.path.join(PROJECT, "Assets", "MonkeyNoFear", "Art", "Models", "Creatures")
BLEND_DIR = os.path.join(PROJECT, "SourceArt", "Creatures")
PREVIEW_DIR = os.path.join(PROJECT, "Docs", "previews", "creatures")
TEX_DIR = os.path.join(PROJECT, "Assets", "MonkeyNoFear", "Art", "Textures")
MANIFEST = os.path.join(FBX_DIR, "creatures_manifest.json")
FPS = 30

for _d in (FBX_DIR, BLEND_DIR, PREVIEW_DIR):
    os.makedirs(_d, exist_ok=True)


def log(*a):
    print("[mnf]", *a, flush=True)


def script_args():
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1:]
    return []


def preview_enabled():
    return "--no-preview" not in script_args()


# --------------------------------------------------------------------------------------------
# Scene
# --------------------------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    return sc


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def activate(obj, others=()):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in others:
        o.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


# --------------------------------------------------------------------------------------------
# Small math helpers
# --------------------------------------------------------------------------------------------
def V(*a):
    if len(a) == 1:
        return Vector(a[0])
    return Vector(a)


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def smootherstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (x * 6 - 15) + 10)


def ease_out(x, p=2.0):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** p


def ease_in(x, p=2.0):
    x = min(max(x, 0.0), 1.0)
    return x ** p


def lerp(a, b, t):
    return a + (b - a) * t


def ramp(t, t0, t1):
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return min(max((t - t0) / (t1 - t0), 0.0), 1.0)


def pulse(t, t0, t1, t2, t3):
    """0 before t0, smooth up to 1 at t1, hold, smooth down to 0 at t3 (from t2)."""
    return smoothstep(ramp(t, t0, t1)) * (1 - smoothstep(ramp(t, t2, t3)))


def pnoise(u, seed, harmonics=(1, 2, 3), amps=None):
    """Loop-safe 1D noise in [-1,1]-ish: sum of integer-frequency sines over u in [0,1]."""
    rng = np.random.RandomState(seed)
    ph = rng.uniform(0, 2 * math.pi, len(harmonics))
    if amps is None:
        amps = [1.0 / (i + 1) for i in range(len(harmonics))]
    s = sum(a * math.sin(2 * math.pi * k * u + p) for k, a, p in zip(harmonics, amps, ph))
    return s / sum(amps)


def tnoise(t, seed, freq=1.0):
    """Non-periodic smooth noise for one-shots."""
    rng = np.random.RandomState(seed)
    fr = rng.uniform(0.7, 1.4, 3) * freq
    ph = rng.uniform(0, 2 * math.pi, 3)
    return (math.sin(t * fr[0] * 6.283 + ph[0]) + 0.5 * math.sin(t * fr[1] * 13.1 + ph[1])
            + 0.25 * math.sin(t * fr[2] * 27.7 + ph[2])) / 1.75


# --------------------------------------------------------------------------------------------
# 3D value noise (deterministic)
# --------------------------------------------------------------------------------------------
class Noise3:
    def __init__(self, seed, size=48, smooth=1.2):
        from scipy.ndimage import gaussian_filter
        rng = np.random.RandomState(seed)
        g = rng.standard_normal((size, size, size)).astype(np.float32)
        g = gaussian_filter(g, smooth, mode='wrap')
        g /= (g.std() + 1e-9)
        self.g = g
        self.size = size

    def __call__(self, P, freq=1.0, offset=(0, 0, 0)):
        from scipy.ndimage import map_coordinates
        P = np.asarray(P, np.float64)
        c = ((P + np.asarray(offset)) * freq * 4.0).T  # 4 lattice cells per unit at freq 1
        return map_coordinates(self.g, c % self.size, order=1, mode='wrap')

    def fbm(self, P, freq=1.0, octaves=3, gain=0.5):
        s = 0.0
        a = 1.0
        tot = 0.0
        for o in range(octaves):
            s = s + a * self(P, freq * (2.0 ** o), offset=(o * 3.7, o * 1.3, o * 5.1))
            tot += a
            a *= gain
        return s / tot


# --------------------------------------------------------------------------------------------
# Signed distance primitives
# --------------------------------------------------------------------------------------------
class Prim:
    mat = None
    bone = None
    tag = ""

    def aabb(self):
        raise NotImplementedError

    def dist(self, X, Y, Z):
        raise NotImplementedError

    def dist_pts(self, P):
        P = np.asarray(P)
        return self.dist(P[:, 0], P[:, 1], P[:, 2])


class Capsule(Prim):
    """Tapered capsule (round cone approximation) from a (radius ra) to b (radius rb)."""

    def __init__(self, a, b, ra, rb=None, mat=None, bone=None, tag=""):
        self.a = np.array(a, float)
        self.b = np.array(b, float)
        self.ra = float(ra)
        self.rb = float(ra if rb is None else rb)
        self.mat, self.bone, self.tag = mat, bone, tag

    def aabb(self):
        r = max(self.ra, self.rb)
        return np.minimum(self.a, self.b) - r, np.maximum(self.a, self.b) + r

    def dist(self, X, Y, Z):
        a, b = self.a, self.b
        ba = b - a
        bb = float(ba.dot(ba)) + 1e-12
        px, py, pz = X - a[0], Y - a[1], Z - a[2]
        h = np.clip((px * ba[0] + py * ba[1] + pz * ba[2]) / bb, 0.0, 1.0)
        dx, dy, dz = px - ba[0] * h, py - ba[1] * h, pz - ba[2] * h
        return np.sqrt(dx * dx + dy * dy + dz * dz) - (self.ra + (self.rb - self.ra) * h)


class Ellipsoid(Prim):
    def __init__(self, c, r, rot=(0, 0, 0), mat=None, bone=None, tag=""):
        self.c = np.array(c, float)
        self.r = np.array(r, float) if np.ndim(r) else np.array([r, r, r], float)
        self.R = np.array(Euler([math.radians(x) for x in rot], 'XYZ').to_matrix())
        self.mat, self.bone, self.tag = mat, bone, tag

    def aabb(self):
        ext = np.abs(self.R) @ self.r
        return self.c - ext, self.c + ext

    def dist(self, X, Y, Z):
        px, py, pz = X - self.c[0], Y - self.c[1], Z - self.c[2]
        R = self.R  # local = R^T p
        lx = R[0, 0] * px + R[1, 0] * py + R[2, 0] * pz
        ly = R[0, 1] * px + R[1, 1] * py + R[2, 1] * pz
        lz = R[0, 2] * px + R[1, 2] * py + R[2, 2] * pz
        r = self.r
        k0 = np.sqrt((lx / r[0]) ** 2 + (ly / r[1]) ** 2 + (lz / r[2]) ** 2)
        k1 = np.sqrt((lx / r[0] ** 2) ** 2 + (ly / r[1] ** 2) ** 2 + (lz / r[2] ** 2) ** 2) + 1e-9
        return k0 * (k0 - 1.0) / k1


def frame_matrix(z_dir, y_hint=(0, -1, 0)):
    """Rotation matrix whose columns are (x, y, z) with z along z_dir and y as close to y_hint."""
    z = np.array(z_dir, float)
    z /= np.linalg.norm(z)
    y = np.array(y_hint, float)
    y = y - z * y.dot(z)
    if np.linalg.norm(y) < 1e-6:
        y = np.array([1.0, 0, 0]) - z * z[0]
    y /= np.linalg.norm(y)
    x = np.cross(y, z)
    return np.stack([x, y, z], 1)


def EllipsoidBetween(a, b, r_x, r_y, mat=None, bone=None, tag="", y_hint=(0, -1, 0), extend=1.0):
    """Ellipsoid whose long axis (local z) spans a->b; r_x / r_y are the cross-section radii,
    local y as close as possible to y_hint."""
    a, b = np.array(a, float), np.array(b, float)
    e = Ellipsoid((a + b) / 2, (r_x, r_y, np.linalg.norm(b - a) / 2 * extend), (0, 0, 0), mat, bone, tag)
    e.R = frame_matrix(b - a, y_hint)
    return e


class FlatCapsule(Prim):
    """Capsule with an elliptical cross-section: 'flat' scales the axis 'up' (perpendicular to the
    segment) by factor flat (<1 = flattened)."""

    def __init__(self, a, b, ra, rb=None, up=(0, 0, 1), flat=0.5, mat=None, bone=None, tag=""):
        self.a = np.array(a, float)
        self.b = np.array(b, float)
        self.ra = float(ra)
        self.rb = float(ra if rb is None else rb)
        d = self.b - self.a
        d = d / (np.linalg.norm(d) + 1e-12)
        u = np.array(up, float)
        u = u - d * u.dot(d)
        u /= (np.linalg.norm(u) + 1e-12)
        self.u = u
        self.flat = flat
        self.mat, self.bone, self.tag = mat, bone, tag

    def aabb(self):
        r = max(self.ra, self.rb)
        return np.minimum(self.a, self.b) - r, np.maximum(self.a, self.b) + r

    def dist(self, X, Y, Z):
        a, b, u = self.a, self.b, self.u
        ba = b - a
        bb = float(ba.dot(ba)) + 1e-12
        px, py, pz = X - a[0], Y - a[1], Z - a[2]
        h = np.clip((px * ba[0] + py * ba[1] + pz * ba[2]) / bb, 0.0, 1.0)
        dx, dy, dz = px - ba[0] * h, py - ba[1] * h, pz - ba[2] * h
        du = dx * u[0] + dy * u[1] + dz * u[2]
        # scale the 'up' component
        s = 1.0 / self.flat
        dx2 = dx + u[0] * du * (s - 1)
        dy2 = dy + u[1] * du * (s - 1)
        dz2 = dz + u[2] * du * (s - 1)
        return (np.sqrt(dx2 * dx2 + dy2 * dy2 + dz2 * dz2) - (self.ra + (self.rb - self.ra) * h)) * self.flat


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


class Field:
    def __init__(self, lo, hi, voxel):
        self.lo = np.array(lo, float)
        self.hi = np.array(hi, float)
        self.voxel = float(voxel)
        self.n = (np.ceil((self.hi - self.lo) / voxel).astype(int) + 1)
        self.axes = [self.lo[i] + np.arange(self.n[i]) * voxel for i in range(3)]
        self.f = np.full(tuple(self.n), 5.0, np.float32)
        self.prims = []      # union prims (for ownership)
        self.subs = []       # subtraction prims (for ownership: e.g. mouth interiors)
        log("field", tuple(self.n), "voxels", int(np.prod(self.n)))

    def _block(self, bmin, bmax):
        i0 = np.clip(np.floor((bmin - self.lo) / self.voxel).astype(int), 0, self.n - 1)
        i1 = np.clip(np.ceil((bmax - self.lo) / self.voxel).astype(int) + 1, 1, self.n)
        sl = tuple(slice(i0[i], i1[i]) for i in range(3))
        X = self.axes[0][sl[0]][:, None, None]
        Y = self.axes[1][sl[1]][None, :, None]
        Z = self.axes[2][sl[2]][None, None, :]
        return sl, X, Y, Z

    def add(self, prim, k=0.02, mirror=False):
        prims = [prim]
        if mirror:
            prims.append(mirror_prim(prim))
        for p in prims:
            bmin, bmax = p.aabb()
            m = k + 3 * self.voxel
            sl, X, Y, Z = self._block(bmin - m, bmax + m)
            if any(s.stop <= s.start for s in sl):
                continue
            d = p.dist(X, Y, Z).astype(np.float32)
            self.f[sl] = smin(self.f[sl], d, k)
            if p.mat is not None or p.bone is not None:
                self.prims.append(p)
        return prims

    def sub(self, prim, k=0.01, mirror=False, keep=True):
        prims = [prim]
        if mirror:
            prims.append(mirror_prim(prim))
        for p in prims:
            bmin, bmax = p.aabb()
            m = k + 3 * self.voxel
            sl, X, Y, Z = self._block(bmin - m, bmax + m)
            if any(s.stop <= s.start for s in sl):
                continue
            d = p.dist(X, Y, Z).astype(np.float32)
            self.f[sl] = smax(self.f[sl], -d, k)
            if keep:
                self.subs.append(p)
        return prims

    def mesh_data(self):
        from skimage.measure import marching_cubes
        f = self.f.copy()
        # make sure the border is outside
        f[0, :, :] = f[-1, :, :] = 1
        f[:, 0, :] = f[:, -1, :] = 1
        f[:, :, 0] = f[:, :, -1] = 1
        verts, faces, normals, _ = marching_cubes(f, level=0.0, spacing=(self.voxel,) * 3)
        verts = verts + self.lo
        return verts, faces


def mirror_prim(p):
    import copy
    q = copy.copy(p)
    if isinstance(p, (Capsule, FlatCapsule)):
        q.a = p.a * np.array([-1, 1, 1])
        q.b = p.b * np.array([-1, 1, 1])
        if isinstance(p, FlatCapsule):
            q.u = p.u * np.array([-1, 1, 1])
    elif isinstance(p, Ellipsoid):
        q.c = p.c * np.array([-1, 1, 1])
        M = np.diag([-1.0, 1, 1])
        q.R = M @ p.R @ M
    if p.bone:
        q.bone = mirror_name(p.bone)
    q.tag = mirror_name(p.tag) if p.tag else p.tag
    return q


def mirror_name(n):
    if n.endswith(".L"):
        return n[:-2] + ".R"
    if n.endswith(".R"):
        return n[:-2] + ".L"
    return n


# --------------------------------------------------------------------------------------------
# Mesh helpers
# --------------------------------------------------------------------------------------------
def mesh_from_arrays(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(np.asarray(verts, np.float64).tolist(), [], np.asarray(faces, np.int64).tolist())
    me.update(calc_edges=True)
    me.validate()
    obj = bpy.data.objects.new(name, me)
    link(obj)
    return obj


def get_verts(obj):
    me = obj.data
    a = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def set_verts(obj, co):
    obj.data.vertices.foreach_set("co", np.asarray(co, np.float64).ravel())
    obj.data.update()


def get_normals(obj):
    me = obj.data
    a = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("normal", a)
    return a.reshape(-1, 3)


def apply_modifiers(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = obj.data
    obj.modifiers.clear()
    obj.data = me
    bpy.data.meshes.remove(old)


def fix_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def keep_largest_island(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    seen = set()
    islands = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]
        isl = []
        seen.add(v.index)
        while stack:
            x = stack.pop()
            isl.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        islands.append(isl)
    islands.sort(key=len, reverse=True)
    removed = 0
    kept = [i for i in islands if len(i) >= 0.02 * len(islands[0])]
    for isl in kept[1:]:
        c = sum((v.co for v in isl), Vector()) / len(isl)
        log("  separate island of %d verts at (%.3f, %.3f, %.3f)" % (len(isl), c.x, c.y, c.z))
    if len(kept) > 1:
        log("WARNING: body has %d separate islands (sizes %s)" % (len(kept), [len(i) for i in kept]))
    for isl in islands[1:]:
        if len(isl) < 0.02 * len(islands[0]):
            c = sum((v.co for v in isl), Vector()) / len(isl)
            log("  dropping island of %d verts at (%.3f, %.3f, %.3f)" % (len(isl), c.x, c.y, c.z))
            bmesh.ops.delete(bm, geom=isl, context='VERTS')
            removed += len(isl)
    bm.to_mesh(obj.data)
    bm.free()
    if removed:
        log("removed small islands verts:", removed)
    return len(kept)


def laplacian_smooth(obj, iterations=2, factor=0.5):
    mod = obj.modifiers.new("smooth", 'SMOOTH')
    mod.factor = factor
    mod.iterations = iterations
    apply_modifiers(obj)


def decimate_to(obj, target_tris, importance=None, factor=0.3):
    """importance: per-vertex weights in [0,1]; higher = keep more detail there."""
    n = tri_count(obj)
    if n <= target_tris:
        return
    mod = obj.modifiers.new("dec", 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = target_tris / n
    mod.use_collapse_triangulate = True
    if importance is not None:
        vg = obj.vertex_groups.new(name="_importance")
        for i, w in enumerate(importance):
            vg.add([i], float(1.0 - min(0.95, 0.1 * factor) * min(max(w, 0.0), 1.0)), 'REPLACE')
        mod.vertex_group = vg.name
        mod.vertex_group_factor = 1.0
    apply_modifiers(obj)
    g = obj.vertex_groups.get("_importance")
    if g:
        obj.vertex_groups.remove(g)
    log("decimated", n, "->", tri_count(obj))


def tri_count(obj):
    me = obj.data
    n = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", n)
    return int((n - 2).sum())


def shade_smooth(obj):
    me = obj.data
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    me.update()


def face_centers(obj):
    me = obj.data
    a = np.empty(len(me.polygons) * 3, np.float64)
    me.polygons.foreach_get("center", a)
    return a.reshape(-1, 3)


def face_normals(obj):
    me = obj.data
    a = np.empty(len(me.polygons) * 3, np.float64)
    me.polygons.foreach_get("normal", a)
    return a.reshape(-1, 3)


def displace(obj, fn):
    """fn(co Nx3, normals Nx3) -> offset along normal (N,)"""
    co = get_verts(obj)
    nr = get_normals(obj)
    off = fn(co, nr)
    set_verts(obj, co + nr * off[:, None])


def body_from_field(name, field, target_tris, displace_fn=None, smooth_iter=2, pre_smooth=1, importance_fn=None,
                    importance_factor=0.3):
    t0 = time.time()
    verts, faces = field.mesh_data()
    log("marching cubes", len(verts), "verts", len(faces), "faces", "%.1fs" % (time.time() - t0))
    obj = mesh_from_arrays(name, verts, faces)
    fix_normals(obj)
    keep_largest_island(obj)
    if pre_smooth:
        laplacian_smooth(obj, iterations=pre_smooth, factor=0.5)
    if displace_fn is not None:
        displace(obj, displace_fn)
    if smooth_iter:
        laplacian_smooth(obj, iterations=smooth_iter, factor=0.4)
    imp = importance_fn(get_verts(obj)) if importance_fn is not None else None
    decimate_to(obj, target_tris, imp, importance_factor)
    fix_normals(obj)
    shade_smooth(obj)
    log("body", name, tri_count(obj), "tris  %.1fs" % (time.time() - t0))
    return obj


# --------------------------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------------------------
CATALOG = {
    # name: (texture set, base colour, roughness, extra)
    "MNF_FurRotten": ("fur_rotten", (0.105, 0.085, 0.065), 0.92, {}),
    "MNF_SkinDecayed": ("skin_decayed", (0.15, 0.135, 0.112), 0.5, {"var": 0.5}),
    "MNF_FurRabbit": ("fur_rabbit", (0.17, 0.12, 0.08), 0.9, {"var": 0.35}),
    "MNF_FurRabbitMangy": ("fur_rabbit_mangy", (0.14, 0.11, 0.075), 0.9, {"var": 0.5}),
    "MNF_FurBoar": ("fur_boar", (0.075, 0.062, 0.052), 0.88, {}),
    "MNF_FurDark": ("fur_dark", (0.075, 0.07, 0.065), 0.9, {}),
    "MNF_MineralCrust": ("mineral_crust", (0.2, 0.185, 0.16), 0.85, {"var": 0.55}),
    "MNF_MournerSkin": ("mourner_skin", (0.19, 0.165, 0.14), 0.55, {"var": 0.35}),
    "MNF_Teeth": (None, (0.48, 0.40, 0.24), 0.38, {}),
    "MNF_Gums": (None, (0.19, 0.05, 0.05), 0.3, {}),
    "MNF_Nails": (None, (0.28, 0.25, 0.19), 0.45, {}),
    "MNF_Flesh": (None, (0.42, 0.09, 0.09), 0.25, {}),
    "MNF_EyeWet": (None, (0.008, 0.008, 0.008), 0.04, {"spec": 1.0}),
    "MNF_EyeClouded": (None, (0.55, 0.60, 0.64), 0.25, {}),
    "MNF_EyeGlint": (None, (0.85, 0.9, 0.75), 0.2, {"emit": ((0.85, 0.95, 0.75), 3.0)}),
    "MNF_MournerGlow": (None, (0.5, 0.6, 0.15), 0.4, {"emit": ((0.72, 0.86, 0.28), 2.0)}),
    "MNF_Glass": (None, (0.6, 0.62, 0.55), 0.15, {"glass": True}),
    "MNF_MetalRusted": ("metal_rusted", (0.28, 0.14, 0.07), 0.8, {"metal": 0.4, "var": 0.5}),
    "MNF_BulbWarm": (None, (1.0, 0.75, 0.4), 0.3, {"emit": ((1.0, 0.7, 0.35), 8.0)}),
    "MNF_Rope": ("rope", (0.3, 0.25, 0.17), 0.9, {}),
    "MNF_Rubber": ("rubber", (0.04, 0.04, 0.04), 0.7, {}),
}


def get_material(name):
    if name not in CATALOG:
        raise ValueError("material not in catalog: " + name)
    m = bpy.data.materials.get(name)
    if m:
        return m
    texset, col, rough, extra = CATALOG[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = rough
    tex_path = os.path.join(TEX_DIR, texset + "_A.png") if texset else None
    if tex_path and os.path.exists(tex_path):
        img = bpy.data.images.load(tex_path, check_existing=True)
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = img
        nt.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        # procedural mottling
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 9.0
        nz.inputs["Detail"].default_value = 6.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        cr = nt.nodes.new("ShaderNodeValToRGB")
        var = extra.get("var", 0.3)
        c0 = [c * (1 - var) for c in col] + [1]
        c1 = [min(1, c * (1 + var * 0.7)) for c in col] + [1]
        cr.color_ramp.elements[0].color = c0
        cr.color_ramp.elements[1].color = c1
        cr.color_ramp.elements[0].position = 0.3
        cr.color_ramp.elements[1].position = 0.7
        nt.links.new(nz.outputs["Fac"], cr.inputs["Fac"])
        nt.links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
    if "metal" in extra:
        bsdf.inputs["Metallic"].default_value = extra["metal"]
    if "emit" in extra:
        ec, es = extra["emit"]
        bsdf.inputs["Emission Color"].default_value = list(ec) + [1]
        bsdf.inputs["Emission Strength"].default_value = es
    if extra.get("glass"):
        bsdf.inputs["Transmission Weight"].default_value = 0.85
        bsdf.inputs["Base Color"].default_value = list(col) + [1]
    if "spec" in extra:
        bsdf.inputs["Specular IOR Level"].default_value = extra["spec"]
    m.diffuse_color = list(col) + [1]
    return m


def set_materials(obj, names):
    obj.data.materials.clear()
    for n in names:
        obj.data.materials.append(get_material(n))


def assign_body_materials(obj, field, mat_names, rules=(), default=None):
    """Face material = material of nearest tagged union primitive (by signed distance), then the
    optional rules(fn(centers, normals, mats(list of str), owners(list of prim)) -> mats) apply."""
    C = face_centers(obj)
    N = face_normals(obj)
    prims = [p for p in field.prims if p.mat is not None]
    D = np.stack([p.dist_pts(C) for p in prims], axis=1)
    idx = D.argmin(axis=1)
    mats = np.array([prims[i].mat for i in idx], dtype=object)
    owners = [prims[i] for i in idx]
    # faces lining a subtraction (mouth interior etc.)
    for s in field.subs:
        if s.mat is None:
            continue
        ds = s.dist_pts(C)
        mats[ds < field.voxel * 1.2] = s.mat
    for r in rules:
        mats = r(C, N, mats, owners)
    set_materials(obj, mat_names)
    lut = {n: i for i, n in enumerate(mat_names)}
    mi = np.array([lut.get(m, lut.get(default, 0)) for m in mats], np.int32)
    obj.data.polygons.foreach_set("material_index", mi)
    obj.data.update()


# --------------------------------------------------------------------------------------------
# Detail parts (explicit geometry with explicit weights)
# --------------------------------------------------------------------------------------------
class Parts:
    """Accumulates small rigid detail meshes. Each vertex gets either explicit weights
    {bone: w} or an anchor point whose nearest-skin-vertex weights are copied at join time."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.fmat = []
        self.vweights = []   # dict or None
        self.vanchor = []    # Vector or None

    def _add(self, verts, faces, mat, bone=None, anchor=None, weights=None):
        base = len(self.verts)
        for i, v in enumerate(verts):
            self.verts.append(Vector(v))
            if weights is not None:
                w = weights[i] if isinstance(weights, list) else weights
                self.vweights.append(w)
                self.vanchor.append(None)
            elif bone is not None:
                self.vweights.append({bone: 1.0})
                self.vanchor.append(None)
            else:
                self.vweights.append(None)
                self.vanchor.append(Vector(anchor) if anchor is not None else Vector(v))
        for f in faces:
            self.faces.append([base + i for i in f])
            self.fmat.append(mat)
        return base

    @staticmethod
    def _frame(d):
        d = Vector(d).normalized()
        up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        x = d.cross(up).normalized()
        y = d.cross(x).normalized()
        return x, y, d

    def cone(self, base, tip, radius, mat, segs=5, bone=None, anchor=None, weights=None, flat=1.0, twist=0.0):
        base, tip = Vector(base), Vector(tip)
        x, y, d = self._frame(tip - base)
        vs = []
        for i in range(segs):
            a = 2 * math.pi * i / segs + twist
            vs.append(base + x * math.cos(a) * radius + y * math.sin(a) * radius * flat)
        vs.append(tip)
        vs.append(base - d * radius * 0.3)
        fs = []
        for i in range(segs):
            j = (i + 1) % segs
            fs.append([i, j, segs])
            fs.append([j, i, segs + 1])
        return self._add(vs, fs, mat, bone, anchor if anchor is not None else base, weights)

    def tube(self, pts, radii, mat, segs=5, bone=None, anchor=None, weights=None, cap=True, flat=1.0):
        pts = [Vector(p) for p in pts]
        if not isinstance(radii, (list, tuple)):
            radii = [radii] * len(pts)
        vs = []
        n = len(pts)
        ws = []
        for k, p in enumerate(pts):
            d = (pts[min(k + 1, n - 1)] - pts[max(k - 1, 0)])
            x, y, d = self._frame(d)
            for i in range(segs):
                a = 2 * math.pi * i / segs
                vs.append(p + x * math.cos(a) * radii[k] + y * math.sin(a) * radii[k] * flat)
                if isinstance(weights, list):
                    ws.append(weights[k])
        fs = []
        for k in range(n - 1):
            for i in range(segs):
                j = (i + 1) % segs
                a, b, c, e = k * segs + i, k * segs + j, (k + 1) * segs + j, (k + 1) * segs + i
                fs.append([a, b, c])
                fs.append([a, c, e])
        if cap:
            vs.append(pts[0])
            vs.append(pts[-1])
            if isinstance(weights, list):
                ws.append(weights[0])
                ws.append(weights[-1])
            c0, c1 = len(vs) - 2, len(vs) - 1
            for i in range(segs):
                j = (i + 1) % segs
                fs.append([j, i, c0])
                fs.append([(n - 1) * segs + i, (n - 1) * segs + j, c1])
        return self._add(vs, fs, mat, bone, anchor if anchor is not None else pts[0],
                         ws if isinstance(weights, list) else weights)

    def ellipsoid(self, c, r, mat, rot=(0, 0, 0), segs=10, rings=6, bone=None, anchor=None, weights=None,
                  jitter=0.0, seed=0, noise=None):
        c = Vector(c)
        r = Vector(r) if hasattr(r, "__len__") else Vector((r, r, r))
        R = Euler([math.radians(a) for a in rot], 'XYZ').to_matrix()
        rng = np.random.RandomState(seed)
        vs = [c + R @ Vector((0, 0, -r.z))]
        for j in range(1, rings):
            th = math.pi * j / rings
            for i in range(segs):
                ph = 2 * math.pi * i / segs
                p = Vector((math.sin(th) * math.cos(ph) * r.x, math.sin(th) * math.sin(ph) * r.y, -math.cos(th) * r.z))
                if jitter:
                    p = p * (1 + rng.uniform(-jitter, jitter))
                vs.append(c + R @ p)
        vs.append(c + R @ Vector((0, 0, r.z)))
        fs = []
        for i in range(segs):
            fs.append([0, 1 + (i + 1) % segs, 1 + i])
        for j in range(rings - 2):
            for i in range(segs):
                a = 1 + j * segs + i
                b = 1 + j * segs + (i + 1) % segs
                c2 = 1 + (j + 1) * segs + (i + 1) % segs
                d = 1 + (j + 1) * segs + i
                fs.append([a, b, c2])
                fs.append([a, c2, d])
        top = len(vs) - 1
        for i in range(segs):
            a = 1 + (rings - 2) * segs + i
            b = 1 + (rings - 2) * segs + (i + 1) % segs
            fs.append([a, b, top])
        return self._add(vs, fs, mat, bone, anchor if anchor is not None else c, weights)

    def rock(self, c, r, mat, seed, rot=(0, 0, 0), bone=None, anchor=None, weights=None, detail=1):
        """Faceted irregular stone (icosphere with jitter)."""
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=detail, radius=1.0)
        rng = np.random.RandomState(seed)
        r = Vector(r) if hasattr(r, "__len__") else Vector((r, r, r))
        R = Euler([math.radians(a) for a in rot], 'XYZ').to_matrix()
        vs = []
        for v in bm.verts:
            p = v.co * (1 + rng.uniform(-0.25, 0.2))
            p = Vector((p.x * r.x, p.y * r.y, p.z * r.z))
            # flatten facets a bit
            vs.append(Vector(c) + R @ p)
        fs = [[v.index for v in f.verts] for f in bm.faces]
        bm.free()
        return self._add(vs, fs, mat, bone, anchor if anchor is not None else c, weights)

    def box(self, c, size, mat, rot=(0, 0, 0), bone=None, anchor=None, weights=None):
        c = Vector(c)
        R = Euler([math.radians(a) for a in rot], 'XYZ').to_matrix()
        sx, sy, sz = [s * 0.5 for s in size]
        vs = [c + R @ Vector((x * sx, y * sy, z * sz)) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        fs = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
        return self._add(vs, fs, mat, bone, anchor if anchor is not None else c, weights)

    def build(self, name, mat_names):
        if not self.verts:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in self.verts], [], self.faces)
        me.update(calc_edges=True)
        obj = bpy.data.objects.new(name, me)
        link(obj)
        set_materials(obj, mat_names)
        lut = {n: i for i, n in enumerate(mat_names)}
        obj.data.polygons.foreach_set("material_index", np.array([lut[m] for m in self.fmat], np.int32))
        fix_normals(obj)
        shade_smooth(obj)
        return obj


# --------------------------------------------------------------------------------------------
# UVs
# --------------------------------------------------------------------------------------------
def uv_unwrap(obj, repeat_m=0.5):
    activate(obj)
    me = obj.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    # texel density: 1 texture repeat per repeat_m metres
    uv = np.empty(len(me.loops) * 2, np.float64)
    me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    area3 = 0.0
    areauv = 0.0
    co = get_verts(obj)
    for p in me.polygons:
        li = list(p.loop_indices)
        vi = list(p.vertices)
        for k in range(1, len(li) - 1):
            a, b, c = co[vi[0]], co[vi[k]], co[vi[k + 1]]
            area3 += 0.5 * np.linalg.norm(np.cross(b - a, c - a))
            ua, ub, uc = uv[li[0]], uv[li[k]], uv[li[k + 1]]
            areauv += 0.5 * abs((ub[0] - ua[0]) * (uc[1] - ua[1]) - (ub[1] - ua[1]) * (uc[0] - ua[0]))
    if areauv > 0:
        s = math.sqrt((area3 / (repeat_m ** 2)) / areauv)
        uv *= s
        me.uv_layers["UVMap"].data.foreach_set("uv", uv.ravel())
    me.uv_layers.active = me.uv_layers["UVMap"]


# --------------------------------------------------------------------------------------------
# Armature
# --------------------------------------------------------------------------------------------
class BoneDef:
    def __init__(self, name, head, tail, parent=None, deform=True, connect=False):
        self.name, self.head, self.tail = name, Vector(head), Vector(tail)
        self.parent, self.deform, self.connect = parent, deform, connect


def mirror_bones(defs):
    out = []
    for b in defs:
        out.append(b)
        if b.name.endswith(".L"):
            out.append(BoneDef(mirror_name(b.name), Vector((-b.head.x, b.head.y, b.head.z)),
                               Vector((-b.tail.x, b.tail.y, b.tail.z)),
                               mirror_name(b.parent) if b.parent else None, b.deform, b.connect))
    return out


def build_armature(name, defs):
    arm = bpy.data.armatures.new(name + "_Armature")
    arm.display_type = 'STICK'
    obj = bpy.data.objects.new(name, arm)
    link(obj)
    obj.show_in_front = True
    activate(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    ebs = {}
    for d in defs:
        eb = arm.edit_bones.new(d.name)
        eb.head = d.head
        eb.tail = d.tail
        eb.use_deform = d.deform
        ebs[d.name] = eb
    for d in defs:
        eb = ebs[d.name]
        if d.parent:
            eb.parent = ebs[d.parent]
            eb.use_connect = d.connect and (ebs[d.parent].tail - eb.head).length < 1e-4
        # sane, consistent roll: local Z toward forward (-Y) for vertical bones, else toward up (+Z)
        v = (eb.tail - eb.head).normalized()
        ref = Vector((0, -1, 0)) if abs(v.z) > 0.7 else Vector((0, 0, 1))
        if abs(v.dot(ref)) > 0.98:
            ref = Vector((1, 0, 0))
        eb.align_roll(ref)
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return obj


def skin_body(body, arm):
    """Bone-heat automatic weights for the skin mesh."""
    activate(arm, others=[body])
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    # check
    deform = [b.name for b in arm.data.bones if b.use_deform]
    empty = []
    for bn in deform:
        vg = body.vertex_groups.get(bn)
        if vg is None:
            empty.append(bn)
    W = weight_matrix(body, deform)
    unweighted = int((W.sum(axis=1) < 1e-4).sum())
    log("auto weights: bones without group:", empty, "unweighted verts:", unweighted)
    return W


def weight_matrix(obj, bones):
    idx = {}
    for b in bones:
        vg = obj.vertex_groups.get(b)
        if vg:
            idx[vg.index] = bones.index(b)
    W = np.zeros((len(obj.data.vertices), len(bones)))
    for v in obj.data.vertices:
        for g in v.groups:
            j = idx.get(g.group)
            if j is not None:
                W[v.index, j] = g.weight
    return W


def write_weights(obj, bones, W, limit=4):
    for b in bones:
        if obj.vertex_groups.get(b) is None:
            obj.vertex_groups.new(name=b)
    # limit + normalise
    W = W.copy()
    if limit and W.shape[1] > limit:
        idx = np.argsort(-W, axis=1)[:, limit:]
        np.put_along_axis(W, idx, 0.0, axis=1)
    s = W.sum(axis=1)
    zero = np.nonzero(s < 1e-6)[0]
    if len(zero):
        co = get_verts(obj)
        good = np.nonzero(s >= 1e-6)[0]
        kd = KDTree(len(good))
        for k, i in enumerate(good):
            kd.insert(co[i], k)
        kd.balance()
        for i in zero:
            _, k, _ = kd.find(co[i])
            W[i] = W[good[k]]
        log("write_weights: filled %d zero-weight verts from neighbours" % len(zero))
    s = W.sum(axis=1, keepdims=True)
    s[s < 1e-9] = 1
    W = W / s
    for j, b in enumerate(bones):
        vg = obj.vertex_groups[b]
        vg.remove(list(range(len(obj.data.vertices))))
        nz = np.nonzero(W[:, j] > 1e-4)[0]
        for i in nz:
            vg.add([int(i)], float(W[i, j]), 'REPLACE')
    return W


def prim_ownership_weight(co, field, bone_tags, others_k=0.015):
    """Soft region weight in [0,1]: how much the point belongs to primitives with tag in bone_tags
    (compared against all other union prims)."""
    A = [p for p in field.prims if p.tag in bone_tags]
    B = [p for p in field.prims if p.tag not in bone_tags]
    da = np.min(np.stack([p.dist_pts(co) for p in A], 1), 1)
    db = np.min(np.stack([p.dist_pts(co) for p in B], 1), 1)
    x = (db - da) / others_k
    return np.clip(0.5 + 0.5 * x, 0, 1)


def prim_center(p):
    if isinstance(p, Ellipsoid):
        return p.c
    return (p.a + p.b) / 2


def seg_dist(P, a, b):
    ba = b - a
    h = np.clip(((P - a) @ ba) / (ba @ ba + 1e-12), 0, 1)
    return np.linalg.norm(P - (a + h[:, None] * ba), axis=1)


def auto_assign_prim_bones(field, arm):
    """Primitives without an explicit bone get the deform bone whose segment is closest to the
    primitive (sampled along capsules)."""
    bones = [b for b in arm.data.bones if b.use_deform]
    segs = [(b.name, np.array(b.head_local), np.array(b.tail_local)) for b in bones]
    for p in field.prims:
        if p.bone:
            continue
        if isinstance(p, Ellipsoid):
            pts = np.array([p.c])
        else:
            pts = np.array([p.a + (p.b - p.a) * t for t in (0.25, 0.5, 0.75)])
        best = None
        for n, a, b in segs:
            d = seg_dist(pts, a, b).mean()
            if best is None or d < best[0]:
                best = (d, n)
        p.bone = best[1]


def ownership_weights(co, field, bones, sigma):
    prims = [p for p in field.prims if p.bone in bones]
    D = np.stack([p.dist_pts(co) for p in prims], 1)
    dmin = D.min(1, keepdims=True)
    S = np.exp(-np.maximum(D - dmin, 0) / sigma)
    W = np.zeros((len(co), len(bones)))
    for i, p in enumerate(prims):
        W[:, bones.index(p.bone)] += S[:, i]
    W /= W.sum(1, keepdims=True)
    return W, D, prims


def refine_weights(arm, co, field, W_heat, bones, sigma=0.015, margin=None, own_mix=0.0):
    """Mask bone-heat weights with primitive ownership (a vertex may only be influenced by bones
    whose primitives are near it, plus their parents/children) and fall back to ownership weights
    where heat gave nothing usable."""
    margin = margin if margin is not None else 2.5 * sigma
    W_own, D, prims = ownership_weights(co, field, bones, sigma)
    dmin = D.min(1, keepdims=True)
    near = D < dmin + margin
    allowed = np.zeros_like(W_heat, dtype=bool)
    rel = {}
    for b in arm.data.bones:
        if b.name not in bones:
            continue
        s = {b.name}
        if b.parent and b.parent.name in bones:
            s.add(b.parent.name)
        for c in b.children:
            if c.name in bones:
                s.add(c.name)
        rel[b.name] = [bones.index(x) for x in s]
    for i, p in enumerate(prims):
        rows = np.nonzero(near[:, i])[0]
        for j in rel[p.bone]:
            allowed[rows, j] = True
    W = W_heat * allowed
    s = W.sum(1)
    need = np.clip((0.7 - s) / 0.7, 0, 1)
    W = W + W_own * need[:, None]
    if own_mix:
        W = W * (1 - own_mix) + W_own * own_mix
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    nfix = int((need > 0.01).sum())
    log("refine_weights: %d verts used ownership fallback" % nfix)
    return W


def override_weights(W, bones, bone, w):
    """Blend each vertex toward 100% `bone` by factor w (N,)."""
    j = bones.index(bone)
    W = W * (1 - w[:, None])
    W[:, j] += w
    return W


def side_cleanup(W, bones, co, eps=0.02):
    """Remove .L influence from verts at x < -eps and .R from x > eps (prevents cross-body bleed)."""
    for j, b in enumerate(bones):
        if b.endswith(".L"):
            W[co[:, 0] < -eps, j] = 0
        elif b.endswith(".R"):
            W[co[:, 0] > eps, j] = 0
    return W


def smooth_weights(obj, W, iterations=2, factor=0.5, mask=None):
    me = obj.data
    ev = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    n = len(me.vertices)
    for _ in range(iterations):
        acc = np.zeros_like(W)
        cnt = np.zeros(n)
        np.add.at(acc, ev[:, 0], W[ev[:, 1]])
        np.add.at(acc, ev[:, 1], W[ev[:, 0]])
        np.add.at(cnt, ev[:, 0], 1)
        np.add.at(cnt, ev[:, 1], 1)
        avg = acc / np.maximum(cnt, 1)[:, None]
        f = factor if mask is None else factor * mask[:, None]
        W = W * (1 - f) + avg * f
    return W


def join_parts(body, parts_obj, arm):
    """Copy anchor weights for parts, then join into the body (single skinned mesh)."""
    if parts_obj is None:
        return body
    deform = [b.name for b in arm.data.bones if b.use_deform]
    Wb = weight_matrix(body, deform)
    co = get_verts(body)
    kd = KDTree(len(co))
    for i, c in enumerate(co):
        kd.insert(c, i)
    kd.balance()
    for b in deform:
        if parts_obj.vertex_groups.get(b) is None:
            parts_obj.vertex_groups.new(name=b)
    return Wb, kd, deform


def finalize_join(body, parts_obj, parts, arm):
    deform = [b.name for b in arm.data.bones if b.use_deform]
    Wb = weight_matrix(body, deform)
    co = get_verts(body)
    kd = KDTree(len(co))
    for i, c in enumerate(co):
        kd.insert(c, i)
    kd.balance()
    for b in deform:
        if parts_obj.vertex_groups.get(b) is None:
            parts_obj.vertex_groups.new(name=b)
    for vi, (w, anc) in enumerate(zip(parts.vweights, parts.vanchor)):
        if w is None:
            # average of 3 nearest skin verts
            res = kd.find_n(anc, 3)
            acc = np.zeros(len(deform))
            tot = 0
            for (_, idx, dist) in res:
                ww = 1.0 / (dist + 1e-3)
                acc += Wb[idx] * ww
                tot += ww
            acc /= tot
            w = {deform[j]: acc[j] for j in range(len(deform)) if acc[j] > 1e-3}
        s = sum(w.values())
        for b, x in w.items():
            parts_obj.vertex_groups[b].add([vi], float(x / s), 'REPLACE')
    # join
    activate(body, others=[parts_obj])
    bpy.ops.object.join()
    return body


def add_armature_modifier(obj, arm):
    for m in obj.modifiers:
        if m.type == 'ARMATURE':
            m.object = arm
            return m
    m = obj.modifiers.new("Armature", 'ARMATURE')
    m.object = arm
    obj.parent = arm
    return m


# --------------------------------------------------------------------------------------------
# Pose solving (FK + analytic two-bone IK)
# --------------------------------------------------------------------------------------------
def deg(v):
    return [math.radians(x) for x in v]


class Pose(dict):
    """Keys: ('r', bone) -> world-axis euler degrees (parent relative), ('w', bone) -> absolute
    world-axis rotation relative to the rest orientation, ('l', bone) -> world-axis translation,
    ('s', bone) -> uniform scale factor (as 3-vector; only x used), ('ik', upper) -> [tx,ty,tz, px,py,pz, weight]"""

    def r(self, bone, x=0, y=0, z=0):
        k = ('r', bone)
        self[k] = self.get(k, np.zeros(3)) + np.array([x, y, z], float)
        return self

    def l(self, bone, x=0, y=0, z=0):
        k = ('l', bone)
        self[k] = self.get(k, np.zeros(3)) + np.array([x, y, z], float)
        return self

    def w(self, bone, x=0, y=0, z=0):
        k = ('w', bone)
        self[k] = self.get(k, np.zeros(3)) + np.array([x, y, z], float)
        return self

    def s(self, bone, f):
        self[('s', bone)] = np.array([f, f, f], float)
        return self

    def a(self, bone, x, y, z, weight=1.0):
        """Aim: the bone points along world direction (x, y, z) (minimal twist)."""
        d = np.array([x, y, z], float)
        d /= np.linalg.norm(d)
        self[('a', bone)] = np.array(list(d) + [weight], float)
        return self

    def ik(self, upper, target, pole, weight=1.0):
        self[('ik', upper)] = np.array(list(target) + list(pole) + [weight], float)
        return self

    def copy(self):
        p = Pose()
        for k, v in self.items():
            p[k] = np.array(v, float)
        return p

    def add(self, other, f=1.0):
        out = self.copy()
        for k, v in other.items():
            if k[0] in ('ik', 's', 'a'):
                out[k] = np.array(v, float)
            else:
                out[k] = out.get(k, np.zeros(3)) + np.asarray(v) * f
        return out

    def mirrored(self):
        """Mirror L<->R (x flip): rotations about Y and Z flip sign, X stays."""
        out = Pose()
        for (kind, b), v in self.items():
            nb = mirror_name(b)
            v = np.array(v, float)
            if kind in ('r', 'w'):
                v = v * np.array([1, -1, -1])
            elif kind == 'l':
                v = v * np.array([-1, 1, 1])
            elif kind == 'ik':
                v = v * np.array([-1, 1, 1, -1, 1, 1, 1])
            elif kind == 'a':
                v = v * np.array([-1, 1, 1, 1])
            out[(kind, nb)] = v
        return out


def combo(poses, weights):
    out = Pose()
    keys = set()
    for p in poses:
        keys |= set(p.keys())
    for k in keys:
        if k[0] == 's':
            acc = np.zeros(3)
            for p, w in zip(poses, weights):
                acc = acc + (p[k] if k in p else np.ones(3)) * w
            out[k] = acc
            continue
        if k[0] in ('ik', 'a'):
            # pick weighted for those present (renormalise)
            acc = None
            tw = 0
            for p, w in zip(poses, weights):
                if k in p:
                    acc = (p[k] * w) if acc is None else acc + p[k] * w
                    tw += w
            if acc is not None and abs(tw) > 1e-9:
                out[k] = acc / tw
                if k[0] in ('ik', 'a'):
                    # IK / aim weight blends toward 0 where a pose has no entry for this bone
                    wi = 6 if k[0] == 'ik' else 3
                    out[k][wi] = sum(w * p[k][wi] for p, w in zip(poses, weights) if k in p)
            continue
        acc = np.zeros(3)
        for p, w in zip(poses, weights):
            if k in p:
                acc = acc + p[k] * w
        out[k] = acc
    return out


def keyed(t, keys, loop_len=None, mode='smooth'):
    """keys: list of (time, Pose). Interpolates with Catmull-Rom ('cr') or eased ('smooth') blend.
    If loop_len is given, the key list is treated cyclically (first key should be at 0 and the
    pose at loop_len equals keys[0])."""
    ts = [k[0] for k in keys]
    ps = [k[1] for k in keys]
    n = len(keys)
    if loop_len is not None:
        t = t % loop_len
        ts2 = ts + [loop_len]
        ps2 = ps + [ps[0]]
    else:
        if t <= ts[0]:
            return ps[0].copy()
        if t >= ts[-1]:
            return ps[-1].copy()
        ts2, ps2 = ts, ps
    i = 0
    while i < len(ts2) - 2 and t >= ts2[i + 1]:
        i += 1
    t0, t1 = ts2[i], ts2[i + 1]
    u = 0 if t1 == t0 else (t - t0) / (t1 - t0)
    if mode == 'smooth':
        u = smoothstep(u)
        return combo([ps2[i], ps2[i + 1]], [1 - u, u])
    if mode == 'linear':
        return combo([ps2[i], ps2[i + 1]], [1 - u, u])
    # Catmull-Rom
    m = len(ps2)
    if loop_len is not None:
        P0 = ps2[(i - 1) % (m - 1)]
        P3 = ps2[(i + 2) % (m - 1)] if i + 2 < m else ps2[(i + 2) % (m - 1)]
    else:
        P0 = ps2[max(i - 1, 0)]
        P3 = ps2[min(i + 2, m - 1)]
    P1, P2 = ps2[i], ps2[i + 1]
    u2, u3 = u * u, u * u * u
    w0 = 0.5 * (-u3 + 2 * u2 - u)
    w1 = 0.5 * (3 * u3 - 5 * u2 + 2)
    w2 = 0.5 * (-3 * u3 + 4 * u2 + u)
    w3 = 0.5 * (u3 - u2)
    return combo([P0, P1, P2, P3], [w0, w1, w2, w3])


class Rig:
    def __init__(self, arm):
        self.arm = arm
        self.bones = {b.name: b for b in arm.data.bones}
        self.rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
        self.rest_rot = {n: m.to_3x3() for n, m in self.rest.items()}
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
        self.children = {}
        for n, p in self.parent.items():
            self.children.setdefault(p, []).append(n)
        self.order = []

        def walk(n):
            self.order.append(n)
            for c in self.children.get(n, []):
                walk(c)
        for r in self.children[None]:
            walk(r)
        self.local = {}
        for n in self.order:
            p = self.parent[n]
            self.local[n] = (self.rest[p].inverted() @ self.rest[n]) if p else self.rest[n].copy()
        self.length = {n: b.length for n, b in self.bones.items()}
        self.lower_of = {}
        for n in self.order:
            p = self.parent[n]
            if p and n not in self.lower_of.values():
                pass
        self.max_ik_err = 0.0

    def head(self, n):
        return self.rest[n].translation.copy()

    def tail(self, n):
        return (self.rest[n] @ Vector((0, self.length[n], 0, 1))).to_3d() if False else \
            self.rest[n].translation + self.rest_rot[n] @ Vector((0, self.length[n], 0))

    def basis_from_world_rot(self, n, euler_deg):
        R = self.rest_rot[n]
        Rw = Euler(deg(euler_deg), 'XYZ').to_matrix()
        return R.transposed() @ Rw @ R

    def solve(self, pose, ik_chains):
        """Returns {bone: basis Matrix(4x4)} and pose-space matrices."""
        basis = {}
        M = {}
        ikmap = {}
        for upper, lower in ik_chains:
            ikmap[upper] = lower
        lower_targets = {}
        for n in self.order:
            p = self.parent[n]
            B = Matrix.Identity(3)
            k = ('r', n)
            if k in pose:
                B = self.basis_from_world_rot(n, pose[k])
            Lm = self.local[n]
            Mp = M[p] if p else Matrix.Identity(4)
            M0 = Mp @ Lm
            rot0 = M0.to_3x3().normalized()
            if ('w', n) in pose:
                desired = Euler(deg(pose[('w', n)]), 'XYZ').to_matrix() @ self.rest_rot[n]
                B = rot0.inverted() @ desired
            if ('a', n) in pose:
                av = pose[('a', n)]
                if av[3] > 1e-4:
                    B = self._blend(B, self._aim(rot0, Vector(av[0:3])), float(min(av[3], 1.0)))
            if n in lower_targets:
                tdir, w = lower_targets[n]
                Bik = self._aim(rot0, tdir)
                B = self._blend(B, Bik, w)
            tr = Vector((0, 0, 0))
            if ('l', n) in pose:
                tr = rot0.inverted() @ Vector(pose[('l', n)])
            sc = 1.0
            if ('s', n) in pose:
                sc = float(pose[('s', n)][0])
            if ('ik', n) in pose and n in ikmap:
                ikv = pose[('ik', n)]
                T = Vector(ikv[0:3])
                pole = Vector(ikv[3:6])
                w = float(ikv[6])
                if w > 1e-4:
                    H = M0.translation
                    lower = ikmap[n]
                    L1 = self.length[n] * self._scale_of(M0)
                    L2 = self.length[lower] * self._scale_of(M0)
                    K, err = two_bone(H, T, L1, L2, pole)
                    self.max_ik_err = max(self.max_ik_err, err * w)
                    Bik = self._aim(rot0, K - H)
                    B = self._blend(B, Bik, w)
                    lower_targets[lower] = (T - K, w)
            Bm = B.to_4x4()
            if sc != 1.0:
                Bm = Bm @ Matrix.Diagonal((sc, sc, sc, 1.0))
            Bm.translation = tr
            basis[n] = Bm
            M[n] = M0 @ Bm
        return basis, M

    @staticmethod
    def _scale_of(M):
        return M.to_3x3().col[1].length

    @staticmethod
    def _aim(rot0, direction):
        y0 = rot0 @ Vector((0, 1, 0))
        q = y0.rotation_difference(direction.normalized()).to_matrix()
        return rot0.inverted() @ q @ rot0

    @staticmethod
    def _blend(A, B, w):
        if w >= 0.9999:
            return B
        if w <= 1e-4:
            return A
        qa = A.to_quaternion()
        qb = B.to_quaternion()
        return qa.slerp(qb, w).to_matrix()


def two_bone(H, T, L1, L2, pole):
    d_vec = T - H
    d = d_vec.length
    err = 0.0
    dmax = (L1 + L2) * 0.9995
    dmin = abs(L1 - L2) * 1.001 + 1e-5
    if d > dmax:
        err = d - dmax
        d = dmax
    if d < dmin:
        d = dmin
    u = d_vec.normalized()
    pole = Vector(pole)
    n = pole - u * pole.dot(u)
    if n.length < 1e-6:
        n = Vector((0, -1, 0)) - u * (-u.y)
    n.normalize()
    ca = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
    ca = max(-1.0, min(1.0, ca))
    sa = math.sqrt(1 - ca * ca)
    K = H + (u * ca + n * sa) * L1
    return K, err


# --------------------------------------------------------------------------------------------
# Clip baking
# --------------------------------------------------------------------------------------------
class Clip:
    def __init__(self, name, frames, fn, loop=True, speed=0.0, events=None, bones=None, notes=""):
        self.name, self.frames, self.fn = name, int(frames), fn
        self.loop, self.speed = loop, speed
        self.events = events or {}
        self.bones = bones  # restrict keyed bones (e.g. blink)
        self.notes = notes

    @property
    def length(self):
        return self.frames / FPS


def bake_clips(arm, clips, ik_chains, loc_bones=("hips",), scale_bones=()):
    rig = Rig(arm)
    arm.animation_data_create()
    results = {}
    for clip in clips:
        act = bpy.data.actions.new(clip.name)
        act.use_fake_user = True
        arm.animation_data.action = act
        prevq = {}
        rig.max_ik_err = 0.0
        for f in range(clip.frames + 1):
            u = f / clip.frames
            t = f / FPS
            pose = clip.fn(u, t)
            basis, _ = rig.solve(pose, ik_chains)
            for n in rig.order:
                if clip.bones is not None and n not in clip.bones:
                    continue
                if n == 'root':
                    continue
                pb = arm.pose.bones[n]
                q = basis[n].to_quaternion()
                if n in prevq and q.dot(prevq[n]) < 0:
                    q.negate()
                prevq[n] = q
                pb.rotation_quaternion = q
                pb.keyframe_insert("rotation_quaternion", frame=f, group=n)
                if n in loc_bones:
                    pb.location = basis[n].translation
                    pb.keyframe_insert("location", frame=f, group=n)
                if n in scale_bones:
                    pb.scale = basis[n].to_scale()
                    pb.keyframe_insert("scale", frame=f, group=n)
        set_linear(act)
        results[clip.name] = act
        log("baked %s %d frames, max IK reach error %.3f m" % (clip.name, clip.frames, rig.max_ik_err))
    reset_pose(arm)
    return results


def action_fcurves(act):
    out = []
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out.extend(cb.fcurves)
    except AttributeError:
        out = list(act.fcurves)
    return out


def set_linear(act):
    for fc in action_fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
        pb.scale = Vector((1, 1, 1))


def set_action(arm, act):
    arm.animation_data.action = act
    try:
        if act and arm.animation_data.action_slot is None and len(act.slots):
            arm.animation_data.action_slot = act.slots[0]
    except AttributeError:
        pass


# --------------------------------------------------------------------------------------------
# Gait helpers
# --------------------------------------------------------------------------------------------
def foot_track(u, offset, duty, travel, lift, rest, lift_pow=1.0, fwd=(0, -1, 0)):
    """Foot target for an in-place cycle. Stance: foot slides backward by `travel` (= speed*duty*T).
    Returns (pos Vector, in_contact bool, s (0..1 within the phase))."""
    p = (u - offset) % 1.0
    rest = Vector(rest)
    fwd = Vector(fwd)
    if p < duty:
        s = p / duty
        along = 0.5 - s
        h = 0.0
        contact = True
    else:
        s = (p - duty) / (1 - duty)
        along = -0.5 + smootherstep(s)
        h = lift * (math.sin(math.pi * s) ** lift_pow)
        contact = False
    return rest + fwd * (along * travel) + Vector((0, 0, h)), contact, s


def contact_frames(frames, offset, duty=None):
    """Frame index where a foot with the given phase offset touches down."""
    f = int(round((offset % 1.0) * frames)) % frames
    return f


# --------------------------------------------------------------------------------------------
# Verification: deformation sanity
# --------------------------------------------------------------------------------------------
def deformation_check(body, arm, actions, step=3):
    me = body.data
    ev = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    rest = get_verts(body)
    L0 = np.linalg.norm(rest[ev[:, 0]] - rest[ev[:, 1]], axis=1) + 1e-9
    report = {}
    worst = (0, None)
    sc = bpy.context.scene
    for name, act in actions.items():
        reset_pose(arm)
        set_action(arm, act)
        f0, f1 = act.frame_range
        mx, mn = 1.0, 1.0
        for f in range(int(f0), int(f1) + 1, step):
            sc.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            ev_obj = body.evaluated_get(dg)
            m2 = ev_obj.to_mesh()
            co = np.empty(len(m2.vertices) * 3)
            m2.vertices.foreach_get("co", co)
            ev_obj.to_mesh_clear()
            co = co.reshape(-1, 3)
            L = np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1)
            r = L / L0
            # ignore microscopic edges
            ok = L0 > 1e-3
            mx = max(mx, float(r[ok].max()))
            mn = min(mn, float(r[ok].min()))
        report[name] = (round(mx, 2), round(mn, 2))
        if mx > worst[0]:
            worst = (mx, name)
    set_action(arm, None)
    reset_pose(arm)
    sc.frame_set(0)
    log("deformation (max stretch, min shrink) per clip:", report)
    return report


# --------------------------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------------------------
def export_fbx(name, arm, meshes, animated=True):
    path = os.path.join(FBX_DIR, name + ".fbx")
    reset_pose(arm)
    if arm.animation_data:
        arm.animation_data.action = None
    bpy.context.scene.frame_set(0)
    activate(arm, others=meshes)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH', 'EMPTY'},
                             apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y',
                             bake_space_transform=False, use_mesh_modifiers=True, mesh_smooth_type='FACE',
                             use_tspace=True, add_leaf_bones=False, primary_bone_axis='Y',
                             secondary_bone_axis='X', armature_nodetype='NULL', bake_anim=animated,
                             bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
                             bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
                             path_mode='STRIP')
    log("exported", path)
    return path


def save_blend(name):
    path = os.path.join(BLEND_DIR, name + ".blend")
    try:
        bpy.context.preferences.filepaths.save_version = 0  # no .blend1 backups
    except Exception:
        pass
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    log("saved", path)
    return path


def check_transforms(objs):
    for o in objs:
        s = o.scale
        assert min(s) > 0, "negative scale on " + o.name
        assert (o.matrix_world.to_3x3() - Matrix.Identity(3)).to_quaternion().angle < 1e-4 or True


def update_manifest(name, entry):
    data = {}
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST) as fh:
                data = json.load(fh)
        except Exception:
            data = {}
    data[name] = entry
    order = ["Hollowback", "Rabbit", "Falsekin", "CeilingClerk", "Borer", "LanternMourner", "Gaunt", "Boar",
             "Gloomrat"]
    out = {k: data[k] for k in order if k in data}
    for k in data:
        if k not in out:
            out[k] = data[k]
    with open(MANIFEST, "w") as fh:
        json.dump(out, fh, indent=1)
    log("manifest updated", name)


def mesh_bounds(objs, arm=None):
    lo = np.array([1e9] * 3)
    hi = np.array([-1e9] * 3)
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        e = o.evaluated_get(dg)
        m = e.to_mesh()
        co = np.empty(len(m.vertices) * 3)
        m.vertices.foreach_get("co", co)
        e.to_mesh_clear()
        co = co.reshape(-1, 3)
        co = co @ np.array(o.matrix_world.to_3x3()).T + np.array(o.matrix_world.translation)
        lo = np.minimum(lo, co.min(0))
        hi = np.maximum(hi, co.max(0))
    return lo, hi


def manifest_entry(name, arm, meshes, clips, eye_height, extra=None):
    lo, hi = mesh_bounds(meshes)
    tris = sum(tri_count(m) for m in meshes)
    mats = []
    for m in meshes:
        for s in m.data.materials:
            if s and s.name not in mats:
                mats.append(s.name)
    head = arm.data.bones.get("head")
    e = {
        "file": name + ".fbx",
        "height": round(float(hi[2]), 3),
        "length": round(float(hi[1] - lo[1]), 3),
        "width": round(float(hi[0] - lo[0]), 3),
        "eye_height": round(float(eye_height), 3),
        "tris": int(tris),
        "materials": mats,
        "bones": [b.name for b in arm.data.bones],
        "head_rest_position": [round(float(x), 4) for x in (arm.matrix_world @ head.head_local)] if head else None,
        "fbx_take_prefix": arm.name + "|",
        "fps": FPS,
        "clips": {},
    }
    for c in clips:
        ce = {"length": round(c.length, 4), "loop": bool(c.loop), "frames": c.frames}
        if c.loop or c.speed:
            ce["speed"] = c.speed
        ce["events"] = c.events
        if c.notes:
            ce["notes"] = c.notes
        e["clips"][c.name] = ce
    if extra:
        e.update(extra)
    return e


# --------------------------------------------------------------------------------------------
# Preview rendering
# --------------------------------------------------------------------------------------------
def setup_render(res=(320, 240), samples=16):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 4
    sc.cycles.volume_bounces = 0
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 4


def _world(color=(0.3, 0.3, 0.3), strength=1.0, fog=None):
    w = bpy.data.worlds.get("PreviewWorld") or bpy.data.worlds.new("PreviewWorld")
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = list(color) + [1]
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    if fog:
        vs = nt.nodes.new("ShaderNodeVolumePrincipled")
        vs.inputs["Density"].default_value = fog[0]
        vs.inputs["Color"].default_value = list(fog[1]) + [1]
        vs.inputs["Anisotropy"].default_value = 0.3
        nt.links.new(vs.outputs["Volume"], out.inputs["Volume"])
    bpy.context.scene.world = w


def _clear_preview_objects():
    for o in list(bpy.data.objects):
        if o.get("mnf_preview"):
            bpy.data.objects.remove(o, do_unlink=True)


def _light(name, kind, loc, energy, size=1.0, color=(1, 1, 1), target=(0, 0, 1)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == 'AREA':
        ld.size = size
    elif kind == 'SPOT':
        ld.spot_size = math.radians(40)
        ld.shadow_soft_size = size
    else:
        ld.shadow_soft_size = size
    o = bpy.data.objects.new(name, ld)
    o["mnf_preview"] = 1
    link(o)
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def _camera(loc, target, lens=50):
    cd = bpy.data.cameras.new("PreviewCam")
    cd.lens = lens
    cd.clip_start = 0.01
    cd.clip_end = 500
    o = bpy.data.objects.new("PreviewCam", cd)
    o["mnf_preview"] = 1
    link(o)
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = o
    return o


def _ground(size, z=0.0, color=(0.22, 0.22, 0.22)):
    me = bpy.data.meshes.new("PreviewGround")
    s = size
    me.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [[0, 1, 2, 3]])
    o = bpy.data.objects.new("PreviewGround", me)
    o["mnf_preview"] = 1
    link(o)
    m = bpy.data.materials.get("PreviewGroundMat") or bpy.data.materials.new("PreviewGroundMat")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = list(color) + [1]
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    me.materials.append(m)
    return o


def _cam_fit(center, size, direction, lens=50, aspect=1.0, margin=1.15):
    """Place camera along direction (from center) so a box of `size` (extent) fits.
    aspect = min(w, h) / max(w, h) of the render (36 mm sensor fits the larger side)."""
    fov = 2 * math.atan(18.0 / lens * aspect)
    radius = 0.5 * float(np.linalg.norm(size)) * margin
    dist = radius / math.tan(fov / 2) * 1.0
    d = Vector(direction).normalized()
    return Vector(center) + d * dist


def render_still(path, res=(320, 240), samples=16):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def preview_setup_studio(center, size, fog=False):
    _clear_preview_objects()
    c = Vector(center)
    R = max(size) * 1.4 + 0.5
    if fog:
        _world((0.035, 0.04, 0.045), 1.0, fog=(0.25 / max(max(size), 0.3), (0.55, 0.58, 0.6)))
        _light("Moon", 'SUN', (0, 10, 10), 0.6, size=0.02, color=(0.7, 0.75, 0.85), target=(0, 0, 0))
        _light("BackFog", 'SPOT', c + Vector((0.3 * R, 2.2 * R, 0.6 * R)), 900 * R * R, size=0.3,
               color=(0.75, 0.8, 0.9), target=c)
    else:
        _world((0.3, 0.3, 0.3), 0.35)
        _light("Key", 'AREA', c + Vector((-1.2 * R, -1.6 * R, 1.4 * R)), 75 * R * R, size=R, target=c)
        _light("Fill", 'AREA', c + Vector((1.6 * R, -1.0 * R, 0.6 * R)), 18 * R * R, size=R, target=c)
        _light("Rim", 'AREA', c + Vector((0.4 * R, 1.8 * R, 1.6 * R)), 90 * R * R, size=R * 0.6, target=c)
    _ground(max(size) * 6 + 2)


def compose_grid(images, cols, out, labels=None, title=None, cell=None, bg=(40, 40, 40)):
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert("RGB") for p in images]
    w, h = ims[0].size if cell is None else cell
    rows = int(math.ceil(len(ims) / cols))
    top = 22 if title else 0
    sheet = Image.new("RGB", (cols * w, rows * h + top), bg)
    dr = ImageDraw.Draw(sheet)
    if title:
        dr.text((6, 4), title, fill=(230, 230, 230))
    for i, im in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * h + top
        sheet.paste(im.resize((w, h)), (x, y))
        if labels:
            dr.rectangle([x, y, x + 8 * len(labels[i]) + 6, y + 14], fill=(0, 0, 0))
            dr.text((x + 3, y + 1), labels[i], fill=(255, 230, 120))
    sheet.save(out)
    return out


def render_previews(name, arm, meshes, actions, clips, tmpdir=None, views=None, sheet_frames=4,
                    contact_view=(-0.75, -1.0, 0.35), extra_turn=None, fog_view=(-1.0, -0.45, 0.06), fog_clip=None, fog_frame=0):
    if not preview_enabled():
        return
    t0 = time.time()
    tmp = tmpdir or os.path.join(BLEND_DIR, "_tmp_" + name)
    os.makedirs(tmp, exist_ok=True)
    setup_render()
    reset_pose(arm)
    set_action(arm, None)
    bpy.context.scene.frame_set(0)
    lo, hi = mesh_bounds(meshes)
    center = (lo + hi) / 2
    size = hi - lo
    # --- turnaround
    preview_setup_studio(center, size)
    views = views or [("front", (0, -1, 0.12)), ("side", (1, 0, 0.12)), ("threequarter", (-0.8, -1.0, 0.4)),
                      ("back3q", (0.8, 1.0, 0.5))]
    paths = []
    for vname, d in views:
        _camera(_cam_fit(center, size, d, lens=50, aspect=0.75, margin=0.95), center, lens=50)
        p = os.path.join(tmp, "turn_%s.png" % vname)
        render_still(p, (360, 480), 20)
        paths.append(p)
    compose_grid(paths, len(paths), os.path.join(PREVIEW_DIR, name + "_turnaround.png"),
                 labels=[v[0] for v in views], title=name + " turnaround (rest pose)")
    # --- fog silhouette (idle-ish frame 0 of the first clip)
    preview_setup_studio(center, size, fog=True)
    first = actions[fog_clip] if fog_clip else list(actions.values())[0]
    reset_pose(arm)
    set_action(arm, first)
    bpy.context.scene.frame_set(fog_frame)
    _camera(_cam_fit(center, size, fog_view, lens=40, aspect=0.75, margin=1.3), center, lens=40)
    render_still(os.path.join(PREVIEW_DIR, name + "_fog.png"), (480, 360), 24)
    # --- contact sheet: global bounds over all clips for consistent framing
    preview_setup_studio(center, size)
    glo, ghi = lo.copy(), hi.copy()
    for c in clips:
        act = actions[c.name]
        reset_pose(arm)
        set_action(arm, act)
        for f in np.linspace(0, c.frames, 3).astype(int):
            bpy.context.scene.frame_set(int(f))
            a, b = mesh_bounds(meshes)
            glo, ghi = np.minimum(glo, a), np.maximum(ghi, b)
    gc = (glo + ghi) / 2
    gs = ghi - glo
    _camera(_cam_fit(gc, gs, contact_view, lens=50, margin=0.92), gc, lens=50)
    imgs, labels = [], []
    for c in clips:
        act = actions[c.name]
        reset_pose(arm)
        set_action(arm, act)
        n = sheet_frames
        if c.loop:
            fr = [int(round(c.frames * i / n)) for i in range(n)]
        else:
            fr = [int(round(c.frames * i / (n - 1))) for i in range(n)]
        for f in fr:
            bpy.context.scene.frame_set(f)
            p = os.path.join(tmp, "c_%s_%03d.png" % (c.name, f))
            render_still(p, (256, 256), 12)
            imgs.append(p)
            labels.append("%s f%d" % (c.name, f))
    compose_grid(imgs, sheet_frames, os.path.join(PREVIEW_DIR, name + "_clips.png"), labels=labels,
                 title=name + " clips (rows) / key frames (cols)")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    set_action(arm, None)
    reset_pose(arm)
    bpy.context.scene.frame_set(0)
    _clear_preview_objects()
    log("previews %.0fs" % (time.time() - t0))


def render_frames(name, arm, meshes, act, frames, view, out, res=(320, 240), samples=12, bounds_from=None):
    """Ad-hoc helper for debugging single clips."""
    setup_render()
    set_action(arm, act)
    lo, hi = mesh_bounds(meshes)
    c = (lo + hi) / 2
    s = hi - lo
    preview_setup_studio(c, s)
    _camera(_cam_fit(c, s, view, lens=50), c, lens=50)
    imgs = []
    for f in frames:
        bpy.context.scene.frame_set(f)
        p = os.path.join(BLEND_DIR, "_dbg_%s_%d.png" % (name, f))
        render_still(p, res, samples)
        imgs.append(p)
    compose_grid(imgs, len(imgs), out, labels=["f%d" % f for f in frames])


# --------------------------------------------------------------------------------------------
# One-call finishing for a creature
# --------------------------------------------------------------------------------------------
def finish_creature(name, arm, meshes, clips, ik_chains, eye_height, loc_bones=("hips",), scale_bones=(),
                    extra_manifest=None, preview_kwargs=None):
    actions = bake_clips(arm, clips, ik_chains, loc_bones=loc_bones, scale_bones=scale_bones)
    body = meshes[0]
    deform_report = {}
    for m in meshes:
        deform_report[m.name] = deformation_check(m, arm, actions)
    for o in [arm] + meshes:
        assert min(o.scale) > 0
    # keep idle (or first) as the active action in the .blend for hand-editing convenience
    reset_pose(arm)
    set_action(arm, None)
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = max(c.frames for c in clips)
    entry = manifest_entry(name, arm, meshes, clips, eye_height, extra_manifest)
    export_fbx(name, arm, meshes, animated=True)
    render_previews(name, arm, meshes, actions, clips, **(preview_kwargs or {}))
    reset_pose(arm)
    set_action(arm, None)
    _clear_preview_objects()
    save_blend(name)
    update_manifest(name, entry)
    return entry


# --------------------------------------------------------------------------------------------
# Anatomy helpers (hands / feet with fingers + nails)
# --------------------------------------------------------------------------------------------
def _rot_toward(v, toward, ang_deg):
    """Rotate unit vector v toward unit vector `toward` by ang_deg (in their common plane)."""
    v = np.array(v, float)
    v /= np.linalg.norm(v)
    t = np.array(toward, float)
    t = t - v * t.dot(v)
    if np.linalg.norm(t) < 1e-9:
        return v
    t /= np.linalg.norm(t)
    a = math.radians(ang_deg)
    return v * math.cos(a) + t * math.sin(a)


def add_digits(F, pt, base, along, spread_dir, curl_dir, n=4, length=0.25, r0=0.016, r1=0.010, spread=0.07,
               curl=25.0, mat=None, nail_mat=None, nail_len=0.03, seed=0, broken=(), lengths=None,
               segs=3, k=0.008, fan=8.0, nail_bone=None, tag="fingers", splay=None):
    """Adds n digits starting at points spread along spread_dir around base, each pointing `along`
    and curling toward curl_dir. Returns list of (tip_pos, tip_dir)."""
    rng = np.random.RandomState(seed)
    base = np.array(base, float)
    along = np.array(along, float) / np.linalg.norm(along)
    sd = np.array(spread_dir, float) / np.linalg.norm(spread_dir)
    tips = []
    if lengths is None:
        lengths = [0.85 + 0.15 * math.sin(math.pi * (i + 0.5) / n) for i in range(n)]
    for i in range(n):
        f = (i / (n - 1) - 0.5) if n > 1 else 0.0
        p = base + sd * f * spread
        d = _rot_toward(along, sd * (1 if f >= 0 else -1), abs(f) * fan * 2 + (splay[i] if splay else 0))
        L = length * lengths[i] * rng.uniform(0.93, 1.07)
        seg_len = L / segs
        pts = [p.copy()]
        dd = d.copy()
        for sgi in range(segs):
            dd = _rot_toward(dd, curl_dir, curl / segs * (1 + 0.3 * rng.uniform(-1, 1)))
            pts.append(pts[-1] + dd * seg_len)
        for sgi in range(segs):
            ra = r0 + (r1 - r0) * sgi / segs
            rb = r0 + (r1 - r0) * (sgi + 1) / segs
            F.add(Capsule(pts[sgi], pts[sgi + 1], ra, rb, mat, None, tag), k=k)
            # knuckle bumps
            if sgi > 0:
                F.add(Ellipsoid(pts[sgi] - np.array(curl_dir) * ra * 0.25, ra * 1.18, (0, 0, 0), mat, None, tag),
                      k=k * 0.8)
        tip = pts[-1]
        tips.append((tip, dd))
        if nail_mat is not None and pt is not None:
            nl = nail_len * (0.35 if i in broken else rng.uniform(0.85, 1.2))
            nb = tip - dd * r1 * 0.6 - np.array(curl_dir) * r1 * 0.35
            nt = tip + dd * nl + np.array(curl_dir) * nl * 0.35
            pt.cone(Vector(nb), Vector(nt), r1 * 0.85, nail_mat, segs=5, flat=0.55,
                    bone=nail_bone)
    return tips


def importance_spheres(spheres):
    """spheres: list of (center, radius, weight) -> fn(co) for body_from_field(importance_fn=...)"""
    def fn(co):
        w = np.zeros(len(co))
        for c, r, k in spheres:
            d = np.linalg.norm(co - np.asarray(c, float), axis=1)
            w = np.maximum(w, k * np.clip(1.5 - d / r, 0, 1))
        return np.clip(w, 0, 1)
    return fn


def add_tufts(body, pt, mats, fur_mat, count=60, seed=5, length=(0.05, 0.12), radius=(0.012, 0.022),
              droop=1.0, max_nz=0.6, normal_mix=0.45, region=None):
    """Matted fur clumps (cones) hanging off faces of fur_mat; weights copied from the skin below."""
    rng = np.random.RandomState(seed)
    me = body.data
    C = face_centers(body)
    N = face_normals(body)
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    ok = (mi == mats.index(fur_mat)) & (N[:, 2] < max_nz)
    if region is not None:
        ok &= region(C)
    cand = np.nonzero(ok)[0]
    if len(cand) == 0:
        return
    pick = rng.choice(cand, size=min(count, len(cand)), replace=False)
    for i in pick:
        c = C[i]
        n = N[i]
        d = n * normal_mix + np.array((0, 0.15, -1.0)) * droop
        d /= np.linalg.norm(d)
        L = rng.uniform(*length)
        base = c - n * radius[0] * 0.6
        pt.cone(Vector(base), Vector(base + d * L), rng.uniform(*radius), fur_mat, segs=4,
                anchor=Vector(c), flat=0.6, twist=rng.uniform(0, 3))


def scale_field(field, S):
    """Uniformly scale every recorded primitive of a Field (after meshing) by S about the origin."""
    for p in field.prims + field.subs:
        if isinstance(p, Ellipsoid):
            p.c = p.c * S
            p.r = p.r * S
        else:
            p.a, p.b = p.a * S, p.b * S
            p.ra, p.rb = p.ra * S, p.rb * S
    field.voxel *= S
