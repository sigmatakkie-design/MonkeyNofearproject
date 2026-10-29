"""kitB_shared - geometry shared by Kit_Forest and Kit_Mine (artist B): planks, bolts, plates, rail track,
mine timber support sets, minecart, caged lamp, rubble.  All functions add into a propkit_b_helpers.MB."""
import math
from mathutils import Vector, Matrix, Quaternion
import propkit_b_helpers as H
from propkit_b_helpers import MB, M, add_box, add_beam, add_cyl, add_tube, rng, frame_from

PLANK_NB = {'MNF_WoodPlanks': 6, 'MNF_WoodCrate': 4}
PLANK_TILE = {'MNF_WoodPlanks': 2.0, 'MNF_WoodCrate': 1.0, 'MNF_WoodBeam': 2.0, 'MNF_WoodRotten': 1.5}
Z = Vector((0, 0, 1))
GAUGE = 0.6          # narrow gauge (rail centre to rail centre)
RAIL_TOP = 0.19      # rail head top above the sleeper bottom (track pivot)


def plank(mb, p0, p1, w, t, mat='MNF_WoodPlanks', up=(0, 0, 1), seed=0, warp=0.0, jag0=0.0, jag1=0.0, rough=0.0,
          segs=None):
    """A single board.  Plank-atlas materials get their visible face mapped onto one board row."""
    r = rng(seed)
    nb = PLANK_NB.get(mat)
    add_beam(mb, p0, p1, w, t, mat, up=up, chamfer=min(0.008, t * 0.3), segs=segs or (2 if warp else 1),
             warp=warp, jag0=jag0, jag1=jag1, seed=seed, tile=PLANK_TILE.get(mat, 2.0),
             board=(r.randrange(nb), nb) if nb else None, rough=rough)


def timber(mb, p0, p1, w, h, mat='MNF_WoodBeam', up=(0, 0, 1), seed=0, jag0=0.0, jag1=0.0, warp=0.0, rough=0.012,
           chamfer=0.025, segs=None):
    add_beam(mb, p0, p1, w, h, mat, up=up, chamfer=chamfer, segs=segs or (3 if warp else 1), warp=warp, jag0=jag0,
             jag1=jag1, seed=seed, tile=2.0, rough=rough)


def obox(mb, center, normal, up, size, mat, bevel=0.0, tile=1.0, jitter=0.0, seed=0):
    """Box whose local Y axis = normal, Z = up.  size = (along side, along normal, along up)."""
    F = frame_from(normal, up).to_4x4()
    F.translation = Vector(center)
    add_box(mb, size, F, mat, bevel=bevel, tile=tile, jitter=jitter, seed=seed)


def bolt(mb, pos, normal, r=0.016, h=0.014, mat='MNF_MetalRusted', segs=6):
    n = Vector(normal).normalized()
    add_cyl(mb, Vector(pos), Vector(pos) + n * h, r, r * 0.85, segs, mat, cap0=False, cap1=True, tile=0.3,
            smooth=False)


def sweep_profile(mb, pts, prof, mat, tile=1.5, top_idx=None, top_mat=None, cap_pieces=None, up=Z):
    """Extrude a closed 2D profile (x across, y up) along a polyline.  cap_pieces: list of index lists
    (convex pieces) used to cap both ends (handles concave profiles)."""
    pts = [Vector(p) for p in pts]
    n = len(prof)
    per = [0.0]
    for i in range(n):
        per.append(per[-1] + (Vector(prof[(i + 1) % n]) - Vector(prof[i])).length)
    arc = [0.0]
    for i in range(1, len(pts)):
        arc.append(arc[-1] + (pts[i] - pts[i - 1]).length)
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = t.cross(up).normalized()
        u2 = side.cross(t).normalized()
        rings.append([mb.av(p + side * x + u2 * y) for (x, y) in prof])
    for i in range(len(pts) - 1):
        A, B = rings[i], rings[i + 1]
        for j in range(n):
            jn = (j + 1) % n
            m = top_mat if (top_mat and j == top_idx) else mat
            mb.face([A[j], A[jn], B[jn], B[j]],
                    [(arc[i] / tile, per[j] / tile), (arc[i] / tile, per[j + 1] / tile),
                     (arc[i + 1] / tile, per[j + 1] / tile), (arc[i + 1] / tile, per[j] / tile)], m)
    if cap_pieces:
        for ring, rev in ((rings[0], False), (rings[-1], True)):
            for piece in cap_pieces:
                ids = [ring[k] for k in piece]
                uvs = [(prof[k][0] / tile, prof[k][1] / tile) for k in piece]
                if not rev:
                    ids = ids[::-1]; uvs = uvs[::-1]
                mb.face(ids, uvs, mat)


# rail: flat-bottom profile, 90 mm tall
_FW, _FT, _WW, _HB, _HW, _HH = 0.037, 0.011, 0.007, 0.064, 0.022, 0.09
RAIL_PROF = [(-_FW, 0), (_FW, 0), (_FW, _FT), (_WW, _FT), (_WW, _HB), (_HW, _HB), (_HW, _HH), (-_HW, _HH),
             (-_HW, _HB), (-_WW, _HB), (-_WW, _FT), (-_FW, _FT)]
RAIL_CAPS = [[0, 1, 2, 3, 10, 11], [10, 3, 4, 9], [9, 4, 5, 6, 7, 8]]


def track(mb, path, length, seed=0, spacing=0.5, first=0.25, nseg=1, plates=True, sleeper_mat='MNF_WoodBeam',
          skip=(), broken=(), extra_jitter=1.0, z0=0.0):
    """Narrow-gauge track along path(s)->(pos, tangent) for s in [0, length].  Sleepers 0.1 m tall at z0,
    rails on top (rail head top at z0 + RAIL_TOP).  Rails MNF_MetalRusted with a worn MNF_MetalBare head."""
    r = rng(seed)
    s = first
    k = 0
    while s < length - 0.05:
        if k not in skip:
            p, t = path(s)
            side = t.cross(Z).normalized()
            yaw = math.radians(r.uniform(-3, 3) * extra_jitter)
            sd = Quaternion(Z, yaw) @ side
            off = t * r.uniform(-0.03, 0.03) * extra_jitter
            c = p + off + Vector((0, 0, z0 + 0.05))
            jag = (0.08, 0.0) if k in broken else (r.uniform(0, 0.03), r.uniform(0, 0.03))
            timber(mb, c - sd * 0.56, c + sd * (0.56 if k not in broken else 0.32), 0.16, 0.1, sleeper_mat,
                   seed=seed * 31 + k, jag0=jag[0], jag1=jag[1] if k not in broken else 0.12, rough=0.006,
                   chamfer=0.012)
            if plates:
                for sg in (-1, 1):
                    pc = p + side * (sg * GAUGE / 2) + Vector((0, 0, z0 + 0.105))
                    obox(mb, pc, side, Z, (0.12, 0.15, 0.01), 'MNF_MetalRusted')
                    for sp in (-1, 1):
                        add_box(mb, (0.016, 0.016, 0.03),
                                Matrix.Translation(pc + side * (sp * 0.05) + t * (0.03 * sp) + Vector((0, 0, 0.01))),
                                'MNF_MetalRusted')
        s += spacing
        k += 1
    for sg in (-1, 1):
        pts = []
        for i in range(nseg + 1):
            p, t = path(length * i / nseg)
            side = t.cross(Z).normalized()
            pts.append(p + side * (sg * GAUGE / 2) + Vector((0, 0, z0 + 0.1)))
        sweep_profile(mb, pts, RAIL_PROF, 'MNF_MetalRusted', tile=1.5, top_idx=6, top_mat='MNF_MetalBare',
                      cap_pieces=RAIL_CAPS)


def straight_path(origin=(0, 0, 0), direction=(0, -1, 0)):
    o = Vector(origin); d = Vector(direction).normalized()
    return lambda s: (o + d * s, d)


def arc_path(radius, sign=1, origin=(0, 0, 0)):
    """Starts at origin heading -Y, curving towards +X (sign=1)."""
    o = Vector(origin)
    c = o + Vector((radius * sign, 0, 0))

    def fn(s):
        a = s / radius
        p = c + Vector((-radius * sign * math.cos(a), -radius * math.sin(a), 0))
        t = Vector((sign * math.sin(a), -math.cos(a), 0))
        return p, t
    return fn


# -----------------------------------------------------------------------------------------------
def support_set(mb, y=0.0, width=3.5, height=3.2, post=0.26, header=0.3, seed=0, cracked=True, lagging=True,
                brackets=True, lag_depth=0.9, side_lag=True, wedges=True):
    """Three-piece mine timber set: battered posts + header (+ iron brackets, wedges, lagging)."""
    r = rng(seed)
    hw = width / 2
    for sg in (-1, 1):
        x0 = sg * (hw + post / 2 + 0.06)
        x1 = sg * (hw + post / 2)
        timber(mb, (x0, y + r.uniform(-0.02, 0.02), 0.0), (x1, y, height), post, post, up=(0, 1, 0),
               seed=seed + sg, rough=0.01, jag0=0.0)
        # foot block
        add_box(mb, (post + 0.14, post + 0.1, 0.07), Matrix.Translation((x0, y, 0.035)), 'MNF_WoodBeam', bevel=0.01,
                tile=2.0, jitter=0.006, seed=seed + 3)
    hl = hw + post + 0.22
    if cracked:
        sag = r.uniform(0.025, 0.045)
        xm = r.uniform(-0.4, 0.4)
        timber(mb, (-hl, y, height + header / 2), (xm, y, height + header / 2 - sag), post + 0.04, header,
               up=(0, 0, 1), seed=seed + 5, jag1=0.07)
        timber(mb, (xm - 0.04, y, height + header / 2 - sag), (hl, y, height + header / 2), post + 0.04, header,
               up=(0, 0, 1), seed=seed + 6, jag0=0.07)
    else:
        timber(mb, (-hl, y, height + header / 2), (hl, y, height + header / 2), post + 0.04, header, seed=seed + 5)
    if brackets:
        for sg in (-1, 1):
            x = sg * (hw + post / 2)
            for face in (-1, 1):
                fy = y + face * (post / 2 + 0.006)
                obox(mb, (x, fy, height - 0.12), Vector((0, face, 0)), Z, (post + 0.02, 0.01, 0.26), 'MNF_MetalRusted',
                     bevel=0.003)
                obox(mb, (x, fy, height + header / 2), Vector((0, face, 0)), Z, (0.4, 0.01, header * 0.7),
                     'MNF_MetalRusted', bevel=0.003)
                if face == -1:
                    for bz in (height - 0.18, height - 0.05, height + header * 0.5):
                        bolt(mb, (x, fy - 0.005, bz), (0, -1, 0))
    if wedges:
        for k in range(3):
            x = r.uniform(-hw, hw)
            add_box(mb, (0.22, 0.18, 0.12), M((x, y, height + header + 0.06), (0, r.uniform(-8, 8), r.uniform(-20, 20))),
                    'MNF_WoodBeam', bevel=0.01, tile=2.0, jitter=0.01, seed=seed + 20 + k)
    if lagging:
        n = int(width / 0.24) + 2
        for k in range(n):
            if r.random() < 0.12:
                continue
            x = -hw - 0.1 + (width + 0.2) * (k + 0.5) / n
            z = height + header + 0.01 + r.uniform(0, 0.02)
            plank(mb, (x, y - lag_depth / 2 + r.uniform(-0.05, 0.05), z), (x, y + lag_depth / 2, z + r.uniform(-0.02, 0.02)),
                  0.2, 0.035, 'MNF_WoodPlanks', seed=seed * 7 + k, jag0=r.uniform(0, 0.05))
    if side_lag:
        for sg in (-1, 1):
            x = sg * (hw + post + 0.03)
            for k in range(6):
                if r.random() < 0.25:
                    continue
                z = 0.3 + k * 0.48
                plank(mb, (x, y - lag_depth / 2, z), (x, y + lag_depth / 2, z + r.uniform(-0.03, 0.03)), 0.22, 0.035,
                      'MNF_WoodPlanks', up=(sg, 0, 0), seed=seed * 11 + k + sg * 50, jag1=r.uniform(0, 0.08))


# -----------------------------------------------------------------------------------------------
def minecart(mb, seed=0, mm=None, ore=True, missing_wheel=None):
    """Rusty narrow-gauge ore cart, long axis along Y.  Local pivot: wheel running surface at z=0."""
    r = rng(seed)
    sub = MB()
    MAT = 'MNF_MetalRusted'
    zb, zt = 0.34, 0.95
    bx, by = 0.33, 0.5        # bottom half-sizes
    tx, ty = 0.43, 0.62       # top half-sizes
    wt = 0.025
    ob = [Vector((sx * bx, sy * by, zb)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    ot = [Vector((sx * tx, sy * ty, zt)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    # dents
    for v in ot:
        v.z += r.uniform(-0.02, 0.01)
    ib = [Vector((v.x * (1 - wt / bx), v.y * (1 - wt / by), zb + wt)) for v in ob]
    it = [Vector((v.x * (1 - wt / tx), v.y * (1 - wt / ty), v.z)) for v in ot]
    O = [sub.av(v) for v in ob + ot]
    I = [sub.av(v) for v in ib + it]
    t = 1.2
    for i in range(4):
        j = (i + 1) % 4
        a, b = O[i], O[j]
        c, d = O[j + 4], O[i + 4]
        L = (ob[j] - ob[i]).length
        sub.face([a, b, c, d], [(0, 0), (L / t, 0), (L / t, 0.62 / t), (0, 0.62 / t)], MAT)
        sub.face([I[j], I[i], I[i + 4], I[j + 4]], [(0, 0), (L / t, 0), (L / t, 0.62 / t), (0, 0.62 / t)], MAT)
        sub.face([O[i + 4], O[j + 4], I[j + 4], I[i + 4]], [(0, 0), (L / t, 0), (L / t, 0.02), (0, 0.02)], MAT)
    sub.face([O[3], O[2], O[1], O[0]], [(0, 0), (0.66, 0), (0.66, 1), (0, 1)], MAT)
    sub.face([I[0], I[1], I[2], I[3]], [(0, 0), (0.66, 0), (0.66, 1), (0, 1)], MAT)
    # rim lip
    for i in range(4):
        j = (i + 1) % 4
        a = ot[i] + (ot[i] - Vector((0, 0, ot[i].z))).normalized() * 0.012
        b = ot[j] + (ot[j] - Vector((0, 0, ot[j].z))).normalized() * 0.012
        add_beam(sub, a, b, 0.05, 0.045, MAT, chamfer=0.008, tile=1.5)
    # corner irons + vertical ribs
    for i in range(4):
        out = Vector((ob[i].x, ob[i].y, 0)).normalized() * 0.01
        add_beam(sub, ob[i] + out, ot[i] + out, 0.06, 0.06, MAT, up=Vector((ob[i].x, ob[i].y, 0)), chamfer=0.01,
                 tile=1.5)
    for sx in (-1, 1):
        for f in (-0.4, 0.4):
            a = Vector((sx * (bx + 0.012), f * by * 0.9, zb + 0.02))
            b = Vector((sx * (tx + 0.012), f * ty * 0.9, zt - 0.05))
            add_beam(sub, a, b, 0.012, 0.07, MAT, up=(sx, 0, 0), chamfer=0.0, tile=1.5)
    # chassis
    for sx in (-1, 1):
        add_beam(sub, (sx * 0.2, -0.6, 0.27), (sx * 0.2, 0.6, 0.27), 0.06, 0.12, MAT, chamfer=0.006, tile=1.5)
    for sy in (-1, 1):
        add_beam(sub, (-0.36, sy * 0.6, 0.27), (0.36, sy * 0.6, 0.27), 0.1, 0.13, MAT, chamfer=0.01, tile=1.5)
        # coupler link
        add_beam(sub, (0, sy * 0.62, 0.26), (0, sy * 0.8, 0.26), 0.05, 0.03, 'MNF_MetalBare', chamfer=0.004, tile=0.5)
        ring = [Vector((math.cos(a) * 0.05, sy * 0.84 + math.sin(a) * 0.05 * sy, 0.26))
                for a in [k * 2 * math.pi / 8 for k in range(9)]]
        add_tube(sub, ring, [0.011] * 9, 5, MAT, tile_v=0.5, cap1=False)
    # wheels (axis along X), running surface at z=0
    wr = 0.17
    wi = 0
    for sy in (-0.36, 0.36):
        add_cyl(sub, (-0.36, sy, wr), (0.36, sy, wr), 0.03, 0.03, 6, MAT, tile=0.5)
        for sx in (-1, 1):
            if missing_wheel == wi:
                wi += 1
                continue
            wi += 1
            xc = sx * GAUGE / 2
            add_cyl(sub, (xc + sx * 0.03, sy, wr), (xc - sx * 0.03, sy, wr), wr, wr * 0.97, 10, MAT, tile=0.6,
                    up=(0, 0, 1), cap1=False)
            # flange (inside)
            add_cyl(sub, (xc - sx * 0.03, sy, wr), (xc - sx * 0.045, sy, wr), wr + 0.022, wr + 0.022, 10, MAT, tile=0.6)
            add_cyl(sub, (xc + sx * 0.03, sy, wr), (xc + sx * 0.05, sy, wr), 0.05, 0.035, 6, MAT, tile=0.5)
            # bearing block
            add_box(sub, (0.07, 0.12, 0.1), Matrix.Translation((sx * 0.2, sy, wr + 0.04)), MAT, bevel=0.01)
    if ore:
        for k in range(5):
            a = r.uniform(0, 6.28)
            rad = r.uniform(0.0, 0.25)
            bm = H.cut_rock(seed * 50 + k, (r.uniform(0.28, 0.42), r.uniform(0.28, 0.42), r.uniform(0.2, 0.3)), cuts=7,
                            subdiv=0, sink=0.0, bevel=0.0 if k % 2 else 0.03)
            mat = 'MNF_OreIron' if k % 3 == 0 else 'MNF_RockMine'
            H.rock_to_mb(sub, bm, M((math.cos(a) * rad * 0.8, math.sin(a) * rad * 1.3, 0.72 + r.uniform(0, 0.12)),
                                    (r.uniform(0, 40), r.uniform(0, 40), r.uniform(0, 360))), mat, tile=1.5)
            bm.free()
        # heap base
        add_box(sub, (0.7, 1.05, 0.1), Matrix.Translation((0, 0, 0.82)), 'MNF_RockMine', jitter=0.03, seed=seed, tile=1.5)
    mb.merge(sub, mm)


def cage_lamp(mb, center, top_z, r=0.075, h=0.2, shade=True, bars=6, mat_cage='MNF_MetalRusted',
              shade_mat='MNF_MetalPainted_Green'):
    """Caged bulb hanging below top_z, centred on `center` (x,y). Returns bulb centre."""
    c = Vector(center)
    z1 = top_z
    z0 = top_z - h
    add_cyl(mb, (c.x, c.y, z1), (c.x, c.y, z1 - 0.05), 0.03, 0.035, 8, 'MNF_Plastic_Black', cap0=True)
    if shade:
        add_cyl(mb, (c.x, c.y, z1 - 0.04), (c.x, c.y, z1 - 0.085), 0.04, r * 1.45, 12, shade_mat, cap0=True,
                cap1=False)
    ring_top = [Vector((c.x + math.cos(a) * r, c.y + math.sin(a) * r, z1 - 0.07)) for a in
                [k * 2 * math.pi / 10 for k in range(11)]]
    add_tube(mb, ring_top, [0.004] * 11, 4, mat_cage, tile_v=0.3, cap1=False, smooth=False)
    ring_mid = [Vector((c.x + math.cos(a) * r, c.y + math.sin(a) * r, z0 + h * 0.4)) for a in
                [k * 2 * math.pi / 10 for k in range(11)]]
    add_tube(mb, ring_mid, [0.004] * 11, 4, mat_cage, tile_v=0.3, cap1=False, smooth=False)
    for k in range(bars):
        a = k * 2 * math.pi / bars
        p0 = Vector((c.x + math.cos(a) * r, c.y + math.sin(a) * r, z1 - 0.07))
        pm = Vector((c.x + math.cos(a) * r * 1.05, c.y + math.sin(a) * r * 1.05, z0 + h * 0.4))
        p1 = Vector((c.x + math.cos(a) * r * 0.15, c.y + math.sin(a) * r * 0.15, z0))
        add_tube(mb, [p0, pm, p1], [0.004] * 3, 3, mat_cage, tile_v=0.3, cap1=False, smooth=False)
    add_cyl(mb, (c.x, c.y, z0 + 0.004), (c.x, c.y, z0 - 0.006), 0.02, 0.015, 6, mat_cage)
    return Vector((c.x, c.y, z1 - 0.085 - r * 0.85))


def bulb_mesh(center, r=0.045, mat='MNF_BulbWarm', segs=10, stretch=1.25):
    """Pear-shaped bulb as its own MB (in parent space)."""
    mb = MB()
    c = Vector(center)
    pts, radii = [], []
    prof = [(0.0, 0.30), (0.25, 0.55), (0.5, 0.92), (0.75, 1.0), (0.9, 0.8), (1.0, 0.0)]
    for t, f in prof:
        pts.append(c + Vector((0, 0, r * stretch * (1 - 2 * t) + r * 0.3)))
        radii.append(max(0.002, r * f))
    add_tube(mb, pts, radii, segs, mat, tile_v=0.2, cap0=True, apex=True)
    return mb


def rubble(mb, center, radius, n, seed, mat='MNF_RockMine', sizes=(0.15, 0.6), height=0.8, moss=None, hull_pts=None,
           flat=1.0, bevel_min=0.45):
    """Rocks smaller than bevel_min metres get no chamfer (cheap); larger ones are chamfered."""
    """Pile of fractured rocks around center (cone-ish distribution)."""
    r = rng(seed)
    c = Vector(center)
    for k in range(n):
        a = r.uniform(0, 6.28)
        d = radius * math.sqrt(r.random())
        s = r.uniform(*sizes) * (1.2 - 0.6 * d / radius)
        z = max(0.0, height * (1 - d / radius) ** 1.2 * r.uniform(0.3, 1.0) - s * 0.3)
        bm = H.cut_rock(seed * 100 + k, (s * r.uniform(0.8, 1.4), s * r.uniform(0.8, 1.3), s * r.uniform(0.5, 0.9) * flat),
                        cuts=r.randint(6, 9), subdiv=0, sink=0.15, bevel=0.035 if s >= bevel_min else 0.0)
        n0 = len(mb.v)
        H.rock_to_mb(mb, bm, M((c.x + math.cos(a) * d * 1.3, c.y + math.sin(a) * d, c.z + z),
                               (r.uniform(-25, 25), r.uniform(-25, 25), r.uniform(0, 360))), mat, moss,
                     moss_thresh=0.7, tile=3.0, seed=seed + k)
        if hull_pts is not None:
            hull_pts.extend(Vector(v) for v in mb.v[n0:])
        bm.free()
