"""The Mines: three levels carved as a signed-distance field (air < 0), meshed with marching cubes in
overlapping chunks (crack-free, and each chunk is a culling unit in Unity).

 L1 (floor ~ +1)  entrance tunnel from the cliff notch · junction hall · west drift → collapse → crawlspace →
                  crystal pocket · east drift → storage room · drop shaft to L2 · lift shaft top · ramp down
 L2 (floor -25)   junction · the Clerk Gallery (beam-lined loop) · worker room · the Grinding Hall (Borer) ·
                  flooded gallery → pump room · plugged drift → deep shaft · ramp to L3
 L3 (floor -55)   hub · breaker room + lift bottom · the chasm edge (the Gaunt walks below) · west tunnel with an
                  unstable plank bridge over a pit (Mourner lure) · east tunnel → crawl → anomalous core pocket
Run: python build_mine.py -- <project_root>
"""
import math, sys, os, random, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lvl_common import *
from skimage import measure

VOX = 0.7
GX0, GX1, GY0, GY1, GZ0, GZ1 = -45.0, 125.0, 234.5, 450.0, -95.0, 12.0
CHUNK = 40
RNG = random.Random(4242)

# -------------------------------------------------------------------------------------------- noise
_rng = np.random.RandomState(7)
_LAT = _rng.rand(64, 64, 64).astype(np.float32) * 2 - 1


def noise3(x, y, z, cell):
    fx, fy, fz = x / cell, y / cell, z / cell
    ix, iy, iz = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64), np.floor(fz).astype(np.int64)
    tx, ty, tz = fx - ix, fy - iy, fz - iz
    tx, ty, tz = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty), tz * tz * (3 - 2 * tz)
    def g(a, b, c):
        return _LAT[(ix + a) & 63, (iy + b) & 63, (iz + c) & 63]
    x00 = g(0, 0, 0) * (1 - tx) + g(1, 0, 0) * tx
    x10 = g(0, 1, 0) * (1 - tx) + g(1, 1, 0) * tx
    x01 = g(0, 0, 1) * (1 - tx) + g(1, 0, 1) * tx
    x11 = g(0, 1, 1) * (1 - tx) + g(1, 1, 1) * tx
    return (x00 * (1 - ty) + x10 * ty) * (1 - tz) + (x01 * (1 - ty) + x11 * ty) * tz


def rock_noise(x, y, z):
    return noise3(x, y, z, 3.2) * 0.75 + noise3(x + 17, y - 9, z + 5, 1.3) * 0.3


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# -------------------------------------------------------------------------------------------- primitives
class Prim:
    def __init__(self, aabb, fn, tag=''):
        self.aabb = aabb   # (min xyz, max xyz)
        self.fn = fn       # fn(X, Y, Z) -> sdf
        self.tag = tag


PRIMS = []


def sd_round_box_local(qa, qb, qc, ha, hb, hc, r):
    """Signed distance of a rounded box in local coordinates (qa, qb, qc relative to the centre)."""
    da = np.abs(qa) - (ha - r)
    db = np.abs(qb) - (hb - r)
    dc = np.abs(qc) - (hc - r)
    outside = np.sqrt(np.maximum(da, 0) ** 2 + np.maximum(db, 0) ** 2 + np.maximum(dc, 0) ** 2)
    inside = np.minimum(np.maximum(da, np.maximum(db, dc)), 0)
    return outside + inside - r


def tunnel(nodes, w=4.0, h=4.0, amp=0.28, tag='tunnel'):
    """Polyline of (x, y, floor_z) nodes. Flat floor, vertical-ish walls, rounded top."""
    rr = min(w * 0.25, h * 0.3)
    for (ax, ay, az), (bx, by, bz) in zip(nodes[:-1], nodes[1:]):
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-3:
            continue
        dx, dy = (bx - ax) / L, (by - ay) / L
        ext = w * 0.5
        def fn(X, Y, Z, ax=ax, ay=ay, az=az, bz=bz, dx=dx, dy=dy, L=L, ext=ext):
            px, py = X - ax, Y - ay
            along = px * dx + py * dy
            lat = -px * dy + py * dx
            t = np.clip(along / L, 0, 1)
            floor = az + (bz - az) * t
            v = Z - floor
            d = sd_round_box_local(along - L * 0.5, lat, v - (h - rr) * 0.5, L * 0.5 + ext, w * 0.5, (h + rr) * 0.5, rr)
            d = np.maximum(d, -v)
            return d + amp * rock_noise(X, Y, Z) * smooth(0.2, 1.4, v)
        mnx, mxx = min(ax, bx) - w - 1, max(ax, bx) + w + 1
        mny, mxy = min(ay, by) - w - 1, max(ay, by) + w + 1
        PRIMS.append(Prim(((mnx, mny, min(az, bz) - 1.5), (mxx, mxy, max(az, bz) + h + 1.5)), fn, tag))


def chamber(cx, cy, fz, sx, sy, h, amp=0.45, round_r=2.5, tag='chamber'):
    rr = min(round_r, h * 0.45, sx * 0.4, sy * 0.4)
    def fn(X, Y, Z):
        v = Z - fz
        d = sd_round_box_local(X - cx, Y - cy, v - (h - rr) * 0.5, sx * 0.5, sy * 0.5, (h + rr) * 0.5, rr)
        d = np.maximum(d, -v)
        return d + amp * rock_noise(X, Y, Z) * smooth(0.2, 1.6, v)
    PRIMS.append(Prim(((cx - sx / 2 - 2, cy - sy / 2 - 2, fz - 1.5), (cx + sx / 2 + 2, cy + sy / 2 + 2, fz + h + 2)), fn, tag))


def shaft(cx, cy, z0, z1, sx, sy, amp=0.12, tag='shaft'):
    def fn(X, Y, Z):
        d = sd_round_box_local(X - cx, Y - cy, Z - (z0 + z1) * 0.5, sx * 0.5, sy * 0.5, (z1 - z0) * 0.5, 0.4)
        return d + amp * rock_noise(X, Y, Z)
    PRIMS.append(Prim(((cx - sx / 2 - 1.5, cy - sy / 2 - 1.5, z0 - 1.5), (cx + sx / 2 + 1.5, cy + sy / 2 + 1.5, z1 + 1.5)), fn, tag))


def chasm(x0, x1, y0, y1, z0, z1):
    def fn(X, Y, Z):
        cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
        d = sd_round_box_local(X - cx, Y - cy, Z - cz, (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2, 6.0)
        return d + 1.4 * noise3(X, Y, Z * 0.6, 7.0) + 0.5 * rock_noise(X, Y, Z)
    PRIMS.append(Prim(((x0 - 4, y0 - 4, z0 - 4), (x1 + 4, y1 + 4, z1 + 4)), fn, 'chasm'))


def sdf_at(p):
    X = np.array([[[p[0]]]]); Y = np.array([[[p[1]]]]); Z = np.array([[[p[2]]]])
    d = 1e9
    for pr in PRIMS:
        (a, b) = pr.aabb
        if a[0] <= p[0] <= b[0] and a[1] <= p[1] <= b[1] and a[2] <= p[2] <= b[2]:
            d = min(d, float(pr.fn(X, Y, Z)[0, 0, 0]))
    return d


# -------------------------------------------------------------------------------------------- layout
L1, L2, L3 = 1.0, -25.0, -55.0
ENTRANCE = [(25, 234.5, 4.0), (25, 250, 3.0), (25, 268, L1)]
HALL = (25, 277, L1, 22, 16, 7.0)
LIFT_TUNNEL_TOP = [(14, 281, L1), (7.6, 282, L1)]
WEST = [(14, 274, L1), (-8, 270, L1), (-22, 282, 0.8), (-26, 296, 0.5)]
CRAWL = [(-26, 298, 0.5), (-33, 311, 0.5)]
POCKET = (-35, 316, 0.5, 7, 6, 3.0)
EAST = [(36, 277, L1), (52, 282, L1), (62, 292, L1), (66, 297, L1)]
STORAGE = (69, 301, L1, 9, 7, 3.6)
DROP_SHAFT = (52, 285.6, L2, L1 + 3.0, 3.6, 3.6)
RAMP12 = [(25, 284, L1), (25, 300, -3), (20, 318, -8), (36, 327, -12), (48, 316, -16), (44, 300, -21), (33, 293, L2)]
J2 = (30, 291, L2, 16, 12, 6.0)
DROP_BOTTOM = [(52, 286, L2), (37, 290, L2)]
GALLERY = [(22, 293, L2), (-8, 297, L2), (-12, 330, L2), (30, 341, L2), (50, 322, L2), (40, 300, L2), (36, 296, L2)]
WORKER = (-15, 334, L2, 10, 8, 3.8)
GRIND_LINK = [(50, 322, L2), (61, 328, L2)]
GRIND = (72, 334, L2, 26, 20, 9.0)
PLUG_DRIFT = [(84, 336, L2), (100, 341, L2)]
DEEP_SHAFT = (100, 344, L3, L2 + 3.5, 3.6, 3.6)
FLOOD = [(36, 287, L2), (50, 276, -26.2), (70, 272, -26.2), (84, 280, L2)]
PUMP = (89, 283, L2, 8, 8, 4.0)
RAMP23 = [(30, 341, L2), (24, 358, -31), (8, 371, -37), (16, 388, -43), (34, 384, -49), (40, 371, L3)]
LIFT_SHAFT = (5, 282, L3 - 1.0, L1 + 7.0, 3.8, 3.8)
LIFT_TUNNEL_BOTTOM = [(7.6, 283, L3), (14, 291, L3)]
BREAKER = (18, 294, L3, 8, 7, 3.6)
L3_SOUTH = [(18, 298, L3), (28, 330, L3), (38, 358, L3)]
H3 = (40, 365, L3, 18, 14, 7.0)
K3_LINK = [(40, 372, L3), (40, 385, L3)]
K3 = (40, 392, L3, 26, 16, 8.0)
CHASM = (12, 68, 399, 440, -88, -38)
WEST3 = [(31, 365, L3), (10, 368, L3), (-18, 372, L3), (-30, 376, L3)]
PIT = (-3, 370, -63.0, 6, 8, 8.5)
PIT_EXIT = [(-3, 370, -63), (-2, 386, -60), (14, 392, -56.5), (27, 392, L3)]
EAST3 = [(49, 365, L3), (75, 368, L3), (100, 372, L3), (110, 376, L3)]
DEEP_LINK = [(100, 346, L3), (100, 371, L3)]
CRAWL3 = [(110, 376, L3), (116, 383, L3)]
ANOM = (118, 388, L3, 6, 6, 3.2)


def define():
    PRIMS.clear()
    tunnel(ENTRANCE, tag='entrance'); chamber(*HALL[:3], *HALL[3:], tag='hall')
    tunnel(LIFT_TUNNEL_TOP); tunnel(WEST, tag='west'); tunnel(CRAWL, w=1.7, h=1.2, amp=0.15, tag='crawl'); chamber(*POCKET, tag='pocket')
    tunnel(EAST, tag='east'); chamber(*STORAGE, round_r=1.0, tag='storage'); shaft(*DROP_SHAFT)
    tunnel(RAMP12, tag='ramp12')
    chamber(*J2, tag='j2'); tunnel(DROP_BOTTOM); tunnel(GALLERY, w=4.0, h=3.8, tag='gallery'); chamber(*WORKER, round_r=1.0, tag='worker')
    tunnel(GRIND_LINK, w=4.5, h=4.2); chamber(*GRIND, amp=0.7, round_r=4.0, tag='grind'); tunnel(PLUG_DRIFT, w=3.6, h=3.4); shaft(*DEEP_SHAFT)
    tunnel(FLOOD, w=4.5, h=3.8, tag='flood'); chamber(*PUMP, round_r=1.2, tag='pump')
    tunnel(RAMP23, tag='ramp23')
    shaft(*LIFT_SHAFT, amp=0.05); tunnel(LIFT_TUNNEL_BOTTOM); chamber(*BREAKER, round_r=1.0, tag='breaker'); tunnel(L3_SOUTH, tag='l3south')
    chamber(*H3, tag='h3'); tunnel(K3_LINK, w=5.0, h=4.5); chamber(*K3, amp=0.6, round_r=3.0, tag='k3')
    chasm(*CHASM)
    tunnel(WEST3, tag='west3'); chamber(PIT[0], PIT[1], PIT[2], PIT[3], PIT[4], PIT[5], round_r=0.8, tag='pit'); tunnel(PIT_EXIT, w=3.2, h=3.2, tag='pitexit')
    tunnel(EAST3, tag='east3'); tunnel(DEEP_LINK); tunnel(CRAWL3, w=1.9, h=1.4, amp=0.15); chamber(*ANOM, round_r=1.5, tag='anom')


# -------------------------------------------------------------------------------------------- meshing
def mesh_all(coll):
    nx = int(round((GX1 - GX0) / VOX)) + 1
    ny = int(round((GY1 - GY0) / VOX)) + 1
    nz = int(round((GZ1 - GZ0) / VOX)) + 1
    objs, tris = [], 0
    t0 = time.time()
    for ci in range(0, nx - 1, CHUNK):
        for cj in range(0, ny - 1, CHUNK):
            for ck in range(0, nz - 1, CHUNK):
                i1, j1, k1 = min(ci + CHUNK + 1, nx), min(cj + CHUNK + 1, ny), min(ck + CHUNK + 1, nz)
                xs = GX0 + np.arange(ci, i1) * VOX
                ys = GY0 + np.arange(cj, j1) * VOX
                zs = GZ0 + np.arange(ck, k1) * VOX
                cmin = (xs[0], ys[0], zs[0]); cmax = (xs[-1], ys[-1], zs[-1])
                hits = [p for p in PRIMS if all(p.aabb[0][a] <= cmax[a] and p.aabb[1][a] >= cmin[a] for a in range(3))]
                if not hits:
                    continue
                vol = np.full((len(xs), len(ys), len(zs)), 3.0, dtype=np.float32)
                for p in hits:
                    (a, b) = p.aabb
                    ia = max(0, int(math.floor((a[0] - xs[0]) / VOX))); ib = min(len(xs), int(math.ceil((b[0] - xs[0]) / VOX)) + 1)
                    ja = max(0, int(math.floor((a[1] - ys[0]) / VOX))); jb = min(len(ys), int(math.ceil((b[1] - ys[0]) / VOX)) + 1)
                    ka = max(0, int(math.floor((a[2] - zs[0]) / VOX))); kb = min(len(zs), int(math.ceil((b[2] - zs[0]) / VOX)) + 1)
                    if ia >= ib or ja >= jb or ka >= kb:
                        continue
                    X, Y, Z = np.meshgrid(xs[ia:ib], ys[ja:jb], zs[ka:kb], indexing='ij')
                    vol[ia:ib, ja:jb, ka:kb] = np.minimum(vol[ia:ib, ja:jb, ka:kb], p.fn(X, Y, Z).astype(np.float32))
                if vol.min() >= 0 or vol.max() <= 0:
                    continue
                verts, faces, normals, _ = measure.marching_cubes(vol, level=0.0, spacing=(VOX, VOX, VOX))
                if len(faces) == 0:
                    continue
                verts += np.array(cmin)
                # faces must face the air (we always look at the rock from inside the mine)
                f = faces[len(faces) // 2]
                a, b, c = verts[f[0]], verts[f[1]], verts[f[2]]
                n = np.cross(b - a, c - a); n /= (np.linalg.norm(n) + 1e-9)
                probe = (a + b + c) / 3 + n * 0.35
                if sdf_at(probe) > 0:
                    faces = faces[:, ::-1]
                centre_z = (cmin[2] + cmax[2]) * 0.5
                name = f'Mine_{ci // CHUNK}_{cj // CHUNK}_{ck // CHUNK}'
                me = bpy.data.meshes.new(name)
                me.from_pydata(verts.tolist(), [], faces.tolist())
                me.update()
                me.uv_layers.new(name='UVMap')
                mat = 'MNF_RockWet_Tri' if centre_z < -40 else 'MNF_RockMine_Tri'
                me.materials.append(material(mat))
                for p in me.polygons:
                    p.use_smooth = True
                ob = bpy.data.objects.new(name, me)
                coll.objects.link(ob)
                objs.append(ob)
                tris += len(faces)
    print(f'mine mesh: {len(objs)} chunks, {tris} tris, {time.time() - t0:.1f}s')
    return objs, tris


# -------------------------------------------------------------------------------------------- dressing
def seg_points(nodes, spacing, start=0.0):
    """Yields (pos(x,y,floor), dir(dx,dy)) every `spacing` meters along a node path."""
    acc = start
    for (ax, ay, az), (bx, by, bz) in zip(nodes[:-1], nodes[1:]):
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-3:
            continue
        dx, dy = (bx - ax) / L, (by - ay) / L
        t = acc
        while t < L:
            k = t / L
            yield (ax + dx * t, ay + dy * t, az + (bz - az) * k), (dx, dy)
            t += spacing
        acc = t - L


def dress(mk):
    M = lambda n, loc, fwd=(0, -1, 0), **k: marker(n, loc, fwd, mk, **k)
    S, N, E, W = (0, -1, 0), (0, 1, 0), (1, 0, 0), (-1, 0, 0)

    def frames(nodes, spacing, broken=0.1):
        for (x, y, z), (dx, dy) in seg_points(nodes, spacing, spacing * 0.5):
            M('MK_PROP_SupportFrame_Broken' if RNG.random() < broken else 'MK_PROP_SupportFrame', (x, y, z), (dx, dy, 0))

    def lamps(nodes, spacing, preset, w=4.0, h=2.5):
        side = 1
        for (x, y, z), (dx, dy) in seg_points(nodes, spacing, 3.0):
            nx_, ny_ = -dy * side, dx * side
            M('MK_LIGHT_' + preset, (x + nx_ * (w / 2 - 0.45), y + ny_ * (w / 2 - 0.45), z + h), (-nx_, -ny_, 0))
            side = -side

    def rails(nodes, spacing=2.0):
        for (x, y, z), (dx, dy) in seg_points(nodes, spacing, 1.0):
            M('MK_PROP_Rail_Straight', (x, y, z + 0.01), (dx, dy, 0))

    def ores(nodes, spacing, zone, w=4.0, wall_chance=0.4):
        for (x, y, z), (dx, dy) in seg_points(nodes, spacing, RNG.uniform(2, spacing)):
            side = RNG.choice((-1, 1))
            nx_, ny_ = -dy * side, dx * side
            if RNG.random() < wall_chance and zone != 'Anomalous':
                M(f'MK_ORE_{zone}_Wall', (x + nx_ * (w / 2 - 0.55), y + ny_ * (w / 2 - 0.55), z + 0.9), (-nx_, -ny_, 0))
            else:
                M(f'MK_ORE_{zone}', (x + nx_ * (w / 2 - 0.9), y + ny_ * (w / 2 - 0.9), z), (dx, dy, 0))

    def clerk_nodes(nodes, spacing, h=3.8):
        for (x, y, z), _ in seg_points(nodes, spacing, 1.0):
            M('MK_CLERK_NODE', (x, y, z + h - 0.6))

    def drips(nodes, n):
        pts = list(seg_points(nodes, 6.0, 2.0))
        for k in range(min(n, len(pts))):
            (x, y, z), _ = pts[RNG.randrange(len(pts))]
            M('MK_SOUND_drip', (x, y, z + 3.0))

    # ---------------- L1
    frames(ENTRANCE, 3.5, 0.05); lamps(ENTRANCE, 9.0, 'MineLamp'); rails(ENTRANCE + [(25, 284, L1)])
    frames(WEST, 3.8, 0.15); lamps(WEST, 11.0, 'MineLamp'); ores(WEST, 7.5, 'Shallow')
    frames(EAST, 3.8, 0.1); lamps(EAST, 11.0, 'MineLamp'); rails(EAST); ores(EAST, 9.0, 'Shallow')
    frames(RAMP12, 5.0, 0.2); lamps(RAMP12, 14.0, 'MineLampDim'); ores(RAMP12, 14.0, 'Shallow')
    hx, hy, hz = HALL[:3]
    M('MK_LIGHT_String', (hx, hy - 2, hz + 5.2), E)
    M('MK_LIGHT_MineLamp', (hx - 10.4, hy + 3, hz + 3), E); M('MK_LIGHT_MineLamp', (hx + 10.4, hy - 3, hz + 3), W)
    M('MK_PROP_Workstation', (hx + 8, hy + 5.5, hz), S)
    M('MK_LORE_lore_quota', (hx + 8.1, hy + 5.4, hz + 0.8), S)
    M('MK_PROP_Minecart', (hx - 6, hy - 4, hz), N); M('MK_PROP_Crate_Mine', (hx + 9, hy - 6, hz), W)
    M('MK_PROP_Barrel_Mine', (hx + 9.6, hy - 4.8, hz), W); M('MK_PROP_ToolPile', (hx - 9, hy + 6, hz), E)
    M('MK_PROP_PipeRun', (hx - 10.6, hy - 6, hz + 4.2), E)
    for k in range(4):
        M('MK_ORE_Shallow', (hx - 8 + k * 5.0, hy + 7.0, hz), S)
    M('MK_EVENT_MinecartNudge', (hx - 1.5, hy - 6, hz), N)
    M('MK_EVENT_PARecording', (hx + 10.6, hy + 1, hz + 3.5), W)
    M('MK_SIGN_5_0.7_0.5', (23.0, 239.0, 3.6 + 1.6), E)                # LEVEL 1 on the entrance wall
    M('MK_SIGN_3_0.6_0.45', (hx - 10.7, hy - 0.5, hz + 2.2), E)
    M('MK_SOUND_electrical_buzz_loop', (STORAGE[0], STORAGE[1], L1 + 3))
    # lift top
    M('MK_ELEV_Top', (LIFT_SHAFT[0], LIFT_SHAFT[1], L1), E)
    M('MK_ELEV_CallTop', (10.5, 279.95, L1 + 1.3), N)
    M('MK_SIGN_0_0.6_0.6', (12.0, 279.95, L1 + 2.2), N)
    # crawl + pocket
    M('MK_PROP_RubblePile_A', (-25.4, 296.6, 0.5), (0.3, 1, 0))
    px, py, pz = POCKET[:3]
    M('MK_ORE_Mid', (px - 1.5, py + 1.5, pz), S); M('MK_ORE_Mid', (px + 2, py - 1, pz), W)
    M('MK_LORE_lore_knocking', (px, py - 1.8, pz + 0.05), S)
    M('MK_ITEM_miner_tag', (px + 0.6, py - 2.0, pz + 0.05), S)
    M('MK_EVENT_LightTurnsOn', (-29.0, 304.0, 0.5 + 0.9), (0.9, -0.4, 0))
    M('MK_EVENT_PhantomFootsteps', (-26, 294, 0.5))
    # storage room
    sx, sy, sz = STORAGE[:3]
    M('MK_PROP_Generator_Small', (sx + 2.5, sy + 2, sz), S); M('MK_PROP_Crate_Mine', (sx - 3, sy + 2.3, sz), S)
    M('MK_PROP_Crate_Mine', (sx - 3.2, sy + 1.0, sz), E); M('MK_PROP_Workstation', (sx - 2.5, sy - 2.2, sz), N)
    M('MK_LORE_lore_assay', (sx - 2.4, sy - 2.3, sz + 0.8), N)
    M('MK_EVENT_DeadRoomHum', (sx + 2.5, sy + 2, sz + 1.0))
    M('MK_LIGHT_MineLampDim', (sx + 4.3, sy - 1, sz + 2.4), W)
    M('MK_EVENT_MinecartNudge', (45.0, 279.6, L1), (0.95, 0.3, 0))
    # drop shaft: timber ledges (geometry is built separately) + a hanging rope from L1
    M('MK_ROPE_26', (DROP_SHAFT[0] + 1.2, DROP_SHAFT[1] + 1.2, L1 + 0.6))

    # ---------------- L2
    jx, jy, jz = J2[:3]
    M('MK_SIGN_6_0.7_0.5', (jx - 7.6, jy + 2, jz + 2.0), E)
    M('MK_LIGHT_MineLampDim', (jx + 7.6, jy, jz + 3.0), W); M('MK_LIGHT_MineLampDim', (jx - 7.6, jy - 3, jz + 3.0), E)
    M('MK_PROP_Minecart', (jx + 4, jy - 4, jz), E)
    frames(GALLERY, 3.0, 0.12); clerk_nodes(GALLERY, 4.0); lamps(GALLERY, 18.0, 'MineLampDim'); ores(GALLERY, 9.0, 'Mid')
    clerk_nodes([(jx - 6, jy - 4, jz + 2), (jx + 6, jy - 4, jz + 2)], 4.0, h=4.6)
    clerk_nodes([(jx - 6, jy + 3, jz + 2), (jx + 6, jy + 3, jz + 2)], 4.0, h=4.6)
    M('MK_CLERK_SPAWN', (-10, 312, L2 + 3.2))
    wx, wy, wz = WORKER[:3]
    clerk_nodes([(wx - 3, wy, wz), (wx + 3, wy, wz)], 3.0)
    M('MK_PROP_Workstation', (wx - 2, wy + 2.5, wz), S); M('MK_PROP_Helmet', (wx - 1.6, wy + 2.3, wz + 0.8), S)
    M('MK_LORE_lore_tally', (wx - 2.3, wy + 2.4, wz + 0.82), S)
    M('MK_DECAL_9_0.9', (wx - 4.6, wy, wz + 1.6), E); M('MK_DECAL_6_0.4', (wx + 4.6, wy + 1, wz + 1.3), W)
    M('MK_SIGN_14_0.4_0.4', (wx + 4.6, wy - 2, wz + 2.0), W)
    M('MK_EVENT_LightTurnsOn', (wx + 4.4, wy + 3, wz + 2.4), W)
    M('MK_EVENT_WallScratch', (10.0, 339.0, L2 + 1.2), S)              # plate is centred on its pivot
    M('MK_EVENT_PhantomFootsteps', (-11, 316, L2)); M('MK_EVENT_PeripheralSilhouette', (-12, 327, L2), S)
    drips(GALLERY, 6)
    # grinding hall (Borer)
    gx, gy, gz = GRIND[:3]
    M('MK_BORER_SPAWN_34', (gx, gy, gz))
    M('MK_BORER_HOLE', (gx - 12.2, gy + 4, gz), E); M('MK_BORER_HOLE', (gx + 12.2, gy - 6, gz), W); M('MK_BORER_HOLE', (gx + 4, gy + 9.2, gz), S)
    M('MK_BORER_HOLE_Plug', (85.5, 336.4, L2), (-0.95, -0.3, 0))
    for k in range(5):
        M('MK_ORE_Mid', (gx - 9 + k * 4.5, gy - 8.2, gz), N)
    M('MK_ORE_Deep', (gx + 8, gy + 6, gz), S)
    M('MK_PROP_RubblePile_B', (gx - 6, gy + 6, gz), E); M('MK_PROP_SupportFrame_Broken', (61.5, 328.5, L2), (1, 0.55, 0))
    for (x, y, f, c) in [(gx - 12.4, gy + 4, E, 5), (gx + 12.4, gy - 6, W, 4), (gx + 4, gy + 9.4, S, 5), (gx - 12.4, gy - 3, E, 15)]:
        M(f'MK_DECAL_{c}_1.4', (x, y, gz + 1.5), f)
    M('MK_LORE_lore_borer', (58, 326.5, L2 + 0.05), S)
    M('MK_LIGHT_MineLampDim', (gx - 12.6, gy - 7, gz + 3.0), E)
    # a worked hall, not an empty cavern: string lights, wall lamps, the grinder's generator + pipe run, a parked cart,
    # tool and supply piles (all snapped to the rock by snap_markers)
    M('MK_LIGHT_String', (gx - 4, gy, gz + 7.5), E); M('MK_LIGHT_String', (gx + 5, gy + 1, gz + 7.5), (0.2, 1, 0))
    M('MK_LIGHT_MineLamp', (gx + 12.6, gy + 3, gz + 3.0), W); M('MK_LIGHT_MineLamp', (gx - 2, gy + 9.6, gz + 3.0), S)
    M('MK_PROP_Generator_Small', (gx + 9.5, gy + 6.5, gz), S); M('MK_PROP_PipeRun', (gx + 12.7, gy + 6.0, gz + 2.2), W)
    M('MK_PROP_Minecart', (gx - 4.0, gy - 4.5, gz), E); M('MK_PROP_ToolPile', (gx - 7.5, gy - 3.0, gz), E)
    M('MK_PROP_Barrel_Mine', (gx + 7.4, gy + 7.6, gz), S); M('MK_PROP_Barrel_Mine', (gx + 6.6, gy + 7.9, gz), S)
    M('MK_PROP_Crate_Mine', (gx + 10.2, gy + 3.2, gz), W); M('MK_PROP_Crate_Mine', (gx + 9.4, gy + 2.0, gz), (-0.9, 0.4, 0))
    M('MK_PROP_Sign_Level', (gx - 11.0, gy + 7.5, gz), (0.6, -0.8, 0))
    M('MK_SIGN_4_0.6_0.6', (gx + 12.4, gy + 5.0, gz + 1.8), W)            # HIGH VOLTAGE by the generator
    # flooded gallery + pump room
    for (x, y, z), (dx, dy) in seg_points(FLOOD[1:3], 2.0, 1.0):
        M('MK_PROP_Walkway', (x - dy * 1.3, y + dx * 1.3, -25.45), (dy, -dx, 0))      # long axis (local X) along the tunnel
    for x, y in ((52, 276), (66, 272), (79, 276)):
        M('MK_SOUND_water_trickle_loop', (x, y, -25.0))
    px, py, pz = PUMP[:3]
    M('MK_PROP_Generator_Small', (px + 2, py + 2, pz), S); M('MK_ITEM_miner_tag', (px - 2, py - 2, pz + 0.05), N)
    M('MK_ORE_Mid', (px - 2.5, py + 2.5, pz), S); M('MK_EVENT_DeadRoomHum', (px + 2, py + 2, pz + 1))
    M('MK_EVENT_LightTurnsOn', (px - 3.6, py, pz + 2.4), E)
    # ramp to L3
    frames(RAMP23, 6.0, 0.35); lamps(RAMP23, 20.0, 'MineLampDim'); ores(RAMP23, 15.0, 'Mid'); drips(RAMP23, 4)
    M('MK_EVENT_PhantomFootsteps', (16, 386, -43))
    M('MK_MOURNER_POINT', (16, 388, -43))

    # ---------------- L3
    hx3, hy3, hz3 = H3[:3]
    M('MK_SIGN_7_0.8_0.55', (hx3 - 8.6, hy3 - 3, hz3 + 2.2), E)
    M('MK_SIGN_13_0.8_0.8', (hx3 - 8.6, hy3 + 2.5, hz3 + 1.6), E)          # DO NOT FOLLOW THE LIGHT
    M('MK_LIGHT_MineLampDim', (hx3 + 8.6, hy3, hz3 + 3), W)
    M('MK_EVENT_PARecording', (hx3 + 8.7, hy3 + 4, hz3 + 3.5), W)
    M('MK_MOURNER_SPAWN', (hx3, hy3 + 4, hz3))
    for k in range(3):
        M('MK_ORE_Deep', (hx3 - 6 + k * 6, hy3 - 6.2, hz3), N)
    # breaker room + lift bottom
    bx, by, bz = BREAKER[:3]
    M('MK_ELEV_Bottom', (LIFT_SHAFT[0], LIFT_SHAFT[1], L3), E)
    M('MK_ELEV_CallBottom', (bx - 3.9, by - 1.0, bz + 1.3), E)
    M('MK_ELEV_Breaker', (bx + 3.9, by, bz + 1.3), W)
    M('MK_SIGN_4_0.5_0.5', (bx + 3.95, by + 1.0, bz + 2.1), W)
    M('MK_LORE_lore_last_Tape', (bx + 2.5, by - 2.6, bz + 0.05), N)
    M('MK_PROP_Workstation', (bx + 1.5, by - 2.5, bz), N)
    M('MK_LIGHT_MineLampDim', (bx - 3.9, by + 2, bz + 2.6), E)
    frames(L3_SOUTH, 7.0, 0.5); lamps(L3_SOUTH, 24.0, 'MineLampDim'); ores(L3_SOUTH, 11.0, 'Deep')
    # chasm edge
    kx, ky, kz = K3[:3]
    for k in range(10):
        M('MK_PROP_Railing', (kx - 9 + k * 2.0, ky + 6.6, kz), N)
    M('MK_LORE_lore_chasm', (kx - 4, ky + 4.0, kz + 0.05), N)
    M('MK_ITEM_miner_tag', (kx + 9, ky + 5.0, kz + 0.05), N)
    for k in range(4):
        M('MK_ORE_Deep', (kx - 11 + k * 7, ky - 6.5, kz), N)
    M('MK_MOURNER_POINT', (kx - 11, ky + 5, kz)); M('MK_MOURNER_POINT', (kx + 11, ky + 5, kz))
    M('MK_EVENT_PeripheralSilhouette', (kx + 12, ky + 5.5, kz), W)
    M('MK_GAUNT_SPAWN', (16, 425, CHASM[4]))
    for k, (x, y) in enumerate([(16, 425), (30, 432), (48, 430), (64, 422)]):
        M(f'MK_GAUNT_PATH_{k}', (x, y, CHASM[4]))
    # west tunnel: unstable bridge over a pit + lure
    frames(WEST3, 6.0, 0.4); ores(WEST3, 12.0, 'Deep')
    M('MK_MOURNER_LURE', (-10, 369.5, L3)); M('MK_MOURNER_POINT', (-28, 376, L3))
    M('MK_LORE_lore_foreman_Tape', (14, 367.5, L3 + 0.05), W)
    M('MK_EVENT_PhantomFootsteps', (-28, 376, L3)); M('MK_EVENT_PeripheralSilhouette', (-26, 375, L3), E)
    frames(PIT_EXIT, 6.0, 0.6)
    # east tunnel → crawl → anomalous pocket
    frames(EAST3, 6.0, 0.4); ores(EAST3, 12.0, 'Deep'); drips(EAST3, 4)
    M('MK_MOURNER_POINT', (105, 374, L3)); M('MK_EVENT_WallScratch', (80, 366.3, L3), N)
    M('MK_EVENT_PeripheralSilhouette', (104, 373, L3), W)
    ax_, ay_, az_ = ANOM[:3]
    M('MK_ORE_Anomalous', (ax_ - 1, ay_ + 1, az_), S); M('MK_ORE_Anomalous', (ax_ + 1.5, ay_ - 1, az_), W)
    M('MK_LIGHT_Crystal', (ax_, ay_, az_ + 2.0))
    # teleports for debugging
    M('MK_TELEPORT_MineL1', (hx, hy - 4, hz + 0.1), N); M('MK_TELEPORT_MineL2', (jx, jy, jz + 0.1), N)
    M('MK_TELEPORT_MineL3', (hx3, hy3, hz3 + 0.1), N); M('MK_TELEPORT_Chasm', (kx, ky, kz + 0.1), N)


def extra_geometry(coll):
    g = Geo(tile=1.5)
    # drop shaft and deep shaft: timber ledges every 3.5 m (climbing route down)
    for (cx, cy, z0, z1, sx, sy) in (DROP_SHAFT, DEEP_SHAFT):
        k = 0
        z = z1 - 4.0
        while z > z0 + 1.0:
            side = k % 4
            if side == 0:
                g.box((cx - sx / 2 + 0.1, cy - sy / 2 + 0.1, z), (cx - sx / 2 + 1.0, cy + sy / 2 - 0.1, z + 0.25), 'MNF_WoodBeam')
            elif side == 1:
                g.box((cx - sx / 2 + 0.1, cy + sy / 2 - 1.0, z), (cx + sx / 2 - 0.1, cy + sy / 2 - 0.1, z + 0.25), 'MNF_WoodBeam')
            elif side == 2:
                g.box((cx + sx / 2 - 1.0, cy - sy / 2 + 0.1, z), (cx + sx / 2 - 0.1, cy + sy / 2 - 0.1, z + 0.25), 'MNF_WoodBeam')
            else:
                g.box((cx - sx / 2 + 0.1, cy - sy / 2 + 0.1, z), (cx + sx / 2 - 0.1, cy - sy / 2 + 1.0, z + 0.25), 'MNF_WoodBeam')
            z -= 3.5
            k += 1
    # lift shaft guide rails in the corners (outside the 3 x 3 m platform)
    cx, cy, z0, z1, sx, sy = LIFT_SHAFT
    for dx in (-1, 1):
        for dy in (-1, 1):
            x, y = cx + dx * 1.7, cy + dy * 1.7
            g.box((x - 0.08, y - 0.08, z0), (x + 0.08, y + 0.08, z1), 'MNF_MetalRusted')
    g.build('ShaftTimbers', coll)

    # the plank bridge over the pit (collapses when stood on)
    px, py, pz, psx, psy, ph = PIT
    u = Geo(tile=1.5)
    for k in range(9):
        x = px - psx / 2 - 0.4 + k * ((psx + 0.8) / 8.6)
        u.box((x, py - 1.4, L3 - 0.12), (x + 0.6, py + 1.4, L3 - 0.02), 'MNF_WoodRotten')
    u.box((px - psx / 2 - 0.6, py - 1.5, L3 - 0.3), (px + psx / 2 + 0.6, py - 1.3, L3 - 0.1), 'MNF_WoodRotten')
    u.box((px - psx / 2 - 0.6, py + 1.3, L3 - 0.3), (px + psx / 2 + 0.6, py + 1.5, L3 - 0.1), 'MNF_WoodRotten')
    u.build('UNSTABLE_PlankBridge', coll)

    # water in the flooded gallery
    w = Geo(tile=3.0)
    for (ax, ay, az), (bx, by, bz) in zip(FLOOD[:-1], FLOOD[1:]):
        L = math.hypot(bx - ax, by - ay); dx, dy = (bx - ax) / L, (by - ay) / L
        nx_, ny_ = -dy * 2.6, dx * 2.6
        a0, b0 = (ax - dx * 2, ay - dy * 2), (bx + dx * 2, by + dy * 2)
        w.quad((a0[0] + nx_, a0[1] + ny_, -25.55), (a0[0] - nx_, a0[1] - ny_, -25.55), (b0[0] - nx_, b0[1] - ny_, -25.55), (b0[0] + nx_, b0[1] + ny_, -25.55), 'MNF_Water')
    w.build('WATER_Flood', coll)


def zones(coll):
    zone_box('ZONE_MineShallow_3', (GX0, GY0, -6), (GX1, GY1, 14), coll)
    zone_box('ZONE_MineMid_3', (GX0, GY0, -36), (GX1, GY1, -6), coll)
    zone_box('ZONE_MineDeep_3', (GX0, GY0, -100), (GX1, GY1, -36), coll)
    zone_box('GAUNTVIEW', (27, 392, L3 - 1), (53, 402, L3 + 6), coll)
    zone_box('KILL_Chasm', (CHASM[0], CHASM[2], CHASM[4] + 1), (CHASM[1], CHASM[3], CHASM[4] + 10), coll)


# -------------------------------------------------------------------------------------------- surface snapping
WALL_PREFIX = ('MK_LIGHT_MineLamp', 'MK_EVENT_LightTurnsOn', 'MK_EVENT_PARecording', 'MK_EVENT_WallScratch', 'MK_PROP_PA_Speaker',
               'MK_PROP_TunnelMarker_', 'MK_PROP_ScratchedPlate', 'MK_PROP_MineLamp', 'MK_ELEV_CallTop', 'MK_ELEV_CallBottom',
               'MK_ELEV_Breaker', 'MK_SIGN_', 'MK_DECAL_', 'MK_PROP_PipeRun')
FLOOR_PREFIX = ('MK_PROP_', 'MK_ORE_', 'MK_ITEM_', 'MK_LORE_', 'MK_BORER_HOLE', 'MK_EVENT_MinecartNudge', 'MK_EVENT_PeripheralSilhouette',
                'MK_TELEPORT_', 'MK_MOURNER_', 'MK_GAUNT_')
REST = {'MK_ITEM_miner_tag': 0.006, 'MK_ITEM_food_can': 0.065, 'MK_ITEM_glowstick': 0.016, 'MK_ITEM_medkit': 0.205,
        'MK_ITEM_battery': 0.02, 'MK_ITEM_flare': 0.017, 'MK_LORE_': 0.006}
ATLAS = 4


def _clean(n):
    import re
    return re.sub(r'\.\d{3}$', '', n)


def _set_fwd(e, f, pitch=None):
    e.rotation_euler = Euler((e.rotation_euler.x if pitch is None else pitch, e.rotation_euler.y, yaw_from_forward(f)), 'XYZ')


def obox(g, centre, right, up, fwd, hw, hh, hd, mat):
    """Oriented box: half extents along right/up/fwd."""
    c = Vector(centre)
    P = lambda a, b, d: tuple(c + right * (a * hw) + up * (b * hh) + fwd * (d * hd))
    q = [((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)), ((1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1)),
         ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)), ((1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1)),
         ((-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1)), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))]
    for quad in q:
        g.face([P(*v) for v in quad], mat)


def snap_markers(geo_coll, mk_coll):
    """The rock is an SDF with noise, the markers were laid out on the nominal tunnel: put every wall prop on the
    real wall (facing out along the surface), every floor prop/item on the real floor, rails along the slope, signs
    on backing planks and decals as meshes that follow the rock."""
    from mathutils.bvhtree import BVHTree
    import bmesh as _bm
    rock = [o for o in geo_coll.objects if o.type == 'MESH' and not o.name.startswith(('ZONE_', 'WATER_', 'KILL_', 'GAUNTVIEW'))]
    bm = _bm.new()
    for o in rock:
        tmp = o.data.copy()
        tmp.transform(o.matrix_world)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    deco = Geo(tile=1.0)
    stats = {}
    up = Vector((0, 0, 1))

    def count(k):
        stats[k] = stats.get(k, 0) + 1

    def wall_hit(p, f):
        h = bvh.ray_cast(p + f * 0.6, -f, 4.0)
        if h[0] is not None:
            return h
        best = None
        for k in range(16):
            a = k * math.pi / 8
            d = Vector((math.cos(a), math.sin(a), 0))
            hh = bvh.ray_cast(p, d, 4.0)
            if hh[0] is not None and (best is None or hh[3] < best[3]):
                best = hh
        return best

    def floor_z(p, above=0.8, depth=3.0):
        h = bvh.ray_cast(p + up * above, -up, above + depth)
        return None if h[0] is None else h[0].z

    frames = []
    for e in mk_coll.objects:
        if _clean(e.name).startswith('MK_PROP_SupportFrame'):
            ff = e.matrix_world.to_3x3() @ Vector((0, -1, 0))
            frames.append((e.location.copy(), Vector((ff.x, ff.y, 0)).normalized()))

    def in_frame(q):
        for fp, ff in frames:
            d = q - fp
            if abs(d.z) < 4.5 and d.length < 3.2 and abs(d.dot(ff)) < 0.65:
                return True
        return False

    def clear_of_frames(e, tangent):
        q = e.location.copy()
        if not in_frame(q):
            return
        for off in (1.2, -1.2, 1.9, -1.9):
            if not in_frame(q + tangent * off):
                e.location = q + tangent * off
                count('moved_off_frame')
                return

    for e in list(mk_coll.objects):
        n = _clean(e.name)
        if n.startswith(('MK_LIGHT_MineLamp', 'MK_ORE_', 'MK_EVENT_LightTurnsOn', 'MK_PROP_PA_Speaker')):
            ff = e.matrix_world.to_3x3() @ Vector((0, -1, 0))
            clear_of_frames(e, Vector((-ff.y, ff.x, 0)).normalized() if not n.startswith('MK_ORE_') or n.endswith('_Wall')
                            else Vector((ff.x, ff.y, 0)).normalized())
        p = e.location.copy()
        f = e.matrix_world.to_3x3() @ Vector((0, -1, 0))
        f.z = 0
        f = f.normalized() if f.length > 1e-4 else Vector((0, -1, 0))
        if n.startswith(WALL_PREFIX) or (n.startswith('MK_ORE_') and n.endswith('_Wall')):
            if abs(e.rotation_euler.x) > 0.3:         # floor/ceiling decals: leave
                continue
            h = wall_hit(p, f)
            if h is None:
                count('wall_miss'); continue
            loc, nrm = h[0], h[1]
            nh = Vector((nrm.x, nrm.y, 0))
            nf = nh.normalized() if nh.length > 0.35 else f
            if nf.dot(f) < -0.2:
                nf = f
            e.location = loc
            _set_fwd(e, nf)
            count('wall')
            if n.startswith('MK_SIGN_'):
                parts = n.split('_')
                w, hgt = float(parts[3]), float(parts[4]) if len(parts) > 4 else float(parts[3])
                right = Vector((-nf.y, nf.x, 0)).normalized()           # Blender local +X of a marker facing nf
                # backing plank bolted to the rock (its back on the most protruding rock under it), sign on its face
                prot = 0.0
                for a_ in (-1, 0, 1):
                    for b_ in (-1, 0, 1):
                        c = loc + right * (a_ * (w / 2 + 0.06)) + up * (b_ * (hgt / 2 + 0.06))
                        hh = bvh.ray_cast(c + nf * 0.6, -nf, 1.2)
                        if hh[0] is not None:
                            prot = max(prot, 0.6 - hh[3])
                base = loc + nf * prot
                obox(deco, base + nf * 0.03, right, up, nf, w / 2 + 0.06, hgt / 2 + 0.06, 0.03, 'MNF_WoodPlanks')
                e.location = base + nf * 0.06
                count('sign_plank')
            elif n.startswith('MK_DECAL_'):
                parts = n.split('_')
                cell, size = int(parts[2]), float(parts[3])
                right = Vector((-nf.y, nf.x, 0)).normalized()
                N = 7
                verts, uvs, faces = [], [], []
                for j in range(N + 1):
                    for i in range(N + 1):
                        u, v = i / N, j / N
                        q = loc + right * ((u - 0.5) * size) + up * ((v - 0.5) * size)
                        hh = bvh.ray_cast(q + nf * 0.6, -nf, 1.4)
                        verts.append(tuple((hh[0] + hh[1].normalized() * 0.012) if hh[0] is not None else (q + nf * 0.012)))
                        r_, c_ = divmod(cell, ATLAS)
                        uvs.append((c_ / ATLAS + (0.004 + u * (1 / ATLAS - 0.008)), 1 - (r_ + 1) / ATLAS + (0.004 + v * (1 / ATLAS - 0.008))))
                for j in range(N):
                    for i in range(N):
                        a0 = j * (N + 1) + i
                        faces.append((a0, a0 + 1, a0 + N + 2, a0 + N + 1))
                me = bpy.data.meshes.new('NOCOL_DECAL_%d' % cell)
                me.from_pydata(verts, [], faces)
                uvl = me.uv_layers.new(name='UVMap')
                for poly in me.polygons:
                    for li in poly.loop_indices:
                        uvl.data[li].uv = uvs[me.loops[li].vertex_index]
                me.materials.append(material('MNF_Decals'))
                ob = bpy.data.objects.new('NOCOL_DECAL_%d' % cell, me)
                geo_coll.objects.link(ob)
                bpy.data.objects.remove(e)
                count('decal_mesh')
            continue
        if n.startswith('MK_LIGHT_String'):
            h = bvh.ray_cast(p, up, 6.0)
            if h[0] is not None:
                e.location.z = h[0].z
                count('ceiling')
            continue
        if n.startswith('MK_PROP_Walkway'):
            fz = floor_z(p, above=0.3, depth=4.0)
            if fz is None or fz > p.z - 0.1:
                bpy.data.objects.remove(e)                   # dry floor here: no catwalk needed
                count('walkway_removed'); continue
            right = Vector((-f.y, f.x, 0))
            for a in (-0.85, 0.85):
                for b in (-0.45, 0.45):
                    c = p + right * a + f * b
                    cz = floor_z(c, above=0.1, depth=4.0)
                    if cz is not None and cz < p.z - 0.05:
                        deco.box((c.x - 0.04, c.y - 0.04, cz - 0.1), (c.x + 0.04, c.y + 0.04, p.z), 'MNF_MetalRusted')
            count('walkway_posts'); continue
        if n.startswith('MK_PROP_Railing'):
            q = p.copy()
            for k in range(41):
                fz = floor_z(q + f * 0.1, above=0.5, depth=0.6)
                if fz is not None:
                    break
                q -= f * 0.25
            if fz is not None:
                e.location = Vector((q.x, q.y, fz))
                count('railing')
            continue
        if n.startswith('MK_PROP_Rail_'):
            z0 = floor_z(p, above=0.5, depth=1.5)
            z1 = floor_z(p + f * 2.0, above=0.5, depth=1.5)
            if z0 is not None and z1 is not None:
                e.location.z = z0
                _set_fwd(e, f, pitch=-math.atan2(z1 - z0, 2.0))
                count('rail')
            continue
        if n.startswith(FLOOR_PREFIX) and not n.startswith(('MK_PROP_Elevator', 'MK_PROP_LampString')):
            fz = floor_z(p, above=0.8, depth=3.5)
            if fz is None or not (-0.6 < p.z - fz < 3.0):
                continue                                     # on furniture / in a shaft: keep the authored height
            rest = next((v for k, v in REST.items() if n.startswith(k)), None)
            if n.startswith(('MK_ITEM_', 'MK_LORE_')):
                e.location.z = fz + (rest if rest is not None else 0.01)
            else:
                e.location.z = fz - (0.02 if n.startswith('MK_PROP_') else 0.0)
            count('floor')
    if deco.faces:
        deco.build('MineDressing', geo_coll)
    print('snap:', stats)


def build(out_dir):
    reset_scene()
    geo = collection('MineGeometry')
    mk = collection('MineMarkers')
    define()
    mesh_objs, tris = mesh_all(geo)
    extra_geometry(geo)
    zones(geo)
    dress(mk)
    snap_markers(geo, mk)
    objs = [o for o in bpy.data.objects if o.type in ('MESH', 'EMPTY')]
    export_fbx(os.path.join(out_dir, 'Mine.fbx'), objs)
    return objs, tris


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    root = argv[0] if argv else os.path.join(os.path.dirname(__file__), '..', '..', '..')
    out = os.path.join(root, 'Assets', 'MonkeyNoFear', 'Art', 'Models', 'Levels')
    objs, tris = build(out)
    os.makedirs(os.path.join(root, 'SourceArt', 'Levels'), exist_ok=True)
    prev = os.path.join(root, 'Docs', 'previews', 'levels')
    os.makedirs(prev, exist_ok=True)
    for o in bpy.data.objects:
        if o.name.startswith(('ZONE_', 'GAUNTVIEW', 'KILL_')):
            o.hide_render = True
    load_kits(os.path.join(root, 'Assets', 'MonkeyNoFear', 'Art', 'Models', 'Props'))
    dress_preview([o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.startswith('MK_')])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(root, 'SourceArt', 'Levels', 'Mine_preview.blend'))
    lamps = [((25, 255, 3.5), 400), ((25, 277, 5), 1500), ((30, 291, -21), 900), ((40, 365, -50), 900), ((40, 392, -50), 1200), ((72, 334, -19), 1500)]
    render_preview(os.path.join(prev, 'mine_entrance.png'), (25, 246.5, 4.4), (25, 275, 2.0), lens=18, samples=10, sun=False, world=0.02, res=(800, 450), extra_lights=lamps)
    render_preview(os.path.join(prev, 'mine_hall.png'), (16, 270, 4.0), (32, 282, 1.5), lens=16, samples=10, sun=False, world=0.02, res=(800, 450), extra_lights=lamps)
    render_preview(os.path.join(prev, 'mine_gallery.png'), (20, 293.5, L2 + 1.6), (-8, 297, L2 + 1.5), lens=18, samples=10, sun=False, world=0.02, res=(800, 450), extra_lights=lamps + [((5, 295, -22), 500)])
    render_preview(os.path.join(prev, 'mine_grind.png'), (62, 327, L2 + 3), (78, 338, L2 + 1), lens=16, samples=10, sun=False, world=0.02, res=(800, 450), extra_lights=lamps)
    render_preview(os.path.join(prev, 'mine_chasm.png'), (40, 397.5, L3 + 1.7), (36, 428, -82), lens=18, samples=10, sun=False, world=0.02, res=(800, 450), extra_lights=lamps + [((40, 420, -70), 4000)])
    print('mine objects', len(objs), 'tris', tris)
