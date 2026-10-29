"""kitA_deposits.py - Kit_Deposits.fbx: mineable ore deposits (prop artist A).

Each deposit = top-level empty at the origin (pivot at the bottom centre where it meets the floor, or
the wall-contact centre with -Y out of the wall for *_Wall variants) with children:
  Base      host rock mesh (stays), pivot at the deposit origin
  Chunk_00..Chunk_04  removable ore pieces, each pivoted at its own centre
  COL_Body  box collider
Shape language per ore type (brief): iron = bulbous metallic nodules erupting through a lumpy boulder,
copper = fractured angular blocks with jagged vein ridges + patina crust, crystal = hexagonal prism
clusters, blackstone = tall angular obsidian monolith shards, anomalous = a fleshy glowing core inside a
cracked-open rock with veins crawling over the stone.
"""
import math
import random

import bmesh
from mathutils import Vector, Matrix

import propkit_a_helpers as H
from propkit_a_helpers import MB, xf, lerp

KIT = "Kit_Deposits"
ROCK = "MNF_RockMine"
TILE_ROCK = 1.5
TILE_ORE = 0.8
WALL = xf(rot=(90, 0, 0))   # floor frame (+Z up) -> wall frame (+Z becomes -Y, out of the wall)

NAMES = ["Deposit_Iron", "Deposit_Copper", "Deposit_Crystal", "Deposit_Blackstone", "Deposit_Anomalous",
         "Deposit_Iron_Wall", "Deposit_Copper_Wall", "Deposit_Crystal_Wall"]
REQUIRED = {n: ["Base", "Chunk_00", "Chunk_01", "Chunk_02", "Chunk_03", "COL_Body"] for n in NAMES}
BUDGET = (500, 5000)
OVERVIEW_ROWS = 2
OVERVIEW_CELL = 0.5


class Shape:
    """MB plus a merged copy of the geometry for ray casting (surface placement)."""

    def __init__(self, tile):
        self.mb = MB(tile)
        self.shape = bmesh.new()
        self._tree = None

    def add(self, part, mat, m=None, **kw):
        cp = part.copy()
        if m is not None:
            bmesh.ops.transform(cp, matrix=m, verts=cp.verts)
        H.merge_into(self.shape, cp)
        self._tree = None
        self.mb.add(part, mat, m, **kw)

    def tree(self):
        if self._tree is None:
            self._tree = H.bvh_of(self.shape)
        return self._tree


def floor_rock(radius, seed, scale, amp=0.25, freq=1.2, subdiv=3, facets=0, sink=0.05, cut=0.3, facet_depth=(0.7, 0.9)):
    """Rock whose lower part is squashed flat at z = -sink (sits on / slightly into the floor)."""
    zc = cut * radius * scale[2]
    bm = H.rock(radius, seed, subdiv, scale, amp, freq, flat_bottom=-zc, facets=facets, facet_depth=facet_depth, squash=0.08)
    H.transform(bm, xf((0, 0, zc - sink)))
    return bm


def dirs_upper(rng, n, zmin=0.25, zmax=0.95, jitter=0.4, phase=0.0):
    out = []
    for k in range(n):
        a = phase + math.tau * k / n + rng.uniform(-jitter, jitter)
        z = rng.uniform(zmin, zmax)
        r = math.sqrt(max(0.0, 1 - z * z))
        out.append(Vector((r * math.cos(a), r * math.sin(a), z)))
    return out


def finish(name, base_mb, chunk_mbs, wall, notes, col_shrink=0.92, extra_base=None):
    """Create the empty + children; apply the wall transform if needed."""
    root = H.empty(name, None, (0, 0, 0), size=0.25)
    root.empty_display_type = "PLAIN_AXES"
    if wall:
        base_mb.transform(WALL)
        for c in chunk_mbs:
            c.transform(WALL)
    mn, mx = base_mb.bounds()
    amn, amx = mn.copy(), mx.copy()
    for c in chunk_mbs:
        a, b = c.bounds()
        for i in range(3):
            amn[i] = min(amn[i], a[i]); amx[i] = max(amx[i], b[i])
    base_mb.to_object("Base", root, smooth_angle=55)
    for i, c in enumerate(chunk_mbs):
        cmn, cmx = c.bounds()
        c.to_object("Chunk_%02d" % i, root, pivot=(cmn + cmx) / 2, smooth_angle=45)
    ctr = (mn + mx) / 2
    half = (mx - mn) / 2 * col_shrink
    cmn, cmx = ctr - half, ctr + half
    if wall:
        cmx.y = 0.0
    else:
        cmn.z = 0.0
    H.col_box("COL_Body", root, cmn, cmx)
    return {"root": root, "notes": notes, "view": "iso", "cell": 0.25, "figure": True, "wall": wall, "hero": True,
            "hero_shots": [("iso", (amn, amx)), ("isol" if not wall else "top", (amn, amx))]}


# ============================================================================================
# Iron: lumpy boulder with dark metallic nodules erupting through it
# ============================================================================================
def build_iron(wall=False, seed=11):
    rng = random.Random(seed)
    S = Shape(TILE_ROCK)
    sc = (1.0, 0.86, 0.62) if not wall else (1.08, 0.92, 0.36)
    base = floor_rock(0.5, seed, sc, amp=0.3, freq=1.05, subdiv=4)
    S.add(base, ROCK, uv="box")
    tree = S.tree()
    centre = Vector((0, 0, 0.12 if not wall else 0.05))
    chunks = []
    spots = [(0.0, 0.0)] + [(math.cos(a) * 0.3, math.sin(a) * 0.25) for a in (0.5, 1.9, 3.4, 4.9)]
    for k, (sx, sy) in enumerate(spots):
        sx += rng.uniform(-0.04, 0.04); sy += rng.uniform(-0.04, 0.04)
        loc, n = H.top_hit(tree, sx, sy)
        d = (loc - centre).normalized()
        n = (n + d * 0.5).normalized()
        cm = MB(TILE_ORE)
        r = rng.uniform(0.13, 0.17) * (0.85 if wall else 1.0)
        nod = H.rock(r, seed * 10 + k, 3, (1.0, 0.95, 0.85), amp=0.2, freq=1.6)
        cm.add(nod, "MNF_OreIron", H.place(loc + n * r * 0.45, n, spin=rng.uniform(0, 90)), uv="box")
        t = n.orthogonal().normalized()
        for j in range(2):
            q = Matrix.Rotation(math.tau * j / 2 + rng.uniform(-0.6, 0.6), 4, n) @ t
            rr = r * rng.uniform(0.4, 0.55)
            sm = H.rock(rr, seed * 10 + k + 50 + j, 2, (1, 1, 0.8), amp=0.3, freq=2.0)
            cm.add(sm, "MNF_OreIron", H.place(loc + q * r * 0.95 + n * rr * 0.1, n), uv="box")
        chunks.append(cm)
        # broken rock lips round the eruption (stay on the Base after mining)
        for j in range(4):
            q = Matrix.Rotation(math.tau * j / 4 + rng.uniform(-0.4, 0.4), 4, n) @ t
            fl = H.rock(r * 0.55, seed * 100 + k * 7 + j, 1, (1.4, 0.9, 0.45), amp=0.25, facets=2)
            tilt = (n * 0.6 + q).normalized()
            S.add(fl, ROCK, H.place(loc + q * r * 1.25 - n * 0.01, tilt, spin=rng.uniform(0, 180)), uv="box")
    nm = "Deposit_Iron_Wall" if wall else "Deposit_Iron"
    return finish(nm, S.mb, chunks, wall,
                  "Iron deposit ~1.0 m: lumpy boulder (MNF_RockMine) with 5 bulbous metallic nodule clusters "
                  "(MNF_OreIron) erupting through cracked rock lips. Chunk_* pivots at their centres." +
                  (" Wall variant: pivot at wall contact, -Y out of the wall." if wall else ""))


# ============================================================================================
# Copper: fractured angular blocks + jagged vein ridges + green patina crust
# ============================================================================================
def build_copper(wall=False, seed=21):
    rng = random.Random(seed)
    S = Shape(TILE_ROCK)
    zs = 1.0 if not wall else 0.6
    blocks = [((-0.2, 0.03, 0), 0.42, (1.0, 0.85, 0.85 * zs), 0), ((0.26, -0.06, 0), 0.36, (1.0, 0.9, 0.8 * zs), 25),
              ((0.04, 0.28, 0), 0.27, (1.1, 0.8, 0.75 * zs), -30), ((-0.1, -0.32, 0), 0.2, (1.1, 0.9, 0.6 * zs), 60)]
    for k, (p, r, sc, rot) in enumerate(blocks):
        b = floor_rock(r, seed + k, sc, amp=0.08, freq=1.0, subdiv=3, facets=12, facet_depth=(0.55, 0.8), cut=0.25)
        S.add(b, ROCK, xf(p, (0, 0, rot)), uv="box", flat=False)
    tree = S.tree()
    centre = Vector((0.02, 0.0, 0.18 * zs))
    chunks = []
    # vein ridges: outcrop lines running across the fractured blocks (follow the top surface)
    lines = [((-0.5, -0.18), (0.45, 0.05)), ((-0.35, 0.3), (0.15, -0.42)), ((0.05, 0.42), (0.5, -0.12)),
             ((-0.55, 0.12), (-0.05, 0.42)), ((0.1, -0.45), (0.5, 0.15))]
    for k, (p0, p1) in enumerate(lines):
        pts, nrm = [], []
        steps = 13
        for i in range(steps):
            t = i / (steps - 1)
            x = lerp(p0[0], p1[0], t) + 0.03 * math.sin(t * 7 + k)
            y = lerp(p0[1], p1[1], t) + 0.03 * math.cos(t * 5 + k)
            loc, n = H.top_hit(tree, x, y)
            if loc is None:
                continue
            pts.append(loc)
            nrm.append(n)
        # smooth normals along the ridge
        nrm = [(nrm[max(i - 1, 0)] + nrm[i] * 2 + nrm[min(i + 1, len(nrm) - 1)]).normalized() for i in range(len(nrm))]
        cm = MB(TILE_ORE)
        cm.add(H.ridge(pts, nrm, rng.uniform(0.11, 0.15), rng.uniform(0.09, 0.12), seed + k, jag=0.5, depth=0.05),
               "MNF_OreCopper", uv="box")
        for j in (2, 6):
            if j < len(pts):
                cr = H.rock(0.045, seed * 3 + k * 5 + j, 2, (1.4, 1.2, 0.55), amp=0.3)
                cm.add(cr, "MNF_OreCopper", H.place(pts[j] + nrm[j] * 0.05, nrm[j], spin=rng.uniform(0, 180)), uv="box")
        chunks.append(cm)
    # patina crust patches that stay on the host rock
    for k in range(7):
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.1, 1))).normalized()
        loc, n = H.surface_hit(tree, centre, d)
        cr = H.rock(rng.uniform(0.05, 0.08), seed * 7 + k, 1, (1.5, 1.2, 0.3), amp=0.35)
        S.add(cr, "MNF_OreCopper", H.place(loc, n, spin=rng.uniform(0, 180)), uv="box")
    nm = "Deposit_Copper_Wall" if wall else "Deposit_Copper"
    return finish(nm, S.mb, chunks, wall,
                  "Copper deposit ~1.1 m: fractured, flat-faceted rock blocks (MNF_RockMine) with 5 jagged copper vein "
                  "ridges (MNF_OreCopper, removable chunks) and green patina crust patches." +
                  (" Wall variant: pivot at wall contact, -Y out of the wall." if wall else ""))


# ============================================================================================
# Crystal: hexagonal luminous prism clusters at different angles
# ============================================================================================
def build_crystal(wall=False, seed=31):
    rng = random.Random(seed)
    S = Shape(TILE_ROCK)
    sc = (1.15, 0.95, 0.42) if not wall else (1.15, 0.95, 0.3)
    base = floor_rock(0.46, seed, sc, amp=0.3, freq=1.2, subdiv=4)
    S.add(base, ROCK, uv="box")
    for k in range(5):
        a = math.tau * k / 5 + 0.3
        rb = H.rock(rng.uniform(0.09, 0.15), seed + 40 + k, 2, (1.2, 1.0, 0.6), amp=0.3, facets=2)
        S.add(rb, ROCK, xf((math.cos(a) * 0.5, math.sin(a) * 0.42, 0.0)), uv="box")
    tree = S.tree()
    centre = Vector((0, 0, 0.05))
    chunks = []
    heights = [0.78, 0.55, 0.48, 0.42, 0.36] if not wall else [0.6, 0.48, 0.42, 0.38, 0.34]
    spots = [(0.02, 0.03)] + [(math.cos(a) * 0.3, math.sin(a) * 0.24) for a in (0.3, 1.7, 3.0, 4.5)]
    for k, (sx, sy) in enumerate(spots):
        loc, n = H.top_hit(tree, sx + rng.uniform(-0.03, 0.03), sy + rng.uniform(-0.03, 0.03))
        d = Vector((sx, sy, 0.0)) * 1.6
        axis = (n * 0.6 + d + Vector((0, 0, 0.45 if k else 1.5))).normalized()
        cm = MB(TILE_ORE)
        Hh = heights[k]
        R = Hh * rng.uniform(0.1, 0.13)
        root_p = loc - axis * 0.06
        cm.add(H.prism(R, Hh, 6, tip=0.22, taper=0.92, seed=seed + k), "MNF_Crystal", H.place(root_p, axis, spin=rng.uniform(0, 60)))
        t = axis.orthogonal().normalized()
        for j in range(3):
            q = Matrix.Rotation(math.tau * j / 3 + rng.uniform(-0.5, 0.5), 4, axis) @ t
            ax2 = (axis + q * rng.uniform(0.45, 0.8)).normalized()
            h2 = Hh * rng.uniform(0.35, 0.6)
            cm.add(H.prism(h2 * rng.uniform(0.1, 0.14), h2, 6, tip=0.25, seed=seed + k * 9 + j), "MNF_Crystal",
                   H.place(root_p + q * R * 0.8, ax2, spin=rng.uniform(0, 60)))
        chunks.append(cm)
    # small stubs that remain
    for k in range(6):
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.3, 1))).normalized()
        loc, n = H.surface_hit(tree, centre, d)
        h = rng.uniform(0.06, 0.14)
        S.add(H.prism(h * 0.18, h, 6, tip=0.3, seed=seed + 70 + k), "MNF_Crystal", H.place(loc - n * 0.015, (n + d).normalized()))
    nm = "Deposit_Crystal_Wall" if wall else "Deposit_Crystal"
    return finish(nm, S.mb, chunks, wall,
                  "Crystal deposit ~1.2 m: low rock base with 5 clusters of hexagonal luminous prisms (MNF_Crystal, "
                  "emissive) growing at different angles; small crystal stubs stay after mining." +
                  (" Wall variant: pivot at wall contact, -Y out of the wall." if wall else ""))


# ============================================================================================
# Blackstone: angular obsidian-like monolith shards jutting from the ground
# ============================================================================================
def build_blackstone(seed=41):
    rng = random.Random(seed)
    S = Shape(TILE_ROCK)
    # cracked ground plates heaved up around the shards
    for k in range(7):
        a = math.tau * k / 7 + rng.uniform(-0.2, 0.2)
        rr = rng.uniform(0.35, 0.55)
        pl = H.rock(rng.uniform(0.15, 0.22), seed + k, 2, (1.4, 1.1, 0.6), amp=0.12, facets=6, facet_depth=(0.5, 0.75))
        p = Vector((math.cos(a) * rr, math.sin(a) * rr, 0.0))
        tilt = (Vector((0, 0, 1)) - p.normalized() * 0.25).normalized()
        S.add(pl, ROCK, H.place(p, tilt, spin=math.degrees(a)), uv="box", flat=True)
    # broken stump + glassy debris that stay
    S.add(H.shard(0.28, 0.2, seed=seed + 20, n=16, taper=0.5), "MNF_Blackstone", xf((0.0, 0.0, -0.03), (4, -6, 20)), uv="box", flat=True)
    for k in range(6):
        a = rng.uniform(0, math.tau)
        rr = rng.uniform(0.25, 0.6)
        S.add(H.shard(rng.uniform(0.06, 0.14), rng.uniform(0.03, 0.05), seed=seed + 30 + k, n=9),
              "MNF_Blackstone", xf((math.cos(a) * rr, math.sin(a) * rr, -0.01), (rng.uniform(50, 80), 0, math.degrees(a) + 90)),
              uv="box", flat=True)
    chunks = []
    spec = [(1.3, 0.2, (0.02, 0.0), (0, 0)), (1.0, 0.17, (0.15, 0.1), (-16, 20)), (0.82, 0.15, (-0.16, 0.08), (15, 18)),
            (0.7, 0.14, (0.05, -0.18), (22, -10)), (0.55, 0.12, (-0.1, -0.12), (14, -28))]
    for k, (ln, w, (px, py), (rx, ry)) in enumerate(spec):
        cm = MB(TILE_ORE)
        cm.add(H.shard(ln, w, seed=seed + 100 + k, n=20, taper=0.08, depth_ratio=0.7), "MNF_Blackstone",
               xf((px, py, -0.06), (rx, ry, rng.uniform(0, 180))), uv="box", flat=True)
        cm.add(H.shard(ln * 0.45, w * 0.55, seed=seed + 120 + k, n=12, taper=0.1), "MNF_Blackstone",
               xf((px, py, -0.04), (rx, ry, 0)) @ xf((w * 0.55, 0, 0), (0, 14, rng.uniform(0, 90))), uv="box", flat=True)
        chunks.append(cm)
    return finish("Deposit_Blackstone", S.mb, chunks, False,
                  "Blackstone deposit ~1.3 m: 5 tall angular obsidian monolith shards (MNF_Blackstone, flat-shaded "
                  "facets) jutting from heaved, cracked ground plates; a broken stump and glassy debris stay.")


# ============================================================================================
# Anomalous: organic glowing core in cracked-open rock, veins spreading into the stone
# ============================================================================================
def build_anomalous(seed=51):
    rng = random.Random(seed)
    S = Shape(TILE_ROCK)
    zc = 0.36
    core_c = Vector((0, 0, zc))
    # inner core (stays): lumpy, glowing flesh with darker membrane patches
    core = H.icosphere(1.0, 3)
    for v in core.verts:
        v.co *= 1.0 + 0.14 * H.fbm(v.co * 2.2, seed)
        v.co = Vector((v.co.x * 0.36, v.co.y * 0.33, v.co.z * 0.32)) + core_c
    core.normal_update()
    S.add(core, lambda f: "MNF_Flesh" if H.fbm(f.calc_center_median() * 5.0, seed + 3) > 0.12 else "MNF_Anomalous", uv="box")
    # rock shell broken into 4 thick fragments with cracks between, open at the top
    shell = H.rock(0.5, seed + 1, 4, (1.0, 0.92, 0.78), amp=0.22, freq=1.2)
    H.transform(shell, xf((0, 0, zc)))
    for v in shell.verts:
        if v.co.z < 0.02:
            v.co.z = 0.02 + (v.co.z - 0.02) * 0.1 - 0.05
    shell.normal_update()
    sectors = 4
    for k in range(sectors):
        piece = shell.copy()
        a0 = math.tau * k / sectors + 0.35
        a1 = a0 + math.tau / sectors
        kill = []
        for f in piece.faces:
            c = f.calc_center_median() - core_c
            ang = math.atan2(c.y, c.x) % math.tau
            inside = (a0 % math.tau <= ang < a1 % math.tau) if (a0 % math.tau) < (a1 % math.tau) else \
                (ang >= a0 % math.tau or ang < a1 % math.tau)
            top = c.z > 0.22 + 0.05 * math.sin(ang * 3 + k)
            if not inside or top:
                kill.append(f)
        bmesh.ops.delete(piece, geom=kill, context="FACES")
        loose = [v for v in piece.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(piece, geom=loose, context="VERTS")
        res = bmesh.ops.solidify(piece, geom=list(piece.faces), thickness=0.07)
        mid = (a0 + a1) / 2
        push = Vector((math.cos(mid), math.sin(mid), 0.0)) * 0.035
        H.jitter(piece, 0.004, seed + k)
        S.add(piece, ROCK, xf(push), uv="box")
    tree = S.tree()
    # veins crawling out from the cracks over the stone (stay)
    for vb in H.veins(tree, rng, core_c, 0.5, [(math.cos(a), math.sin(a), rng.uniform(-0.1, 0.5))
                                                 for a in [math.tau * k / 8 + 0.35 + (0.39 if k % 2 else 0) for k in range(8)]],
                      steps=7, step_ang=0.17, r0=0.014, r1=0.004, branch=1, offset_k=0.45, bias=(0, 0, -1)):
        S.mb.add(vb, "MNF_Anomalous")
    chunks = []
    # pulsing growths bulging out of the cracks and the open top
    spots = [(0.0, 0.0, 1.0), ] + [(math.cos(math.tau * k / 4 + 0.35), math.sin(math.tau * k / 4 + 0.35), 0.35) for k in range(4)]
    for k, d in enumerate(spots):
        d = Vector(d).normalized()
        loc, n = H.surface_hit(tree, core_c, d)
        cm = MB(TILE_ORE)
        r = 0.11 if k == 0 else rng.uniform(0.07, 0.09)
        g = H.icosphere(1.0, 2)
        for v in g.verts:
            v.co *= 1.0 + 0.25 * H.fbm(v.co * 2.0, seed + 60 + k)
            v.co = Vector((v.co.x * r, v.co.y * r, v.co.z * r * 0.85))
        g.normal_update()
        cm.add(g, lambda f: "MNF_Anomalous" if f.calc_center_median().z > -r * 0.2 else "MNF_Flesh",
               H.place(loc + d * r * 0.1, d, spin=rng.uniform(0, 90)), uv="box")
        # little pustules on the growth
        for j in range(3):
            q = Matrix.Rotation(math.tau * j / 3, 4, d) @ d.orthogonal().normalized()
            cm.add(H.uvsphere(r * 0.28, 8, 5), "MNF_Anomalous", xf(loc + d * r * 0.75 + q * r * 0.55))
        chunks.append(cm)
    return finish("Deposit_Anomalous", S.mb, chunks, False,
                  "Anomalous deposit ~1.0 m: rock (MNF_RockMine) cracked open into 4 thick fragments around a lumpy "
                  "glowing core (MNF_Anomalous/MNF_Flesh); veins spread outward over the stone. Chunks = 5 pulsing "
                  "growths bulging from the cracks/top (pulse them in Unity via emission).")


def build():
    return [build_iron(), build_copper(), build_crystal(), build_blackstone(), build_anomalous(),
            build_iron(wall=True, seed=12), build_copper(wall=True, seed=22), build_crystal(wall=True, seed=32)]
