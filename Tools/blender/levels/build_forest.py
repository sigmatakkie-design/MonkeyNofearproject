"""The Haunted Forest: a 300 × 300 m heightfield between the bunker (south) and the mine cliff (north).

Landmarks (Blender XY):  bunker portal cut (0, 44) · trail north · river with a broken bridge (~y 112)
 · log crossing (west) · shallow ford (east) · Camp A (35, 140) · the Clearing (10, 170) · the Shelf plateau with
 the ruined cabin and watchtower (-60, 175) · grotto (85, 195) · huge gnarled trees · mine entrance (25, 235)
 in the north cliff. Boundary cliffs plus invisible slippery walls keep players inside.
"""
import math, sys, os, random
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lvl_common import *

X0, X1, Y0, Y1, STEP = -150.0, 150.0, -60.0, 240.0, 1.5
RNG = random.Random(1337)

TRAIL = [(0, 46), (-6, 70), (-12, 88), (-2, 104), (2, 112), (8, 124), (28, 136), (31, 150), (14, 164), (12, 182), (24, 198), (27, 214), (25, 232)]
CLEARING, CAMP_A, CABIN, GROTTO = (10, 170), (35, 140), (-60, 176), (85, 196)
MINE_X, MINE_Z = 25.0, 4.0


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def value_noise(X, Y, cell, seed, amp):
    rng = np.random.RandomState(seed)
    nx = int((X1 - X0) / cell) + 4
    ny = int((Y1 - Y0) / cell) + 4
    g = rng.rand(ny, nx) * 2 - 1
    fx = (X - X0) / cell + 1
    fy = (Y - Y0) / cell + 1
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
    tx, ty = fx - ix, fy - iy
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a = g[iy, ix]; b = g[iy, ix + 1]; c = g[iy + 1, ix]; d = g[iy + 1, ix + 1]
    return amp * ((a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty)


def river_y(x):
    return 112 + 8 * np.sin(x / 35.0) + 3 * np.sin(x / 13.0 + 1.0)


def dist_polyline(X, Y, pts):
    d = np.full(X.shape, 1e9)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        t = np.clip(((X - ax) * vx + (Y - ay) * vy) / L2, 0, 1)
        px, py = ax + t * vx, ay + t * vy
        d = np.minimum(d, np.hypot(X - px, Y - py))
    return d


def height_field(X, Y):
    h = value_noise(X, Y, 70, 1, 2.6) + value_noise(X, Y, 23, 2, 1.0) + value_noise(X, Y, 8, 3, 0.25)
    # gentle rise toward the mine, then the north cliff
    h += 4.0 * smooth(170, 226, Y)
    keep = smooth(6, 14, np.abs(X - MINE_X))       # the cliff stays straight at the mine notch
    off = value_noise(X, Y * 0 + 230, 17, 11, 3.5) * keep
    hgt = 26.0 + value_noise(X, Y * 0 + 230, 23, 12, 7.0) * keep
    h += hgt * smooth(230.5 + off, 234.0 + off, Y)
    h += value_noise(X, Y, 3.5, 13, 0.9) * smooth(229, 233, Y)     # rocky detail on the cliff face
    # boundary cliffs
    h += 24.0 * smooth(134, 141, np.abs(X)) + 24.0 * smooth(-46, -53, Y)
    # bunker hill (mesa above the underground bunker and the exit corridor)
    r = np.sqrt((X / 45.0) ** 2 + ((Y + 5) / 50.0) ** 2)
    h += 9.0 * smooth(1.0, 0.75, r)
    # the Shelf: raised west plateau (a 6.5 m escarpment: climbable shortcut, the trail goes around)
    shelf = smooth(151, 155, Y) * smooth(212, 207, Y) * smooth(-6, -26, X)
    h += 6.5 * shelf
    # river channel + banks that never dip under the water line
    dr = np.abs(Y - river_y(X))
    ford = smooth(12, 4, np.abs(X - 70))           # shallow ford in the east
    bed = -2.3 + 1.6 * ford
    h = np.where((dr > 3.5) & (dr < 14), np.maximum(h, -0.2), h)
    h = h * (1 - smooth(6.5, 3.0, dr)) + bed * smooth(6.5, 3.0, dr)
    # trail: slight depression
    dt = dist_polyline(X, Y, TRAIL)
    h -= 0.18 * smooth(2.5, 0.8, dt)
    # flattened sites
    for (cx, cy), rad, target in [((0, 57), 10, 0.0), (CAMP_A, 8, None), (CLEARING, 18, None), (CABIN, 10, None), ((MINE_X, 222), 14, MINE_Z)]:
        d = np.hypot(X - cx, Y - cy)
        m = smooth(rad, rad * 0.55, d)
        tz = target if target is not None else float(height_field_point(cx, cy))
        h = h * (1 - m) + tz * m
    # bunker portal cut: flat floor at 0 between retaining walls
    cut = smooth(5.9, 5.3, np.abs(X)) * smooth(37.5, 38.6, Y) * smooth(64, 57, Y)
    h = h * (1 - cut)
    # mine entrance notch in the cliff
    notch = smooth(3.6, 3.1, np.abs(X - MINE_X)) * smooth(224, 226, Y) * smooth(236.5, 235.4, Y)
    h = h * (1 - notch) + MINE_Z * notch
    return h, dr, dt, shelf


_point_cache = {}
def height_field_point(x, y):
    """Height before site flattening (used to pick each site's target level)."""
    key = (x, y)
    if key not in _point_cache:
        X = np.array([[x]], float); Y = np.array([[y]], float)
        h = value_noise(X, Y, 70, 1, 2.6) + value_noise(X, Y, 23, 2, 1.0) + 4.0 * smooth(170, 226, Y)
        shelf = smooth(151, 155, Y) * smooth(212, 207, Y) * smooth(-6, -26, X)
        _point_cache[key] = (h + 6.5 * shelf)[0, 0]
    return _point_cache[key]


class Terrain:
    def __init__(self):
        xs = np.arange(X0, X1 + 0.01, STEP)
        ys = np.arange(Y0, Y1 + 0.01, STEP)
        self.xs, self.ys = xs, ys
        self.X, self.Y = np.meshgrid(xs, ys)
        self.H, self.dr, self.dt, self.shelf = height_field(self.X, self.Y)

    def h(self, x, y):
        fx = (x - X0) / STEP; fy = (y - Y0) / STEP
        ix = int(np.clip(math.floor(fx), 0, len(self.xs) - 2)); iy = int(np.clip(math.floor(fy), 0, len(self.ys) - 2))
        tx, ty = fx - ix, fy - iy
        H = self.H
        return float((H[iy, ix] * (1 - tx) + H[iy, ix + 1] * tx) * (1 - ty) + (H[iy + 1, ix] * (1 - tx) + H[iy + 1, ix + 1] * tx) * ty)

    def slope(self, x, y):
        e = 1.0
        gx = (self.h(x + e, y) - self.h(x - e, y)) / (2 * e)
        gy = (self.h(x, y + e) - self.h(x, y - e)) / (2 * e)
        return math.degrees(math.atan(math.hypot(gx, gy)))

    def colors(self):
        H = self.H
        gy, gx = np.gradient(H, STEP)
        steep = np.degrees(np.arctan(np.hypot(gx, gy)))
        R = np.clip(smooth(2.6, 0.6, self.dt) + smooth(7, 3.5, self.dr) * 0.8, 0, 1)            # mud
        low = H - (value_noise(self.X, self.Y, 70, 1, 2.6) + 4.0 * smooth(170, 226, self.Y))
        G = np.clip(smooth(10, 5, self.dr) * 0.6 + smooth(0.2, -1.0, low) * 0.7 + value_noise(self.X, self.Y, 12, 9, 0.5) + 0.15, 0, 1)
        B = np.clip(smooth(32, 48, steep), 0, 1)
        G = G * (1 - R)
        return R, G, B

    def build(self, coll, chunks=8):
        R, G, B = self.colors()
        nx, ny = len(self.xs), len(self.ys)
        objs = []
        cx = np.linspace(0, nx - 1, chunks + 1).astype(int)
        cy = np.linspace(0, ny - 1, chunks + 1).astype(int)
        for j in range(chunks):
            for i in range(chunks):
                ia, ib, ja, jb = cx[i], cx[i + 1], cy[j], cy[j + 1]
                verts, faces, cols = [], [], []
                w = ib - ia + 1
                for yy in range(ja, jb + 1):
                    for xx in range(ia, ib + 1):
                        verts.append((self.xs[xx], self.ys[yy], self.H[yy, xx]))
                        cols.append((R[yy, xx], G[yy, xx], B[yy, xx], 1.0))
                for yy in range(jb - ja):
                    for xx in range(ib - ia):
                        a = yy * w + xx
                        b, c, d = a + 1, a + w + 1, a + w
                        # skip the faces that would cover the mine tunnel mouth
                        cxm = (verts[a][0] + verts[c][0]) / 2; cym = (verts[a][1] + verts[c][1]) / 2
                        czm = (verts[a][2] + verts[c][2]) / 2
                        if abs(cxm - MINE_X) < 3.4 and 234.0 < cym < 239.5 and czm < 10.5:
                            continue
                        faces.append((a, b, c, d))
                me = bpy.data.meshes.new(f'Terrain_{i}_{j}')
                me.from_pydata(verts, [], faces)
                me.update()
                uv = me.uv_layers.new(name='UVMap')
                for poly in me.polygons:
                    for li in poly.loop_indices:
                        v = me.vertices[me.loops[li].vertex_index].co
                        uv.data[li].uv = (v.x / 3.0, v.y / 3.0)
                ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
                for k, c in enumerate(cols):
                    ca.data[k].color = c
                me.materials.append(material('MNF_Terrain'))
                for p in me.polygons:
                    p.use_smooth = True
                ob = bpy.data.objects.new(f'Terrain_{i}_{j}', me)
                coll.objects.link(ob)
                objs.append(ob)
        return objs


def build(out_dir):
    reset_scene()
    geo_c = collection('ForestGeometry')
    mk_c = collection('ForestMarkers')
    T = Terrain()
    T.build(geo_c)
    M = lambda n, loc, fwd=(0, -1, 0), **k: marker(n, loc, fwd, mk_c, **k)
    S, N, E, W = (0, -1, 0), (0, 1, 0), (1, 0, 0), (-1, 0, 0)
    rot = lambda deg: fwd_from_yaw_deg(deg)

    # ---------------- concrete cut at the bunker portal + water + invisible boundary
    g = Geo(tile=2.0)
    for side in (-1, 1):
        x0 = 5.3 if side > 0 else -5.9
        for k in range(10):
            ya, yb = 38.5 + k * 2.0, 40.5 + k * 2.0
            top = max(T.h(side * 6.5, ya), T.h(side * 6.5, yb)) + 0.35
            if top < 0.5:
                continue
            g.box((x0, ya, -0.5), (x0 + 0.6, yb, top), 'MNF_ConcreteWall')
    g.box((-5.3, 38.5, -0.3), (5.3, 49.0, 0.02), 'MNF_ConcreteFloor', tile=2.5)
    g.build('PortalCut', geo_c)

    w = Geo(tile=3.0)
    xs = np.arange(-138, 139, 3.0)
    for a, b in zip(xs[:-1], xs[1:]):
        ya, yb = float(river_y(a)), float(river_y(b))
        z = -1.0 + (0.9 if abs((a + b) / 2 - 70) < 8 else 0.0)
        w.quad((a, ya - 4.2, z), (b, yb - 4.2, z), (b, yb + 4.2, z), (a, ya + 4.2, z), 'MNF_Water')
    w.build('WATER_River', geo_c)

    bnd = Geo()
    bnd.box((-150, -60, -20), (-144, 240, 70), 'MNF_RockDry_Tri')
    bnd.box((144, -60, -20), (150, 240, 70), 'MNF_RockDry_Tri')
    bnd.box((-150, -60, -20), (150, -54, 70), 'MNF_RockDry_Tri')
    bnd.box((-150, 238, 30), (150, 244, 80), 'MNF_RockDry_Tri')
    bnd.build('COLONLY_NOCLIMB_Bounds', geo_c)

    zone_box('ZONE_Forest_0', (-150, -60, -30), (150, 240, 90), geo_c)

    # ---------------- scatter (exclusion-aware)
    def excluded(x, y, margin=0.0):
        if abs(x) > 136 - margin or y < -44 + margin or y > 229 - margin:
            return True
        if abs(y - float(river_y(x))) < 7.5 + margin:
            return True
        d_trail = float(dist_polyline(np.array([[x]]), np.array([[y]]), TRAIL)[0, 0])
        if d_trail < 3.8 + margin:
            return True
        for (cx, cy), r in [((0, 54), 12), (CAMP_A, 8), (CLEARING, 16), (CABIN, 9), ((MINE_X, 222), 15), (GROTTO, 7), ((0, 0), 0)]:
            if math.hypot(x - cx, y - cy) < r + margin:
                return True
        if abs(x) < 7 and 30 < y < 64:
            return True
        return False

    def place(name, x, y, sink=0.12, scale=(0.85, 1.25), yaw=None, slope_max=30):
        if T.slope(x, y) > slope_max:
            return False
        s = RNG.uniform(*scale)
        M(f'MK_PROP_{name}', (x, y, T.h(x, y) - sink), rot(yaw if yaw is not None else RNG.uniform(0, 360)), scale=s)
        return True

    counts = {}
    cell = 8.0
    for gy in np.arange(-44, 229, cell):
        for gx in np.arange(-136, 136, cell):
            x, y = gx + RNG.uniform(0.5, cell - 0.5), gy + RNG.uniform(0.5, cell - 0.5)
            if excluded(x, y):
                continue
            d_trail = float(dist_polyline(np.array([[x]]), np.array([[y]]), TRAIL)[0, 0])
            p = 0.78 if d_trail > 25 else 0.5
            if RNG.random() > p:
                continue
            near_water = abs(y - float(river_y(x))) < 20
            dead = RNG.random() < (0.55 if near_water or math.hypot(x - CLEARING[0], y - CLEARING[1]) < 35 else 0.27)
            kind = 'Tree_Dead_' + RNG.choice('ABC') if dead else 'Tree_Pine_' + RNG.choice('ABC')
            if place(kind, x, y, sink=0.2):
                counts[kind[:9]] = counts.get(kind[:9], 0) + 1

    def scatter(name, n, scale=(0.8, 1.3), near=None, radius=None, sink=0.05, margin=0.0):
        k = 0
        tries = 0
        while k < n and tries < n * 30:
            tries += 1
            if near:
                a = RNG.uniform(0, 2 * math.pi); r = RNG.uniform(0, radius)
                x, y = near[0] + math.cos(a) * r, near[1] + math.sin(a) * r
                if abs(x) > 136 or y < -44 or y > 229 or abs(y - float(river_y(x))) < 4:
                    continue
            else:
                x, y = RNG.uniform(-134, 134), RNG.uniform(-42, 226)
                if excluded(x, y, margin):
                    continue
            if place(name, x, y, sink=sink, scale=scale):
                k += 1
        counts[name] = counts.get(name, 0) + k

    scatter('Bush_A', 170); scatter('Bush_B', 150)
    scatter('Fern', 320, scale=(0.8, 1.6)); scatter('GrassTuft', 160, scale=(0.8, 1.5))
    scatter('GrassTuft', 90, near=CLEARING, radius=15, scale=(0.9, 1.6))
    scatter('MushroomCluster', 45)
    for r in 'ABCDE':
        scatter('Rock_' + r, 28, scale=(0.7, 1.5), sink=0.15)
    scatter('Boulder_Large', 9, scale=(0.8, 1.3), sink=0.4, margin=4)
    scatter('Stump', 30); scatter('Log', 30)
    # banks: ferns and grass along the river
    for k in range(70):
        x = RNG.uniform(-130, 130)
        side = RNG.choice((-1, 1))
        y = float(river_y(x)) + side * RNG.uniform(5.5, 9)
        place(RNG.choice(['Fern', 'GrassTuft', 'Rock_A', 'Rock_B']), x, y, sink=0.05)

    # ---------------- break up the north cliff with rock chunks along its base
    for x in np.arange(-128, 130, 11.0):
        if abs(x - MINE_X) < 10:
            continue
        xx = float(x + RNG.uniform(-3, 3))
        yy = 229.0 + RNG.uniform(-1.0, 1.5)
        M('MK_PROP_CliffChunk_' + RNG.choice('AB'), (xx, yy, T.h(xx, yy) - 0.6), rot(RNG.uniform(160, 200)), scale=RNG.uniform(0.9, 1.5))

    # ---------------- portal approach
    M('MK_PROP_WarningBoard', (-7.5, 60, T.h(-7.5, 60) - 0.1), S)
    M('MK_PROP_SignPost', (4.2, 64, T.h(4.2, 64) - 0.1), S)
    for k, x in enumerate((-16, -13.4, -10.8)):
        M('MK_PROP_Fence_Section' if k != 1 else 'MK_PROP_Fence_Broken', (x, 58, T.h(x, 58) - 0.1), S)
    M('MK_SIGN_12_0.55_0.7', (-13.4, 57.86, T.h(-13.4, 58) + 1.0), S)       # missing poster pinned to the fence
    M('MK_PROP_Barrel', (4.5, 49, 0.0), W)
    M('MK_PROP_Crate_Mine', (-4.2, 48.5, 0.0), E)

    # ---------------- trail dressing: posts with numbered markers, fences, carts
    for k, (x, y) in enumerate(TRAIL[1:-1]):
        if k % 2 == 0:
            sx, sy = x + 3.2, y
            M('MK_PROP_SignPost', (sx, sy, T.h(sx, sy) - 0.1), rot(RNG.uniform(-20, 20)))
    M('MK_PROP_Minecart_Abandoned', (-14, 92, T.h(-14, 92) - 0.1), rot(70))
    M('MK_PROP_Fence_Broken', (6, 130, T.h(6, 130) - 0.1), rot(30))
    M('MK_SIGN_15_0.55_0.55', (1.4, 76, T.h(1.4, 76) + 1.6), S)

    # ---------------- river crossings
    bx = 2.0
    M('MK_PROP_Bridge_Broken', (bx, float(river_y(bx)), -0.15), S)
    lx = -40.0
    M('MK_PROP_FallenTree', (lx, float(river_y(lx)), 0.1), E)
    M('MK_ITEM_miner_tag', (bx + 0.4, float(river_y(bx)) - 6.5, T.h(bx, float(river_y(bx)) - 6.5) + 0.05), S)
    for x in (-90, -25, 45, 110):
        M('MK_SOUND_stream_loop', (x, float(river_y(x)), -0.8))
    for x in (-60, 20, 85):
        M('MK_SOUND_frogs_loop', (x, float(river_y(x)) + 7, T.h(x, float(river_y(x)) + 7) + 0.3))

    # ---------------- Camp A
    cx, cy = CAMP_A
    cz = T.h(cx, cy)
    M('MK_PROP_Tent', (cx - 2.5, cy + 2.0, cz - 0.05), rot(200))
    M('MK_PROP_Campfire', (cx + 0.5, cy - 0.5, cz - 0.05))
    M('MK_PROP_Crate_Mine', (cx + 2.8, cy + 2.2, cz), rot(15))
    M('MK_PROP_Barrel_Mine', (cx + 3.6, cy + 1.0, cz), rot(0))
    M('MK_PROP_Log', (cx + 0.6, cy - 2.4, cz - 0.05), rot(80))
    M('MK_PROP_Log', (cx - 1.6, cy - 1.2, cz - 0.05), rot(20))
    M('MK_LORE_lore_rabbits', (cx + 2.8, cy + 2.2, cz + 0.62), S)
    M('MK_ITEM_food_can', (cx + 2.6, cy + 2.0, cz + 0.65), S)
    M('MK_PROP_WarningBoard', (cx - 5, cy - 4, T.h(cx - 5, cy - 4) - 0.1), rot(160))

    # ---------------- the Clearing (rabbits — and maybe not only rabbits)
    cx, cy = CLEARING
    M('MK_WILD_Rabbit_5_14_FK', (cx, cy, T.h(cx, cy)))
    M('MK_FALSEKIN', (cx + 6, cy + 5, T.h(cx + 6, cy + 5)))
    M('MK_FKNEST', (cx - 13, cy + 12, T.h(cx - 13, cy + 12) - 0.05))
    for a in range(4):
        ang = a * 1.7 + 0.4
        x, y = cx + math.cos(ang) * 15, cy + math.sin(ang) * 15
        M('MK_PROP_Burrow', (x, y, T.h(x, y) - 0.1), rot(RNG.uniform(0, 360)))
    # other wildlife areas
    M('MK_WILD_Rabbit_3_12', (-72, 88, T.h(-72, 88)))
    for x, y in ((-64, 80), (-80, 95)):
        M('MK_PROP_Burrow', (x, y, T.h(x, y) - 0.1))
    M('MK_WILD_Rabbit_4_12_FK', (62, 60, T.h(62, 60)))
    M('MK_FALSEKIN', (66, 64, T.h(66, 64)))
    M('MK_FKNEST', (78, 72, T.h(78, 72) - 0.05))
    M('MK_PROP_Burrow', (55, 52, T.h(55, 52) - 0.1))
    M('MK_WILD_Boar_2_16', (-95, 212, T.h(-95, 212)))
    M('MK_WILD_Boar_2_16', (105, 150, T.h(105, 150)))
    M('MK_WILD_Gloomrat_3_8', (CABIN[0] + 6, CABIN[1] - 6, T.h(CABIN[0] + 6, CABIN[1] - 6)))
    # cover spots (undergrowth the Falsekin retreats into)
    for k in range(28):
        x, y = RNG.uniform(-120, 120), RNG.uniform(20, 225)
        if excluded(x, y):
            continue
        M('MK_COVER', (x, y, T.h(x, y)))
        place('Bush_A', x + 0.5, y, sink=0.05)

    # ---------------- the Shelf: ruined cabin + watchtower
    cx, cy = CABIN
    cz = T.h(cx, cy)
    M('MK_PROP_Cabin_Ruin', (cx, cy, cz - 0.05), rot(15))
    M('MK_PROP_Watchtower', (cx + 12, cy + 11, T.h(cx + 12, cy + 11) - 0.1), rot(200))
    M('MK_LIGHT_Camp', (cx + 0.3, cy + 0.2, cz + 3.0))
    M('MK_LORE_lore_tall', (cx + 1.0, cy - 0.6, cz + 0.05), S)
    M('MK_LORE_lore_children', (cx - 1.2, cy + 1.0, cz + 0.05), S)
    M('MK_ITEM_glowstick', (cx + 0.8, cy + 1.4, cz + 0.05), S)
    M('MK_ITEM_medkit', (cx + 12.3, cy + 11.3, T.h(cx + 12, cy + 11) + 6.0), S)  # reward on the tower platform
    # a scramble route up the escarpment near the trail (rocks as steps)
    for k, (x, y) in enumerate([(-14, 150), (-15.5, 152), (-17, 154)]):
        M('MK_PROP_Rock_E', (x, y, T.h(x, y) - 0.3 + k * 0.6), rot(k * 50), scale=1.2)

    # ---------------- grotto (hidden resource pocket formed by cliff chunks)
    gx, gy = GROTTO
    gz = T.h(gx, gy)
    M('MK_PROP_CliffChunk_A', (gx - 4.5, gy + 1.0, gz - 0.5), rot(80))
    M('MK_PROP_CliffChunk_B', (gx + 4.5, gy + 1.5, gz - 0.5), rot(-100))
    M('MK_PROP_Boulder_Large', (gx, gy + 5.5, gz - 0.4), rot(10), scale=1.3)
    M('MK_PROP_Boulder_Large', (gx - 6.5, gy - 3.0, gz - 0.4), rot(140))
    M('MK_ORE_Shallow', (gx + 0.5, gy + 2.0, gz - 0.05), S)
    M('MK_ORE_Mid', (gx - 1.5, gy + 1.0, gz - 0.05), rot(40))
    M('MK_LORE_lore_borer', (gx + 1.2, gy - 0.5, gz + 0.05), S)

    # ---------------- landmarks: gnarled giants
    for (x, y) in ((-20, 146), (58, 108), (-100, 60), (95, 210)):
        M('MK_PROP_Tree_Gnarled', (x, y, T.h(x, y) - 0.2), rot(RNG.uniform(0, 360)), scale=1.25)

    # ---------------- mine apron
    mz = MINE_Z
    M('MK_PROP_MineEntrance', (MINE_X, 235.3, mz), S)
    for y in np.arange(214, 235, 2.0):
        M('MK_PROP_Rail_Straight', (MINE_X + 0.6, float(y), T.h(MINE_X, float(y)) - 0.02), N)
    M('MK_PROP_Minecart_Abandoned', (MINE_X - 5, 222, T.h(MINE_X - 5, 222) - 0.05), rot(110))
    M('MK_PROP_ToolPile', (MINE_X + 5, 226, mz), rot(200))
    M('MK_PROP_Crate_Mine', (MINE_X + 4.5, 229.5, mz), rot(10))
    M('MK_PROP_WarningBoard', (MINE_X - 6, 219, T.h(MINE_X - 6, 219) - 0.1), rot(20))
    M('MK_SIGN_3_0.7_0.5', (MINE_X - 6.1, 218.85, T.h(MINE_X - 6, 219) + 1.6), rot(20))
    for k in range(5):
        x = MINE_X - 16 + k * 2.65
        M('MK_PROP_Fence_Section' if k % 3 else 'MK_PROP_Fence_Broken', (x, 214, T.h(x, 214) - 0.1), S)
    M('MK_LIGHT_MineLampDim', (MINE_X + 2.6, 234.6, mz + 2.8), S)

    # ---------------- Hollowback territory and points of interest
    M('MK_HB_SPAWN', (-34, 132, T.h(-34, 132)))
    for (x, y) in [(CAMP_A[0] + 6, CAMP_A[1] + 4), (CLEARING[0] - 18, CLEARING[1]), (CLEARING[0] + 16, CLEARING[1] + 8), (-20, 146), (58, 108),
                   (-45, 100), (-10, 128), (40, 118), (CABIN[0] + 8, CABIN[1] - 14), (gx - 8, gy - 6), (-2, 196), (48, 168), (-70, 140),
                   (70, 140), (16, 80), (-30, 70), (34, 200)]:
        if not excluded(x, y) or True:
            M('MK_HB_POINT', (x, y, T.h(x, y)))

    # ---------------- atmosphere: fog banks, sounds, silhouettes
    for (x, y) in [(0, 112), (-60, 115), (60, 110), (10, 170), (-40, 60), (40, 80), (-80, 200), (80, 190), (25, 215), (-100, 140), (100, 120), (0, 140), (-30, 175), (60, 30)]:
        M('MK_FOGBANK', (x, y, T.h(x, y) + 2.0))
    for (x, y) in [(-45, 140), (55, 176), (-22, 206), (92, 122), (-95, 100)]:
        M('MK_EVENT_PeripheralSilhouette', (x, y, T.h(x, y)), rot(RNG.uniform(0, 360)))
    for (x, y) in [(-110, 30), (110, 60), (-60, 220), (60, 210), (0, 160)]:
        M('MK_SOUND_leaves_rustle', (x, y, T.h(x, y) + 3))

    M('MK_TELEPORT_ForestCentre', (2, 100, T.h(2, 100) + 0.1), N)
    M('MK_TELEPORT_Clearing', (CLEARING[0], CLEARING[1] - 14, T.h(CLEARING[0], CLEARING[1] - 14) + 0.1), N)
    M('MK_TELEPORT_MineApron', (MINE_X, 220, T.h(MINE_X, 220) + 0.1), N)

    objs = [o for o in bpy.data.objects if o.type in ('MESH', 'EMPTY')]
    export_fbx(os.path.join(out_dir, 'Forest.fbx'), objs)
    print('forest counts', counts)
    return T, objs


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    root = argv[0] if argv else os.path.join(os.path.dirname(__file__), '..', '..', '..')
    out = os.path.join(root, 'Assets', 'MonkeyNoFear', 'Art', 'Models', 'Levels')
    T, objs = build(out)
    prev = os.path.join(root, 'Docs', 'previews', 'levels')
    os.makedirs(prev, exist_ok=True)
    for o in bpy.data.objects:
        if o.name.startswith('COLONLY_') or o.name.startswith('ZONE_'):
            o.hide_render = True
    load_kits(os.path.join(root, 'Assets', 'MonkeyNoFear', 'Art', 'Models', 'Props'))
    dress_preview([o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.startswith('MK_')])
    os.makedirs(os.path.join(root, 'SourceArt', 'Levels'), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(root, 'SourceArt', 'Levels', 'Forest_preview.blend'))
    render_preview(os.path.join(prev, 'forest_overview.png'), (0, -110, 170), (0, 110, 0), lens=22, samples=10)
    views = {'portal': ((8, 75, 4.0), (0, 44, 1.5)), 'bridge': ((-6, 96, 2.2), (3, 115, 0.5)),
             'clearing': ((-8, 150, 2.0), (12, 172, 0.5)), 'mine_apron': ((18, 205, 6.5), (25, 236, 5.0)),
             'camp': ((28, 128, 2.2), (35, 141, 0.5)), 'cabin': ((-48, 160, 10.0), (-60, 177, 7.0))}
    for name, (cam, tgt) in views.items():
        cz = T.h(cam[0], cam[1]) + cam[2]
        tz = T.h(tgt[0], tgt[1]) + tgt[2]
        render_preview(os.path.join(prev, f'forest_{name}.png'), (cam[0], cam[1], cz), (tgt[0], tgt[1], tz), lens=20, samples=10, res=(800, 450))
    print('forest objects', len(objs))
