"""mnf_sets_organic"""
import numpy as np
import mnf_noise as mn
import mnf_texio as tio
from mnf_registry import texset
from mnf_noise import seed_of, smoothstep, grid
from mnf_sets_hard import crack_mask, scratch_lines, pits, vstreak_field, stain_blobs, rust_colour

TAU = 2 * np.pi


# =========================================================================== WOOD helpers
def grain_field(S, seed, rings=10, wav=1.2, knots=(), along="u", ramp=None, vary=None, cathedral=0):
    """Ring coordinate field for straight-grain timber (contours = growth rings).

    Grain runs along U (lines are horizontal) when along == 'u'. ``knots`` = [(x, y, strength, sx, sy)].
    ``ramp`` optional per-pixel additive (e.g. sawtooth) to break continuity at board joints.
    """
    yy, xx = grid(S)
    if along == "v":
        yy, xx = xx, yy
    vary = rings * 0.06 if vary is None else vary
    f = yy * rings
    f = f + wav * (mn.fbm(S, (1, 2) if along == "u" else (2, 1), 4, seed) - 0.5) * 2.0
    f = f + vary * (mn.fbm(S, (4, 1) if along == "u" else (1, 4), 3, seed + 2) - 0.5) * 2.0
    f = f + 0.12 * (mn.fbm(S, (3, 6) if along == "u" else (6, 3), 3, seed + 1) - 0.5)
    r = mn.rng(seed + 5)
    for _ in range(cathedral):
        kx, ky = r.random(2)
        sx, sy = r.uniform(0.12, 0.3), r.uniform(0.02, 0.05)
        dx = mn.pdelta(xx, kx)
        dy = mn.pdelta(yy, ky)
        f = f + r.uniform(2.0, 5.0) * np.exp(-(dx / sx) ** 2 - (dy / sy) ** 2)
    for (kx, ky, ks, sx, sy) in knots:
        dx = mn.pdelta(xx, kx)
        dy = mn.pdelta(yy, ky)
        g = np.exp(-(dx / sx) ** 2 - (dy / sy) ** 2)
        f = f + ks * g
    if ramp is not None:
        f = f + ramp
    return f


def ring_profile(f, sharp=3.0):
    """0..1 latewood darkness: thin dark line at the end of each ring + soft earlywood ramp."""
    t = np.mod(f, 1.0)
    late = smoothstep(0.62, 0.9, t) * smoothstep(1.0, 0.94, t)
    return np.clip(late ** (2.0 / sharp) * 0.85 + t * 0.15, 0, 1)


def knot_mask(S, knots, along="u", core=0.5):
    yy, xx = grid(S)
    if along == "v":
        yy, xx = xx, yy
    out = np.zeros((S, S))
    for (kx, ky, ks, sx, sy) in knots:
        dx = mn.pdelta(xx, kx)
        dy = mn.pdelta(yy, ky)
        d = np.sqrt((dx / (sx * core)) ** 2 + (dy / (sy * core)) ** 2)
        out = np.maximum(out, smoothstep(1.0, 0.6, d))
    return out


def fibres(S, seed, along="u", f=(160, 3)):
    fq = f if along == "u" else (f[1], f[0])
    return mn.fbm(S, fq, 3, seed, gain=0.6)


def wood_colour(t, palette):
    return tio.gradient_map(np.clip(t, 0, 1), palette)


def random_knots(r, n, sx=(0.02, 0.05), ratio=(0.3, 0.55), strength=(4.0, 9.0), yband=None):
    out = []
    for _ in range(n):
        x = r.random()
        y = r.random() if yband is None else r.uniform(*yband)
        a = r.uniform(*sx)
        out.append((x, y, r.uniform(*strength) * (1 if r.random() < 0.5 else -1), a, a * r.uniform(*ratio)))
    return out


def boards(S, seed, n_boards, gap_px=2.0, joints=True, pal=None, rings=(14, 22), knots_per=(0, 2),
           wav=1.0, weather=0.5):
    """Horizontal boards stacked along V, one butt joint per board per repeat.

    Returns dict with albedo base, height, gap mask, board id, joint mask, knot mask, ring field.
    """
    yy, xx = grid(S)
    r = mn.rng(seed)
    yb = yy + 0.5 / n_boards                          # keep board gaps away from the tile edge
    bid = np.floor(yb * n_boards).astype(int) % n_boards
    by = np.mod(yb * n_boards, 1.0)                   # 0..1 inside board (top -> bottom)
    bh_px = S / n_boards
    gap = smoothstep(gap_px / bh_px, 0.0, by) + smoothstep(1 - gap_px / bh_px, 1.0, by)
    gap = np.clip(gap, 0, 1)
    ring = np.zeros((S, S))
    tone = np.zeros((S, S))
    knots = np.zeros((S, S))
    joint = np.zeros((S, S))
    endshade = np.zeros((S, S))
    for b in range(n_boards):
        jx = r.uniform(0.08, 0.92)
        kn = []
        for _ in range(int(r.integers(knots_per[0], knots_per[1] + 1))):
            a = r.uniform(0.015, 0.04)
            kn.append((r.random(), (b + r.uniform(0.25, 0.75) - 0.5) / n_boards, r.uniform(4.0, 9.0) * r.choice([-1, 1]),
                       a, a * r.uniform(0.3, 0.5)))
        saw = np.mod(xx - jx, 1.0) if joints else None
        ramp = saw * r.uniform(2.0, 6.0) if joints else None
        f = grain_field(S, seed_of(seed, "b", b), int(r.integers(*rings)), wav * r.uniform(0.6, 1.4), kn,
                        ramp=ramp, cathedral=int(r.integers(0, 3)))
        m = bid == b
        ring[m] = f[m]
        tval = r.random()
        if joints:
            tone_b = tval + 0.08 * (saw - 0.5)
        else:
            tone_b = np.full((S, S), tval)
        tone[m] = tone_b[m]
        km = knot_mask(S, kn)
        knots[m] = km[m]
        if joints:
            dj = np.abs(mn.pdelta(xx, jx)) * S
            jm = smoothstep(gap_px * 0.9, 0.0, dj)
            joint[m] = jm[m]
            endshade[m] = smoothstep(18.0, 0.0, dj)[m]
    return dict(ring=ring, tone=tone, gap=gap, joint=joint, knots=knots, bid=bid, by=by, endshade=endshade)


def wood_finish(S, sd, B, pal, weather=0.4, dirt_amt=0.4, nstrength=7.0, base_smooth=0.25, grey=None):
    late = ring_profile(B["ring"])
    fib = fibres(S, seed_of(sd, "fib"))
    fib2 = fibres(S, seed_of(sd, "fib2"), f=(64, 2))
    macro = mn.fbm(S, 3, 5, seed_of(sd, "macro"))
    t = 0.5 * (1 - late) + 0.25 * fib + 0.25 * B["tone"]
    alb = wood_colour(t, pal)
    alb = alb * (1 - 0.35 * B["knots"])[..., None]
    alb = alb * (1 - 0.18 * B["endshade"])[..., None]
    if grey is not None:
        g = np.clip(weather * (0.6 + 0.8 * macro) * (0.7 + 0.6 * fib2), 0, 1)
        alb = tio.mix(alb, tio.desaturate(alb, 0.8) * 0.9 + np.array(grey) / 255.0 * 0.25, g * 0.6)
    dirt = smoothstep(0.3, 1.0, 0.7 * mn.warped_fbm(S, 4, 5, seed_of(sd, "dirt"), warp_amt=0.08)
                      + 0.3 * mn.fbm(S, (24, 6), 3, seed_of(sd, "dirtb")))
    alb = alb * (1 - dirt_amt * 0.35 * dirt)[..., None]
    crevice = np.clip(B["gap"] + B["joint"], 0, 1)
    alb = tio.mix(alb, tio.rgb(28, 22, 18), crevice * 0.9)
    h = 0.6 + 0.05 * late + 0.06 * (fib - 0.5) + 0.03 * (fib2 - 0.5) - 0.06 * B["knots"] * 0 - 0.5 * crevice
    h = h + 0.04 * B["knots"]
    rounding = smoothstep(0.0, 0.08, B["by"]) * smoothstep(1.0, 0.92, B["by"])
    h = h * (0.85 + 0.15 * rounding)
    h = np.clip(h, 0, 1)
    ao = mn.ambient_occlusion(h, (2, 5, 10), 1.8)
    alb = alb * (0.7 + 0.3 * ao)[..., None]
    smooth = np.clip(base_smooth + 0.08 * (fib - 0.5) - 0.1 * dirt + 0.05 * late, 0.03, 0.9)
    return alb, h, smooth, dict(late=late, fib=fib, dirt=dirt, macro=macro)


# =========================================================================== WOOD sets
@texset("wood_planks", 2.0, notes="Weathered grey-brown floor/wall planks (6 boards per repeat along V, grain along U),"
        " staggered butt joints, knots, nail holes, dirt in the gaps.")
def wood_planks(S):
    sd = "wood_planks"
    B = boards(S, seed_of(sd, "b"), 6, 2.2, True, rings=(80, 120), knots_per=(0, 2), wav=2.0)
    pal = [(0, (58, 44, 32)), (0.35, (86, 68, 50)), (0.7, (112, 92, 70)), (1, (128, 108, 84))]
    alb, h, smooth, X = wood_finish(S, sd, B, pal, weather=0.6, dirt_amt=0.8, grey=(120, 116, 108))
    yy, xx = grid(S)
    r = mn.rng(seed_of(sd, "nails"))
    nails = np.zeros((S, S))
    for b in range(6):
        for nx in (r.random(), r.random()):
            for ny in (0.28, 0.72):
                cy = (b + ny - 0.5) / 6
                d = np.sqrt(mn.pdelta(xx, nx) ** 2 + mn.pdelta(yy, cy) ** 2) * S
                nails = np.maximum(nails, smoothstep(3.2, 1.8, d))
    rust_halo = mn.blur(nails, 3.0) * 2.0
    alb = tio.mix(alb, tio.rgb(70, 46, 32), np.clip(rust_halo, 0, 1) * 0.5)
    alb = tio.mix(alb, tio.rgb(34, 30, 28), nails)
    h = h - 0.15 * nails
    scr = scratch_lines(S, 160, seed_of(sd, "scr"), (0.02, 0.1), (-0.3, 0.3), (0.6, 1.5), 0.1, value=(0.2, 0.6))
    alb = tio.mix(alb, alb * 1.25, scr * 0.5)
    h = h - 0.03 * scr
    return tio.finish(alb, h, nails * 0.6, smooth, nstrength=7.0, ao_strength=0.5)


@texset("wood_crate", 1.0, notes="Rough-sawn pine crate boards (4 per repeat along V), saw marks, nail heads, "
        "grime; lighter than planks.")
def wood_crate(S):
    sd = "wood_crate"
    B = boards(S, seed_of(sd, "b"), 4, 2.5, False, rings=(40, 64), knots_per=(0, 1), wav=2.0)
    pal = [(0, (96, 72, 46)), (0.35, (128, 100, 68)), (0.7, (152, 124, 88)), (1, (166, 140, 102))]
    alb, h, smooth, X = wood_finish(S, sd, B, pal, weather=0.4, dirt_amt=0.65, grey=(130, 124, 112))
    yy, xx = grid(S)
    # circular saw arcs
    arcs = 0.5 + 0.5 * np.sin(TAU * (36 * xx + 1.6 * np.cos(TAU * yy * 4)))     # circular-saw arcs
    arcs = arcs * (0.5 + 0.5 * mn.fbm(S, 6, 3, seed_of(sd, "arc")))
    alb = alb * (1 - 0.06 * arcs)[..., None]
    h = h + 0.02 * arcs
    nails = np.zeros((S, S))
    for b in range(4):
        for nx in (0.07, 0.93):
            for ny in (0.3, 0.7):
                d = np.sqrt(mn.pdelta(xx, nx) ** 2 + mn.pdelta(yy, (b + ny - 0.5) / 4) ** 2) * S
                nails = np.maximum(nails, np.sqrt(np.clip(1 - (d / 4.5) ** 2, 0, 1)))
    stain = np.clip(mn.blur(nails, 4) * 2.2, 0, 1) * mn.fbm(S, 16, 3, seed_of(sd, "ns"))
    alb = tio.mix(alb, tio.rgb(84, 58, 40), stain * 0.6)
    alb = tio.mix(alb, tio.rgb(70, 68, 66) * (0.7 + 0.5 * nails)[..., None], smoothstep(0.0, 0.2, nails))
    h = np.maximum(h, 0.55 + 0.15 * nails * (nails > 0.01))
    metal = smoothstep(0.0, 0.2, nails) * 0.7
    smooth = np.where(nails > 0.05, 0.35, smooth)
    return tio.finish(alb, h, metal, smooth, nstrength=7.0, ao_strength=0.5)


@texset("wood_rotten", 1.5, notes="Dark wet decaying wood: deep splits along U, punky eroded areas, fungal "
        "staining and mould, glossy wet patches.")
def wood_rotten(S):
    sd = "wood_rotten"
    yy, xx = grid(S)
    r = mn.rng(seed_of(sd, "k"))
    kn = random_knots(r, 2, (0.03, 0.06))
    f = grain_field(S, seed_of(sd, "g"), 56, 3.0, kn, cathedral=2)
    late = ring_profile(f)
    fib = fibres(S, seed_of(sd, "fib"))
    split = mn.worley(S, 70, seed_of(sd, "split"), aspect=(9, 1),
                      warp_px=mn.warp_field(S, 6, 10, seed_of(sd, "sw")))
    splits = smoothstep(0.05, 0.0, split.edge) * smoothstep(0.35, 0.6, mn.fbm(S, 4, 4, seed_of(sd, "sm")))
    splits = np.maximum(splits, smoothstep(0.02, 0.0, np.abs(mn.fbm(S, (2, 12), 4, seed_of(sd, "sl")) - 0.5)) * 0.8)
    punk = smoothstep(0.45, 0.75, mn.warped_fbm(S, 4, 6, seed_of(sd, "punk"), warp_amt=0.1))
    cubic = mn.worley(S, 600, seed_of(sd, "cubic"), aspect=(2, 1))
    cubes = smoothstep(0.05, 0.0, cubic.edge) * smoothstep(0.5, 0.8, punk) * 0.6   # brown-rot cubical cracking
    fung = smoothstep(0.55, 0.8, mn.warped_fbm(S, 6, 5, seed_of(sd, "fung"), warp_amt=0.12))
    mould = smoothstep(0.8, 0.95, mn.fbm(S, 40, 3, seed_of(sd, "mould"))) * smoothstep(0.3, 0.6, fung + punk * 0.5)
    wet = smoothstep(0.4, 0.8, mn.warped_fbm(S, 3, 5, seed_of(sd, "wet"), warp_amt=0.1))
    h = (0.6 + 0.05 * late + 0.1 * (fib - 0.5) - 0.18 * punk * (0.6 + 0.8 * mn.fbm(S, 24, 3, seed_of(sd, "pd")))
         - 0.45 * splits - 0.1 * cubes)
    h = np.clip(h, 0, 1)
    t = np.clip(0.5 * (1 - late) + 0.3 * fib + 0.2 * mn.fbm(S, 4, 4, seed_of(sd, "tone")), 0, 1)
    alb = tio.gradient_map(t, [(0, (30, 24, 19)), (0.4, (50, 38, 28)), (0.75, (70, 54, 40)), (1, (84, 68, 52))])
    alb = tio.mix(alb, tio.rgb(88, 72, 54), punk * 0.35)
    alb = tio.mix(alb, tio.rgb(40, 44, 30), fung * 0.5)
    alb = tio.mix(alb, tio.rgb(120, 122, 104), mould * 0.6)
    alb = alb * (1 - 0.25 * wet)[..., None]
    alb = tio.mix(alb, tio.rgb(14, 11, 9), np.clip(splits + cubes * 0.6, 0, 1))
    ao = mn.ambient_occlusion(h, (2, 5, 12), 2.0)
    alb = alb * (0.65 + 0.35 * ao)[..., None]
    smooth = np.clip(0.12 + 0.5 * wet * (1 - punk * 0.5) + 0.05 * fib - 0.05 * mould, 0.03, 0.85)
    return tio.finish(alb, h, 0.0, smooth, nstrength=9.0, ao_strength=1.0)


@texset("wood_beam", 2.0, notes="Heavy dark mine timber (grain along U): long drying checks, adze scallops, "
        "oily grime and dust.")
def wood_beam(S):
    sd = "wood_beam"
    yy, xx = grid(S)
    r = mn.rng(seed_of(sd, "k"))
    kn = random_knots(r, 3, (0.025, 0.05))
    f = grain_field(S, seed_of(sd, "g"), 48, 3.5, kn, cathedral=3)
    late = ring_profile(f)
    fib = fibres(S, seed_of(sd, "fib"))
    chk = mn.worley(S, 40, seed_of(sd, "chk"), aspect=(10, 1), warp_px=mn.warp_field(S, 4, 8, seed_of(sd, "cw")))
    checks = smoothstep(0.035, 0.0, chk.edge) * smoothstep(0.45, 0.65, mn.fbm(S, (3, 2), 4, seed_of(sd, "cm")))
    checks_w = mn.blur(checks, 2.5)
    adze_c = mn.worley(S, 60, seed_of(sd, "adze"), aspect=(1, 2.5))
    adze = adze_c.f1 ** 2
    dirt = smoothstep(0.35, 0.9, mn.warped_fbm(S, 3, 5, seed_of(sd, "dirt"), warp_amt=0.1))
    dust = smoothstep(0.6, 0.9, mn.fbm(S, 8, 4, seed_of(sd, "dust")))
    h = 0.6 + 0.04 * late + 0.08 * (fib - 0.5) + 0.12 * (adze - 0.5) - 0.5 * checks - 0.04 * checks_w
    h = np.clip(h, 0, 1)
    t = np.clip(0.55 * (1 - late) + 0.25 * fib + 0.2 * mn.fbm(S, 4, 4, seed_of(sd, "tone")), 0, 1)
    alb = tio.gradient_map(t, [(0, (40, 30, 22)), (0.4, (62, 48, 35)), (0.75, (84, 66, 48)), (1, (98, 80, 60))])
    alb = alb * (1 - 0.35 * knot_mask(S, kn))[..., None]
    alb = alb * (1 - 0.3 * dirt)[..., None]
    alb = tio.mix(alb, tio.rgb(110, 100, 86), dust * 0.25 * smoothstep(0.4, 0.7, h))
    alb = tio.mix(alb, tio.rgb(18, 14, 11), checks * 0.95)
    ao = mn.ambient_occlusion(h, (2, 5, 12), 2.0)
    alb = alb * (0.65 + 0.35 * ao)[..., None]
    smooth = np.clip(0.2 + 0.18 * dirt + 0.05 * fib - 0.12 * dust, 0.03, 0.8)
    return tio.finish(alb, h, 0.0, smooth, nstrength=8.0, ao_strength=1.0)


@texset("wood_handle", 0.5, notes="Hand-worn hardwood tool handle (ash/hickory, grain along U): fine straight grain, "
        "polished grip wear with grime, varnish remnants.")
def wood_handle(S):
    sd = "wood_handle"
    f = grain_field(S, seed_of(sd, "g"), 70, 0.8, [], cathedral=0, vary=2.0)
    late = ring_profile(f, 2.0)
    fib = fibres(S, seed_of(sd, "fib"), f=(256, 4))
    pores = smoothstep(0.75, 0.9, fibres(S, seed_of(sd, "pore"), f=(128, 8))) * late
    grip = smoothstep(0.2, 0.9, mn.warped_fbm(S, 3, 5, seed_of(sd, "grip"), warp_amt=0.12))
    varn = smoothstep(0.4, 0.85, mn.fbm(S, 6, 5, seed_of(sd, "varn"))) * (1 - grip)
    scr = scratch_lines(S, 200, seed_of(sd, "scr"), (0.01, 0.06), (0, np.pi), (0.5, 1.2), 0.2, value=(0.3, 1))
    h = 0.6 + 0.02 * late + 0.03 * (fib - 0.5) - 0.05 * pores - 0.04 * scr + 0.01 * varn
    t = np.clip(0.6 * (1 - late) + 0.25 * fib + 0.15 * mn.fbm(S, 4, 4, seed_of(sd, "tone")), 0, 1)
    alb = tio.gradient_map(t, [(0, (96, 70, 46)), (0.4, (126, 96, 64)), (0.75, (148, 116, 80)), (1, (160, 130, 92))])
    alb = alb * (1 - 0.18 * grip)[..., None]
    alb = tio.mix(alb, alb * np.array([0.88, 0.78, 0.62]), varn * 0.35)
    alb = tio.mix(alb, alb * 0.6, pores * 0.5)
    alb = tio.mix(alb, alb * 1.2, scr * 0.4)
    smooth = np.clip(0.32 + 0.25 * grip + 0.25 * varn - 0.1 * scr + 0.04 * fib, 0.05, 0.85)
    return tio.finish(alb, h, 0.0, smooth, nstrength=5.0, ao_strength=0.4)


# =========================================================================== BARK
@texset("bark_pine", 1.5, notes="Pine bark, tiles vertically along V (and U): deep furrows between flaky "
        "layered plates, reddish exposed scales, grey weathered tops, lichen specks.")
def bark_pine(S):
    sd = "bark_pine"
    wy, wx = mn.warp_field(S, 5, 18, seed_of(sd, "w"))
    wy2, wx2 = mn.warp_field(S, 40, 2.5, seed_of(sd, "w2"), octaves=3)
    c = mn.worley(S, 30, seed_of(sd, "plates"), aspect=(1, 3.2), warp_px=(wy + wy2, wx + wx2))
    r = mn.rng(seed_of(sd, "pt"))
    ptone = c.per_cell(r.random(c.n))
    plate = smoothstep(0.05, 0.38, c.edge * (0.8 + 0.4 * mn.fbm(S, (6, 12), 3, seed_of(sd, "pe"))))
    layers = mn.fbm(S, (6, 10), 5, seed_of(sd, "layers"))
    terr = np.floor(layers * 5 + ptone * 2) / 5.0
    terr_soft = mn.blur(terr, 0.8)
    flake_edge = np.clip(np.abs(mn.gradient(terr)[0]) + np.abs(mn.gradient(terr)[1]), 0, 1) > 0.01
    fib = mn.fbm(S, (8, 96), 3, seed_of(sd, "fib"))
    tilt = c.per_cell(r.normal(0, 0.6, c.n)) * c.dy * 6
    h = plate * (0.45 + 0.25 * terr_soft + 0.12 * ptone + 0.08 * tilt) + 0.07 * (fib - 0.5)
    h = mn.blur(h, 0.6)
    h = mn.norm01(h, 0.2, 99.8)
    fresh = smoothstep(0.5, 0.75, mn.fbm(S, (4, 8), 4, seed_of(sd, "fresh")) * 0.6 + (1 - terr_soft) * 0.4) * plate
    top = tio.gradient_map(np.clip(ptone * 0.5 + layers * 0.5, 0, 1),
                           [(0, (74, 62, 54)), (0.5, (96, 82, 70)), (1, (112, 100, 88))])
    redc = tio.gradient_map(layers, [(0, (98, 56, 38)), (1, (132, 80, 52))])
    alb = tio.mix(top, redc, fresh * 0.75)
    alb = alb * (1 + 0.15 * (fib - 0.5))[..., None]
    furrow = 1 - plate
    alb = tio.mix(alb, tio.rgb(30, 22, 18), smoothstep(0.0, 0.8, furrow))
    alb = tio.mix(alb, alb * 0.7, flake_edge.astype(float) * 0.5 * plate)
    lich = smoothstep(0.82, 0.88, mn.fbm(S, 12, 4, seed_of(sd, "lich"))) * plate
    alb = tio.mix(alb, tio.rgb(112, 122, 100), lich * 0.6)
    ao = mn.ambient_occlusion(h, (2, 6, 14), 2.2)
    alb = alb * (0.6 + 0.4 * ao)[..., None]
    smooth = np.clip(0.14 + 0.06 * fib - 0.05 * lich, 0.03, 0.5)
    return tio.finish(alb, h, 0.0, smooth, nstrength=11.0, ao_strength=1.6)


@texset("bark_dead", 1.5, notes="Pale grey weathered dead wood, twisted grain (tiles along V), long splits, "
        "a few remaining dark bark patches.")
def bark_dead(S):
    sd = "bark_dead"
    wy = np.zeros((S, S))
    wx = (mn.fbm(S, (2, 4), 4, seed_of(sd, "wx")) - 0.5) * 2 * 22
    wy2 = np.zeros((S, S))
    wx2 = (mn.fbm(S, (4, 24), 3, seed_of(sd, "wx2")) - 0.5) * 2 * 2.5
    g = mn.wave_lines(S, 40, 3, warp_px=(wy + wy2, wx + wx2))          # slanted (twisted) grain lines
    g2 = mn.wave_lines(S, 110, 8, warp_px=(wy + wy2 * 0.5, wx + wx2 * 0.5))
    lw = 0.1 + 0.15 * mn.fbm(S, (4, 16), 3, seed_of(sd, "lw"))
    grain = 1 - smoothstep(0.0, lw, np.minimum(g, 1 - g))
    grain = grain * (0.4 + 0.6 * mn.fbm(S, (3, 30), 3, seed_of(sd, "gm")))
    grain2 = (1 - smoothstep(0.0, 0.2, np.minimum(g2, 1 - g2))) * 0.6
    fib = mn.fbm(S, (6, 120), 3, seed_of(sd, "fib"))
    split = smoothstep(0.012, 0.0, np.abs(mn.warp(mn.fbm(S, (2, 10), 4, seed_of(sd, "sp")), wy, wx) - 0.5))
    split = split * smoothstep(0.3, 0.55, mn.fbm(S, (3, 2), 3, seed_of(sd, "spm")))
    bark = smoothstep(0.74, 0.79, mn.warped_fbm(S, (3, 5), 6, seed_of(sd, "bark"), warp_amt=0.08))
    bark_c = mn.worley(S, 300, seed_of(sd, "bc"), aspect=(1, 2))
    bark_h = bark * (0.12 + 0.1 * smoothstep(0.0, 0.2, bark_c.edge))
    h = 0.55 - 0.07 * grain - 0.03 * grain2 + 0.07 * (fib - 0.5) - 0.45 * split + bark_h
    h = np.clip(h, 0, 1)
    t = np.clip(0.55 - 0.3 * grain - 0.1 * grain2 + 0.3 * fib + 0.3 * (mn.fbm(S, 3, 4, seed_of(sd, "tone")) - 0.5), 0, 1)
    alb = tio.gradient_map(t, [(0, (96, 94, 88)), (0.4, (122, 119, 111)), (0.75, (142, 139, 130)),
                               (1, (156, 152, 142))])
    alb = tio.mix(alb, tio.rgb(104, 92, 78), smoothstep(0.5, 0.9, mn.fbm(S, (3, 10), 4, seed_of(sd, "br"))) * 0.35)
    alb = tio.mix(alb, tio.rgb(46, 38, 32) * (0.8 + 0.4 * smoothstep(0.0, 0.2, bark_c.edge))[..., None], bark * 0.9)
    alb = tio.mix(alb, tio.rgb(30, 26, 22), split)
    ao = mn.ambient_occlusion(h, (2, 5, 12), 2.0)
    alb = alb * (0.65 + 0.35 * ao)[..., None]
    smooth = np.clip(0.12 + 0.05 * fib + 0.04 * bark, 0.03, 0.5)
    return tio.finish(alb, h, 0.0, smooth, nstrength=9.0, ao_strength=1.2)


# =========================================================================== GROUND
def _leaf_sprite(r, length, width_ratio, colour, lobed=False):
    """Small dead-leaf sprite: (rgb, alpha, height) arrays, pointing along +x."""
    from PIL import Image, ImageDraw
    ss = 4
    L = int(length)
    W = max(3, int(length * width_ratio))
    pad = 2
    w_img, h_img = (L + 2 * pad) * ss, (W + 2 * pad) * ss
    im = Image.new("L", (w_img, h_img), 0)
    d = ImageDraw.Draw(im)
    pts_top, pts_bot = [], []
    for t in np.linspace(0, 1, 24):
        prof = np.sin(np.pi * t ** 0.8) * (1.0 - 0.15 * t)
        if lobed:
            prof *= 0.8 + 0.2 * np.abs(np.sin(t * np.pi * 5))
        prof *= 1 + (r.random() - 0.5) * 0.1
        x = (pad + t * L) * ss
        pts_top.append((x, (pad + W / 2 - prof * W / 2) * ss))
        pts_bot.append((x, (pad + W / 2 + prof * W / 2) * ss))
    d.polygon(pts_top + pts_bot[::-1], fill=255)
    # holes (decay)
    for _ in range(int(r.integers(0, 3))):
        hx, hy = r.uniform(0.3, 0.8) * L + pad, pad + W / 2 + r.uniform(-0.25, 0.25) * W
        rr = r.uniform(0.5, 1.5)
        d.ellipse([(hx - rr) * ss, (hy - rr) * ss, (hx + rr) * ss, (hy + rr) * ss], fill=0)
    a = mn.downsample(np.asarray(im, dtype=np.float64) / 255.0, ss)
    hh, ww = a.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    mid = np.abs(yy - (pad + W / 2 - 0.5))
    from scipy import ndimage
    dist = ndimage.distance_transform_edt(a > 0.5)
    dome = np.clip(dist / max(1.0, W * 0.35), 0, 1)
    rib = smoothstep(0.9, 0.0, mid) * (xx > pad) * (a > 0.3)
    curl = r.uniform(-0.6, 0.6)
    height = 0.3 + 0.5 * dome * (1 - curl * 0.5) + curl * (1 - dome) * 0.5 + 0.15 * rib
    col = np.ones((hh, ww, 3)) * np.array(colour) / 255.0
    col = col * (0.85 + 0.3 * r.random((hh, ww, 1)) * 0.3)
    col = col * (0.85 + 0.25 * dome[..., None])
    col = tio.mix(col, col * 0.7, rib * 0.6)
    edge_dark = smoothstep(2.0, 0.0, dist) * (a > 0.3)
    col = tio.mix(col, col * 0.6, edge_dark * 0.5)
    return col, a, height * a


def _line_sprite(length, width, angle, colour, taper=0.4):
    from PIL import Image, ImageDraw
    ss = 4
    L = length
    hw = int(np.ceil(L / 2 + width + 2))
    im = Image.new("L", (2 * hw * ss, 2 * hw * ss), 0)
    d = ImageDraw.Draw(im)
    dx, dy = np.cos(angle) * L / 2, np.sin(angle) * L / 2
    c = hw * ss
    d.line([(c - dx * ss, c - dy * ss), (c + dx * ss, c + dy * ss)], fill=255, width=max(1, int(width * ss)))
    a = mn.downsample(np.asarray(im, dtype=np.float64) / 255.0, ss)
    col = np.ones(a.shape + (3,)) * np.array(colour) / 255.0
    return col, a, a * 0.6


def _scatter(canvas_rgb, canvas_h, sprite, cy, cx, tint, lift=0.04):
    col, a, h = sprite
    hh, ww = a.shape
    n = canvas_h.shape[0]
    ys = (np.arange(hh) + int(cy) - hh // 2) % n
    xs = (np.arange(ww) + int(cx) - ww // 2) % n
    ix = np.ix_(ys, xs)
    reg_h = canvas_h[ix]
    m = a > 0.05
    if not m.any():
        return
    base = np.percentile(reg_h[m], 75) + lift
    canvas_h[ix] = reg_h * (1 - a) + (base + h * 0.25) * a
    canvas_rgb[ix] = canvas_rgb[ix] * (1 - a[..., None]) + (col * tint) * a[..., None]


@texset("forest_floor", 2.0, notes="Dark forest soil densely littered with dead leaves, pine needles and twigs; "
        "terrain base layer.")
def forest_floor(S):
    sd = "forest_floor"
    ss = 2
    N = S * ss
    r = mn.rng(seed_of(sd, "scatter"))
    soil_n = mn.fbm(N, 8, 6, seed_of(sd, "soil"))
    grit = mn.fbm(N, 128, 2, seed_of(sd, "grit"))
    rgb = tio.gradient_map(np.clip(0.7 * soil_n + 0.3 * grit, 0, 1),
                           [(0, (30, 24, 19)), (0.5, (46, 37, 28)), (1, (62, 50, 38))])
    hgt = 0.25 + 0.1 * soil_n + 0.04 * grit
    leaf_cols = [(98, 64, 38), (74, 50, 32), (118, 84, 46), (52, 38, 28), (92, 74, 50), (126, 92, 54),
                 (44, 34, 26), (84, 60, 36), (108, 92, 60), (70, 46, 30), (134, 100, 60), (60, 50, 38),
                 (96, 56, 34), (80, 70, 52)]
    needle_cols = [(110, 74, 46), (92, 64, 42), (76, 56, 40), (120, 88, 56), (66, 50, 36)]
    leaves = []
    for i in range(14):
        col = leaf_cols[i % len(leaf_cols)]
        L = r.uniform(36, 80)
        leaves.append(_leaf_sprite(r, L, r.uniform(0.38, 0.62), col, lobed=(i % 4 == 0)))
    from scipy import ndimage

    def rot(sp, ang):
        col, a, h = sp
        col_r = np.stack([ndimage.rotate(col[..., c], ang, reshape=True, order=1) for c in range(3)], -1)
        return np.clip(col_r, 0, 1), np.clip(ndimage.rotate(a, ang, reshape=True, order=1), 0, 1), \
            np.clip(ndimage.rotate(h, ang, reshape=True, order=1), 0, 1)

    leaf_rot = [[rot(sp, ang) for ang in range(0, 360, 30)] for sp in leaves]
    needles = []
    for k in range(36):
        ang = r.uniform(0, np.pi)
        needles.append(_line_sprite(r.uniform(22, 48), r.uniform(1.4, 2.2), ang, needle_cols[k % len(needle_cols)]))
    twigs = []
    for k in range(10):
        twigs.append(_line_sprite(r.uniform(60, 180), r.uniform(2.5, 5), r.uniform(0, np.pi), (58, 46, 36)))
    density = mn.fbm(N, 3, 4, seed_of(sd, "dens"))
    items = []
    for _ in range(1700):
        items.append(("leaf", r.random(2)))
    for _ in range(3600):
        items.append(("needle", r.random(2)))
    for _ in range(26):
        items.append(("twig", r.random(2)))
    order = r.permutation(len(items))
    for idx in order:
        kind, (x, y) = items[idx]
        cy, cx = y * N, x * N
        dval = density[int(cy) % N, int(cx) % N]
        if kind == "leaf":
            if r.random() > 0.45 + 0.55 * dval:
                continue
            sp = leaf_rot[r.integers(len(leaf_rot))][r.integers(12)]
            _scatter(rgb, hgt, sp, cy, cx, r.uniform(0.75, 1.15), 0.03)
        elif kind == "needle":
            if r.random() > 0.3 + 0.7 * (1 - dval):
                continue
            sp = needles[r.integers(len(needles))]
            _scatter(rgb, hgt, sp, cy, cx, r.uniform(0.7, 1.2), 0.015)
        else:
            _scatter(rgb, hgt, twigs[r.integers(len(twigs))], cy, cx, r.uniform(0.8, 1.1), 0.05)
    rgb = mn.downsample(rgb, ss)
    hgt = mn.downsample(hgt, ss)
    h = mn.norm01(hgt, 0.5, 99.5)
    ao = mn.ambient_occlusion(h, (1.5, 4, 10), 2.4)
    alb = rgb * (0.55 + 0.45 * ao)[..., None]
    damp = smoothstep(0.45, 0.85, mn.warped_fbm(S, 3, 5, seed_of(sd, "damp"), warp_amt=0.1))
    alb = alb * (1 - 0.2 * damp)[..., None]
    alb = tio.desaturate(alb, 0.15)
    smooth = np.clip(0.12 + 0.3 * damp * (1 - h * 0.5) + 0.05 * mn.fbm(S, 32, 3, seed_of(sd, "sm")), 0.03, 0.7)
    return tio.finish(alb, h, 0.0, smooth, nstrength=10.0, ao_strength=1.0)


@texset("mud", 2.0, notes="Wet dark mud with smeared ruts, grit, small stones and glossy puddles "
        "(puddles flat + smoothness ~0.93). Terrain R channel.")
def mud(S):
    sd = "mud"
    wy, wx = mn.warp_field(S, 3, 40, seed_of(sd, "w"))
    base = mn.warp(mn.fbm(S, 4, 6, seed_of(sd, "base")), wy, wx)
    smear = mn.warp(mn.fbm(S, (3, 14), 4, seed_of(sd, "smear")), wy * 0.6, wx * 0.6)
    ruts = smoothstep(0.45, 0.0, np.abs(mn.warp(mn.fbm(S, (1, 3), 3, seed_of(sd, "rut")), wy, wx) - 0.5)) * 0.6
    fine = mn.fbm(S, 48, 4, seed_of(sd, "fine"))
    st = mn.worley(S, 500, seed_of(sd, "stones"))
    r = mn.rng(seed_of(sd, "st"))
    srad = st.per_cell(r.uniform(0.1, 0.35, st.n)) * st.per_cell(r.random(st.n) < 0.12)
    stones = np.sqrt(np.clip(1 - (st.f1 / (srad + 1e-6)) ** 2, 0, 1)) * (srad > 0)
    stones = stones * smoothstep(0.3, 0.6, base)
    h = 0.5 + 0.25 * (base - 0.5) + 0.1 * (smear - 0.5) - 0.12 * ruts + 0.04 * (fine - 0.5) + 0.08 * stones
    water_lvl = np.percentile(h, 16)
    puddle = smoothstep(water_lvl + 0.005, water_lvl - 0.01, h)
    h_w = np.maximum(h, water_lvl)
    h_w = mn.norm01(h_w, 0.2, 99.8)
    t = np.clip(0.5 * base + 0.3 * smear + 0.2 * fine, 0, 1)
    alb = tio.gradient_map(t, [(0, (34, 27, 21)), (0.5, (52, 41, 31)), (1, (70, 57, 43))])
    wetness = np.clip(0.5 + 0.5 * mn.fbm(S, 6, 4, seed_of(sd, "wet")) - h_w * 0.3, 0, 1)
    alb = alb * (1 - 0.25 * wetness)[..., None]
    alb = tio.mix(alb, tio.rgb(66, 58, 48) * (0.8 + 0.4 * fine)[..., None], smoothstep(0.0, 0.4, stones) * 0.7)
    alb = tio.mix(alb, tio.rgb(26, 22, 18), puddle * 0.85)
    shore = smoothstep(0.03, 0.0, np.abs(h - water_lvl)) * (1 - puddle)
    smooth = np.clip(0.3 + 0.35 * wetness + 0.08 * fine - 0.1 * stones + 0.25 * shore, 0.05, 0.85)
    smooth = smooth * (1 - puddle) + 0.93 * puddle
    nh = h_w * (1 - puddle) + (mn.norm01(np.maximum(h, water_lvl), 0.2, 99.8)) * puddle
    return tio.finish(alb, h_w, 0.0, smooth, nheight=nh, nstrength=10.0, ao_strength=1.0)


@texset("moss", 1.0, notes="Dense damp moss cushions: granular shoots, yellow-green tops, dark gaps, brown dead "
        "patches. Terrain G channel.")
def moss(S):
    sd = "moss"
    wy, wx = mn.warp_field(S, 6, 10, seed_of(sd, "w"))
    cush = mn.worley(S, 70, seed_of(sd, "cush"), warp_px=(wy, wx))
    cush_h = np.sqrt(np.clip(1 - cush.f1 ** 2 * 0.7, 0, 1)) * (0.6 + 0.4 * mn.fbm(S, 12, 4, seed_of(sd, "cv")))
    cush_h = cush_h * smoothstep(0.0, 0.5, cush.edge * 0.5 + mn.fbm(S, 24, 3, seed_of(sd, "ce")) * 0.5)
    sh = mn.worley(S, 9000, seed_of(sd, "shoots"))
    shoots = np.clip(1 - sh.f1 * 1.2, 0, 1) ** 1.5
    sh2 = mn.worley(S, 2500, seed_of(sd, "shoots2"))
    shoots2 = np.clip(1 - sh2.f1 * 1.1, 0, 1)
    fine = mn.fbm(S, 64, 3, seed_of(sd, "fine"))
    h = 0.4 * cush_h + 0.25 * shoots + 0.15 * shoots2 + 0.1 * fine + 0.15 * mn.fbm(S, 4, 4, seed_of(sd, "m"))
    h = mn.norm01(h, 0.5, 99.5)
    dead = smoothstep(0.6, 0.8, mn.warped_fbm(S, 4, 5, seed_of(sd, "dead"), warp_amt=0.1))
    t = np.clip(h * 0.7 + 0.3 * mn.fbm(S, 8, 4, seed_of(sd, "tone")), 0, 1)
    alb = tio.gradient_map(t, [(0, (20, 26, 14)), (0.35, (40, 54, 24)), (0.65, (62, 78, 32)), (0.85, (84, 96, 40)),
                               (1, (100, 108, 50))])
    brown = tio.gradient_map(t, [(0, (30, 24, 16)), (0.6, (72, 60, 38)), (1, (96, 82, 54))])
    alb = tio.mix(alb, brown, dead * 0.8)
    tips = smoothstep(0.7, 0.95, shoots) * (1 - dead)
    alb = tio.mix(alb, tio.rgb(110, 120, 56), tips * 0.35)
    ao = mn.ambient_occlusion(h, (1.5, 4, 10), 2.2)
    alb = alb * (0.55 + 0.45 * ao)[..., None]
    damp = mn.fbm(S, 5, 4, seed_of(sd, "damp"))
    smooth = np.clip(0.12 + 0.2 * damp + 0.08 * tips - 0.05 * dead, 0.03, 0.6)
    return tio.finish(alb, h, 0.0, smooth, nstrength=10.0, ao_strength=1.0)


# =========================================================================== SKIN / FLESH
@texset("skin_decayed", 0.5, notes="Stretched pale grey-brown decayed skin: mottling, bruising, dark veins, "
        "wrinkles/stretch marks, crusted lesions with wet glossy cores.")
def skin_decayed(S):
    sd = "skin_decayed"
    mott = mn.warped_fbm(S, 5, 6, seed_of(sd, "mott"), warp_amt=0.1)
    bruise = smoothstep(0.55, 0.85, mn.warped_fbm(S, 3, 5, seed_of(sd, "bruise"), warp_amt=0.12))
    yellow = smoothstep(0.55, 0.85, mn.warped_fbm(S, 4, 5, seed_of(sd, "yel"), warp_amt=0.1))
    wy, wx = mn.warp_field(S, 4, 10, seed_of(sd, "ww"))
    wr = mn.warp(mn.fbm(S, (40, 5), 4, seed_of(sd, "wr"), mode="ridged"), wy, wx)
    wrink = smoothstep(0.55, 0.95, wr)
    stretch = smoothstep(0.86, 0.98, mn.warp(mn.fbm(S, (64, 3), 2, seed_of(sd, "str")), wy, wx)) * \
        smoothstep(0.55, 0.75, mn.fbm(S, 3, 4, seed_of(sd, "strm")))
    pore = pits(S, 5000, seed_of(sd, "pore"), 0.05, 0.2, keep=0.5)
    vwy, vwx = mn.warp_field(S, 6, 14, seed_of(sd, "vw"))
    vc = mn.worley(S, 40, seed_of(sd, "vein"), warp_px=(vwy, vwx))
    vc2 = mn.worley(S, 160, seed_of(sd, "vein2"), warp_px=(vwy * 0.5, vwx * 0.5))
    vein = np.clip(smoothstep(0.035, 0.0, vc.edge) * smoothstep(0.3, 0.6, mn.fbm(S, 4, 3, seed_of(sd, "vm")))
                   + 0.6 * smoothstep(0.025, 0.0, vc2.edge) * smoothstep(0.5, 0.7, mn.fbm(S, 6, 3, seed_of(sd, "vm2"))),
                   0, 1)
    vein_s = mn.blur(vein, 1.2)
    lw1 = mn.warp_field(S, 12, 6, seed_of(sd, "lw"))
    lw2 = mn.warp_field(S, 24, 5, seed_of(sd, "lw2"))
    les = mn.worley(S, 14, seed_of(sd, "les"), warp_px=(lw1[0] + lw2[0], lw1[1] + lw2[1]))
    r = mn.rng(seed_of(sd, "lr"))
    lrad = les.per_cell(r.uniform(0.05, 0.24, les.n)) * les.per_cell(r.random(les.n) < 0.45)
    ld = les.f1 / (lrad + 1e-6)
    core = smoothstep(0.75, 0.45, ld) * (lrad > 0)
    rim = smoothstep(1.1, 0.8, ld) * (1 - core) * (lrad > 0)
    halo = smoothstep(1.7, 0.9, ld) * (lrad > 0) * (0.6 + 0.4 * mn.fbm(S, 16, 3, seed_of(sd, "hv")))
    crust = smoothstep(0.5, 0.7, mn.fbm(S, 40, 3, seed_of(sd, "crust"))) * (rim + core * 0.4)
    h = (0.55 + 0.04 * (mott - 0.5) - 0.08 * wrink + 0.03 * stretch - 0.06 * pore + 0.03 * vein_s
         + 0.08 * rim + 0.06 * crust - 0.12 * core)
    h = np.clip(h, 0, 1)
    alb = tio.gradient_map(mott, [(0, (104, 96, 88)), (0.5, (126, 116, 104)), (1, (142, 132, 118))])
    alb = tio.mix(alb, tio.rgb(98, 86, 94), bruise * 0.5)
    alb = tio.mix(alb, tio.rgb(150, 140, 100), yellow * 0.3)
    alb = tio.mix(alb, tio.rgb(176, 164, 150), stretch * 0.4)
    alb = tio.mix(alb, alb * 0.72, wrink * 0.6)
    alb = tio.mix(alb, tio.rgb(70, 66, 92), vein_s * 0.5)
    alb = tio.mix(alb, tio.rgb(128, 76, 66), halo * 0.35)
    alb = tio.mix(alb, tio.rgb(118, 92, 56), crust * 0.6)
    alb = tio.mix(alb, tio.rgb(66, 26, 22) * (0.7 + 0.6 * mn.fbm(S, 32, 3, seed_of(sd, "cc")))[..., None], core * 0.85)
    alb = alb * (1 - 0.15 * pore)[..., None]
    smooth = np.clip(0.3 + 0.08 * mott - 0.1 * crust + 0.55 * core + 0.1 * halo, 0.05, 0.92)
    return tio.finish(alb, h, 0.0, smooth, nstrength=7.0, ao_strength=0.8)


@texset("mourner_skin", 0.5, notes="Tight grey-brown wrinkled hairless skin (Mourner): multi-scale crease network,"
        " pale scar lines, slight waxy sheen.")
def mourner_skin(S):
    sd = "mourner_skin"
    wy, wx = mn.warp_field(S, 5, 12, seed_of(sd, "w"))
    cr1 = mn.worley(S, 50, seed_of(sd, "c1"), aspect=(1, 1.6), warp_px=(wy, wx))
    cr2 = mn.worley(S, 300, seed_of(sd, "c2"), warp_px=(wy * 0.5, wx * 0.5))
    cr3 = mn.worley(S, 1800, seed_of(sd, "c3"), warp_px=(wy * 0.2, wx * 0.2))
    rid1 = mn.warp(mn.fbm(S, 4, 4, seed_of(sd, "r1"), mode="ridged"), wy, wx)
    rid2 = mn.warp(mn.fbm(S, 10, 3, seed_of(sd, "r2"), mode="ridged"), wy * 0.5, wx * 0.5)
    c1 = smoothstep(0.66, 0.96, rid1) * (0.6 + 0.4 * mn.fbm(S, 8, 3, seed_of(sd, "c1m")))
    c2 = smoothstep(0.72, 0.97, rid2) * 0.6 + smoothstep(0.08, 0.0, cr2.edge) ** 1.5 * 0.25
    c3 = smoothstep(0.10, 0.0, cr3.edge) * 0.4
    wr = smoothstep(0.6, 0.95, mn.warp(mn.fbm(S, (28, 4), 3, seed_of(sd, "wr"), mode="ridged"), wy, wx))
    puff = (np.sqrt(np.clip(1 - cr2.f1 ** 2 * 0.5, 0, 1)) * 0.5 + np.sqrt(np.clip(1 - cr3.f1 ** 2 * 0.5, 0, 1)) * 0.3)
    scar = smoothstep(0.01, 0.0, np.abs(mn.warped_fbm(S, 2, 4, seed_of(sd, "scar"), warp_amt=0.05) - 0.5)) * \
        smoothstep(0.5, 0.7, mn.fbm(S, 3, 3, seed_of(sd, "scm")))
    mott = mn.warped_fbm(S, 4, 6, seed_of(sd, "mott"), warp_amt=0.1)
    h = 0.55 + 0.12 * puff - 0.2 * c1 - 0.1 * c2 - 0.05 * c3 - 0.06 * wr + 0.04 * scar + 0.03 * (mott - 0.5)
    h = mn.blur(h, 0.8)
    h = mn.norm01(h, 0.3, 99.7)
    alb = tio.gradient_map(mott, [(0, (86, 76, 68)), (0.5, (106, 95, 84)), (1, (124, 111, 98))])
    alb = alb * (0.9 + 0.14 * puff)[..., None]
    alb = tio.mix(alb, tio.rgb(58, 48, 42), np.clip(c1 * 0.45 + c2 * 0.3 + c3 * 0.2 + wr * 0.25, 0, 1))
    alb = tio.mix(alb, tio.rgb(146, 136, 124), scar * 0.6)
    smooth = np.clip(0.36 + 0.1 * puff - 0.15 * c1 - 0.05 * c2, 0.05, 0.8)
    return tio.finish(alb, h, 0.0, smooth, nstrength=9.0, ao_strength=1.2)


@texset("meat", 0.3, notes="Raw red meat: muscle fibre striations, white-pink fat marbling, silver-skin, "
        "wet glossy surface.")
def meat(S):
    sd = "meat"
    wy, wx = mn.warp_field(S, 3, 30, seed_of(sd, "w"))
    fib = mn.warp(mn.fbm(S, (6, 90), 3, seed_of(sd, "fib")), wy, wx)
    bundle = mn.warp(mn.worley(S, 120, seed_of(sd, "bund"), aspect=(1, 4)).edge, wy, wx)
    bund = smoothstep(0.08, 0.0, bundle)
    fat_f = mn.warped_fbm(S, 5, 6, seed_of(sd, "fat"), warp_amt=0.12)
    fat = smoothstep(0.035, 0.0, np.abs(fat_f - 0.55)) * smoothstep(0.3, 0.6, mn.fbm(S, 4, 3, seed_of(sd, "fm")))
    fleck = smoothstep(0.86, 0.95, mn.fbm(S, (12, 40), 3, seed_of(sd, "fleck")))
    fat = np.clip(fat + fleck * 0.8, 0, 1)
    silver = smoothstep(0.7, 0.85, mn.warped_fbm(S, 3, 5, seed_of(sd, "silver"), warp_amt=0.1))
    tone = mn.fbm(S, 6, 5, seed_of(sd, "tone"))
    h = 0.5 + 0.06 * (fib - 0.5) - 0.06 * bund + 0.05 * fat + 0.04 * (tone - 0.5)
    alb = tio.gradient_map(np.clip(0.6 * tone + 0.4 * fib, 0, 1),
                           [(0, (84, 22, 24)), (0.4, (112, 30, 30)), (0.75, (136, 44, 40)), (1, (150, 58, 52))])
    alb = tio.mix(alb, alb * 0.7, bund * 0.6)
    alb = tio.mix(alb, tio.rgb(206, 182, 160), fat * 0.85)
    alb = tio.mix(alb, tio.rgb(178, 160, 160), silver * 0.35)
    smooth = np.clip(0.58 + 0.2 * tone + 0.1 * silver - 0.1 * fat, 0.3, 0.9)
    return tio.finish(alb, h, 0.0, smooth, nstrength=12.0, ao_strength=0.6)


@texset("flesh", 0.4, notes="Wet torn dark-red flesh: shredded fibrous strands, dark clots, pale tissue, "
        "glossy membranes (MNF_Flesh, wounds, gore).")
def flesh(S):
    sd = "flesh"
    wy, wx = mn.warp_field(S, 3, 50, seed_of(sd, "w"))
    wy2, wx2 = mn.warp_field(S, 12, 8, seed_of(sd, "w2"))
    src = mn.rng(seed_of(sd, "noise")).random((S, S))
    vy = np.ones((S, S)) * 0.3 + (mn.fbm(S, 4, 4, seed_of(sd, "vy")) - 0.5) * 2.0
    vx = np.ones((S, S)) + (mn.fbm(S, 4, 4, seed_of(sd, "vx")) - 0.5) * 1.5
    nrm = np.sqrt(vy * vy + vx * vx) + 1e-6
    strands = mn.lic(mn.blur(src, 0.6), vy / nrm, vx / nrm, length=14, step=1.0)
    strands = mn.norm01(strands, 1, 99)
    tear = smoothstep(0.4, 0.75, mn.warp(mn.fbm(S, (6, 3), 5, seed_of(sd, "tear")), wy + wy2, wx + wx2))
    clot = smoothstep(0.6, 0.8, mn.warped_fbm(S, 5, 5, seed_of(sd, "clot"), warp_amt=0.12))
    lumps = mn.worley(S, 200, seed_of(sd, "lumps"))
    lump = np.sqrt(np.clip(1 - lumps.f1 ** 2 * 0.6, 0, 1))
    tissue = smoothstep(0.65, 0.85, mn.fbm(S, 8, 4, seed_of(sd, "tissue"))) * (1 - clot)
    h = 0.5 + 0.12 * (strands - 0.5) * tear + 0.1 * lump * (1 - tear) + 0.08 * clot - 0.1 * tear * 0.5
    h = mn.blur(h, 0.6)
    h = mn.norm01(h, 0.5, 99.5)
    alb = tio.gradient_map(np.clip(0.5 * strands + 0.5 * lump, 0, 1),
                           [(0, (40, 8, 10)), (0.4, (70, 14, 16)), (0.75, (100, 24, 24)), (1, (124, 38, 36))])
    alb = tio.mix(alb, tio.rgb(150, 82, 78) * (0.7 + 0.5 * strands)[..., None], tissue * 0.5)
    alb = tio.mix(alb, tio.rgb(26, 5, 6), clot * 0.85)
    alb = alb * (0.75 + 0.25 * strands * tear + 0.25 * (1 - tear))[..., None]
    smooth = np.clip(0.72 + 0.18 * clot + 0.08 * lump - 0.15 * tear * strands, 0.4, 0.96)
    return tio.finish(alb, h, 0.0, smooth, nstrength=7.0, ao_strength=1.0)


# =========================================================================== FABRIC / ROPE / PAPER
def weave(S, n, twill=False, seed=0, jitter=1.0):
    """Woven thread height (0..1) for plain (n x n threads) or 2/2 twill weave, plus per-thread ids."""
    wy, wx = mn.warp_field(S, 6, jitter, seed, octaves=3)
    yy, xx = grid(S)
    u = (xx + wx / S) * n
    v = (yy + wy / S) * n
    iu, iv = np.floor(u), np.floor(v)
    fu, fv = u - iu, v - iv
    pw = np.sin(np.pi * fu)          # warp thread cross-section (vertical threads)
    pf = np.sin(np.pi * fv)          # weft thread cross-section (horizontal threads)
    if twill:
        over = ((iu + iv) % 4) < 2
    else:
        over = ((iu + iv) % 2) == 0
    warp_top = pw ** 0.6 * (0.75 + 0.25 * np.sin(np.pi * fv))
    weft_top = pf ** 0.6 * (0.75 + 0.25 * np.sin(np.pi * fu))
    h = np.where(over, np.maximum(warp_top, weft_top * 0.55), np.maximum(weft_top, warp_top * 0.55))
    which = np.where(over, warp_top > weft_top * 0.55, weft_top <= warp_top * 0.55)   # True = warp visible
    return h, which, (iu % n).astype(int), (iv % n).astype(int), fu, fv


@texset("fabric_canvas", 0.5, notes="Dirty olive-khaki cotton canvas, plain weave (~96 threads per repeat), slubs, "
        "water-stain tide marks, grime.")
def fabric_canvas(S):
    sd = "fabric_canvas"
    n = 96
    h, which, iu, iv, fu, fv = weave(S, n, False, seed_of(sd, "w"), 1.2)
    r = mn.rng(seed_of(sd, "thr"))
    tw = r.random(n)
    tf = r.random(n)
    thread_tone = np.where(which, tw[iu], tf[iv])
    fuzz = mn.fbm(S, 128, 2, seed_of(sd, "fuzz"))
    fib = np.where(which, mn.fbm(S, (64, 256), 2, seed_of(sd, "fa")), mn.fbm(S, (256, 64), 2, seed_of(sd, "fb")))
    macro = mn.fbm(S, 4, 5, seed_of(sd, "macro"))
    stain, rim = stain_blobs(S, seed_of(sd, "stain"), 3, 0.66, 0.06, 40)
    dirt = smoothstep(0.35, 0.95, mn.warped_fbm(S, 3, 5, seed_of(sd, "dirt"), warp_amt=0.1))
    t = np.clip(0.35 * thread_tone + 0.25 * fib + 0.4 * macro, 0, 1)
    alb = tio.gradient_map(t, [(0, (82, 78, 58)), (0.5, (104, 98, 72)), (1, (124, 116, 86))])
    alb = alb * (0.7 + 0.3 * h)[..., None]
    alb = alb * (1 - 0.1 * stain - 0.18 * rim - 0.15 * dirt)[..., None]
    alb = tio.mix(alb, alb * 1.15, fuzz * 0.2)
    hh = 0.5 * h + 0.05 * fib + 0.03 * fuzz
    smooth = np.clip(0.12 + 0.06 * h + 0.06 * stain - 0.04 * dirt, 0.03, 0.4)
    return tio.finish(alb, hh, 0.0, smooth, nstrength=4.0, ao_strength=0.6, ao_radii=(1, 3))


@texset("fabric_blanket", 0.6, notes="Coarse worn wool blanket: 2/2 twill, fuzzy fibres, faded dark stripes, "
        "pilling and stains; dull grey-brown.")
def fabric_blanket(S):
    sd = "fabric_blanket"
    yy, xx = grid(S)
    n = 64
    h, which, iu, iv, fu, fv = weave(S, n, True, seed_of(sd, "w"), 1.8)
    r = mn.rng(seed_of(sd, "thr"))
    tw = r.random(n)
    tf = r.random(n)
    thread_tone = np.where(which, tw[iu], tf[iv])
    fuzz = mn.blur(mn.rng(seed_of(sd, "fz")).random((S, S)), 0.8)
    fuzz2 = mn.fbm(S, 64, 3, seed_of(sd, "fuzz2"))
    stripe_band = smoothstep(0.035, 0.025, np.abs(mn.pdelta(yy, 0.2))) + \
        smoothstep(0.012, 0.006, np.abs(mn.pdelta(yy, 0.27)))
    stripe = np.clip(stripe_band, 0, 1) * (~which)
    pill = smoothstep(0.85, 0.95, mn.value(S, 96, seed_of(sd, "pill"))) * smoothstep(0.4, 0.7, mn.fbm(S, 4, 3,
                                                                                                    seed_of(sd, "pm")))
    stain, rim = stain_blobs(S, seed_of(sd, "stain"), 3, 0.72, 0.07, 30)
    macro = mn.fbm(S, 3, 5, seed_of(sd, "macro"))
    t = np.clip(0.3 * thread_tone + 0.3 * fuzz2 + 0.4 * macro, 0, 1)
    alb = tio.gradient_map(t, [(0, (64, 62, 54)), (0.5, (82, 78, 68)), (1, (98, 93, 80))])
    alb = tio.mix(alb, tio.rgb(46, 34, 30), stripe * 0.8)
    alb = alb * (0.72 + 0.28 * h)[..., None] * (0.9 + 0.2 * fuzz)[..., None]
    alb = tio.mix(alb, alb * 1.2, pill * 0.5)
    alb = alb * (1 - 0.1 * stain - 0.12 * rim)[..., None]
    hh = 0.45 * h + 0.12 * fuzz2 + 0.05 * fuzz + 0.1 * pill
    smooth = np.clip(0.08 + 0.04 * h + 0.04 * stain, 0.02, 0.3)
    return tio.finish(alb, hh, 0.0, smooth, nstrength=4.0, ao_strength=0.6, ao_radii=(1, 3))


@texset("rope", 0.25, notes="Dirty twisted hemp rope: 3 strands around V, twisting along U (map U along the rope "
        "length, V around it), fibres and fuzz.")
def rope(S):
    sd = "rope"
    yy, xx = grid(S)
    wy, wx = mn.warp_field(S, 8, 1.5, seed_of(sd, "w"), octaves=2)
    s = mn.wave_lines(S, 4, 3, warp_px=(wy, wx))           # strands: 3 around, 4 twists per repeat along U
    prof = np.sin(np.pi * s) ** 0.5
    sid = np.floor(np.mod(4 * xx + 3 * yy, 3.0)).astype(int)
    fib = mn.wave_lines(S, 20, 55, warp_px=(wy * 2, wx * 2))
    fibre = (0.5 + 0.5 * np.sin(fib * TAU)) * (0.6 + 0.4 * mn.fbm(S, 32, 2, seed_of(sd, "fm")))
    hairs = scratch_lines(S, 260, seed_of(sd, "hair"), (0.01, 0.04), (0, np.pi), (0.4, 0.8), 1.0, value=(0.3, 0.8))
    fib_n = mn.fbm(S, 96, 2, seed_of(sd, "fn"))
    fuzz = mn.blur(mn.rng(seed_of(sd, "fz")).random((S, S)), 0.7)
    h = 0.75 * prof + 0.12 * fibre * prof + 0.06 * fib_n + 0.05 * hairs
    dirt = smoothstep(0.3, 0.9, mn.fbm(S, (4, 8), 4, seed_of(sd, "dirt")))
    r = mn.rng(seed_of(sd, "tone"))
    stone = np.array([r.uniform(0.85, 1.1) for _ in range(3)])[sid]
    t = np.clip(0.5 * fibre + 0.3 * fib_n + 0.2 * fuzz, 0, 1)
    alb = tio.gradient_map(t, [(0, (96, 80, 58)), (0.5, (124, 106, 78)), (1, (146, 128, 96))])
    alb = alb * stone[..., None]
    alb = alb * (0.3 + 0.7 * prof)[..., None]
    alb = alb * (1 - 0.35 * dirt)[..., None]
    alb = tio.mix(alb, tio.rgb(150, 132, 100), hairs * 0.5)
    smooth = np.clip(0.1 + 0.05 * fibre - 0.03 * dirt, 0.02, 0.3)
    return tio.finish(alb, h, 0.0, smooth, nstrength=6.0, ao_strength=0.8)


@texset("paper", 0.3, notes="Aged yellowed paper: fibres, foxing spots, coffee-ring and water tide stains, "
        "faint fold creases (notes, posters, labels).")
def paper(S):
    sd = "paper"
    yy, xx = grid(S)
    fib = mn.fbm(S, 96, 3, seed_of(sd, "fib"))
    fibl = scratch_lines(S, 400, seed_of(sd, "fibl"), (0.005, 0.02), (0, np.pi), (0.4, 0.8), 0.6, value=(0.2, 0.6))
    macro = mn.fbm(S, 3, 5, seed_of(sd, "macro"))
    fox = pits(S, 300, seed_of(sd, "fox"), 0.05, 0.3, keep=0.25, irregular=3.0)
    fox = smoothstep(0.0, 0.5, fox) * smoothstep(0.4, 0.7, mn.fbm(S, 4, 3, seed_of(sd, "fm")))
    stain, rim = stain_blobs(S, seed_of(sd, "stain"), 2, 0.7, 0.05, 50)
    d = np.sqrt(mn.pdelta(xx, 0.3) ** 2 + mn.pdelta(yy, 0.65) ** 2)
    ring = smoothstep(0.006, 0.0, np.abs(d - 0.12 - 0.006 * mn.fbm(S, 16, 3, seed_of(sd, "rg")))) * \
        smoothstep(0.3, 0.6, mn.fbm(S, 6, 3, seed_of(sd, "rgm")))
    fold = smoothstep(0.004, 0.0, np.abs(mn.pdelta(xx, 0.5))) + smoothstep(0.004, 0.0, np.abs(mn.pdelta(yy, 0.5)))
    fold_s = smoothstep(0.02, 0.0, np.abs(mn.pdelta(xx, 0.5))) + smoothstep(0.02, 0.0, np.abs(mn.pdelta(yy, 0.5)))
    crumple, _ = _crumple(S, seed_of(sd, "crumple"))
    h = 0.5 + 0.02 * (fib - 0.5) + 0.05 * crumple - 0.04 * np.clip(fold, 0, 1) + 0.01 * fibl
    alb = tio.gradient_map(np.clip(0.6 * macro + 0.4 * fib, 0, 1),
                           [(0, (176, 164, 132)), (0.5, (192, 182, 152)), (1, (204, 196, 168))])
    alb = tio.mix(alb, alb * 0.93, fibl * 0.5)
    alb = tio.mix(alb, tio.rgb(150, 118, 76), fox * 0.6)
    alb = tio.mix(alb, tio.rgb(166, 146, 106), stain * 0.4)
    alb = tio.mix(alb, tio.rgb(130, 104, 70), np.clip(rim * 0.5 + ring * 0.6, 0, 1))
    alb = alb * (1 - 0.1 * np.clip(fold_s, 0, 1))[..., None]
    smooth = np.clip(0.12 + 0.04 * fib + 0.05 * stain, 0.03, 0.3)
    return tio.finish(alb, h, 0.0, smooth, nstrength=5.0, ao_strength=0.4)


def _crumple(S, seed):
    f, c = None, mn.worley(S, 60, seed)
    r = mn.rng(seed + 1)
    a = c.per_cell(r.normal(0, 1, c.n))
    b = c.per_cell(r.normal(0, 1, c.n))
    h = (a * c.dx + b * c.dy) / np.sqrt(1 / 60)
    return mn.norm01(mn.blur(h, 2.0)), c


@texset("water", 2.0, kind="normal", notes="Only _N: gentle tileable ripple normal for puddles/flooded floors "
        "(scroll two copies in opposite directions).")
def water(S):
    sd = "water"
    yy, xx = grid(S)
    r = mn.rng(seed_of(sd, "waves"))
    h = np.zeros((S, S))
    for _ in range(48):
        kx, ky = r.integers(-9, 10), r.integers(-9, 10)
        if kx == 0 and ky == 0:
            continue
        k = np.sqrt(kx * kx + ky * ky)
        h += np.sin(TAU * (kx * xx + ky * yy) + r.uniform(0, TAU)) / k ** 1.4
    h = mn.norm01(h)
    h = 0.7 * h + 0.3 * mn.fbm(S, 12, 4, seed_of(sd, "fine"))
    n = mn.height_to_normal(h, 3.0)
    return tio.TexSet(None, n, None)


# =========================================================================== FUR
def fur_layer(S, sd, n, length, width, turb=0.3, clump_n=0, clump_k=0.0, root_cols=None, tip_cols=None,
              band=None, keep=None, segs=6, curl=0.4, base_angle=np.pi / 2, ss=2, height_gain=1.0):
    """Draw a tileable strand layer. Returns (premultiplied rgb, height, coverage).

    root_cols / tip_cols: (n,3) 0..255 colour arrays. band: optional (n,3) mid-band colour (agouti).
    keep: optional (S,S) probability map of a strand rooting at that pixel (bald patches).
    """
    r = mn.rng(seed_of(sd, "roots"))
    ang = base_angle + (mn.fbm(S, 3, 4, seed_of(sd, "flowA")) - 0.5) * 2 * turb * np.pi
    ang = ang + (mn.fbm(S, 12, 3, seed_of(sd, "flowB")) - 0.5) * turb * np.pi * 0.5
    dX, dY = np.cos(ang), np.sin(ang)
    if clump_n:
        c = mn.worley(S, clump_n, seed_of(sd, "clump"), warp_px=mn.warp_field(S, 8, 6, seed_of(sd, "cw")))
        tx, ty = -c.dx, -c.dy
        tn = np.sqrt(tx * tx + ty * ty) + 1e-6
        w = clump_k * smoothstep(0.0, 0.25, c.f1)
        dX = dX + w * tx / tn
        dY = dY + w * ty / tn
        nn = np.sqrt(dX * dX + dY * dY) + 1e-6
        dX, dY = dX / nn, dY / nn
    roots = r.random((n, 2))
    if keep is not None:
        ix = (roots[:, 1] * S).astype(int) % S
        jx = (roots[:, 0] * S).astype(int) % S
        roots = roots[r.random(n) < keep[ix, jx]]
        root_cols = root_cols[: len(roots)] if root_cols is not None else None
    n = len(roots)
    L = r.uniform(length[0], length[1], n)
    Wd = r.uniform(width[0], width[1], n)
    rc = np.asarray(root_cols[:n], dtype=np.float64)
    tc = np.asarray(tip_cols[:n], dtype=np.float64)
    bc = None if band is None else np.asarray(band[:n], dtype=np.float64)

    def dirs(x, y):
        i = int(y * S) % S
        j = int(x * S) % S
        return dX[i, j], dY[i, j]

    def col(i, t):
        if bc is None:
            c = rc[i] + (tc[i] - rc[i]) * t
        elif t < 0.55:
            c = rc[i] + (bc[i] - rc[i]) * (t / 0.55)
        elif t < 0.78:
            c = bc[i]
        else:
            c = bc[i] + (tc[i] - bc[i]) * min(1.0, (t - 0.78) / 0.12)
        return (int(c[0]), int(c[1]), int(c[2]))

    return tio.draw_strands(S, roots, dirs, L, Wd, col, ss=ss, segs=segs, curl=curl, seed=seed_of(sd, "curl"),
                            height_gain=height_gain)


def _jitter_cols(r, n, base, var, dark_frac=0.0, dark=(0.6, 0.8)):
    b = np.array(base, dtype=np.float64)
    out = b[None, :] * (1 + (r.random((n, 1)) - 0.5) * 2 * var) + (r.random((n, 3)) - 0.5) * 6
    if dark_frac:
        m = r.random(n) < dark_frac
        out[m] *= r.uniform(*dark, m.sum())[:, None]
    return np.clip(out, 0, 255)


def fur_compose(S, sd, layers, under, under_h, smooth_base=0.22, nstrength=3.5, extra_smooth=None, ao_mul=None):
    """Stack strand layers (first = bottom) over an under-colour; build the TexSet."""
    alb = under.copy()
    h = under_h.copy()
    cov_tot = np.zeros((S, S))
    for (rgb_l, h_l, cov) in layers:
        alb = rgb_l + alb * (1 - cov[..., None])
        h = np.maximum(h * (1 - cov) + h_l, h * 0.9)
        cov_tot = np.maximum(cov_tot, cov)
    h = mn.blur(h, 0.5)
    ao = mn.ambient_occlusion(h, (1.5, 4, 10), 2.0)
    if ao_mul is not None:
        ao = ao * ao_mul
    alb = alb * (0.6 + 0.4 * ao)[..., None]
    smooth = np.full((S, S), smooth_base) + (extra_smooth if extra_smooth is not None else 0)
    return tio.finish(alb, h, 0.0, np.clip(smooth, 0.02, 0.9), nstrength=nstrength, ao_strength=0.0,
                      ao=ao), cov_tot


def _skin_under(S, sd, base=(120, 100, 92), dark=(70, 56, 52)):
    mott = mn.warped_fbm(S, 6, 5, seed_of(sd, "skin"), warp_amt=0.1)
    wy, wx = mn.warp_field(S, 4, 10, seed_of(sd, "skw"))
    wr = smoothstep(0.6, 0.95, mn.warp(mn.fbm(S, (30, 6), 3, seed_of(sd, "skwr"), mode="ridged"), wy, wx))
    col = tio.mix(np.ones((S, S, 3)) * tio.rgb(base), np.ones((S, S, 3)) * tio.rgb(dark), mott)
    col = col * (1 - 0.3 * wr)[..., None]
    h = 0.1 + 0.05 * mott - 0.04 * wr
    return col, h


@texset("fur_rotten", 0.4, notes="Matted dirty brown-grey fur with converging clumps, grime and wet strands, "
        "bald patches of sick skin (Rotten creatures).")
def fur_rotten(S):
    sd = "fur_rotten"
    r = mn.rng(seed_of(sd, "cols"))
    bald_f = mn.warped_fbm(S, 4, 6, seed_of(sd, "bald"), warp_amt=0.12)
    bald = smoothstep(0.68, 0.76, bald_f)
    keep = np.clip(1 - bald * 1.0, 0, 1) * (1 - 0.5 * smoothstep(0.6, 0.7, bald_f))
    n = 22000
    rc = _jitter_cols(r, n, (40, 34, 29), 0.2)
    tc = _jitter_cols(r, n, (104, 94, 80), 0.25, dark_frac=0.35, dark=(0.45, 0.7))
    under, uh = _skin_under(S, sd, (112, 96, 88), (72, 58, 54))
    les = smoothstep(0.82, 0.9, mn.fbm(S, 14, 4, seed_of(sd, "les"))) * bald
    under = tio.mix(under, tio.rgb(70, 30, 26), les * 0.8)
    under_dark = tio.mix(np.ones((S, S, 3)) * tio.rgb(34, 29, 25), under, smoothstep(0.55, 0.72, bald_f))
    L1 = fur_layer(S, sd + "a", n, (0.045, 0.085), (1.1, 1.7), turb=0.35, clump_n=60, clump_k=1.4,
                   root_cols=rc, tip_cols=tc, keep=keep, curl=0.5)
    wet = smoothstep(0.55, 0.8, mn.fbm(S, 6, 4, seed_of(sd, "wet")))
    grime = smoothstep(0.5, 0.85, mn.warped_fbm(S, 5, 5, seed_of(sd, "grime"), warp_amt=0.08))
    ts, cov = fur_compose(S, sd, [L1], under_dark, uh, 0.18, 4.0, extra_smooth=0.3 * wet + 0.35 * les)
    ts.albedo = ts.albedo * (1 - 0.3 * wet * cov - 0.25 * grime)[..., None]
    return ts


def _rabbit_cols(r, n):
    rc = _jitter_cols(r, n, (88, 78, 68), 0.12)
    bc = _jitter_cols(r, n, (60, 50, 42), 0.15)
    tc = _jitter_cols(r, n, (152, 138, 118), 0.12, dark_frac=0.2, dark=(0.4, 0.6))
    return rc, bc, tc


@texset("fur_rabbit", 0.3, notes="Soft dense agouti rabbit fur (grey-brown, dark band, pale tips), gentle flow.")
def fur_rabbit(S):
    sd = "fur_rabbit"
    r = mn.rng(seed_of(sd, "cols"))
    n = 26000
    rc, bc, tc = _rabbit_cols(r, n)
    under = np.ones((S, S, 3)) * tio.rgb(70, 60, 52)
    L1 = fur_layer(S, sd, n, (0.03, 0.05), (1.0, 1.4), turb=0.22, clump_n=140, clump_k=0.35,
                   root_cols=rc, tip_cols=tc, band=bc, curl=0.3)
    ts, _ = fur_compose(S, sd, [L1], under, np.zeros((S, S)) + 0.1, 0.2, 3.0)
    return ts


@texset("fur_rabbit_mangy", 0.3, notes="Rabbit fur with irregular mange: bald patches of dark stretched wrinkled "
        "skin, scabs, thinning broken fur at the patch edges.")
def fur_rabbit_mangy(S):
    sd = "fur_rabbit_mangy"
    r = mn.rng(seed_of(sd, "cols"))
    n = 26000
    rc, bc, tc = _rabbit_cols(r, n)
    bf = mn.warped_fbm(S, 4, 6, seed_of(sd, "bald"), warp_amt=0.14) * 0.8 + 0.2 * mn.fbm(S, 20, 3, seed_of(sd, "bb"))
    bald = smoothstep(0.54, 0.6, bf)
    thin = smoothstep(0.45, 0.56, bf)
    keep = np.clip(1 - thin * 0.85 - bald, 0, 1)
    under_skin, uh = _skin_under(S, sd, (74, 60, 57), (44, 35, 34))
    scab = smoothstep(0.8, 0.88, mn.fbm(S, 20, 4, seed_of(sd, "scab"))) * bald
    under_skin = tio.mix(under_skin, tio.rgb(72, 34, 28), scab * 0.85)
    under = tio.mix(np.ones((S, S, 3)) * tio.rgb(70, 60, 52), under_skin, smoothstep(0.46, 0.58, bf))
    L1 = fur_layer(S, sd, n, (0.03, 0.05), (1.0, 1.4), turb=0.3, clump_n=140, clump_k=0.5,
                   root_cols=rc, tip_cols=tc, band=bc, keep=keep, curl=0.45)
    ts, cov = fur_compose(S, sd, [L1], under, uh + 0.05 * scab, 0.2, 3.0,
                          extra_smooth=0.15 * bald * (1 - scab) + 0.3 * scab)
    return ts


@texset("fur_boar", 0.4, notes="Dark coarse bristly boar hide: long thick straight bristles with grizzled "
        "grey tips over dark skin.")
def fur_boar(S):
    sd = "fur_boar"
    r = mn.rng(seed_of(sd, "cols"))
    n = 12000
    rc = _jitter_cols(r, n, (26, 21, 18), 0.25)
    tc = _jitter_cols(r, n, (64, 56, 48), 0.3)
    grey = r.random(n) < 0.3
    tc[grey] = np.clip(np.array([118, 110, 100])[None, :] * r.uniform(0.8, 1.15, (grey.sum(), 1)), 0, 255)
    under, uh = _skin_under(S, sd, (46, 40, 37), (30, 26, 24))
    L0 = fur_layer(S, sd + "u", 16000, (0.02, 0.035), (1.0, 1.3), turb=0.4, root_cols=_jitter_cols(r, 16000, (30, 25, 21), 0.2),
                   tip_cols=_jitter_cols(r, 16000, (44, 37, 31), 0.2), curl=0.9)
    L1 = fur_layer(S, sd, n, (0.07, 0.12), (1.6, 2.4), turb=0.12, clump_n=90, clump_k=0.25,
                   root_cols=rc, tip_cols=tc, curl=0.15, segs=5)
    ts, _ = fur_compose(S, sd, [L0, L1], under, uh, 0.26, 4.5)
    return ts


@texset("fur_dark", 0.4, notes="Dusty near-black grimy fur: dark matted strands, dust-greyed tips and grime clumps.")
def fur_dark(S):
    sd = "fur_dark"
    r = mn.rng(seed_of(sd, "cols"))
    n = 22000
    rc = _jitter_cols(r, n, (20, 19, 18), 0.2)
    tc = _jitter_cols(r, n, (40, 37, 35), 0.25)
    dusty = r.random(n) < 0.4
    tc[dusty] = np.clip(np.array([76, 71, 64])[None, :] * r.uniform(0.8, 1.2, (dusty.sum(), 1)), 0, 255)
    under = np.ones((S, S, 3)) * tio.rgb(18, 17, 16)
    L1 = fur_layer(S, sd, n, (0.045, 0.08), (1.1, 1.6), turb=0.3, clump_n=80, clump_k=0.9,
                   root_cols=rc, tip_cols=tc, curl=0.45)
    dust = smoothstep(0.5, 0.85, mn.warped_fbm(S, 4, 5, seed_of(sd, "dust"), warp_amt=0.1))
    ts, cov = fur_compose(S, sd, [L1], under, np.zeros((S, S)) + 0.1, 0.2, 4.0, extra_smooth=-0.08 * dust)
    ts.albedo = tio.mix(ts.albedo, ts.albedo * 1.35 + 0.03, dust * 0.5)
    return ts
