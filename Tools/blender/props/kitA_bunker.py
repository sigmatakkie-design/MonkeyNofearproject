"""kitA_bunker.py - Kit_Bunker.fbx: survivor bunker furniture & machinery (prop artist A).

Pivots (ASSET_SPEC §6): floor props at the bottom centre, wall props at the wall-contact centre with -Y
pointing out of the wall, ceiling props at the top contact point.  Front faces -Y.
Moving parts are separate top-level objects (TerminalButton_Cap, BigButton_Cap, Lever_Handle,
SecurityGate_Bars); their bodies carry a SOCKET_* empty that marks where the moving part's pivot sits.
"""
import math
import random

import bmesh
from mathutils import Vector, Matrix

import propkit_a_helpers as H
from propkit_a_helpers import MB, xf, lerp

KIT = "Kit_Bunker"
T_BIG, T_MED, T_SMALL = 2.0, 1.5, 0.5
OVERVIEW_ROWS = 3
OVERVIEW_CELL = 0.5

GRAY, GREEN, YEL, RED = "MNF_MetalPainted_Gray", "MNF_MetalPainted_Green", "MNF_MetalPainted_Yellow", "MNF_MetalPainted_Red"
BARE, RUST, HAZ, RUB = "MNF_MetalBare", "MNF_MetalRusted", "MNF_Hazard", "MNF_Rubber"

REQUIRED = {
    "Workbench": [], "Terminal": ["Screen"], "TerminalButton_Body": [], "TerminalButton_Cap": [],
    "BigButton_Body": [], "BigButton_Cap": [], "Lever_Base": [], "Lever_Handle": [],
    "SecurityGate_Frame": [], "SecurityGate_Bars": ["COL_Bars"], "WarningBeacon": ["Lamp"],
    "FluorescentFixture": ["Tube"], "CageLamp": ["Bulb"], "EmergencyLight": ["Bulb"],
    "ToolRack": ["SOCKET_0", "SOCKET_1", "SOCKET_2", "SOCKET_3", "SOCKET_4", "SOCKET_5"],
    "ShelfUnit": [], "StorageLocker": ["SOCKET_Deposit"], "SellMachine": ["SOCKET_Bin", "Screen"],
    "Dispenser": ["SOCKET_Out"], "Bunkbed": [], "Generator": [], "VentFan": ["Fan"],
    "Pipe_Straight": [], "Pipe_Elbow": [], "Pipe_Valve": [], "CableBundle": [],
    "Crate_A": [], "Crate_B": [], "Barrel": [], "Chair": [], "Table": [], "Radio": [], "Clipboard": [],
    "Locker_Tall": [], "FuseBox": [], "Bucket": [], "BlastDoor": [], "PosterBoard": [],
}
LARGE = {"Workbench", "Terminal", "ToolRack", "SecurityGate_Frame", "SecurityGate_Bars", "ShelfUnit", "StorageLocker", "SellMachine",
         "Bunkbed", "Generator", "BlastDoor", "Table", "Locker_Tall"}


def budget_for(name):
    return (50, 5000) if name in LARGE else (50, 1500)


def E(root, notes="", view="iso", cell=0.5, figure=False, hero=False, shots=None, wall=False):
    return {"root": root, "notes": notes, "view": view, "cell": cell, "figure": figure, "hero": hero,
            "hero_shots": shots, "wall": wall}


# --------------------------------------------------------------------------------------------
# small builders
# --------------------------------------------------------------------------------------------
def bx(mb, mn, mx, mat, b=0.008, seg=1, m=None, **kw):
    mb.add(H.box_mm(mn, mx, b, seg), mat, m, **kw)


def rod(mb, a, b, r, mat, n=8, bevel=0.0, caps=True, flat=False):
    a, b = Vector(a), Vector(b)
    d = b - a
    mb.add(H.cyl(r, d.length, n, bevel=bevel, caps=caps, flat=flat), mat, H.place(a, d))


def bolts(mb, pts, normal, r=0.009, mat=BARE, washer=False):
    for p in pts:
        mb.add(H.bolt(r, r * 0.6, washer=washer), mat, H.place(p, normal))


def cable(mb, pts, r=0.008, n=6, mat=RUB):
    mb.add(H.sweep(pts, r, n), mat)


def flange_ring(mb, center, axis, r_in, r_out, thick, mat, nbolts=8, bolt_mat=BARE, n=16):
    prof = [(r_in, 0), (r_out - 0.004, 0), (r_out, 0.004), (r_out, thick - 0.004), (r_out - 0.004, thick), (r_in, thick)]
    mb.add(H.lathe(prof, n, cap_start=False, cap_end=False), mat, H.place(center, axis))
    ax = Vector(axis).normalized()
    t = ax.orthogonal().normalized()
    for k in range(nbolts):
        q = Matrix.Rotation(math.tau * k / nbolts, 4, ax) @ t
        mb.add(H.bolt(0.008, 0.006, washer=False), bolt_mat, H.place(Vector(center) + ax * thick + q * (r_in + r_out) / 2, ax))


def hazard_plate(mb, mn, mx, b=0.003):
    bx(mb, mn, mx, HAZ, b)


# ============================================================================================
# Workbench
# ============================================================================================
def tool_outline_shapes():
    hammer = [(-0.012, -0.16), (0.012, -0.16), (0.012, 0.06), (0.05, 0.06), (0.05, 0.1), (-0.06, 0.1), (-0.07, 0.085),
              (-0.012, 0.075)]
    wrench = [(-0.011, -0.13), (0.011, -0.13), (0.011, 0.09), (0.028, 0.1), (0.03, 0.14), (0.012, 0.15), (0.008, 0.125),
              (-0.008, 0.125), (-0.012, 0.15), (-0.03, 0.14), (-0.028, 0.1), (-0.011, 0.09)]
    saw = [(-0.14, -0.05), (0.14, -0.02), (0.14, 0.03), (0.2, 0.03), (0.22, 0.07), (0.2, 0.1), (0.1, 0.1), (0.08, 0.05),
           (-0.14, 0.03)]
    pliers = [(-0.02, -0.13), (-0.008, -0.13), (-0.004, 0.02), (0.004, 0.02), (0.008, -0.13), (0.02, -0.13), (0.012, 0.04),
              (0.006, 0.1), (-0.006, 0.1), (-0.012, 0.04)]
    screwdriver = [(-0.01, -0.12), (0.01, -0.12), (0.01, -0.02), (0.003, -0.01), (0.003, 0.1), (-0.003, 0.1),
                   (-0.003, -0.01), (-0.01, -0.02)]
    return [hammer, wrench, saw, pliers, screwdriver]


def build_workbench():
    mb = MB(T_MED)
    W, D, top = 2.2, 0.9, 0.95
    lx, ly = W / 2 - 0.06, D / 2 - 0.06
    # top: thick plank slab with steel nosing
    for k in range(6):
        y0 = -D / 2 + k * D / 6
        bx(mb, (-W / 2, y0 + 0.002, top - 0.06), (W / 2, y0 + D / 6 - 0.002, top), "MNF_WoodPlanks", 0.006)
    bx(mb, (-W / 2 - 0.005, -D / 2 - 0.006, top - 0.065), (W / 2 + 0.005, -D / 2 + 0.003, top + 0.003), BARE, 0.003)
    # legs, aprons, lower diamond-plate shelf, feet
    for sx in (-1, 1):
        for sy in (-1, 1):
            zt = top - 0.06 if sy < 0 else 2.15
            bx(mb, (sx * lx - 0.03, sy * ly - 0.03, 0.02), (sx * lx + 0.03, sy * ly + 0.03, zt), GRAY, 0.006)
            bx(mb, (sx * lx - 0.045, sy * ly - 0.045, 0), (sx * lx + 0.045, sy * ly + 0.045, 0.02), RUB, 0.004)
        # side apron + diagonal brace
        bx(mb, (sx * lx - 0.02, -ly, top - 0.12), (sx * lx + 0.02, ly, top - 0.06), GRAY, 0.004)
        rod(mb, (sx * lx, -ly + 0.03, 0.2), (sx * lx, ly - 0.03, top - 0.12), 0.015, GRAY, 6)
    for sy in (-1, 1):
        bx(mb, (-lx, sy * ly - 0.02, top - 0.12), (lx, sy * ly + 0.02, top - 0.06), GRAY, 0.004)
        bx(mb, (-lx, sy * ly - 0.02, 0.16), (lx, sy * ly + 0.02, 0.2), GRAY, 0.004)
    bx(mb, (-lx + 0.03, -ly + 0.02, 0.19), (lx - 0.03, ly - 0.02, 0.2), "MNF_MetalDiamond", 0.002)
    # drawer under the top
    bx(mb, (0.25, -ly - 0.03, top - 0.2), (0.85, ly - 0.1, top - 0.065), GRAY, 0.006)
    bx(mb, (0.5, -ly - 0.05, top - 0.15), (0.6, -ly - 0.03, top - 0.125), BARE, 0.004)
    # pegboard back panel (1.2 m) with frame, pegs and painted tool outlines
    py = D / 2 - 0.05
    bx(mb, (-lx + 0.03, py - 0.01, top), (lx - 0.03, py + 0.01, top + 1.2), GREEN, 0.004)
    bx(mb, (-lx, py - 0.02, top + 1.17), (lx, py + 0.03, top + 1.21), GRAY, 0.005)
    bx(mb, (-lx, py - 0.02, top + 0.01), (lx, py + 0.03, top + 0.05), GRAY, 0.005)
    shapes = tool_outline_shapes()
    rng = random.Random(3)
    slots = [(-0.85, 1.55, 0), (-0.55, 1.5, 1), (-0.15, 1.6, 2), (0.3, 1.5, 3), (0.55, 1.5, 4), (0.85, 1.55, 1),
             (-0.6, 1.2, 4), (0.05, 1.22, 0), (0.75, 1.2, 3)]
    hung = {1, 4, 7}
    for i, (x, z, si) in enumerate(slots):
        m = xf((x, py - 0.0105, z), (90, 0, 0)) @ xf(rot=(0, 0, rng.uniform(-6, 6)))
        mb.add(H.outline_strip(shapes[si], 0.006), YEL, m)
        rod(mb, (x, py - 0.01, z + 0.09), (x, py - 0.07, z + 0.1), 0.004, BARE, 5)
        if i in hung:
            # actual tool hanging on its outline
            if si == 0:
                mb.add(H.extrude_poly(shapes[si][:3] + [(-0.012, 0.075)], 0.02, bevel=0.003), "MNF_WoodHandle", m @ xf((0, 0, 0.002)))
                bx(mb, (-0.07, 0.06, 0.002), (0.05, 0.1, 0.03), BARE, 0.004, m=m)
            elif si == 1:
                mb.add(H.extrude_poly(shapes[1], 0.008, bevel=0.002), BARE, m @ xf((0, 0, 0.002)))
            else:
                mb.add(H.extrude_poly(shapes[si], 0.01, bevel=0.002), BARE, m @ xf((0, 0, 0.002)))
    # vice on the front-left corner
    vx, vy = -0.8, -ly + 0.02
    bx(mb, (vx - 0.09, vy - 0.06, top), (vx + 0.09, vy + 0.14, top + 0.05), RED, 0.008)
    bx(mb, (vx - 0.08, vy - 0.03, top + 0.05), (vx + 0.08, vy + 0.03, top + 0.13), RED, 0.008)
    bx(mb, (vx - 0.08, vy - 0.17, top + 0.05), (vx + 0.08, vy - 0.11, top + 0.13), RED, 0.008)
    for yy in (vy - 0.035, vy - 0.105):
        bx(mb, (vx - 0.08, yy - 0.006, top + 0.1), (vx + 0.08, yy + 0.006, top + 0.135), BARE, 0.002)
    rod(mb, (vx, vy - 0.11, top + 0.04), (vx, vy - 0.25, top + 0.04), 0.012, BARE, 8)
    rod(mb, (vx - 0.12, vy - 0.25, top + 0.04), (vx + 0.12, vy - 0.25, top + 0.04), 0.007, BARE, 6)
    for sx in (-1, 1):
        mb.add(H.uvsphere(0.013, 8, 5), BARE, xf((vx + sx * 0.125, vy - 0.25, top + 0.04)))
    bolts(mb, [(vx + sx * 0.06, vy + sy * 0.05 + 0.05, top + 0.05) for sx in (-1, 1) for sy in (-1, 1)], (0, 0, 1), 0.008)
    # scattered tools: hammer, wrench, screwdriver, can of bolts, rag, oil can
    rod(mb, (0.1, -0.15, top + 0.015), (0.4, -0.05, top + 0.015), 0.014, "MNF_WoodHandle", 8)
    bx(mb, (0.38, -0.12, top), (0.43, 0.04, top + 0.035), BARE, 0.006, m=xf((0.405, -0.04, 0), (0, 0, 18)) @ xf((-0.405, 0.04, 0)))
    mb.add(H.extrude_poly(shapes[1], 0.008, bevel=0.002), BARE, xf((-0.25, -0.2, top), (0, 0, 70)))
    rod(mb, (-0.45, 0.05, top + 0.014), (-0.33, 0.12, top + 0.014), 0.013, "MNF_Plastic_Yellow", 8)
    rod(mb, (-0.33, 0.12, top + 0.014), (-0.2, 0.195, top + 0.014), 0.0035, BARE, 5)
    can = H.lathe([(0.0, 0.0), (0.06, 0.0), (0.062, 0.01), (0.062, 0.12), (0.058, 0.124), (0.055, 0.118), (0.0, 0.118)], 12)
    mb.add(can, BARE, xf((0.7, 0.15, top)))
    for k in range(4):
        mb.add(H.bolt(0.01, 0.007, washer=False), RUST, xf((0.69 + 0.015 * k, 0.14 + 0.01 * (k % 2), top + 0.118), (rng.uniform(-30, 30), 20, 0)))
    rag = H.rock(0.12, 7, 2, (1.2, 0.8, 0.12), amp=0.4, freq=2.0)
    mb.add(rag, "MNF_FabricCanvas", xf((-0.1, 0.2, top + 0.012)), uv="box")
    oc = H.lathe([(0.0, 0.0), (0.05, 0.0), (0.05, 0.05), (0.03, 0.09), (0.008, 0.1), (0.006, 0.2), (0.0, 0.2)], 10)
    mb.add(oc, RED, xf((1.0, 0.1, top)) @ xf(rot=(0, 0, 0)))
    root = mb.to_object("Workbench")
    H.col_box("COL_Top", root, (-W / 2, -D / 2, 0), (W / 2, D / 2, top))
    H.col_box("COL_Pegboard", root, (-lx - 0.03, py - 0.02, top), (lx + 0.03, py + 0.03, top + 1.21))
    return E(root, "Heavy steel/wood workbench 2.2 x 0.9 m, top at 0.95 m, pegboard back panel 1.2 m high with painted "
                   "tool outlines (some empty), vice, drawer, scattered tools.", figure=True, hero=True,
             shots=[("iso", None), ("front", ((-1.1, -0.5, 0.9), (1.1, 0.5, 2.2)))])


# ============================================================================================
# Terminal
# ============================================================================================
def build_terminal():
    mb = MB(T_MED)
    W, D, Hd = 0.72, 0.6, 0.95
    # pedestal console with sloped keyboard shelf
    bx(mb, (-W / 2, -D / 2 + 0.05, 0.08), (W / 2, D / 2, Hd), GRAY, 0.012, 2)
    bx(mb, (-W / 2 + 0.03, -D / 2 + 0.08, 0.0), (W / 2 - 0.03, D / 2 - 0.03, 0.08), "MNF_Rubber", 0.006)
    shelf = H.extrude_poly([(-D / 2 - 0.08, Hd - 0.07), (-D / 2 + 0.06, Hd - 0.07), (-D / 2 + 0.06, Hd + 0.005),
                            (-D / 2 - 0.08, Hd - 0.035)], W + 0.02, bevel=0.006, z0=-(W + 0.02) / 2)
    mb.add(shelf, GRAY, xf((0, 0, 0), (90, 0, 90)))
    # side vents and access panel
    for sx in (-1, 1):
        for k in range(5):
            bx(mb, (sx * (W / 2) - 0.004, -0.15 + k * 0.05, 0.6), (sx * (W / 2) + 0.004, -0.13 + k * 0.05, 0.8), "MNF_Plastic_Black", 0.002)
    bx(mb, (-W / 2 + 0.06, -D / 2 + 0.045, 0.18), (W / 2 - 0.06, -D / 2 + 0.055, 0.75), GRAY, 0.004)
    bolts(mb, [(sx * (W / 2 - 0.08), -D / 2 + 0.045, z) for sx in (-1, 1) for z in (0.22, 0.71)], (0, -1, 0), 0.007)
    bx(mb, (-0.12, -D / 2 + 0.04, 0.62), (0.12, -D / 2 + 0.046, 0.7), "MNF_Paper", 0.002)
    # keyboard on the sloped shelf
    kb_m = xf((0, -D / 2 - 0.005, Hd - 0.03), (-14, 0, 0))
    bx(mb, (-0.23, -0.09, 0.0), (0.23, 0.09, 0.03), "MNF_Plastic_Gray", 0.008, m=kb_m)
    for r in range(4):
        n = 12 if r < 3 else 10
        for c in range(n):
            x = -0.2 + c * 0.034 + (0.017 if r == 3 else 0)
            y = 0.05 - r * 0.033
            bx(mb, (x - 0.013, y - 0.013, 0.03), (x + 0.013, y + 0.013, 0.042), "MNF_Plastic_Black", 0.0, m=kb_m)
    bx(mb, (-0.1, -0.078, 0.03), (0.1, -0.058, 0.04), "MNF_Plastic_Black", 0.0, m=kb_m)
    # steel monitor stand + CRT
    bx(mb, (-0.16, -0.12, Hd), (0.16, 0.18, Hd + 0.03), GRAY, 0.006)
    rod(mb, (0, 0.03, Hd + 0.03), (0, 0.03, Hd + 0.11), 0.04, BARE, 10)
    bx(mb, (-0.18, -0.12, Hd + 0.11), (0.18, 0.2, Hd + 0.13), GRAY, 0.006)
    mz = Hd + 0.13
    cy = -0.16
    bez = H.box(0.52, 0.09, 0.46, 0.02, 2)
    mb.add(bez, "MNF_Plastic_Gray", xf((0, cy + 0.045, mz + 0.23)))
    # tapered tube housing behind the bezel
    rings = []
    for t, (w, h, y) in enumerate(((0.48, 0.42, cy + 0.09), (0.44, 0.38, cy + 0.22), (0.3, 0.26, cy + 0.42), (0.26, 0.22, cy + 0.45))):
        rings.append([Vector((px, y, mz + 0.23 + py)) for px, py in H.rrect2d(w, h, 0.04, 1)])
    for r in rings:
        r.reverse()
    mb.add(H.skin([[Vector((p.x, p.y, p.z)) for p in r] for r in rings], cap_start=False), "MNF_Plastic_Gray")
    for k in range(6):
        bx(mb, (-0.11 + k * 0.045, cy + 0.36, mz + 0.355), (-0.09 + k * 0.045, cy + 0.42, mz + 0.36), "MNF_Plastic_Black", 0.0)
    # screen recess frame (dark) + knobs + power lamp
    for (a, b) in (((-0.235, cy - 0.003, mz + 0.05), (0.235, cy + 0.01, mz + 0.07)), ((-0.235, cy - 0.003, mz + 0.39), (0.235, cy + 0.01, mz + 0.41)),
                   ((-0.235, cy - 0.003, mz + 0.05), (-0.215, cy + 0.01, mz + 0.41)), ((0.215, cy - 0.003, mz + 0.05), (0.235, cy + 0.01, mz + 0.41))):
        bx(mb, a, b, "MNF_Plastic_Black", 0.003)
    for k, x in enumerate((0.12, 0.17)):
        mb.add(H.cyl(0.011, 0.012, 10, bevel=0.003), "MNF_Plastic_Black", H.place((x, cy, mz + 0.025), (0, -1, 0)))
    mb.add(H.uvsphere(0.006, 8, 5), "MNF_BulbGreen", xf((-0.2, cy - 0.001, mz + 0.025)))
    # cables: monitor -> console -> floor
    cable(mb, [(0.05, cy + 0.44, mz + 0.12), (0.06, 0.3, mz + 0.02), (0.08, 0.33, Hd - 0.1), (0.1, 0.33, 0.3), (0.2, 0.4, 0.02), (0.35, 0.55, 0.01)], 0.008)
    cable(mb, [(-0.05, cy + 0.44, mz + 0.1), (-0.07, 0.31, mz - 0.02), (-0.1, 0.32, 0.5), (-0.15, 0.38, 0.02), (-0.3, 0.5, 0.012)], 0.006)
    cable(mb, [(-0.2, -D / 2 - 0.02, Hd - 0.02), (-0.24, -D / 2 - 0.01, Hd - 0.12), (-0.28, -D / 2 + 0.04, Hd - 0.08), (-0.3, -0.24, Hd - 0.001)], 0.004)
    root = mb.to_object("Terminal")
    sp = Vector((0, cy - 0.001, mz + 0.23))
    sb = MB(T_SMALL)
    sb.add(H.quad(0.42, 0.32, "-Y"), "MNF_Screen", xf(sp))
    sb.to_object("Screen", root, pivot=sp, weighted=False)
    H.col_box("COL_Console", root, (-W / 2, -D / 2 - 0.08, 0), (W / 2, D / 2, Hd))
    H.col_box("COL_Monitor", root, (-0.26, cy, Hd), (0.26, cy + 0.45, mz + 0.46))
    return E(root, "Floor console terminal: steel pedestal with sloped keyboard shelf, CRT (0.52 m bezel) on a steel stand, "
                   "cables. Child `Screen` = 0.42 x 0.32 m quad facing -Y, pivot at its centre (%.2f m high), UV 0..1." % sp.z,
             figure=True, hero=True, shots=[("iso", None), ("front", ((-0.3, -0.4, 0.85), (0.3, 0.2, 1.62)))])


# ============================================================================================
# Buttons & lever (moving parts separate)
# ============================================================================================
def build_terminal_button():
    mb = MB(T_SMALL)
    o, i, d = 0.07, 0.052, 0.016
    ring = [Vector((x, 0, z)) for x, z in H.rrect2d(o, o, 0.006, 1)]
    inner = [Vector((x, 0, z)) for x, z in H.rrect2d(i, i, 0.004, 1)]
    # bezel: back plate + raised chamfered frame
    bx(mb, (-o / 2, -0.004, -o / 2), (o / 2, 0.0, o / 2), "MNF_Plastic_Black", 0.002)
    rings = [[p + Vector((0, -0.004, 0)) for p in ring], [p * 1.0 + Vector((0, -d + 0.003, 0)) for p in ring],
             [Vector((p.x * 0.96, -d, p.z * 0.96)) for p in ring], [Vector((p.x, -d, p.z)) for p in inner],
             [Vector((p.x, -0.006, p.z)) for p in inner]]
    mb.add(H.skin(rings, cap_start=False, cap_end=True), "MNF_Plastic_Black", flat=False)
    for sx in (-1, 1):
        for sz in (-1, 1):
            mb.add(H.cyl(0.0025, 0.001, 6, flat=True), BARE, H.place((sx * 0.029, -d, sz * 0.029), (0, -1, 0)))
    body = mb.to_object("TerminalButton_Body", smooth_angle=35)
    H.empty("SOCKET_Cap", body, (0, -0.006, 0))
    cb = MB(T_SMALL)
    cap = H.box(0.046, 0.022, 0.046, 0.005, 2)
    for v in cap.verts:
        if v.co.y < -0.005:
            v.co.y -= 0.002 * (1 - (v.co.x / 0.023) ** 2) * (1 - (v.co.z / 0.023) ** 2)
    cap.normal_update()
    cb.add(cap, "MNF_Plastic_Yellow", xf((0, -0.011, 0)))
    capo = cb.to_object("TerminalButton_Cap", smooth_angle=35)
    return [E(body, "7 cm square console push-button bezel, console-mounted (pivot at the console surface, -Y out). "
                    "SOCKET_Cap marks the cap's rest pivot (y=-0.006).", view="front", cell=0.02,
              shots=[("iso", None)], hero=False),
            E(capo, "Button cap 46 mm, pivot at its base; presses along +Y (~8 mm travel) into the body. Place at "
                    "TerminalButton_Body/SOCKET_Cap.", view="iso", cell=0.02)]


def build_big_button():
    mb = MB(T_SMALL)
    w, d, h = 0.15, 0.09, 0.17
    bx(mb, (-w / 2, -d, -h / 2), (w / 2, 0, h / 2), "MNF_Plastic_Yellow", 0.012, 2)
    bx(mb, (-w / 2 - 0.01, -0.006, -h / 2 - 0.01), (w / 2 + 0.01, 0, h / 2 + 0.01), GRAY, 0.003)
    # hazard frame on the front face
    for (a, b) in (((-w / 2 + 0.008, -d - 0.002, h / 2 - 0.024), (w / 2 - 0.008, -d + 0.001, h / 2 - 0.008)),
                   ((-w / 2 + 0.008, -d - 0.002, -h / 2 + 0.008), (w / 2 - 0.008, -d + 0.001, -h / 2 + 0.024))):
        hazard_plate(mb, a, b, 0.002)
    guard = H.lathe([(0.03, 0.0), (0.05, 0.0), (0.052, 0.004), (0.048, 0.022), (0.042, 0.026), (0.03, 0.026)], 16,
                    cap_start=False, cap_end=False)
    mb.add(guard, "MNF_Plastic_Black", H.place((0, -d, 0), (0, -1, 0)))
    mb.add(H.cyl(0.03, 0.004, 16), "MNF_Plastic_Black", H.place((0, -d, 0), (0, -1, 0)))
    bx(mb, (-0.04, -d - 0.001, -0.075), (0.04, -d + 0.002, -0.06), "MNF_Paper", 0.001)
    rod(mb, (0, -d / 2, h / 2), (0, -d / 2, h / 2 + 0.25), 0.012, BARE, 8)
    bx(mb, (-0.018, -d / 2 - 0.018, h / 2), (0.018, -d / 2 + 0.018, h / 2 + 0.02), BARE, 0.004)
    bolts(mb, [(sx * (w / 2 + 0.003), -0.006, sz * (h / 2 + 0.003)) for sx in (-1, 1) for sz in (-1, 1)], (0, -1, 0), 0.006)
    body = mb.to_object("BigButton_Body", smooth_angle=35)
    H.empty("SOCKET_Cap", body, (0, -d - 0.004, 0))
    cb = MB(T_SMALL)
    cb.add(H.lathe([(0.0, 0.0), (0.014, 0.0), (0.014, 0.018), (0.034, 0.02), (0.037, 0.026), (0.035, 0.034), (0.024, 0.044),
                    (0.0, 0.048)], 16), RED, H.place((0, 0, 0), (0, -1, 0)))
    capo = cb.to_object("BigButton_Cap", smooth_angle=50)
    return [E(body, "Emergency mushroom button housing (yellow, hazard frame, black guard) with conduit; wall-mounted pivot "
                    "(-Y out). SOCKET_Cap marks where the cap pivot sits.", view="iso", cell=0.05, wall=True),
            E(capo, "Red mushroom cap (MNF_MetalPainted_Red - no red plastic in the catalog), pivot at its base, presses "
                    "along +Y. Place at BigButton_Body/SOCKET_Cap.", view="iso", cell=0.02)]


def build_lever():
    mb = MB(T_SMALL)
    w, d, h = 0.17, 0.12, 0.32
    bx(mb, (-w / 2 - 0.02, -0.008, -h / 2 - 0.02), (w / 2 + 0.02, 0, h / 2 + 0.02), GRAY, 0.004)
    bolts(mb, [(sx * (w / 2 + 0.008), -0.008, sz * (h / 2 + 0.008)) for sx in (-1, 1) for sz in (-1, 1)], (0, -1, 0), 0.007)
    # box with a vertical slot in its front (two half boxes + side cheeks)
    bx(mb, (-w / 2, -d, -h / 2), (-0.012, -0.008, h / 2), GRAY, 0.01, 2)
    bx(mb, (0.012, -d, -h / 2), (w / 2, -0.008, h / 2), GRAY, 0.01, 2)
    bx(mb, (-0.012, -d + 0.02, -h / 2), (0.012, -0.008, h / 2), GRAY, 0.004)
    bx(mb, (-0.012, -d, h / 2 - 0.05), (0.012, -0.008, h / 2), GRAY, 0.004)
    bx(mb, (-0.012, -d, -h / 2), (0.012, -0.008, -h / 2 + 0.05), GRAY, 0.004)
    # hazard quadrant plates beside the slot + ON/OFF labels
    for x0, x1 in ((-0.07, -0.02), (0.02, 0.07)):
        hazard_plate(mb, (x0, -d - 0.002, -0.1), (x1, -d + 0.001, 0.1), 0.002)
    for z in (0.125, -0.125):
        bx(mb, (-0.04, -d - 0.002, z - 0.012), (0.04, -d + 0.001, z + 0.012), "MNF_Paper", 0.001)
    rod(mb, (-w / 2 - 0.004, -0.07, 0), (w / 2 + 0.004, -0.07, 0), 0.012, BARE, 10)
    rod(mb, (0, -d / 2, h / 2), (0, -d / 2, h / 2 + 0.2), 0.014, BARE, 8)
    base = mb.to_object("Lever_Base", smooth_angle=35)
    H.empty("SOCKET_Handle", base, (0, -0.07, 0))
    hb = MB(T_SMALL)
    hb.add(H.cyl(0.024, 0.02, 12, bevel=0.003), BARE, H.place((-0.01, 0, 0), (1, 0, 0)))
    bx(hb, (-0.009, -0.34, -0.014), (0.009, 0.0, 0.014), RED, 0.004)
    rod(hb, (-0.07, -0.34, 0), (0.07, -0.34, 0), 0.018, RUB, 10, bevel=0.005)
    bx(hb, (-0.014, -0.36, -0.02), (0.014, -0.32, 0.02), RED, 0.005)
    handle = hb.to_object("Lever_Handle", smooth_angle=35)
    return [E(base, "Industrial wall lever box (pivot at wall contact, -Y out) with slot, hazard quadrant, ON/OFF plates. "
                    "SOCKET_Handle = hinge position for Lever_Handle.", view="iso", cell=0.05, wall=True),
            E(handle, "Lever handle, pivot at the hinge axle; authored at neutral pointing -Y out of the wall, rotate about "
                      "X +-45 deg. T-grip (rubber) at 0.34 m.", view="iso", cell=0.05)]


# ============================================================================================
# Security gate
# ============================================================================================
def build_gate_frame():
    mb = MB(T_BIG)
    W2, Hh = 1.5, 2.8
    jw, jd = 0.3, 0.4
    for sx in (-1, 1):
        x0, x1 = sx * W2, sx * (W2 + jw)
        lo, hi = min(x0, x1), max(x0, x1)
        bx(mb, (lo, -jd / 2, 0), (hi, jd / 2, Hh + 0.5), GRAY, 0.015, 2)
        # hazard-striped jamb faces (front + inner)
        hazard_plate(mb, (lo + 0.03, -jd / 2 - 0.006, 0.05), (hi - 0.03, -jd / 2 + 0.001, Hh - 0.05), 0.003)
        hazard_plate(mb, (lo + 0.03, jd / 2 - 0.001, 0.05), (hi - 0.03, jd / 2 + 0.006, Hh - 0.05), 0.003)
        # guide channel lips on the inner face
        for sy in (-1, 1):
            bx(mb, (x0 - sx * 0.06 if sx > 0 else x0, sy * 0.06 - 0.015, 0), (x0 if sx > 0 else x0 + 0.06, sy * 0.06 + 0.015, Hh), BARE, 0.004)
        # base plate + anchor bolts
        bx(mb, (lo - 0.06, -jd / 2 - 0.08, 0), (hi + 0.06, jd / 2 + 0.08, 0.025), GRAY, 0.006)
        bolts(mb, [(lo - 0.03, sy * (jd / 2 + 0.05), 0.025) for sy in (-1, 1)] + [(hi + 0.03, sy * (jd / 2 + 0.05), 0.025) for sy in (-1, 1)],
              (0, 0, 1), 0.014, washer=True)
        # rivet rows on the jamb front edges
        for z in (0.3, 0.9, 1.5, 2.1, 2.7):
            for xx in (lo + 0.015, hi - 0.015):
                mb.add(H.rivet(0.009, 0.005), BARE, H.place((xx, -jd / 2, z), (0, -1, 0)))
    # header beam with slot, hazard band along its lower front edge
    bx(mb, (-W2 - jw, -0.25, Hh), (W2 + jw, -0.05, Hh + 0.55), GRAY, 0.015, 2)
    bx(mb, (-W2 - jw, 0.05, Hh), (W2 + jw, 0.25, Hh + 0.55), GRAY, 0.015, 2)
    bx(mb, (-W2 - jw, -0.25, Hh + 0.5), (W2 + jw, 0.25, Hh + 0.6), GRAY, 0.012)
    hazard_plate(mb, (-W2, -0.256, Hh + 0.02), (W2, -0.249, Hh + 0.16), 0.002)
    for k in range(9):
        x = -1.6 + k * 0.4
        for z in (Hh + 0.25, Hh + 0.45):
            mb.add(H.rivet(0.01, 0.005), BARE, H.place((x, -0.25, z), (0, -1, 0)))
    # motor housing, motor, gearbox, cable conduit
    mx0 = 0.6
    bx(mb, (mx0, -0.22, Hh + 0.6), (mx0 + 0.9, 0.22, Hh + 1.05), YEL, 0.02, 2)
    hazard_plate(mb, (mx0 + 0.02, -0.226, Hh + 0.62), (mx0 + 0.88, -0.219, Hh + 0.7), 0.002)
    for k in range(6):
        bx(mb, (mx0 + 0.1 + k * 0.05, -0.227, Hh + 0.78), (mx0 + 0.13 + k * 0.05, -0.219, Hh + 0.98), "MNF_Plastic_Black", 0.0)
    mb.add(H.cyl(0.13, 0.38, 14, bevel=0.015), GREEN, H.place((mx0 - 0.4, 0.0, Hh + 0.75), (1, 0, 0)))
    for k in range(5):
        mb.add(H.cyl(0.137, 0.012, 14), GREEN, H.place((mx0 - 0.37 + k * 0.07, 0.0, Hh + 0.75), (1, 0, 0)))
    bx(mb, (mx0 - 0.05, -0.12, Hh + 0.6), (mx0, 0.12, Hh + 0.9), GRAY, 0.008)
    bx(mb, (mx0 - 0.42, -0.14, Hh + 0.6), (mx0 - 0.37, 0.14, Hh + 0.65), GRAY, 0.005)
    rod(mb, (mx0 + 0.75, 0.1, Hh + 1.05), (mx0 + 0.75, 0.1, Hh + 1.5), 0.025, BARE, 8)
    cable(mb, [(mx0 - 0.4, 0.05, Hh + 0.88), (mx0 - 0.55, 0.08, Hh + 0.95), (mx0 - 0.7, 0.15, Hh + 1.2), (mx0 - 0.72, 0.2, Hh + 1.5)], 0.015)
    root = mb.to_object("SecurityGate_Frame", smooth_angle=35)
    for sx, nm in ((-1, "COL_JambL"), (1, "COL_JambR")):
        x0, x1 = sx * W2, sx * (W2 + jw)
        H.col_box(nm, root, (min(x0, x1), -jd / 2, 0), (max(x0, x1), jd / 2, Hh + 0.5))
    H.col_box("COL_Header", root, (-W2 - jw, -0.25, Hh), (W2 + jw, 0.25, Hh + 0.6))
    H.empty("SOCKET_Bars", root, (0, 0, 0))
    return E(root, "Heavy steel gate frame for a 3.0 x 2.8 m opening: hazard-striped jambs with guide channels, slotted "
                   "header, motor housing on top. Pivot at the floor centre of the opening. SOCKET_Bars = closed position "
                   "of SecurityGate_Bars (slides +Z up through the header slot; ceiling space needed above).",
             figure=True, hero=True, shots=[("iso", None)])


def build_gate_bars():
    mb = MB(T_BIG)
    W2, Hh = 1.5, 2.8
    # side stiles (run in the frame channels)
    for sx in (-1, 1):
        bx(mb, (sx * W2 - 0.04 - (0 if sx < 0 else 0.0), -0.04, 0.0), (sx * W2 + 0.04, 0.04, Hh), GRAY, 0.008)
    # bottom rail (heavy, hazard front), braces, top rail
    bx(mb, (-W2, -0.05, 0.0), (W2, 0.05, 0.14), GRAY, 0.012)
    hazard_plate(mb, (-W2 + 0.05, -0.056, 0.015), (W2 - 0.05, -0.049, 0.125), 0.002)
    bx(mb, (-W2, -0.04, Hh - 0.1), (W2, 0.04, Hh), GRAY, 0.01)
    for z in (0.95, 1.85):
        bx(mb, (-W2, -0.045, z - 0.05), (W2, -0.02, z + 0.05), GRAY, 0.006)
        bx(mb, (-W2, 0.02, z - 0.05), (W2, 0.045, z + 0.05), GRAY, 0.006)
    # thick vertical bars
    n = 15
    for k in range(n):
        x = -W2 + 0.12 + k * (2 * W2 - 0.24) / (n - 1)
        mb.add(H.cyl(0.025, Hh - 0.22, 8, caps=False), GRAY, xf((x, 0, 0.13)))
        for z in (0.95, 1.85):
            for sy in (-1, 1):
                mb.add(H.cyl(0.007, 0.004, 6, flat=True), BARE, H.place((x, sy * 0.045, z), (0, sy, 0)))
    root = mb.to_object("SecurityGate_Bars", smooth_angle=40)
    H.col_box("COL_Bars", root, (-W2 - 0.04, -0.05, 0), (W2 + 0.04, 0.05, Hh))
    return E(root, "Moving barred gate 3.0 x 2.8 m: 15 thick bars, paired braces, heavy hazard-striped bottom rail. "
                   "Pivot at the bottom centre; slides upward (+Z). COL_Bars box.", figure=True)


# ============================================================================================
# Lights
# ============================================================================================
def build_warning_beacon():
    mb = MB(T_SMALL)
    bx(mb, (-0.07, -0.01, -0.09), (0.07, 0.0, 0.07), GRAY, 0.004)
    bolts(mb, [(sx * 0.05, -0.01, sz) for sx in (-1, 1) for sz in (-0.07, 0.05)], (0, -1, 0), 0.006)
    # L bracket out of the wall, platform
    bx(mb, (-0.025, -0.16, -0.03), (0.025, -0.01, 0.0), GRAY, 0.004)
    bx(mb, (-0.02, -0.13, -0.08), (0.02, -0.11, -0.03), GRAY, 0.003)
    mb.add(H.extrude_poly([(0, 0), (0.12, 0), (0, -0.1)], 0.008, bevel=0.0015, z0=-0.004), GRAY, xf((0, -0.01, 0.0), (90, 0, -90)))
    bc = Vector((0, -0.16, 0.0))
    mb.add(H.lathe([(0.0, 0.0), (0.075, 0.0), (0.078, 0.006), (0.075, 0.05), (0.068, 0.055), (0.0, 0.055)], 16), "MNF_Plastic_Black", xf(bc))
    # wire cage round the dome
    for k in range(4):
        arc = [Vector((0.078 * math.cos(math.pi * i / 10), 0, 0.055 + 0.13 * math.sin(math.pi * i / 10))) for i in range(11)]
        mb.add(H.sweep(arc, 0.0035, 5), BARE, xf(bc, (0, 0, 45 * k)))
    for z, r in ((0.1, 0.077), (0.15, 0.062)):
        mb.add(H.torus(r, 0.0035, 16, 4), BARE, xf(bc + Vector((0, 0, z))))
    cable(mb, [(0.04, -0.15, 0.01), (0.05, -0.1, -0.02), (0.045, -0.03, -0.04), (0.04, -0.005, -0.05)], 0.006)
    root = mb.to_object("WarningBeacon", smooth_angle=40)
    lb = MB(T_SMALL)
    lp = bc + Vector((0, 0, 0.055))
    lb.add(H.lathe([(0.0, 0.0), (0.06, 0.0), (0.06, 0.06), (0.052, 0.095), (0.032, 0.115), (0.0, 0.122)], 16), "MNF_BulbRed", xf(lp))
    lb.add(H.box(0.05, 0.004, 0.07), BARE, xf(lp + Vector((0, 0.0, 0.045))))
    lb.to_object("Lamp", root, pivot=lp)
    return E(root, "Rotating amber/red beacon on a wall bracket with wire cage. Child `Lamp` (MNF_BulbRed dome + reflector "
                   "vane) pivots at the dome base for rotation about Z. Wall pivot, -Y out.", view="iso", cell=0.1, wall=True)


def build_fluorescent():
    mb = MB(T_MED)
    L = 1.25
    for sx in (-1, 1):
        x = sx * 0.45
        mb.add(H.cyl(0.04, 0.012, 10, bevel=0.003), GRAY, xf((x, 0, -0.012)))
        # chain links
        for k in range(6):
            mb.add(H.torus(0.011, 0.0025, 8, 4), BARE, xf((x, 0, -0.025 - k * 0.022), (0, 90 if k % 2 else 0, 90)))
    hz = -0.16
    # sheet metal housing: channel with folded lips
    bx(mb, (-L / 2, -0.09, hz - 0.012), (L / 2, 0.09, hz), GRAY, 0.004)
    for sy in (-1, 1):
        mb.add(H.extrude_poly([(-0.09 * sy, hz), (-0.09 * sy, hz - 0.06), (-0.075 * sy, hz - 0.065), (-0.07 * sy, hz - 0.058),
                               (-0.08 * sy, hz - 0.012)], L, bevel=0.0), GRAY,
               xf((-L / 2, 0, 0)) @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))))  # profile in YZ, extruded along X
    for sx in (-1, 1):
        bx(mb, (sx * L / 2 - 0.012, -0.09, hz - 0.065), (sx * L / 2 + 0.002 * sx, 0.09, hz), GRAY, 0.003)
        for sy in (-1, 1):
            bx(mb, (sx * (L / 2 - 0.035) - 0.012, sy * 0.035 - 0.012, hz - 0.05), (sx * (L / 2 - 0.035) + 0.012, sy * 0.035 + 0.012, hz - 0.012),
               "MNF_Plastic_Gray", 0.003)
    bx(mb, (-L / 2 + 0.03, -0.06, hz - 0.016), (L / 2 - 0.03, 0.06, hz - 0.012), BARE, 0.0)
    # wire guard rods under the tubes
    for sy in (-0.05, 0.0, 0.05):
        rod(mb, (-L / 2 + 0.01, sy, hz - 0.068), (L / 2 - 0.01, sy, hz - 0.068), 0.0025, BARE, 4)
    cable(mb, [(0.45, 0.03, -0.012), (0.42, 0.04, -0.06), (0.4, 0.04, hz + 0.002)], 0.005)
    root = mb.to_object("FluorescentFixture", smooth_angle=35)
    tb = MB(T_SMALL)
    tp = Vector((0, 0, hz - 0.035))
    for sy in (-1, 1):
        tb.add(H.cyl(0.013, L - 0.09, 10), "MNF_BulbCold", H.place((-(L - 0.09) / 2, sy * 0.035, hz - 0.035), (1, 0, 0)))
    tb.to_object("Tube", root, pivot=tp)
    return E(root, "1.25 m twin-tube fluorescent fixture hanging on short chains; ceiling mount, pivot at the top contact. "
                   "Child `Tube` (both MNF_BulbCold tubes) pivoted at the tube centre.", view="under", cell=0.1)


def build_cage_lamp():
    mb = MB(T_SMALL)
    mb.add(H.lathe([(0.0, 0.0), (0.075, 0.0), (0.078, 0.008), (0.07, 0.03), (0.05, 0.04), (0.0, 0.04)], 14), GRAY, H.place((0, 0, 0), (0, -1, 0)))
    bolts(mb, [(0.06 * math.cos(a), -0.008, 0.06 * math.sin(a)) for a in (0.8, 2.4, 3.9, 5.5)], (0, -1, 0), 0.005)
    mb.add(H.cyl(0.03, 0.03, 12, bevel=0.004), "MNF_Plastic_Black", H.place((0, -0.04, 0), (0, -1, 0)))
    bc = Vector((0, -0.12, 0))
    # cage: ring at the base, 5 ribs, cap
    mb.add(H.torus(0.055, 0.004, 16, 4), YEL, H.place((0, -0.065, 0), (0, -1, 0)))
    for k in range(5):
        a = math.tau * k / 5
        arc = []
        for i in range(9):
            t = i / 8
            r = 0.055 * math.sin(math.pi * (0.5 + 0.5 * t)) + 0.012
            arc.append(Vector((r * math.cos(a), -0.065 - 0.11 * t, r * math.sin(a))))
        mb.add(H.sweep(arc, 0.0035, 4), YEL)
    mb.add(H.cyl(0.018, 0.008, 10), YEL, H.place((0, -0.172, 0), (0, -1, 0)))
    mb.add(H.lathe([(0.0, -0.002), (0.046, 0.0), (0.05, 0.02), (0.04, 0.08), (0.02, 0.095), (0.0, 0.098)], 12), "MNF_Glass",
           H.place((0, -0.06, 0), (0, -1, 0)))
    rod(mb, (0, -0.02, 0.07), (0, -0.02, 0.4), 0.012, BARE, 8)
    root = mb.to_object("CageLamp", smooth_angle=40)
    bb = MB(T_SMALL)
    bb.add(H.lathe([(0.012, 0.0), (0.014, 0.012), (0.03, 0.03), (0.032, 0.045), (0.022, 0.065), (0.0, 0.07)], 12, cap_start=True), "MNF_BulbWarm",
           H.place((0, -0.07, 0), (0, -1, 0)))
    bb.to_object("Bulb", root, pivot=bc)
    return E(root, "Wall-mounted bulkhead cage lamp (yellow cage, glass globe, conduit up). Child `Bulb` (MNF_BulbWarm) "
                   "pivoted at the bulb centre. Wall pivot, -Y out.", view="iso", cell=0.1, wall=True)


def build_emergency_light():
    mb = MB(T_SMALL)
    w, d, h = 0.32, 0.09, 0.13
    bx(mb, (-w / 2, -d, -h / 2), (w / 2, 0, h / 2), "MNF_Plastic_Gray", 0.012, 2)
    bx(mb, (-w / 2 - 0.01, -0.005, -h / 2 - 0.01), (w / 2 + 0.01, 0, h / 2 + 0.01), GRAY, 0.003)
    for k in range(7):
        bx(mb, (-0.13 + k * 0.012, -d - 0.002, 0.02), (-0.125 + k * 0.012, -d + 0.001, 0.05), "MNF_Plastic_Black", 0.0)
    mb.add(H.cyl(0.008, 0.006, 8, bevel=0.002), RUB, H.place((0.12, -d, 0.035), (0, -1, 0)))
    mb.add(H.uvsphere(0.004, 6, 4), "MNF_BulbGreen", xf((0.095, -d - 0.001, 0.035)))
    bx(mb, (-0.05, -d - 0.002, 0.025), (0.05, -d + 0.001, 0.05), "MNF_Paper", 0.001)
    rod(mb, (0.12, -0.045, h / 2), (0.12, -0.045, h / 2 + 0.25), 0.012, BARE, 8)
    root = mb.to_object("EmergencyLight", smooth_angle=35)
    bb = MB(T_SMALL)
    lens = H.lathe([(0.0, -0.13), (0.04, -0.13), (0.045, -0.12), (0.045, 0.12), (0.04, 0.13), (0.0, 0.13)], 12)
    for v in lens.verts:
        if v.co.y > 0:
            v.co.y *= 0.2
    lens.normal_update()
    bp = Vector((0, -d, -0.022))
    bb.add(lens, "MNF_BulbRed", xf(bp, (0, 90, 0)) @ xf(scale=(1, 1.0, 1)))
    bb.to_object("Bulb", root, pivot=bp)
    return E(root, "Red emergency light box with a long red lens (child `Bulb`, MNF_BulbRed), test button, conduit. "
                   "Wall pivot, -Y out.", view="iso", cell=0.1, wall=True)


# ============================================================================================
# Racks, shelves, lockers
# ============================================================================================
def build_tool_rack():
    mb = MB(T_MED)
    W = 2.0
    for sz in (-1, 1):
        bx(mb, (-W / 2 - 0.02, -0.03, sz * 0.13 - 0.025), (W / 2 + 0.02, 0.0, sz * 0.13 + 0.025), GRAY, 0.005)
        bolts(mb, [(x, -0.03, sz * 0.13) for x in (-0.95, -0.3, 0.3, 0.95)], (0, -1, 0), 0.008)
    for k in range(4):
        z0 = -0.19 + k * 0.095
        bx(mb, (-W / 2, -0.055, z0 + 0.002), (W / 2, -0.03, z0 + 0.093), "MNF_WoodPlanks", 0.004)
    hazard_plate(mb, (-W / 2, -0.06, 0.17), (W / 2, -0.052, 0.19), 0.002)
    sockets = []
    for i in range(6):
        x = -0.85 + i * 0.34
        bx(mb, (x - 0.05, -0.065, -0.06), (x + 0.05, -0.055, 0.06), GRAY, 0.003)
        bolts(mb, [(x + sx * 0.035 * sz, -0.065, sz * 0.045) for sz in (-1, 1) for sx in (1,)], (0, -1, 0), 0.005)
        # forked cradle: two prongs angled up
        for sx in (-1, 1):
            pts = [(x + sx * 0.028, -0.065, 0.0), (x + sx * 0.028, -0.13, 0.005), (x + sx * 0.03, -0.17, 0.035), (x + sx * 0.03, -0.175, 0.06)]
            mb.add(H.sweep(pts, 0.008, 6), BARE)
            mb.add(H.uvsphere(0.011, 6, 4), RUB, xf(pts[-1]))
        bx(mb, (x - 0.05, -0.061, -0.165), (x + 0.05, -0.0555, -0.135), "MNF_Paper", 0.001)
        sockets.append(Vector((x, -0.15, 0.03)))
    root = mb.to_object("ToolRack", smooth_angle=35)
    for i, p in enumerate(sockets):
        H.empty("SOCKET_%d" % i, root, p)
    return E(root, "2.0 m wall tool rack: planked board on steel rails, 6 forked hook brackets with label plates. "
                   "SOCKET_0..5 at the cradle centres (tools rest across the forks). Wall pivot, -Y out.",
             view="iso", cell=0.1, wall=True)


def _jar(mb, p, r, h, rng):
    mb.add(H.lathe([(0.0, 0.0), (r, 0.0), (r * 1.02, h * 0.1), (r, h * 0.85), (r * 0.8, h * 0.92), (r * 0.8, h)], 10, cap_end=False), "MNF_Glass", xf(p))
    mb.add(H.cyl(r * 0.85, h * 0.12, 10, bevel=0.002), BARE, xf(Vector(p) + Vector((0, 0, h * 0.94))))
    mb.add(H.cyl(r * 0.9, h * rng.uniform(0.3, 0.6), 8), "MNF_Paper", xf(Vector(p) + Vector((0, 0, 0.005))))


def _can(mb, p, r=0.04, h=0.11):
    mb.add(H.lathe([(0.0, 0.0), (r, 0.0), (r, h), (0.0, h)], 10), BARE, xf(p))
    mb.add(H.lathe([(r * 1.01, h * 0.15), (r * 1.01, h * 0.85)], 10, cap_start=False, cap_end=False), "MNF_Paper", xf(p))


def build_shelf_unit():
    mb = MB(T_MED)
    rng = random.Random(14)
    W, D, Hh = 1.0, 0.45, 2.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            L = [(0, 0), (0.04, 0), (0.04, 0.004), (0.004, 0.004), (0.004, 0.04), (0, 0.04)]
            mb.add(H.extrude_poly(L, Hh), GRAY, xf((sx * W / 2, sy * D / 2, 0)) @ xf(scale=(-sx, -sy, 1)) if sx * sy > 0 else
                   xf((sx * W / 2, sy * D / 2, 0)) @ xf(rot=(0, 0, 90 if sx < 0 else -90)))
            bx(mb, (sx * W / 2 - 0.03, sy * D / 2 - 0.03, 0.0), (sx * W / 2 + 0.03, sy * D / 2 + 0.03, 0.006), GRAY, 0.002)
    shelves = [0.08, 0.5, 0.92, 1.34, 1.76, 1.98]
    for z in shelves:
        bx(mb, (-W / 2 + 0.002, -D / 2 + 0.002, z - 0.012), (W / 2 - 0.002, D / 2 - 0.002, z), GRAY, 0.003)
        bx(mb, (-W / 2 + 0.002, -D / 2 - 0.004, z - 0.035), (W / 2 - 0.002, -D / 2 + 0.008, z), GRAY, 0.003)
        bolts(mb, [(sx * (W / 2 - 0.01), -D / 2 - 0.004, z - 0.018) for sx in (-1, 1)], (0, -1, 0), 0.006)
    # back X bracing
    for (a, b) in (((-W / 2, D / 2, 0.1), (W / 2, D / 2, 1.0)), ((W / 2, D / 2, 0.1), (-W / 2, D / 2, 1.0)),
                   ((-W / 2, D / 2, 1.0), (W / 2, D / 2, 1.95)), ((W / 2, D / 2, 1.0), (-W / 2, D / 2, 1.95))):
        rod(mb, a, b, 0.006, GRAY, 4)
    # contents
    z = 0.08
    bx(mb, (-0.45, -0.18, z), (-0.05, 0.18, z + 0.3), "MNF_WoodCrate", 0.01)
    bx(mb, (0.0, -0.16, z), (0.42, 0.14, z + 0.22), RED, 0.01)
    bx(mb, (0.0, -0.165, z + 0.22), (0.42, 0.145, z + 0.25), RED, 0.008)
    rod(mb, (0.08, -0.01, z + 0.27), (0.34, -0.01, z + 0.27), 0.008, BARE, 6)
    z = 0.5
    for k in range(5):
        _can(mb, (-0.4 + k * 0.09, -0.1 + (k % 2) * 0.04, z))
    _can(mb, (-0.36, -0.05, z + 0.11))
    mb.add(H.torus(0.12, 0.03, 14, 6, scale=(1.0, 1.0)), RUB, xf((0.25, 0.0, z + 0.03)))
    mb.add(H.torus(0.09, 0.022, 12, 5), RUB, xf((0.25, 0.0, z + 0.08)))
    z = 0.92
    for k in range(4):
        _jar(mb, (-0.38 + k * 0.1, -0.08, z), 0.04, 0.14 + 0.02 * (k % 2), rng)
    bx(mb, (0.05, -0.17, z), (0.43, 0.17, z + 0.2), "MNF_Paper", 0.006)
    bx(mb, (0.08, -0.15, z + 0.2), (0.4, 0.16, z + 0.36), "MNF_Paper", 0.006, m=xf((0.24, 0, 0), (0, 0, 6)) @ xf((-0.24, 0, 0)))
    z = 1.34
    mb.add(H.torus(0.13, 0.035, 14, 6), "MNF_Rope", xf((-0.25, 0.0, z + 0.035)))
    mb.add(H.torus(0.1, 0.03, 12, 5), "MNF_Rope", xf((-0.24, 0.01, z + 0.09)))
    jc = H.box(0.3, 0.14, 0.4, 0.03, 2)
    mb.add(jc, RED, xf((0.25, 0.0, z + 0.2)))
    bx(mb, (0.15, -0.025, z + 0.4), (0.35, 0.025, z + 0.44), RED, 0.01)
    rod(mb, (0.34, 0.0, z + 0.4), (0.38, 0.0, z + 0.46), 0.015, RED, 8)
    z = 1.76
    for k in range(3):
        bx(mb, (-0.44 + k * 0.3, -0.18, z), (-0.18 + k * 0.3, 0.18, z + 0.18 - 0.03 * k), "MNF_WoodCrate", 0.008)
    root = mb.to_object("ShelfUnit", smooth_angle=35)
    H.col_box("COL_Shelf", root, (-W / 2, -D / 2, 0), (W / 2, D / 2, Hh))
    return E(root, "2.0 m steel shelving (angle posts, folded shelves, X bracing) stocked with crates, a toolbox, cans, "
                   "jars, cable and rope coils, paper boxes and a jerrycan.", figure=True, hero=True, shots=[("iso", None)])


def build_storage_locker():
    mb = MB(T_MED)
    W, D, Hb, Ht = 1.2, 0.6, 1.25, 1.6
    bx(mb, (-W / 2, -D / 2, 0.08), (W / 2, D / 2, Hb), GREEN, 0.015, 2)
    bx(mb, (-W / 2 + 0.03, -D / 2 + 0.03, 0.0), (W / 2 - 0.03, D / 2 - 0.03, 0.08), GRAY, 0.008)
    # double doors with louvres, handles, hinges
    for sx in (-1, 1):
        x0, x1 = (0.006, W / 2 - 0.04) if sx > 0 else (-W / 2 + 0.04, -0.006)
        bx(mb, (x0, -D / 2 - 0.012, 0.13), (x1, -D / 2 + 0.002, Hb - 0.05), GREEN, 0.006)
        for k in range(5):
            z = 0.95 + k * 0.035
            bx(mb, (x0 + 0.08, -D / 2 - 0.02, z), (x1 - 0.08, -D / 2 - 0.01, z + 0.012), GREEN, 0.003, m=None)
        for k in range(5):
            z = 0.22 + k * 0.035
            bx(mb, (x0 + 0.08, -D / 2 - 0.02, z), (x1 - 0.08, -D / 2 - 0.01, z + 0.012), GREEN, 0.003)
        hx = 0.04 * sx
        bx(mb, (hx - 0.012, -D / 2 - 0.05, 0.55), (hx + 0.012, -D / 2 - 0.012, 0.75), BARE, 0.006)
        for z in (0.25, 1.05):
            rod(mb, (sx * (W / 2 - 0.035), -D / 2 - 0.012, z), (sx * (W / 2 - 0.035), -D / 2 - 0.012, z + 0.1), 0.012, BARE, 8)
    bx(mb, (-0.12, -D / 2 - 0.016, 1.05), (0.12, -D / 2 - 0.012, 1.11), "MNF_Paper", 0.002)
    # open hopper on top: sloped funnel walls with a hazard rim
    ow, od = 1.0, 0.45
    zt = Ht
    zb = Hb + 0.02
    iw, idp = 0.5, 0.2
    outer = [Vector((-ow / 2, -od / 2, zt)), Vector((ow / 2, -od / 2, zt)), Vector((ow / 2, od / 2, zt)), Vector((-ow / 2, od / 2, zt))]
    inner = [Vector((-iw / 2, -idp / 2, zb)), Vector((iw / 2, -idp / 2, zb)), Vector((iw / 2, idp / 2, zb)), Vector((-iw / 2, idp / 2, zb))]
    funnel = H.skin([[p + Vector((0, 0, 0)) for p in outer], inner], cap_start=False, cap_end=True)
    mb.add(funnel, BARE, flat=True)
    shell_o = [Vector((-ow / 2 - 0.04, -od / 2 - 0.04, Hb)), Vector((ow / 2 + 0.04, -od / 2 - 0.04, Hb)),
               Vector((ow / 2 + 0.04, od / 2 + 0.04, Hb)), Vector((-ow / 2 - 0.04, od / 2 + 0.04, Hb))]
    rings = [shell_o, [p + Vector((0, 0, zt - Hb)) for p in shell_o], [p + Vector((0, 0, 0)) for p in outer]]
    mb.add(H.skin(rings, cap_start=False, cap_end=False), YEL, flat=True)
    for sy in (-1, 1):
        hazard_plate(mb, (-ow / 2 - 0.04, sy * (od / 2 + 0.04) - 0.004, zt - 0.08), (ow / 2 + 0.04, sy * (od / 2 + 0.04) + 0.004, zt - 0.01), 0.002)
    root = mb.to_object("StorageLocker", smooth_angle=35)
    H.empty("SOCKET_Deposit", root, (0, 0, (zt + zb) / 2))
    H.col_box("COL_Body", root, (-W / 2, -D / 2, 0), (W / 2, D / 2, Hb))
    return E(root, "Heavy locker cabinet 1.2 w x 1.6 h x 0.6 d, double louvred doors, open hopper on top (1.0 x 0.45 m "
                   "opening at 1.6 m). SOCKET_Deposit at the hopper centre.", figure=True, hero=True, shots=[("iso", None)])


# ============================================================================================
# Sell machine & dispenser
# ============================================================================================
def build_sell_machine():
    mb = MB(T_MED)
    W, D = 1.1, 0.85
    zt = 1.0
    # lower cabinet with hopper bin cut into the top
    bx(mb, (-W / 2, -D / 2, 0.06), (W / 2, D / 2, zt - 0.06), GRAY, 0.015, 2)
    bx(mb, (-W / 2 + 0.03, -D / 2 + 0.03, 0.0), (W / 2 - 0.03, D / 2 - 0.03, 0.06), "MNF_Rubber", 0.006)
    hazard_plate(mb, (-W / 2 + 0.02, -D / 2 - 0.006, 0.08), (W / 2 - 0.02, -D / 2 + 0.001, 0.2), 0.003)
    hw, hd = 0.6, 0.5
    hy = -D / 2 + 0.05 + hd / 2
    o = [Vector((-hw / 2, hy - hd / 2, zt)), Vector((hw / 2, hy - hd / 2, zt)), Vector((hw / 2, hy + hd / 2, zt)), Vector((-hw / 2, hy + hd / 2, zt))]
    ib = [Vector((-0.17, hy - 0.08, zt - 0.32)), Vector((0.17, hy - 0.08, zt - 0.32)), Vector((0.17, hy + 0.08, zt - 0.32)), Vector((-0.17, hy + 0.08, zt - 0.32))]
    mb.add(H.skin([o, ib], cap_start=False, cap_end=True), BARE, flat=True)
    # top deck around the hopper opening
    bx(mb, (-W / 2, -D / 2, zt - 0.06), (-hw / 2, D / 2, zt), GRAY, 0.008)
    bx(mb, (hw / 2, -D / 2, zt - 0.06), (W / 2, D / 2, zt), GRAY, 0.008)
    bx(mb, (-hw / 2, hy + hd / 2, zt - 0.06), (hw / 2, D / 2, zt), GRAY, 0.008)
    bx(mb, (-hw / 2, -D / 2, zt - 0.06), (hw / 2, hy - hd / 2, zt), GRAY, 0.008)
    for sy in (-1, 1):
        hazard_plate(mb, (-hw / 2 - 0.04, hy + sy * (hd / 2 + 0.02) - 0.02, zt), (hw / 2 + 0.04, hy + sy * (hd / 2 + 0.02) + 0.02, zt + 0.012), 0.002)
    for sx in (-1, 1):
        hazard_plate(mb, (sx * (hw / 2 + 0.02) - 0.02, hy - hd / 2 - 0.04, zt), (sx * (hw / 2 + 0.02) + 0.02, hy + hd / 2 + 0.04, zt + 0.012), 0.002)
    # back tower with the screen, buttons, sign plate area
    ty0 = D / 2 - 0.32
    bx(mb, (-W / 2, ty0, zt), (W / 2, D / 2, 2.05), YEL, 0.015, 2)
    bx(mb, (-0.26, ty0 - 0.03, 1.33), (0.26, ty0 + 0.01, 1.71), "MNF_Plastic_Black", 0.012)
    bx(mb, (-0.4, ty0 - 0.012, 1.8), (0.4, ty0 + 0.005, 1.98), GRAY, 0.004)
    for k in range(4):
        x = -0.24 + k * 0.16
        bx(mb, (x - 0.05, ty0 - 0.03, 1.12), (x + 0.05, ty0 + 0.005, 1.2), GRAY, 0.006)
        mb.add(H.cyl(0.026, 0.02, 12, bevel=0.005), ["MNF_BulbGreen", "MNF_BulbRed", "MNF_Plastic_Yellow", "MNF_Plastic_Black"][k],
               H.place((x, ty0 - 0.03, 1.16), (0, -1, 0)))
    # coin/ore result chute
    bx(mb, (0.33, -D / 2 - 0.08, 0.42), (0.5, -D / 2 + 0.01, 0.46), BARE, 0.006)
    bx(mb, (0.33, -D / 2 - 0.08, 0.42), (0.345, -D / 2 + 0.01, 0.52), BARE, 0.004)
    bx(mb, (0.485, -D / 2 - 0.08, 0.42), (0.5, -D / 2 + 0.01, 0.52), BARE, 0.004)
    bx(mb, (0.33, -D / 2 - 0.004, 0.46), (0.5, -D / 2 + 0.001, 0.6), "MNF_Plastic_Black", 0.004)
    # pneumatic tube up into the ceiling (assumed 3.0 m)
    tx, ty = -0.3, D / 2 - 0.15
    mb.add(H.cyl(0.11, 0.08, 14, bevel=0.01), GRAY, xf((tx, ty, 2.05)))
    mb.add(H.cyl(0.075, 0.42, 14, caps=False), BARE, xf((tx, ty, 2.13)))
    mb.add(H.cyl(0.078, 0.3, 14, caps=False), "MNF_Glass", xf((tx, ty, 2.55)))
    mb.add(H.cyl(0.075, 0.12, 14, caps=False), BARE, xf((tx, ty, 2.85)))
    for z in (2.13, 2.55, 2.85):
        mb.add(H.cyl(0.09, 0.03, 14, bevel=0.006), BARE, xf((tx, ty, z - 0.015)))
    mb.add(H.cyl(0.16, 0.02, 14, bevel=0.005), GRAY, xf((tx, ty, 2.98)))
    bolts(mb, [(tx + 0.13 * math.cos(a), ty + 0.13 * math.sin(a), 2.98) for a in (0.4, 2.0, 3.5, 5.1)], (0, 0, -1), 0.008)
    # side cable conduit and gauge
    cable(mb, [(W / 2 - 0.05, D / 2 - 0.05, 2.05), (W / 2 - 0.05, D / 2 - 0.05, 2.4), (W / 2 - 0.1, D / 2 - 0.05, 2.99)], 0.018, mat=BARE)
    mb.add(H.cyl(0.05, 0.03, 14, bevel=0.006), BARE, H.place((0.38, ty0, 1.5), (0, -1, 0)))
    mb.add(H.cyl(0.042, 0.002, 14), "MNF_Paper", H.place((0.38, ty0 - 0.03, 1.5), (0, -1, 0)))
    mb.add(H.cyl(0.044, 0.003, 14), "MNF_Glass", H.place((0.38, ty0 - 0.033, 1.5), (0, -1, 0)))
    root = mb.to_object("SellMachine", smooth_angle=35)
    sp = Vector((0, ty0 - 0.031, 1.52))
    sb = MB(T_SMALL)
    sb.add(H.quad(0.44, 0.32, "-Y"), "MNF_Screen", xf(sp))
    sb.to_object("Screen", root, pivot=sp, weighted=False)
    H.empty("SOCKET_Bin", root, (0, hy, zt - 0.15))
    H.col_box("COL_Cabinet", root, (-W / 2, -D / 2, 0), (W / 2, D / 2, zt))
    H.col_box("COL_Tower", root, (-W / 2, ty0, zt), (W / 2, D / 2, 2.05))
    return E(root, "Assay & Trade machine: cabinet with hazard kick plate and a 0.6 x 0.5 m hopper bin opening at 1.0 m "
                   "(SOCKET_Bin at the hopper centre), yellow back tower with child `Screen` (0.44 x 0.32 quad facing -Y), "
                   "buttons, gauge, sign plate area (1.8-1.98 m) for the ASSAY/TRADE atlas sign, pneumatic tube rising to "
                   "a ceiling flange at 3.0 m.", figure=True, hero=True, shots=[("iso", None), ("isol", None)])


def build_dispenser():
    mb = MB(T_SMALL)
    bx(mb, (-0.22, -0.012, -0.3), (0.22, 0.0, 0.32), YEL, 0.006)
    for sz in (-1, 1):
        hazard_plate(mb, (-0.21, -0.016, sz * 0.27 - 0.02 + (0.03 if sz > 0 else 0)), (0.21, -0.011, sz * 0.27 + 0.02 + (0.03 if sz > 0 else 0)), 0.002)
    bolts(mb, [(sx * 0.19, -0.012, sz) for sx in (-1, 1) for sz in (-0.27, 0.29)], (0, -1, 0), 0.007)
    # tube coming down the wall from above, bending out to the outlet
    path = [Vector((0, -0.09, 1.4)), Vector((0, -0.09, 0.5))] + H.bezier((0, -0.09, 0.5), (0, -0.09, 0.3), (0, -0.12, 0.18), (0, -0.2, 0.12), 6)[1:]
    mb.add(H.sweep(path, 0.075, 14), BARE)
    for z in (0.5, 0.9, 1.3):
        mb.add(H.cyl(0.09, 0.03, 14, bevel=0.006), BARE, xf((0, -0.09, z - 0.015)))
        bx(mb, (-0.012, -0.03, z - 0.03), (0.012, -0.012, z + 0.03), GRAY, 0.003)
    mb.add(H.cyl(0.078, 0.2, 14, caps=False), "MNF_Glass", xf((0, -0.09, 0.62)))
    # outlet mouth with flap and the tray below
    mo = path[-1]
    d = (path[-1] - path[-2]).normalized()
    mb.add(H.lathe([(0.075, 0.0), (0.095, 0.0), (0.1, 0.01), (0.1, 0.035), (0.075, 0.04)], 14, cap_start=False, cap_end=False), GRAY, H.place(mo, d))
    mb.add(H.box(0.15, 0.008, 0.13, 0.004, 1), GRAY, xf(mo + d * 0.045 + Vector((0, -0.03, -0.03)), (-35, 0, 0)))
    ty = -0.2
    bx(mb, (-0.16, ty - 0.13, -0.08), (0.16, -0.012, -0.06), GRAY, 0.005)
    for sx in (-1, 1):
        bx(mb, (sx * 0.16 - 0.008, ty - 0.13, -0.08), (sx * 0.16 + 0.008, -0.012, 0.0), GRAY, 0.003)
    bx(mb, (-0.16, ty - 0.138, -0.08), (0.16, ty - 0.122, 0.0), GRAY, 0.003)
    mb.add(H.extrude_poly([(0, 0), (0.11, 0), (0, -0.12)], 0.01, bevel=0.002, z0=-0.005), GRAY, xf((-0.12, -0.012, -0.07), (90, 0, -90)))
    mb.add(H.extrude_poly([(0, 0), (0.11, 0), (0, -0.12)], 0.01, bevel=0.002, z0=-0.005), GRAY, xf((0.12, -0.012, -0.07), (90, 0, -90)))
    root = mb.to_object("Dispenser", smooth_angle=35)
    H.empty("SOCKET_Out", root, (0, ty - 0.065, -0.06))
    return E(root, "Pneumatic delivery outlet: tube runs down the wall (from 1.4 m above the pivot), bends out to a mouth "
                   "with a hinged flap over a small tray (SOCKET_Out at the tray centre). Wall pivot, -Y out.",
             view="iso", cell=0.1, wall=True)


# ============================================================================================
# Bunkbed
# ============================================================================================
def _mattress(mb, mn, mx, seed, stain=True):
    m = H.box_mm(mn, mx, 0.035, 2)
    H.displace(m, 0.008, 4.0, seed)
    mb.add(m, "MNF_FabricCanvas")


def _blanket(mb, x0, x1, y0, y1, ztop, drop, seed):
    """Draped blanket: grid over the mattress top that falls over the -Y side."""
    nx, ny = 12, 7
    bm = bmesh.new()
    uv = H.uv_layer(bm)
    grid = []
    for i in range(nx + 1):
        row = []
        for j in range(ny + 1):
            u = i / nx
            v = j / ny
            x = lerp(x0, x1, u)
            # v 0..0.7 across the top, 0.7..1 down the side
            if v <= 0.72:
                y = lerp(y1, y0, v / 0.72)
                z = ztop + 0.006 + 0.015 * H.fbm((x * 3, y * 3, 0), seed)
            else:
                t = (v - 0.72) / 0.28
                y = y0 - 0.02 - 0.03 * t
                z = ztop - drop * t
            z += 0.012 * math.sin(x * 9 + seed) * (1 if v > 0.2 else 0.3)
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for i in range(nx):
        for j in range(ny):
            f = bm.faces.new([grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]])
            f.smooth = True
    bm.normal_update()
    # thickness
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=0.012)
    for f in bm.faces:
        f.smooth = True
    H.uv_box(bm, 1.0)
    mb.add(bm, "MNF_FabricBlanket", uv="keep")


def build_bunkbed():
    mb = MB(T_MED)
    L, W, Hh = 2.0, 0.9, 1.75
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx(mb, (sx * L / 2 - 0.025, sy * W / 2 - 0.025, 0), (sx * L / 2 + 0.025, sy * W / 2 + 0.025, Hh), GREEN, 0.006)
            mb.add(H.cyl(0.035, 0.012, 8), RUB, xf((sx * L / 2, sy * W / 2, 0)))
        # end frames with rungs (ladder at +X end)
        for z in (0.32, 0.6, 1.25, 1.65):
            bx(mb, (sx * L / 2 - 0.015, -W / 2, z - 0.015), (sx * L / 2 + 0.015, W / 2, z + 0.015), GREEN, 0.004)
    for z in (0.32, 1.25):
        for sy in (-1, 1):
            bx(mb, (-L / 2, sy * W / 2 - 0.02, z - 0.03), (L / 2, sy * W / 2 + 0.02, z + 0.03), GREEN, 0.005)
        # spring deck (grate) + cross slats
        bx(mb, (-L / 2 + 0.03, -W / 2 + 0.03, z - 0.01), (L / 2 - 0.03, W / 2 - 0.03, z), "MNF_MetalGrate", 0.0)
        for k in range(5):
            x = -0.8 + k * 0.4
            bx(mb, (x - 0.02, -W / 2, z - 0.035), (x + 0.02, W / 2, z - 0.01), GREEN, 0.003)
    # top safety rail
    for sy in (1,):
        bx(mb, (-L / 2, sy * W / 2 - 0.015, 1.55), (L / 2, sy * W / 2 + 0.015, 1.58), GREEN, 0.004)
    bx(mb, (-L / 2, -W / 2 - 0.015, 1.55), (-L / 2 + 0.9, -W / 2 + 0.015, 1.58), GREEN, 0.004)
    rod(mb, (-L / 2 + 0.9, -W / 2, 1.28), (-L / 2 + 0.9, -W / 2, 1.58), 0.014, GREEN, 6)
    # mattresses, pillows, blanket
    _mattress(mb, (-L / 2 + 0.04, -W / 2 + 0.04, 0.32), (L / 2 - 0.04, W / 2 - 0.04, 0.45), 3)
    _mattress(mb, (-L / 2 + 0.04, -W / 2 + 0.04, 1.25), (L / 2 - 0.04, W / 2 - 0.04, 1.37), 5)
    for z, s in ((0.45, 7), (1.37, 9)):
        p = H.box(0.32, 0.55, 0.1, 0.04, 2)
        H.displace(p, 0.01, 6, s)
        mb.add(p, "MNF_FabricCanvas", xf((-L / 2 + 0.25, 0.0, z + 0.04), (0, 8, 3)))
    _blanket(mb, -L / 2 + 0.55, L / 2 - 0.08, -W / 2 + 0.04, W / 2 - 0.04, 0.45, 0.3, 4)
    top_blanket = H.box(0.9, 0.7, 0.06, 0.025, 2)
    H.displace(top_blanket, 0.02, 5, 11)
    mb.add(top_blanket, "MNF_FabricBlanket", xf((0.45, 0.05, 1.39), (0, 0, 12)))
    root = mb.to_object("Bunkbed", smooth_angle=40)
    H.col_box("COL_Lower", root, (-L / 2, -W / 2, 0), (L / 2, W / 2, 0.45))
    H.col_box("COL_Upper", root, (-L / 2, -W / 2, 1.2), (L / 2, W / 2, 1.37))
    H.col_box("COL_Frame", root, (-L / 2 - 0.03, W / 2 - 0.03, 0), (L / 2 + 0.03, W / 2 + 0.03, Hh))
    return E(root, "Steel bunk bed 2.0 x 0.9 x 1.75 m, stained canvas mattresses and pillows, blanket draped over the lower "
                   "bunk (MNF_FabricBlanket), safety rail on top.", figure=True, hero=True, shots=[("iso", None)])


# ============================================================================================
# Generator
# ============================================================================================
def _gauge(mb, p, n, r=0.045):
    mb.add(H.cyl(r, 0.025, 14, bevel=0.005), BARE, H.place(p, n))
    q = Vector(p) + Vector(n).normalized() * 0.025
    mb.add(H.cyl(r * 0.85, 0.002, 14), "MNF_Paper", H.place(q, n))
    mb.add(H.cyl(r * 0.87, 0.004, 14), "MNF_Glass", H.place(q, n))


def build_generator():
    mb = MB(T_MED)
    L, W = 2.1, 0.95
    # skid base: channel rails + cross members, fuel tank inside, hazard stripes along the rails
    for sy in (-1, 1):
        bx(mb, (-L / 2, sy * W / 2 - 0.06, 0), (L / 2, sy * W / 2 + 0.06, 0.16), GRAY, 0.008)
        hazard_plate(mb, (-L / 2 + 0.05, sy * (W / 2 + 0.06) - (0.004 if sy > 0 else 0.0) + (0 if sy > 0 else -0.002), 0.03),
                     (L / 2 - 0.05, sy * (W / 2 + 0.06) + (0.002 if sy > 0 else 0.004), 0.13), 0.002)
    bx(mb, (-L / 2 + 0.1, -W / 2 + 0.06, 0.02), (L / 2 - 0.1, W / 2 - 0.06, 0.3), GRAY, 0.02, 2)
    mb.add(H.cyl(0.05, 0.03, 10, bevel=0.006), RED, xf((-0.7, 0.25, 0.3)))
    # engine block, head, valve cover
    bx(mb, (-0.75, -0.3, 0.3), (0.25, 0.3, 0.85), GREEN, 0.03, 2)
    bx(mb, (-0.72, -0.27, 0.85), (0.22, 0.27, 0.98), GREEN, 0.02, 2)
    bx(mb, (-0.7, -0.2, 0.98), (0.2, 0.2, 1.07), RED, 0.025, 2)
    for k in range(4):
        x = -0.6 + k * 0.24
        mb.add(H.bolt(0.012, 0.01, washer=True), BARE, xf((x, 0.0, 1.07)))
        # injector lines
        rod(mb, (x, -0.2, 1.02), (x, -0.32, 0.9), 0.007, BARE, 5)
    # exhaust manifold -> muffler -> stack
    rod(mb, (-0.7, 0.31, 0.92), (0.2, 0.31, 0.92), 0.04, RUST, 8)
    mb.add(H.cyl(0.12, 0.55, 14, bevel=0.02), RUST, H.place((-0.35, 0.4, 1.2), (1, 0, 0)))
    rod(mb, (-0.3, 0.33, 0.92), (-0.3, 0.4, 1.15), 0.04, RUST, 8)
    mb.add(H.sweep([(0.2, 0.4, 1.2), (0.32, 0.4, 1.2), (0.38, 0.4, 1.28), (0.38, 0.4, 1.85)], 0.05, 10), RUST)
    mb.add(H.cyl(0.07, 0.04, 10, bevel=0.008), RUST, xf((0.38, 0.4, 1.82)))
    # alternator at +X with cooling ribs
    ax0 = 0.25
    mb.add(H.cyl(0.3, 0.55, 18, bevel=0.03), YEL, H.place((ax0, 0, 0.6), (1, 0, 0)))
    for k in range(6):
        mb.add(H.cyl(0.31, 0.018, 18), YEL, H.place((ax0 + 0.06 + k * 0.08, 0, 0.6), (1, 0, 0)))
    mb.add(H.cyl(0.16, 0.06, 14, bevel=0.01), GRAY, H.place((ax0 + 0.55, 0, 0.6), (1, 0, 0)))
    bx(mb, (ax0 + 0.1, -0.15, 0.88), (ax0 + 0.4, 0.15, 1.02), GRAY, 0.01)
    bx(mb, (ax0, -0.28, 0.3), (ax0 + 0.55, 0.28, 0.36), GRAY, 0.008)
    # radiator at -X with grille and fan shroud
    bx(mb, (-1.0, -0.42, 0.3), (-0.88, 0.42, 1.15), GRAY, 0.015, 2)
    bx(mb, (-1.006, -0.36, 0.38), (-0.99, 0.36, 1.08), "MNF_MetalGrate", 0.0)
    mb.add(H.cyl(0.3, 0.1, 16, caps=False), GRAY, H.place((-0.88, 0, 0.72), (1, 0, 0)))
    mb.add(H.cyl(0.05, 0.08, 6, bevel=0.01), RED, xf((-0.94, 0.0, 1.15)))
    # air filter canister
    mb.add(H.cyl(0.1, 0.25, 12, bevel=0.015), GREEN, H.place((-0.4, -0.45, 1.05), (0, 1, 0)))
    rod(mb, (-0.4, -0.25, 1.05), (-0.4, -0.2, 1.0), 0.04, RUB, 8)
    # control panel on a post with gauges
    bx(mb, (0.85, -0.42, 0.16), (0.9, -0.37, 1.1), GRAY, 0.006)
    bx(mb, (0.68, -0.5, 1.0), (1.02, -0.4, 1.35), GRAY, 0.012, 2)
    hazard_plate(mb, (0.69, -0.505, 1.31), (1.01, -0.499, 1.34), 0.002)
    for k, x in enumerate((0.75, 0.85, 0.95)):
        _gauge(mb, (x, -0.5, 1.22), (0, -1, 0), 0.035)
    mb.add(H.cyl(0.02, 0.025, 10, bevel=0.004), RED, H.place((0.76, -0.5, 1.08), (0, -1, 0)))
    bx(mb, (0.86, -0.52, 1.06), (0.96, -0.5, 1.1), BARE, 0.004)
    mb.add(H.uvsphere(0.01, 8, 5), "MNF_BulbGreen", xf((0.98, -0.502, 1.08)))
    # pipes and cables
    cable(mb, [(0.82, -0.42, 1.05), (0.7, -0.38, 0.95), (0.55, -0.32, 0.7), (0.5, -0.3, 0.45)], 0.012)
    cable(mb, [(0.88, -0.38, 1.02), (0.75, -0.25, 0.98), (0.6, -0.1, 1.0), (0.4, 0.0, 1.02)], 0.01)
    mb.add(H.sweep([(-0.6, -0.31, 0.5), (-0.6, -0.4, 0.45), (-0.6, -0.42, 0.33), (-0.65, -0.38, 0.3)], 0.012, 6), BARE)
    mb.add(H.sweep([(-0.15, -0.31, 0.62), (-0.15, -0.38, 0.62), (-0.1, -0.42, 0.42), (0.05, -0.42, 0.31)], 0.01, 6), RUB)
    bolts(mb, [(x, sy * (W / 2 - 0.0), 0.16) for x in (-0.9, -0.3, 0.3, 0.9) for sy in (-1, 1)], (0, 0, 1), 0.012, washer=True)
    root = mb.to_object("Generator", smooth_angle=35)
    H.col_box("COL_Body", root, (-L / 2, -W / 2 - 0.06, 0), (L / 2, W / 2 + 0.06, 1.15))
    return E(root, "Large diesel generator on a hazard-striped skid: engine block, red valve cover, rusty exhaust with "
                   "muffler and stack, yellow alternator, radiator grille, control panel with 3 gauges, pipes and cables.",
             figure=True, hero=True, shots=[("iso", None), ("isol", None)])


# ============================================================================================
# Vent fan
# ============================================================================================
def build_vent_fan():
    mb = MB(T_MED)
    S, Dp = 0.8, 0.28
    # square housing (frame from 4 beveled boxes) and back plate
    t = 0.07
    for (a, b) in (((-S / 2, -Dp, S / 2 - t), (S / 2, 0, S / 2)), ((-S / 2, -Dp, -S / 2), (S / 2, 0, -S / 2 + t)),
                   ((-S / 2, -Dp, -S / 2 + t), (-S / 2 + t, 0, S / 2 - t)), ((S / 2 - t, -Dp, -S / 2 + t), (S / 2, 0, S / 2 - t))):
        bx(mb, a, b, GRAY, 0.012, 1)
    bx(mb, (-S / 2 - 0.03, -0.012, -S / 2 - 0.03), (S / 2 + 0.03, 0, S / 2 + 0.03), GRAY, 0.004)
    bolts(mb, [(sx * (S / 2 + 0.012), -0.012, sz * (S / 2 + 0.012)) for sx in (-1, 1) for sz in (-1, 1)], (0, -1, 0), 0.01)
    # round shroud inside the square, corner infill plates
    sh = H.lathe([(0.33, -0.0), (0.33, Dp - 0.03), (0.345, Dp - 0.01), (0.36, Dp)], 20, cap_start=False, cap_end=False)
    mb.add(sh, GRAY, H.place((0, 0, 0), (0, -1, 0)))
    for sx in (-1, 1):
        for sz in (-1, 1):
            tri = [(sx * (S / 2 - t), sz * (S / 2 - t)), (sx * 0.22, sz * (S / 2 - t)), (sx * (S / 2 - t), sz * 0.22)]
            mb.add(H.extrude_poly(tri, 0.012), GRAY, xf((0, -Dp + 0.012, 0), (90, 0, 0)) @ xf(scale=(1, 1, 1)))
    # motor on struts behind the blades
    mb.add(H.cyl(0.09, 0.14, 10, bevel=0.015), "MNF_Plastic_Black", H.place((0, -0.03, 0), (0, -1, 0)))
    for k in range(3):
        a = math.tau * k / 3 + math.pi / 2
        rod(mb, (0.08 * math.cos(a), -0.08, 0.08 * math.sin(a)), (0.335 * math.cos(a), -0.08, 0.335 * math.sin(a)), 0.012, GRAY, 6)
    # guard grille on the front: rings + radial wires
    gy = -Dp - 0.01
    for r, n in ((0.11, 12), (0.22, 18), (0.32, 22)):
        mb.add(H.torus(r, 0.004, n, 4), BARE, xf((0, gy, 0), (90, 0, 0)))
    for k in range(8):
        a = math.tau * k / 8
        rod(mb, (0.0, gy, 0.0), (0.34 * math.cos(a), gy, 0.34 * math.sin(a)), 0.0035, BARE, 4)
    mb.add(H.cyl(0.035, 0.01, 10), BARE, H.place((0, gy + 0.005, 0), (0, -1, 0)))
    root = mb.to_object("VentFan", smooth_angle=35)
    fb = MB(T_SMALL)
    hub = Vector((0, -0.17, 0))
    fb.add(H.cyl(0.07, 0.07, 14, bevel=0.012), GRAY, H.place(hub + Vector((0, 0.035, 0)), (0, -1, 0)))
    for k in range(5):
        blade = [(0.0, -0.05), (0.3, -0.09), (0.32, 0.0), (0.29, 0.07), (0.0, 0.035)]
        bl = H.extrude_poly(blade, 0.006, bevel=0.0015, z0=-0.003)
        for v in bl.verts:
            tw = v.co.x * 1.2
            y, z = v.co.y, v.co.z
            v.co.y, v.co.z = y * math.cos(tw) - z * math.sin(tw), y * math.sin(tw) + z * math.cos(tw)
        bl.normal_update()
        fb.add(bl, GRAY, xf(hub, (0, 72 * k, 0)) @ xf((0.04, 0, 0), (90, 25, 0)))
    fb.to_object("Fan", root, pivot=hub)
    return E(root, "Wall ventilation fan: 0.8 m square housing, round shroud, motor on struts, front guard grille. Child "
                   "`Fan` (5 twisted blades + hub) pivots at the hub; spin about Y. Wall pivot, -Y out.",
             view="iso", cell=0.1, wall=True)


# ============================================================================================
# Pipes, cables
# ============================================================================================
def _pipe_flanged(mb, path, r=0.075, n=16, mat=GREEN, nbolts=8):
    mb.add(H.sweep(path, r, n, caps=False), mat)
    for end, nxt in ((path[0], path[1]), (path[-1], path[-2])):
        d = (Vector(end) - Vector(nxt)).normalized()
        flange_ring(mb, Vector(end) - d * 0.03, d, r - 0.01, 0.12, 0.03, mat, nbolts=nbolts, n=n)
        # dark inner wall so the open end does not show the void
        mb.add(H.lathe([(r - 0.012, 0.0), (r - 0.012, -0.06)], n, cap_start=False, cap_end=True), RUB, H.place(end, d))


def build_pipe_straight():
    mb = MB(T_MED)
    _pipe_flanged(mb, [Vector((0, 0, 0)), Vector((1.0, 0, 0)), Vector((2.0, 0, 0))])
    for x in (0.7, 1.3):
        mb.add(H.torus(0.079, 0.006, 16, 4), BARE, H.place((x, 0, 0), (1, 0, 0)))
    bx(mb, (0.98, -0.02, 0.07), (1.02, 0.02, 0.1), "MNF_Paper", 0.002)
    root = mb.to_object("Pipe_Straight", smooth_angle=40)
    return E(root, "2 m flanged pipe, 0.15 m diameter, along +X from the origin (pivot at the inlet flange face centre).",
             view="iso", cell=0.25)


def build_pipe_elbow():
    mb = MB(T_MED)
    R = 0.3
    path = [Vector((0, 0, 0)), Vector((0.08, 0, 0))]
    for i in range(1, 9):
        a = math.pi / 2 * i / 8
        path.append(Vector((0.08 + R * math.sin(a), 0, R * (1 - math.cos(a)))))
    path.append(path[-1] + Vector((0, 0, 0.08)))
    _pipe_flanged(mb, path)
    root = mb.to_object("Pipe_Elbow", smooth_angle=40)
    return E(root, "90 deg flanged elbow: inlet at the origin facing -X, runs +X and turns up to an outlet at "
                   "(%.2f, 0, %.2f) facing +Z. Bend radius 0.3 m." % (path[-1].x, path[-1].z), view="iso", cell=0.25)


def build_pipe_valve():
    mb = MB(T_MED)
    _pipe_flanged(mb, [Vector((0, 0, 0)), Vector((0.3, 0, 0)), Vector((0.6, 0, 0))], nbolts=6, n=14)
    body = H.lathe([(0.0, -0.13), (0.06, -0.13), (0.11, -0.1), (0.125, -0.02), (0.11, 0.06), (0.07, 0.1), (0.07, 0.13), (0.0, 0.13)], 12)
    mb.add(body, GREEN, H.place((0.3, 0, 0), (1, 0, 0)))
    mb.add(H.cyl(0.07, 0.12, 12, bevel=0.01), GREEN, xf((0.3, 0, 0.08)))
    flange_ring(mb, Vector((0.3, 0, 0.2)), (0, 0, 1), 0.02, 0.085, 0.02, GREEN, nbolts=4, n=12)
    mb.add(H.cyl(0.018, 0.15, 8), BARE, xf((0.3, 0, 0.2)))
    # spoked handwheel
    wc = Vector((0.3, 0, 0.33))
    mb.add(H.torus(0.13, 0.012, 16, 5), RED, xf(wc))
    mb.add(H.cyl(0.03, 0.03, 8, bevel=0.006), RED, xf(wc - Vector((0, 0, 0.015))))
    for k in range(4):
        a = math.tau * k / 4 + 0.4
        rod(mb, wc, wc + Vector((0.125 * math.cos(a), 0.125 * math.sin(a), 0.0)), 0.008, RED, 5)
    root = mb.to_object("Pipe_Valve", smooth_angle=40)
    return E(root, "0.6 m flanged pipe section with a gate valve and red handwheel on top. Along +X from the origin.",
             view="iso", cell=0.25)


def build_cable_bundle():
    mb = MB(T_SMALL)
    rng = random.Random(6)
    for sx in (-1, 1):
        bx(mb, (sx * 1.0 - 0.03, -0.02, -0.02), (sx * 1.0 + 0.03, 0.04, 0.09), BARE, 0.004)
        bx(mb, (sx * 1.0 - 0.05, 0.04, -0.03), (sx * 1.0 + 0.05, 0.05, 0.1), BARE, 0.003)
        bolts(mb, [(sx * 1.0 + dx, 0.04, 0.07) for dx in (-0.03, 0.03)], (0, -1, 0), 0.006)
    offs = [(-0.012, 0.0), (0.012, 0.0), (0.0, 0.02), (-0.02, 0.03), (0.02, 0.025), (0.0, 0.045)]
    for k, (dy, dz) in enumerate(offs):
        sag = 0.22 + k * 0.025 + rng.uniform(-0.02, 0.02)
        pts = H.catenary((-1.0, dy, dz + 0.02), (1.0, dy, dz + 0.02), sag, 12)
        for p in pts[1:-1]:
            p.y += rng.uniform(-0.01, 0.01)
        cable(mb, pts, 0.011 if k % 3 else 0.016, 5)
    for x in (-0.55, 0.0, 0.55):
        z = -0.24 * 4 * (0.5 + x / 2) * (0.5 - x / 2) + 0.01
        mb.add(H.torus(0.04, 0.004, 10, 4, scale=(1.0, 1.2)), "MNF_Plastic_Black", xf((x, 0.005, z + 0.035), (0, 90, 0)))
    root = mb.to_object("CableBundle", smooth_angle=45)
    return E(root, "2 m bundle of 6 drooping rubber cables between two clamp brackets at x=+-1 (attachment height z=0), "
                   "zip ties. Pivot at the centre between the clamps; backs of the clamps at +Y (wall/ceiling side).",
             view="front", cell=0.25)


# ============================================================================================
# Clutter
# ============================================================================================
def build_crate_a():
    mb = MB(T_MED)
    W, D, Hh = 0.8, 0.6, 0.55
    rng = random.Random(2)
    pl = 4
    for k in range(pl):
        z0 = 0.02 + k * (Hh - 0.04) / pl
        z1 = z0 + (Hh - 0.04) / pl - 0.008
        for sy in (-1, 1):
            bx(mb, (-W / 2 + 0.02, sy * D / 2 - 0.012, z0), (W / 2 - 0.02, sy * D / 2 + 0.012, z1), "MNF_WoodCrate", 0.004)
        for sx in (-1, 1):
            bx(mb, (sx * W / 2 - 0.012, -D / 2 + 0.02, z0), (sx * W / 2 + 0.012, D / 2 - 0.02, z1), "MNF_WoodCrate", 0.004)
    for k in range(5):
        x0 = -W / 2 + 0.02 + k * (W - 0.04) / 5
        bx(mb, (x0, -D / 2 + 0.01, Hh - 0.025), (x0 + (W - 0.04) / 5 - 0.008, D / 2 - 0.01, Hh), "MNF_WoodCrate", 0.004)
        bx(mb, (x0, -D / 2 + 0.01, 0.0), (x0 + (W - 0.04) / 5 - 0.008, D / 2 - 0.01, 0.025), "MNF_WoodCrate", 0.004)
    # corner battens + metal corner brackets
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (0.0, Hh - 0.06):
                bx(mb, (sx * W / 2 - (0.05 if sx > 0 else -0.0) - (0.0 if sx > 0 else 0.016), sy * D / 2 - (0.05 if sy > 0 else -0.0) - (0.0 if sy > 0 else 0.016), z),
                   (sx * W / 2 + (0.016 if sx > 0 else 0.05), sy * D / 2 + (0.016 if sy > 0 else 0.05), z + 0.06), BARE, 0.0)
    for sy in (-1, 1):
        for x in (-0.25, 0.25):
            bx(mb, (x - 0.03, sy * (D / 2 + 0.012) - 0.006, 0.02), (x + 0.03, sy * (D / 2 + 0.012) + 0.006, Hh - 0.02), "MNF_WoodCrate", 0.004)
    bx(mb, (-0.15, -D / 2 - 0.02, 0.22), (0.15, -D / 2 - 0.018, 0.34), "MNF_Paper", 0.001)
    root = mb.to_object("Crate_A", smooth_angle=35)
    return E(root, "Wooden supply crate 0.8 x 0.6 x 0.55 m, planked with battens and steel corner brackets, paper label.",
             cell=0.25)


def build_crate_b():
    mb = MB(T_MED)
    W, D, Hh = 1.0, 0.5, 0.45
    bx(mb, (-W / 2, -D / 2, 0.02), (W / 2, D / 2, Hh - 0.1), GREEN, 0.012, 2)
    bx(mb, (-W / 2 - 0.006, -D / 2 - 0.006, Hh - 0.1), (W / 2 + 0.006, D / 2 + 0.006, Hh), GREEN, 0.015, 2)
    for x in (-0.3, 0.0, 0.3):
        bx(mb, (x - 0.02, -D / 2 - 0.012, Hh - 0.002), (x + 0.02, D / 2 + 0.012, Hh + 0.012), GREEN, 0.005)
    for sx in (-1, 1):
        bx(mb, (sx * (W / 2 - 0.08) - 0.035, -D / 2 - 0.008, 0.0), (sx * (W / 2 - 0.08) + 0.035, D / 2 + 0.008, 0.03), GREEN, 0.005)
        # latch
        bx(mb, (sx * 0.3 - 0.03, -D / 2 - 0.014, Hh - 0.15), (sx * 0.3 + 0.03, -D / 2 - 0.004, Hh - 0.07), BARE, 0.004)
        # side handle
        pts = [(sx * (W / 2 + 0.005), -0.08, 0.27), (sx * (W / 2 + 0.035), -0.06, 0.24), (sx * (W / 2 + 0.035), 0.06, 0.24), (sx * (W / 2 + 0.005), 0.08, 0.27)]
        mb.add(H.sweep(pts, 0.008, 6), BARE)
        bx(mb, (sx * (W / 2) - 0.004, -0.1, 0.25), (sx * (W / 2) + 0.004 * sx + (0.008 if sx > 0 else -0.0), 0.1, 0.29), BARE, 0.003)
    bx(mb, (-0.15, -D / 2 - 0.009, 0.15), (0.15, -D / 2 - 0.006, 0.26), "MNF_Paper", 0.001)
    root = mb.to_object("Crate_B", smooth_angle=35)
    return E(root, "Military steel footlocker 1.0 x 0.5 x 0.45 m with lid ribs, latches, side handles, stencil label.",
             cell=0.25)


def build_barrel():
    mb = MB(T_MED)
    R, Hh = 0.29, 0.88
    prof = [(0.0, 0.006), (R - 0.02, 0.006), (R - 0.012, 0.0), (R, 0.012), (R - 0.004, 0.03)]
    for zc in (0.29, 0.59):
        prof += [(R - 0.004, zc - 0.02), (R + 0.008, zc - 0.006), (R + 0.008, zc + 0.006), (R - 0.004, zc + 0.02)]
    prof += [(R - 0.004, Hh - 0.03), (R, Hh - 0.012), (R - 0.012, Hh), (R - 0.02, Hh - 0.006), (0.0, Hh - 0.006)]
    b = H.lathe(prof, 20)
    H.dent(b, (0.2, -0.2, 0.45), 0.14, 0.025)
    H.dent(b, (-0.25, 0.1, 0.75), 0.1, 0.015)
    mb.add(b, RED)
    for (x, y, r) in ((0.15, 0.08, 0.035), (-0.17, -0.05, 0.022)):
        mb.add(H.cyl(r, 0.012, 8, bevel=0.003, flat=True), BARE, xf((x, y, Hh - 0.008)))
    bx(mb, (-0.12, -R - 0.004, 0.36), (0.12, -R + 0.01, 0.52), "MNF_Paper", 0.002)
    root = mb.to_object("Barrel", smooth_angle=40)
    return E(root, "Dented steel oil drum 0.58 x 0.88 m (MNF_MetalPainted_Red) with rolling hoops, bungs, label.", cell=0.25)


def build_chair():
    mb = MB(T_MED)
    sw, sd, sh = 0.44, 0.42, 0.46
    for sx in (-1, 1):
        rod(mb, (sx * sw / 2, -sd / 2, 0.0), (sx * sw / 2, -sd / 2 + 0.02, sh), 0.012, GRAY, 8)
        rod(mb, (sx * sw / 2, sd / 2, 0.0), (sx * sw / 2, sd / 2 - 0.02, 0.88), 0.012, GRAY, 8)
        rod(mb, (sx * sw / 2, -sd / 2 + 0.02, sh - 0.02), (sx * sw / 2, sd / 2 - 0.02, sh - 0.02), 0.01, GRAY, 6)
        rod(mb, (sx * sw / 2, -sd / 2 + 0.01, 0.15), (sx * sw / 2, sd / 2 - 0.01, 0.15), 0.008, GRAY, 6)
        for sy in (-1, 1):
            mb.add(H.cyl(0.016, 0.012, 8), RUB, xf((sx * sw / 2, sy * sd / 2 - (0.0), 0.0)))
    rod(mb, (-sw / 2, -sd / 2 + 0.02, sh - 0.03), (sw / 2, -sd / 2 + 0.02, sh - 0.03), 0.01, GRAY, 6)
    for k in range(3):
        y0 = -sd / 2 + 0.02 + k * (sd - 0.04) / 3
        bx(mb, (-sw / 2 - 0.01, y0 + 0.003, sh - 0.01), (sw / 2 + 0.01, y0 + (sd - 0.04) / 3 - 0.003, sh + 0.012), "MNF_WoodPlanks", 0.004)
    for z in (0.62, 0.78):
        bx(mb, (-sw / 2 - 0.01, sd / 2 - 0.035, z), (sw / 2 + 0.01, sd / 2 - 0.012, z + 0.1), "MNF_WoodPlanks", 0.005,
           m=xf((0, sd / 2, z), (-8, 0, 0)) @ xf((0, -sd / 2, -z)))
    root = mb.to_object("Chair", smooth_angle=40)
    return E(root, "Steel-tube chair with plank seat and backrest; seat at 0.46 m.", cell=0.25)


def build_table():
    mb = MB(T_MED)
    W, D, Hh = 1.4, 0.8, 0.76
    for k in range(5):
        y0 = -D / 2 + k * D / 5
        bx(mb, (-W / 2, y0 + 0.003, Hh - 0.035), (W / 2, y0 + D / 5 - 0.003, Hh), "MNF_WoodPlanks", 0.005)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx(mb, (sx * (W / 2 - 0.06) - 0.025, sy * (D / 2 - 0.06) - 0.025, 0.0), (sx * (W / 2 - 0.06) + 0.025, sy * (D / 2 - 0.06) + 0.025, Hh - 0.035), GRAY, 0.005)
        bx(mb, (sx * (W / 2 - 0.06) - 0.015, -D / 2 + 0.06, Hh - 0.1), (sx * (W / 2 - 0.06) + 0.015, D / 2 - 0.06, Hh - 0.035), GRAY, 0.004)
        bx(mb, (sx * (W / 2 - 0.06) - 0.012, -D / 2 + 0.06, 0.12), (sx * (W / 2 - 0.06) + 0.012, D / 2 - 0.06, 0.15), GRAY, 0.004)
    for sy in (-1, 1):
        bx(mb, (-W / 2 + 0.06, sy * (D / 2 - 0.06) - 0.015, Hh - 0.1), (W / 2 - 0.06, sy * (D / 2 - 0.06) + 0.015, Hh - 0.035), GRAY, 0.004)
    bx(mb, (-W / 2 + 0.06, -0.012, 0.12), (W / 2 - 0.06, 0.012, 0.15), GRAY, 0.004)
    root = mb.to_object("Table", smooth_angle=35)
    H.col_box("COL_Top", root, (-W / 2, -D / 2, 0), (W / 2, D / 2, Hh))
    return E(root, "Steel-framed table 1.4 x 0.8 m, plank top at 0.76 m.", cell=0.25)


def build_radio():
    mb = MB(T_SMALL)
    W, D, Hh = 0.4, 0.22, 0.27
    bx(mb, (-W / 2, -D / 2, 0.012), (W / 2, D / 2, Hh), GREEN, 0.015, 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.add(H.cyl(0.014, 0.012, 8, bevel=0.003), RUB, xf((sx * (W / 2 - 0.03), sy * (D / 2 - 0.03), 0.0)))
    # front panel: dial window, speaker grille, knobs, switches
    bx(mb, (-W / 2 + 0.015, -D / 2 - 0.006, 0.03), (W / 2 - 0.015, -D / 2 + 0.001, Hh - 0.015), GRAY, 0.004)
    bx(mb, (-0.17, -D / 2 - 0.012, 0.16), (0.05, -D / 2 - 0.005, 0.235), "MNF_Plastic_Black", 0.004)
    bx(mb, (-0.16, -D / 2 - 0.0125, 0.17), (0.04, -D / 2 - 0.009, 0.225), "MNF_Paper", 0.0)
    mb.add(H.quad(0.2, 0.055, "-Y"), "MNF_Glass", xf((-0.06, -D / 2 - 0.0128, 0.1975)))
    bx(mb, (-0.17, -D / 2 - 0.012, 0.045), (0.05, -D / 2 - 0.005, 0.14), "MNF_MetalGrate", 0.004)
    for k, (x, z, r) in enumerate(((0.12, 0.2, 0.026), (0.12, 0.09, 0.018), (0.165, 0.09, 0.015))):
        mb.add(H.cyl(r, 0.022, 12, bevel=0.004), "MNF_Plastic_Black", H.place((x, -D / 2 - 0.006, z), (0, -1, 0)))
    for x in (0.08, 0.1):
        rod(mb, (x, -D / 2 - 0.006, 0.05), (x, -D / 2 - 0.022, 0.06), 0.003, BARE, 5)
    # carry handle and telescopic antenna
    hp = [(-0.12, 0.0, Hh), (-0.11, 0.0, Hh + 0.05), (0.11, 0.0, Hh + 0.05), (0.12, 0.0, Hh)]
    mb.add(H.sweep(hp, 0.009, 6), RUB)
    ab = Vector((0.16, 0.07, Hh))
    mb.add(H.cyl(0.012, 0.02, 8, bevel=0.003), "MNF_Plastic_Black", xf(ab))
    d = Vector((-0.25, 0.1, 1.0)).normalized()
    seg = [(0.006, 0.25), (0.0045, 0.22), (0.003, 0.2)]
    p = ab + Vector((0, 0, 0.02))
    for r, ln in seg:
        mb.add(H.cyl(r, ln, 6), BARE, H.place(p, d))
        p = p + d * ln
    mb.add(H.uvsphere(0.006, 6, 4), BARE, xf(p))
    root = mb.to_object("Radio", smooth_angle=35)
    db = MB(T_SMALL)
    dp = Vector((0.12, -D / 2 - 0.006, 0.2))
    db.add(H.cyl(0.026, 0.024, 12, bevel=0.005), "MNF_Plastic_Black", H.place(dp, (0, -1, 0)))
    db.add(H.box(0.004, 0.003, 0.02), "MNF_Paper", xf(dp + Vector((0, -0.0245, 0.012))))
    db.to_object("Dial", root, pivot=dp)
    return E(root, "Military field radio 0.4 x 0.22 x 0.27 m: dial window, speaker grille, knobs, rubber carry handle, "
                   "3-section telescopic antenna. Extra child `Dial` (tuning knob, pivot at its axis, turns about Y). "
                   "Pivot at the bottom centre.", cell=0.1)


def build_clipboard():
    mb = MB(T_SMALL)
    bx(mb, (-0.115, -0.16, 0.0), (0.115, 0.16, 0.004), "MNF_WoodPlanks", 0.002)
    rng = random.Random(4)
    for k in range(3):
        sh = H.box(0.21, 0.28, 0.001)
        for v in sh.verts:
            v.co.z += 0.004 * (v.co.y / 0.14) ** 2 * (1 if v.co.y < 0 else 0.2)
        sh.normal_update()
        mb.add(sh, "MNF_Paper", xf((rng.uniform(-0.004, 0.004), -0.01 + rng.uniform(-0.004, 0.004), 0.0045 + k * 0.0012), (0, 0, rng.uniform(-3, 3))))
    bx(mb, (-0.05, 0.12, 0.004), (0.05, 0.15, 0.014), BARE, 0.004)
    rod(mb, (-0.045, 0.125, 0.016), (0.045, 0.125, 0.016), 0.004, BARE, 6)
    mb.add(H.extrude_poly([(-0.04, 0.0), (0.04, 0.0), (0.035, 0.03), (-0.035, 0.03)], 0.002, z0=0.0), BARE, xf((0, 0.1, 0.017), (8, 0, 0)))
    root = mb.to_object("Clipboard", smooth_angle=35)
    return E(root, "Clipboard 0.23 x 0.32 m lying flat (papers face +Z, clip toward +Y). Pivot at the bottom centre.",
             view="top", cell=0.1)


def build_locker_tall():
    mb = MB(T_MED)
    W, D, Hh = 0.45, 0.5, 1.9
    bx(mb, (-W / 2, -D / 2 + 0.02, 0.1), (W / 2, D / 2, Hh), GRAY, 0.01, 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx(mb, (sx * (W / 2 - 0.03) - 0.015, sy * (D / 2 - 0.04) - 0.015, 0.0), (sx * (W / 2 - 0.03) + 0.015, sy * (D / 2 - 0.04) + 0.015, 0.1), GRAY, 0.004)
    door = H.box(W - 0.03, 0.02, Hh - 0.16, 0.006, 1)
    H.dent(door, (0.06, -0.01, -0.25), 0.12, 0.012, direction=(0, 1, 0))
    mb.add(door, GRAY, xf((0, -D / 2 + 0.012, (Hh + 0.12) / 2)))
    for zz in (Hh - 0.25, 0.3):
        for k in range(6):
            z = zz + k * 0.025
            bx(mb, (-0.12, -D / 2 - 0.006, z), (0.12, -D / 2 + 0.004, z + 0.01), "MNF_Plastic_Black", 0.002)
    bx(mb, (0.14, -D / 2 - 0.03, 0.85), (0.17, -D / 2 + 0.002, 1.05), BARE, 0.006)
    bx(mb, (0.135, -D / 2 - 0.018, 0.9), (0.175, -D / 2 - 0.008, 0.95), BARE, 0.003)
    mb.add(H.torus(0.014, 0.004, 10, 4), BARE, xf((0.155, -D / 2 - 0.03, 0.9), (90, 0, 0)))
    bx(mb, (0.14, -D / 2 - 0.05, 0.86), (0.17, -D / 2 - 0.028, 0.885), BARE, 0.004)
    bx(mb, (-0.05, -D / 2 - 0.004, Hh - 0.1), (0.05, -D / 2 + 0.001, Hh - 0.06), "MNF_Paper", 0.001)
    for z in (0.3, Hh - 0.3):
        rod(mb, (-W / 2 + 0.01, -D / 2 + 0.005, z), (-W / 2 + 0.01, -D / 2 + 0.005, z + 0.08), 0.01, BARE, 6)
    root = mb.to_object("Locker_Tall", smooth_angle=35)
    return E(root, "Single tall steel locker 0.45 x 0.5 x 1.9 m, dented door, louvres, padlock hasp, name plate.",
             figure=True)


def build_fusebox():
    mb = MB(T_SMALL)
    W, D, Hh = 0.4, 0.15, 0.5
    bx(mb, (-W / 2, -D + 0.02, -Hh / 2), (W / 2, 0, Hh / 2), GRAY, 0.012, 2)
    bx(mb, (-W / 2 + 0.006, -D, -Hh / 2 + 0.006), (W / 2 - 0.006, -D + 0.022, Hh / 2 - 0.006), GRAY, 0.008)
    for z in (-0.15, 0.15):
        mb.add(H.cyl(0.01, 0.05, 8), BARE, xf((-W / 2 - 0.004, -D + 0.01, z - 0.025)))
    hazard_plate(mb, (-0.15, -D - 0.003, 0.12), (0.15, -D + 0.001, 0.2), 0.002)
    bx(mb, (-0.12, -D - 0.003, 0.04), (0.12, -D + 0.001, 0.1), "MNF_Paper", 0.002)
    bx(mb, (0.13, -D - 0.025, -0.08), (0.16, -D, 0.0), BARE, 0.005)
    # side breaker handle
    mb.add(H.cyl(0.03, 0.02, 10, bevel=0.005), BARE, H.place((W / 2, -D / 2, 0.0), (1, 0, 0)))
    bx(mb, (W / 2 + 0.01, -D / 2 - 0.012, 0.0), (W / 2 + 0.03, -D / 2 + 0.012, 0.16), RED, 0.006)
    rod(mb, (W / 2 + 0.02, -D / 2 - 0.035, 0.16), (W / 2 + 0.02, -D / 2 + 0.035, 0.16), 0.014, RUB, 8)
    for x in (-0.1, 0.0, 0.1):
        rod(mb, (x, -D / 2, Hh / 2), (x, -D / 2, Hh / 2 + 0.3), 0.016, BARE, 8)
        mb.add(H.cyl(0.024, 0.03, 8, bevel=0.004), BARE, xf((x, -D / 2, Hh / 2)))
    rod(mb, (0.0, -D / 2, -Hh / 2), (0.0, -D / 2, -Hh / 2 - 0.25), 0.02, BARE, 8)
    root = mb.to_object("FuseBox", smooth_angle=35)
    return E(root, "Wall fuse box 0.4 x 0.5 x 0.15 m with hinged door, HIGH-VOLTAGE hazard band + label, side breaker "
                   "handle, conduits up/down. Wall pivot, -Y out.", view="iso", cell=0.1, wall=True)


def build_bucket():
    mb = MB(T_SMALL)
    prof = [(0.0, 0.004), (0.115, 0.004), (0.12, 0.0), (0.125, 0.015)]
    for k in range(3):
        z = 0.07 + k * 0.08
        prof += [(0.125 + z * 0.1, z - 0.008), (0.129 + z * 0.1, z), (0.125 + z * 0.1, z + 0.008)]
    prof += [(0.155, 0.29), (0.162, 0.3), (0.158, 0.306), (0.15, 0.298)]
    prof2 = prof + [(0.145, 0.296), (0.118, 0.015), (0.0, 0.015)]
    b = H.lathe(prof2, 18, cap_end=True)
    H.dent(b, (0.13, -0.08, 0.15), 0.08, 0.012)
    mb.add(b, BARE)
    for sx in (-1, 1):
        mb.add(H.cyl(0.015, 0.006, 8), BARE, H.place((sx * 0.155, 0, 0.27), (sx, 0, 0)))
    bail = [Vector((0.16 * math.cos(math.pi * i / 12), 0.0, 0.27 + 0.17 * math.sin(math.pi * i / 12))) for i in range(13)]
    bail = [xf(rot=(0, 0, 0)) @ p for p in bail]
    for p in bail:
        p.y = -0.06 * math.sin(math.pi * (p.x + 0.16) / 0.32)
    mb.add(H.sweep(bail, 0.0035, 5), BARE)
    rod(mb, (-0.045, bail[6].y, bail[6].z - 0.001), (0.045, bail[6].y, bail[6].z - 0.001), 0.012, "MNF_WoodHandle", 8)
    root = mb.to_object("Bucket", smooth_angle=40)
    return E(root, "Galvanised steel bucket (top 0.32 m dia, 0.3 m tall), dented, wire bail with wooden grip.", cell=0.1)


# ============================================================================================
# Blast door, poster board
# ============================================================================================
def build_blast_door():
    mb = MB(T_BIG)
    R, T = 1.3, 0.45
    zc = R + 0.08
    c = Vector((0, -T, zc))
    # stepped round door body built along -Y (back face against the wall at y=0)
    prof = [(0.0, 0.0), (R - 0.06, 0.0), (R, 0.04), (R, T * 0.55), (R - 0.12, T * 0.6), (R - 0.14, T - 0.03), (R - 0.17, T),
            (0.0, T)]
    body = H.lathe(prof, 32)
    mb.add(body, GRAY, H.place((0, 0, zc), (0, -1, 0)), uv="box")
    # hazard band round the rim, inner raised ring
    mb.add(H.lathe([(R + 0.004, 0.06), (R + 0.004, T * 0.5)], 32, cap_start=False, cap_end=False), HAZ, H.place((0, 0, zc), (0, -1, 0)))
    ring = H.lathe([(0.75, 0.0), (0.8, 0.0), (0.8, 0.05), (0.75, 0.06)], 32, cap_start=False, cap_end=False)
    mb.add(ring, GRAY, H.place((0, -T, zc), (0, -1, 0)))
    # locking bolts (retracted, ends visible on the rim) + carriers + linkage bars to the hub
    nb = 12
    for k in range(nb):
        a = math.tau * k / nb + math.tau / nb / 2
        u = Vector((math.cos(a), 0, math.sin(a)))
        mb.add(H.cyl(0.055, 0.12, 10, bevel=0.01), BARE, H.place(Vector((0, -T * 0.3, zc)) + u * (R - 0.08), u))
        car = Vector((0, -T - 0.02, zc)) + u * 1.0
        mb.add(H.box(0.12, 0.05, 0.1, 0.012, 1), GRAY, xf(car, (0, -math.degrees(a), 0)))
        if k % 2 == 0:
            p0 = Vector((0, -T - 0.05, zc)) + u * 0.2
            p1 = Vector((0, -T - 0.05, zc)) + u * 0.95
            mb.add(H.box(0.75, 0.025, 0.05, 0.006, 1), BARE, xf((p0 + p1) / 2, (0, -math.degrees(a), 0)))
    # central hub + handwheel
    mb.add(H.cyl(0.2, 0.08, 20, bevel=0.015), BARE, H.place(c, (0, -1, 0)))
    wc = c + Vector((0, -0.18, 0))
    mb.add(H.torus(0.42, 0.03, 32, 6), RED, xf(wc, (90, 0, 0)))
    for k in range(4):
        a = math.tau * k / 4 + math.pi / 4
        u = Vector((math.cos(a), 0, math.sin(a)))
        rod(mb, wc + u * 0.06, wc + u * 0.41, 0.022, RED, 8)
    mb.add(H.cyl(0.08, 0.2, 14, bevel=0.015), RED, H.place(c, (0, -1, 0)))
    # hinge: arm from the door edge to a vertical hinge barrel near the wall
    hx = R + 0.25
    for z in (zc - 0.65, zc + 0.65):
        bx(mb, (R - 0.3, -T * 0.75, z - 0.09), (hx + 0.05, -T * 0.25, z + 0.09), GRAY, 0.02, 2)
    mb.add(H.cyl(0.16, 1.7, 18, bevel=0.03), GRAY, xf((hx, -T * 0.5, zc - 0.85)))
    for z in (zc - 0.85, zc + 0.85):
        mb.add(H.cyl(0.19, 0.08, 18, bevel=0.015), BARE, xf((hx, -T * 0.5, z - 0.04)))
    bolts(mb, [(R - 0.2 + dx, -T * 0.75, z) for z in (zc - 0.65, zc + 0.65) for dx in (0.0, 0.15)], (0, -1, 0), 0.025, washer=True)
    root = mb.to_object("BlastDoor", smooth_angle=35)
    H.col_box("COL_Door", root, (-R, -T, 0.08), (R, 0.0, zc + R))
    H.col_box("COL_Hinge", root, (R - 0.3, -T, zc - 0.9), (hx + 0.2, 0.0, zc + 0.9))
    return E(root, "Huge round blast door (2.6 m dia, 0.45 m thick) in the open position swung flat against a wall: "
                   "inner face out (-Y) showing the red handwheel, hub, bolt carriers/linkage, retracted locking bolts on "
                   "the hazard-striped rim, hinge arms + barrel on +X. Pivot at the floor below the door centre, back "
                   "face on the wall plane y=0.", figure=True, hero=True, shots=[("iso", None)], wall=True)


def build_poster_board():
    mb = MB(T_SMALL)
    W, Hh = 1.0, 0.7
    bx(mb, (-W / 2 + 0.03, -0.012, -Hh / 2 + 0.03), (W / 2 - 0.03, 0.0, Hh / 2 - 0.03), "MNF_WoodRotten", 0.0)
    for (a, b) in (((-W / 2, -0.025, Hh / 2 - 0.035), (W / 2, 0.0, Hh / 2)), ((-W / 2, -0.025, -Hh / 2), (W / 2, 0.0, -Hh / 2 + 0.035)),
                   ((-W / 2, -0.025, -Hh / 2 + 0.035), (-W / 2 + 0.035, 0.0, Hh / 2 - 0.035)), ((W / 2 - 0.035, -0.025, -Hh / 2 + 0.035), (W / 2, 0.0, Hh / 2 - 0.035))):
        bx(mb, a, b, "MNF_WoodPlanks", 0.005)
    rng = random.Random(13)
    notes = [(-0.32, 0.18, 0.16, 0.2), (-0.1, 0.2, 0.14, 0.12), (0.15, 0.17, 0.2, 0.15), (0.35, 0.15, 0.12, 0.17),
             (-0.3, -0.1, 0.18, 0.13), (-0.05, -0.08, 0.13, 0.17), (0.2, -0.12, 0.17, 0.14), (0.38, -0.15, 0.1, 0.12)]
    pins = []
    for k, (x, z, w, h) in enumerate(notes):
        q = H.quad(w, h, "-Y")
        for v in q.verts:
            pass
        # subdivide a little for a curl
        bmesh.ops.subdivide_edges(q, edges=[e for e in q.edges if abs(e.verts[0].co.x - e.verts[1].co.x) > 1e-4], cuts=2, use_grid_fill=True)
        for v in q.verts:
            v.co.y -= 0.006 * ((v.co.z + h / 2) / h) ** 2 * (1 if k % 3 else 0.3)
        q.normal_update()
        H.uv_box(q, 0.5)
        mb.add(q, "MNF_Paper", xf((x, -0.0135 - 0.0005 * k, z), (0, rng.uniform(-8, 8), 0)), uv="keep")
        pp = Vector((x + rng.uniform(-0.02, 0.02), -0.016, z + h / 2 - 0.02))
        pins.append(pp)
        mb.add(H.cyl(0.006, 0.008, 6, bevel=0.002), "MNF_Plastic_Orange" if k % 2 else "MNF_Plastic_Yellow", H.place(pp, (0, -1, 0)))
    # string connecting some of the pins
    for a, b in ((0, 2), (2, 6), (1, 4), (4, 7), (3, 5)):
        p0, p1 = pins[a] + Vector((0, -0.006, 0)), pins[b] + Vector((0, -0.006, 0))
        mb.add(H.sweep([p0, (p0 + p1) / 2 + Vector((0, -0.002, -0.01)), p1], 0.0012, 3), "MNF_Rope")
    root = mb.to_object("PosterBoard", smooth_angle=35)
    return E(root, "Cork board 1.0 x 0.7 m (cork face uses MNF_WoodRotten - no cork in the catalog) with pinned curled "
                   "notes and string between pins. Wall pivot, -Y out.", view="front", cell=0.1, wall=True)


def build():
    out = [build_workbench(), build_terminal()]
    out += build_terminal_button()
    out += build_big_button()
    out += build_lever()
    out += [build_gate_frame(), build_gate_bars(), build_warning_beacon(), build_fluorescent(), build_cage_lamp(),
            build_emergency_light(), build_tool_rack(), build_shelf_unit(), build_storage_locker(), build_sell_machine(),
            build_dispenser(), build_bunkbed(), build_generator(), build_vent_fan(), build_pipe_straight(),
            build_pipe_elbow(), build_pipe_valve(), build_cable_bundle(), build_crate_a(), build_crate_b(),
            build_barrel(), build_chair(), build_table(), build_radio(), build_clipboard(), build_locker_tall(),
            build_fusebox(), build_bucket(), build_blast_door(), build_poster_board()]
    return out
