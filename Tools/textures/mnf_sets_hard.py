"""mnf_sets_hard - concrete, metal, rubber/plastic, rock, ore and mineral texture sets."""
from __future__ import annotations

import numpy as np

import mnf_noise as mn
import mnf_texio as tio
from mnf_noise import seed_of, smoothstep, grid
from mnf_registry import texset


# =========================================================================== shared helpers
def crack_mask(S, seed, n=14, width=0.03, coverage=0.55, warp_amt=22.0, wiggle=3.0, branch=True):
    """Tileable crack network (1 = crack centre). Width in cell-spacing units."""
    wy, wx = mn.warp_field(S, 4, warp_amt, seed)
    c = mn.worley(S, n, seed, warp_px=(wy, wx), k=2)
    wy2, wx2 = mn.warp_field(S, 32, wiggle, seed + 5, octaves=3)
    e = mn.warp(c.edge, wy2, wx2)
    m = mn.fbm(S, 3, 4, seed + 9)
    wvar = width * (0.35 + 0.9 * mn.fbm(S, 8, 3, seed + 13))
    crack = smoothstep(wvar, 0.0, e) * smoothstep(1.0 - coverage - 0.08, 1.0 - coverage + 0.08, m)
    if branch:
        c2 = mn.worley(S, n * 4, seed + 77, warp_px=(wy * 0.6, wx * 0.6), k=2)
        e2 = mn.warp(c2.edge, wy2, wx2)
        crack2 = smoothstep(width * 0.45, 0.0, e2) * smoothstep(0.72, 0.85, m)
        crack = np.maximum(crack, crack2 * 0.8)
    return crack


def scratch_lines(S, n, seed, length=(0.02, 0.12), angle=(0, np.pi), width=(0.6, 1.4), curve=0.15,
                  ss=2, value=(0.4, 1.0)):
    """Tileable thin scratches (0..1)."""
    r = mn.rng(seed)
    cv = tio.WrapCanvas(S, ss, "L", 0)
    for _ in range(n):
        x, y = r.random(2)
        a = r.uniform(*angle)
        L = r.uniform(*length)
        k = (r.random() - 0.5) * curve
        pts = []
        for t in np.linspace(0, 1, 6):
            aa = a + k * t * 6
            pts.append((x + np.cos(aa) * L * t, y + np.sin(aa) * L * t))
        cv.line(pts, int(255 * r.uniform(*value)), r.uniform(*width))
    return cv.array()


def pits(S, n, seed, rmin=0.05, rmax=0.22, keep=0.6, irregular=0.0):
    """Small pits (0..1, 1 = deepest), sizes relative to cell spacing; ``irregular`` warps their shape (px)."""
    wp = mn.warp_field(S, 48, irregular, seed + 1, octaves=2) if irregular > 0 else None
    c = mn.worley(S, n, seed, k=2, warp_px=wp)
    r = mn.rng(seed + 3)
    rad = c.per_cell(r.uniform(rmin, rmax, c.n))
    on = c.per_cell(r.random(c.n) < keep)
    d = np.clip(1.0 - c.f1 / rad, 0, 1)
    return (d ** 0.7) * on


def stain_blobs(S, seed, freq=3, thresh=0.62, soft=0.05, warp=30):
    """Irregular stains: returns (inside 0..1, rim 0..1)."""
    wy, wx = mn.warp_field(S, 5, warp, seed)
    f = mn.warp(mn.fbm(S, freq, 6, seed + 1), wy, wx)
    inside = smoothstep(thresh - soft, thresh + soft, f)
    rim = smoothstep(soft * 2.5, 0.0, np.abs(f - thresh)) * (1 - inside * 0.5)
    return inside, rim


def drip_streaks(S, seed, sources, length=0.35, width=0.010, jitter=0.6):
    """Vertical downward streak intensity originating at source points [(x, y, strength), ...]."""
    yy, xx = grid(S)
    out = np.zeros((S, S))
    r = mn.rng(seed)
    wob = (mn.fbm(S, (6, 24), 3, seed + 1) - 0.5) * 0.02
    for (sx, sy, st) in sources:
        for _ in range(int(2 + r.integers(0, 3))):
            ox = sx + (r.random() - 0.5) * width * 6 * jitter
            w = width * r.uniform(0.4, 1.4)
            L = length * r.uniform(0.4, 1.3)
            dx = mn.pdelta(xx + wob, ox)
            dy = np.mod(yy - sy, 1.0)
            prof = np.exp(-(dx / w) ** 2) * np.exp(-dy / L) * smoothstep(0.0, 0.01, dy)
            out += prof * st * r.uniform(0.5, 1.0)
    return np.clip(out, 0, 1)


def vstreak_field(S, seed, fx=48, fy=3, sharp=2.0):
    """Generic fine vertical water-stain streaks (0..1)."""
    s = mn.fbm(S, (fy, fx), 4, seed, gain=0.55)
    s2 = mn.fbm(S, (fy * 2, fx * 2), 3, seed + 1)
    return np.clip(smoothstep(0.45, 0.95, s * 0.75 + s2 * 0.25), 0, 1) ** sharp


def rust_colour(S, seed, t=None):
    """Rust colour field (sRGB float)."""
    t = mn.fbm(S, 6, 6, seed) if t is None else t
    v = mn.fbm(S, 40, 3, seed + 1)
    c = tio.gradient_map(np.clip(t * 0.8 + v * 0.2, 0, 1), [
        (0.00, (44, 30, 24)), (0.25, (72, 44, 30)), (0.5, (102, 60, 36)),
        (0.72, (126, 78, 46)), (0.88, (140, 96, 60)), (1.0, (112, 88, 66))])
    return c


def steel_colour(S, seed, base=(150, 152, 155), var=0.08):
    v = mn.fbm(S, 8, 5, seed)
    c = np.ones((S, S, 3)) * tio.rgb(base)
    return np.clip(c * (1 + (v - 0.5)[..., None] * var * 2), 0, 1)


def grime(S, seed, freq=4):
    """Low-frequency dirt amount 0..1."""
    g = mn.warped_fbm(S, freq, 6, seed, warp_amt=0.06)
    return g


# =========================================================================== CONCRETE
@texset("concrete_wall", 2.4, notes="Damp dark cast concrete: formwork seam + tie holes with rust streaks, "
        "cracks with efflorescence, vertical water streaks, pores. One panel seam per repeat.")
def concrete_wall(S):
    sd = "concrete_wall"
    yy, xx = grid(S)
    macro = mn.fbm(S, 3, 6, seed_of(sd, "macro"))
    mid = mn.fbm(S, 10, 5, seed_of(sd, "mid"))
    micro = mn.fbm(S, 48, 3, seed_of(sd, "micro"), gain=0.6)
    grain = mn.fbm(S, (40, 3), 3, seed_of(sd, "grain"))           # plywood formwork imprint
    pore = pits(S, 1100, seed_of(sd, "pores"), 0.03, 0.15, keep=0.3)
    pore_big = pits(S, 90, seed_of(sd, "pores2"), 0.02, 0.08, keep=0.4)

    seam_y, seam_x = 0.62, 0.30
    dyS = np.abs(mn.pdelta(yy, seam_y))
    dxS = np.abs(mn.pdelta(xx, seam_x))
    wob = (mn.fbm(S, 16, 3, seed_of(sd, "seamwob")) - 0.5) * 0.004
    seam_h = smoothstep(0.0045, 0.0, np.abs(mn.pdelta(yy + wob, seam_y)))
    seam_v = smoothstep(0.0040, 0.0, np.abs(mn.pdelta(xx + wob, seam_x)))
    fin = np.maximum(seam_h, seam_v)
    step = np.mod(xx - seam_x, 1.0) * 0.025 + np.mod(yy - seam_y, 1.0) * 0.02   # panel misalignment

    # tie holes (4 per panel)
    holes = np.zeros((S, S))
    hole_rim = np.zeros((S, S))
    srcs = []
    for hx in (seam_x + 0.25, seam_x + 0.75):
        for hy in (seam_y + 0.25, seam_y + 0.75):
            hx, hy = hx % 1.0, hy % 1.0
            d = np.sqrt(mn.pdelta(xx, hx) ** 2 + mn.pdelta(yy, hy) ** 2)
            holes = np.maximum(holes, smoothstep(0.016, 0.006, d))
            hole_rim = np.maximum(hole_rim, smoothstep(0.03, 0.012, d) * (1 - smoothstep(0.016, 0.006, d)))
            srcs.append((hx, hy + 0.012, 1.0))
    rust = drip_streaks(S, seed_of(sd, "rust"), srcs, length=0.22, width=0.006)

    cr = crack_mask(S, seed_of(sd, "crack"), n=10, width=0.02, coverage=0.36)
    cr_wide = mn.blur(cr, 5)
    eff_src = mn.blur(np.maximum(cr, seam_h * 0.6), 2.0)
    # efflorescence & dark water run down from cracks / seam: smear downward (wrap)
    acc = np.zeros_like(eff_src)
    for k in range(1, 40, 2):
        acc += np.roll(eff_src, k, axis=0) * np.exp(-k / 14.0)
    run = np.clip(acc / 4.0, 0, 1) * vstreak_field(S, seed_of(sd, "runmod"), 60, 4, 0.6)
    streak = vstreak_field(S, seed_of(sd, "streak"), 52, 3, 1.3)
    seam_run = np.exp(-np.mod(yy - seam_y, 1.0) / 0.25) * vstreak_field(S, seed_of(sd, "seamrun"), 70, 3, 1.5)
    damp = smoothstep(0.3, 0.95, mn.warped_fbm(S, 3, 5, seed_of(sd, "damp"), warp_amt=0.1) * 0.8
                     + 0.2 * mn.fbm(S, 16, 4, seed_of(sd, "dampb")))
    wet = np.clip(damp * 0.6 + streak * 0.6 + seam_run * 0.7 + run * 0.5, 0, 1)

    height = (0.55 + 0.10 * (macro - 0.5) + 0.06 * (mid - 0.5) + 0.035 * (micro - 0.5) + 0.02 * (grain - 0.5)
              + step - 0.32 * pore - 0.2 * pore_big - 0.4 * cr - 0.05 * cr_wide + 0.05 * fin
              - 0.30 * holes + 0.02 * hole_rim)
    height = mn.norm01(height, 0.1, 99.9)

    mott = np.clip(mid * 0.6 + macro * 0.4, 0, 1)
    alb = tio.gradient_map(mott, [(0.0, (74, 77, 77)), (0.45, (94, 96, 95)), (0.8, (108, 109, 105)),
                                  (1.0, (118, 117, 111))])
    alb = tio.tint_var(alb, 0.04, seed_of(sd, "tint"), 5)
    speck = mn.value(S, 256, seed_of(sd, "speck"))
    alb = alb * (1 + 0.12 * (micro - 0.5))[..., None]
    alb = tio.mix(alb, alb * 1.25, smoothstep(0.93, 0.99, speck) * 0.6)
    alb = tio.mix(alb, alb * 0.6, smoothstep(0.07, 0.01, speck) * 0.6)
    alb = alb * (1 - 0.30 * damp - 0.28 * streak - 0.3 * seam_run - 0.2 * run)[..., None]
    alb = tio.mix(alb, tio.rgb(150, 151, 142), np.clip(run * 0.55 * (1 - damp), 0, 1))   # calcium bloom
    alb = tio.mix(alb, tio.rgb(88, 60, 42), np.clip(rust * 0.6 * mn.fbm(S, (6, 40), 3, seed_of(sd, "rv")) * 1.6, 0, 1))
    alb = alb * (1 - 0.4 * pore - 0.3 * pore_big)[..., None]
    alb = tio.mix(alb, tio.rgb(38, 38, 36), np.clip(cr * 0.85 + holes * 0.85, 0, 1))
    ao = mn.ambient_occlusion(height, (2, 5, 12), 2.0)
    alb = alb * (0.72 + 0.28 * ao)[..., None]

    smooth = 0.16 + 0.07 * micro + 0.30 * wet + 0.12 * cr_wide - 0.08 * run * (1 - damp) + 0.15 * rust
    return tio.finish(alb, height, 0.0, smooth, nstrength=18.0, ao_strength=1.6)


@texset("concrete_floor", 2.0, notes="Dark scuffed floor slab: saw-cut joint, exposed aggregate wear, "
        "oil stains (glossy), cracks, scuffs, grime.")
def concrete_floor(S):
    sd = "concrete_floor"
    yy, xx = grid(S)
    macro = mn.fbm(S, 3, 6, seed_of(sd, "macro"))
    mid = mn.fbm(S, 12, 5, seed_of(sd, "mid"))
    micro = mn.fbm(S, 64, 3, seed_of(sd, "micro"), gain=0.6)
    agg = mn.worley(S, 2200, seed_of(sd, "agg"), k=2)
    r = mn.rng(seed_of(sd, "aggc"))
    stone_tone = agg.per_cell(r.random(agg.n))
    srad = agg.per_cell(r.uniform(0.12, 0.42, agg.n))
    stone = smoothstep(srad, srad * 0.6, agg.f1) * agg.per_cell(r.random(agg.n) < 0.7)
    wear = smoothstep(0.45, 0.8, mn.warped_fbm(S, 4, 5, seed_of(sd, "wear"), warp_amt=0.08))
    exposed = stone * wear

    joint = smoothstep(0.004, 0.0015, np.abs(mn.pdelta(xx, 0.5)))
    joint_edge = smoothstep(0.012, 0.004, np.abs(mn.pdelta(xx, 0.5))) * (1 - joint)
    cr = crack_mask(S, seed_of(sd, "crack"), n=8, width=0.018, coverage=0.3)
    scuff = scratch_lines(S, 260, seed_of(sd, "scuff"), (0.01, 0.08), (0, np.pi), (0.6, 2.0), 0.4,
                          value=(0.2, 0.8))
    scuff = mn.blur(scuff, 0.6)
    oil, oil_rim = stain_blobs(S, seed_of(sd, "oil"), 3, 0.80, 0.06, 40)
    oil2, oil_rim2 = stain_blobs(S, seed_of(sd, "oil2"), 6, 0.86, 0.04, 15)
    oil = np.clip(oil + oil2 * 0.8, 0, 1) * (0.55 + 0.45 * mn.fbm(S, 12, 4, seed_of(sd, "oilv")))
    oil_rim = np.clip(oil_rim + oil_rim2, 0, 1)
    pore = pits(S, 1800, seed_of(sd, "pore"), 0.04, 0.18, keep=0.4)
    dirt = grime(S, seed_of(sd, "dirt"), 3)
    puddle_wet = smoothstep(0.6, 0.9, mn.warped_fbm(S, 2, 5, seed_of(sd, "wet"), warp_amt=0.12))

    height = (0.55 + 0.06 * (macro - 0.5) + 0.05 * (mid - 0.5) + 0.03 * (micro - 0.5)
              + 0.05 * exposed * (stone_tone - 0.3) - 0.35 * joint - 0.03 * joint_edge
              - 0.35 * cr - 0.2 * pore - 0.015 * scuff)
    height = mn.norm01(height, 0.1, 99.9)

    alb = tio.gradient_map(np.clip(mid * 0.6 + macro * 0.4, 0, 1),
                           [(0.0, (66, 67, 66)), (0.5, (84, 85, 82)), (1.0, (102, 101, 96))])
    alb = tio.tint_var(alb, 0.08, seed_of(sd, "tint"), 4)
    alb = alb * (1 + 0.14 * (micro - 0.5))[..., None]
    stone_col = tio.gradient_map(stone_tone, [(0, (70, 68, 64)), (0.5, (112, 108, 100)), (1, (140, 136, 128))])
    alb = tio.mix(alb, stone_col, exposed * 0.85)
    alb = alb * (1 - 0.35 * dirt * (1 - wear * 0.5))[..., None]
    alb = tio.mix(alb, alb * 1.35, scuff * 0.45)
    alb = tio.mix(alb, tio.rgb(30, 28, 26), oil * 0.7)
    alb = tio.mix(alb, tio.rgb(44, 40, 36), oil_rim * 0.25)
    alb = alb * (1 - 0.4 * pore)[..., None]
    alb = tio.mix(alb, tio.rgb(25, 25, 24), np.clip(cr * 0.9 + joint * 0.9, 0, 1))
    alb = alb * (1 - 0.25 * puddle_wet)[..., None]
    ao = mn.ambient_occlusion(height, (2, 5, 12), 2.0)
    alb = alb * (0.75 + 0.25 * ao)[..., None]

    smooth = (0.2 + 0.08 * micro + 0.12 * exposed + 0.5 * oil + 0.2 * oil_rim + 0.45 * puddle_wet
              - 0.08 * dirt - 0.06 * scuff)
    return tio.finish(alb, height, 0.0, np.clip(smooth, 0.05, 0.92), nstrength=16.0, ao_strength=1.6)


# =========================================================================== METALS
@texset("metal_grate", 1.0, cutout=True, notes="Bar floor grating, 16 serrated bearing bars x 8 cross bars per "
        "repeat; holes are alpha cutout (alpha test 0.5). Rust + mud in the joints.")
def metal_grate(S):
    sd = "metal_grate"
    yy, xx = grid(S)
    nb, nc = 16, 8
    db = np.abs(mn.pdelta(xx * nb, np.round(xx * nb))) * (S / nb)        # px to bearing bar centre
    dc = np.abs(mn.pdelta(yy * nc, np.round(yy * nc))) * (S / nc)        # px to cross bar centre
    tb, tc = 3.6, 3.0
    bar = smoothstep(tb + 0.7, tb - 0.7, db)
    cross = smoothstep(tc + 0.7, tc - 0.7, dc)
    alpha = np.maximum(bar, cross)
    prof_b = np.sqrt(np.clip((tb - db) / tb, 0, 1)) * 0.25 + 0.75
    notch = smoothstep(0.25, 0.0, np.abs(mn.pdelta(yy * 64, np.round(yy * 64))))   # serrations
    hb = prof_b * (1 - 0.18 * notch)
    hc = (np.sqrt(np.clip((tc - dc) / tc, 0, 1)) * 0.2 + 0.62)
    height = np.maximum(hb * bar, hc * cross)
    joint = bar * cross
    jd = np.sqrt(np.minimum(db, 12) ** 2 + np.minimum(dc, 12) ** 2)
    near_joint = smoothstep(14, 3, jd)

    macro = mn.fbm(S, 6, 5, seed_of(sd, "m"))
    rustn = mn.warped_fbm(S, 8, 6, seed_of(sd, "rust"), warp_amt=0.05)
    rust_amt = np.clip(smoothstep(0.45, 0.8, rustn) * 0.8 + near_joint * 0.5 * rustn + (1 - prof_b) * 0.6, 0, 1)
    steel = steel_colour(S, seed_of(sd, "st"), (96, 98, 99), 0.12)
    worn = notch * 0 + smoothstep(0.85, 1.0, hb) * bar * smoothstep(0.4, 0.7, macro)      # polished bar tops
    alb = tio.mix(steel, tio.rgb(150, 150, 148), worn * 0.6)
    rc = rust_colour(S, seed_of(sd, "rc"))
    alb = tio.mix(alb, rc * 0.85, rust_amt * 0.85)
    mud = smoothstep(0.5, 0.75, mn.fbm(S, 10, 5, seed_of(sd, "mud"))) * near_joint
    alb = tio.mix(alb, tio.rgb(52, 44, 36), np.clip(mud, 0, 1))
    scr = scratch_lines(S, 160, seed_of(sd, "scr"), (0.01, 0.05), (1.3, 1.85), (0.5, 1.0), 0.05)
    alb = tio.mix(alb, tio.rgb(165, 165, 162), scr * bar * 0.5)
    height = height - 0.05 * rust_amt * rustn - 0.03 * mud
    metal = np.clip(0.9 - rust_amt * 0.85 - mud, 0, 1) * alpha
    smooth = np.clip(0.38 + 0.25 * worn - 0.25 * rust_amt - 0.2 * mud + 0.1 * scr, 0.05, 0.9)
    ao = 1 - 0.5 * near_joint * (1 - joint * 0.3)
    return tio.finish(alb, height, metal, smooth, ao=ao, nstrength=6.0, ao_strength=0.6, alpha=alpha)


def _tread_pattern(S, cells=16, la=11.5, lb=3.3, sharp=1.35):
    yy, xx = grid(S)
    cy, cx = yy * cells, xx * cells
    iy, ix = np.floor(cy), np.floor(cx)
    fy, fx = (cy - iy - 0.5) * (S / cells), (cx - ix - 0.5) * (S / cells)
    sgn = np.where(((iy + ix) % 2) == 0, 1.0, -1.0)
    a = (fx + sgn * fy) / np.sqrt(2)
    b = (fx - sgn * fy) / np.sqrt(2)
    r = (np.abs(a) / la) ** sharp + (np.abs(b) / lb) ** 2
    cap = np.sqrt(np.clip(1 - r, 0, 1))
    return cap, smoothstep(1.05, 0.85, r)


@texset("metal_diamond", 1.0, notes="Worn steel diamond tread plate: polished bump tops, grime and rust in "
        "the valleys, scuffs.")
def metal_diamond(S):
    sd = "metal_diamond"
    cap, body = _tread_pattern(S)
    macro = mn.fbm(S, 4, 6, seed_of(sd, "m"))
    micro = mn.fbm(S, 64, 3, seed_of(sd, "mi"))
    dent = mn.fbm(S, 8, 4, seed_of(sd, "dent"))
    height = 0.35 + 0.55 * cap + 0.04 * (dent - 0.5) + 0.01 * micro
    pit = pits(S, 900, seed_of(sd, "pit"), 0.03, 0.16, keep=0.25) * (1 - body)
    height -= 0.06 * pit
    scr = scratch_lines(S, 420, seed_of(sd, "scr"), (0.02, 0.15), (0, np.pi), (0.5, 1.2), 0.2,
                        value=(0.3, 1.0))
    scuff = scratch_lines(S, 90, seed_of(sd, "scuff"), (0.03, 0.12), (-0.5, 0.5), (2.0, 5.0), 0.3,
                          value=(0.2, 0.5))
    scuff = mn.blur(scuff, 1.2)
    valley = 1 - body
    grime_amt = np.clip(valley * smoothstep(0.3, 0.75, mn.warped_fbm(S, 6, 5, seed_of(sd, "g"), warp_amt=0.05))
                        + valley * 0.25, 0, 1)
    rust_amt = smoothstep(0.55, 0.85, mn.warped_fbm(S, 5, 6, seed_of(sd, "r"), warp_amt=0.08)
                          * 0.6 + 0.4 * mn.fbm(S, 40, 3, seed_of(sd, "rb"))) * (0.25 + 0.75 * valley)
    polish = smoothstep(0.55, 0.95, cap) * (0.5 + 0.5 * macro)
    steel = steel_colour(S, seed_of(sd, "st"), (112, 113, 114), 0.15)
    alb = tio.mix(steel, tio.rgb(170, 170, 168), polish * 0.7)
    alb = tio.mix(alb, tio.rgb(178, 178, 175), np.clip(scr * 0.6 + scuff * 0.3, 0, 1))
    alb = tio.mix(alb, tio.rgb(46, 42, 38), grime_amt * 0.8)
    alb = tio.mix(alb, rust_colour(S, seed_of(sd, "rc")) * 0.8, rust_amt * 0.85)
    alb = tio.mix(alb, tio.rgb(40, 32, 26), pit * 0.8)
    metal = np.clip(1.0 - grime_amt * 0.8 - rust_amt * 0.9, 0, 1)
    smooth = np.clip(0.45 + 0.3 * polish - 0.25 * grime_amt - 0.3 * rust_amt + 0.08 * scr - 0.1 * micro,
                     0.05, 0.92)
    return tio.finish(alb, height, metal, smooth, nstrength=7.0, ao_strength=1.0)


@texset("metal_rusted", 1.5, notes="Heavily rusted steel: flaking scale, pitting, rust bloom, run streaks, "
        "remnants of old grey paint and exposed steel.")
def metal_rusted(S):
    sd = "metal_rusted"
    yy, xx = grid(S)
    macro = mn.fbm(S, 3, 6, seed_of(sd, "macro"))
    mid = mn.warped_fbm(S, 8, 6, seed_of(sd, "mid"), warp_amt=0.06)
    fine = mn.fbm(S, 48, 4, seed_of(sd, "fine"), gain=0.6)
    wy, wx = mn.warp_field(S, 6, 14, seed_of(sd, "fw"))
    flakes = mn.worley(S, 220, seed_of(sd, "flk"), warp_px=(wy, wx))
    r = mn.rng(seed_of(sd, "flkr"))
    flake_on = flakes.per_cell(r.random(flakes.n) < 0.55) * smoothstep(0.35, 0.6, mid)
    flake_lift = flakes.per_cell(r.uniform(0.0, 1.0, flakes.n))
    flake_h = (flake_on * (0.08 + 0.05 * flake_lift) + flake_on * smoothstep(0.25, 0.0, flakes.edge) * 0.05)
    flake_gap = smoothstep(0.06, 0.0, flakes.edge) * flake_on
    pit = pits(S, 3600, seed_of(sd, "pit"), 0.04, 0.22, keep=0.4, irregular=2.5) * \
        smoothstep(0.3, 0.7, mn.fbm(S, 6, 4, seed_of(sd, "pitm")))
    pit2 = pits(S, 260, seed_of(sd, "pit2"), 0.04, 0.16, keep=0.3, irregular=5.0)
    paint = smoothstep(0.7, 0.75, mn.warped_fbm(S, 4, 6, seed_of(sd, "paint"), warp_amt=0.1)) * (1 - flake_on)
    steel_x = smoothstep(0.82, 0.9, mn.fbm(S, 10, 5, seed_of(sd, "sx"))) * (1 - paint)
    run = vstreak_field(S, seed_of(sd, "run"), 40, 3, 1.2)

    height = (0.45 + 0.12 * (macro - 0.5) + 0.12 * (mid - 0.5) + 0.06 * (fine - 0.5) + flake_h
              - 0.22 * pit - 0.25 * pit2 - 0.12 * flake_gap + 0.05 * paint - 0.06 * steel_x)
    height = mn.norm01(height, 0.2, 99.8)

    t = np.clip(mid * 0.45 + macro * 0.3 + fine * 0.2 + flake_lift * flake_on * 0.2 - 0.05, 0, 1)
    alb = rust_colour(S, seed_of(sd, "rc"), t)
    bloom = smoothstep(0.55, 0.85, mn.fbm(S, 20, 4, seed_of(sd, "bloom")))
    alb = tio.mix(alb, tio.rgb(150, 92, 50), bloom * 0.35 * (1 - paint))
    alb = tio.mix(alb, tio.rgb(40, 27, 20), np.clip(pit * 0.7 + pit2 * 0.75 + flake_gap * 0.6, 0, 1))
    alb = tio.mix(alb, tio.rgb(76, 80, 76) * (0.8 + 0.4 * fine)[..., None], paint * 0.85)
    alb = tio.mix(alb, tio.rgb(80, 78, 76), steel_x * 0.85)
    alb = alb * (1 - 0.25 * run * (1 - paint))[..., None]
    ao = mn.ambient_occlusion(height, (2, 6, 14), 2.0)
    alb = alb * (0.7 + 0.3 * ao)[..., None]
    metal = np.clip(steel_x * 0.75, 0, 1)
    smooth = np.clip(0.14 + 0.06 * fine + 0.2 * paint + 0.25 * steel_x + 0.12 * run - 0.05 * bloom, 0.04, 0.8)
    return tio.finish(alb, height, metal, smooth, nstrength=12.0, ao_strength=1.2)


@texset("metal_painted", 1.0, notes="Neutral light-grey worn industrial paint (tint the albedo in the material: "
        "green/grey/yellow/red). Chips reveal primer, steel and rust; rust bleed streaks.")
def metal_painted(S):
    sd = "metal_painted"
    macro = mn.fbm(S, 4, 6, seed_of(sd, "macro"))
    peel = mn.fbm(S, 96, 2, seed_of(sd, "peel"))           # orange peel
    f = (0.55 * mn.warped_fbm(S, 5, 6, seed_of(sd, "chip"), warp_amt=0.09)
         + 0.3 * mn.fbm(S, 24, 4, seed_of(sd, "chip2")) + 0.15 * mn.fbm(S, 64, 2, seed_of(sd, "chip3")))
    th = 0.70
    edge_soft = 0.006
    chip = smoothstep(th - edge_soft, th + edge_soft, f)
    deep = smoothstep(th + 0.025, th + 0.04, f)
    primer = chip * (1 - deep)
    scr = scratch_lines(S, 220, seed_of(sd, "scr"), (0.01, 0.09), (0, np.pi), (0.5, 1.2), 0.25, value=(0.5, 1))
    scr = np.clip(scr * 1.3, 0, 1) * (1 - chip)
    rust_vs_steel = smoothstep(0.4, 0.6, mn.fbm(S, 10, 4, seed_of(sd, "rvs")))
    expose_rust = deep * rust_vs_steel
    expose_steel = np.clip(deep * (1 - rust_vs_steel) + scr * 0.8, 0, 1)
    # rust bleed below chips
    src = mn.blur(expose_rust, 1.5)
    acc = np.zeros_like(src)
    for k in range(1, 60, 2):
        acc += np.roll(src, k, axis=0) * np.exp(-k / 22.0)
    bleed = np.clip(acc / 5.0, 0, 1) * vstreak_field(S, seed_of(sd, "bl"), 80, 4, 0.7) * (1 - chip)
    dirt = smoothstep(0.35, 0.95, mn.warped_fbm(S, 3, 6, seed_of(sd, "dirt"), warp_amt=0.1))
    streak = vstreak_field(S, seed_of(sd, "streak"), 60, 3, 2.0)

    height = 0.62 + 0.01 * (peel - 0.5) + 0.03 * (macro - 0.5) - 0.12 * chip - 0.1 * deep - 0.03 * scr
    rim = smoothstep(0.02, 0.0, np.abs(f - th)) * (1 - chip)
    height += 0.02 * rim
    height = np.clip(height, 0, 1)

    paint = tio.gradient_map(macro, [(0, (196, 197, 195)), (0.5, (208, 208, 205)), (1, (216, 215, 211))])
    paint = paint * (1 + 0.025 * (peel - 0.5))[..., None]
    paint = paint * (1 - 0.18 * dirt - 0.12 * streak)[..., None]
    paint = tio.mix(paint, tio.rgb(150, 112, 84), bleed * 0.55)
    alb = tio.mix(paint, tio.rgb(92, 84, 78), primer)           # dark grey-brown primer
    alb = tio.mix(alb, rust_colour(S, seed_of(sd, "rc")), expose_rust)
    alb = tio.mix(alb, steel_colour(S, seed_of(sd, "st"), (128, 129, 130), 0.1), expose_steel)
    metal = np.clip(expose_steel * 0.9, 0, 1)
    smooth = np.clip(0.42 + 0.04 * peel - 0.14 * dirt - 0.2 * primer - 0.25 * expose_rust + 0.1 * expose_steel
                     - 0.1 * bleed, 0.05, 0.9)
    return tio.finish(alb, height, metal, smooth, nstrength=6.0, ao_strength=0.8)


@texset("metal_bare", 0.5, notes="Brushed / scratched bare steel for tool heads and rails; fingerprints, "
        "tarnish and small rust spots.")
def metal_bare(S):
    sd = "metal_bare"
    brush = mn.fbm(S, (256, 2), 2, seed_of(sd, "brush"), gain=0.6)
    brush2 = mn.fbm(S, (128, 4), 3, seed_of(sd, "brush2"))
    macro = mn.fbm(S, 4, 5, seed_of(sd, "macro"))
    scr = scratch_lines(S, 500, seed_of(sd, "scr"), (0.02, 0.25), (0, np.pi), (0.4, 1.0), 0.05, value=(0.3, 1))
    scr2 = scratch_lines(S, 120, seed_of(sd, "scr2"), (0.05, 0.4), (-0.15, 0.15), (0.5, 1.4), 0.02, value=(0.4, 1))
    scr = np.clip(scr + scr2, 0, 1)
    tarnish = smoothstep(0.45, 0.9, mn.warped_fbm(S, 4, 6, seed_of(sd, "tarn"), warp_amt=0.1))
    rust = smoothstep(0.84, 0.9, mn.fbm(S, 14, 5, seed_of(sd, "rust"))) * smoothstep(0.5, 0.8, tarnish)
    smudge = smoothstep(0.55, 0.85, mn.fbm(S, 10, 4, seed_of(sd, "smudge")))
    height = 0.5 + 0.05 * (brush - 0.5) + 0.02 * (brush2 - 0.5) - 0.06 * scr + 0.04 * rust
    steel = tio.gradient_map(np.clip(brush * 0.75 + macro * 0.25, 0, 1),
                             [(0, (150, 152, 155)), (0.5, (170, 171, 173)), (1, (186, 187, 188))])
    alb = tio.mix(steel, tio.rgb(196, 197, 198), scr * 0.5)
    alb = tio.mix(alb, tio.rgb(120, 116, 108), tarnish * 0.25 * (0.6 + 0.8 * mn.fbm(S, 32, 3, seed_of(sd, "tb"))))
    alb = tio.mix(alb, rust_colour(S, seed_of(sd, "rc")), rust)
    metal = np.clip(1.0 - rust * 0.9 - tarnish * 0.15, 0, 1)
    smooth = np.clip(0.62 + 0.12 * (brush - 0.5) - 0.2 * tarnish - 0.18 * smudge - 0.4 * rust + 0.05 * scr,
                     0.05, 0.92)
    return tio.finish(alb, height, metal, smooth, nstrength=5.0, ao_strength=0.3)


@texset("hazard_stripes", 1.0, notes="Worn black/yellow 45 degree caution stripes (4 pairs per repeat along U), "
        "paint wear to steel, scuffs, grime.")
def hazard_stripes(S):
    sd = "hazard_stripes"
    wy, wx = mn.warp_field(S, 24, 1.2, seed_of(sd, "w"), octaves=3)
    s = mn.wave_lines(S, 4, 4, warp_px=(wy, wx))
    yellow = smoothstep(0.495, 0.505, s) * smoothstep(1.0, 0.99, s) + smoothstep(0.01, 0.0, s)
    yellow = np.clip(yellow, 0, 1)
    macro = mn.fbm(S, 4, 6, seed_of(sd, "m"))
    f = 0.45 * mn.warped_fbm(S, 8, 6, seed_of(sd, "chip"), warp_amt=0.06) + 0.55 * mn.fbm(S, 32, 3, seed_of(sd, "c2"))
    chip = smoothstep(0.71, 0.72, f)
    scuff = mn.blur(scratch_lines(S, 160, seed_of(sd, "scuff"), (0.03, 0.15), (-0.4, 0.4), (1, 4), 0.2,
                                  value=(0.2, 0.7)), 1.0)
    dirt = smoothstep(0.3, 0.95, mn.warped_fbm(S, 3, 6, seed_of(sd, "dirt"), warp_amt=0.1))
    fade = mn.fbm(S, 8, 4, seed_of(sd, "fade"))
    yel = tio.gradient_map(fade, [(0, (176, 138, 28)), (0.5, (196, 156, 36)), (1, (206, 170, 58))])
    blk = tio.gradient_map(fade, [(0, (26, 26, 25)), (1, (40, 39, 37))])
    alb = tio.mix(blk, yel, yellow)
    alb = alb * (1 - 0.3 * dirt)[..., None]
    alb = tio.mix(alb, alb * 0.6 + 0.12, scuff * 0.5)
    steel = steel_colour(S, seed_of(sd, "st"), (96, 96, 96), 0.2)
    rc = rust_colour(S, seed_of(sd, "rc"))
    under = tio.mix(steel, rc, smoothstep(0.4, 0.6, mn.fbm(S, 12, 4, seed_of(sd, "u"))))
    alb = tio.mix(alb, under, chip)
    height = 0.6 + 0.02 * (macro - 0.5) - 0.12 * chip + 0.01 * yellow - 0.02 * scuff
    metal = chip * 0.6
    smooth = np.clip(0.38 - 0.15 * dirt - 0.1 * scuff - 0.15 * chip + 0.05 * yellow, 0.05, 0.9)
    return tio.finish(alb, height, metal, smooth, nstrength=6.0, ao_strength=0.6)


@texset("rubber", 0.5, notes="Dark worn rubber (cables, grips, hoses): ozone micro-cracks, abrasion, dust in pores.")
def rubber(S):
    sd = "rubber"
    macro = mn.fbm(S, 4, 5, seed_of(sd, "m"))
    stip = mn.fbm(S, 128, 2, seed_of(sd, "stip"))
    oz = mn.worley(S, 700, seed_of(sd, "oz"), aspect=(1, 7), k=2)
    ozc = smoothstep(0.05, 0.0, oz.edge) * smoothstep(0.55, 0.8, mn.fbm(S, 6, 4, seed_of(sd, "ozm")))
    abr = mn.blur(scratch_lines(S, 200, seed_of(sd, "abr"), (0.02, 0.1), (0, np.pi), (1, 3), 0.2,
                                value=(0.2, 0.6)), 1.0)
    dust = smoothstep(0.5, 0.9, mn.warped_fbm(S, 4, 5, seed_of(sd, "dust"), warp_amt=0.1))
    height = 0.5 + 0.03 * (macro - 0.5) + 0.02 * (stip - 0.5) - 0.2 * ozc - 0.02 * abr
    alb = tio.gradient_map(macro, [(0, (36, 36, 37)), (1, (50, 49, 49))])
    alb = alb * (1 + 0.08 * (stip - 0.5))[..., None]
    alb = tio.mix(alb, tio.rgb(66, 64, 60), np.clip(abr * 0.6 + dust * 0.35, 0, 1))
    alb = tio.mix(alb, tio.rgb(22, 22, 22), ozc * 0.8)
    smooth = np.clip(0.36 + 0.08 * (stip - 0.5) - 0.18 * dust - 0.12 * abr + 0.06 * macro, 0.05, 0.8)
    return tio.finish(alb, height, 0.0, smooth, nstrength=8.0, ao_strength=0.6)


@texset("plastic", 0.5, notes="Neutral light moulded plastic (tinted in Unity: yellow/orange/black/gray); "
        "fine texture, scuffs, scratches, grime.")
def plastic(S):
    sd = "plastic"
    macro = mn.fbm(S, 4, 5, seed_of(sd, "m"))
    tex = mn.fbm(S, 128, 2, seed_of(sd, "tex"))
    scr = scratch_lines(S, 300, seed_of(sd, "scr"), (0.02, 0.12), (0, np.pi), (0.4, 1.0), 0.3, value=(0.3, 1))
    scuff = mn.blur(scratch_lines(S, 120, seed_of(sd, "scuff"), (0.02, 0.1), (0, np.pi), (2, 6), 0.3,
                                  value=(0.2, 0.6)), 1.5)
    dirt = smoothstep(0.4, 0.95, mn.warped_fbm(S, 3, 6, seed_of(sd, "dirt"), warp_amt=0.1))
    height = 0.5 + 0.012 * (tex - 0.5) + 0.02 * (macro - 0.5) - 0.04 * scr
    alb = tio.gradient_map(macro, [(0, (198, 198, 196)), (1, (212, 211, 208))])
    alb = alb * (1 - 0.07 * dirt)[..., None]
    alb = tio.mix(alb, alb * 1.06, scr * 0.6)
    alb = tio.mix(alb, alb * 0.8, scuff * 0.6)
    smooth = np.clip(0.58 + 0.04 * (tex - 0.5) - 0.18 * dirt - 0.25 * scuff - 0.2 * scr, 0.05, 0.9)
    return tio.finish(alb, height, 0.0, smooth, nstrength=5.0, ao_strength=0.4)


# =========================================================================== ROCK
def facets(S, n, seed, slope=1.0, warp_amt=0.0, warp_freq=6, offset=0.3):
    """Fractured planar facets: each Voronoi cell is a randomly tilted plane (tileable)."""
    wp = mn.warp_field(S, warp_freq, warp_amt, seed + 3) if warp_amt else None
    c = mn.worley(S, n, seed, warp_px=wp)
    r = mn.rng(seed + 1)
    sp = np.sqrt(1.0 / n)
    a = c.per_cell(r.normal(0, slope, c.n))
    b = c.per_cell(r.normal(0, slope, c.n))
    o = c.per_cell(r.random(c.n))
    h = (a * c.dx + b * c.dy) / sp + o * offset
    return h, c


def facets_aniso(S, n, seed, slope, aspect, warp_amt=0.0, offset=0.3):
    """Like facets() but with stretched cells (aspect=(ay, ax); ax>ay -> tall shards)."""
    wp = mn.warp_field(S, 6, warp_amt, seed + 3) if warp_amt else None
    c = mn.worley(S, n, seed, aspect=aspect, warp_px=wp)
    r = mn.rng(seed + 1)
    sp = np.sqrt(1.0 / n)
    a = c.per_cell(r.normal(0, slope, c.n))
    b = c.per_cell(r.normal(0, slope, c.n))
    o = c.per_cell(r.random(c.n))
    h = (a * c.dx + b * c.dy) / sp + o * offset
    return h, c


def rock_height(S, seed, big=16, small=80, slope=0.9, ridge_w=0.25, crack_cov=0.4, warp_amt=24):
    f1, c1 = facets(S, big, seed, slope, warp_amt)
    f2, c2 = facets(S, small, seed + 50, slope * 0.8, warp_amt * 0.4, 12)
    rid = mn.fbm(S, 4, 6, seed + 7, mode="ridged")
    det = mn.fbm(S, 32, 4, seed + 8)
    fine = mn.fbm(S, 96, 2, seed + 9)
    cr = crack_mask(S, seed + 11, n=12, width=0.02, coverage=crack_cov)
    h = 0.42 * f1 + 0.18 * f2 + ridge_w * rid + 0.07 * det + 0.02 * fine - 0.25 * cr
    h = mn.blur(h, 0.7)
    h = mn.norm01(h, 0.5, 99.5)
    return dict(h=h, c1=c1, c2=c2, rid=rid, det=det, fine=fine, crack=cr)


def lichen(S, seed, cov=0.75, freq=10):
    f = mn.warped_fbm(S, freq, 5, seed, warp_amt=0.04) * 0.7 + 0.3 * mn.fbm(S, 48, 3, seed + 1)
    return smoothstep(cov, cov + 0.04, f), smoothstep(cov - 0.03, cov, f)


@texset("rock_dry", 3.0, notes="Dry grey-brown fractured rock (cliffs, boulders, terrain B channel): facets, "
        "cracks, dust on ledges, sparse lichen. Works triplanar.")
def rock_dry(S):
    sd = "rock_dry"
    R = rock_height(S, seed_of(sd, "h"))
    h = R["h"]
    r = mn.rng(seed_of(sd, "tone"))
    tone = R["c1"].per_cell(r.random(R["c1"].n)) * 0.6 + R["c2"].per_cell(r.random(R["c2"].n)) * 0.4
    macro = mn.fbm(S, 3, 5, seed_of(sd, "macro"))
    yy, xx = grid(S)
    strata = 0.5 + 0.5 * np.sin(TAU * (3 * xx + 7 * yy) + 4 * mn.fbm(S, 4, 4, seed_of(sd, "st")))
    t = np.clip(0.45 * tone + 0.3 * macro + 0.15 * R["det"] + 0.1 * strata + 0.15 * (h - 0.5), 0, 1)
    alb = tio.gradient_map(t, [(0, (64, 61, 56)), (0.4, (90, 86, 79)), (0.75, (112, 106, 97)),
                               (1, (134, 127, 116))])
    alb = tio.tint_var(alb, 0.06, seed_of(sd, "tint"), 6)
    alb = alb * (1 + 0.15 * (R["fine"] - 0.5))[..., None]
    cvx = mn.convexity(h, 3)
    dust = np.clip(smoothstep(0.0, 0.04, cvx) * 0.5 + smoothstep(0.55, 0.85, mn.fbm(S, 8, 4, seed_of(sd, "dust"))) * 0.4,
                   0, 1)
    alb = tio.mix(alb, tio.rgb(140, 132, 118), dust * 0.4)
    l1, l1e = lichen(S, seed_of(sd, "lichen"), 0.70)
    l2, _ = lichen(S, seed_of(sd, "lichen2"), 0.80, 16)
    alb = tio.mix(alb, tio.rgb(118, 124, 102) * (0.85 + 0.3 * R["fine"])[..., None], l1 * 0.8)
    alb = tio.mix(alb, tio.rgb(70, 72, 60), (l1e - l1) * 0.5)
    alb = tio.mix(alb, tio.rgb(138, 104, 62), l2 * 0.6)
    alb = tio.mix(alb, tio.rgb(36, 33, 30), R["crack"] * 0.85)
    ao = mn.ambient_occlusion(h, (2, 6, 16), 2.6)
    alb = alb * (0.5 + 0.5 * ao)[..., None]
    h2 = h + 0.03 * l1
    smooth = np.clip(0.14 + 0.1 * R["fine"] + 0.06 * (1 - dust) - 0.05 * l1, 0.04, 0.6)
    return tio.finish(alb, h2, 0.0, smooth, nstrength=9.0, ao_strength=1.5)


@texset("rock_wet", 3.0, notes="Dark wet rock: glossy water film in cavities and run streaks, drier matte "
        "ridges, algae tint. Works triplanar.")
def rock_wet(S):
    sd = "rock_wet"
    yy, xx = grid(S)
    R = rock_height(S, seed_of(sd, "h"), big=14, small=70, slope=1.0)
    h = R["h"]
    r = mn.rng(seed_of(sd, "tone"))
    tone = R["c1"].per_cell(r.random(R["c1"].n))
    macro = mn.fbm(S, 3, 5, seed_of(sd, "macro"))
    t = np.clip(0.4 * tone + 0.4 * macro + 0.2 * R["det"], 0, 1)
    alb = tio.gradient_map(t, [(0, (40, 39, 38)), (0.5, (56, 54, 51)), (1, (72, 68, 63))])
    alb = alb * (1 + 0.15 * (R["fine"] - 0.5))[..., None]
    cav = mn.cavity(h, 5)
    pool = smoothstep(0.005, 0.05, cav)
    run = vstreak_field(S, seed_of(sd, "run"), 36, 3, 0.9)
    film = np.clip(pool * 0.8 + run * 0.7 + smoothstep(0.4, 0.8, mn.fbm(S, 6, 4, seed_of(sd, "film"))) * 0.5, 0, 1)
    dry = smoothstep(0.02, 0.06, mn.convexity(h, 3)) * (1 - film)
    alb = alb * (1 - 0.3 * film)[..., None]
    alb = tio.mix(alb, tio.rgb(84, 80, 72), dry * 0.4)
    algae = smoothstep(0.55, 0.85, mn.warped_fbm(S, 5, 5, seed_of(sd, "alg"), warp_amt=0.08)) * film
    alb = tio.mix(alb, tio.rgb(34, 44, 32), algae * 0.6)
    calc = smoothstep(0.75, 0.9, run * mn.fbm(S, 12, 4, seed_of(sd, "calc")) * 1.6)
    alb = tio.mix(alb, tio.rgb(110, 108, 100), calc * 0.35)
    alb = tio.mix(alb, tio.rgb(22, 21, 20), R["crack"] * 0.9)
    ao = mn.ambient_occlusion(h, (2, 6, 16), 2.2)
    alb = alb * (0.62 + 0.38 * ao)[..., None]
    smooth = np.clip(0.3 + 0.55 * film + 0.08 * R["fine"] - 0.2 * dry - 0.05 * algae, 0.05, 0.95)
    return tio.finish(alb, h, 0.0, smooth, nstrength=9.0, ao_strength=1.5)


@texset("rock_mine", 3.0, notes="Dark brownish blasted mine rock: half-barrel drill holes, pick/chisel gouges, "
        "faceted fractures, dust on upward faces. Works triplanar.")
def rock_mine(S):
    sd = "rock_mine"
    yy, xx = grid(S)
    R = rock_height(S, seed_of(sd, "h"), big=10, small=60, slope=1.3, ridge_w=0.15, crack_cov=0.35)
    h = R["h"].copy()
    r = mn.rng(seed_of(sd, "tools"))
    # drill half-barrels (vertical, slightly wavy, partial length)
    drill = np.zeros((S, S))
    for k in range(3):
        x0 = (k + r.uniform(0.2, 0.8)) / 3.0
        rad = r.uniform(0.018, 0.026)
        wob = (mn.fbm(S, (2, 1), 2, seed_of(sd, "dw", k)) - 0.5) * 0.02
        d = np.abs(mn.pdelta(xx + wob, x0)) / rad
        seg = smoothstep(0.35, 0.5, mn.fbm(S, (2, 1), 3, seed_of(sd, "ds", k)))
        drill = np.maximum(drill, np.sqrt(np.clip(1 - d * d, 0, 1)) * seg)
    rings = 0.5 + 0.5 * np.sin(yy * TAU * 90)
    h = h - 0.28 * drill * (1 - 0.06 * rings)
    # pick / chisel gouges
    cv = tio.WrapCanvas(S, 2, "L", 0)
    for _ in range(140):
        x, y = r.random(2)
        a = r.normal(-0.9, 0.35)
        L = r.uniform(0.015, 0.05)
        w = r.uniform(1.5, 4.0)
        cv.line([(x, y), (x + np.cos(a) * L, y + np.sin(a) * L)], int(r.uniform(120, 255)), w)
    gouge = mn.blur(cv.array(), 1.2)
    h = h - 0.2 * gouge
    h = mn.norm01(h, 0.3, 99.7)
    n = mn.height_to_normal(h, 11.0)
    up = smoothstep(0.05, 0.35, n[..., 1])
    r2 = mn.rng(seed_of(sd, "tone"))
    tone = R["c1"].per_cell(r2.random(R["c1"].n))
    macro = mn.fbm(S, 3, 5, seed_of(sd, "macro"))
    t = np.clip(0.4 * tone + 0.4 * macro + 0.2 * R["det"], 0, 1)
    alb = tio.gradient_map(np.clip(t + 0.25 * (h - 0.5), 0, 1),
                           [(0, (42, 35, 29)), (0.5, (66, 55, 45)), (1, (96, 82, 67))])
    alb = alb * (1 + 0.22 * (R["fine"] - 0.5))[..., None]
    fresh = np.clip(gouge * 0.8 + drill * 0.3, 0, 1)
    alb = tio.mix(alb, tio.rgb(100, 90, 78), fresh * 0.4)
    alb = tio.mix(alb, tio.rgb(112, 102, 88), up * 0.35)
    soot = smoothstep(0.55, 0.85, mn.warped_fbm(S, 4, 5, seed_of(sd, "soot"), warp_amt=0.08))
    alb = alb * (1 - 0.3 * soot)[..., None]
    alb = tio.mix(alb, tio.rgb(28, 24, 21), R["crack"] * 0.9)
    ao = mn.ambient_occlusion(h, (2, 6, 16), 2.6)
    alb = alb * (0.5 + 0.5 * ao)[..., None]
    smooth = np.clip(0.16 + 0.08 * R["fine"] - 0.08 * up + 0.12 * fresh + 0.1 * soot, 0.04, 0.6)
    return tio.finish(alb, h, 0.0, smooth, normal=n, ao_strength=1.5)


TAU = 2 * np.pi


def veins(S, seed, freq=4, width=0.035, warp_amt=0.12, octaves=5):
    """Thin branching vein network 0..1 (iso-line of warped fBm)."""
    f = mn.warped_fbm(S, freq, octaves, seed, warp_amt=warp_amt)
    wv = width * (0.5 + mn.fbm(S, 8, 3, seed + 3))
    return smoothstep(wv, 0.0, np.abs(f - 0.5)), f


@texset("ore_iron", 1.5, notes="Iron ore: dark rock with metallic hematite/magnetite veins and flecks "
        "(metallic in mask R), red-brown oxide halos.")
def ore_iron(S):
    sd = "ore_iron"
    R = rock_height(S, seed_of(sd, "h"), big=12, small=70, slope=0.8)
    v1, _ = veins(S, seed_of(sd, "v1"), 3, 0.06)
    v2, _ = veins(S, seed_of(sd, "v2"), 6, 0.035)
    v3, _ = veins(S, seed_of(sd, "v3"), 12, 0.03)
    vein = np.clip(v1 + v2 * 0.8 + v3 * 0.5, 0, 1)
    halo = np.clip(mn.blur(vein, 6) * 2.5, 0, 1)
    fl = pits(S, 2600, seed_of(sd, "fl"), 0.05, 0.25, keep=0.35, irregular=2.0)
    fl = np.clip(fl * 3, 0, 1) * smoothstep(0.35, 0.7, mn.fbm(S, 6, 4, seed_of(sd, "flm")) + halo * 0.3)
    metal_m = np.clip(vein + fl, 0, 1)
    h = R["h"] + 0.06 * vein + 0.03 * fl
    macro = mn.fbm(S, 3, 5, seed_of(sd, "m"))
    rock = tio.gradient_map(np.clip(0.5 * macro + 0.3 * R["det"] + 0.2 * R["fine"], 0, 1),
                            [(0, (48, 45, 42)), (0.5, (64, 60, 55)), (1, (80, 74, 67))])
    rock = tio.mix(rock, tio.rgb(92, 52, 38), halo * 0.55 * (0.5 + mn.fbm(S, 16, 3, seed_of(sd, "hv"))))
    metal_col = tio.gradient_map(mn.fbm(S, 24, 3, seed_of(sd, "mc")), [(0, (104, 106, 112)), (1, (150, 150, 154))])
    alb = tio.mix(rock, metal_col, metal_m)
    alb = tio.mix(alb, tio.rgb(30, 28, 26), R["crack"] * 0.85)
    ao = mn.ambient_occlusion(h, (2, 6, 14), 2.0)
    alb = alb * (0.65 + 0.35 * ao)[..., None]
    smooth = np.clip(0.18 + 0.1 * R["fine"] + 0.4 * metal_m, 0.04, 0.8)
    return tio.finish(alb, h, metal_m * 0.9, smooth, nstrength=9.0, ao_strength=1.3)


@texset("ore_copper", 1.5, notes="Copper ore: grey-brown rock with metallic red-orange native copper veins, "
        "green malachite / verdigris patina crusts around them (matte).")
def ore_copper(S):
    sd = "ore_copper"
    R = rock_height(S, seed_of(sd, "h"), big=12, small=70, slope=0.8)
    v1, _ = veins(S, seed_of(sd, "v1"), 3, 0.035)
    v2, _ = veins(S, seed_of(sd, "v2"), 7, 0.022)
    vein = np.clip(v1 + v2 * 0.7, 0, 1)
    halo = np.clip(mn.blur(vein, 11) * 3.5, 0, 1)
    bot = mn.worley(S, 1400, seed_of(sd, "bot"))
    bubbles = np.clip(1 - bot.f1 * 1.4, 0, 1)
    pat_f = halo * (0.4 + 0.9 * mn.fbm(S, 12, 4, seed_of(sd, "pf")))
    patina = smoothstep(0.25, 0.5, pat_f) * (1 - vein)
    tarnish = smoothstep(0.4, 0.7, mn.fbm(S, 20, 3, seed_of(sd, "tarn")))
    h = R["h"] + 0.05 * vein + patina * (0.04 + 0.05 * bubbles)
    macro = mn.fbm(S, 3, 5, seed_of(sd, "m"))
    rock = tio.gradient_map(np.clip(0.5 * macro + 0.3 * R["det"] + 0.2 * R["fine"], 0, 1),
                            [(0, (62, 58, 52)), (0.5, (82, 76, 68)), (1, (100, 93, 82))])
    cu = tio.mix(np.ones((S, S, 3)) * tio.rgb(176, 104, 68), np.ones((S, S, 3)) * tio.rgb(124, 70, 46), tarnish)
    pat_c = tio.gradient_map(mn.fbm(S, 16, 4, seed_of(sd, "pc")) * 0.7 + bubbles * 0.3,
                             [(0, (38, 84, 64)), (0.5, (58, 116, 88)), (0.8, (84, 140, 116)), (1, (110, 150, 132))])
    alb = tio.mix(rock, pat_c, patina)
    alb = tio.mix(alb, cu, vein)
    alb = tio.mix(alb, tio.rgb(32, 30, 28), R["crack"] * 0.85)
    ao = mn.ambient_occlusion(h, (2, 6, 14), 2.0)
    alb = alb * (0.65 + 0.35 * ao)[..., None]
    smooth = np.clip(0.18 + 0.08 * R["fine"] + 0.38 * vein * (1 - tarnish * 0.5) - 0.06 * patina, 0.04, 0.8)
    return tio.finish(alb, h, vein * 0.95, smooth, nstrength=9.0, ao_strength=1.3)


@texset("crystal", 0.6, emission=True, notes="Pale cyan luminous crystal facets; internal fractures and cloudy "
        "inclusions; _E emission glows strongest along fractures and facet cores.")
def crystal(S):
    sd = "crystal"
    f1, c1 = facets_aniso(S, 26, seed_of(sd, "f1"), 1.6, (1.0, 2.6), 10, offset=0.5)
    f2, c2 = facets_aniso(S, 110, seed_of(sd, "f2"), 0.9, (2.2, 1.0), 4, offset=0.2)
    h = mn.norm01(0.7 * f1 + 0.25 * f2 + 0.05 * mn.fbm(S, 32, 3, seed_of(sd, "d")), 0.5, 99.5)
    edge = smoothstep(0.08, 0.0, c1.edge)
    edge2 = smoothstep(0.06, 0.0, c2.edge)
    frac = crack_mask(S, seed_of(sd, "frac"), n=16, width=0.012, coverage=0.7, warp_amt=8, wiggle=1.0)
    r = mn.rng(seed_of(sd, "tone"))
    tone = c1.per_cell(r.random(c1.n)) * 0.7 + c2.per_cell(r.random(c2.n)) * 0.3
    cloud = mn.warped_fbm(S, 6, 5, seed_of(sd, "cloud"), warp_amt=0.1)
    core = np.clip(1 - c1.f1 * 1.1, 0, 1)
    alb = tio.gradient_map(np.clip(tone * 0.75 + cloud * 0.25, 0, 1),
                           [(0, (70, 128, 150)), (0.4, (110, 176, 194)), (0.75, (150, 206, 218)), (1, (186, 230, 236))])
    alb = alb * (0.85 + 0.3 * smoothstep(0.3, 1.0, h))[..., None]
    alb = tio.mix(alb, tio.rgb(214, 238, 240), np.clip(edge * 0.4 + edge2 * 0.15 + frac * 0.7, 0, 1))
    alb = tio.mix(alb, tio.rgb(70, 100, 112), smoothstep(0.6, 0.85, cloud) * 0.35)
    glow = np.clip(0.25 + 0.45 * core * tone + 0.8 * frac + 0.25 * edge + 0.15 * cloud, 0, 1.3)
    emis = tio.mix(np.ones((S, S, 3)) * tio.rgb(16, 64, 80), np.ones((S, S, 3)) * tio.rgb(120, 230, 245),
                   np.clip(glow, 0, 1))
    emis = emis * np.clip(glow, 0.2, 1.0)[..., None]
    smooth = np.clip(0.9 - 0.25 * frac - 0.1 * edge2, 0.3, 0.97)
    return tio.finish(alb, h, 0.0, smooth, nstrength=6.0, ao_strength=0.6, emission=emis)


@texset("blackstone", 1.0, notes="Near-black light-absorbing glassy stone (obsidian-like): conchoidal ripple "
        "fractures, faint violet sheen (slight metallic/violet spec on glassy faces), matte weathered patches.")
def blackstone(S):
    sd = "blackstone"
    f1, c1 = facets(S, 20, seed_of(sd, "f1"), 1.1, 14, offset=0.4)
    wy, wx = mn.warp_field(S, 6, 10, seed_of(sd, "rw"))
    c = mn.worley(S, 20, seed_of(sd, "f1"), warp_px=(wy, wx))
    rip = 0.5 + 0.5 * np.sin(c.f1 * 38.0 + mn.fbm(S, 8, 3, seed_of(sd, "rp")) * 6)
    rip = rip * smoothstep(1.2, 0.2, c.f1)
    f2, c2 = facets(S, 120, seed_of(sd, "f2"), 0.6, 4, offset=0.1)
    matte = smoothstep(0.55, 0.8, mn.warped_fbm(S, 4, 5, seed_of(sd, "matte"), warp_amt=0.1))
    h = mn.norm01(0.6 * f1 + 0.1 * f2 + 0.05 * rip + 0.04 * matte * mn.fbm(S, 64, 2, seed_of(sd, "mt")), 0.5, 99.5)
    edge = smoothstep(0.05, 0.0, c1.edge)
    sheen = mn.fbm(S, 5, 4, seed_of(sd, "sheen"))
    alb = tio.gradient_map(sheen, [(0, (14, 13, 16)), (0.5, (20, 18, 24)), (1, (30, 24, 38))])
    alb = tio.mix(alb, tio.rgb(40, 38, 42), matte * 0.6)
    alb = tio.mix(alb, tio.rgb(46, 42, 52), edge * 0.5)
    metal = np.clip(0.3 * (1 - matte) * smoothstep(0.4, 0.8, sheen), 0, 1)
    smooth = np.clip(0.88 - 0.5 * matte - 0.15 * edge + 0.04 * rip, 0.2, 0.96)
    return tio.finish(alb, h, metal, smooth, nstrength=5.0, ao_strength=0.8, clamp=False)


@texset("anomalous", 1.0, emission=True, notes="Fleshy red/black organic-metal: dark plated metal with "
        "bulging vein network; _E emission glows red-orange in the veins and nodes.")
def anomalous(S):
    sd = "anomalous"
    wy, wx = mn.warp_field(S, 4, 30, seed_of(sd, "w"))
    c = mn.worley(S, 26, seed_of(sd, "cells"), warp_px=(wy, wx))
    wy2, wx2 = mn.warp_field(S, 10, 6, seed_of(sd, "w2"))
    c2 = mn.worley(S, 110, seed_of(sd, "cells2"), warp_px=(wy2 + wy * 0.3, wx2 + wx * 0.3))
    v_big = smoothstep(0.09, 0.0, c.edge)
    v_small = smoothstep(0.06, 0.0, c2.edge) * smoothstep(0.3, 0.6, mn.fbm(S, 5, 4, seed_of(sd, "vm")))
    v_fine, _ = veins(S, seed_of(sd, "fine"), 8, 0.02, 0.1)
    vein = np.clip(v_big + v_small * 0.75 + v_fine * 0.5, 0, 1)
    node = smoothstep(0.25, 0.0, c.f3 - c.f1) * v_big
    flesh_m = smoothstep(0.4, 0.7, mn.warped_fbm(S, 5, 5, seed_of(sd, "flesh"), warp_amt=0.1))
    plate = np.clip(c.f1 * 0.8, 0, 1)
    wet = mn.fbm(S, 24, 4, seed_of(sd, "wet"))
    h = (0.45 + 0.12 * plate * (1 - flesh_m) + 0.05 * (wet - 0.5) + 0.25 * np.sqrt(v_big)
         + 0.12 * v_small + 0.06 * v_fine + 0.08 * node)
    h = mn.blur(h, 0.8)
    metal_c = tio.gradient_map(mn.fbm(S, 12, 4, seed_of(sd, "mc")), [(0, (30, 26, 27)), (1, (54, 46, 46))])
    flesh_c = tio.gradient_map(wet, [(0, (46, 12, 14)), (0.5, (70, 18, 20)), (1, (92, 30, 30))])
    alb = tio.mix(metal_c, flesh_c, flesh_m)
    vein_c = tio.gradient_map(np.clip(vein, 0, 1), [(0, (66, 14, 14)), (1, (124, 30, 22))])
    alb = tio.mix(alb, vein_c, np.clip(vein * 1.2, 0, 1))
    alb = tio.mix(alb, tio.rgb(16, 8, 9), smoothstep(0.04, 0.12, c.edge) * smoothstep(0.2, 0.12, c.edge) * 0.6)
    pulse = mn.fbm(S, 6, 3, seed_of(sd, "pulse"))
    glow = np.clip(vein * (0.35 + 0.65 * pulse) + node * 0.8, 0, 1)
    emis = tio.gradient_map(glow, [(0, (0, 0, 0)), (0.4, (90, 10, 4)), (0.8, (220, 50, 16)), (1, (255, 120, 50))])
    metal = np.clip(0.75 * (1 - flesh_m) * (1 - vein), 0, 1)
    smooth = np.clip(0.55 + 0.25 * flesh_m + 0.2 * vein + 0.1 * wet, 0.2, 0.95)
    return tio.finish(alb, h, metal, smooth, nstrength=8.0, ao_strength=1.2, emission=emis)


@texset("mineral_crust", 1.0, notes="Crusted mineral growths over stone: botryoidal nodules, pale chalky crust "
        "with ochre/rust staining, small crystalline glints (smoothness).")
def mineral_crust(S):
    sd = "mineral_crust"
    R = rock_height(S, seed_of(sd, "h"), big=10, small=50, slope=0.7, crack_cov=0.3)
    cov = smoothstep(0.3, 0.7, mn.warped_fbm(S, 4, 6, seed_of(sd, "cov"), warp_amt=0.1) * 0.75
                     + 0.25 * mn.fbm(S, 24, 3, seed_of(sd, "covb")))
    b1 = mn.worley(S, 160, seed_of(sd, "b1"))
    b2 = mn.worley(S, 900, seed_of(sd, "b2"))
    b3 = mn.worley(S, 3500, seed_of(sd, "b3"))
    nod = (np.sqrt(np.clip(1 - b1.f1 ** 2 * 0.8, 0, 1)) * 0.5 + np.sqrt(np.clip(1 - b2.f1 ** 2 * 0.8, 0, 1)) * 0.3
           + np.sqrt(np.clip(1 - b3.f1 ** 2 * 0.8, 0, 1)) * 0.2)
    crust_h = cov * (0.25 + 0.35 * nod)
    h = mn.norm01(R["h"] * 0.6 + crust_h, 0.5, 99.5)
    stain = mn.warped_fbm(S, 5, 5, seed_of(sd, "stain"), warp_amt=0.1)
    stone = tio.gradient_map(np.clip(R["det"] * 0.5 + R["fine"] * 0.5, 0, 1),
                             [(0, (60, 57, 53)), (1, (92, 87, 80))])
    crust = tio.gradient_map(np.clip(stain * 0.7 + nod * 0.3, 0, 1),
                             [(0, (110, 92, 68)), (0.35, (134, 122, 102)), (0.7, (156, 150, 134)),
                              (1, (172, 168, 156))])
    green = smoothstep(0.7, 0.85, mn.fbm(S, 7, 4, seed_of(sd, "green")))
    crust = tio.mix(crust, tio.rgb(120, 132, 112), green * 0.5)
    alb = tio.mix(stone, crust, smoothstep(0.05, 0.6, cov) * (0.75 + 0.25 * nod))
    alb = alb * (0.85 + 0.15 * smoothstep(0.0, 0.8, nod))[..., None]
    alb = tio.mix(alb, tio.rgb(34, 32, 30), R["crack"] * (1 - cov) * 0.85)
    ao = mn.ambient_occlusion(h, (2, 5, 12), 2.2)
    alb = alb * (0.62 + 0.38 * ao)[..., None]
    glint = smoothstep(0.9, 0.97, mn.value(S, 256, seed_of(sd, "glint"))) * cov
    smooth = np.clip(0.18 + 0.05 * R["fine"] + 0.6 * glint - 0.06 * cov, 0.04, 0.9)
    return tio.finish(alb, h, 0.0, smooth, nstrength=8.0, ao_strength=1.4)
