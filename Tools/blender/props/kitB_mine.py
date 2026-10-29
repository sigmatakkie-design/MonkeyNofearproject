"""kitB_mine - builds Kit_Mine (mine infrastructure) for MONKEY NO FEAR (artist B).

usage: python kitB_mine.py -- [--only Name1,Name2] [--blend out.blend] [--noexport]
Default: builds everything, saves SourceArt/Props/Kit_Mine.blend, exports
Assets/MonkeyNoFear/Art/Models/Props/Kit_Mine.fbx and props_manifest_Kit_Mine.json.
All objects at the world origin; pivot at the base (wall-mounted props: wall-contact centre, -Y out of the wall).
"""
import bpy, sys, os, math
from mathutils import Vector, Matrix, Quaternion, noise
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import propkit_b_helpers as H
from propkit_b_helpers import MB, M, add_box, add_beam, add_cyl, add_tube, add_card, rng
import kitB_shared as S
import kitB_treegen as T
from kitB_shared import timber, plank, obox, bolt, Z

KIT = 'Kit_Mine'
BUILDERS = []
NOTES = {}
top = H.make_top


def builder(fn):
    BUILDERS.append(fn)
    return fn


# =============================================================================================
# Timber support sets
# =============================================================================================
@builder
def SupportFrame(coll):
    mb = MB()
    S.support_set(mb, y=0.0, seed=1, cracked=True, side_lag=False)
    ob = top(mb, 'SupportFrame', coll, sharp=40)
    H.col_box(ob, 'COL_Post_L', (-2.1, -0.15, 0), (-1.75, 0.15, 3.2))
    H.col_box(ob, 'COL_Post_R', (1.75, -0.15, 0), (2.1, 0.15, 3.2))
    H.col_box(ob, 'COL_Header', (-2.25, -0.17, 3.2), (2.25, 0.17, 3.52))
    NOTES['SupportFrame'] = ('Timber set for a 3.5 m wide x 3.2 m tall tunnel (inner clearance), posts battered '
                             'inwards, cracked/sagging header, rusted iron brackets + bolts, wedges, lagging boards on top '
                             '(+-0.45 m along Y). Frame plane = XZ, tunnel runs along Y; stack sets every '
                             '~1.5-2.5 m.')
    return ob


@builder
def SupportFrame_Broken(coll):
    r = rng(2)
    mb = MB()
    hw, post, height, header = 1.75, 0.26, 3.2, 0.3
    # right post intact
    timber(mb, (1.94, 0, 0), (1.88, 0, height), post, post, up=(0, 1, 0), seed=21)
    add_box(mb, (0.4, 0.36, 0.07), Matrix.Translation((1.94, 0, 0.035)), 'MNF_WoodBeam', bevel=0.01, tile=2.0)
    # left post: snapped stump + fallen upper part
    timber(mb, (-1.94, 0, 0), (-1.86, 0.03, 1.15), post, post, up=(0, 1, 0), seed=22, jag1=0.18)
    add_box(mb, (0.4, 0.36, 0.07), Matrix.Translation((-1.94, 0, 0.035)), 'MNF_WoodBeam', bevel=0.01, tile=2.0)
    timber(mb, (-1.55, 0.55, 0.13), (-0.45, -0.75, 0.55), post, post, up=(0, 0, 1), seed=23, jag0=0.2)
    # header: still on the right post, dropped onto the stump on the left, cracked in two
    pr = Vector((2.12, 0.02, height + header / 2))
    pm = Vector((0.2, -0.05, 2.35))
    pl = Vector((-2.15, 0.1, 1.38))
    timber(mb, pr, pm, post + 0.04, header, seed=24, jag1=0.12)
    timber(mb, pm + Vector((0.02, 0, -0.05)), pl, post + 0.04, header, seed=25, jag0=0.12)
    # bracket left on the right joint, a loose one on the floor
    for face in (-1, 1):
        obox(mb, (1.88, face * 0.136, height - 0.12), Vector((0, face, 0)), Z, (0.28, 0.01, 0.26), 'MNF_MetalRusted')
    bolt(mb, (1.88, -0.14, height - 0.1), (0, -1, 0))
    obox(mb, (-0.9, 0.6, 0.006), Vector((0, 0, 1)), Vector((0.3, 1, 0)), (0.28, 0.012, 0.26), 'MNF_MetalRusted')
    # lagging: a few boards still on the right, others hanging / fallen
    for k in range(4):
        x = 0.9 + k * 0.26
        z = height + header + 0.01
        plank(mb, (x, -0.45, z), (x, 0.45, z + r.uniform(-0.02, 0.02)), 0.2, 0.035, seed=200 + k)
    for k in range(5):
        a = Vector((r.uniform(-1.6, 0.6), r.uniform(-0.6, 0.6), r.uniform(0.02, 0.4)))
        d = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.1, 0.6))).normalized()
        plank(mb, a, a + d * r.uniform(0.6, 1.0), 0.2, 0.035, seed=210 + k, jag1=0.1)
    plank(mb, (0.7, -0.3, height + 0.3), (0.35, -0.2, 2.45), 0.2, 0.035, seed=220, jag1=0.1)
    # rubble from the collapsed roof on the left
    hull = []
    S.rubble(mb, (-1.25, 0.05, 0), 1.3, 22, 7, 'MNF_RockMine', sizes=(0.18, 0.65), height=1.0, hull_pts=hull)
    ob = top(mb, 'SupportFrame_Broken', coll, sharp=40)
    H.col_box(ob, 'COL_Post_R', (1.75, -0.15, 0), (2.1, 0.15, 3.2))
    H.col_box(ob, 'COL_PostStump_L', (-2.1, -0.15, 0), (-1.72, 0.18, 1.2))
    d = (pl - pr)
    ang = math.degrees(math.atan2(d.z, -d.x))
    H.col_obox(ob, 'COL_Header_CONVEX', (pr + pl) / 2, (d.length, 0.32, 0.32), (0, ang, 0))
    H.col_hull(ob, 'COL_Rubble_CONVEX', hull)
    NOTES['SupportFrame_Broken'] = ('Collapsed set: left post snapped (stump + fallen piece), cracked header dropped '
                                    'onto the stump at ~1.4 m, rock rubble pile on the left, fallen lagging. The '
                                    'passage on the right half (x>-0.3) stays open above ~2.3 m only at the right.')
    return ob


# =============================================================================================
# Rails (track runs from the pivot along -Y; SOCKET_End = where the next piece's pivot goes)
# =============================================================================================
@builder
def Rail_Straight(coll):
    mb = MB()
    S.track(mb, S.straight_path(), 2.0, seed=3, spacing=0.5, first=0.25)
    ob = top(mb, 'Rail_Straight', coll, sharp=40)
    H.empty(ob, 'SOCKET_End', (0, -2.0, 0))
    H.col_box(ob, 'COL_Track', (-0.56, -2.0, 0), (0.56, 0.0, 0.19))
    NOTES['Rail_Straight'] = ('2 m narrow-gauge track (0.6 m gauge), sleepers 0.1 m (MNF_WoodBeam), rails '
                              'MNF_MetalRusted with worn MNF_MetalBare heads; rail top at z=0.19. Runs from the pivot '
                              '(y=0) to y=-2; SOCKET_End marks the joint (its -Y = track direction).')
    return ob


@builder
def Rail_Curve(coll):
    mb = MB()
    R, ang = 8.0, 15.0
    L = R * math.radians(ang)
    path = S.arc_path(R, 1)
    S.track(mb, path, L, seed=4, spacing=0.5, first=0.25, nseg=8)
    ob = top(mb, 'Rail_Curve', coll, sharp=40)
    p, t = path(L)
    H.empty(ob, 'SOCKET_End', (p.x, p.y, 0), (0, 0, ang))
    H.col_obox(ob, 'COL_Track_CONVEX', (p.x / 2, p.y / 2, 0.095), (1.2, L, 0.19), (0, 0, ang / 2))
    NOTES['Rail_Curve'] = ('Gentle curve: radius 8 m, 15 deg, arc %.2f m, starts at the pivot heading -Y and bends '
                           'towards +X. SOCKET_End at the end (rotated 15 deg, -Y = track direction). For a left '
                           'curve use the piece reversed (enter from SOCKET_End).' % L)
    return ob


@builder
def Rail_End(coll):
    mb = MB()
    S.track(mb, S.straight_path(), 1.7, seed=5, spacing=0.5, first=0.25)
    yb = -1.35
    for sx in (-1, 1):
        # steel stop posts + diagonal back braces
        add_beam(mb, (sx * 0.42, yb, 0.0), (sx * 0.42, yb, 0.78), 0.1, 0.1, 'MNF_MetalRusted', up=(0, 1, 0),
                 chamfer=0.004, tile=1.5)
        add_beam(mb, (sx * 0.42, yb - 0.05, 0.62), (sx * 0.42, yb - 0.6, 0.05), 0.08, 0.08, 'MNF_MetalRusted',
                 up=(1, 0, 0), chamfer=0.004, tile=1.5)
        add_box(mb, (0.2, 0.2, 0.02), Matrix.Translation((sx * 0.42, yb, 0.01)), 'MNF_MetalRusted', bevel=0.003)
        for bx in (-0.06, 0.06):
            bolt(mb, (sx * 0.42 + bx, yb + 0.07, 0.02), (0, 0, 1), r=0.014)
    timber(mb, (-0.72, yb + 0.12, 0.6), (0.72, yb + 0.12, 0.6), 0.24, 0.26, seed=51)
    obox(mb, (0, yb + 0.245, 0.6), Vector((0, 1, 0)), Z, (1.3, 0.012, 0.22), 'MNF_Hazard', bevel=0.003)
    for bx in (-0.5, 0.5):
        bolt(mb, (bx, yb + 0.25, 0.6), (0, 1, 0))
    ob = top(mb, 'Rail_End', coll, sharp=40)
    H.col_box(ob, 'COL_Track', (-0.56, -1.7, 0), (0.56, 0.0, 0.19))
    H.col_box(ob, 'COL_Stop', (-0.75, yb - 0.1, 0), (0.75, yb + 0.26, 0.78))
    NOTES['Rail_End'] = ('1.7 m track ending in a buffer stop at y=-1.35 (steel posts, timber bumper with a '
                         'MNF_Hazard plate facing the incoming cart, back braces). Attach its pivot to a SOCKET_End.')
    return ob


# =============================================================================================
# Lamps
# =============================================================================================
@builder
def MineLamp(coll):
    mb = MB()
    # wall plate (contact at y=0)
    obox(mb, (0, -0.008, 0), Vector((0, -1, 0)), Z, (0.1, 0.016, 0.24), 'MNF_MetalRusted', bevel=0.004)
    for bz in (-0.09, 0.09):
        bolt(mb, (0, -0.016, bz), (0, -1, 0), r=0.013)
    # bracket arm: out of the wall, curling down at the end
    arm = [Vector((0, -0.016, 0.03)), Vector((0, -0.12, 0.05)), Vector((0, -0.22, 0.055)), Vector((0, -0.285, 0.035)),
           Vector((0, -0.3, 0.0))]
    add_tube(mb, arm, [0.012] * 5, 6, 'MNF_MetalRusted', tile_v=0.5, cap0=True, cap1=True)
    add_beam(mb, (0, -0.016, -0.06), (0, -0.16, 0.045), 0.01, 0.025, 'MNF_MetalRusted', chamfer=0.0, tile=0.5)
    bc = S.cage_lamp(mb, (0, -0.3), -0.0, r=0.075, h=0.22)
    # cable from the wall into the socket
    cab = [Vector((0.03, -0.012, -0.11)), Vector((0.05, -0.08, -0.04)), Vector((0.04, -0.2, 0.0)),
           Vector((0.02, -0.29, 0.02))]
    add_tube(mb, cab, [0.006] * 4, 4, 'MNF_Rubber', tile_v=0.5, cap1=False)
    ob = top(mb, 'MineLamp', coll, sharp=40, mount='wall')
    bulb = S.bulb_mesh(bc, r=0.042)
    H.child_mesh(ob, 'Bulb', bulb, bc)
    NOTES['MineLamp'] = ('Wall-mounted caged mining lamp. Pivot = wall-contact centre, -Y out of the wall. Child '
                         '`Bulb` (MNF_BulbWarm, pivot at the bulb centre %s) - put the light there.'
                         % [round(v, 3) for v in bc])
    return ob


@builder
def LampString(coll):
    mb = MB()
    n = 20
    pts = []
    for k in range(n + 1):
        x = -2.0 + 4.0 * k / n
        pts.append(Vector((x, 0, -0.45 * (1 - (x / 2.0) ** 2))))
    add_tube(mb, pts, [0.0055] * len(pts), 4, 'MNF_Rubber', tile_v=0.5, cap1=False)
    for sx in (-1, 1):   # eye hooks / anchors
        ring = [Vector((sx * 2.0 + math.cos(a) * 0.025 * sx, 0, 0.03 + math.sin(a) * 0.025)) for a in
                [k * 2 * math.pi / 8 for k in range(9)]]
        add_tube(mb, ring, [0.005] * 9, 4, 'MNF_MetalRusted', tile_v=0.3, cap1=False, smooth=False)
        add_cyl(mb, (sx * 2.0, 0, 0.055), (sx * 2.0, 0, 0.13), 0.008, 0.005, 6, 'MNF_MetalRusted', tile=0.3)
        add_box(mb, (0.05, 0.05, 0.012), Matrix.Translation((sx * 2.0, 0, 0.13)), 'MNF_MetalRusted', bevel=0.003)
    ob = top(mb, 'LampString', coll, sharp=40, mount='ceiling')
    bulbs = []
    for i, x in enumerate((-1.25, -0.45, 0.4, 1.2)):
        zw = -0.45 * (1 - (x / 2.0) ** 2)
        drop = (0.07, 0.12, 0.06, 0.16)[i]
        sub = MB()
        add_tube(sub, [Vector((x, 0, zw)), Vector((x + 0.005, 0, zw - drop * 0.5)), Vector((x, 0, zw - drop))],
                 [0.004] * 3, 4, 'MNF_Rubber', tile_v=0.3, cap1=False)
        add_cyl(sub, (x, 0, zw - drop), (x, 0, zw - drop - 0.055), 0.016, 0.019, 8, 'MNF_Plastic_Black', tile=0.2)
        mb.merge(sub)
        bc = Vector((x, 0, zw - drop - 0.055 - 0.045))
        bulbs.append(bc)
    # rebuild the top object mesh with the drops included
    me_old = ob.data
    ob.data = mb.to_object('_tmp', coll).data
    bpy.data.objects.remove(bpy.data.objects['_tmp'])
    bpy.data.meshes.remove(me_old)
    ob.data.name = 'LampString'
    ob.data.set_sharp_from_angle(angle=math.radians(40))
    for i, bc in enumerate(bulbs):
        H.child_mesh(ob, 'Bulb_%d' % i, S.bulb_mesh(bc, r=0.032), bc)
    NOTES['LampString'] = ('4 m string of bare bulbs sagging 0.45 m between two eye hooks at x=+-2. Pivot = midpoint '
                           'between the hooks at hook height (z=0); everything hangs below. Children Bulb_0..Bulb_3 '
                           '(MNF_BulbWarm), each pivot at the bulb centre.')
    return ob


@builder
def Ladder(coll):
    mb = MB()
    for sx in (-0.25, 0.25):
        timber(mb, (sx, 0, 0), (sx, 0, 3.0), 0.05, 0.09, up=(0, 1, 0), seed=300, chamfer=0.01, rough=0.004)
        # hooks at the top (hook over a ledge, towards +Y)
        hk = [Vector((sx, 0.0, 2.92)), Vector((sx, 0.0, 3.08)), Vector((sx, 0.08, 3.12)), Vector((sx, 0.14, 3.06)),
              Vector((sx, 0.14, 2.98))]
        add_tube(mb, hk, [0.012] * 5, 6, 'MNF_MetalRusted', tile_v=0.3, cap0=True, cap1=True)
        bolt(mb, (sx - 0.03 * (1 if sx > 0 else -1) * 0, -0.046, 2.95), (0, -1, 0), r=0.01)
    for k in range(10):
        z = 0.28 + k * 0.29
        add_cyl(mb, (-0.25, 0, z), (0.25, 0, z), 0.019, 0.019, 6, 'MNF_WoodHandle', cap0=False, cap1=False, tile=0.5,
                noise_amp=0.0)
    ob = top(mb, 'Ladder', coll, sharp=40)
    H.col_box(ob, 'COL_Ladder', (-0.29, -0.05, 0), (0.29, 0.05, 3.0))
    H.empty(ob, 'SOCKET_Top', (0, 0.0, 3.0))
    NOTES['Ladder'] = ('3 m wooden ladder in the XZ plane (climb from -Y), 10 rungs at 0.29 m, steel hooks at the top '
                       'curling towards +Y to hang over a ledge. COL_Ladder = climb volume.')
    return ob


def rail_post(mb, x, y, z0, h, mat='MNF_MetalPainted_Yellow', base=False):
    add_cyl(mb, (x, y, z0), (x, y, z0 + h), 0.024, 0.024, 8, mat, tile=1.0, cap0=False)
    if base:
        add_box(mb, (0.14, 0.14, 0.012), Matrix.Translation((x, y, z0 + 0.006)), mat, bevel=0.003)
        for bx in (-0.05, 0.05):
            for by in (-0.05, 0.05):
                bolt(mb, (x + bx, y + by, z0 + 0.012), (0, 0, 1), r=0.009, h=0.008, mat='MNF_MetalRusted')


def rail_run(mb, x0, x1, y, z0, h=1.1, posts=(), mat='MNF_MetalPainted_Yellow', base=False, toe=True):
    for x in posts:
        rail_post(mb, x, y, z0, h, mat, base)
    for z in (z0 + h, z0 + h * 0.52):
        add_cyl(mb, (x0, y, z), (x1, y, z), 0.022, 0.022, 8, mat, tile=1.0, cap0=True, cap1=True)
    if toe:
        obox(mb, ((x0 + x1) / 2, y, z0 + 0.06), Vector((0, 1, 0)), Z, (abs(x1 - x0), 0.006, 0.1), mat, tile=1.0)


@builder
def Walkway(coll):
    mb = MB()
    zt = 0.21
    for sy in (-0.5, 0.5):
        add_beam(mb, (-1.0, sy, 0.09), (1.0, sy, 0.09), 0.06, 0.18, 'MNF_MetalRusted', chamfer=0.004, tile=1.5)
    for x in (-0.95, -0.32, 0.32, 0.95):
        add_beam(mb, (x, -0.47, 0.13), (x, 0.47, 0.13), 0.05, 0.1, 'MNF_MetalRusted', chamfer=0.004, tile=1.5)
    add_box(mb, (2.0, 0.94, 0.03), Matrix.Translation((0, 0, zt - 0.015)), 'MNF_MetalGrate', tile=1.0)
    for sy in (-0.5, 0.5):
        rail_run(mb, -1.0, 1.0, sy, zt, posts=(-0.95, 0.0, 0.95))
    ob = top(mb, 'Walkway', coll, sharp=40)
    H.col_box(ob, 'COL_Floor', (-1.0, -0.5, 0), (1.0, 0.5, zt))
    H.col_box(ob, 'COL_Rail_Front', (-1.0, -0.53, zt), (1.0, -0.47, zt + 1.12))
    H.col_box(ob, 'COL_Rail_Back', (-1.0, 0.47, zt), (1.0, 0.53, zt + 1.12))
    NOTES['Walkway'] = ('2 m (X) x 1 m grated walkway section (MNF_MetalGrate deck, rusted stringers), yellow pipe '
                        'railings both sides. Pivot at the bottom centre; deck top at z=0.21. Chain along X every 2 m.')
    return ob


@builder
def Railing(coll):
    mb = MB()
    rail_run(mb, -1.0, 1.0, 0.0, 0.0, posts=(-0.95, 0.0, 0.95), base=True)
    ob = top(mb, 'Railing', coll, sharp=40)
    H.col_box(ob, 'COL_Railing', (-1.0, -0.04, 0), (1.0, 0.04, 1.12))
    NOTES['Railing'] = '2 m yellow pipe railing (top 1.1 m, mid rail, toe board) with bolted floor base plates.'
    return ob


@builder
def Elevator_Platform(coll):
    r = rng(310)
    mb = MB()
    hs = 1.5
    zt = 0.23
    for sy in (-hs + 0.06, hs - 0.06):
        add_beam(mb, (-hs, sy, 0.1), (hs, sy, 0.1), 0.12, 0.2, 'MNF_MetalPainted_Yellow', chamfer=0.006, tile=1.0)
    for sx in (-hs + 0.06, hs - 0.06):
        add_beam(mb, (sx, -hs + 0.12, 0.1), (sx, hs - 0.12, 0.1), 0.12, 0.2, 'MNF_MetalPainted_Yellow', chamfer=0.006,
                 tile=1.0)
    for x in (-0.75, 0.0, 0.75):
        add_beam(mb, (x, -hs + 0.12, 0.11), (x, hs - 0.12, 0.11), 0.08, 0.16, 'MNF_MetalRusted', chamfer=0.004, tile=1.5)
    add_box(mb, (2 * hs, 2 * hs, 0.03), Matrix.Translation((0, 0, zt - 0.015)), 'MNF_MetalDiamond', tile=1.0)
    obox(mb, (0, -hs + 0.08, zt + 0.002), Vector((0, 0, 1)), Vector((0, 1, 0)), (2 * hs - 0.1, 0.004, 0.12), 'MNF_Hazard',
         tile=1.0)
    # corner posts + top frame
    ch = 2.45
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_beam(mb, (sx * (hs - 0.05), sy * (hs - 0.05), zt), (sx * (hs - 0.05), sy * (hs - 0.05), zt + ch), 0.09,
                     0.09, 'MNF_MetalPainted_Yellow', up=(0, 1, 0), chamfer=0.004, tile=1.0)
    for a, b in ((((-1, -1), (1, -1))), (((1, -1), (1, 1))), (((1, 1), (-1, 1))), (((-1, 1), (-1, -1)))):
        add_beam(mb, (a[0] * (hs - 0.05), a[1] * (hs - 0.05), zt + ch), (b[0] * (hs - 0.05), b[1] * (hs - 0.05), zt + ch),
                 0.09, 0.09, 'MNF_MetalPainted_Yellow', chamfer=0.004, tile=1.0)
    # railings (left, right, back) + cage mesh above them, front open
    for (x0, y0, x1, y1) in ((-hs + 0.05, hs - 0.05, hs - 0.05, hs - 0.05), (-hs + 0.05, -hs + 0.05, -hs + 0.05, hs - 0.05),
                             (hs - 0.05, -hs + 0.05, hs - 0.05, hs - 0.05)):
        a = Vector((x0, y0, 0)); b = Vector((x1, y1, 0))
        for z in (zt + 0.55, zt + 1.1):
            add_cyl(mb, a + Vector((0, 0, z)), b + Vector((0, 0, z)), 0.022, 0.022, 8, 'MNF_MetalPainted_Yellow', tile=1.0)
        d = (b - a)
        L = d.length
        nrm = Vector((-d.y, d.x, 0)).normalized()
        c = (a + b) / 2
        obox(mb, c + Vector((0, 0, zt + 0.06)), nrm, Z, (L, 0.006, 0.1), 'MNF_MetalPainted_Yellow', tile=1.0)
        obox(mb, c + Vector((0, 0, zt + 1.1 + (ch - 1.1) / 2)), nrm, Z, (L - 0.1, 0.012, ch - 1.15), 'MNF_MetalGrate',
             tile=1.0)
    # hoist bridle: chains from the top corners to a shackle, cable stub up
    sh = Vector((0, 0, zt + ch + 1.0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = Vector((sx * (hs - 0.05), sy * (hs - 0.05), zt + ch))
            add_tube(mb, [p, p.lerp(sh, 0.5), sh], [0.012] * 3, 4, 'MNF_MetalRusted', tile_v=0.3, cap1=False,
                     smooth=False)
    add_cyl(mb, sh - Vector((0, 0, 0.05)), sh + Vector((0, 0, 0.12)), 0.06, 0.05, 8, 'MNF_MetalRusted', tile=0.5)
    add_cyl(mb, sh + Vector((0, 0, 0.12)), sh + Vector((0, 0, 1.2)), 0.018, 0.018, 6, 'MNF_MetalBare', tile=1.0)
    # control box on the front-right post
    obox(mb, (hs - 0.1, -hs + 0.22, zt + 1.15), Vector((-1, 0, 0)), Z, (0.22, 0.12, 0.3), 'MNF_MetalPainted_Gray',
         bevel=0.01)
    add_cyl(mb, (hs - 0.165, -hs + 0.22, zt + 1.22), (hs - 0.2, -hs + 0.22, zt + 1.22), 0.025, 0.022, 8,
            'MNF_Plastic_Black', tile=0.3)
    ob = top(mb, 'Elevator_Platform', coll, sharp=40)
    lamp = MB()
    add_cyl(lamp, (hs - 0.165, -hs + 0.22, zt + 1.1), (hs - 0.19, -hs + 0.22, zt + 1.1), 0.018, 0.016, 8,
            'MNF_BulbRed', tile=0.3)
    H.child_mesh(ob, 'Lamp', lamp, (hs - 0.18, -hs + 0.22, zt + 1.1))
    H.col_box(ob, 'COL_Floor', (-hs, -hs, 0), (hs, hs, zt))
    H.col_box(ob, 'COL_Rail_Back', (-hs, hs - 0.1, zt), (hs, hs, zt + ch))
    H.col_box(ob, 'COL_Rail_Left', (-hs, -hs, zt), (-hs + 0.1, hs, zt + ch))
    H.col_box(ob, 'COL_Rail_Right', (hs - 0.1, -hs, zt), (hs, hs, zt + ch))
    NOTES['Elevator_Platform'] = ('3 x 3 m caged lift platform; moves vertically. Pivot at the bottom centre of the '
                                  'frame, floor (MNF_MetalDiamond, hazard edge) top at z=0.23; railings + grate cage on '
                                  'back/left/right up to 2.68 m, front (-Y) open. Hoist bridle + cable stub on top '
                                  '(to ~4.9 m). Small control box with child `Lamp` (MNF_BulbRed indicator).')
    return ob


@builder
def Elevator_Frame(coll):
    mb = MB()
    hs = 1.72
    Hs = 8.0

    def ibeam(x, y, z0, z1, rot):
        # H-section: two flanges + web
        F = Matrix.Rotation(math.radians(rot), 4, 'Z')
        for off in (-0.07, 0.07):
            add_beam(mb, F @ Vector((off, 0, 0)) + Vector((x, y, z0)), F @ Vector((off, 0, 0)) + Vector((x, y, z1)), 0.15,
                     0.014, 'MNF_MetalRusted', up=F @ Vector((1, 0, 0)), chamfer=0.0, tile=1.5)
        add_beam(mb, Vector((x, y, z0)), Vector((x, y, z1)), 0.13, 0.012, 'MNF_MetalRusted', up=F @ Vector((0, 1, 0)),
                 chamfer=0.0, tile=1.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            ibeam(sx * hs, sy * hs, 0.0, Hs, 0)
    for z in (0.15, 4.15):
        for a, b in ((((-1, -1), (1, -1))), (((1, -1), (1, 1))), (((1, 1), (-1, 1))), (((-1, 1), (-1, -1)))):
            if a[1] == -1 and b[1] == -1 and z > 1:
                continue   # keep the front open at the landing level
            add_beam(mb, (a[0] * hs, a[1] * hs, z), (b[0] * hs, b[1] * hs, z), 0.12, 0.16, 'MNF_MetalPainted_Yellow',
                     chamfer=0.005, tile=1.0)
    # X bracing on back and sides
    for (a, b) in (((-1, 1), (1, 1)), ((-1, -1), (-1, 1)), ((1, -1), (1, 1))):
        for (z0, z1) in ((0.25, 4.05), (4.25, 7.95)):
            pa0 = Vector((a[0] * hs, a[1] * hs, z0)); pb1 = Vector((b[0] * hs, b[1] * hs, z1))
            pb0 = Vector((b[0] * hs, b[1] * hs, z0)); pa1 = Vector((a[0] * hs, a[1] * hs, z1))
            out = Vector(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0)).normalized() * 0.09
            add_beam(mb, pa0 + out, pb1 + out, 0.08, 0.012, 'MNF_MetalRusted', up=out, chamfer=0.0, tile=1.5)
            add_beam(mb, pb0 + out * 1.2, pa1 + out * 1.2, 0.08, 0.012, 'MNF_MetalRusted', up=out, chamfer=0.0, tile=1.5)
    # timber guide rails for the cage shoes (left/right)
    for sx in (-1, 1):
        timber(mb, (sx * (hs - 0.14), 0, 0.0), (sx * (hs - 0.14), 0, Hs), 0.14, 0.12, up=(0, 1, 0), seed=320,
               chamfer=0.012, rough=0.003)
        for z in (1.0, 3.0, 5.0, 7.0):
            add_beam(mb, (sx * (hs - 0.05), 0, z), (sx * (hs - 0.2), 0, z), 0.18, 0.06, 'MNF_MetalRusted', up=(0, 0, 1),
                     chamfer=0.0, tile=1.0)
            add_beam(mb, (sx * hs, -hs + 0.07, z), (sx * hs, hs - 0.07, z), 0.05, 0.08, 'MNF_MetalRusted', chamfer=0.0,
                     tile=1.5)
    ob = top(mb, 'Elevator_Frame', coll, sharp=40)
    for i, (sx, sy) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1))):
        H.col_box(ob, 'COL_Guide_%d' % i, (sx * hs - 0.09, sy * hs - 0.09, 0), (sx * hs + 0.09, sy * hs + 0.09, Hs))
    H.col_box(ob, 'COL_Side_L', (-hs - 0.12, -hs, 0), (-hs + 0.0, hs, Hs))
    H.col_box(ob, 'COL_Side_R', (hs, -hs, 0), (hs + 0.12, hs, Hs))
    H.col_box(ob, 'COL_Side_Back', (-hs, hs, 0), (hs, hs + 0.12, Hs))
    NOTES['Elevator_Frame'] = ('8 m stackable shaft segment (stack every 8 m along Z for the 40 m shaft): four H-beam '
                               'corner guides on a 3.44 m square around the 3 x 3 m platform, ring frames at 0.15 and '
                               '4.15 m (front ring only at the bottom so landings stay open), X bracing on back/sides, '
                               'timber cage-shoe guides at x=+-1.58. Pivot at the bottom centre; front (-Y) open.')
    return ob


@builder
def Minecart(coll):
    mb = MB()
    S.minecart(mb, seed=201, ore=True)
    ob = top(mb, 'Minecart', coll, sharp=40)
    H.col_box(ob, 'COL_Body', (-0.47, -0.66, 0.2), (0.47, 0.66, 0.98))
    H.col_box(ob, 'COL_Wheels', (-0.36, -0.56, 0.0), (0.36, 0.56, 0.2))
    NOTES['Minecart'] = ('Rusty narrow-gauge ore cart, long axis along Y, ore heap inside (MNF_RockMine + MNF_OreIron). '
                         'Pivot = bottom centre at the wheel running surface; to sit on Kit_Mine rails place it at '
                         'z=+0.19 (rail top). Wheel gauge 0.6 m.')
    return ob


def helmet(mb, mm=None, lamp=True):
    sub = MB()
    prof = [(0.0, 1.0), (0.012, 1.0), (0.02, 0.93), (0.06, 0.9), (0.105, 0.78), (0.14, 0.55), (0.16, 0.25), (0.165, 0.0)]
    R = 0.118
    pts = [Vector((0, 0, z)) for z, _ in prof]
    rad = [R * f for _, f in prof]
    add_tube(sub, pts, rad, 14, 'MNF_Plastic_Yellow', tile_v=0.3, apex=True, cap0=False)
    # inner shell (flipped) so the inside reads from below
    n0 = len(sub.f)
    add_tube(sub, [Vector((0, 0, 0.012)), Vector((0, 0, 0.1)), Vector((0, 0, 0.15))], [R * 0.95, R * 0.75, 0.002], 12,
             'MNF_Plastic_Black', tile_v=0.3, apex=True, cap0=False)
    for i in range(n0, len(sub.f)):
        sub.f[i] = sub.f[i][::-1]; sub.uv[i] = sub.uv[i][::-1]
    # brim: wider at the front (-Y peak)
    na = 16
    inner, outer = [], []
    for k in range(na):
        a = 2 * math.pi * k / na
        dv = Vector((math.cos(a), math.sin(a), 0))
        ext = 0.03 + 0.045 * max(0.0, -math.sin(a)) ** 2
        inner.append(sub.av(dv * R * 0.98 + Vector((0, 0, 0.008))))
        outer.append(sub.av(dv * (R + ext) + Vector((0, 0, 0.0 - 0.01 * max(0, -math.sin(a))))))
    for k in range(na):
        kn = (k + 1) % na
        sub.face([inner[k], outer[k], outer[kn], inner[kn]], [(0, k / na), (0.1, k / na), (0.1, (k + 1) / na),
                                                               (0, (k + 1) / na)], 'MNF_Plastic_Yellow')
        sub.face([inner[kn], outer[kn], outer[k], inner[k]], [(0, (k + 1) / na), (0.1, (k + 1) / na), (0.1, k / na),
                                                               (0, k / na)], 'MNF_Plastic_Yellow')
    # crest ridge
    crest = [Vector((0, y, z)) for y, z in ((-0.1, 0.09), (-0.06, 0.135), (0.0, 0.17), (0.06, 0.135), (0.1, 0.09))]
    add_tube(sub, crest, [0.012] * 5, 5, 'MNF_Plastic_Yellow', tile_v=0.3, cap0=True, cap1=True)
    if lamp:
        add_box(sub, (0.05, 0.02, 0.05), Matrix.Translation((0, -R - 0.005, 0.075)), 'MNF_MetalBare', bevel=0.004)
        add_cyl(sub, (0, -R - 0.012, 0.085), (0, -R - 0.07, 0.085), 0.034, 0.038, 12, 'MNF_Plastic_Black', tile=0.2)
        add_cyl(sub, (0, -R - 0.07, 0.085), (0, -R - 0.074, 0.085), 0.03, 0.03, 12, 'MNF_Glass', tile=0.2, cap0=False)
        cab = [Vector((0.02, -R - 0.02, 0.085)), Vector((0.06, -0.1, 0.13)), Vector((0.07, 0.0, 0.16)),
               Vector((0.06, 0.1, 0.11)), Vector((0.05, 0.13, 0.03))]
        add_tube(sub, cab, [0.006] * 5, 4, 'MNF_Rubber', tile_v=0.3, cap1=False)
    mb.merge(sub, mm)
    return sub


@builder
def Helmet(coll):
    mb = MB()
    helmet(mb)
    ob = top(mb, 'Helmet', coll, sharp=50)
    H.col_box(ob, 'COL_Helmet', (-0.15, -0.2, 0), (0.15, 0.15, 0.17))
    NOTES['Helmet'] = ('Miner hard hat (MNF_Plastic_Yellow) with brim peak and lamp facing -Y (MNF_Glass lens), cable '
                       'to the back. Pivot at the brim bottom centre.')
    return ob


@builder
def Workstation(coll):
    r = rng(330)
    mb = MB()
    zt = 0.76
    # steel frame + wooden top
    for sx in (-0.65, 0.65):
        for sy in (-0.3, 0.3):
            add_beam(mb, (sx, sy, 0), (sx, sy, zt - 0.04), 0.045, 0.045, 'MNF_MetalPainted_Gray', up=(0, 1, 0),
                     chamfer=0.004, tile=1.0)
        add_beam(mb, (sx, -0.3, 0.12), (sx, 0.3, 0.12), 0.03, 0.03, 'MNF_MetalPainted_Gray', chamfer=0.003, tile=1.0)
    add_beam(mb, (-0.65, 0.3, 0.5), (0.65, 0.3, 0.5), 0.03, 0.12, 'MNF_MetalPainted_Gray', chamfer=0.003, tile=1.0)
    for k in range(4):
        y = -0.33 + 0.66 * (k + 0.5) / 4
        plank(mb, (-0.72, y, zt - 0.02), (0.72, y, zt - 0.02), 0.165, 0.04, 'MNF_WoodPlanks', seed=331 + k)
    # drawer unit with one drawer pulled out
    add_box(mb, (0.42, 0.6, 0.6), Matrix.Translation((0.4, 0, 0.36)), 'MNF_MetalPainted_Green', bevel=0.008, tile=1.0)
    for k, z in enumerate((0.58, 0.38, 0.18)):
        dy = -0.22 if k == 0 else 0.0
        add_box(mb, (0.38, 0.02, 0.17), Matrix.Translation((0.4, -0.305 + dy, z)), 'MNF_MetalPainted_Green', bevel=0.004)
        add_beam(mb, (0.34, -0.33 + dy, z + 0.03), (0.46, -0.33 + dy, z + 0.03), 0.015, 0.015, 'MNF_MetalBare',
                 chamfer=0.0, tile=0.5)
        if k == 0:
            add_box(mb, (0.36, 0.44, 0.012), Matrix.Translation((0.4, -0.08 + dy, z - 0.07)), 'MNF_MetalPainted_Green')
            for sx in (0.23, 0.57):
                add_box(mb, (0.012, 0.44, 0.13), Matrix.Translation((sx, -0.08 + dy, z - 0.01)), 'MNF_MetalPainted_Green')
            add_box(mb, (0.2, 0.25, 0.04), M((0.4, -0.15 + dy, z - 0.04), (0, 0, 12)), 'MNF_Paper', tile=0.3)
    # helmet, thermos, mug, papers
    helmet(mb, M((-0.35, 0.05, zt), (0, 4, 35)))
    add_cyl(mb, (0.05, 0.12, zt), (0.05, 0.12, zt + 0.27), 0.045, 0.045, 12, 'MNF_MetalPainted_Green', tile=0.3,
            rings=2)
    add_cyl(mb, (0.05, 0.12, zt + 0.27), (0.05, 0.12, zt + 0.33), 0.042, 0.038, 12, 'MNF_MetalPainted_Gray', tile=0.3)
    add_cyl(mb, (0.16, -0.05, zt), (0.16, -0.05, zt + 0.09), 0.04, 0.042, 10, 'MNF_MetalPainted_Gray', tile=0.3,
            cap1=False)
    add_cyl(mb, (0.16, -0.05, zt + 0.005), (0.16, -0.05, zt + 0.07), 0.035, 0.037, 10, 'MNF_Plastic_Black', tile=0.3,
            cap0=False, cap1=True)
    for k in range(6):
        c = Vector((r.uniform(-0.6, 0.3), r.uniform(-0.25, 0.25), zt + 0.002 + k * 0.002))
        a = r.uniform(-30, 30)
        add_box(mb, (0.21, 0.297, 0.002), M(c, (r.uniform(-2, 2), r.uniform(-2, 2), a)), 'MNF_Paper', tile=0.3)
    for k in range(3):   # papers on the floor
        c = Vector((r.uniform(-0.9, 0.9), r.uniform(-0.9, -0.4), 0.002))
        add_box(mb, (0.21, 0.297, 0.002), M(c, (0, 0, r.uniform(0, 180))), 'MNF_Paper', tile=0.3)
    # chair: pushed back and tipped against the desk
    cm = M((-0.25, -0.75, 0), (0, 0, 165)) @ M((0, 0, 0), (-12, 0, 0))
    ch = MB()
    for sx in (-0.2, 0.2):
        add_beam(ch, (sx, -0.2, 0), (sx, -0.18, 0.45), 0.025, 0.025, 'MNF_MetalPainted_Gray', up=(0, 1, 0), chamfer=0.0)
        add_beam(ch, (sx, 0.2, 0), (sx, 0.22, 0.9), 0.025, 0.025, 'MNF_MetalPainted_Gray', up=(0, 1, 0), chamfer=0.0)
    add_box(ch, (0.44, 0.42, 0.03), Matrix.Translation((0, 0.0, 0.46)), 'MNF_WoodPlanks', bevel=0.006, tile=2.0)
    add_box(ch, (0.42, 0.03, 0.22), M((0, 0.22, 0.75), (-8, 0, 0)), 'MNF_WoodPlanks', bevel=0.006, tile=2.0)
    mb.merge(ch, cm)
    ob = top(mb, 'Workstation', coll, sharp=40)
    H.col_box(ob, 'COL_Desk', (-0.73, -0.34, 0), (0.73, 0.34, zt))
    cv = [cm @ Vector(v) for v in ch.v]
    H.col_box(ob, 'COL_Chair', [min(v[k] for v in cv) for k in range(3)], [max(v[k] for v in cv) for k in range(3)])
    NOTES['Workstation'] = ('Abandoned miner desk 1.45 x 0.68 m, top at 0.76 m: drawer unit with one drawer pulled out, '
                            'helmet, thermos, mug, scattered papers (also on the floor), chair pushed back. Desk front '
                            '= -Y.')
    return ob


def _rubble_pile(name, coll, seed, radius, height, n, timbers):
    r = rng(seed)
    mb = MB()
    hull = []
    S.rubble(mb, (0, 0, 0), radius, n, seed, 'MNF_RockMine', sizes=(0.2, 0.75), height=height, hull_pts=hull,
             bevel_min=0.55)
    for k in range(timbers):
        a = r.uniform(0, 6.28)
        p = Vector((math.cos(a) * radius * 0.4, math.sin(a) * radius * 0.3, height * r.uniform(0.2, 0.6)))
        d = Vector((math.cos(a + 1.6), math.sin(a + 1.6), r.uniform(-0.4, 0.3))).normalized()
        L = r.uniform(1.2, 2.4)
        timber(mb, p - d * L / 2, p + d * L / 2, 0.22, 0.22, seed=seed + k, jag0=0.15, jag1=0.25)
    for k in range(3):
        a = Vector((r.uniform(-radius, radius), r.uniform(-radius * 0.6, radius * 0.6), r.uniform(0.05, height * 0.5)))
        plank(mb, a, a + Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.2, 0.5))).normalized() * 1.1, 0.2,
              0.035, seed=seed + 20 + k, jag1=0.15)
    ob = top(mb, name, coll, sharp=40)
    H.col_hull(ob, 'COL_Pile_CONVEX', hull)
    NOTES[name] = ('Collapsed rock & timber rubble ~%.1f m wide, %.1f m tall (MNF_RockMine, broken beams, planks). '
                   'Convex collider.' % (radius * 2.6, height))
    return ob


@builder
def RubblePile_A(coll):
    return _rubble_pile('RubblePile_A', coll, 340, 1.3, 1.3, 26, 3)


@builder
def RubblePile_B(coll):
    return _rubble_pile('RubblePile_B', coll, 341, 0.85, 0.75, 16, 1)


@builder
def LooseRockWall(coll):
    r = rng(350)
    mb = MB()
    # packed boulders filling the 3.5 x 3.2 tunnel section, ~1 m thick
    z = 0.0
    row = 0
    while z < 3.1:
        hsz = r.uniform(0.45, 0.7) if z < 1.6 else r.uniform(0.35, 0.6)
        x = -1.85 + r.uniform(0, 0.2)
        while x < 1.85:
            w = r.uniform(0.45, 0.85) * (hsz / 0.55)
            for dy in (0.0,):
                bm = H.cut_rock(3500 + row * 40 + int(x * 10), (w * 1.05, r.uniform(0.8, 1.05), hsz * 1.15),
                                cuts=r.randint(6, 8), subdiv=0, sink=0.0, bevel=0.03 if w > 0.75 else 0.0)
                H.rock_to_mb(mb, bm, M((x + w / 2, dy + r.uniform(-0.1, 0.1), z + r.uniform(-0.05, 0.05)),
                                       (r.uniform(-12, 12), r.uniform(-12, 12), r.uniform(-15, 15))), 'MNF_RockMine', None,
                             tile=3.0)
                bm.free()
            x += w * 0.85
        z += hsz * 0.78
        row += 1
    for k in range(2):
        a = Vector((r.uniform(-1.3, 1.3), -0.45, r.uniform(0.8, 2.6)))
        timber(mb, a, a + Vector((r.uniform(-0.8, 0.8), -0.4, r.uniform(-0.5, 0.5))), 0.2, 0.2, seed=360 + k, jag1=0.25)
    S.rubble(mb, (0, -0.75, 0), 1.2, 10, 361, 'MNF_RockMine', sizes=(0.15, 0.4), height=0.35)
    ob = top(mb, 'LooseRockWall', coll, sharp=40)
    H.col_box(ob, 'COL_Wall', (-1.8, -0.55, 0), (1.8, 0.55, 3.25))
    NOTES['LooseRockWall'] = ('Plug of packed loose boulders filling a 3.5 x 3.2 m tunnel section (XZ plane, ~1 m thick '
                              'along Y) with broken timbers and spill on the -Y side. Borer emergence point; the builder '
                              'can hide the whole object.')
    return ob


@builder
def BorerHole(coll):
    r = rng(370)
    mb = MB()
    cz = 1.25
    hr = 1.25
    na, nr = 30, 6
    W, Ht = 2.9, 4.2
    grid = []
    rim = []
    for j in range(na):
        a = 2 * math.pi * j / na
        rim.append(hr * (1 + 0.12 * noise.noise(Vector((math.cos(a) * 2.5, math.sin(a) * 2.5, 7.0)))
                         + 0.05 * r.uniform(-1, 1)))
    for i in range(nr + 1):
        row = []
        t = i / nr
        for j in range(na):
            a = 2 * math.pi * j / na
            dv = Vector((math.cos(a), 0, math.sin(a)))
            # distance to the rectangular border of the wall piece
            dx = (W / abs(dv.x)) if abs(dv.x) > 1e-4 else 1e9
            dzu = ((Ht - cz) / dv.z) if dv.z > 1e-4 else 1e9
            dzd = (cz / -dv.z) if dv.z < -1e-4 else 1e9
            dist = min(dx, dzu, dzd)
            rho = rim[j] + (dist - rim[j]) * t ** 1.3
            p = Vector((dv.x * rho, 0, cz + dv.z * rho))
            p.y = -0.35 * (1 - t) ** 2 + 0.12 * noise.noise(Vector((p.x * 1.4, 3.0, p.z * 1.4))) * (1 - t * 0.6)
            if i == nr:
                p.y = 0.05
            p.z = max(0.0, p.z)
            row.append(p)
        grid.append([mb.av(p) for p in row])
    for i in range(nr):
        for j in range(na):
            jn = (j + 1) % na
            q = [grid[i][j], grid[i + 1][j], grid[i + 1][jn], grid[i][jn]]
            if all(mb.v[k].z < 0.01 for k in q):
                continue
            mb.face(q, [(mb.v[k].x / 3.0, mb.v[k].z / 3.0) for k in q], 'MNF_RockMine', False)
    # throat: tunnel going +Y, narrowing and dipping, faces inwards, floor flattened
    prev = grid[0]
    depth = [0.6, 1.3, 2.1, 3.0]
    for k, dy in enumerate(depth):
        sc = 1 - 0.12 * (k + 1)
        ring = []
        for j in range(na):
            a = 2 * math.pi * j / na
            rr = rim[j] * sc * (1 + 0.06 * r.uniform(-1, 1))
            p = Vector((math.cos(a) * rr, dy, cz - 0.08 * (k + 1) + math.sin(a) * rr))
            p.z = max(-0.02 * k, p.z)
            ring.append(mb.av(p))
        for j in range(na):
            jn = (j + 1) % na
            mb.face([prev[j], prev[jn], ring[jn], ring[j]], [(j / na * 4, k * 0.3), (jn / na * 4, k * 0.3),
                                                             (jn / na * 4, k * 0.3 + 0.3), (j / na * 4, k * 0.3 + 0.3)],
                    'MNF_RockMine', False)
        prev = ring
    cend = mb.av((0, 3.4, cz - 0.4))
    for j in range(na):
        mb.face([prev[j], prev[(j + 1) % na], cend], [(0, 0), (1, 0), (0.5, 1)], 'MNF_RockMine', False)
    # broken rock around the rim and on the floor
    for k in range(10):
        a = r.uniform(0, 6.28) if k < 6 else r.uniform(-2.6, -0.5)
        d = hr * r.uniform(1.05, 1.5)
        p = Vector((math.cos(a) * d, -0.3 - r.uniform(0, 0.4), max(0.0, cz + math.sin(a) * d)))
        if k >= 6:
            p = Vector((r.uniform(-1.6, 1.6), r.uniform(-1.4, -0.4), 0.0))
        sz = r.uniform(0.25, 0.55)
        bm = H.cut_rock(3700 + k, (sz * 1.2, sz, sz * 0.8), cuts=7, subdiv=0, sink=0.1, bevel=0.03 if sz > 0.4 else 0.0)
        H.rock_to_mb(mb, bm, M(p, (r.uniform(-20, 20), r.uniform(-20, 20), r.uniform(0, 360))), 'MNF_RockMine', None,
                     tile=3.0)
        bm.free()
    # deep claw gouges radiating from the hole (dark grooves set into the face)
    for g, (a0, L) in enumerate(((0.5, 1.0), (2.4, 0.9), (3.6, 1.1), (5.6, 0.8))):
        for c in range(4):
            off = (c - 1.5) * 0.09
            dv = Vector((math.cos(a0), 0, math.sin(a0)))
            perp = Vector((-dv.z, 0, dv.x))
            p0 = Vector((0, 0, cz)) + dv * (hr * 1.18) + perp * off
            p1 = p0 + dv * L * (1 - 0.15 * abs(c - 1.5)) + perp * 0.04 * c
            for p in (p0, p1):
                p.y = -0.35 * 0.0 + 0.12 * noise.noise(Vector((p.x * 1.4, 3.0, p.z * 1.4))) - 0.03
            add_beam(mb, p0, p1, 0.028, 0.02, 'MNF_Blackstone', up=(0, -1, 0), chamfer=0.0, tile=1.0, taper=0.3)
    ob = top(mb, 'BorerHole', coll, sharp=45)
    H.col_box(ob, 'COL_Wall_L', (-W, -0.3, 0), (-hr * 0.95, 0.4, Ht))
    H.col_box(ob, 'COL_Wall_R', (hr * 0.95, -0.3, 0), (W, 0.4, Ht))
    H.col_box(ob, 'COL_Wall_Top', (-hr, -0.3, cz + hr * 0.92), (hr, 0.4, Ht))
    H.col_box(ob, 'COL_Floor', (-1.0, 0.0, -0.15), (1.0, 3.2, 0.0))
    NOTES['BorerHole'] = ('Ragged 2.5 m burrow opening in a 5.8 x 4.2 m rock wall piece (XZ plane, -Y out), broken '
                          'rock lip pushed outwards, throat tunnelling 3.4 m into +Y (faces point inwards), rock debris, '
                          'deep claw gouges (MNF_Blackstone grooves). Pivot = centre of the opening floor.')
    return ob


@builder
def PA_Speaker(coll):
    mb = MB()
    obox(mb, (0, -0.008, 0), Vector((0, -1, 0)), Z, (0.12, 0.016, 0.26), 'MNF_MetalRusted', bevel=0.004)
    for bz in (-0.1, 0.1):
        bolt(mb, (0, -0.016, bz), (0, -1, 0), r=0.013)
    add_beam(mb, (0, -0.016, 0.0), (0, -0.3, 0.02), 0.04, 0.04, 'MNF_MetalRusted', chamfer=0.004, tile=1.0)
    add_beam(mb, (0, -0.016, -0.1), (0, -0.25, 0.0), 0.02, 0.03, 'MNF_MetalRusted', chamfer=0.0, tile=1.0)
    # yoke
    for sx in (-0.11, 0.11):
        add_beam(mb, (sx, -0.3, 0.02), (sx, -0.3, -0.06), 0.015, 0.03, 'MNF_MetalRusted', up=(0, 1, 0), chamfer=0.0)
    add_beam(mb, (-0.11, -0.3, 0.035), (0.11, -0.3, 0.035), 0.03, 0.03, 'MNF_MetalRusted', chamfer=0.0)
    d = Vector((0, -1, -0.27)).normalized()
    c0 = Vector((0, -0.2, -0.04))
    driver = [c0 - d * 0.1, c0 - d * 0.02, c0]
    add_tube(mb, driver, [0.06, 0.075, 0.075], 12, 'MNF_MetalPainted_Gray', tile_v=0.3, cap0=True, cap1=False)
    hp = [c0 + d * t for t in (0.0, 0.12, 0.24, 0.33, 0.4, 0.43)]
    hrad = [0.05, 0.07, 0.1, 0.15, 0.21, 0.225]
    add_tube(mb, hp, hrad, 14, 'MNF_MetalPainted_Gray', tile_v=0.5, cap1=False)
    n0 = len(mb.f)
    add_tube(mb, hp, [x * 0.94 for x in hrad], 14, 'MNF_MetalRusted', tile_v=0.5, cap1=False)
    for i in range(n0, len(mb.f)):
        mb.f[i] = mb.f[i][::-1]; mb.uv[i] = mb.uv[i][::-1]
    add_tube(mb, [hp[-1] - d * 0.005, hp[-1] + d * 0.012], [0.232, 0.232], 14, 'MNF_MetalRusted', tile_v=0.3, cap1=False)
    add_tube(mb, [c0 - d * 0.04, c0 - d * 0.05], [0.07, 0.001], 12, 'MNF_Rubber', tile_v=0.3, cap1=False)
    cab = [c0 - d * 0.1, Vector((0.04, -0.12, -0.1)), Vector((0.05, -0.04, -0.15)), Vector((0.05, -0.012, -0.2))]
    add_tube(mb, cab, [0.008] * 4, 4, 'MNF_Rubber', tile_v=0.3, cap1=False)
    ob = top(mb, 'PA_Speaker', coll, sharp=40, mount='wall')
    tip = c0 + d * 0.43
    H.empty(ob, 'SOCKET_Sound', tuple(tip), (math.degrees(math.atan2(0.27, 1.0)), 0, 0))
    NOTES['PA_Speaker'] = ('Old horn loudspeaker on a wall bracket, horn aimed -Y and 15 deg down. Pivot = wall-contact '
                           'centre. SOCKET_Sound at the horn mouth (-Y = sound direction) for the audio source.')
    return ob


@builder
def Crate_Mine(coll):
    r = rng(380)
    mb = MB()
    sx, sy, sz = 0.9, 0.6, 0.6
    add_box(mb, (sx - 0.06, sy - 0.06, sz - 0.06), Matrix.Translation((0, 0, sz / 2)), 'MNF_WoodCrate', tile=1.0)
    t = 0.025
    for k in range(3):     # long sides
        z = 0.03 + (sz - 0.06) * (k + 0.5) / 3
        for s_ in (-1, 1):
            plank(mb, (-sx / 2, s_ * (sy / 2 - t / 2), z), (sx / 2, s_ * (sy / 2 - t / 2), z + r.uniform(-0.004, 0.004)),
                  0.17, t, 'MNF_WoodCrate', up=(0, s_, 0), seed=381 + k + s_ * 10)
            plank(mb, (s_ * (sx / 2 - t / 2), -sy / 2 + t, z), (s_ * (sx / 2 - t / 2), sy / 2 - t, z), 0.17, t,
                  'MNF_WoodCrate', up=(s_, 0, 0), seed=391 + k + s_ * 10)
    for k in range(4):     # lid boards, one shifted
        x = -sx / 2 + sx * (k + 0.5) / 4
        sh = 0.06 if k == 2 else 0.0
        plank(mb, (x, -sy / 2 + sh, sz - t / 2 + (0.01 if k == 2 else 0)), (x, sy / 2 + sh, sz - t / 2), sx / 4 - 0.008, t,
              'MNF_WoodCrate', seed=401 + k)
    for cx in (-1, 1):     # corner battens + iron corner straps
        for cy in (-1, 1):
            add_beam(mb, (cx * (sx / 2 - 0.02), cy * (sy / 2 - 0.02), 0), (cx * (sx / 2 - 0.02), cy * (sy / 2 - 0.02), sz),
                     0.055, 0.055, 'MNF_WoodCrate', up=(0, 1, 0), chamfer=0.006, tile=1.0)
            for zz in (0.04, sz - 0.04):
                add_box(mb, (0.09, 0.09, 0.05), Matrix.Translation((cx * (sx / 2 - 0.03), cy * (sy / 2 - 0.03), zz)),
                        'MNF_MetalRusted', bevel=0.004)
    ob = top(mb, 'Crate_Mine', coll, sharp=40)
    H.col_box(ob, 'COL_Crate', (-sx / 2, -sy / 2, 0), (sx / 2, sy / 2, sz + 0.01))
    NOTES['Crate_Mine'] = '0.9 x 0.6 x 0.6 m board crate (MNF_WoodCrate) with rusted iron corners, one lid board shifted.'
    return ob


@builder
def Barrel_Mine(coll):
    mb = MB()
    R, Hh = 0.29, 0.88
    br = T.Branch([Vector((0, 0, z)) for z in (0.0, 0.03, 0.29, 0.31, 0.57, 0.59, 0.85, 0.88)],
                  [R - 0.01, R, R, R + 0.012, R + 0.012, R, R, R - 0.01], 0, 16)
    off = 3.3

    def dent(i, j, a, dv):
        z = br.pts[i].z
        return 1.0 - 0.05 * max(0, math.cos(a - 1.0)) * math.exp(-((z - 0.45) / 0.15) ** 2) + \
            0.006 * noise.noise(Vector((math.cos(a) * 3 + off, math.sin(a) * 3, z * 4)))
    add_tube(mb, br.pts, br.radii, 16, 'MNF_MetalPainted_Red', tile_v=1.0, urep=2, cap0=True, cap1=False,
             noise_fn=dent, face_mat_fn=lambda i, j, dv: 'MNF_MetalRusted' if i in (0, 6) else 'MNF_MetalPainted_Red')
    # recessed lid with bungs
    lid = [Vector((0, 0, Hh)), Vector((0, 0, Hh - 0.015))]
    add_tube(mb, lid, [R - 0.01, R - 0.025], 16, 'MNF_MetalRusted', tile_v=0.3, cap1=True)
    for (x, y, rr) in ((0.17, 0.05, 0.035), (-0.16, -0.08, 0.022)):
        add_cyl(mb, (x, y, Hh - 0.015), (x, y, Hh), rr, rr, 8, 'MNF_MetalRusted', tile=0.2)
    ob = top(mb, 'Barrel_Mine', coll, sharp=40)
    H.col_box(ob, 'COL_Barrel', (-R, -R, 0), (R, R, Hh))
    NOTES['Barrel_Mine'] = '200 l steel drum (MNF_MetalPainted_Red, rusted rims/lid), rolling hoops, dent, bungs.'
    return ob


def shovel(mb, mm, broken=False, seed=0):
    sub = MB()
    L = 0.45 if broken else 1.0
    add_cyl(sub, (0, 0, 0.27), (0, 0, 0.27 + L), 0.018, 0.017, 6, 'MNF_WoodHandle', tile=0.5, cap1=True)
    if broken:
        add_beam(sub, (0, 0, 0.27 + L - 0.01), (0, 0, 0.27 + L + 0.06), 0.03, 0.03, 'MNF_WoodHandle', taper=0.2,
                 chamfer=0.0, tile=0.5)
    else:
        add_beam(sub, (-0.07, 0, 0.27 + L), (0.07, 0, 0.27 + L), 0.03, 0.03, 'MNF_WoodHandle', chamfer=0.006, tile=0.5)
    add_cyl(sub, (0, 0, 0.2), (0, 0, 0.3), 0.024, 0.02, 6, 'MNF_MetalRusted', tile=0.3)
    # blade: curved plate
    rows = []
    for k in range(4):
        z = 0.22 - 0.22 * k / 3
        w = 0.1 + 0.03 * math.sin(k / 3 * math.pi * 0.8)
        row = [sub.av((x * w, 0.03 * (x * x) - 0.01 * k, z)) for x in (-1, 0, 1)]
        rows.append(row)
    for k in range(3):
        for i in range(2):
            q = [rows[k][i], rows[k][i + 1], rows[k + 1][i + 1], rows[k + 1][i]]
            sub.face(q, [(i * 0.1, k * 0.1), ((i + 1) * 0.1, k * 0.1), ((i + 1) * 0.1, (k + 1) * 0.1), (i * 0.1, (k + 1) * 0.1)],
                     'MNF_MetalRusted', True)
            sub.face(q[::-1], [(i * 0.1, (k + 1) * 0.1), ((i + 1) * 0.1, (k + 1) * 0.1), ((i + 1) * 0.1, k * 0.1),
                               (i * 0.1, k * 0.1)], 'MNF_MetalRusted', True)
    mb.merge(sub, mm)


def pick(mb, mm, broken=False):
    sub = MB()
    L = 0.4 if broken else 0.85
    add_cyl(sub, (0, 0, 0), (0, 0, L), 0.02, 0.018, 6, 'MNF_WoodHandle', tile=0.5)
    head = [Vector((-0.3, 0, L - 0.05)), Vector((-0.15, 0, L + 0.02)), Vector((0, 0, L + 0.04)), Vector((0.15, 0, L + 0.02)),
            Vector((0.3, 0, L - 0.06))]
    add_tube(sub, head, [0.004, 0.018, 0.026, 0.018, 0.004], 5, 'MNF_MetalRusted', tile_v=0.3, cap1=False)
    mb.merge(sub, mm)


@builder
def ToolPile(coll):
    mb = MB()
    shovel(mb, M((0.0, 0.15, 0.03), (-90, 0, 20)) @ M((0, 0, -0.5), (0, 0, 0)))
    shovel(mb, M((0.3, -0.1, 0.06), (-85, 8, -35)) @ M((0, 0, -0.45), (0, 0, 0)), broken=True)
    shovel(mb, M((-0.45, 0.35, 0.0), (-20, 0, 10)), seed=2)
    pick(mb, M((-0.1, -0.25, 0.08), (-88, 0, 70)) @ M((0, 0, -0.4), (0, 0, 0)))
    pick(mb, M((0.45, 0.2, 0.02), (-75, -10, -110)) @ M((0, 0, -0.2), (0, 0, 0)), broken=True)
    add_cyl(mb, (-0.6, -0.3, 0.02), (0.2, -0.55, 0.03), 0.019, 0.018, 6, 'MNF_WoodHandle', tile=0.5)
    zmin = min(v.z for v in mb.v)
    mb.transform(Matrix.Translation((0, 0, -zmin)))
    ob = top(mb, 'ToolPile', coll, sharp=40)
    mn = [min(v[k] for v in mb.v) for k in range(3)]
    mx = [max(v[k] for v in mb.v) for k in range(3)]
    H.col_box(ob, 'COL_Pile', mn, (mx[0], mx[1], min(mx[2], 0.25)))
    NOTES['ToolPile'] = ('Heap of broken shovels and picks (MNF_WoodHandle, MNF_MetalRusted): one shovel leaning, '
                         'broken handles. Decorative (not the Kit_Tools pickaxes).')
    return ob


@builder
def Sign_Level(coll):
    mb = MB()
    add_cyl(mb, (0, 0.02, 0), (0, 0.02, 1.85), 0.03, 0.03, 8, 'MNF_MetalRusted', tile=1.0)
    add_box(mb, (0.22, 0.22, 0.012), Matrix.Translation((0, 0.02, 0.006)), 'MNF_MetalRusted', bevel=0.003)
    for bx in (-0.08, 0.08):
        for by in (-0.08, 0.08):
            bolt(mb, (bx, 0.02 + by, 0.012), (0, 0, 1), r=0.01, h=0.008)
    zc = 1.55
    obox(mb, (0, -0.02, zc), Vector((0, -1, 0)), Z, (0.52, 0.01, 0.52), 'MNF_MetalPainted_Gray', bevel=0.004, jitter=0.002,
         seed=4)
    for z in (zc - 0.17, zc + 0.17):
        ring = [Vector((math.cos(a) * 0.04, 0.02 + math.sin(a) * 0.04, z)) for a in
                [-math.pi / 2 + k * math.pi / 6 for k in range(-3, 10)]]
        add_tube(mb, ring, [0.005] * len(ring), 4, 'MNF_MetalRusted', tile_v=0.3, cap1=False, smooth=False)
    ob = top(mb, 'Sign_Level', coll, sharp=40)
    b = MB()
    add_card(b, Vector((0, -0.0265, zc - 0.23)), (0, 0, 1), (1, 0, 0), 0.46, 0.46, 'MNF_Signs', segs=1)
    H.child_mesh(ob, 'Board', b, (0, -0.0265, zc))
    H.col_box(ob, 'COL_Post', (-0.11, -0.09, 0), (0.11, 0.13, 1.85))
    NOTES['Sign_Level'] = ('Steel post 1.85 m with a 0.52 m painted plate. Child `Board`: 0.46 m square quad (MNF_Signs) '
                           'facing -Y, pivot at its centre (0, -0.027, %.2f).' % zc)
    return ob


def _marker(name, coll, mat):
    mb = MB()
    obox(mb, (0, -0.006, 0), Vector((0, -1, 0)), Z, (0.08, 0.012, 0.32), 'MNF_MetalRusted', bevel=0.003)
    for bz in (-0.12, 0.12):
        bolt(mb, (0, -0.012, bz), (0, -1, 0), r=0.011)
    add_beam(mb, (0, -0.012, 0.0), (0, -0.045, 0.0), 0.05, 0.05, 'MNF_MetalRusted', chamfer=0.0, tile=0.5)
    ob = top(mb, name, coll, sharp=40, mount='wall')
    plate = MB()
    obox(plate, (0, -0.05, 0), Vector((0, -1, 0)), Vector((1, 0, 1)).normalized(), (0.24, 0.008, 0.24), mat, bevel=0.003,
         jitter=0.001, seed=5)
    bolt(plate, (0, -0.054, 0), (0, -1, 0), r=0.012)
    H.child_mesh(ob, 'Plate', plate, (0, -0.05, 0))
    NOTES[name] = ('Wall-mounted colour-coded tunnel marker: diamond plate child `Plate` (%s), pivot at the plate '
                   'centre; bracket pivot = wall-contact centre, -Y out.' % mat)
    return ob


@builder
def TunnelMarker_Red(coll):
    return _marker('TunnelMarker_Red', coll, 'MNF_MetalPainted_Red')


@builder
def TunnelMarker_Yellow(coll):
    return _marker('TunnelMarker_Yellow', coll, 'MNF_MetalPainted_Yellow')


@builder
def TunnelMarker_Green(coll):
    return _marker('TunnelMarker_Green', coll, 'MNF_MetalPainted_Green')


@builder
def PipeRun(coll):
    r = rng(390)
    mb = MB()
    zc, R = 0.72, 0.25

    def duct(x0, x1, seed):
        pts = [Vector((x0 + (x1 - x0) * k / 4, 0, zc)) for k in range(5)]
        dent_c = r.uniform(0.3, 0.7)
        rad = [R] * 5

        def nf(i, j, a, dv):
            t = i / 4
            return 1.0 - 0.07 * max(0.0, dv.z) * math.exp(-((t - dent_c) / 0.2) ** 2) * (1 if seed % 2 else 0)
        add_tube(mb, pts, rad, 14, 'MNF_MetalRusted', tile_v=1.5, urep=1, cap1=False, noise_fn=nf)
    duct(-2.0, 0.0, 1)
    duct(0.0, 2.0, 2)
    for x in (-2.0, 0.0, 2.0):
        add_cyl(mb, (x - 0.025, 0, zc), (x + 0.025, 0, zc), R + 0.035, R + 0.035, 14, 'MNF_MetalRusted', tile=1.0,
                cap0=x == -2.0, cap1=x == 2.0, up=(0, 0, 1))
    # inner dark disc at the ends (duct is hollow)
    for x in (-1.99, 1.99):
        add_cyl(mb, (x, 0, zc), (x + 0.001 * (1 if x < 0 else -1), 0, zc), R * 0.95, R * 0.95, 14, 'MNF_Rubber', tile=1.0,
                cap0=True, cap1=False)
    # small air line alongside
    add_cyl(mb, (-2.0, 0.38, zc - 0.17), (2.0, 0.38, zc - 0.17), 0.05, 0.05, 8, 'MNF_MetalPainted_Green', tile=1.0)
    # saddle stands
    for x in (-1.2, 1.2):
        for sy in (-1, 1):
            add_beam(mb, (x, sy * 0.32, 0.0), (x, sy * 0.3, zc - 0.25), 0.05, 0.05, 'MNF_MetalRusted', up=(1, 0, 0),
                     chamfer=0.004, tile=1.0)
        add_beam(mb, (x, -0.36, zc - 0.25), (x, 0.48, zc - 0.25), 0.07, 0.05, 'MNF_MetalRusted', chamfer=0.004, tile=1.0)
        add_box(mb, (0.16, 0.8, 0.012), Matrix.Translation((x, 0.0, 0.006)), 'MNF_MetalRusted', bevel=0.003)
        strap = [Vector((x, math.cos(a) * (R + 0.012), zc + math.sin(a) * (R + 0.012))) for a in
                 [math.pi + k * math.pi / 8 for k in range(-1, 10)]]
        add_tube(mb, strap, [0.008] * len(strap), 4, 'MNF_MetalRusted', tile_v=0.5, cap1=False, smooth=False)
    ob = top(mb, 'PipeRun', coll, sharp=40)
    H.col_box(ob, 'COL_Pipe', (-2.03, -0.4, 0), (2.03, 0.45, zc + R + 0.04))
    NOTES['PipeRun'] = ('4 m rusty ventilation duct (0.5 m) along X on two floor saddles, flanged joints at x=-2/0/+2 '
                        '(chain every 4 m), dent, small green air line alongside.')
    return ob


@builder
def Generator_Small(coll):
    mb = MB()
    for sy in (-0.32, 0.32):
        add_beam(mb, (-0.65, sy, 0.05), (0.65, sy, 0.05), 0.08, 0.1, 'MNF_MetalRusted', chamfer=0.004, tile=1.5)
    for sx in (-0.65, 0.65):
        obox(mb, (sx * 1.005, 0, 0.05), Vector((1 if sx > 0 else -1, 0, 0)), Z, (0.72, 0.008, 0.09), 'MNF_Hazard')
    add_box(mb, (1.3, 0.72, 0.02), Matrix.Translation((0, 0, 0.11)), 'MNF_MetalRusted', tile=1.5)
    # engine block + fins + alternator
    add_box(mb, (0.55, 0.5, 0.42), Matrix.Translation((-0.25, 0, 0.33)), 'MNF_MetalPainted_Green', bevel=0.025, tile=1.0)
    for k in range(6):
        add_box(mb, (0.5, 0.012, 0.12), Matrix.Translation((-0.25, -0.15 + k * 0.06, 0.6)), 'MNF_MetalRusted')
    add_cyl(mb, (0.03, 0, 0.32), (0.5, 0, 0.32), 0.17, 0.17, 14, 'MNF_MetalPainted_Green', tile=1.0)
    for k in range(5):
        x = 0.1 + k * 0.08
        add_cyl(mb, (x, 0, 0.32), (x + 0.02, 0, 0.32), 0.18, 0.18, 14, 'MNF_MetalRusted', tile=1.0, cap0=False, cap1=False)
    # fuel tank on a frame
    for sx in (-0.5, 0.45):
        for sy in (-0.28, 0.28):
            add_beam(mb, (sx, sy, 0.12), (sx, sy, 0.72), 0.03, 0.03, 'MNF_MetalRusted', up=(0, 1, 0), chamfer=0.0)
    add_tube(mb, [Vector((-0.55, 0, 0.82)), Vector((-0.5, 0, 0.82)), Vector((0.45, 0, 0.82)), Vector((0.5, 0, 0.82))],
             [0.08, 0.12, 0.12, 0.08], 14, 'MNF_MetalPainted_Red', tile_v=1.0, cap0=True, cap1=True)
    add_cyl(mb, (0.2, 0, 0.93), (0.2, 0, 0.98), 0.035, 0.035, 8, 'MNF_MetalRusted', tile=0.3)
    # exhaust + muffler
    ex = [Vector((-0.45, -0.2, 0.45)), Vector((-0.6, -0.25, 0.5)), Vector((-0.62, -0.25, 0.8)), Vector((-0.6, -0.2, 1.05))]
    add_tube(mb, ex, [0.03] * 4, 8, 'MNF_MetalRusted', tile_v=0.5, cap1=True)
    add_cyl(mb, (-0.62, -0.25, 0.55), (-0.62, -0.25, 0.78), 0.06, 0.06, 10, 'MNF_MetalRusted', tile=0.5)
    # control panel with gauges
    obox(mb, (0.45, -0.3, 0.6), Vector((0, -1, 0)), Z, (0.3, 0.08, 0.25), 'MNF_MetalPainted_Gray', bevel=0.008)
    for gx in (0.38, 0.52):
        add_cyl(mb, (gx, -0.34, 0.63), (gx, -0.36, 0.63), 0.045, 0.045, 12, 'MNF_MetalBare', tile=0.2, cap1=False)
        add_cyl(mb, (gx, -0.345, 0.63), (gx, -0.352, 0.63), 0.038, 0.038, 12, 'MNF_Glass', tile=0.2, cap0=False)
    for gx in (0.36, 0.45, 0.54):
        add_cyl(mb, (gx, -0.34, 0.53), (gx, -0.37, 0.53), 0.012, 0.012, 6, 'MNF_Plastic_Black', tile=0.2)
    cab = [Vector((0.6, -0.25, 0.55)), Vector((0.75, -0.3, 0.3)), Vector((0.85, -0.5, 0.03)), Vector((1.3, -0.7, 0.02))]
    add_tube(mb, cab, [0.015] * 4, 5, 'MNF_Rubber', tile_v=0.5, cap1=True)
    ob = top(mb, 'Generator_Small', coll, sharp=40)
    H.col_box(ob, 'COL_Body', (-0.67, -0.4, 0), (0.67, 0.4, 0.98))
    NOTES['Generator_Small'] = ('Dead mine generator on a skid (1.3 x 0.72 m): engine block with cooling fins, '
                                'alternator, red fuel tank, exhaust + muffler, gauge panel facing -Y, hazard-striped skid '
                                'ends, trailing cable.')
    return ob


@builder
def ScratchedPlate(coll):
    r = rng(400)
    mb = MB()
    N = 30
    Wd = 2.0
    strokes = []
    for (ax, az, ang, L) in ((-0.45, 0.55, -62, 0.75), (0.15, 0.3, -70, 0.6), (-0.2, -0.25, -55, 0.5)):
        d = Vector((math.cos(math.radians(ang)), 0, math.sin(math.radians(ang))))
        perp = Vector((-d.z, 0, d.x))
        for c in range(4):
            o = perp * (c - 1.5) * 0.065
            a = Vector((ax, 0, az)) + o + d * abs(c - 1.5) * 0.04
            b = a + (Quaternion((0, 1, 0), math.radians((c - 1.5) * 3)) @ d) * L * (1 - 0.12 * abs(c - 1.5))
            strokes.append((a, b, perp * r.uniform(0.02, 0.05)))
    def bulge(x, z):
        # broad dents punched from behind (towards -Y)
        d = 0.06 * math.exp(-(((x + 0.1) ** 2 + (z - 0.1) ** 2) / 0.15))
        d += 0.025 * math.exp(-(((x - 0.55) ** 2 + (z + 0.45) ** 2) / 0.05))
        return d
    N = 20
    grid = []
    for j in range(N + 1):
        row = []
        for i in range(N + 1):
            x = -Wd / 2 + Wd * i / N
            z = -Wd / 2 + Wd * j / N
            edge = i in (0, N) or j in (0, N)
            row.append(mb.av((x, -0.012 - (0 if edge else bulge(x, z)), z)))
        grid.append(row)
    for j in range(N):
        for i in range(N):
            q = [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
            mb.face(q, [((i) / N * 2, j / N * 2), ((i + 1) / N * 2, j / N * 2), ((i + 1) / N * 2, (j + 1) / N * 2),
                        (i / N * 2, (j + 1) / N * 2)], 'MNF_MetalPainted_Gray', True)
    # claw strokes pushed out from the other side: raised, tapered ridges with torn dark centres
    for a, b, bow in strokes:
        steps = 3
        pts = []
        for k in range(steps + 1):
            t = k / steps
            p = a.lerp(b, t) + bow * math.sin(t * math.pi)
            p.y = -0.012 - bulge(p.x, p.z) - 0.002
            pts.append(p)
        for k in range(steps):
            t0, t1 = k / steps, (k + 1) / steps
            w = 0.034
            add_beam(mb, pts[k], pts[k + 1], w, 0.016, 'MNF_MetalPainted_Gray', up=(0, -1, 0), chamfer=0.007, tile=1.0,
                     taper=(0.5 if k == steps - 1 else 1.0), cap0=(k == 0), cap1=(k == steps - 1))
    # back + rim
    add_box(mb, (Wd, 0.006, Wd), Matrix.Translation((0, -0.003, 0)), 'MNF_MetalPainted_Gray')
    for k in range(4):
        a = k * math.pi / 2
        for t in range(8):
            u = -Wd / 2 + 0.06 + (Wd - 0.12) * t / 7
            x, z = [(u, Wd / 2 - 0.05), (Wd / 2 - 0.05, u), (u, -Wd / 2 + 0.05), (-Wd / 2 + 0.05, u)][k]
            if t in (0, 7) and k % 2:
                continue
            bolt(mb, (x, -0.012, z), (0, -1, 0), r=0.016, h=0.01, segs=6)
    ob = top(mb, 'ScratchedPlate', coll, sharp=60, mount='wall')
    H.col_box(ob, 'COL_Plate', (-1.0, -0.03, -1.0), (1.0, 0.0, 1.0))
    NOTES['ScratchedPlate'] = ('2 x 2 m riveted steel wall panel (MNF_MetalPainted_Gray). Pivot = wall-contact centre '
                               '(panel spans z=-1..1), -Y out. Raised claw-stroke ridges and a dent bulge TOWARDS the '
                               'player, as if something scratched and hit it from the other side.')
    return ob


if __name__ == '__main__':
    H.run_kit(KIT, BUILDERS, NOTES)
