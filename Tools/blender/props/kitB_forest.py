"""kitB_forest - builds Kit_Forest (haunted forest props) for MONKEY NO FEAR.

usage: python kitB_forest.py -- [--only Name1,Name2] [--blend out.blend] [--noexport]
Default: builds everything, saves SourceArt/Props/Kit_Forest.blend, exports
Assets/MonkeyNoFear/Art/Models/Props/Kit_Forest.fbx and props_manifest_Kit_Forest.json.
All objects are modelled at the world origin, pivot at the base, front = -Y.
"""
import bpy, sys, os, math
from mathutils import Vector, Matrix, Quaternion, noise
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import propkit_b_helpers as H
from propkit_b_helpers import MB, M, add_box, add_beam, add_cyl, add_tube, add_card, rng, hull_rock, rock_to_mb
import kitB_treegen as T
import kitB_shared as S

KIT = 'Kit_Forest'
BUILDERS = []
NOTES = {}


def builder(fn):
    BUILDERS.append(fn)
    return fn


top = H.make_top


# =============================================================================================
# Trees
# =============================================================================================
PINES = {
    'Tree_Pine_A': dict(seed=101, height=15.0, r0=0.32, whorls=16, crown_w=3.0, dead_frac=0.33),
    'Tree_Pine_B': dict(seed=202, height=17.5, r0=0.37, whorls=17, crown_w=3.3, dead_frac=0.42, per_whorl=(4, 5)),
    'Tree_Pine_C': dict(seed=303, height=12.5, r0=0.27, whorls=14, crown_w=2.7, dead_frac=0.24, lean=0.06),
}


def _pine(name, coll):
    mb, trunk = T.make_pine(**PINES[name])
    ob = top(mb, name, coll)
    mn, mx = T.trunk_col_bounds(trunk, 7.0, 0.9)
    H.col_box(ob, 'COL_Trunk', mn, mx)
    NOTES[name] = ('Dark conifer, %.1f m. Bark MNF_BarkPine (V tiles along trunk), needle cards MNF_FoliagePine '
                   '(full 0..1 UV, cluster base at V=0, custom normals point out of the crown). Lower whorls are '
                   'dead bare branches. COL_Trunk covers the trunk to 7 m.' % PINES[name]['height'])
    return ob


for _n in PINES:
    builder((lambda n: (lambda coll: _pine(n, coll)))(_n)).__name__ = _n

DEADS = {
    # the claw: upright trunk splitting into crooked leaders that hook inwards like closing fingers
    'Tree_Dead_A': dict(seed=404, height=10.5, r0=0.34, trunk_frac=0.5, leaders=5, leader_ang=(22, 45),
                        leader_r=(0.7, 0.85), laterals=4, lat_len=0.42, lat_r=(0.55, 0.7), claw=1.1, lean=0.05,
                        sub=(2, 3), twigs=(1, 2)),
    # the crawler: strongly leaning, long sagging arms reaching towards the ground with clawed hands
    'Tree_Dead_B': dict(seed=505, height=10.0, r0=0.36, trunk_frac=0.62, leaders=2, leader_ang=(25, 40), laterals=5,
                        lat_ang=(55, 85), lat_len=0.6, lat_r=(0.6, 0.75), droop=0.1, claw=0.9, lean=0.32,
                        sub=(2, 3), twigs=(1, 2), hands=0.9, broken_p=0.1),
    # the scarecrow: snapped, splintered trunk with long outstretched arms ending in fingered tips
    'Tree_Dead_C': dict(seed=606, height=9.5, r0=0.4, trunk_frac=0.85, leaders=0, snapped=True, laterals=5,
                        lat_start=0.42, lat_ang=(62, 92), lat_len=0.62, lat_r=(0.55, 0.72), claw=1.15, lean=0.05,
                        broken_p=0.2, hands=0.95, sub=(2, 3), twigs=(1, 2)),
}


def _dead(name, coll):
    mb, trunk = T.make_dead(**DEADS[name])
    ob = top(mb, name, coll)
    mn, mx = T.trunk_col_bounds(trunk, 4.0, 0.9)
    H.col_box(ob, 'COL_Trunk', mn, mx)
    NOTES[name] = 'Twisted dead tree, bare clawing branches (MNF_BarkDead). COL_Trunk covers the lower 4 m of trunk.'
    return ob


for _n in DEADS:
    builder((lambda n: (lambda coll: _dead(n, coll)))(_n)).__name__ = _n


@builder
def Tree_Gnarled(coll):
    mb, trunk = T.make_dead(seed=707, height=9.5, r0=0.8, trunk_frac=0.45, leaders=4, leader_ang=(36, 58),
                            leader_r=(0.7, 0.85), laterals=2, lat_start=0.5, lat_len=0.45, lat_r=(0.55, 0.7),
                            claw=0.9, sub=(3, 4), twigs=(1, 3), lobes=5, lobe_amp=0.14,
                            hollow=(0.0, 2.0, 0.9, 0.62), trunk_segs=20, roots=7, root_len=(0.6, 1.3),
                            root_rise=0.25, leaf_tufts=8, tuft_size=1.2, trunk_wander=0.1, flare=0.35, lean=0.05,
                            sides=(8, 6, 4, 3), trunk_taper=1.6, limb_taper=1.5, broken_p=0.0, leader_len=0.72)
    ob = top(mb, 'Tree_Gnarled', coll)
    mn, mx = T.trunk_col_bounds(trunk, 4.0, 0.85)
    H.col_box(ob, 'COL_Trunk', mn, mx)
    NOTES['Tree_Gnarled'] = ('Huge old twisted tree, 10 m, trunk ~1.5 m, buttress roots, hollow at the base facing -Y '
                             '(inner faces MNF_WoodRotten), a few dying leaf tufts (MNF_FoliageLeaf). The COL_Trunk box '
                             'covers the trunk (the hollow is inside the box).')
    return ob


# =============================================================================================
# Rocks
# =============================================================================================
ROCKS = {
    'Rock_A': dict(seed=11, size=(0.62, 0.5, 0.42), cuts=8, subdiv=0, moss=False),
    'Rock_B': dict(seed=12, size=(1.2, 0.9, 0.55), cuts=9, subdiv=1, moss=True, strata=0.06, taper_top=0.2),
    'Rock_C': dict(seed=13, size=(0.85, 0.7, 1.7), cuts=10, subdiv=1, moss=True, tilt=(7, -5, 20), taper_top=0.3),
    'Rock_D': dict(seed=14, size=(2.2, 1.7, 1.3), cuts=11, subdiv=1, moss=True, strata=0.07),
    'Rock_E': dict(seed=15, size=(3.0, 2.5, 2.2), cuts=12, subdiv=1, moss=True, strata=0.08),
}


def _rock(name, coll):
    p = dict(ROCKS[name])
    moss = p.pop('moss')
    tilt = p.pop('tilt', (0, 0, 0))
    bm = H.cut_rock(**p)
    mb = MB()
    rock_to_mb(mb, bm, M((0, 0, 0), tilt), 'MNF_RockDry', 'MNF_Moss' if moss else None, moss_thresh=0.7,
               seed=p['seed'])
    if tilt != (0, 0, 0):
        zmin = min(v.z for v in mb.v)
        mb.transform(Matrix.Translation((0, 0, -zmin - 0.1 * p['size'][2])))
    ob = top(mb, name, coll, sharp=35)
    H.col_hull(ob, 'COL_Rock_CONVEX', [Vector(v) for v in mb.v])
    NOTES[name] = ('Sharp fractured, weathered rock ~%.1f m (MNF_RockDry%s). Base sunk ~10%% below z=0. '
                   'COL_Rock_CONVEX = convex hull.' % (max(p['size']), ', moss on up-facing faces' if moss else ''))
    bm.free()
    return ob


for _n in ROCKS:
    builder((lambda n: (lambda coll: _rock(n, coll)))(_n)).__name__ = _n


@builder
def Boulder_Large(coll):
    mb = MB()
    bm = H.cut_rock(21, (5.6, 4.8, 4.4), cuts=14, subdiv=2, disp=0.012, lowfreq=0.04, strata=0.05, taper_top=0.2)
    rock_to_mb(mb, bm, None, 'MNF_RockDry', 'MNF_Moss', moss_thresh=0.66, seed=21)
    main_pts = [Vector(v) for v in mb.v]
    n0 = len(mb.v)
    # a lower step block at the front-right so the boulder can be climbed
    bm2 = H.cut_rock(22, (2.6, 2.3, 2.1), cuts=10, subdiv=1)
    rock_to_mb(mb, bm2, M((2.4, -1.9, 0), (0, 0, 25)), 'MNF_RockDry', 'MNF_Moss', moss_thresh=0.66, seed=22)
    step_pts = [Vector(v) for v in mb.v[n0:]]
    ob = top(mb, 'Boulder_Large', coll, sharp=35)
    H.col_hull(ob, 'COL_Boulder_CONVEX', main_pts)
    H.col_hull(ob, 'COL_Step_CONVEX', step_pts)
    NOTES['Boulder_Large'] = ('5.6 m climbable boulder with a ~2 m step block at the front-right (+X/-Y) to climb '
                              'up. Two convex colliders.')
    bm.free(); bm2.free()
    return ob


def _cliff(name, coll, seed, width, height, depth, nblocks, overhang=0.0):
    r = rng(seed)
    mb = MB()
    hulls = []
    bh = height / nblocks
    for b in range(nblocks):
        z = b * bh
        w = width * r.uniform(0.88, 1.0) * (1 - 0.15 * b / nblocks)
        yoff = r.uniform(-0.45, 0.25) * depth * 0.4
        if overhang and b == nblocks - 2:
            yoff -= overhang
        split = r.random() < 0.55 and b > 0
        parts = [(-w * 0.25 + r.uniform(-0.2, 0.2), w * 0.52), (w * 0.27, w * 0.5)] if split else [(0, w)]
        for k, (xc, pw) in enumerate(parts):
            bm = H.cut_rock(seed * 10 + b * 3 + k, (pw, depth * r.uniform(0.85, 1.0), bh * 1.55), cuts=9, subdiv=1,
                            disp=0.012, lowfreq=0.03, strata=0.1, strata_freq=1.2, front_flat=0.2, sink=0.0,
                            taper_top=0.05, nz_bias=0.0)
            n0 = len(mb.v)
            rock_to_mb(mb, bm, M((xc + r.uniform(-0.15, 0.15) * width * 0.2, yoff + r.uniform(-0.2, 0.2),
                                  z - (0.3 if b == 0 else 0.05)), (r.uniform(-3, 3), r.uniform(-3, 3), r.uniform(-5, 5))),
                       'MNF_RockDry_Tri', 'MNF_Moss', moss_thresh=0.68, seed=seed + b)
            hulls.append([Vector(v) for v in mb.v[n0:]])
            bm.free()
    ob = top(mb, name, coll, sharp=35)
    for i, hp in enumerate(hulls):
        H.col_hull(ob, 'COL_Block_%d_CONVEX' % i, hp)
    NOTES[name] = ('Cliff wall piece %.0f m wide x %.0f m tall: stacked fractured strata blocks with ledges%s on the '
                   '-Y face; back (+Y) flattened to butt into terrain. MNF_RockDry_Tri (triplanar) + MNF_Moss on ledge '
                   'tops. One convex collider per block.' % (width, height, ' and an overhang' if overhang else ''))
    return ob


@builder
def CliffChunk_A(coll):
    return _cliff('CliffChunk_A', coll, 31, 8.0, 10.0, 3.4, 5)


@builder
def CliffChunk_B(coll):
    return _cliff('CliffChunk_B', coll, 32, 6.5, 11.5, 3.0, 6, overhang=0.9)


# =============================================================================================
# Mine entrance
# =============================================================================================
@builder
def MineEntrance(coll):
    from kitB_shared import timber, plank, obox, bolt, Z
    r = rng(41)
    mb = MB()
    hw, ht = 1.75, 3.2           # opening (matches Kit_Mine SupportFrame)
    # --- portal frame ---
    for sg in (-1, 1):
        timber(mb, (sg * 1.96, 0, -0.1), (sg * 1.94, 0, ht), 0.4, 0.4, up=(0, 1, 0), seed=410 + sg, rough=0.015,
               chamfer=0.035)
        # kicker braces to the ground outside
        timber(mb, (sg * 2.05, 0.05, 2.5), (sg * 2.75, 0.15, -0.1), 0.26, 0.26, up=(0, 1, 0), seed=412 + sg)
        # wing wall planks (retain the hillside), angled back
        for k in range(6):
            z = 0.12 + k * 0.4
            if k == 4 and sg == 1:
                continue
            a = Vector((sg * 2.15, 0.1, z))
            b = Vector((sg * (2.15 + 0.95 * (1 - z / 3.2) + 0.25), 0.75, z + r.uniform(-0.04, 0.04)))
            plank(mb, a, b, 0.36, 0.06, 'MNF_WoodPlanks', up=(0, 0, 1), seed=420 + k + sg * 10, jag1=r.uniform(0, 0.15))
    timber(mb, (-2.6, 0, ht + 0.23), (2.6, 0, ht + 0.23), 0.46, 0.46, seed=430, rough=0.015, chamfer=0.04)
    # inverted-V rafters + gable boards + sign plate
    for sg in (-1, 1):
        timber(mb, (sg * 2.55, -0.05, ht + 0.4), (sg * 0.02, -0.05, 4.5), 0.26, 0.26, up=(0, 1, 0), seed=431 + sg)
    for k in range(-8, 9):
        x = k * 0.27
        ztop = 4.5 - abs(x) * (4.5 - ht - 0.45) / 2.55 - 0.05
        if ztop < ht + 0.6 or k == 5:
            continue
        plank(mb, (x, 0.04, ht + 0.42), (x, 0.04, ztop - r.uniform(0, 0.12)), 0.26, 0.045, 'MNF_WoodPlanks',
              up=(0, 1, 0), seed=440 + k, jag1=r.uniform(0.02, 0.1))
    plate_c = Vector((0, -0.21, 4.02))
    obox(mb, plate_c + Vector((0, 0.02, 0)), Vector((0, -1, 0)), Z, (0.86, 0.025, 0.86), 'MNF_MetalRusted', bevel=0.006,
         jitter=0.004, seed=3)
    for bx, bz in ((-0.38, -0.38), (0.38, -0.38), (-0.38, 0.38), (0.38, 0.38)):
        bolt(mb, plate_c + Vector((bx, 0.008, bz)), (0, -1, 0), r=0.018)
    # boards nailed across the upper corners / hanging
    plank(mb, (1.75, -0.24, 2.55), (0.75, -0.25, 3.25), 0.2, 0.04, 'MNF_WoodPlanks', up=(0, -1, 0), seed=450)
    plank(mb, (-0.95, -0.26, 3.28), (-0.82, -0.3, 2.05), 0.2, 0.04, 'MNF_WoodPlanks', up=(0, -1, 0), seed=451,
          jag1=0.12)
    plank(mb, (-1.75, -0.24, 2.9), (-1.2, -0.25, 3.25), 0.2, 0.04, 'MNF_WoodPlanks', up=(0, -1, 0), seed=452, jag1=0.1)
    # --- tunnel lining going into the hill (+Y) ---
    for k, y in enumerate((1.7, 3.4)):
        S.support_set(mb, y=y, seed=460 + k, cracked=(k == 1), lagging=False, brackets=(k == 0), wedges=False,
                      side_lag=False)
    for sg in (-1, 1):
        x = sg * (hw + 0.26 + 0.05)
        for k in range(7):
            if r.random() < 0.18:
                continue
            z = 0.25 + k * 0.45
            plank(mb, (x, 0.25, z), (x, 4.0, z + r.uniform(-0.04, 0.04)), 0.3, 0.05, 'MNF_WoodPlanks', up=(sg, 0, 0),
                  seed=470 + k + sg * 20, jag1=r.uniform(0, 0.3))
    for k in range(13):
        if r.random() < 0.15:
            continue
        x = -1.9 + k * 0.32
        plank(mb, (x, 0.25, ht + 0.34), (x, 4.0, ht + 0.34 + r.uniform(-0.03, 0.03)), 0.28, 0.05, 'MNF_WoodPlanks',
              seed=490 + k, jag1=r.uniform(0, 0.4))
    # floor
    add_box(mb, (3.8, 3.8, 0.15), Matrix.Translation((0, 2.1, -0.075)), 'MNF_Mud', tile=2.0, jitter=0.0)
    # --- rails leading in ---
    S.track(mb, S.straight_path((0.05, 4.0, 0), (0.015, -1, 0)), 7.0, seed=42, spacing=0.6, first=0.3,
            plates=False, skip=(8, 10), broken=(4, 9), extra_jitter=2.5, z0=-0.045)
    # scattered planks
    for k in range(5):
        a = Vector((r.uniform(-3.2, 3.2), r.uniform(-3.5, -0.6), 0.03))
        if abs(a.x) < 0.8:
            a.x += 1.6 * (1 if a.x >= 0 else -1)
        d = Quaternion(Z, r.uniform(0, 6.28)) @ Vector((1, 0, 0))
        plank(mb, a, a + d * r.uniform(1.0, 2.2), 0.22, 0.045, 'MNF_WoodPlanks', seed=500 + k, jag1=0.15, warp=0.02)
    plank(mb, (-2.45, -0.7, 0.0), (-2.2, -0.32, 2.1), 0.24, 0.05, 'MNF_WoodPlanks', up=(0, -1, 0), seed=510)
    # --- rocks merging the portal into the hillside ---
    hullL, hullR, hullT = [], [], []
    S.rubble(mb, (-3.6, 0.9, 0), 1.4, 8, 43, 'MNF_RockDry', sizes=(0.4, 1.4), height=2.3, moss='MNF_Moss',
             hull_pts=hullL, bevel_min=0.9)
    S.rubble(mb, (3.6, 0.9, 0), 1.4, 8, 44, 'MNF_RockDry', sizes=(0.4, 1.4), height=2.0, moss='MNF_Moss',
             hull_pts=hullR, bevel_min=0.9)
    for k, (x, sz) in enumerate(((-1.9, 1.7), (1.7, 1.9))):
        bm = H.cut_rock(45 + k, (sz * 1.3, sz, sz * 0.8), cuts=9, subdiv=0, sink=0.0)
        n0 = len(mb.v)
        rock_to_mb(mb, bm, M((x, 1.7 + k * 0.2, 3.3), (0, r.uniform(-10, 10), r.uniform(0, 90))),
                   'MNF_RockDry', 'MNF_Moss', moss_thresh=0.62, seed=45 + k)
        hullT.extend(Vector(v) for v in mb.v[n0:])
        bm.free()
    ob = top(mb, 'MineEntrance', coll, sharp=40)
    board = MB()
    add_card(board, plate_c + Vector((0, -0.006, -0.36)), (0, 0, 1), (1, 0, 0), 0.72, 0.72, 'MNF_Signs', segs=1)
    H.child_mesh(ob, 'Board', board, plate_c + Vector((0, -0.006, 0)))
    H.col_box(ob, 'COL_Post_L', (-2.16, -0.2, 0), (-1.75, 0.2, ht))
    H.col_box(ob, 'COL_Post_R', (1.75, -0.2, 0), (2.16, 0.2, ht))
    H.col_box(ob, 'COL_Header', (-2.6, -0.25, ht), (2.6, 0.25, 4.5))
    H.col_box(ob, 'COL_Wall_L', (-2.35, 0.2, 0), (-1.75, 4.0, ht + 0.4))
    H.col_box(ob, 'COL_Wall_R', (1.75, 0.2, 0), (2.35, 4.0, ht + 0.4))
    H.col_box(ob, 'COL_Ceiling', (-2.35, 0.2, ht), (2.35, 4.0, ht + 0.45))
    H.col_box(ob, 'COL_Floor', (-1.9, 0.2, -0.15), (1.9, 4.0, 0.0))
    H.col_hull(ob, 'COL_RocksL_CONVEX', hullL)
    H.col_hull(ob, 'COL_RocksR_CONVEX', hullR)
    H.col_hull(ob, 'COL_RocksTop_CONVEX', hullT)
    NOTES['MineEntrance'] = ('Timber mine portal, 5 m wide x 4.5 m tall; opening 3.5 x 3.2 m (= Kit_Mine SupportFrame). '
                             'Pivot = bottom centre of the opening at the portal face; -Y faces the forest; a 4 m timbered '
                             'tunnel section runs into +Y (two support sets, wall/ceiling lagging, mud floor top at z=0), '
                             'continue with the mine level from y=4. Rails from y=+4 to y=-3 (rail top ~z=0.15). Child '
                             '`Board` = 0.72 m square quad (MNF_Signs, UV 0..1) on the rusted plate, facing -Y, pivot at '
                             'its centre. Rock piles at both sides/top blend into cliffs.')
    return ob


# =============================================================================================
# Deadwood
# =============================================================================================
def _up_normal(center, up=0.8):
    c = Vector(center)

    def fn(p):
        o = Vector((p.x - c.x, p.y - c.y, 0))
        o = o.normalized() if o.length > 1e-4 else Vector((0, 0, 0))
        return (o * 0.55 + Vector((0, 0, up))).normalized()
    return fn


def bracket_fungus(mb, pos, outward, size, mat='MNF_Teeth'):
    """Half-disc shelf fungus stuck to a trunk."""
    o = Vector(outward).normalized()
    side = o.cross(Vector((0, 0, 1))).normalized()
    pts = []
    c = Vector(pos)
    n = 7
    top_ids, bot_ids = [], []
    for k in range(n + 1):
        a = math.pi * k / n
        d = side * math.cos(a) * size + o * math.sin(a) * size * 0.7
        top_ids.append(mb.av(c + d + Vector((0, 0, size * 0.18 * math.sin(a)))))
        bot_ids.append(mb.av(c + d * 0.97 - Vector((0, 0, size * 0.08))))
    ct = mb.av(c + o * size * 0.05 + Vector((0, 0, size * 0.12)))
    cb = mb.av(c - Vector((0, 0, size * 0.08)))
    for k in range(n):
        mb.face([ct, top_ids[k + 1], top_ids[k]], [(0.5, 0.5), (0.5 + 0.5 * math.cos(math.pi * (k + 1) / n), 1),
                                                    (0.5 + 0.5 * math.cos(math.pi * k / n), 1)], mat, True)
        mb.face([top_ids[k], top_ids[k + 1], bot_ids[k + 1], bot_ids[k]], [(k / n, 0), ((k + 1) / n, 0),
                                                                            ((k + 1) / n, 0.1), (k / n, 0.1)], mat, True)
        mb.face([cb, bot_ids[k], bot_ids[k + 1]], [(0.5, 0.5), (0, 0), (1, 0)], 'MNF_Gums', True)


@builder
def Stump(coll):
    r = rng(51)
    mb = MB()
    br = T.Branch([Vector((0, 0, -0.1)), Vector((0, 0, 0.15)), Vector((0.01, 0, 0.38)), Vector((0.02, 0.01, 0.58))],
                  [0.44, 0.39, 0.36, 0.35], 0, 14)
    rings = T.sweep(mb, br, 'MNF_BarkPine', tile_v=1.5, noise_fn=T.bark_noise(0.08, 3, 0.04, 51, flare=0.35,
                                                                               flare_h=0.2, br=br), apex=False, cap1=True)
    for vi in rings[-1]:
        mb.v[vi] = mb.v[vi] + Vector((0, 0, r.uniform(-0.12, 0.14)))
    mb.fm[-1] = mb.mi('MNF_WoodRotten')
    # splinters on the rim
    for k in range(5):
        a = r.uniform(0, 6.28)
        base = Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 0.5))
        add_beam(mb, base, base + Vector((math.cos(a) * 0.04, math.sin(a) * 0.04, r.uniform(0.15, 0.32))),
                 r.uniform(0.04, 0.08), 0.03, 'MNF_WoodRotten', up=(math.cos(a), math.sin(a), 0), taper=0.12,
                 chamfer=0.0, tile=1.5)
    T.add_roots(mb, (0, 0, 0), 0.38, 5, 52, 'MNF_BarkPine', length=(0.4, 0.8), rad=(0.3, 0.42), segs=5, nseg=4)
    for k, (a, z, sz) in enumerate(((0.6, 0.32, 0.12), (1.0, 0.22, 0.09), (-2.2, 0.4, 0.1))):
        o = Vector((math.cos(a), math.sin(a), 0))
        bracket_fungus(mb, o * 0.37 + Vector((0, 0, z)), o, sz)
    ob = top(mb, 'Stump', coll, sharp=50)
    H.col_box(ob, 'COL_Stump', (-0.4, -0.4, 0), (0.4, 0.4, 0.55))
    NOTES['Stump'] = 'Snapped pine stump ~0.6 m, jagged rotten top, roots, pale bracket fungi (MNF_Teeth/MNF_Gums).'
    return ob


def _log_tube(mb, pts, radii, seed, bark='MNF_BarkPine', moss=True, segs=10, cap0=True, jag_end=0.0):
    br = T.Branch([Vector(p) for p in pts], radii, 0, segs)
    off = seed * 1.7

    def face_fn(i, j, dv):
        if moss and dv.z > 0.45 + 0.25 * noise.noise(Vector((i * 0.7 + off, j * 0.5, 0))):
            return 'MNF_Moss'
        return bark
    rings = add_tube(mb, br.pts, br.radii, segs, bark, tile_v=1.5, urep=max(1, round(2 * math.pi * radii[0] / 1.5)),
                     cap0=cap0, cap1=True, noise_fn=T.bark_noise(0.07, 0, 0, seed, br=None), face_mat_fn=face_fn)
    mb.fm[-1] = mb.mi('MNF_WoodRotten')
    if cap0:
        mb.fm[-2] = mb.mi('MNF_WoodRotten')
    if jag_end:
        r = rng(seed)
        last = rings[-1]
        t = (br.pts[-1] - br.pts[-2]).normalized()
        for vi in last:
            mb.v[vi] = mb.v[vi] + t * r.uniform(-jag_end, jag_end)
    return br


@builder
def Log(coll):
    r = rng(61)
    mb = MB()
    R = 0.24
    pts = [Vector((-1.6 + 3.2 * k / 6, 0.03 * math.sin(k), R - 0.03)) for k in range(7)]
    br = _log_tube(mb, pts, [R * (1 - 0.12 * k / 6) for k in range(7)], 61, jag_end=0.12)
    # branch stubs
    for k, t in enumerate((0.3, 0.62)):
        p, tan, rad = br.sample(t)
        d = Vector((0.3, -0.6 if k else 0.7, 0.75)).normalized()
        sb = T.Branch([p, p + d * 0.25, p + d * 0.42], [rad * 0.3, rad * 0.26, rad * 0.22], 1, 6)
        T.sweep(mb, sb, 'MNF_BarkPine', tile_v=1.0, apex=False, cap1=True)
        mb.fm[-1] = mb.mi('MNF_WoodRotten')
    bracket_fungus(mb, (0.5, -0.22, 0.24), (0, -1, 0), 0.08)
    bracket_fungus(mb, (0.62, -0.2, 0.15), (0, -1, 0), 0.06)
    ob = top(mb, 'Log', coll, sharp=50)
    H.col_box(ob, 'COL_Log', (-1.6, -0.24, 0), (1.6, 0.24, 0.45))
    NOTES['Log'] = '3.2 m fallen pine log along X, moss on top, one snapped end, branch stubs, shelf fungi.'
    return ob


@builder
def FallenTree(coll):
    r = rng(62)
    mb = MB()
    n = 10
    pts, radii = [], []
    for k in range(n + 1):
        t = k / n
        x = -6.0 + 12.0 * t
        rad = 0.44 - 0.24 * t
        z = 0.78 - rad - 0.12 * t + 0.02 * math.sin(t * 9)     # top surface 0.78 -> 0.66
        pts.append(Vector((x, 0.12 * math.sin(t * 3.1), z)))
        radii.append(rad)
    br = _log_tube(mb, pts, radii, 62, cap0=False, jag_end=0.25)
    # root plate at -X end: earth disc with roots
    rp = Vector((-6.05, 0, 0.9))
    disc = []
    nseg = 14
    for k in range(nseg):
        a = 2 * math.pi * k / nseg
        rr = 1.25 * (1 + 0.18 * noise.noise(Vector((math.cos(a) * 2, math.sin(a) * 2, 3.0))))
        disc.append(Vector((0, math.cos(a) * rr, math.sin(a) * rr * 0.85)))
    front = [mb.av(rp + Vector((-0.15, 0, 0)) + d * 1.0) for d in disc]
    back = [mb.av(rp + Vector((0.35, 0, 0)) + d * 0.8) for d in disc]
    cf = mb.av(rp + Vector((-0.3, 0, 0)))
    cb = mb.av(rp + Vector((0.5, 0, 0)))
    for k in range(nseg):
        kn = (k + 1) % nseg
        u0, u1 = k / nseg * 4, (k + 1) / nseg * 4
        mb.face([front[k], front[kn], back[kn], back[k]], [(u0, 0), (u1, 0), (u1, 0.4), (u0, 0.4)], 'MNF_Mud', True)
        mb.face([cf, front[kn], front[k]], [(0.5, 0.5), (0.5 + 0.5 * math.cos(2 * math.pi * kn / nseg),
                                                          0.5 + 0.5 * math.sin(2 * math.pi * kn / nseg)),
                                            (0.5 + 0.5 * math.cos(2 * math.pi * k / nseg),
                                             0.5 + 0.5 * math.sin(2 * math.pi * k / nseg))], 'MNF_Mud', True)
        mb.face([cb, back[k], back[kn]], [(0.5, 0.5), (0, 0), (1, 0)], 'MNF_Mud', True)
    for k in range(16):
        a = 2 * math.pi * k / 16 + r.uniform(-0.2, 0.2)
        rr = r.uniform(0.2, 1.0)
        start = rp + Vector((-0.1, math.cos(a) * rr, math.sin(a) * rr * 0.85))
        d = Vector((-r.uniform(0.3, 0.9), math.cos(a) * 0.8, math.sin(a) * 0.7)).normalized()
        rpts = T.walk(start, d, r.uniform(0.6, 1.6), 4, r, wander=0.45, freq=1.5, gravity=0.2, keep_above=-1)
        T.sweep(mb, T.Branch(rpts, T.taper(len(rpts), r.uniform(0.04, 0.1), 0.008), 2, 4), 'MNF_BarkPine',
                tile_v=1.0)
    for k in range(4):   # clods of earth/stones in the root plate
        bm = H.cut_rock(620 + k, (0.35, 0.3, 0.3), cuts=6, subdiv=0, sink=0.0, bevel=0.0)
        a = r.uniform(0, 6.28)
        rock_to_mb(mb, bm, M(rp + Vector((-0.25, math.cos(a) * 0.7, math.sin(a) * 0.6)), (0, 0, r.uniform(0, 90))),
                   'MNF_RockDry', None, tile=3.0)
        bm.free()
    # broken branches along the trunk (kept off the walking line on top)
    for k in range(7):
        t = 0.15 + 0.8 * k / 7 + r.uniform(-0.03, 0.03)
        p, tan, rad = br.sample(t)
        side = 1 if k % 2 else -1
        d = Vector((r.uniform(-0.3, 0.5), side * 1.0, r.uniform(-0.2, 0.9))).normalized()
        L = r.uniform(0.3, 0.6) if k % 3 else r.uniform(2.2, 3.2)
        bp = T.walk(p + d * rad * 0.5, d, L, 3 if L < 1 else 5, r, wander=0.3, freq=0.9, gravity=0.05, keep_above=0.05)
        b = T.Branch(bp, T.taper(len(bp), rad * (0.32 if L < 1 else 0.42), rad * 0.2 if L < 1 else 0.01), 1, 5)
        T.sweep(mb, b, 'MNF_BarkDead', tile_v=1.2, apex=L >= 1, cap1=L < 1)
        if L < 1:
            mb.fm[-1] = mb.mi('MNF_WoodRotten')
    ob = top(mb, 'FallenTree', coll, sharp=50)
    H.col_box(ob, 'COL_Log', (-6.0, -0.38, 0), (6.0, 0.38, 0.74))
    H.col_box(ob, 'COL_RootPlate', (-6.6, -1.3, 0), (-5.6, 1.3, 2.0))
    NOTES['FallenTree'] = ('12 m fallen pine along X (root plate at -X), walkable top surface ~0.78 m -> 0.66 m, usable '
                           'as a bridge. COL_Log = capsule-like box over the trunk (top 0.74 m), COL_RootPlate.')
    return ob


# =============================================================================================
# Undergrowth (alpha cards; no colliders)
# =============================================================================================
def _bush(name, coll, seed, height, width, ncards, stems):
    r = rng(seed)
    mb = MB()
    for k in range(stems):
        a = r.uniform(0, 6.28)
        d = Vector((math.cos(a) * 0.5, math.sin(a) * 0.5, 1)).normalized()
        sp = T.walk((r.uniform(-0.1, 0.1), r.uniform(-0.1, 0.1), -0.05), d, height * r.uniform(0.6, 0.95), 4, r,
                    wander=0.35, freq=1.2, keep_above=-1)
        T.sweep(mb, T.Branch(sp, T.taper(len(sp), 0.025, 0.005), 1, 4), 'MNF_BarkDead', tile_v=1.0)
    c = Vector((0, 0, height * 0.45))
    nfn = _up_normal((0, 0, 0), 0.7)

    def nrm(p):
        o = (p - c)
        return (o.normalized() * 0.7 + Vector((0, 0, 0.5))).normalized()
    for k in range(ncards):
        # point on a squashed hemisphere shell
        while True:
            v = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.2, 1)))
            if 0.35 < v.length <= 1.0:
                break
        p = Vector((v.x * width / 2, v.y * width / 2, max(0.05, (v.z * 0.55 + 0.42) * height)))
        out = (p - Vector((0, 0, height * 0.2))).normalized()
        up = (out + Vector((0, 0, 0.6))).normalized()
        side = Quaternion(up, r.uniform(0, 6.28)) @ (up.cross(Vector((0, 0, 1))).normalized()
                                                     if abs(up.z) < 0.98 else Vector((1, 0, 0)))
        sz = r.uniform(0.45, 0.7) * (width / 1.6) ** 0.5
        add_card(mb, p - up * sz * 0.45, up, side, sz, sz, 'MNF_FoliageLeaf', bend=sz * 0.12, segs=1, cnormal=nrm)
    ob = top(mb, name, coll)
    NOTES[name] = ('Dense shrub %.1f m tall, %.1f m wide: woody stems + %d leaf cards (MNF_FoliageLeaf, full 0..1 UV, '
                   'custom spherical normals). No collider wanted (builder: do not auto-generate).'
                   % (height, width, ncards))
    return ob


@builder
def Bush_A(coll):
    return _bush('Bush_A', coll, 71, 1.4, 1.9, 64, 7)


@builder
def Bush_B(coll):
    return _bush('Bush_B', coll, 72, 0.9, 1.3, 40, 5)


@builder
def Fern(coll):
    r = rng(73)
    mb = MB()
    nrm = _up_normal((0, 0, 0), 0.9)
    n = 7
    for k in range(n):
        a = k * 2 * math.pi / n + r.uniform(-0.2, 0.2)
        o = Vector((math.cos(a), math.sin(a), 0))
        tilt = math.radians(r.uniform(22, 42))
        up = (o * math.sin(tilt) + Vector((0, 0, math.cos(tilt)))).normalized()
        side = Vector((-o.y, o.x, 0))
        h = r.uniform(0.75, 0.95)
        add_card(mb, o * 0.04, up, side, h * 1.0, h, 'MNF_Fern', bend=h * 0.18, segs=2, cnormal=nrm)
    for k in range(2):
        a = k * math.pi / 2 + 0.4
        add_card(mb, (0, 0, -0.02), (0, 0, 1), (math.cos(a), math.sin(a), 0), 0.7, 0.62, 'MNF_Fern', bend=0.05,
                 segs=1, cnormal=nrm)
    ob = top(mb, 'Fern', coll)
    NOTES['Fern'] = ('Fern clump ~0.6 m tall, 1.3 m wide: 7 outward-arching + 2 crossed upright cards (MNF_Fern, '
                     'cluster base at V=0). No collider.')
    return ob


@builder
def GrassTuft(coll):
    r = rng(74)
    mb = MB()
    nrm = _up_normal((0, 0, 0), 1.2)
    for k in range(3):
        a = k * math.pi / 3 + r.uniform(-0.1, 0.1)
        add_card(mb, (0, 0, -0.02), (0, 0, 1), (math.cos(a), math.sin(a), 0), 0.6, 0.5, 'MNF_Grass', bend=0.04,
                 segs=1, cnormal=nrm)
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.5
        o = Vector((math.cos(a), math.sin(a), 0))
        up = (o * 0.45 + Vector((0, 0, 1))).normalized()
        add_card(mb, o * 0.05 + Vector((0, 0, -0.02)), up, Vector((-o.y, o.x, 0)), 0.45, 0.38, 'MNF_Grass', bend=0.05,
                 segs=1, cnormal=nrm)
    ob = top(mb, 'GrassTuft', coll)
    NOTES['GrassTuft'] = 'Grass tuft ~0.5 m: 3 crossed + 3 splayed cards (MNF_Grass). No collider.'
    return ob


def mushroom(mb, base, h, cap_r, lean, seed, cap_mat='MNF_Teeth'):
    r = rng(seed)
    b = Vector(base)
    d = (Vector((lean[0], lean[1], 1))).normalized()
    sp = [b, b + d * h * 0.5 + Vector((r.uniform(-1, 1) * h * 0.05, 0, 0)), b + d * h]
    add_tube(mb, sp, [cap_r * 0.28, cap_r * 0.22, cap_r * 0.2], 5, 'MNF_Teeth', tile_v=0.3, cap1=False)
    top_p = sp[-1]
    prof = [(0.0, -0.02, 0.3), (0.0, 0.0, 1.0), (0.3, 0.0, 0.95), (0.7, 0.0, 0.55), (1.0, 0.0, 0.0)]
    pts = [top_p + d * (cap_r * (0.15 + 0.6 * t)) for t, _, _ in prof]
    rad = [cap_r * f for _, _, f in prof]
    pts[0] = top_p - d * cap_r * 0.02
    rad[0] = cap_r * 0.3
    add_tube(mb, pts, rad, 8, cap_mat, tile_v=0.2, apex=True, cap0=False)
    # gills under the cap
    ring = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        ring.append(mb.av(top_p + Vector((math.cos(a), math.sin(a), 0)) * cap_r * 0.98 + d * cap_r * 0.13))
    cen = mb.av(top_p + d * cap_r * 0.02)
    for k in range(8):
        mb.face([cen, ring[(k + 1) % 8], ring[k]], [(0.5, 0.5), (1, 0), (0, 0)], 'MNF_Gums', True)


@builder
def MushroomCluster(coll):
    r = rng(75)
    mb = MB()
    # a small rotten log piece they grow from
    _log_tube(mb, [(-0.28, 0.05, 0.08), (0.0, 0.02, 0.09), (0.3, 0.0, 0.07)], [0.1, 0.095, 0.085], 75,
              bark='MNF_WoodRotten', moss=True, segs=8)
    for k in range(7):
        a = r.uniform(0, 6.28)
        d = r.uniform(0.05, 0.3)
        base = Vector((math.cos(a) * d, math.sin(a) * d * 0.8 - 0.08, 0.0))
        if abs(base.y - 0.03) < 0.1 and abs(base.x) < 0.3:
            base.z = 0.12
        h = r.uniform(0.05, 0.16) * (1.6 if k == 0 else 1.0)
        mushroom(mb, base, h, h * r.uniform(0.45, 0.7), (r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3)), 750 + k)
    ob = top(mb, 'MushroomCluster', coll, sharp=60)
    NOTES['MushroomCluster'] = ('Pale sickly mushrooms (MNF_Teeth caps/stems, MNF_Gums gills) on a rotten log stub; '
                                'geometry, not cards (no mushroom card texture in the catalog). No collider.')
    return ob


# =============================================================================================
# Fences & signs
# =============================================================================================
def barbed_wire(mb, pts, seed, spacing=0.13, mat='MNF_MetalRusted'):
    r = rng(seed)
    pts = [Vector(p) for p in pts]
    add_tube(mb, pts, [0.0035] * len(pts), 3, mat, tile_v=0.5, cap1=False, smooth=False)
    br = T.Branch(pts, [0.0035] * len(pts), 3, 3)
    n = max(1, int(br.length / spacing))
    for k in range(n):
        p, t, _ = br.sample((k + 0.5) / n)
        for a in (r.uniform(0, 3.14), None):
            if a is None:
                a = prev + 1.57
            prev = a
            d = Quaternion(t, a) @ T._perp(t)
            w = t * 0.004
            ids = [mb.av(p - d * 0.024 - w), mb.av(p - d * 0.024 + w), mb.av(p + d * 0.024 + w),
                   mb.av(p + d * 0.024 - w)]
            mb.face(ids, [(0, 0), (0.05, 0), (0.05, 0.1), (0, 0.1)], mat)


def sag(a, b, n, depth):
    a = Vector(a); b = Vector(b)
    return [a.lerp(b, k / n) - Vector((0, 0, depth * math.sin(math.pi * k / n))) for k in range(n + 1)]


def fence_post(mb, x, h=1.38, seed=0, snapped=False, lean=(0, 0)):
    from kitB_shared import timber
    top_p = Vector((x + lean[0], lean[1], h))
    timber(mb, (x, 0, -0.15), top_p, 0.13, 0.13, up=(0, 1, 0), seed=seed, rough=0.0, chamfer=0.015,
           jag1=0.12 if snapped else 0.0)
    if not snapped:
        d = (top_p - Vector((x, 0, -0.15))).normalized()
        add_beam(mb, top_p - d * 0.005, top_p + d * 0.1, 0.13, 0.13, 'MNF_WoodBeam', up=(0, 1, 0), taper=0.08,
                 chamfer=0.0, tile=2.0, seed=seed)


@builder
def Fence_Section(coll):
    from kitB_shared import plank
    mb = MB()
    for x in (-1.25, 1.25):
        fence_post(mb, x, seed=900)       # identical, symmetric posts: chained sections overlap cleanly
    for k, z in enumerate((0.42, 0.88)):
        plank(mb, (-1.33, -0.085, z), (1.33, -0.085, z + 0.01 * (k - 0.5)), 0.15, 0.035, 'MNF_WoodPlanks', up=(0, -1, 0),
              seed=901 + k, warp=0.01)
        for x in (-1.25, 1.25):
            S.bolt(mb, (x, -0.103, z), (0, -1, 0), r=0.01, h=0.006)
    for k, z in enumerate((1.1, 1.29)):
        barbed_wire(mb, sag((-1.25, -0.07, z), (1.25, -0.07, z), 8, 0.035), 910 + k)
    ob = top(mb, 'Fence_Section', coll, sharp=40)
    H.col_box(ob, 'COL_Fence', (-1.32, -0.11, 0), (1.32, 0.07, 1.45))
    NOTES['Fence_Section'] = ('2.5 m weathered mining-company fence along X: square posts at x=+-1.25 (identical and '
                              'symmetric so sections chain every 2.5 m and may be rotated 180), two boards and two '
                              'barbed-wire strands on the -Y face.')
    return ob


@builder
def Fence_Broken(coll):
    from kitB_shared import plank
    r = rng(92)
    mb = MB()
    fence_post(mb, -1.25, seed=900)
    fence_post(mb, 1.25, h=0.75, seed=920, snapped=True, lean=(0.28, -0.12))
    plank(mb, (-1.33, -0.085, 0.42), (1.3, -0.1, 0.36), 0.15, 0.035, 'MNF_WoodPlanks', up=(0, -1, 0), seed=921,
          warp=0.02)
    plank(mb, (-1.33, -0.085, 0.88), (-0.25, -0.09, 0.86), 0.15, 0.035, 'MNF_WoodPlanks', up=(0, -1, 0), seed=922,
          jag1=0.15)
    plank(mb, (-0.2, -0.16, 0.84), (0.75, -0.32, 0.02), 0.15, 0.035, 'MNF_WoodPlanks', up=(0, -1, 0), seed=923,
          jag0=0.15)
    plank(mb, (0.6, -0.7, 0.02), (1.7, -0.55, 0.02), 0.15, 0.035, 'MNF_WoodPlanks', seed=924, jag0=0.1)
    barbed_wire(mb, sag((-1.25, -0.07, 1.29), (1.45, -0.18, 0.72), 10, 0.3), 925)
    # cut strand lying on the ground with a coil
    pts = sag((-1.25, -0.07, 1.1), (-0.3, -0.35, 0.04), 6, 0.1)
    c = Vector((0.1, -0.45, 0.04))
    for k in range(1, 18):
        a = k * 0.55
        rr = 0.22 + 0.03 * math.sin(k)
        pts.append(c + Vector((math.cos(a + 3.3) * rr, math.sin(a + 3.3) * rr * 0.8, 0.02 + 0.03 * math.sin(k * 1.7))))
    barbed_wire(mb, pts, 926)
    ob = top(mb, 'Fence_Broken', coll, sharp=40)
    H.col_box(ob, 'COL_Fence', (-1.32, -0.11, 0), (1.32, 0.07, 1.0))
    NOTES['Fence_Broken'] = ('Broken 2.5 m fence: right post snapped and leaning, top board broken and hanging, wire '
                             'sagging / cut and coiled on the ground. Same post spacing as Fence_Section.')
    return ob


def board_child(ob, center, size, normal=(0, -1, 0)):
    """Board quad (MNF_Signs, UV 0..1) facing `normal` (-Y), pivot at its centre."""
    c = Vector(center)
    b = MB()
    add_card(b, c - Vector((0, 0, size / 2)), (0, 0, 1), (1, 0, 0), size, size, 'MNF_Signs', segs=1)
    return H.child_mesh(ob, 'Board', b, c)


@builder
def SignPost(coll):
    from kitB_shared import timber, plank, bolt
    r = rng(93)
    mb = MB()
    timber(mb, (0, 0, -0.2), (0.03, 0.02, 2.25), 0.12, 0.12, up=(0, 1, 0), seed=930, chamfer=0.015)
    add_beam(mb, (0.03, 0.02, 2.245), (0.032, 0.02, 2.33), 0.12, 0.12, 'MNF_WoodBeam', up=(0, 1, 0), taper=0.1,
             chamfer=0.0)
    zc = 1.82
    for k in range(3):
        z = zc - 0.21 + k * 0.21
        plank(mb, (-0.33, -0.08, z), (0.33, -0.08, z + r.uniform(-0.01, 0.01)), 0.2, 0.03, 'MNF_WoodPlanks',
              up=(0, -1, 0), seed=931 + k, jag1=0.03 if k == 2 else 0.0)
    # back cleat
    plank(mb, (0.015, -0.06, zc - 0.32), (0.025, -0.06, zc + 0.33), 0.08, 0.025, 'MNF_WoodPlanks', up=(0, -1, 0),
          seed=935)
    for x in (-0.26, 0.26):
        for z in (zc - 0.21, zc + 0.21):
            bolt(mb, (x, -0.096, z), (0, -1, 0), r=0.008, h=0.004)
    ob = top(mb, 'SignPost', coll, sharp=40)
    board_child(ob, (0, -0.1, zc), 0.56)
    H.col_box(ob, 'COL_Post', (-0.08, -0.08, 0), (0.1, 0.1, 2.3))
    H.col_box(ob, 'COL_Sign', (-0.34, -0.11, zc - 0.32), (0.34, -0.06, zc + 0.32))
    NOTES['SignPost'] = ('Wooden trail post 2.3 m with a 0.66 m board panel. Child `Board`: 0.56 m square quad '
                         '(MNF_Signs, UV 0..1 - Unity assigns the atlas cell) facing -Y, pivot at its centre '
                         '(0, -0.1, %.2f).' % zc)
    return ob


@builder
def WarningBoard(coll):
    from kitB_shared import timber, plank, bolt
    r = rng(94)
    mb = MB()
    for sx in (-0.85, 0.85):
        timber(mb, (sx, 0, -0.3), (sx + r.uniform(-0.03, 0.03), 0.01, 2.55), 0.15, 0.15, up=(0, 1, 0), seed=940,
               chamfer=0.02)
    zc = 1.65
    n = 7
    for k in range(n):
        z = zc - 0.78 + (k + 0.5) * (1.56 / n)
        jl = 0.12 if k == 0 else 0.0
        plank(mb, (-1.0 + (0.18 if k == 0 else 0), -0.1, z), (1.0, -0.1, z + r.uniform(-0.015, 0.015)), 0.215, 0.035,
              'MNF_WoodPlanks', up=(0, -1, 0), seed=941 + k, jag0=jl, jag1=r.uniform(0, 0.05))
        for sx in (-0.85, 0.85):
            bolt(mb, (sx, -0.119, z), (0, -1, 0), r=0.009, h=0.004)
    plank(mb, (-1.08, -0.1, zc + 0.83), (1.08, -0.1, zc + 0.83), 0.09, 0.12, 'MNF_WoodPlanks', up=(0, 0, 1), seed=949)
    # diagonal back brace
    plank(mb, (-0.85, 0.1, 0.4), (0.85, 0.1, 2.3), 0.12, 0.04, 'MNF_WoodPlanks', up=(0, 1, 0), seed=950)
    ob = top(mb, 'WarningBoard', coll, sharp=40)
    board_child(ob, (0, -0.122, zc), 1.42)
    H.col_box(ob, 'COL_Board', (-1.1, -0.13, 0), (1.1, 0.13, 2.6))
    NOTES['WarningBoard'] = ('Large old warning board 2.0 x 1.6 m on two posts. Child `Board`: 1.42 m square quad '
                             '(MNF_Signs) facing -Y, pivot at its centre (0, -0.122, %.2f).' % zc)
    return ob


# =============================================================================================
# Camp
# =============================================================================================
def _ss(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


@builder
def Tent(coll):
    r = rng(81)
    mb = MB()
    nu, nv = 12, 10
    L, W = 2.3, 0.85
    rows = []
    for j in range(nv + 1):
        v = j / nv
        y = -L / 2 + L * v
        h = 0.3 + 0.86 * _ss(v * 1.35 - 0.2)
        row = []
        for i in range(nu + 1):
            u = -1 + 2 * i / nu
            z = h * (1 - abs(u)) ** 1.12
            x = u * W * (1.0 + 0.35 * (1 - h / 1.16))
            z += 0.05 * noise.noise(Vector((x * 3, y * 3, 0.5))) * (1 - abs(u)) * (1.4 - v)
            z = max(z, 0.012)
            row.append(Vector((x, y, z)))
        rows.append(row)
    torn = set()
    for j in range(3, 6):
        for i in range(8, 11):
            if r.random() < 0.75:
                torn.add((i, j))
    ids = [[mb.av(p) for p in row] for row in rows]
    t = 1.5

    def uv(p):
        return (p.x / t + p.y * 0.0, (p.y + abs(p.x) * 0.0 + p.z) / t)
    for j in range(nv):
        for i in range(nu):
            if (i, j) in torn:
                continue
            q = [ids[j][i], ids[j][i + 1], ids[j + 1][i + 1], ids[j + 1][i]]
            uvs = [(i / nu * 2.2 / t, j / nv * L / t), ((i + 1) / nu * 2.2 / t, j / nv * L / t),
                   ((i + 1) / nu * 2.2 / t, (j + 1) / nv * L / t), (i / nu * 2.2 / t, (j + 1) / nv * L / t)]
            mb.face(q, uvs, 'MNF_FabricCanvas', True)
            mb.face(q[::-1], uvs[::-1], 'MNF_FabricCanvas', True)
    # torn flap hanging into the hole
    fl = [rows[6][9], rows[6][10], rows[5][10] + Vector((0.08, 0, -0.25)), rows[5][9] + Vector((0.05, 0, -0.3))]
    fi = [mb.av(p) for p in fl]
    mb.face(fi, [(0, 0), (0.2, 0), (0.2, 0.2), (0, 0.2)], 'MNF_FabricCanvas', True)
    mb.face(fi[::-1], [(0, 0.2), (0.2, 0.2), (0.2, 0), (0, 0)], 'MNF_FabricCanvas', True)
    # back wall (closed end)
    back = rows[-1]
    gi = [mb.av(Vector((p.x * 0.95, p.y + 0.02, 0.0))) for p in back]
    for i in range(nu):
        q = [gi[i], gi[i + 1], ids[-1][i + 1], ids[-1][i]]
        uvs = [(i / nu * 1.4, 0), ((i + 1) / nu * 1.4, 0), ((i + 1) / nu * 1.4, back[i + 1].z / t), (i / nu * 1.4, back[i].z / t)]
        mb.face(q, uvs, 'MNF_FabricCanvas', True)
        mb.face(q[::-1], uvs[::-1], 'MNF_FabricCanvas', True)
    # poles, ropes, pegs
    add_cyl(mb, (0, L / 2 - 0.02, 0), (0, L / 2 - 0.02, 1.2), 0.018, 0.016, 6, 'MNF_WoodHandle', tile=0.5)
    add_cyl(mb, (0.45, -L / 2 - 0.5, 0.02), (-0.2, -L / 2 + 0.4, 0.05), 0.018, 0.016, 6, 'MNF_WoodHandle', tile=0.5)
    for a, b in (((0, L / 2, 1.18), (0, L / 2 + 1.0, 0.04)), ((0.0, -L / 2, 0.3), (0.3, -L / 2 - 0.9, 0.02))):
        pts = sag(a, b, 4, 0.04)
        add_tube(mb, pts, [0.006] * len(pts), 4, 'MNF_Rope', tile_v=0.5, cap1=False)
        add_beam(mb, Vector(b) - Vector((0, 0, 0.12)), Vector(b) + Vector((0, 0, 0.08)), 0.03, 0.03, 'MNF_WoodHandle',
                 taper=0.3, chamfer=0.0, tile=0.5)
    # crumpled blanket inside
    bl = []
    for j in range(5):
        row = []
        for i in range(5):
            x = -0.45 + 0.9 * i / 4 + r.uniform(-0.04, 0.04)
            y = 0.0 + 0.9 * j / 4
            row.append(mb.av((x, y, 0.025 + 0.06 * max(0, noise.noise(Vector((x * 4, y * 4, 2.0)))))))
        bl.append(row)
    for j in range(4):
        for i in range(4):
            mb.face([bl[j][i], bl[j][i + 1], bl[j + 1][i + 1], bl[j + 1][i]],
                    [(i / 4, j / 4), ((i + 1) / 4, j / 4), ((i + 1) / 4, (j + 1) / 4), (i / 4, (j + 1) / 4)],
                    'MNF_FabricBlanket', True)
    ob = top(mb, 'Tent', coll, sharp=60)
    H.col_box(ob, 'COL_Tent', (-1.0, -1.15, 0), (1.0, 1.2, 1.1))
    NOTES['Tent'] = ('Collapsed, torn A-frame canvas tent (front pole fallen, canvas double-sided, rip with a hanging '
                     'flap), guy ropes, pegs, old blanket inside.')
    return ob


@builder
def Campfire(coll):
    r = rng(82)
    mb = MB()
    n = 11
    for k in range(n):
        a = 2 * math.pi * k / n + r.uniform(-0.1, 0.1)
        sz = r.uniform(0.18, 0.28)
        bm = H.cut_rock(820 + k, (sz * 1.2, sz, sz * 0.75), cuts=6, subdiv=0, sink=0.25, bevel=0.05 if k % 2 else 0.0)
        rock_to_mb(mb, bm, M((math.cos(a) * 0.5, math.sin(a) * 0.5, 0), (0, 0, math.degrees(a) + r.uniform(-20, 20))),
                   'MNF_RockDry', None, tile=3.0)
        bm.free()
    # ash bed
    ring = []
    for k in range(12):
        a = 2 * math.pi * k / 12
        rr = 0.42 * (1 + 0.1 * noise.noise(Vector((math.cos(a) * 2, math.sin(a) * 2, 1.0))))
        ring.append(mb.av((math.cos(a) * rr, math.sin(a) * rr, 0.01)))
    c = mb.av((0, 0, 0.05))
    for k in range(12):
        mb.face([c, ring[k], ring[(k + 1) % 12]], [(0.5, 0.5), (0.5 + 0.5 * math.cos(2 * math.pi * k / 12),
                                                                0.5 + 0.5 * math.sin(2 * math.pi * k / 12)),
                                                   (0.5 + 0.5 * math.cos(2 * math.pi * (k + 1) / 12),
                                                    0.5 + 0.5 * math.sin(2 * math.pi * (k + 1) / 12))], 'MNF_Mud', True)
    # charred logs: collapsed teepee
    for k, (a0, a1, z1) in enumerate(((0.3, 0.3 + 3.14, 0.28), (1.9, 1.9 + 3.0, 0.22), (3.6, 3.6, 0.05),
                                      (5.0, 5.0 + 0.5, 0.05))):
        p0 = Vector((math.cos(a0) * 0.42, math.sin(a0) * 0.42, 0.05))
        p1 = Vector((math.cos(a1) * 0.12, math.sin(a1) * 0.12, z1)) if k < 2 else \
            p0 + Vector((math.cos(a0 + 2.2), math.sin(a0 + 2.2), 0)) * 0.5
        br = T.Branch([p0, p0.lerp(p1, 0.5) + Vector((0, 0, 0.02)), p1], [0.055, 0.05, 0.04], 1, 6)
        T.sweep(mb, br, 'MNF_BarkDead', tile_v=1.0, apex=False, cap1=True)
        mb.fm[-1] = mb.mi('MNF_Blackstone')
    for k in range(7):
        bm = H.cut_rock(830 + k, (0.07, 0.06, 0.04), cuts=6, subdiv=0, sink=0.0, bevel=0.0)
        a = r.uniform(0, 6.28); d = r.uniform(0.0, 0.3)
        rock_to_mb(mb, bm, M((math.cos(a) * d, math.sin(a) * d, 0.04), (0, 0, r.uniform(0, 90))), 'MNF_Blackstone', None,
                   tile=1.0)
        bm.free()
    ob = top(mb, 'Campfire', coll, sharp=45)
    H.empty(ob, 'SOCKET_Fire', (0, 0, 0.12))
    NOTES['Campfire'] = ('Stone ring (~1.2 m) with ash bed (MNF_Mud), charred collapsed logs (MNF_BarkDead, '
                         'MNF_Blackstone ends/charcoal). SOCKET_Fire at the fire centre (z=0.12). No collider '
                         '(stones are ankle height).')
    return ob


@builder
def CampLantern(coll):
    mb = MB()
    # bail (hanging point = pivot at the top)
    arc = [Vector((math.sin(a) * 0.08, 0, -0.1 + math.cos(a) * 0.1)) for a in [(-1.25 + 2.5 * k / 8) for k in range(9)]]
    add_tube(mb, arc, [0.0028] * 9, 4, 'MNF_MetalRusted', tile_v=0.3, cap1=False, smooth=False)
    add_cyl(mb, (0, 0, -0.085), (0, 0, -0.115), 0.02, 0.022, 8, 'MNF_MetalRusted', tile=0.3)
    add_cyl(mb, (0, 0, -0.115), (0, 0, -0.14), 0.024, 0.07, 10, 'MNF_MetalPainted_Red', tile=0.3, cap0=True)
    for z in (-0.142, -0.272):
        ring = [Vector((math.cos(a) * 0.068, math.sin(a) * 0.068, z)) for a in [k * 2 * math.pi / 10 for k in range(11)]]
        add_tube(mb, ring, [0.004] * 11, 4, 'MNF_MetalRusted', tile_v=0.3, cap1=False, smooth=False)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        g = [Vector((math.cos(a) * rr, math.sin(a) * rr, z)) for rr, z in ((0.068, -0.142), (0.08, -0.207), (0.068, -0.272))]
        add_tube(mb, g, [0.003] * 3, 3, 'MNF_MetalRusted', tile_v=0.3, cap1=False, smooth=False)
    glass = [Vector((0, 0, z)) for z in (-0.142, -0.17, -0.207, -0.245, -0.272)]
    add_tube(mb, glass, [0.045, 0.059, 0.063, 0.058, 0.046], 12, 'MNF_Glass', tile_v=0.3, cap1=False)
    add_cyl(mb, (0, 0, -0.272), (0, 0, -0.335), 0.072, 0.077, 12, 'MNF_MetalPainted_Red', tile=0.4, rings=2)
    add_cyl(mb, (0, 0, -0.272), (0, 0, -0.255), 0.022, 0.02, 8, 'MNF_MetalRusted', tile=0.3)
    add_cyl(mb, (0.05, 0, -0.262), (0.1, 0, -0.262), 0.006, 0.006, 6, 'MNF_MetalRusted', tile=0.3)
    add_cyl(mb, (0.1, 0, -0.262), (0.105, 0, -0.262), 0.014, 0.014, 8, 'MNF_MetalRusted', tile=0.3)
    ob = top(mb, 'CampLantern', coll, sharp=45, mount='ceiling')
    flame = MB()
    fp = [Vector((0, 0, z)) for z in (-0.254, -0.245, -0.232, -0.218, -0.2)]
    add_tube(flame, fp, [0.004, 0.011, 0.013, 0.008, 0.001], 8, 'MNF_BulbWarm', tile_v=0.1, cap0=True, apex=True)
    H.child_mesh(ob, 'Bulb', flame, (0, 0, -0.232))
    NOTES['CampLantern'] = ('Hanging oil lantern (0.34 m). Pivot = top of the wire bail (hang point), body hangs along '
                            '-Z. Child `Bulb` = flame (MNF_BulbWarm), pivot at (0, 0, -0.232) - put the light there.')
    return ob


# =============================================================================================
# Walkable structures
# =============================================================================================
@builder
def Cabin_Ruin(coll):
    from kitB_shared import timber, plank
    r = rng(101)
    mb = MB()
    HX, HY = 2.0, 2.5          # wall centre lines (4 x 5 m)
    LR = 0.13                  # log radius
    ncourse = 9
    door = (-0.55, 0.55, 1.95)
    win = (-0.6, 0.45, 0.9, 1.65)   # left wall window: y0, y1, z0, z1

    def log(a, b, seed, rad=LR, jag0=0.0, jag1=0.0):
        mat = 'MNF_WoodRotten' if r.random() < 0.22 else 'MNF_WoodBeam'
        a = Vector(a); b = Vector(b)
        d = (b - a).normalized()
        a = a - d * r.uniform(0, jag0); b = b - d * r.uniform(0, jag1) * 0
        br = T.Branch([a, a.lerp(b, 0.5) + Vector((0, 0, r.uniform(-0.015, 0.015))), b],
                      [rad * r.uniform(0.95, 1.05), rad * r.uniform(0.9, 1.0), rad * r.uniform(0.9, 1.05)], 1, 7)
        rings = add_tube(mb, br.pts, br.radii, 7, mat, tile_v=2.0, urep=1, cap0=True, cap1=True,
                         noise_fn=T.bark_noise(0.05, 0, 0, seed, br=None))
        if jag1:
            for vi in rings[-1]:
                mb.v[vi] = mb.v[vi] + d * r.uniform(-jag1, 0.02)
        if jag0:
            for vi in rings[0]:
                mb.v[vi] = mb.v[vi] + d * r.uniform(-0.02, jag0)

    ext = 0.2
    for c in range(ncourse):
        zf = 0.13 + c * 0.25            # front/back courses
        zs = 0.255 + c * 0.25           # side courses (offset half a log)
        # back wall: upper courses missing towards +X (collapsed corner)
        xb_end = HX + ext if c < 6 else 1.0 - (c - 6) * 0.7
        log((-HX - ext, HY, zf), (xb_end, HY, zf), 1000 + c, jag1=0.25 if c >= 6 else 0.0)
        # front wall with door gap
        if zf < door[2]:
            log((-HX - ext, -HY, zf), (door[0], -HY, zf), 1100 + c)
            log((door[1], -HY, zf), (HX + ext, -HY, zf), 1150 + c)
        else:
            log((-HX - ext, -HY, zf), (HX + ext, -HY, zf), 1100 + c)
        # left wall with window
        if win[2] < zs < win[3]:
            log((-HX, -HY - ext, zs), (-HX, win[0], zs), 1200 + c)
            log((-HX, win[1], zs), (-HX, HY + ext, zs), 1250 + c)
        else:
            log((-HX, -HY - ext, zs), (-HX, HY + ext, zs), 1200 + c)
        # right wall: collapsed for y > 0 above course 3
        if c < 4:
            log((HX, -HY - ext, zs), (HX, HY + ext, zs), 1300 + c)
        else:
            ye = 0.7 - (c - 4) * 0.55
            log((HX, -HY - ext, zs), (HX, ye, zs), 1300 + c, jag1=0.3)
    top_z = 0.13 + (ncourse - 1) * 0.25 + LR
    # door frame + window frame boards
    for x in door[:2]:
        timber(mb, (x, -HY, 0.0), (x, -HY, door[2] + 0.1), 0.1, 0.3, up=(0, 1, 0), seed=1400 + int(x * 10), chamfer=0.01)
    for y in win[:2]:
        timber(mb, (-HX, y, win[2] - 0.12), (-HX, y, win[3] + 0.1), 0.08, 0.3, up=(1, 0, 0), seed=1410, chamfer=0.01)
    # fallen logs (inside, right-back corner and outside)
    for k, (a, b) in enumerate((((1.6, 0.8, 0.14), (0.2, 2.1, 0.33)), ((2.5, 0.4, 0.12), (3.6, 2.2, 0.12)),
                                ((1.2, 2.2, 0.35), (2.6, 1.3, 0.12)))):
        log(a, b, 1500 + k, jag1=0.2)
    # raised plank floor on sills
    for y in (-2.2, -0.75, 0.75, 2.2):
        timber(mb, (-HX + 0.1, y, 0.06), (HX - 0.1, y, 0.06), 0.14, 0.12, seed=1600 + int(y * 10), chamfer=0.01)
    n = 17
    for k in range(n):
        y = -HY + 0.14 + (2 * HY - 0.28) * (k + 0.5) / n
        if k in (11, 12) :
            plank(mb, (-HX + 0.13, y, 0.155), (-0.2, y, 0.155), 0.27, 0.04, 'MNF_WoodPlanks', seed=1700 + k, jag1=0.15)
            continue
        if k == 5:
            continue   # missing board (hole)
        plank(mb, (-HX + 0.13, y, 0.155), (HX - 0.13, y, 0.155 + r.uniform(-0.006, 0.006)), 0.27, 0.04, 'MNF_WoodPlanks',
              seed=1700 + k)
    # roof: ridge broken; front half intact, back-right caved in
    rz = top_z + 1.15
    eave = HX + 0.35
    timber(mb, (0, -HY - 0.4, rz), (0, 0.9, rz - 0.04), 0.16, 0.2, seed=1800, jag1=0.15)
    timber(mb, (0.05, 0.95, rz - 0.1), (0.4, HY + 0.2, 0.3), 0.16, 0.2, seed=1801, jag0=0.15)
    rafter_y = (-HY - 0.25, -1.4, -0.3, 0.8, 1.9, HY + 0.1)
    for k, y in enumerate(rafter_y):
        # left side intact
        timber(mb, (-eave, y, top_z - 0.25), (0, y, rz), 0.09, 0.14, up=(0, 1, 0), seed=1810 + k, chamfer=0.01)
        if y < 0.5:
            timber(mb, (eave, y, top_z - 0.25), (0, y, rz), 0.09, 0.14, up=(0, 1, 0), seed=1820 + k, chamfer=0.01)
        elif k == 3:   # broken rafter dangling into the room
            timber(mb, (0.1, y, rz - 0.1), (1.3, y + 0.3, 0.2), 0.09, 0.14, up=(0, 1, 0), seed=1830, jag1=0.15)
    slope = Vector((eave, 0, (top_z - 0.25) - rz))
    sl = slope.length
    for side in (-1, 1):
        sdir = Vector((side * slope.x, 0, slope.z)).normalized()
        nb = 9
        for k in range(nb):
            t = (k + 0.5) / nb * sl
            p = Vector((0, 0, rz + 0.1)) + sdir * t
            up = Vector((side * -slope.z, 0, slope.x)).normalized() * -1 if side < 0 else \
                Vector((-slope.z, 0, slope.x)).normalized()
            up = Vector((-sdir.z * side, 0, abs(sdir.x))).normalized()
            y0 = -HY - 0.45
            if side > 0:
                y1 = 0.35 - k * 0.12 + r.uniform(-0.2, 0.2)
                jag = 0.3
            else:
                y1 = HY + 0.45 if k not in (3, 4) else 0.9 + r.uniform(0, 0.8)
                jag = 0.0 if k not in (3, 4) else 0.3
            mat = 'MNF_WoodRotten' if r.random() < 0.35 else 'MNF_WoodPlanks'
            plank(mb, (p.x, y0, p.z), (p.x, y1, p.z + r.uniform(-0.01, 0.01)), sl / nb * 1.08, 0.035, mat, up=up,
                  seed=1900 + k + side * 30, jag1=jag)
    # fallen roof boards inside
    for k in range(4):
        a = Vector((r.uniform(0.2, 1.7), r.uniform(0.5, 2.2), 0.2))
        b = a + Vector((r.uniform(-0.3, 0.3), r.uniform(-1.6, -0.8), r.uniform(0.3, 1.4)))
        plank(mb, a, b, 0.26, 0.035, 'MNF_WoodPlanks', seed=1950 + k, jag1=0.2)
    # gables (front intact, back half gone)
    for k in range(-7, 8):
        x = k * 0.27
        zt = rz - abs(x) / eave * (rz - top_z + 0.25) - 0.05
        if zt < top_z + 0.05:
            continue
        plank(mb, (x, -HY, top_z - 0.1), (x, -HY, zt - r.uniform(0, 0.1)), 0.26, 0.04, 'MNF_WoodPlanks', up=(0, 1, 0),
              seed=2000 + k, jag1=r.uniform(0, 0.1))
        if x < -0.3:
            plank(mb, (x, HY, top_z - 0.1), (x, HY, zt - r.uniform(0.2, 0.7)), 0.26, 0.04, 'MNF_WoodPlanks',
                  up=(0, 1, 0), seed=2050 + k, jag1=0.15)
    # overgrowth: grass/fern cards around the walls and through the floor gap
    for k, (x, y, kind) in enumerate(((-2.35, -1.0, 'MNF_Grass'), (2.3, -2.0, 'MNF_Fern'), (2.4, 1.4, 'MNF_Fern'),
                                      (0.3, -1.05, 'MNF_Grass'), (-1.2, 2.8, 'MNF_Grass'), (1.2, 1.6, 'MNF_Fern'),
                                      (-2.3, 1.8, 'MNF_Fern'), (0.9, -2.85, 'MNF_Grass'))):
        sz = 0.55 if kind == 'MNF_Grass' else 0.75
        for kk in range(3):
            a = kk * math.pi / 3 + k
            add_card(mb, (x, y, 0.0), (0, 0, 1), (math.cos(a), math.sin(a), 0), sz, sz * 0.85, kind, bend=0.06, segs=1,
                     cnormal=(0, 0, 1))
    ob = top(mb, 'Cabin_Ruin', coll, sharp=45)
    H.col_box(ob, 'COL_Floor', (-HX + 0.1, -HY + 0.1, 0), (HX - 0.1, HY - 0.1, 0.175))
    H.col_box(ob, 'COL_Wall_Back', (-HX - 0.15, HY - LR, 0), (HX + 0.15, HY + LR, top_z))
    H.col_box(ob, 'COL_Wall_Left', (-HX - LR, -HY - 0.15, 0), (-HX + LR, HY + 0.15, top_z))
    H.col_box(ob, 'COL_Wall_Right_A', (HX - LR, -HY - 0.15, 0), (HX + LR, 0.7, top_z))
    H.col_box(ob, 'COL_Wall_Right_B', (HX - LR, 0.7, 0), (HX + LR, HY + 0.15, 1.1))
    H.col_box(ob, 'COL_Wall_FrontL', (-HX - 0.15, -HY - LR, 0), (door[0], -HY + LR, top_z))
    H.col_box(ob, 'COL_Wall_FrontR', (door[1], -HY - LR, 0), (HX + 0.15, -HY + LR, top_z))
    H.col_box(ob, 'COL_Lintel', (door[0], -HY - LR, door[2]), (door[1], -HY + LR, top_z))
    H.col_obox(ob, 'COL_Roof_L_CONVEX', (-eave / 2, -0.95, (rz + top_z - 0.25) / 2 + 0.1), (sl, 2 * HY + 0.9, 0.08),
               (0, -math.degrees(math.atan2(rz - top_z + 0.25, eave)), 0))
    NOTES['Cabin_Ruin'] = ('Ruined 4 x 5 m log cabin. Door gap 1.1 x 1.95 m in the front (-Y) wall, window in the left '
                           'wall, raised plank floor (top z=0.175, one board missing), right-back corner and back half '
                           'of the roof collapsed (broken ridge, dangling rafter, fallen boards), front gable intact, '
                           'grass/fern cards growing around. COL_* boxes for floor, walls (door gap kept open), lintel '
                           'and the intact left roof slope.')
    return ob


@builder
def Watchtower(coll):
    from kitB_shared import timber, plank
    r = rng(102)
    mb = MB()
    pz = 4.2           # platform top
    B, T_ = 1.35, 1.12  # half footprint at base / platform
    posts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            a = Vector((sx * B, sy * B, -0.2))
            b = Vector((sx * T_, sy * T_, pz))
            timber(mb, a, b, 0.2, 0.2, up=(0, 0, 1) if False else (sx, sy, 0), seed=2100 + sx * 3 + sy, chamfer=0.02)
            timber(mb, b - Vector((0, 0, 0.3)), Vector((sx * T_, sy * T_, 5.95)), 0.15, 0.15, up=(sx, sy, 0),
                   seed=2110 + sx * 3 + sy, chamfer=0.015)
            posts.append((a, b))

    def at(sx, sy, z):
        f = (z + 0.2) / (pz + 0.2)
        h = B + (T_ - B) * f
        return Vector((sx * h, sy * h, z))
    # girts and X braces on the back and sides (front has the ladder)
    for z in (0.35, 2.2, pz - 0.18):
        for (s0, s1) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            a, b = at(*s0, z), at(*s1, z)
            out = Vector(((a.x + b.x) / 2, (a.y + b.y) / 2, 0)).normalized()
            plank(mb, a + out * 0.12, b + out * 0.12, 0.16, 0.05, 'MNF_WoodPlanks', up=out, seed=2120 + int(z * 10))
    for (z0, z1) in ((0.35, 2.2), (2.2, pz - 0.18)):
        for k, ((s0, s1)) in enumerate((((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1)))):
            a0, b0, a1, b1 = at(*s0, z0), at(*s1, z0), at(*s0, z1), at(*s1, z1)
            out = Vector(((a0.x + b0.x) / 2, (a0.y + b0.y) / 2, 0)).normalized()
            plank(mb, a0 + out * 0.16, b1 + out * 0.16, 0.14, 0.04, 'MNF_WoodPlanks', up=out, seed=2140 + k)
            if not (k == 1 and z0 > 1):     # one brace missing
                plank(mb, b0 + out * 0.19, a1 + out * 0.19, 0.14, 0.04, 'MNF_WoodPlanks', up=out, seed=2150 + k)
    # platform: joists + boards
    for x in (-0.95, -0.32, 0.32, 0.95):
        timber(mb, (x, -T_ - 0.15, pz - 0.15), (x, T_ + 0.15, pz - 0.15), 0.1, 0.16, seed=2160, chamfer=0.01)
    n = 9
    for k in range(n):
        y = -T_ - 0.1 + (2 * T_ + 0.2) * (k + 0.5) / n
        plank(mb, (-T_ - 0.15, y, pz - 0.035), (T_ + 0.15, y, pz - 0.035 + r.uniform(-0.005, 0.005)), 0.27, 0.045,
              'MNF_WoodPlanks', seed=2170 + k, jag1=0.12 if k == 7 else 0.0)
    # railing: top + mid rails, kneewall boards on 2 sides, gap on the front for the ladder
    gap = 0.38
    for z in (pz + 0.5, pz + 1.0):
        for (s0, s1) in (((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            a = Vector((s0[0] * T_, s0[1] * T_, z)); b = Vector((s1[0] * T_, s1[1] * T_, z))
            out = Vector(((a.x + b.x) / 2, (a.y + b.y) / 2, 0)).normalized()
            plank(mb, a + out * 0.09, b + out * 0.09, 0.12, 0.05, 'MNF_WoodPlanks', up=out, seed=2180 + int(z))
        for sx in (-1, 1):
            plank(mb, (sx * T_, -T_ - 0.09, z), (sx * gap, -T_ - 0.09, z), 0.12, 0.05, 'MNF_WoodPlanks', up=(0, -1, 0),
                  seed=2190 + sx)
    for sx in (-1, 1):
        timber(mb, (sx * gap, -T_ - 0.06, pz - 0.2), (sx * gap, -T_ - 0.06, pz + 1.08), 0.09, 0.09, seed=2195,
               chamfer=0.01)
    for (s0, s1, cnt) in (((1, 1), (-1, 1), 8), ((-1, 1), (-1, -1), 8)):
        a = Vector((s0[0] * T_, s0[1] * T_, 0)); b = Vector((s1[0] * T_, s1[1] * T_, 0))
        out = Vector(((a.x + b.x) / 2, (a.y + b.y) / 2, 0)).normalized()
        for k in range(cnt):
            if r.random() < 0.25:
                continue
            p = a.lerp(b, (k + 0.5) / cnt) + out * 0.14
            plank(mb, p + Vector((0, 0, pz + 0.02)), p + Vector((0, 0, pz + 0.55 + r.uniform(-0.2, 0.05))), 0.27, 0.03,
                  'MNF_WoodPlanks', up=out, seed=2200 + k, jag1=0.08)
    # roof: gable along X, one slope partly gone
    rz = 6.45
    timber(mb, (-T_ - 0.3, 0, rz), (T_ + 0.3, 0, rz), 0.12, 0.14, seed=2210, chamfer=0.01)
    for x in (-T_, 0, T_):
        for sy in (-1, 1):
            timber(mb, (x, sy * (T_ + 0.35), 5.85), (x, 0, rz), 0.08, 0.12, up=(1, 0, 0), seed=2220, chamfer=0.01)
    slope = Vector((0, T_ + 0.35, 5.85 - rz))
    sl = slope.length
    for sy in (-1, 1):
        sdir = Vector((0, sy * slope.y, slope.z)).normalized()
        up = Vector((0, -sdir.z * sy, abs(sdir.y))).normalized()
        nb = 6
        for k in range(nb):
            p = Vector((0, 0, rz + 0.09)) + sdir * ((k + 0.5) / nb * sl)
            x0, x1 = -T_ - 0.35, T_ + 0.35
            jag = 0.0
            if sy > 0 and k >= 3:
                x1 = r.uniform(-0.5, 0.4); jag = 0.25
            plank(mb, (x0, p.y, p.z), (x1, p.y, p.z), sl / nb * 1.06, 0.03, 'MNF_WoodRotten' if r.random() < 0.3 else
                  'MNF_WoodPlanks', up=up, seed=2230 + k + sy * 20, jag1=jag)
    # ladder on the front (-Y) side, through the railing gap
    lb = Vector((0, -T_ - 0.95, 0.0))
    lt = Vector((0, -T_ - 0.12, pz + 0.85))
    ld = (lt - lb).normalized()
    side = Vector((1, 0, 0))
    for sx in (-0.24, 0.24):
        timber(mb, lb + side * sx, lt + side * sx, 0.07, 0.11, up=ld.cross(side) * -1, seed=2240, chamfer=0.01)
    nr = 16
    for k in range(nr):
        t = (k + 0.7) / (nr + 0.3)
        if (lb.lerp(lt, t)).z > pz + 0.2:
            break
        c = lb.lerp(lt, t)
        add_cyl(mb, c - side * 0.24, c + side * 0.24, 0.022, 0.022, 6, 'MNF_WoodHandle', cap0=False, cap1=False,
                tile=0.5)
    ob = top(mb, 'Watchtower', coll, sharp=45)
    for i, (sx, sy) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1))):
        H.col_box(ob, 'COL_Post_%d' % i, (min(sx * B, sx * T_) - 0.12, min(sy * B, sy * T_) - 0.12, 0),
                  (max(sx * B, sx * T_) + 0.12, max(sy * B, sy * T_) + 0.12, pz - 0.2))
    H.col_box(ob, 'COL_Platform', (-T_ - 0.15, -T_ - 0.15, pz - 0.25), (T_ + 0.15, T_ + 0.15, pz))
    H.col_box(ob, 'COL_Rail_Back', (-T_ - 0.15, T_ - 0.05, pz), (T_ + 0.15, T_ + 0.16, pz + 1.08))
    H.col_box(ob, 'COL_Rail_Left', (-T_ - 0.16, -T_ - 0.15, pz), (-T_ + 0.05, T_ + 0.15, pz + 1.08))
    H.col_box(ob, 'COL_Rail_Right', (T_ - 0.05, -T_ - 0.15, pz), (T_ + 0.16, T_ + 0.15, pz + 1.08))
    H.col_box(ob, 'COL_Rail_FrontL', (-T_ - 0.15, -T_ - 0.15, pz), (-gap, -T_ + 0.0, pz + 1.08))
    H.col_box(ob, 'COL_Rail_FrontR', (gap, -T_ - 0.15, pz), (T_ + 0.15, -T_ + 0.0, pz + 1.08))
    H.col_box(ob, 'COL_Ladder', (-0.3, min(lb.y, lt.y) - 0.06, 0), (0.3, max(lb.y, lt.y) + 0.06, pz + 0.85))
    H.col_box(ob, 'COL_Roof', (-T_ - 0.35, -T_ - 0.4, 5.85), (T_ + 0.35, T_ + 0.4, rz + 0.1))
    H.empty(ob, 'SOCKET_LadderTop', (0, -T_ + 0.25, pz), (0, 0, 180))
    NOTES['Watchtower'] = ('Wooden lookout: splayed posts, X-bracing, platform top at z=%.1f (2.5 m square) with 1.08 m '
                           'railing, ladder on the front (-Y) leading through a 0.76 m railing gap, partly collapsed '
                           'gable roof (top ~6.6 m). COL_Ladder is the climb volume (ladder inclined ~10 deg); '
                           'SOCKET_LadderTop = exit point on the platform.' % pz)
    return ob


@builder
def Bridge_Broken(coll):
    from kitB_shared import timber, plank, bolt
    r = rng(103)
    mb = MB()
    HL = 5.0
    gap = 0.75

    def deck_z(y):
        a = abs(y)
        z = 0.1 - 0.12 * (1 - (a / HL) ** 2)
        if a < 2.0:                      # failing ends droop towards the gap
            z -= 0.55 * ((2.0 - a) / (2.0 - gap)) ** 2.2
        return z
    for sg in (-1, 1):
        ys = [sg * (HL - (HL - gap) * k / 8) for k in range(9)]
        for sx in (-0.7, 0.7):
            pts = [Vector((sx + r.uniform(-0.02, 0.02), y, deck_z(y) - 0.2)) for y in ys]
            br = T.Branch(pts, [0.16] * 8 + [0.12], 1, 7)
            rings = T.sweep(mb, br, 'MNF_BarkPine', tile_v=1.5, apex=False, cap1=True,
                            noise_fn=T.bark_noise(0.05, 0, 0, 1030, br=None))
            mb.fm[-1] = mb.mi('MNF_WoodRotten')
            for vi in rings[-1]:
                mb.v[vi] = mb.v[vi] + Vector((0, sg * r.uniform(-0.25, 0.05), 0))
        # planks
        y = sg * (HL - 0.12)
        k = 0
        while abs(y) > gap + 0.05:
            if not (k == 6 and sg > 0):
                z = deck_z(y) - 0.02
                lean = 0.0
                jag0 = jag1 = 0.0
                if abs(y) < gap + 0.5:
                    jag1 = 0.25; lean = r.uniform(-0.15, 0.1)
                plank(mb, (-0.9, y, z), (0.9 + r.uniform(-0.05, 0.05), y + r.uniform(-0.03, 0.03), z + lean), 0.23, 0.05,
                      'MNF_WoodPlanks' if r.random() > 0.2 else 'MNF_WoodRotten', seed=1040 + k + (sg > 0) * 50,
                      jag0=jag0, jag1=jag1)
            y -= sg * 0.255
            k += 1
        # hanging planks at the break
        for k in range(2):
            a = Vector((r.uniform(-0.6, 0.6), sg * (gap + 0.1), deck_z(sg * (gap + 0.1)) - 0.05))
            plank(mb, a, a + Vector((r.uniform(-0.2, 0.2), sg * r.uniform(-0.15, 0.1), -r.uniform(0.8, 1.2))), 0.23, 0.05,
                  'MNF_WoodPlanks', up=(0, 1, 0), seed=1090 + k + sg * 5, jag1=0.15)
        # posts + rope handrail (broken, dangling at the gap)
        for sx in (-0.95, 0.95):
            for yp in (sg * HL, sg * 2.6):
                zt = deck_z(yp) + 1.05
                timber(mb, (sx, yp, deck_z(yp) - 0.35), (sx * 1.02, yp, zt), 0.13, 0.13, up=(0, 1, 0), seed=1100,
                       chamfer=0.015)
            a = Vector((sx * 1.02, sg * HL, deck_z(sg * HL) + 0.98))
            b = Vector((sx * 1.02, sg * 2.6, deck_z(sg * 2.6) + 0.98))
            pts = sag(a, b, 5, 0.12)
            c = b + Vector((0, -sg * 0.9, -0.35))
            pts += [b.lerp(c, 0.5) - Vector((0, 0, 0.05)), c, c + Vector((0.05 * sx, -sg * 0.15, -0.6))]
            add_tube(mb, pts, [0.018] * len(pts), 5, 'MNF_Rope', tile_v=0.6, cap1=True)
        # trestle pier down into the ravine
        yp = sg * 3.4
        for sx in (-0.75, 0.75):
            timber(mb, (sx * 1.35, yp, -3.2), (sx, yp, deck_z(yp) - 0.3), 0.2, 0.2, up=(0, 1, 0), seed=1120, chamfer=0.02)
        timber(mb, (-1.0, yp, deck_z(yp) - 0.38), (1.0, yp, deck_z(yp) - 0.38), 0.2, 0.18, seed=1121)
        plank(mb, (-0.95, yp - 0.12, -2.7), (0.85, yp - 0.12, -0.6), 0.16, 0.05, 'MNF_WoodPlanks', up=(0, -1, 0), seed=1122)
        plank(mb, (0.95, yp - 0.12, -2.7), (-0.85, yp - 0.12, -0.6), 0.16, 0.05, 'MNF_WoodPlanks', up=(0, -1, 0), seed=1123)
    ob = top(mb, 'Bridge_Broken', coll, sharp=45)
    for sg, tag in ((-1, 'A'), (1, 'B')):
        y0, y1 = sorted((sg * HL, sg * 2.0))
        H.col_box(ob, 'COL_Deck_' + tag, (-0.95, y0, -0.15), (0.95, y1, 0.08))
        ya, yb = sg * 2.0, sg * (gap + 0.25)
        za, zb = deck_z(ya) + 0.03, deck_z(yb) + 0.03
        ang = math.degrees(math.atan2(za - zb, abs(ya - yb))) * sg
        H.col_obox(ob, 'COL_DeckEnd_%s_CONVEX' % tag, (0, (ya + yb) / 2, (za + zb) / 2 - 0.06),
                   (1.9, abs(ya - yb), 0.1), (ang, 0, 0))
        for sx in (-0.95, 0.95):
            H.col_box(ob, 'COL_Post_%s%s' % (tag, 'L' if sx < 0 else 'R'), (sx - 0.08, sg * HL - 0.08, -0.3),
                      (sx + 0.08, sg * HL + 0.08, 1.15))
    NOTES['Bridge_Broken'] = ('10 m plank bridge along Y, pivot at the centre of the span at abutment level (deck top '
                              'z~0.1 at both ends, sagging; trestle piers reach z=-3.2 into the ravine). The middle '
                              '%.1f m is broken out: both halves droop into the gap, planks hang down, rope handrails '
                              'snapped and dangling. COL_Deck_A/B (flat parts) + COL_DeckEnd_*_CONVEX (drooping ends) '
                              '+ end posts.' % (2 * gap))
    return ob


@builder
def Minecart_Abandoned(coll):
    r = rng(104)
    mb = MB()
    cart = MB()
    S.minecart(cart, seed=104, ore=False, missing_wheel=2)
    mm = M((0, 0, 0), (0, 0, 18)) @ M((0, 0, 0.43), (0, 97, 0))
    mb.merge(cart, mm)
    zmin = min(v.z for v in mb.v)
    mb.transform(Matrix.Translation((0, 0, -zmin - 0.04)))
    hull = [Vector(v) for v in mb.v]
    # spilled ore and the loose wheel
    S.rubble(mb, (-0.9, -0.2, 0), 0.7, 9, 105, 'MNF_RockMine', sizes=(0.1, 0.28), height=0.15)
    for k in range(3):
        bm = H.cut_rock(1060 + k, (0.18, 0.15, 0.13), cuts=7, subdiv=0, sink=0.1, bevel=0.0)
        rock_to_mb(mb, bm, M((-0.6 - k * 0.3, 0.3 - k * 0.25, 0), (0, 0, k * 40)), 'MNF_OreIron', None, tile=1.5)
        bm.free()
    add_cyl(mb, (1.0, -0.6, 0.0), (1.0, -0.6, 0.06), 0.17, 0.165, 12, 'MNF_MetalRusted', tile=0.6)
    add_cyl(mb, (1.0, -0.6, 0.06), (1.0, -0.6, 0.075), 0.192, 0.192, 12, 'MNF_MetalRusted', tile=0.6)
    for k, (x, y) in enumerate(((0.7, 0.6), (-0.3, -0.75))):
        for kk in range(3):
            a = kk * math.pi / 3 + k
            add_card(mb, (x, y, 0), (0, 0, 1), (math.cos(a), math.sin(a), 0), 0.55, 0.45, 'MNF_Grass', segs=1,
                     cnormal=(0, 0, 1))
    ob = top(mb, 'Minecart_Abandoned', coll, sharp=40)
    H.col_hull(ob, 'COL_Cart_CONVEX', hull)
    NOTES['Minecart_Abandoned'] = ('Rusty ore cart tipped on its side, one wheel missing (lying nearby), spilled ore '
                                   '(MNF_RockMine/MNF_OreIron), grass growing around. Convex collider of the cart.')
    return ob


@builder
def Nest(coll):
    r = rng(106)
    mb = MB()
    # fur-lined dish
    nr, na = 4, 12
    rings = []
    for i in range(nr + 1):
        rr = 0.5 * i / nr
        row = []
        for j in range(na):
            a = 2 * math.pi * j / na
            z = 0.06 + 0.26 * (rr / 0.5) ** 2 + 0.02 * noise.noise(Vector((math.cos(a) * 3, math.sin(a) * 3, rr * 5)))
            row.append(mb.av((math.cos(a) * rr, math.sin(a) * rr, z)))
        rings.append(row)
    for i in range(nr):
        for j in range(na):
            jn = (j + 1) % na
            mb.face([rings[i][j], rings[i][jn], rings[i + 1][jn], rings[i + 1][j]],
                    [(j / na * 3, i / nr), (jn / na * 3 if jn else 3, i / nr), (jn / na * 3 if jn else 3, (i + 1) / nr),
                     (j / na * 3, (i + 1) / nr)], 'MNF_FurRotten' if i < nr - 1 else 'MNF_ForestFloor', True)
    # twigs woven around the rim
    for k in range(32):
        a0 = r.uniform(0, 6.28)
        span = r.uniform(0.9, 1.9)
        rr = r.uniform(0.42, 0.62)
        z = r.uniform(0.0, 0.36) * (rr - 0.3) / 0.32
        pts = []
        for i in range(3):
            a = a0 + span * i / 2
            pts.append(Vector((math.cos(a) * (rr + r.uniform(-0.04, 0.04)), math.sin(a) * (rr + r.uniform(-0.04, 0.04)),
                               z + r.uniform(-0.05, 0.05) + (0.04 if i == 1 else 0))))
        tip = pts[-1] + (pts[-1] - pts[-2]).normalized() * r.uniform(0.05, 0.25) + Vector((0, 0, r.uniform(-0.05, 0.1)))
        pts.append(tip)
        add_tube(mb, pts, [r.uniform(0.012, 0.022)] * 3 + [0.004], 3, 'MNF_BarkDead', tile_v=1.0, cap1=False,
                 smooth=True)
    # bones
    for k in range(3):
        a = r.uniform(0, 6.28)
        c = Vector((math.cos(a) * 0.15, math.sin(a) * 0.15, 0.12))
        d = Vector((math.cos(a + 1.7), math.sin(a + 1.7), r.uniform(0.1, 0.4))).normalized()
        L = r.uniform(0.22, 0.34)
        pts = [c - d * L / 2 + d * L * t for t in (0, 0.08, 0.3, 0.7, 0.92, 1.0)]
        add_tube(mb, pts, [0.004, 0.022, 0.013, 0.013, 0.022, 0.004], 5, 'MNF_Teeth', tile_v=0.3, cap1=False)
    # small skull
    sk = [Vector((0.08, -0.12, 0.13)) + Vector((-0.5, 0.6, 0.15)).normalized() * t for t in (0, 0.03, 0.07, 0.11, 0.14)]
    add_tube(mb, sk, [0.003, 0.035, 0.04, 0.025, 0.002], 8, 'MNF_Teeth', tile_v=0.2, cap1=False, apex=True)
    ey = sk[2] + Vector((0.03, 0.02, 0.025))
    add_cyl(mb, ey, ey + Vector((0.01, 0.0, 0.004)), 0.01, 0.009, 6, 'MNF_Gums', tile=0.1)
    # fur clumps
    for k in range(4):
        bm = H.cut_rock(1070 + k, (0.12, 0.09, 0.06), cuts=6, subdiv=1, sink=0.2, bevel=0.0, disp=0.06)
        a = r.uniform(0, 6.28)
        rock_to_mb(mb, bm, M((math.cos(a) * 0.32, math.sin(a) * 0.32, 0.22), (0, 0, k * 70)), 'MNF_FurRabbitMangy', None,
                   tile=0.5, smooth=True)
        bm.free()
    ob = top(mb, 'Nest', coll, sharp=60)
    NOTES['Nest'] = ('1.25 m twig nest bowl (MNF_BarkDead twigs, MNF_FurRotten lining) with bones and a small skull '
                     '(MNF_Teeth) and mangy fur clumps. No collider (auto).')
    return ob


@builder
def Burrow(coll):
    r = rng(107)
    mb = MB()
    R0 = 0.8
    Hh = 0.34

    def mound(x, y):
        d = math.sqrt(x * x + y * y) / R0
        return max(0.0, Hh * (1 - min(1, d) ** 2) ** 1.4) + 0.03 * noise.noise(Vector((x * 4, y * 4, 1.0))) - 0.02
    hc = Vector((0, -0.42, 0))
    hc.z = mound(hc.x, hc.y)
    hr = 0.16
    na, nr = 20, 7
    grid = []
    for i in range(nr + 1):
        row = []
        for j in range(na):
            a = 2 * math.pi * j / na
            dv = Vector((math.cos(a), math.sin(a), 0))
            # distance from hc along dv to the mound rim circle
            b = hc.x * dv.x + hc.y * dv.y
            cterm = hc.x ** 2 + hc.y ** 2 - (R0 * 1.02) ** 2
            dist = -b + math.sqrt(max(0.0, b * b - cterm))
            t = i / nr
            rho = hr + (dist - hr) * t ** 1.25
            p = Vector((hc.x + dv.x * rho, hc.y + dv.y * rho, 0))
            p.z = mound(p.x, p.y) if i > 0 else mound(p.x, p.y) + 0.05 * max(0, dv.y)
            if i == nr:
                p.z = -0.03
            row.append(mb.av(p))
        grid.append(row)
    for i in range(nr):
        for j in range(na):
            jn = (j + 1) % na
            q = [grid[i][j], grid[i][jn], grid[i + 1][jn], grid[i + 1][j]]
            uvs = [tuple(Vector(mb.v[k].xy) / 1.5) for k in q]
            mat = 'MNF_Mud' if i < 2 else 'MNF_ForestFloor'
            mb.face(q[::-1], uvs[::-1], mat, True)
    # tunnel into the mound (faces point inwards so the inside is visible)
    tdir = Vector((0, 0.65, -0.55)).normalized()
    prev = grid[0]
    for k in range(1, 5):
        c = hc + tdir * (0.16 * k)
        rad = hr * (1 - 0.1 * k)
        F = H.frame_from(tdir, (0, 0, 1))
        ring = []
        for j in range(na):
            a = 2 * math.pi * j / na
            ring.append(mb.av(c + (F.col[0] * math.cos(a) + F.col[2] * math.sin(a)) * rad))
        # match ring orientation to the rim ordering (rim is in XY around hc)
        for j in range(na):
            jn = (j + 1) % na
            mb.face([prev[j], prev[jn], ring[jn], ring[j]], [(j / na, k * 0.2), (jn / na, k * 0.2),
                                                             (jn / na, k * 0.2 + 0.2), (j / na, k * 0.2 + 0.2)],
                    'MNF_Mud', True)
        prev = ring
    cend = mb.av(hc + tdir * 0.75)
    for j in range(na):
        mb.face([prev[j], prev[(j + 1) % na], cend], [(0, 0), (1, 0), (0.5, 1)], 'MNF_Mud', True)
    # dirt clods + grass
    for k in range(6):
        bm = H.cut_rock(1080 + k, (0.12, 0.1, 0.07), cuts=6, subdiv=0, sink=0.3, bevel=0.0)
        a = r.uniform(-2.4, -0.7)
        d = r.uniform(0.45, 0.85)
        rock_to_mb(mb, bm, M((math.cos(a) * d, math.sin(a) * d, 0), (0, 0, k * 50)), 'MNF_Mud', None, tile=1.5)
        bm.free()
    for k, (x, y) in enumerate(((0.45, 0.3), (-0.5, 0.25), (0.1, 0.55))):
        for kk in range(3):
            a = kk * math.pi / 3 + k
            add_card(mb, (x, y, mound(x, y) - 0.02), (0, 0, 1), (math.cos(a), math.sin(a), 0), 0.4, 0.32, 'MNF_Grass',
                     segs=1, cnormal=(0, 0, 1))
    ob = top(mb, 'Burrow', coll, sharp=60)
    H.empty(ob, 'SOCKET_Hole', (hc.x, hc.y, hc.z), (0, 0, 180))
    NOTES['Burrow'] = ('Earth mound 1.6 m wide with a 0.32 m dark hole on the -Y side tunnelling down into it (tunnel '
                       'faces point inwards). SOCKET_Hole = hole mouth, its -Y axis points into the hole (+Y world). '
                       'No collider (auto).')
    return ob


# =============================================================================================
if __name__ == '__main__':
    H.run_kit(KIT, BUILDERS, NOTES)
