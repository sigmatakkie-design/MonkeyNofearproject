"""kitA_tools.py - Kit_Tools.fbx: handheld tools & items (prop artist A).

Pivot = main grip, forward/tip along -Y, up +Z.  Pickaxes: head at the far (-Y) end, pointed
tip toward -Z, adze toward +Z.  See Docs/BRIEF_PROPS.md.
"""
import math
import random
from mathutils import Vector, Matrix

import propkit_a_helpers as H
from propkit_a_helpers import MB, xf, V, lerp, smoothstep

KIT = "Kit_Tools"
RX90 = xf(rot=(90, 0, 0))       # part built along +Z -> points along -Y (forward)
TILE = 0.4

# required names for validation (from the brief)
REQUIRED = {
    "Pickaxe_T1": ["TIP", "COL_Handle", "COL_Head"],
    "Pickaxe_T2": ["TIP", "COL_Handle", "COL_Head"],
    "Pickaxe_T3": ["TIP", "COL_Handle", "COL_Head"],
    "Spear": ["TIP", "COL_Shaft", "COL_Blade"],
    "Flashlight": ["LIGHT"],
    "Headlamp": ["LIGHT"],
    "Glowstick": [], "Flare": ["TIP"], "Noisemaker": [],
    "Scanner": ["Screen", "Lamp"],
    "RopeCoil": ["TIP"], "Medkit": [], "MarkerBeacon": ["Lamp"], "Backpack": [], "Battery": [],
    "FoodCan": [], "RabbitMeat": [], "BoarMeat": [], "FalsekinGland": [], "LoreTape": [], "MinerTag": [],
    "OreChunk_Iron": [], "OreChunk_Copper": [], "OreChunk_Crystal": [], "OreChunk_Blackstone": [],
    "OreChunk_Anomalous": [],
}
BUDGET = (150, 1500)


def E(root, notes="", view="iso", cell=0.1, hero=False, shots=None):
    return {"root": root, "notes": notes, "view": view, "cell": cell, "hero": hero, "hero_shots": shots}


def head_shots(mb, group, pad=0.01):
    mn, mx = mb.gb(group, pad)
    return [("side", (mn, mx)), ("iso", (mn, mx)), ("isol", None)]


def root_mesh(mb, name, smooth_angle=40):
    return mb.to_object(name, smooth_angle=smooth_angle)


def col_from(mb, group, name, parent, pad=0.002):
    mn, mx = mb.gb(group, pad)
    return H.col_box(name, parent, mn, mx)


# ============================================================================================
# Pickaxes
# ============================================================================================
def _handle(mb, y_butt, y_top, rx, rz, seed, mat="MNF_WoodHandle", sides=10, group="handle", head_swell=0.2):
    rng = random.Random(seed)
    ts = [0.0, 0.004, 0.012, 0.03, 0.06, 0.12, 0.25, 0.4, 0.55, 0.7, 0.82, 0.91, 0.97, 1.0]
    pts, sc = [], []
    for i, t in enumerate(ts):
        y = lerp(y_butt, y_top, t)
        s = 1.0 + 0.30 * math.exp(-((t - 0.02) / 0.035) ** 2) + head_swell * smoothstep((t - 0.72) / 0.25)
        if i == 0:
            s *= 0.72
        elif i == len(ts) - 1:
            s *= 0.85
        wob = 0.0015 * math.sin(t * 9.0 + seed)
        pts.append((wob + rng.uniform(-0.0004, 0.0004), y, 0.001 * math.sin(t * 5 + seed)))
        sc.append((rz * s, rx * s))
    mb.add(H.sweep(pts, 1.0, sides, scales=sc, up=(0, 0, 1)), mat, group=group)
    return lambda t: (rx * (1.0 + 0.30 * math.exp(-((t - 0.02) / 0.035) ** 2) + head_swell * smoothstep((t - 0.72) / 0.25)),
                      rz * (1.0 + 0.30 * math.exp(-((t - 0.02) / 0.035) ** 2) + head_swell * smoothstep((t - 0.72) / 0.25)))


def _arm(yh, z0, length, curve, w0, w1, h0, h1, sign, steps=8, profile=None, pw=1.0):
    """Pick arm / adze sweep. sign=-1 -> toward -Z (pick), +1 -> toward +Z (adze)."""
    p = H.bezier((0, yh, z0 * sign), (0, yh, sign * (z0 + 0.35 * length)), (0, yh + curve * 0.35, sign * (z0 + 0.8 * length)),
                 (0, yh + curve, sign * (z0 + length)), steps)
    sc = []
    for i in range(len(p)):
        t = i / (len(p) - 1)
        sc.append((lerp(w0, w1, t ** pw), lerp(h0, h1, t ** pw)))
    prof = profile or H.rrect2d(2, 2, 0.45, 1)
    return H.sweep(p, 1.0, scales=sc, profile=prof, up=(1, 0, 0)), p[-1]


def _wrap_bands(mb, ys, rfun, y_butt, y_top, mat, thick=0.0025, width=0.04, seed=1, tilt=9, sides=10):
    rng = random.Random(seed)
    for i, y in enumerate(ys):
        t = (y - y_butt) / (y_top - y_butt)
        rx, rz = rfun(t)
        r0 = rx + 0.0004
        prof = [(r0, -width / 2), (r0 + thick, -width / 2 + 0.004), (r0 + thick * 1.1, width / 2 - 0.004), (r0 + 0.0002, width / 2)]
        band = H.lathe(prof, sides, cap_start=False, cap_end=False, scale_xy=(1, rz / rx))
        H.jitter(band, 0.0006, seed + i)
        mb.add(band, mat, xf((0, y, 0), (0, 0, (tilt if i % 2 else -tilt) + rng.uniform(-3, 3))) @ RX90, group="handle")


def _ring_on_handle(mb, y, rfun, y_butt, y_top, mat, r_wire=0.0025, sides=12, nv=4, extra=0.0008):
    t = (y - y_butt) / (y_top - y_butt)
    rx, rz = rfun(t)
    tor = H.torus(rx + r_wire * 0.7 + extra, r_wire, sides, nv, scale=(1, (rz + r_wire * 0.7) / (rx + r_wire * 0.7)))
    mb.add(tor, mat, xf((0, y, 0)) @ RX90, group="handle")


def build_pickaxe_t1():
    mb = MB(TILE)
    L = 0.75
    y_butt, y_top = 0.12, -(L - 0.12)
    rx, rz = 0.0128, 0.0172
    rf = _handle(mb, y_butt, y_top, rx, rz, seed=3)
    yh = y_top + 0.042
    rust = "MNF_MetalRusted"
    # forged eye boss
    eye = H.box(0.05, 0.068, 0.082, 0.011, 2)
    H.jitter(eye, 0.0011, 11)
    mb.add(eye, rust, xf((0, yh, 0)), group="head")
    # pick (tip toward -Z, curving back toward the grip)
    arm, tip = _arm(yh, 0.03, 0.205, 0.055, 0.0205, 0.0028, 0.024, 0.0032, -1, steps=8, pw=0.85)
    H.jitter(arm, 0.0009, 12)
    mb.add(arm, rust, group="head")
    # adze end, chisel-flat and slightly chipped
    adze, _ = _arm(yh, 0.03, 0.15, 0.04, 0.021, 0.027, 0.024, 0.0045, +1, steps=6, pw=1.0)
    H.jitter(adze, 0.0009, 13)
    mb.add(adze, rust, group="head")
    # wedge + nail through end grain
    mb.add(H.box(0.004, 0.006, 0.03, 0.001), rust, xf((0.0, y_top - 0.002, 0)), group="head")
    mb.add(H.bolt(0.003, 0.003, washer=False, n=6), rust, xf((0.006, y_top - 0.002, 0.008), (90, 0, 0)), group="head")
    # iron ferrule under the head, twine binding
    _ring_on_handle(mb, yh + 0.05, rf, y_butt, y_top, rust, r_wire=0.003, nv=4, extra=0.0)
    for k in range(2):
        _ring_on_handle(mb, yh + 0.072 + k * 0.0056, rf, y_butt, y_top, "MNF_Rope", r_wire=0.0028, sides=10, nv=4, extra=0.0)
    # rag-wrapped grip + a dangling rag tail
    _wrap_bands(mb, [0.08, 0.046, 0.012, -0.022, -0.056, -0.09], rf, y_butt, y_top, "MNF_FabricCanvas",
                thick=0.003, width=0.037, seed=5)
    tail = H.sweep([(0.012, -0.112, -0.012), (0.017, -0.108, -0.035), (0.016, -0.1, -0.06), (0.022, -0.094, -0.082)], 1.0,
                   profile=[(-0.011, -0.0008), (0.011, -0.0008), (0.011, 0.0008), (-0.011, 0.0008)], up=(1, 0, 0), twist=0.25)
    H.jitter(tail, 0.0008, 7)
    mb.add(tail, "MNF_FabricCanvas", group="handle")
    root = root_mesh(mb, "Pickaxe_T1")
    col_from(mb, "handle", "COL_Handle", root)
    col_from(mb, "head", "COL_Head", root)
    H.empty("TIP", root, tip, (90, 0, 0))
    return E(root, "Rusty Pick. Handle 0.75 m, grip (pivot) 0.12 m from the butt. TIP at the pick point, its -Y axis "
                   "points along the strike direction (-Z of the tool).", view="side", hero=True,
             shots=head_shots(mb, "head"))


def build_pickaxe_t2():
    mb = MB(TILE)
    L = 0.8
    y_butt, y_top = 0.12, -(L - 0.12)
    rx, rz = 0.0128, 0.0172
    rf = _handle(mb, y_butt, y_top, rx, rz, seed=21, head_swell=0.15)
    yh = y_top + 0.044
    steel = "MNF_MetalBare"
    oct8 = H.rrect2d(2, 2, 0.5, 1)
    mb.add(H.box(0.048, 0.07, 0.096, 0.006, 1), steel, xf((0, yh, 0)), group="head")
    arm, tip = _arm(yh, 0.034, 0.23, 0.034, 0.0195, 0.0016, 0.0225, 0.0022, -1, steps=7, profile=oct8, pw=0.9)
    mb.add(arm, steel, group="head", flat=True)
    adze, _ = _arm(yh, 0.034, 0.165, 0.026, 0.0195, 0.024, 0.0225, 0.0028, +1, steps=5, profile=oct8, pw=1.0)
    mb.add(adze, steel, group="head", flat=True)
    mb.add(H.box(0.02, 0.004, 0.03, 0.0012, 1), steel, xf((0, y_top - 0.001, 0)), group="head")
    # yellow painted collar clamped round the eye, with through bolts
    yel = "MNF_MetalPainted_Yellow"
    mb.add(H.box(0.058, 0.084, 0.05, 0.005, 1), yel, xf((0, yh + 0.001, 0)), group="head")
    mb.add(H.box(0.06, 0.03, 0.02, 0.004, 1), yel, xf((0, yh + 0.045, 0)), group="head")
    for sx in (-1, 1):
        for sz in (-1, 1):
            mb.add(H.bolt(0.0045, 0.004, washer=False), steel, H.place((sx * 0.029, yh, sz * 0.013), (sx, 0, 0)), group="head")
    # steel langets down the handle, riveted
    for sz in (-1, 1):
        t0 = (yh + 0.03 - y_butt) / (y_top - y_butt)
        z = sz * (rf(t0)[1] + 0.0016)
        mb.add(H.box(0.013, 0.13, 0.003, 0.001), steel, xf((0, yh + 0.095, z)), group="handle")
        for yy in (yh + 0.07, yh + 0.14):
            mb.add(H.rivet(0.0032, 0.0022), steel, H.place((0, yy, z + sz * 0.0014), (0, 0, sz)), group="handle")
    # ribbed rubber grip sleeve with a flared butt
    prof = [(0.0, -0.124), (0.016, -0.124), (0.0195, -0.119), (0.0195, -0.110)]
    z = -0.105
    k = 0
    while z < 0.115:
        r = 0.0158 if k % 2 == 0 else 0.0168
        prof.append((r, z))
        z += 0.019
        k += 1
    prof += [(0.0152, 0.121), (0.0132, 0.126)]
    grip = H.lathe(prof, 10, cap_end=False, scale_xy=(1.0, 1.28))
    mb.add(grip, "MNF_Rubber", xf((0, 0.0, 0)) @ xf(rot=(-90, 0, 0)), group="handle")
    root = root_mesh(mb, "Pickaxe_T2")
    col_from(mb, "handle", "COL_Handle", root)
    col_from(mb, "head", "COL_Head", root)
    H.empty("TIP", root, tip, (90, 0, 0))
    return E(root, "Tempered Pick. Handle 0.8 m, grip 0.12 m from the butt. Steel head, yellow collar, rubber grip.",
             view="side", hero=True, shots=head_shots(mb, "head"))


def build_pickaxe_t3():
    mb = MB(TILE)
    L = 0.85
    y_butt, y_top = 0.12, -(L - 0.12)
    rx, rz = 0.013, 0.0175
    rf = _handle(mb, y_butt, y_top, rx, rz, seed=37, head_swell=0.12, sides=8)
    yh = y_top + 0.046
    dark = "MNF_Blackstone"
    bare = "MNF_MetalBare"
    hexp = H.circle2d(6, 0)
    # eye block with side crystal sockets and a dorsal fin
    mb.add(H.box(0.05, 0.074, 0.1, 0.008, 1), dark, xf((0, yh, 0)), group="head")
    for sx in (-1, 1):
        mb.add(H.cyl(0.021, 0.007, 8, bevel=0.002), bare, H.place((sx * 0.024, yh, 0), (sx, 0, 0)), group="head")
    arm, tip = _arm(yh, 0.04, 0.25, 0.075, 0.019, 0.0018, 0.023, 0.0022, -1, steps=8, pw=0.8)
    mb.add(arm, lambda f: bare if f.calc_center_median().z < -0.18 else dark, group="head", flat=False)
    # crescent adze
    adze, _ = _arm(yh, 0.04, 0.15, 0.045, 0.019, 0.036, 0.023, 0.0035, +1, steps=5, pw=1.3)
    mb.add(adze, lambda f: bare if f.calc_center_median().z > 0.16 else dark, group="head")
    # resonance crystals poking out of the sockets
    for sx in (-1, 1):
        for k, (a, ln, rr) in enumerate(((0, 0.042, 0.0095), (40, 0.03, 0.0065))):
            dirv = Vector((sx, math.sin(math.radians(a)) * 0.5, math.cos(math.radians(a)) * 0.0 + math.sin(math.radians(a)) * 0.6)).normalized()
            pr = H.prism(rr, ln, 6, tip=0.35, seed=k + (5 if sx > 0 else 9))
            mb.add(pr, "MNF_Crystal", H.place((sx * 0.026, yh, 0), dirv), group="head")
    mb.add(H.box(0.022, 0.004, 0.034, 0.0012, 1), bare, xf((0, y_top - 0.001, 0)), group="head")
    # copper wire wrap round the pick neck and the handle throat
    wire = H.helix(0.0255, 0.04, 4.0, 5, axis_z0=-0.09)
    mb.add(H.sweep(wire, 0.0017, 4), "MNF_OreCopper", xf((0, yh, 0)) @ Matrix.Diagonal((1.0, 1.18, 1, 1)), group="head")
    t0 = (yh + 0.075 - y_butt) / (y_top - y_butt)
    hr = rf(t0)
    wire2 = H.helix(1.0, 0.03, 3.0, 6)
    w2 = H.sweep([Vector((p.x * (hr[0] + 0.0016), p.y * (hr[1] + 0.0016), p.z)) for p in wire2], 0.0016, 4)
    mb.add(w2, "MNF_OreCopper", xf((0, yh + 0.05, 0)) @ RX90, group="handle")
    # steel ferrules + rubber grip
    for y in (yh + 0.105, 0.125 - 0.004):
        _ring_on_handle(mb, y, rf, y_butt, y_top, bare, r_wire=0.0035, sides=8, nv=4, extra=0.0)
    prof = [(0.0, -0.118), (0.0175, -0.118), (0.0185, -0.112)]
    z = -0.1
    k = 0
    while z < 0.11:
        prof.append((0.0158 if k % 2 else 0.0166, z))
        z += 0.03
        k += 1
    prof += [(0.0148, 0.118)]
    mb.add(H.lathe(prof, 10, cap_end=False, scale_xy=(1.0, 1.3)), "MNF_Rubber", xf(rot=(-90, 0, 0)), group="handle")
    root = root_mesh(mb, "Pickaxe_T3")
    col_from(mb, "handle", "COL_Handle", root)
    col_from(mb, "head", "COL_Head", root)
    H.empty("TIP", root, tip, (90, 0, 0))
    return E(root, "Resonance Pick. Handle 0.85 m, grip 0.12 m from the butt. Dark alloy head (MNF_Blackstone) with "
                   "bare-steel edges, luminous crystals (MNF_Crystal) in both eye sockets, copper wire wrap "
                   "(MNF_OreCopper - no copper metal in the catalog).", view="side", hero=True,
             shots=head_shots(mb, "head"))


# ============================================================================================
# Spear
# ============================================================================================
def build_spear():
    mb = MB(TILE)
    rng = random.Random(41)
    y_butt, y_end = 0.45, -0.93
    pts, rad = [], []
    n = 15
    for i in range(n):
        t = i / (n - 1)
        y = lerp(y_butt, y_end, t)
        pts.append((0.004 * math.sin(t * 7.0) + rng.uniform(-0.0008, 0.0008), y, 0.003 * math.sin(t * 4.3 + 1)))
        r = lerp(0.0155, 0.0125, t)
        if i == 0:
            r *= 0.75
        rad.append(r)
    mb.add(H.sweep(pts, 1.0, 8, radii=rad, up=(0, 0, 1)), "MNF_WoodHandle", group="shaft")
    # split-end flare + blade
    blade_out = [(0.0075, -0.88), (0.0085, -0.965), (0.026, -0.985), (0.0305, -1.01), (0.027, -1.05), (0.017, -1.1),
                 (0.0, -1.165), (-0.015, -1.105), (-0.022, -1.07), (-0.017, -1.06), (-0.025, -1.035), (-0.029, -1.005),
                 (-0.025, -0.984), (-0.0085, -0.965), (-0.0075, -0.88)]
    bl = H.blade_poly(blade_out, 0.0055, grind=0.0085, tile=0.3)
    mb.add(bl, lambda f: "MNF_MetalRusted" if abs(f.normal.z) > 0.97 else "MNF_MetalBare", group="blade")
    # rivet hole patch (scrap origin) - a rusty rivet on the blade
    mb.add(H.rivet(0.0042, 0.0018), "MNF_MetalRusted", xf((0.008, -1.0, 0.0026)), group="blade")
    mb.add(H.rivet(0.0042, 0.0018), "MNF_MetalRusted", xf((0.008, -1.0, -0.0026), (180, 0, 0)), group="blade")
    # rope lashing over the split end
    for k, (z0, ln, turns) in enumerate(((-0.875, 0.09, 7.0),)):
        hp = H.helix(0.0158, ln, turns, 7, axis_z0=0.0)
        lash = H.sweep(hp, 0.0029, 4)
        mb.add(lash, "MNF_Rope", xf((0, -0.858, 0)) @ RX90, group="shaft")
    # cross lashing over the blade shoulder
    for sx in (-1, 1):
        p = [(sx * 0.013, -0.95, 0.011), (sx * 0.004, -0.972, 0.0045), (-sx * 0.011, -0.988, 0.0035),
             (-sx * 0.016, -0.975, -0.004), (-sx * 0.007, -0.955, -0.011)]
        mb.add(H.sweep(p, 0.0024, 4), "MNF_Rope", group="shaft")
    # rag grip wrap at the hand position and a cord around the butt
    rng2 = random.Random(9)
    for i, y in enumerate((0.07, 0.04, 0.01, -0.02, -0.05, -0.08)):
        r0 = 0.0152 - (y_butt - y) / (y_butt - y_end) * 0.003 + 0.0007
        band = H.lathe([(r0, -0.018), (r0 + 0.0028, -0.014), (r0 + 0.0028, 0.014), (r0 + 0.0003, 0.018)], 9,
                       cap_start=False, cap_end=False)
        H.jitter(band, 0.0005, 30 + i)
        mb.add(band, "MNF_FabricCanvas", xf((0, y, 0), (0, 0, (8 if i % 2 else -8) + rng2.uniform(-3, 3))) @ RX90, group="shaft")
    for k in range(3):
        mb.add(H.torus(0.0128, 0.0022, 10, 4), "MNF_Rope", xf((0, 0.43 - k * 0.005, 0)) @ RX90, group="shaft")
    root = root_mesh(mb, "Spear")
    col_from(mb, "shaft", "COL_Shaft", root)
    col_from(mb, "blade", "COL_Blade", root)
    H.empty("TIP", root, (0, -1.165, 0))
    return E(root, "Improvised spear, 1.6 m. Grip (pivot) 0.45 m from the butt. TIP at the blade point (-Y). "
                   "Blade lies flat in the XY plane.", view="top", hero=True,
             shots=[("iso", mb.gb("blade", 0.03)), ("isol", None)])


# ============================================================================================
# Flashlight / Headlamp / Glowstick / Flare
# ============================================================================================
def build_flashlight():
    mb = MB(TILE)
    yel, rub = "MNF_Plastic_Yellow", "MNF_Rubber"
    # built along +Z (tail z=-0.1 .. lens z=+0.14), then turned to -Y
    parts = []
    tail = H.lathe([(0, -0.1), (0.012, -0.1), (0.0165, -0.0975), (0.0185, -0.093), (0.0185, -0.078), (0.0172, -0.074)], 14,
                   cap_end=False)
    parts.append((tail, rub))
    body = H.lathe([(0.0168, -0.076), (0.0168, -0.05), (0.0168, 0.04), (0.0172, 0.056), (0.022, 0.07), (0.029, 0.092),
                    (0.0315, 0.1), (0.0315, 0.127), (0.0296, 0.13)], 8, cap_start=False, cap_end=False, phase=math.pi / 8)
    parts.append((body, yel))
    prof = [(0.0172, -0.048)]
    z = -0.044
    k = 0
    while z < 0.034:
        prof.append((0.0186 if k % 2 == 0 else 0.0178, z))
        z += 0.0065
        k += 1
    prof.append((0.0172, 0.036))
    parts.append((H.lathe(prof, 14, cap_start=False, cap_end=False), rub))
    bezel = H.lathe([(0.0298, 0.125), (0.0336, 0.126), (0.0338, 0.137), (0.031, 0.1415), (0.0272, 0.1405), (0.0268, 0.137)],
                    16, cap_start=False, cap_end=False)
    parts.append((bezel, rub))
    lens = H.cyl(0.0272, 0.0016, 16, z0=0.1365)
    parts.append((lens, "MNF_Glass"))
    refl = H.lathe([(0.0268, 0.1355), (0.016, 0.127), (0.0075, 0.118)], 16, cap_start=False, cap_end=False)
    parts.append((refl, "MNF_MetalBare"))
    # switch, head screws, lanyard loop
    parts.append((H.box(0.012, 0.007, 0.022, 0.0025, 2, center=(0, 0.0188, 0.05)), rub))
    parts.append((H.box(0.018, 0.004, 0.03, 0.0015, 1, center=(0, 0.0172, 0.05)), yel))
    for a in (45, 135, 225, 315):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        parts.append((H.transform(H.cyl(0.0024, 0.0016, 6, flat=True), H.place((ca * 0.0305, sa * 0.0305, 0.114), (ca, sa, 0))),
                      "MNF_MetalBare"))
    loop = H.torus(0.007, 0.0018, 10, 4)
    parts.append((H.transform(loop, xf((0, 0, -0.106), (90, 0, 0))), "MNF_MetalBare"))
    for p, m in parts:
        mb.add(p, m, RX90)
    root = root_mesh(mb, "Flashlight")
    bm = MB(TILE)
    bm.add(H.uvsphere(0.0055, 10, 6), "MNF_BulbWarm", RX90 @ xf((0, 0, 0.12)))
    bulb = bm.to_object("Bulb", root, pivot=RX90 @ Vector((0, 0, 0.12)))
    H.empty("LIGHT", root, (0, -0.142, 0))
    return E(root, "Chunky industrial torch, 0.24 m. Pivot at the grip ring centre. LIGHT at the lens facing -Y. "
                   "Extra child `Bulb` (MNF_BulbWarm) so the bulb can be switched.", view="iso", hero=True)


def build_headlamp():
    mb = MB(TILE)
    a, b = 0.081, 0.099
    # elastic head band (horizontal ellipse round the head), flat profile
    pts = [Vector((a * math.cos(TAU * i / 24 - math.pi / 2), b * math.sin(TAU * i / 24 - math.pi / 2), 0)) for i in range(24)]
    rect = [(-1.0, -0.12), (1.0, -0.12), (1.0, 0.12), (-1.0, 0.12)]
    mb.add(H.sweep(pts, 0.0145, profile=rect, closed=True, up=(0, 0, 1)), "MNF_FabricCanvas")
    # top strap over the crown
    arc = [Vector((a * 1.005 * math.cos(math.pi * i / 12), 0.005, 0.0 + 0.108 * math.sin(math.pi * i / 12))) for i in range(13)]
    mb.add(H.sweep(arc, 0.011, profile=[(-1.0, -0.13), (1.0, -0.13), (1.0, 0.13), (-1.0, 0.13)], up=(0, 1, 0)), "MNF_FabricCanvas")
    # sliders/buckles
    mb.add(H.box(0.03, 0.006, 0.034, 0.0015, 1), "MNF_Plastic_Black", xf((0, b + 0.003, 0)))
    mb.add(H.box(0.026, 0.03, 0.006, 0.0015, 1), "MNF_Plastic_Black", xf((0, 0.005, 0.111)))
    # lamp: curved back plate, tilt bracket, housing, lens
    mb.add(H.box(0.07, 0.006, 0.036, 0.003, 2), "MNF_Plastic_Black", xf((0, -b - 0.004, 0)))
    for sx in (-1, 1):
        mb.add(H.box(0.006, 0.02, 0.026, 0.002, 1), "MNF_Plastic_Black", xf((sx * 0.031, -b - 0.016, 0.0)))
        mb.add(H.cyl(0.0075, 0.005, 10, bevel=0.0015), "MNF_Plastic_Gray", H.place((sx * 0.033, -b - 0.022, 0.0), (sx, 0, 0)))
    hy = -b - 0.034
    mb.add(H.box(0.054, 0.036, 0.038, 0.007, 2), "MNF_Plastic_Yellow", xf((0, hy, 0.0)))
    bez = H.lathe([(0.0145, 0), (0.0165, 0.001), (0.0168, 0.007), (0.0145, 0.0085), (0.0128, 0.0075)], 14,
                  cap_start=False, cap_end=False)
    mb.add(bez, "MNF_Plastic_Black", RX90 @ xf((0, 0, -hy + 0.017)))
    mb.add(H.cyl(0.0129, 0.001, 14), "MNF_Glass", RX90 @ xf((0, 0, -hy + 0.0228)))
    mb.add(H.lathe([(0.0128, 0.022), (0.006, 0.014)], 14, cap_start=False, cap_end=False), "MNF_MetalBare",
           RX90 @ xf((0, 0, -hy)))
    mb.add(H.box(0.012, 0.01, 0.005, 0.002, 1), "MNF_Rubber", xf((0.012, hy + 0.004, 0.0205)))
    root = root_mesh(mb, "Headlamp")
    bb = MB(TILE)
    bb.add(H.uvsphere(0.0045, 8, 6), "MNF_BulbWarm", xf((0, hy - 0.012, 0)))
    bb.to_object("Bulb", root, pivot=(0, hy - 0.012, 0))
    H.empty("LIGHT", root, (0, hy - 0.026, 0))
    return E(root, "Headlamp on an elastic strap. Pivot at the strap (head) centre; lamp at -Y. LIGHT at the lens facing -Y. "
                   "Extra child `Bulb`.", view="iso")


TAU = math.tau


def build_glowstick():
    mb = MB(TILE)
    prof = [(0.0, -0.066), (0.005, -0.0655), (0.0072, -0.062)]
    for k in range(9):
        prof.append((0.0072 if k % 2 == 0 else 0.0069, -0.05 + k * 0.0125))
    prof += [(0.0072, 0.062), (0.005, 0.0655), (0.0, 0.066)]
    mb.add(H.lathe(prof, 12), "MNF_BulbGreen", RX90)
    for s in (-1, 1):
        cap = H.lathe([(0.0, 0), (0.0085, 0), (0.0088, 0.002), (0.0088, 0.009), (0.0075, 0.012), (0.0, 0.0125)], 12)
        mb.add(cap, "MNF_Plastic_Gray", RX90 @ xf((0, 0, s * 0.06), (0 if s > 0 else 180, 0, 0)))
    mb.add(H.torus(0.005, 0.0016, 10, 4), "MNF_Plastic_Gray", xf((0, -0.0775, 0), (0, 90, 0)))
    cord = H.catenary((0, -0.081, 0.002), (0.0, -0.081, -0.002), 0.0)
    loop = [Vector((0.0, -0.081 - 0.045 * math.sin(math.pi * i / 14) ** 0.8, 0.012 * math.sin(TAU * i / 14))) for i in range(15)]
    mb.add(H.sweep(loop, 0.0011, 4, closed=True), "MNF_Rope")
    root = root_mesh(mb, "Glowstick")
    return E(root, "Glowstick 0.15 m along Y (plus lanyard loop at -Y). Pivot at centre.", view="iso")


def build_flare():
    mb = MB(TILE)
    body = H.lathe([(0.0, -0.118), (0.0128, -0.118), (0.014, -0.115), (0.014, 0.088)], 14, cap_end=False)
    mb.add(body, "MNF_Plastic_Orange", RX90)
    mb.add(H.lathe([(0.0144, -0.06), (0.0146, -0.058), (0.0146, 0.05), (0.0144, 0.052)], 14, cap_start=False, cap_end=False),
           "MNF_Paper", RX90)
    cap = H.lathe([(0.0145, 0.084), (0.0166, 0.085), (0.0168, 0.12), (0.0155, 0.1255), (0.0, 0.1265)], 14, cap_start=False)
    mb.add(cap, "MNF_Plastic_Black", RX90)
    mb.add(H.cyl(0.0105, 0.0012, 14, z0=0.1262), "MNF_Paper", RX90)
    # folded wire stand at the back end
    stand = [(0.0, 0.118, 0.006), (0.0, 0.122, 0.006), (0.0, 0.123, -0.004), (0.0, 0.118, -0.012), (0.0, 0.1, -0.015)]
    mb.add(H.sweep(stand, 0.0011, 4), "MNF_MetalBare")
    mb.add(H.cyl(0.006, 0.004, 8, z0=-0.122), "MNF_Plastic_Black", RX90)
    root = root_mesh(mb, "Flare")
    H.empty("TIP", root, (0, -0.1275, 0))
    return E(root, "Road flare 0.25 m along Y, striker cap at the burning end (-Y). Pivot at centre (grip).", view="iso")


# ============================================================================================
# Noisemaker
# ============================================================================================
def build_noisemaker():
    mb = MB(TILE)
    r = 0.038
    prof = [(0.0, -0.06), (0.034, -0.06), (0.0375, -0.058), (0.0385, -0.054), (0.0372, -0.05)]
    for zb in (-0.025, 0.025):
        prof += [(0.0372, zb - 0.005), (0.0382, zb), (0.0372, zb + 0.005)]
    prof += [(0.0372, 0.052), (0.0388, 0.056), (0.0385, 0.06)]
    can = H.lathe(prof, 14, cap_end=False)
    H.dent(can, (0.03, -0.022, 0.012), 0.025, 0.006)
    mb.add(can, "MNF_MetalBare")
    lid = H.lathe([(0.0385, 0.06), (0.034, 0.059), (0.033, 0.055), (0.012, 0.056), (0.0, 0.054)], 14, cap_start=False)
    for v in lid.verts:
        if v.co.x > 0.0:
            v.co.z += v.co.x * 0.14
    lid.normal_update()
    mb.add(lid, "MNF_MetalRusted")
    # bolts jammed under the bent lid edge
    rng = random.Random(4)
    for k in range(4):
        a = math.radians(-25 + k * 20)
        p = Vector((math.cos(a) * 0.031, math.sin(a) * 0.031, 0.066 + k * 0.001))
        d = Vector((math.cos(a), math.sin(a), 1.2 + rng.uniform(-0.3, 0.3)))
        shaft = H.cyl(0.0032, 0.022, 6, z0=-0.016, flat=False)
        H.merge_into(shaft, H.bolt(0.0055, 0.004, washer=False), xf((0, 0, 0.006)))
        mb.add(shaft, "MNF_MetalRusted", H.place(p, d, spin=rng.uniform(0, 60)))
    # duct tape band with a torn flap, and a strip over the lid
    tape = H.lathe([(0.0389, -0.018), (0.0397, -0.017), (0.0397, 0.017), (0.0389, 0.018)], 14, cap_start=False, cap_end=False)
    H.jitter(tape, 0.0004, 3)
    mb.add(tape, "MNF_Plastic_Gray")
    flap = H.sweep([(0.0402, 0.0, 0.0), (0.0412, -0.006, -0.012), (0.0425, -0.009, -0.026)], 1.0,
                   profile=[(-0.0005, -0.016), (0.0005, -0.016), (0.0005, 0.016), (-0.0005, 0.016)], up=(1, 0, 0))
    mb.add(flap, "MNF_Plastic_Gray", xf(rot=(0, 0, 40)))
    strip = H.sweep([(-0.0396, -0.008, 0.028), (-0.0396, -0.008, 0.058), (-0.034, -0.008, 0.0632), (0.0, -0.008, 0.0605),
                     (0.03, -0.008, 0.0655), (0.0398, -0.008, 0.062), (0.0398, -0.008, 0.032)], 1.0,
                    profile=[(-0.013, -0.0005), (0.013, -0.0005), (0.013, 0.0005), (-0.013, 0.0005)], up=(0, 1, 0))
    mb.add(strip, "MNF_Plastic_Gray")
    # wire wound round it twice and twisted into a carry loop
    for ang in (90, 0):
        loopp = []
        for i in range(14):
            t = TAU * i / 14
            x, z = 0.0412 * math.cos(t), 0.064 * math.sin(t)
            z = max(-0.0605, min(z, 0.068))
            loopp.append(xf(rot=(0, 0, ang)) @ Vector((x, 0, z)))
        mb.add(H.sweep(loopp, 0.0011, 4, closed=True), "MNF_MetalBare")
    bail = H.bezier((-0.006, 0, 0.069), (-0.03, 0, 0.115), (0.03, 0, 0.115), (0.006, 0, 0.069), 10)
    mb.add(H.sweep(bail, 0.0016, 5), "MNF_MetalBare")
    twist = H.helix(0.0022, 0.012, 3, 6, axis_z0=0.066)
    mb.add(H.sweep(twist, 0.0011, 4), "MNF_MetalBare")
    root = root_mesh(mb, "Noisemaker")
    return E(root, "Rattle can: tin can of bolts, wired shut and taped. Axis Z, pivot at the can centre.", view="iso")


# ============================================================================================
# Scanner
# ============================================================================================
def build_scanner():
    mb = MB(TILE)
    blk, gry = "MNF_Plastic_Black", "MNF_Plastic_Gray"
    # handle (grip at origin) and main body ahead of it
    mb.add(H.box(0.046, 0.1, 0.03, 0.009, 2), blk, xf((0, 0.005, -0.002)))
    for sx in (-1, 1):
        g = H.box(0.006, 0.075, 0.024, 0.0025, 1)
        mb.add(g, "MNF_Rubber", xf((sx * 0.023, 0.008, -0.002)))
    body_y = -0.085
    mb.add(H.box(0.088, 0.105, 0.042, 0.011, 2), blk, xf((0, body_y, 0.004)))
    # raised screen bezel on top
    mb.add(H.box(0.07, 0.06, 0.006, 0.003, 1), gry, xf((0, body_y + 0.004, 0.026)))
    # yellow corner bumpers
    for sx in (-1, 1):
        for sy in (-1, 1):
            bmp = H.box(0.02, 0.024, 0.046, 0.007, 2)
            mb.add(bmp, "MNF_Plastic_Yellow", xf((sx * 0.039, body_y + sy * 0.046, 0.004)))
    # buttons
    for k, x in enumerate((-0.016, 0.0, 0.016)):
        mb.add(H.cyl(0.0042, 0.003, 8, bevel=0.0012), "MNF_Rubber", xf((x, body_y + 0.043, 0.0245)))
    # sensor head at the front + stubby antenna
    mb.add(H.cyl(0.016, 0.006, 14, bevel=0.0015), "MNF_MetalBare", RX90 @ xf((0, 0, -body_y + 0.052)))
    mb.add(H.cyl(0.012, 0.002, 14), "MNF_Glass", RX90 @ xf((0, 0, -body_y + 0.0575)))
    ap = [(0.03, body_y - 0.04, 0.022), (0.031, body_y - 0.055, 0.03), (0.033, body_y - 0.08, 0.036)]
    ant = H.sweep(ap, 1.0, 8, radii=[0.0055, 0.0045, 0.0032], up=(0, 0, 1))
    mb.add(ant, "MNF_Rubber")
    mb.add(H.cyl(0.006, 0.006, 8, bevel=0.0015), "MNF_Rubber", xf((0.03, body_y - 0.035, 0.018), (-90, 0, 0)))
    mb.add(H.uvsphere(0.0042, 8, 5), "MNF_Plastic_Yellow", xf(ap[-1]))
    # lanyard eye at the butt
    mb.add(H.torus(0.006, 0.0018, 10, 4), blk, xf((0, 0.058, -0.002), (0, 90, 0)))
    root = root_mesh(mb, "Scanner")
    sb = MB(TILE)
    sp = Vector((0, body_y + 0.004, 0.0292))
    sb.add(H.quad(0.058, 0.044, "+Z"), "MNF_Screen", xf(sp))
    sb.to_object("Screen", root, pivot=sp, weighted=False)
    lb = MB(TILE)
    lp = Vector((0.026, body_y - 0.03, 0.0262))
    lb.add(H.lathe([(0.0, 0), (0.0042, 0), (0.0042, 0.001), (0.0034, 0.0032), (0.0, 0.0042)], 10), "MNF_BulbGreen", xf(lp))
    lb.to_object("Lamp", root, pivot=lp)
    return E(root, "Handheld ore scanner. Pivot at the handle; antenna/sensor at -Y. Child `Screen` is a flat 58x44 mm quad "
                   "facing +Z (UV 0..1), `Lamp` indicator (MNF_BulbGreen), both pivoted at their centre.", view="top", hero=True)


# ============================================================================================
# RopeCoil
# ============================================================================================
def build_ropecoil():
    mb = MB(TILE)
    R = 0.118
    c = Vector((0, 0, -R))
    # coil bundle in the XZ plane (axis Y), pivot at the top where it is held
    mb.add(H.torus(R, 0.021, 20, 8, scale=(1.0, 1.0)), "MNF_Rope", xf(c, (90, 0, 0)) @ xf(scale=(1, 1, 1)) @ Matrix.Diagonal((1, 1, 1.25, 1)))
    rng = random.Random(8)
    for k in range(2):
        rr = R + rng.uniform(-0.006, 0.008)
        pts = []
        for i in range(24):
            t = TAU * i / 24
            off = 0.016 * math.sin(t * 2 + k * 2.0)
            pts.append(c + Vector(((rr + 0.016 * (1 if k else -1) * math.cos(t * 3)) * math.cos(t), off + (0.012 if k else -0.012),
                                   (rr + 0.012 * math.sin(t * 2 + k)) * math.sin(t))))
        mb.add(H.sweep(pts, 0.0062, 5, closed=True), "MNF_Rope")
    # two binding wraps round the bundle
    for ang in (35, 145):
        a = math.radians(ang)
        p = c + Vector((R * math.cos(a), 0, R * math.sin(a)))
        tan = Vector((-math.sin(a), 0, math.cos(a)))
        for j in range(2):
            mb.add(H.torus(0.026, 0.0058, 9, 4), "MNF_Rope", H.place(p + tan * (j - 0.5) * 0.0115, tan))
    # free end to the hook
    a0 = math.radians(-70)
    p0 = c + Vector((R * math.cos(a0), 0.02, R * math.sin(a0)))
    tail = H.bezier(p0, p0 + Vector((0.04, -0.03, -0.03)), p0 + Vector((0.03, -0.05, -0.08)), p0 + Vector((0.01, -0.04, -0.11)), 9)
    mb.add(H.sweep(tail, 0.0062, 6), "MNF_Rope")
    mb.add(H.cyl(0.0085, 0.022, 8, bevel=0.002), "MNF_MetalBare", H.place(tail[-1] + Vector((0, 0, 0.004)), (0, 0, -1)))
    # J hook with eye
    hp = tail[-1] + Vector((0, 0, -0.024))
    eye = H.torus(0.009, 0.003, 10, 5)
    mb.add(eye, "MNF_MetalBare", xf(hp + Vector((0, 0, -0.006)), (0, 90, 0)))
    hook_path = [Vector((0, 0, -0.016)), Vector((0, 0, -0.06)), Vector((0.006, 0, -0.08)), Vector((0.022, 0, -0.088)),
                 Vector((0.036, 0, -0.078)), Vector((0.04, 0, -0.06)), Vector((0.036, 0, -0.046))]
    rads = [0.0045, 0.0045, 0.0045, 0.0043, 0.004, 0.0032, 0.0012]
    mb.add(H.sweep([hp + p for p in hook_path], 1.0, 6, radii=rads, up=(0, 1, 0)), "MNF_MetalBare")
    root = root_mesh(mb, "RopeCoil")
    H.empty("TIP", root, hp + hook_path[-1], (90, 0, 0))
    return E(root, "Coiled climbing rope (coil in the XZ plane), pivot at the top of the coil where the hand holds it. "
                   "TIP at the hook point (its -Y axis points up the hook's point direction).", view="front")


# ============================================================================================
# Medkit, MarkerBeacon, Backpack, Battery, FoodCan
# ============================================================================================
def build_medkit():
    mb = MB(TILE)
    red = "MNF_MetalPainted_Red"
    w, d, h = 0.25, 0.085, 0.165
    zc = -0.032 - h / 2
    base = H.box(w, d * 0.62, h, 0.012, 2)
    mb.add(base, red, xf((0, 0.0425 - d * 0.31, zc)))
    lid = H.box(w + 0.003, d * 0.4, h + 0.003, 0.014, 2)
    H.dent(lid, (0.06, -0.02, 0.03), 0.04, 0.004, direction=(0, 1, 0))
    H.dent(lid, (-0.09, -0.02, -0.05), 0.03, 0.003, direction=(0, 1, 0))
    mb.add(lid, red, xf((0, -0.0425 + d * 0.2, zc)))
    # white cross sticker on the lid
    cr = [(-0.015, -0.045), (0.015, -0.045), (0.015, -0.015), (0.045, -0.015), (0.045, 0.015), (0.015, 0.015), (0.015, 0.045),
          (-0.015, 0.045), (-0.015, 0.015), (-0.045, 0.015), (-0.045, -0.015), (-0.015, -0.015)]
    cross = H.extrude_poly(cr, 0.0008)
    mb.add(cross, "MNF_Paper", xf((0, -0.0435 - 0.0, zc), (90, 0, 0)) @ xf((0.0, 0.0, 0.0)))
    # hinge along the bottom, latch, handle on top
    mb.add(H.cyl(0.004, w * 0.86, 8), "MNF_MetalBare", xf((-w * 0.43, -0.018, zc - h / 2 - 0.0005), (0, 90, 0)))
    mb.add(H.box(0.03, 0.008, 0.022, 0.002, 1), "MNF_MetalBare", xf((0, -0.0445, zc + h / 2 - 0.016)))
    mb.add(H.box(0.016, 0.004, 0.012, 0.001, 1), "MNF_MetalBare", xf((0, -0.0465, zc + h / 2 - 0.022)))
    for sx in (-1, 1):
        mb.add(H.box(0.016, 0.02, 0.008, 0.002, 1), "MNF_MetalBare", xf((sx * 0.055, 0.0, -0.034)))
    hp = [(-0.055, 0, -0.03), (-0.052, 0, -0.012), (-0.035, 0, 0.0), (0.035, 0, 0.0), (0.052, 0, -0.012), (0.055, 0, -0.03)]
    mb.add(H.sweep(hp, 0.0032, 6), "MNF_MetalBare")
    mb.add(H.cyl(0.0068, 0.06, 10, bevel=0.003), "MNF_Rubber", xf((-0.03, 0, 0.0), (0, 90, 0)))
    root = root_mesh(mb, "Medkit")
    return E(root, "Dented first-aid tin, 0.25 m wide. Pivot at the carry handle (main grip); box hangs below, cross faces -Y.",
             view="iso")


def build_markerbeacon():
    mb = MB(TILE)
    body = H.lathe([(0.0, -0.036), (0.022, -0.036), (0.027, -0.03), (0.028, 0.03), (0.024, 0.036), (0.0, 0.037)], 12)
    mb.add(body, "MNF_Plastic_Orange")
    mb.add(H.lathe([(0.0285, -0.02), (0.0295, -0.017), (0.0295, 0.017), (0.0285, 0.02)], 12, cap_start=False, cap_end=False),
           "MNF_Rubber")
    mb.add(H.cyl(0.024, 0.006, 12, bevel=0.0015, z0=0.035), "MNF_Plastic_Black")
    spike = H.lathe([(0.0, -0.13), (0.0045, -0.09), (0.0085, -0.05), (0.011, -0.037), (0.0, -0.037)], 8)
    mb.add(spike, "MNF_MetalBare")
    for k in range(3):
        fin = H.extrude_poly([(0.0, 0.0), (0.012, 0.0), (0.0, -0.04)], 0.002, z0=-0.001)
        mb.add(fin, "MNF_MetalBare", xf((0, 0, -0.037), (0, 0, k * 120)) @ xf((0.006, 0, 0), (90, 0, 0)))
    # wire guard over the dome
    for k in range(3):
        arc = [Vector((0.021 * math.cos(math.pi * i / 8), 0, 0.041 + 0.03 * math.sin(math.pi * i / 8))) for i in range(9)]
        mb.add(H.sweep(arc, 0.0012, 4), "MNF_MetalBare", xf(rot=(0, 0, k * 60)))
    mb.add(H.box(0.008, 0.004, 0.012, 0.0015, 1), "MNF_Rubber", xf((0, -0.0285, 0.012)))
    root = root_mesh(mb, "MarkerBeacon")
    lb = MB(TILE)
    lp = Vector((0, 0, 0.041))
    lb.add(H.lathe([(0.0, 0), (0.0175, 0), (0.0175, 0.006), (0.014, 0.017), (0.007, 0.023), (0.0, 0.0245)], 12), "MNF_BulbRed", xf(lp))
    lb.to_object("Lamp", root, pivot=lp)
    return E(root, "Deployable beacon, 0.2 m tall, spike down (-Z). Pivot at the body (grip). Child `Lamp` = red dome, pivot at its base.",
             view="iso")


def build_backpack():
    mb = MB(TILE)
    can = "MNF_FabricCanvas"
    zc = -0.24
    body = H.box(0.33, 0.19, 0.42, 0.055, 2)
    H.displace(body, 0.006, 6.0, 3)
    for v in body.verts:
        v.co.y -= 0.018 * math.cos(v.co.z * 3.0) * (1 if v.co.y < 0 else 0)
    mb.add(body, can, xf((0, 0, zc)))
    # lid flap
    lid = H.box(0.345, 0.205, 0.075, 0.03, 1)
    H.displace(lid, 0.004, 8.0, 5)
    mb.add(lid, can, xf((0, 0.0, -0.06)))
    flap = H.box(0.3, 0.02, 0.15, 0.009, 2)
    for v in flap.verts:
        v.co.y -= 0.012 * (1 - (v.co.x / 0.15) ** 2)
    mb.add(flap, can, xf((0, -0.1, -0.13)))
    # front pocket and side bottle pockets
    pk = H.box(0.22, 0.06, 0.15, 0.022, 1)
    H.displace(pk, 0.003, 9.0, 7)
    mb.add(pk, can, xf((0, -0.112, -0.33)))
    for sx in (-1, 1):
        sp = H.cyl(0.042, 0.17, 8, bevel=0.012)
        H.displace(sp, 0.003, 9, 11)
        mb.add(sp, can, xf((sx * 0.178, -0.01, -0.43), scale=(0.9, 1.0, 1.0)))
    # straps & buckles
    for sx in (-1, 1):
        mb.add(H.box(0.026, 0.006, 0.2, 0.0015, 1), "MNF_Rubber", xf((sx * 0.08, -0.121, -0.19)))
        mb.add(H.box(0.034, 0.008, 0.026, 0.002, 1), "MNF_MetalBare", xf((sx * 0.08, -0.124, -0.28)))
        mb.add(H.box(0.026, 0.004, 0.06, 0.0015, 1), "MNF_Rubber", xf((sx * 0.08, -0.12, -0.32)))
    # shoulder straps on the back (+Y), padded
    for sx in (-1, 1):
        sp = H.bezier((sx * 0.07, 0.1, -0.05), (sx * 0.08, 0.17, -0.12), (sx * 0.1, 0.17, -0.34), (sx * 0.15, 0.1, -0.43), 7)
        mb.add(H.sweep(sp, 1.0, profile=H.rrect2d(0.016, 0.06, 0.006, 1), up=(0, 1, 0)), "MNF_Rubber")
        mb.add(H.box(0.04, 0.008, 0.03, 0.002, 1), "MNF_MetalBare", xf((sx * 0.14, 0.11, -0.41)))
    # top carry loop (pivot)
    loop = H.bezier((-0.035, 0.02, -0.03), (-0.03, 0.02, 0.012), (0.03, 0.02, 0.012), (0.035, 0.02, -0.03), 8)
    mb.add(H.sweep(loop, 1.0, profile=H.rrect2d(0.022, 0.006, 0.002, 1), up=(0, 1, 0)), "MNF_Rubber")
    # bedroll strapped under the pack
    roll = H.lathe([(0.0, -0.17), (0.045, -0.17), (0.052, -0.16), (0.055, 0.16), (0.048, 0.17), (0.0, 0.17)], 12)
    H.displace(roll, 0.003, 10, 13)
    mb.add(roll, "MNF_FabricBlanket", xf((0, -0.01, -0.47), (0, 90, 0)))
    for sx in (-1, 1):
        mb.add(H.torus(0.0565, 0.0035, 10, 4), "MNF_Rubber", xf((sx * 0.1, -0.01, -0.47), (0, 90, 0)))
    root = root_mesh(mb, "Backpack", smooth_angle=55)
    return E(root, "Canvas expedition backpack, 0.5 m. Pivot at the top carry strap; back panel/shoulder straps face +Y, "
                   "front pocket faces -Y.", view="iso")


def build_battery():
    mb = MB(TILE)
    mb.add(H.box(0.052, 0.1, 0.034, 0.006, 2), "MNF_Plastic_Black")
    for sy in (-1, 1):
        mb.add(H.box(0.056, 0.016, 0.038, 0.005, 2), "MNF_Plastic_Yellow", xf((0, sy * 0.044, 0)))
    for k in range(5):
        mb.add(H.box(0.0575, 0.004, 0.026, 0.0012, 1), "MNF_Rubber", xf((0, -0.02 + k * 0.01, 0)))
    mb.add(H.quad(0.04, 0.05, "+Z"), "MNF_Paper", xf((0, 0.0, 0.0172)))
    for sx in (-1, 1):
        mb.add(H.cyl(0.0045, 0.006, 8, bevel=0.0012), "MNF_MetalBare", H.place((sx * 0.013, -0.052, 0.004), (0, -1, 0)))
    mb.add(H.box(0.012, 0.006, 0.01, 0.002, 1), "MNF_Plastic_Yellow", xf((0, 0.055, 0.008)))
    root = root_mesh(mb, "Battery")
    return E(root, "Battery pack 0.1 m, terminals at -Y. Pivot at centre.", view="iso")


def build_foodcan():
    mb = MB(TILE)
    prof = [(0.0, -0.06), (0.031, -0.0595), (0.034, -0.0575), (0.0365, -0.0585), (0.0378, -0.0565), (0.0368, -0.053)]
    for k in range(5):
        zb = -0.04 + k * 0.02
        prof += [(0.0368, zb - 0.004), (0.0362, zb), (0.0368, zb + 0.004)]
    prof += [(0.0368, 0.053), (0.0378, 0.0565), (0.0365, 0.0585), (0.034, 0.0575), (0.033, 0.055), (0.015, 0.0556), (0.012, 0.0545),
             (0.0, 0.0548)]
    can = H.lathe(prof, 16)
    H.dent(can, (0.026, -0.026, 0.03), 0.022, 0.005)
    mb.add(can, "MNF_MetalBare")
    label = H.lathe([(0.0371, -0.045), (0.0374, -0.044), (0.0374, 0.044), (0.0371, 0.045)], 16, cap_start=False, cap_end=False)
    H.dent(label, (0.026, -0.026, 0.03), 0.022, 0.005)
    # torn corner: drop a few verts back onto the can
    for v in label.verts:
        if v.co.z > 0.03 and v.co.x > 0.025 and v.co.y > 0:
            v.co.xy = v.co.xy * 0.985
    mb.add(label, "MNF_Paper")
    # key opener soldered to the lid
    mb.add(H.box(0.04, 0.006, 0.002, 0.0006, 1), "MNF_MetalBare", xf((0.0, 0.01, 0.0565)))
    mb.add(H.torus(0.005, 0.0012, 8, 4), "MNF_MetalBare", xf((0.023, 0.01, 0.0565)))
    root = root_mesh(mb, "FoodCan")
    return E(root, "Ration can 0.12 m tall (axis Z), pivot at centre.", view="iso")


# ============================================================================================
# Meat & organic items
# ============================================================================================
def _blob_sweep(path, radii, n, seed, amp, freq):
    bm = H.sweep(path, 1.0, n, radii=radii, up=(0, 0, 1))
    H.displace(bm, amp, freq, seed)
    return bm


def _muscle(path, radii, n, seed, amp=0.004, freq=(38, 38, 9), flat=(1.0, 0.8)):
    """Sweep a muscle mass and add fibre-like anisotropic noise (fibres run along the path)."""
    bm = H.sweep(path, 1.0, n, radii=radii, up=(0, 0, 1), scales=[flat] * len(path))
    bm.normal_update()
    for v in bm.verts:
        q = Vector((v.co.x * freq[0], v.co.z * freq[1], v.co.y * freq[2]))
        v.co += v.normal * amp * (H.fbm(q, seed, 3) + 0.4 * H.nz(q * 3.1, seed + 1))
    bm.normal_update()
    return bm


def build_rabbitmeat():
    mb = MB(TILE)
    # haunch: layered muscle bundles tapering toward the hock; grip (pivot) on the shank bone
    mb.add(_muscle([(0, -0.112, 0.004), (0, -0.104, 0.006), (0, -0.085, 0.008), (0, -0.06, 0.006), (0, -0.035, 0.003),
                    (0, -0.016, 0.0), (0, -0.002, 0.0)], [0.004, 0.02, 0.031, 0.03, 0.022, 0.011, 0.008], 10, 3), "MNF_Meat")
    mb.add(_muscle([(0.006, -0.1, 0.014), (0.009, -0.08, 0.02), (0.008, -0.055, 0.016), (0.004, -0.03, 0.008)],
                   [0.004, 0.017, 0.015, 0.004], 8, 4, flat=(0.7, 1.0)), "MNF_Meat")
    mb.add(_muscle([(-0.008, -0.098, -0.008), (-0.013, -0.075, -0.012), (-0.011, -0.05, -0.01), (-0.004, -0.028, -0.004)],
                   [0.004, 0.016, 0.014, 0.004], 8, 5, flat=(0.8, 1.0)), "MNF_Meat")
    bone = H.sweep([(0, -0.012, 0), (0, 0.02, -0.001), (0, 0.032, -0.002)], 1.0, 8, radii=[0.0055, 0.0048, 0.0058])
    mb.add(bone, "MNF_Teeth")
    knob = H.uvsphere(0.0082, 8, 6, scale=(1.0, 0.8, 0.85))
    H.displace(knob, 0.0012, 90, 2)
    mb.add(knob, "MNF_Teeth", xf((0, 0.036, -0.002)))
    for sx in (-1, 1):
        mb.add(H.sweep([(sx * 0.005, -0.03, 0.006 * sx), (sx * 0.004, -0.008, 0.004), (sx * 0.0035, 0.012, 0.003)], 0.0015, 4), "MNF_Meat")
    root = root_mesh(mb, "RabbitMeat", smooth_angle=70)
    return E(root, "Skinned rabbit haunch 0.15 m. Pivot at the shank bone (grip); meaty end toward -Y.", view="iso")


def build_boarmeat():
    mb = MB(TILE)
    main = _muscle([(0, -0.168, 0.0), (0, -0.158, 0.0), (0, -0.13, 0.004), (0, -0.09, 0.008), (0, -0.05, 0.006), (0, -0.026, 0.002),
                    (0, -0.012, 0.0)], [0.036, 0.05, 0.06, 0.061, 0.049, 0.03, 0.02], 12, 5, amp=0.006, freq=(22, 22, 6),
                   flat=(0.85, 1.0))
    H.facet_cut(main, [((0.12, -1.0, 0.08), 0.163)])
    mb.add(main, "MNF_Meat")
    # secondary muscle bundles on top / side for a layered silhouette
    for k, (sx, sz, r) in enumerate(((0.03, 0.035, 0.03), (-0.035, 0.02, 0.026), (0.0, -0.04, 0.028))):
        mb.add(_muscle([(sx * 0.6, -0.15, sz * 0.6), (sx, -0.115, sz), (sx * 1.05, -0.075, sz * 1.02), (sx * 0.6, -0.035, sz * 0.6)],
                       [0.008, r, r * 0.9, 0.006], 8, 10 + k, amp=0.004, freq=(26, 26, 7), flat=(1.0, 0.75)), "MNF_Meat")
    # butcher's twine, snapped tight onto the meat surface
    tree = H.bvh_of(mb.bm)
    for y in (-0.12, -0.07):
        ring = []
        for i in range(16):
            a = math.tau * i / 16
            d = Vector((math.cos(a), 0.0, math.sin(a)))
            loc, n = H.surface_hit(tree, (0, y, 0.005), d, far=0.3)
            ring.append(loc + d * 0.0012)
        mb.add(H.sweep(ring, 0.0018, 4, closed=True), "MNF_Rope")
    # bone through the cut: shank grip end (pivot) and marrow at the cut face
    bone = H.sweep([(0, -0.162, 0.004), (0, -0.08, 0.004), (0, 0.0, 0.0), (0, 0.05, -0.002)], 1.0, 8,
                   radii=[0.012, 0.01, 0.0085, 0.0095])
    mb.add(bone, "MNF_Teeth")
    mb.add(H.cyl(0.0065, 0.002, 8), "MNF_Meat", xf((0, -0.1625, 0.004), (90, 0, 0)))
    knob = H.uvsphere(0.015, 10, 6, scale=(1.0, 0.75, 0.85))
    H.displace(knob, 0.002, 60, 2)
    mb.add(knob, "MNF_Teeth", xf((0, 0.058, -0.002)))
    for sx in (-1, 1):
        mb.add(H.uvsphere(0.0085, 8, 5), "MNF_Teeth", xf((sx * 0.007, 0.066, -0.004)))
    root = root_mesh(mb, "BoarMeat", smooth_angle=70)
    return E(root, "Boar leg roast on the bone, tied with twine, 0.25 m. Pivot at the bone shank (grip); cut face toward -Y.",
             view="iso")


def build_falsekingland():
    mb = MB(TILE)
    lobes = [((0.0, 0.0, 0.0), 0.04, (1.0, 1.25, 0.85)), ((0.026, 0.022, 0.006), 0.026, (1.0, 1.0, 0.9)),
             ((-0.023, -0.03, -0.004), 0.025, (1.1, 1.0, 0.85)), ((0.006, 0.04, -0.008), 0.018, (1.0, 1.0, 0.8))]
    organ = H.bmesh.new()
    for i, (c, r, s) in enumerate(lobes):
        bm = H.icosphere(1.0, 3 if i == 0 else 2)
        for v in bm.verts:
            v.co *= 1.0 + 0.16 * H.fbm(v.co * 1.8, 20 + i)
            v.co = Vector((v.co.x * r * s[0], v.co.y * r * s[1], v.co.z * r * s[2])) + Vector(c)
        bm.normal_update()
        H.uv_box(bm, TILE)
        H.merge_into(organ, bm)
    tree = H.bvh_of(organ)
    mb.add(organ, "MNF_Flesh", flat=False)
    rng = random.Random(77)
    starts = [(0.15, -1, 0.3), (-0.4, -0.6, 0.7), (0.7, 0.2, 0.6), (-0.6, 0.5, 0.4), (0.2, 0.7, 0.8), (0.3, -0.3, -0.9)]
    for vb in H.veins(tree, rng, (0, 0, 0), 0.045, starts, steps=8, step_ang=0.2, r0=0.0032, r1=0.0011, branch=1, offset_k=0.75):
        mb.add(vb, "MNF_Anomalous")
    # torn duct stubs
    for d, ln in (((0.2, -1, 0.35), 0.026), ((-0.3, -1, -0.1), 0.018)):
        dirv = Vector(d).normalized()
        p0 = Vector((0, -0.04, 0)) + dirv * 0.005
        tube = H.lathe([(0.008, 0), (0.0075, ln * 0.6), (0.0085, ln), (0.0055, ln * 0.95)], 8, cap_start=False, cap_end=False)
        H.jitter(tube, 0.0008, 5)
        mb.add(tube, "MNF_Flesh", H.place(p0, dirv))
    root = root_mesh(mb, "FalsekinGland", smooth_angle=80)
    return E(root, "Falsekin gland ~0.12 m: lumpy multi-lobed organ (MNF_Flesh) with a branching network of glowing veins "
                   "(MNF_Anomalous). Pivot at centre.", view="iso")


# ============================================================================================
# LoreTape, MinerTag
# ============================================================================================
def build_loretape():
    mb = MB(0.3)
    blk = "MNF_Plastic_Black"
    W, Hh, T = 0.1, 0.0635, 0.012
    mb.add(H.box(W, Hh, T, 0.0016, 1), blk)
    # tape-guide bump along the bottom edge (-Y)
    mb.add(H.extrude_poly([(-0.035, -0.0318), (0.035, -0.0318), (0.03, -0.021), (-0.03, -0.021)], T + 0.0016, bevel=0.0006,
                          z0=-(T + 0.0016) / 2), blk)
    for s in (-1, 1):
        # labels on both faces, window strip in the middle
        z = s * (T / 2 + 0.0002)
        rot = (0, 0, 0) if s > 0 else (180, 0, 0)
        mb.add(H.quad(0.086, 0.016, "+Z"), "MNF_Paper", xf((0, 0.0175, z), rot))
        mb.add(H.quad(0.086, 0.006, "+Z"), "MNF_Paper", xf((0, -0.012, z), rot))
        mb.add(H.quad(0.05, 0.012, "+Z"), "MNF_Glass", xf((0, 0.002, z + s * 0.0001), rot))
        for sx in (-1, 1):
            hub = H.lathe([(0.0062, 0), (0.0062, -0.0006), (0.0036, -0.0012), (0.0, -0.0012)], 8, cap_start=False)
            mb.add(hub, "MNF_Plastic_Gray", xf((sx * 0.021, 0.002, z), rot))
        for (x, y) in ((-0.046, 0.028), (0.046, 0.028), (-0.046, -0.028), (0.046, -0.028), (0, -0.026)):
            mb.add(H.cyl(0.0017, 0.0004, 6, flat=True), "MNF_MetalBare", xf((x, y, z), rot))
    # exposed tape at the bottom opening
    mb.add(H.box(0.05, 0.0008, T * 0.6), "MNF_Rubber", xf((0, -0.0322, 0)))
    root = root_mesh(mb, "LoreTape", smooth_angle=35)
    return E(root, "Cassette tape 0.1 m lying flat in XY (labels on +-Z faces). Pivot at centre.", view="top")


def build_minertag():
    mb = MB(0.2)
    tag = H.extrude_poly(H.rrect2d(0.05, 0.028, 0.006, 2), 0.0018, bevel=0.0005, z0=-0.0009)
    mb.add(tag, "MNF_MetalBare")
    rim = H.outline_strip(H.rrect2d(0.044, 0.022, 0.004, 2), 0.0012, z=0.00095)
    mb.add(rim, "MNF_MetalBare")
    for k, ln in enumerate((0.03, 0.024, 0.027)):
        mb.add(H.box(ln, 0.0022, 0.0004), "MNF_MetalBare", xf((-0.003 + (ln - 0.03) / 2, 0.005 - k * 0.0045, 0.0011)))
    # hole + ball chain
    mb.add(H.torus(0.0026, 0.0007, 8, 4), "MNF_MetalBare", xf((0.0205, 0.0, 0.0)))
    pts = []
    N = 36
    for i in range(N):
        t = TAU * i / N
        pts.append(Vector((0.0205 + 0.045 - 0.045 * math.cos(t), 0.028 * math.sin(t), 0.004 * math.sin(t * 2))))
    radii = [0.0013 if i % 2 == 0 else 0.0006 for i in range(N)]
    mb.add(H.sweep(pts, 1.0, 4, radii=radii, closed=True), "MNF_MetalBare")
    root = root_mesh(mb, "MinerTag", smooth_angle=35)
    return E(root, "Dog tag 50 mm lying flat (embossed face +Z) with a ball-chain loop toward +X. Pivot at the tag centre.",
             view="top", cell=0.02)


# ============================================================================================
# Ore chunks (pivot at centre)
# ============================================================================================
def build_ore_iron():
    mb = MB(0.3)
    body = H.rock(0.047, seed=101, subdiv=3, scale=(1.15, 0.95, 0.82), amp=0.32, freq=1.7)
    mb.add(body, "MNF_OreIron", uv="box")
    rng = random.Random(5)
    for k in range(5):
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.6, 1))).normalized()
        nod = H.rock(0.014 + rng.uniform(0, 0.006), seed=110 + k, subdiv=2, amp=0.25)
        mb.add(nod, "MNF_OreIron", xf(Vector((d.x * 0.045, d.y * 0.038, d.z * 0.033))), uv="box")
    # metallic flecks: tiny cubic crystals
    for k in range(3):
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0, 1))).normalized()
        mb.add(H.box(0.008, 0.008, 0.008, 0.0008), "MNF_MetalBare",
               xf(Vector((d.x * 0.048, d.y * 0.04, d.z * 0.035)), (rng.uniform(0, 90), rng.uniform(0, 90), 0)))
    mb.center()
    root = root_mesh(mb, "OreChunk_Iron", smooth_angle=70)
    return E(root, "Iron ore chunk ~0.11 m: heavy dark lumpy nugget with nodules and metallic cubic flecks.", view="iso", cell=0.05)


def build_ore_copper():
    mb = MB(0.3)
    rng = random.Random(202)
    body = H.rock(0.052, seed=202, subdiv=3, scale=(1.2, 0.9, 0.8), amp=0.1, freq=1.2, facets=7, facet_depth=(0.62, 0.85))
    mb.add(body, "MNF_OreCopper", uv="box", flat=False)
    # protruding vein ridges: thin wedge plates poking out of the fracture faces
    for k in range(3):
        a = rng.uniform(0, TAU)
        pl = H.extrude_poly([(-0.045, 0), (-0.02, 0.009), (0.015, 0.012), (0.045, 0.004), (0.04, -0.003), (-0.04, -0.004)],
                            0.007, bevel=0.0015, z0=-0.0035)
        H.jitter(pl, 0.0012, 30 + k)
        mb.add(pl, "MNF_OreCopper", xf((0, 0, 0.004 * k), (rng.uniform(60, 120), rng.uniform(-20, 20), math.degrees(a))) @
               xf((0, 0.03, 0)), uv="box")
    # patina crust lumps
    for k in range(4):
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0, 1))).normalized()
        cr = H.rock(0.012, seed=220 + k, subdiv=1, scale=(1.4, 1.4, 0.5), amp=0.3)
        mb.add(cr, "MNF_OreCopper", H.place(Vector((d.x * 0.05, d.y * 0.04, d.z * 0.036)), d), uv="box")
    mb.center()
    root = root_mesh(mb, "OreChunk_Copper", smooth_angle=40)
    return E(root, "Copper ore chunk ~0.12 m: fractured, flat-faceted rock with protruding vein ridges and patina crust.",
             view="iso", cell=0.05)


def build_ore_crystal():
    mb = MB(0.3)
    base = H.rock(0.03, seed=303, subdiv=2, scale=(1.3, 1.0, 0.55), amp=0.2, facets=3)
    mb.add(base, "MNF_RockMine", uv="box", flat=True)
    for k, (d, r, h) in enumerate((((0.05, 0.0, 1.0), 0.016, 0.11), ((0.55, -0.25, 0.8), 0.011, 0.075),
                                    ((-0.5, 0.35, 0.75), 0.0095, 0.065), ((-0.1, -0.7, 0.6), 0.0075, 0.045))):
        mb.add(H.prism(r, h, 6, tip=0.25, seed=k), "MNF_Crystal", H.place((d[0] * 0.012, d[1] * 0.012, -0.006), d, spin=k * 17))
    mb.center()
    root = root_mesh(mb, "OreChunk_Crystal", smooth_angle=20)
    return E(root, "Crystal ore chunk ~0.14 m: cluster of 4 hexagonal luminous prisms on a small rock matrix.", view="iso", cell=0.05)


def build_ore_blackstone():
    mb = MB(0.3)
    sh = H.shard(0.14, 0.042, seed=404, n=18, taper=0.12, depth_ratio=0.65)
    m = xf((0, 0, 0), (62, 8, 25))
    mb.add(sh, "MNF_Blackstone", m, uv="box", flat=True)
    sh2 = H.shard(0.075, 0.026, seed=405, n=12, taper=0.1)
    mb.add(sh2, "MNF_Blackstone", xf((0.012, -0.01, 0.0), (35, -40, 0)), uv="box", flat=True)
    sh3 = H.shard(0.06, 0.022, seed=406, n=10, taper=0.15)
    mb.add(sh3, "MNF_Blackstone", xf((-0.01, 0.0, 0.01), (70, 30, 140)), uv="box", flat=True)
    sh4 = H.shard(0.05, 0.02, seed=407, n=10, taper=0.2)
    mb.add(sh4, "MNF_Blackstone", xf((0.0, 0.02, -0.01), (100, -20, 60)), uv="box", flat=True)
    mb.center()
    root = root_mesh(mb, "OreChunk_Blackstone", smooth_angle=10)
    return E(root, "Blackstone chunk ~0.15 m: angular glassy-black shard (flat-shaded facets).", view="iso", cell=0.05)


def build_ore_anomalous():
    mb = MB(0.3)
    rock = H.rock(0.045, seed=505, subdiv=3, scale=(1.05, 1.0, 0.9), amp=0.18, freq=1.4)
    H.facet_cut(rock, [((0.2, -1.0, 0.45), 0.022)])
    mb.add(rock, "MNF_RockMine", uv="box")
    core = H.icosphere(1.0, 3)
    for v in core.verts:
        v.co *= 0.021 * (1.0 + 0.12 * H.fbm(v.co * 2.5, 9))
    core.normal_update()
    mb.add(core, "MNF_Anomalous", xf((0.004, -0.009, 0.004)))
    # glowing veins crawling from the core over the rock
    rng = random.Random(55)
    for k in range(6):
        a = rng.uniform(0, TAU)
        pts = []
        for i in range(7):
            t = i / 6
            th = a + t * rng.uniform(-0.8, 0.8)
            ph = lerp(-0.2, 1.0, t) * (1 if k % 2 else -0.6)
            d = Vector((math.cos(th) * math.cos(ph), 0.0 + math.sin(th) * math.cos(ph), math.sin(ph))).normalized()
            d = (d + Vector((0, -0.8 * (1 - t), 0))).normalized()
            pts.append(d * 0.047 * (1.0 + 0.06 * math.sin(i)))
        mb.add(H.sweep(pts, 1.0, 4, radii=[0.0032 * (1 - 0.75 * i / 6) for i in range(7)]), "MNF_Anomalous")
    mb.center()
    root = root_mesh(mb, "OreChunk_Anomalous", smooth_angle=70)
    return E(root, "Anomalous chunk ~0.1 m: rock shell cracked open on one face showing a rounded glowing core, glowing veins.",
             view="iso", cell=0.05)


BUILDERS = [build_pickaxe_t1, build_pickaxe_t2, build_pickaxe_t3, build_spear, build_flashlight, build_headlamp,
            build_glowstick, build_flare, build_noisemaker, build_scanner, build_ropecoil, build_medkit, build_markerbeacon,
            build_backpack, build_battery, build_foodcan, build_rabbitmeat, build_boarmeat, build_falsekingland,
            build_loretape, build_minertag, build_ore_iron, build_ore_copper, build_ore_crystal, build_ore_blackstone,
            build_ore_anomalous]


def build():
    return [b() for b in BUILDERS]
