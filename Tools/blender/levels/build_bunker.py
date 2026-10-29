"""Survivor Bunker 7 + exit corridor. Floor at z = -10 (underground), corridor ramps up to the portal at
y = 44 (ground level z = 0) where it meets the concrete cut in the forest terrain.

Layout (Blender XY, +Y = north toward the forest):
  Main hall      x[-8, 8]   y[-12, 4]    workbench + terminal + dispenser, tool rack, sell machine, locker
  Bunk room      x[-16.3,-8.3] y[-12,-2] spawn, beds, radio
  Generator room x[8.3, 16.3] y[-12,-2]  generator, catwalk, pipes
  Utility corridor x[-1.5,1.5] y[-30,-12.3] -> storage room x[1.8, 9] y[-24,-15]; sealed SECTOR B door at the end
  Security gate in the hall's north wall (y = 4..4.3), exit corridor x[-2, 2] from y 4.3 to 44
"""
import math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lvl_common import *

Z0 = -10.0          # bunker floor
H = 4.2             # room height
T = 0.3             # wall thickness
CORR_W = 4.0
CORR_H = 3.5


def ramp_floor_z(y):
    """Exit corridor floor height."""
    if y <= 10:
        return Z0
    if y >= 40:
        return 0.0
    return Z0 + (y - 10) / 30.0 * 10.0


def wall_x(g, x0, x1, y, z0, h, openings, mat='MNF_ConcreteWall', t=T):
    """Wall running along X between x0..x1, occupying y..y+t. openings: [(cx, width, height)]."""
    cuts = sorted(openings)
    x = x0
    for cx, w, oh in cuts:
        a, b = cx - w / 2, cx + w / 2
        if a > x:
            g.box((x, y, z0), (a, y + t, z0 + h), mat)
        g.box((a, y, z0 + oh), (b, y + t, z0 + h), mat)   # lintel
        x = b
    if x < x1:
        g.box((x, y, z0), (x1, y + t, z0 + h), mat)


def wall_y(g, y0, y1, x, z0, h, openings, mat='MNF_ConcreteWall', t=T):
    cuts = sorted(openings)
    y = y0
    for cy, w, oh in cuts:
        a, b = cy - w / 2, cy + w / 2
        if a > y:
            g.box((x, y, z0), (x + t, a, z0 + h), mat)
        g.box((x, a, z0 + oh), (x + t, b, z0 + h), mat)
        y = b
    if y < y1:
        g.box((x, y, z0), (x + t, y1, z0 + h), mat)


def floor_ceiling(g, x0, x1, y0, y1, z0, h, floor_mat='MNF_ConcreteFloor', ceil_mat='MNF_ConcreteWall'):
    g.box((x0 - T, y0 - T, z0 - 0.4), (x1 + T, y1 + T, z0), floor_mat)
    g.box((x0 - T, y0 - T, z0 + h), (x1 + T, y1 + T, z0 + h + 0.4), ceil_mat)


def hazard_strip(g, x0, y0, x1, y1, z):
    g.box((x0, y0, z), (x1, y1, z + 0.012), 'MNF_Hazard', faces='Z', tile=0.8)


def pipe_run(g, pts, r, mat):
    for a, b in zip(pts[:-1], pts[1:]):
        g.cylinder(a, b, r, mat, seg=10, caps=False, tile=1.0)
    # brackets
    for a, b in zip(pts[:-1], pts[1:]):
        A, B = Vector(a), Vector(b)
        n = int((B - A).length // 2.5)
        for i in range(1, n + 1):
            p = A + (B - A) * (i / (n + 1))
            g.box((p.x - 0.04, p.y - 0.04, p.z), (p.x + 0.04, p.y + 0.04, p.z + r + 0.35), 'MNF_MetalRusted')


def build(out_dir):
    reset_scene()
    geo_c = collection('BunkerGeometry')
    mk_c = collection('BunkerMarkers')
    g = Geo(tile=2.0)

    # ---------------- main hall
    floor_ceiling(g, -8, 8, -12, 4, Z0, H)
    wall_x(g, -8 - T, 8 + T, 4.0, Z0, H, [(0.0, 3.0, 2.8)])                 # north: security gate opening
    wall_x(g, -8 - T, 8 + T, -12 - T, Z0, H, [(0.0, 2.0, 2.4)])             # south: utility corridor
    wall_y(g, -12, 4, -8 - T, Z0, H, [(-7.0, 1.6, 2.3)])                    # west: bunk room door
    wall_y(g, -12, 4, 8, Z0, H, [(-5.0, 1.6, 2.3)])                         # east: generator room door
    # ceiling beams + wall base trim
    for x in (-6, -2, 2, 6):
        g.box((x - 0.15, -12, Z0 + H - 0.45), (x + 0.15, 4, Z0 + H), 'MNF_MetalPainted_Gray')
    for (a, b) in (((-8, -12), (8, -11.9)), ((-8, 3.9), (8, 4.0))):
        g.box((a[0], a[1], Z0), (b[0], b[1], Z0 + 0.25), 'MNF_MetalPainted_Green')
    # hazard stripes: gate threshold and in front of the sell machine
    hazard_strip(g, -2.2, 2.6, 2.2, 3.95, Z0)
    hazard_strip(g, 6.2, -2.8, 7.95, -0.2, Z0)
    # raised metal floor plate at the workbench
    g.box((-7.6, 1.6, Z0), (-1.6, 3.95, Z0 + 0.06), 'MNF_MetalDiamond', tile=1.2)
    # pipes along the north and east walls
    pipe_run(g, [(-7.7, 3.7, Z0 + 3.6), (7.7, 3.7, Z0 + 3.6)], 0.09, 'MNF_MetalPainted_Green')
    pipe_run(g, [(-7.7, 3.45, Z0 + 3.85), (7.7, 3.45, Z0 + 3.85)], 0.06, 'MNF_MetalPainted_Red')
    pipe_run(g, [(7.7, 3.7, Z0 + 3.3), (7.7, -11.7, Z0 + 3.3)], 0.12, 'MNF_MetalPainted_Gray')
    # cable tray over the hall
    g.box((-7.5, -1.2, Z0 + 3.55), (7.5, -0.8, Z0 + 3.6), 'MNF_MetalGrate', tile=0.6)

    # ---------------- bunk room
    floor_ceiling(g, -16.3, -8.3, -12, -2, Z0, H)
    wall_x(g, -16.3 - T, -8.3, -2.0, Z0, H, [])
    wall_x(g, -16.3 - T, -8.3, -12 - T, Z0, H, [])
    wall_y(g, -12, -2, -16.3 - T, Z0, H, [])

    # ---------------- generator room (with a grated catwalk over a cable pit)
    floor_ceiling(g, 8.3, 16.3, -12, -2, Z0, H, floor_mat='MNF_ConcreteFloor')
    wall_x(g, 8.3, 16.3 + T, -2.0, Z0, H, [])
    wall_x(g, 8.3, 16.3 + T, -12 - T, Z0, H, [])
    wall_y(g, -12, -2, 16.3, Z0, H, [])
    hazard_strip(g, 10.6, -9.6, 14.4, -9.4, Z0)
    hazard_strip(g, 10.6, -4.6, 14.4, -4.4, Z0)
    hazard_strip(g, 10.4, -9.6, 10.6, -4.4, Z0)
    hazard_strip(g, 14.4, -9.6, 14.6, -4.4, Z0)
    pipe_run(g, [(16.0, -2.4, Z0 + 0.4), (16.0, -2.4, Z0 + 3.4), (8.6, -2.4, Z0 + 3.4)], 0.14, 'MNF_MetalRusted')
    pipe_run(g, [(16.0, -11.6, Z0 + 0.6), (16.0, -11.6, Z0 + 3.0), (12.0, -11.6, Z0 + 3.0)], 0.1, 'MNF_MetalPainted_Red')

    # ---------------- utility corridor + storage room
    floor_ceiling(g, -1.5, 1.5, -30, -12.3, Z0, 3.2)
    wall_y(g, -30, -12.3, -1.5 - T, Z0, 3.2, [])
    wall_y(g, -30, -12.3, 1.5, Z0, 3.2, [(-19.5, 1.6, 2.3)])
    wall_x(g, -1.5 - T, 1.5 + T, -30 - T, Z0, 3.2, [])
    floor_ceiling(g, 1.8, 9.0, -24, -15, Z0, 3.4)
    wall_x(g, 1.8, 9.0 + T, -15.0, Z0, 3.4, [])
    wall_x(g, 1.8, 9.0 + T, -24 - T, Z0, 3.4, [])
    wall_y(g, -24, -15, 9.0, Z0, 3.4, [])
    pipe_run(g, [(-1.2, -12.5, Z0 + 2.9), (-1.2, -29.7, Z0 + 2.9)], 0.08, 'MNF_MetalRusted')
    pipe_run(g, [(1.2, -12.5, Z0 + 2.75), (1.2, -29.7, Z0 + 2.75)], 0.05, 'MNF_MetalPainted_Green')
    # sealed SECTOR B door at the end: a heavy steel slab with hazard frame
    g.box((-1.3, -29.95, Z0), (1.3, -29.7, Z0 + 2.6), 'MNF_MetalRusted')
    g.box((-1.5, -29.7, Z0 + 2.6), (1.5, -29.6, Z0 + 2.9), 'MNF_Hazard', tile=0.8)

    # ---------------- exit corridor (ramp) and portal
    y0c = 4.3
    ys = [y0c] + [10 + i * 2.5 for i in range(13)] + [42.5, 44.0]
    for a, b in zip(ys[:-1], ys[1:]):
        za, zb = ramp_floor_z(a), ramp_floor_z(b)
        hw = CORR_W / 2
        # floor (sloped slab), ceiling, walls as quads with thickness
        mat_floor = 'MNF_MetalDiamond' if b < 10.5 else 'MNF_ConcreteFloor'
        g.slab([(-hw - T, a, za - 0.4), (hw + T, a, za - 0.4), (hw + T, b, zb - 0.4), (-hw - T, b, zb - 0.4)], 0.4, mat_floor)
        g.slab([(-hw - T, a, za + CORR_H), (hw + T, a, za + CORR_H), (hw + T, b, zb + CORR_H), (-hw - T, b, zb + CORR_H)], 0.4, 'MNF_ConcreteWall')
        for x in (-hw - T, hw):
            g.slab([(x, a, za), (x + T, a, za), (x + T, b, zb), (x, b, zb)], CORR_H, 'MNF_ConcreteWall')
        # hand rail on the west wall
        g.cylinder((-hw + 0.08, a, za + 1.0), (-hw + 0.08, b, zb + 1.0), 0.03, 'MNF_MetalPainted_Yellow', seg=6, caps=False)
    # corridor-side wall around the gate (thicker frame face) and lights recess
    g.box((-2.0, 4.3, Z0 + 2.8), (2.0, 4.5, Z0 + CORR_H), 'MNF_Hazard', tile=0.8)
    # portal frame at the mouth
    g.box((-3.2, 42.8, 0), (-2.0, 44.3, 4.4), 'MNF_ConcreteWall')
    g.box((2.0, 42.8, 0), (3.2, 44.3, 4.4), 'MNF_ConcreteWall')
    g.box((-3.2, 42.8, 3.5), (3.2, 44.3, 4.6), 'MNF_ConcreteWall')
    g.box((-2.0, 44.25, 3.5), (2.0, 44.35, 3.9), 'MNF_Hazard', tile=0.8)
    hazard_strip(g, -2.0, 41.0, 2.0, 42.0, 0.0)

    ob = g.build('BunkerShell', geo_c)
    merge_by_distance(ob)

    # ---------------- zones
    zone_box('ZONE_Bunker_4', (-17, -31, Z0 - 0.5), (17, 4.15, Z0 + H + 0.5), geo_c)
    zone_box('ZONE_Corridor_5', (-2.4, 4.15, Z0 - 0.5), (2.4, 43.0, 5.0), geo_c)

    # ---------------- markers
    M = lambda n, loc, fwd=(0, -1, 0), **k: marker(n, loc, fwd, mk_c, **k)
    S, N, E, W = (0, -1, 0), (0, 1, 0), (1, 0, 0), (-1, 0, 0)
    M('MK_SPAWN_Player', (-11.5, -7.0, Z0), E)
    M('MK_SPAWN_Respawn', (-11.5, -8.5, Z0), E)
    M('MK_STATION_Gate', (0, 4.15, Z0), N)
    M('MK_STATION_Workbench', (-4.6, 3.35, Z0), S)
    M('MK_STATION_Terminal', (-6.65, 3.45, Z0), S)                 # floor console beside the bench
    M('MK_STATION_Dispenser', (-3.0, 3.98, Z0 + 1.05), S)
    M('MK_STATION_ToolRack', (-7.98, -1.0, Z0 + 1.35), E)
    M('MK_STATION_SellMachine', (7.3, -1.5, Z0), W)
    M('MK_STATION_StorageLocker', (7.55, 1.8, Z0), W)
    M('MK_STATION_Bed', (-15.6, -4.6, Z0), E)
    M('MK_PROP_Bunkbed', (-15.6, -9.8, Z0), E)
    M('MK_PROP_Table', (-10.4, -11.2, Z0), N)
    M('MK_STATION_Radio', (-10.4, -11.2, Z0 + 0.78), N)
    M('MK_PROP_Chair', (-10.4, -10.3, Z0), S)
    M('MK_PROP_Locker_Tall', (-12.8, -2.35, Z0), S)
    M('MK_PROP_Locker_Tall', (-13.8, -2.35, Z0), S)
    M('MK_PROP_PosterBoard', (-16.25, -7.0, Z0 + 1.5), E)
    M('MK_LORE_lore_welcome', (-10.2, -11.0, Z0 + 0.82), N)
    M('MK_STATION_Generator', (12.5, -7.0, Z0), W)
    M('MK_PROP_FuseBox', (16.25, -5.0, Z0 + 1.5), W)
    M('MK_PROP_VentFan', (16.25, -9.5, Z0 + 2.6), W)
    M('MK_PROP_Barrel', (15.4, -11.3, Z0), N)
    M('MK_PROP_Barrel', (14.6, -11.4, Z0), N)
    M('MK_PROP_Bucket', (9.2, -11.4, Z0), N)
    # hall clutter
    M('MK_PROP_Table', (2.5, -6.5, Z0), S)
    M('MK_PROP_Chair', (2.5, -7.4, Z0), N)
    M('MK_PROP_Chair', (1.5, -5.8, Z0), E)
    M('MK_PROP_Clipboard', (2.6, -6.4, Z0 + 0.8), S)
    M('MK_PROP_ShelfUnit', (-6.8, -11.6, Z0), N)
    M('MK_PROP_ShelfUnit', (-4.6, -11.6, Z0), N)
    M('MK_PROP_ShelfUnit', (4.6, -11.6, Z0), N)
    M('MK_PROP_Crate_A', (6.8, -11.2, Z0), N)
    M('MK_PROP_Crate_B', (6.9, -10.2, Z0), W)
    M('MK_PROP_Crate_A', (-7.3, -8.9, Z0), E)
    M('MK_PROP_VentFan', (0.0, -11.95, Z0 + 3.4), N)
    M('MK_PROP_CableBundle', (-5.0, 3.9, Z0 + 3.2), S)
    M('MK_ITEM_food_can', (2.2, -6.7, Z0 + 0.8), S)
    M('MK_ITEM_glowstick', (-3.3, 3.2, Z0 + 0.96), S)
    M('MK_ITEM_glowstick', (-3.15, 3.25, Z0 + 0.96), S)
    # utility corridor and storage
    for y in (-15, -18.5, -22.5, -26.5):
        M('MK_PROP_ShelfUnit', (-1.15, y, Z0), E)
    M('MK_PROP_ShelfUnit', (8.6, -17.5, Z0), W)
    M('MK_PROP_ShelfUnit', (8.6, -21.5, Z0), W)
    M('MK_PROP_Crate_A', (3.0, -23.3, Z0), N)
    M('MK_PROP_Crate_B', (4.3, -23.4, Z0), N)
    M('MK_PROP_Crate_A', (3.4, -22.2, Z0 + 0.0), E)
    M('MK_PROP_Barrel', (7.8, -15.7, Z0), S)
    M('MK_LORE_lore_radio', (4.0, -23.2, Z0 + 0.75), N)
    M('MK_EVENT_PipeKnock', (-1.2, -21.0, Z0 + 2.9))
    M('MK_EVENT_PipeKnock', (7.7, -6.0, Z0 + 3.3))
    M('MK_EVENT_BunkerCreak', (0, -28.0, Z0 + 2.5))
    # signs and decals
    M('MK_SIGN_1_0.7_0.7', (2.2, 3.98, Z0 + 1.8), S)              # KEEP GATE CLOSED (hall side)
    M('MK_SIGN_2_0.9_0.9', (-2.3, 4.52, Z0 + 2.0), N)             # SURVIVOR BUNKER 7 (corridor side)
    M('MK_SIGN_10_0.6_0.6', (-6.0, 3.98, Z0 + 2.6), S)            # EQUIPMENT
    M('MK_SIGN_9_0.6_0.6', (7.98, -1.5, Z0 + 2.4), W)             # ASSAY / TRADE
    M('MK_SIGN_11_0.6_0.6', (7.98, 1.8, Z0 + 2.4), W)             # STORAGE
    M('MK_SIGN_4_0.5_0.5', (8.32, -3.6, Z0 + 1.8), W)             # HIGH VOLTAGE next to the generator door
    M('MK_SIGN_0_0.8_0.8', (0.0, -29.65, Z0 + 1.7), N)            # DANGER on SECTOR B door
    M('MK_SIGN_12_0.5_0.6', (-16.25, -5.4, Z0 + 1.6), E)          # MISSING poster
    M('MK_SIGN_8_0.6_0.6', (2.05, 4.52, Z0 + 2.0), N)             # EVACUATION ROUTE
    M('MK_DECAL_5_1.0', (0.0, -29.62, Z0 + 1.0), N)               # deep claw scratches on the sealed door
    M('MK_DECAL_4_0.8', (-0.9, -29.62, Z0 + 0.6), N)
    M('MK_DECAL_1_1.2', (-7.95, -9.0, Z0 + 2.6), E)
    M('MK_DECAL_1_1.2', (7.98, -9.5, Z0 + 2.8), W)
    M('MK_DECAL_3_1.2', (0.5, -3.0, Z0 + 0.02), (0, 0, 1), pitch=math.radians(-90))  # oil stain on the floor
    M('MK_DECAL_9_0.6', (-16.25, -10.5, Z0 + 1.2), E)             # tally marks by the beds
    M('MK_DECAL_12_1.0', (16.25, -7.0, Z0 + 3.0), W)              # rust drips
    # lights
    for x in (-4.0, 4.0):
        for y in (-8.0, -2.5, 2.0):
            M('MK_LIGHT_Fluor', (x, y, Z0 + H), S)
    M('MK_LIGHT_Fluor', (-12.3, -7.0, Z0 + H), S)
    M('MK_LIGHT_FluorBad', (12.3, -7.0, Z0 + H), S)
    M('MK_LIGHT_FluorBad', (0.0, -16.0, Z0 + 3.2), S)
    M('MK_LIGHT_FluorBad', (0.0, -24.0, Z0 + 3.2), S)
    M('MK_LIGHT_Cage', (5.4, -14.98, Z0 + 2.4), S)
    M('MK_LIGHT_Red', (-1.9, 3.98, Z0 + 3.2), S)
    M('MK_LIGHT_Red', (1.9, 3.98, Z0 + 3.2), S)
    M('MK_LIGHT_Emergency', (-7.98, -4.0, Z0 + 3.0), E)
    M('MK_LIGHT_Emergency', (7.98, 0.0, Z0 + 3.0), W)
    M('MK_LIGHT_Emergency', (-12.0, -2.02, Z0 + 3.0), S)
    M('MK_LIGHT_Emergency', (12.0, -2.02, Z0 + 3.0), S)
    for y in (9.0, 18.0, 27.0, 36.0):
        M('MK_LIGHT_Cage', (1.98, y, ramp_floor_z(y) + 2.6), W)
    M('MK_LIGHT_Red', (0.0, 42.6, 3.4), S)
    # outside: the blast door swung open against the cut wall
    M('MK_PROP_BlastDoor', (5.45, 47.5, 0.0), W)                   # swung open, flat against the cut wall
    M('MK_TELEPORT_Bunker', (0, -4, Z0), N)
    M('MK_TELEPORT_Portal', (0, 47, 0.1), N)

    objs = [o for o in bpy.data.objects if o.name != 'PreviewCam' and o.type in ('MESH', 'EMPTY')]
    export_fbx(os.path.join(out_dir, 'Bunker.fbx'), objs)
    return objs


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    root = argv[0] if argv else os.path.join(os.path.dirname(__file__), '..', '..', '..')
    out = os.path.join(root, 'Assets', 'MonkeyNoFear', 'Art', 'Models', 'Levels')
    objs = build(out)
    prev = os.path.join(root, 'Docs', 'previews', 'levels')
    os.makedirs(prev, exist_ok=True)
    # cutaway preview from above (ceiling hidden by placing the camera inside the shell)
    render_preview(os.path.join(prev, 'bunker_hall.png'), (-6.5, -10.5, Z0 + 3.4), (2, 3, Z0 + 0.8), lens=16, samples=12, sun=False, world=0.05,
                   extra_lights=[((0, -4, Z0 + 3.5), 1500), ((-12, -7, Z0 + 3.5), 600), ((12, -7, Z0 + 3.5), 600), ((0, 20, -3), 800)])
    print('bunker objects', len(objs))
