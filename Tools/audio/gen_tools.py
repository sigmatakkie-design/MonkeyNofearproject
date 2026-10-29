"""Tool / item sounds (Tools/): pickaxe on ores, flashlight, spear, flare, scanner, drops."""
from __future__ import annotations

import numpy as np
import scipy.signal as sps

from mnf_dsp import *  # noqa: F401,F403
from mnf_sfx import *  # noqa: F401,F403
from mnf_registry import category

S = category("Tools")


# --------------------------------------------------------------------- pickaxe core layers
def pick_head(rng, decay=0.12):
    """Steel pick head ring (mostly damped by the hand on the shaft)."""
    return strike("metal_bar", rng.uniform(1900, 2700), 0.6, rng, hardness=0.98, decay=decay, noise=0.3)


def rock_crack(rng, f0=None, dur=0.3, bright=14000):
    f0 = f0 or rng.uniform(650, 1100)
    return strike("stone", f0, dur, rng, hardness=0.97, decay=1.0, noise=0.7, n_modes=34, noise_f=(1500, bright))


def chips(rng, dur=0.45, rate=70, smax=0.25):
    return crumble(dur, rng, [(0, 1), (dur * 0.9, 0)], rate=rate, smin=0.02, smax=smax, dust=0.3)


def pick_impact(rng, ring=None, ring_amt=0.6, chip_amt=0.35, crack_amt=1.0, thud_amt=0.5, dur=0.8):
    out = np.zeros(ns(dur))
    place(out, crack_amt * norm(rock_crack(rng)), 0)
    place(out, thud_amt * norm(thump(0.3, rng, 190, 90, 0.06, 0.6, 1200)), 0)
    place(out, 0.22 * norm(pick_head(rng)), 0)
    if ring is not None:
        place(out, ring_amt * norm(ring), 0)
    place(out, chip_amt * norm(chips(rng)), rng.uniform(0.012, 0.03))
    return early_reflections(out, rng, 4, 0.02, 0.18)


@S("pick_hit_rock", variants=4, dur=0.6, desc="Pickaxe on plain rock: sharp stone crack, chips skittering.")
def pick_hit_rock(rng, v):
    return pick_impact(rng)


@S("pick_hit_iron", variants=3, dur=1.0, desc="Pickaxe on iron ore: metallic ring over the stone crack.")
def pick_hit_iron(rng, v):
    ring = strike("metal", rng.uniform(640, 900), 1.3, rng, hardness=0.95, decay=0.45, noise=0.1)
    return pick_impact(rng, ring, 0.75, 0.25, 0.8, dur=1.3)


@S("pick_hit_copper", variants=3, dur=0.8, desc="Pickaxe on copper ore: softer, warmer metallic tone.")
def pick_hit_copper(rng, v):
    ring = lp(strike("metal", rng.uniform(380, 560), 1.0, rng, hardness=0.8, decay=0.3, noise=0.05), 4500, n=2)
    return pick_impact(rng, ring, 0.7, 0.25, 0.65, dur=1.0)


@S("pick_hit_crystal", variants=3, dur=1.8, desc="Pickaxe on crystal: glassy chime with a sinking, beating, subtly wrong resonance.")
def pick_hit_crystal(rng, v):
    d = 2.2
    n = ns(d)
    f0 = rng.uniform(1700, 2500)
    glass = strike("glass", f0, d, rng, hardness=0.98, decay=0.9, noise=0.15)
    # the wrong part: a tritone partial set that slowly sinks in pitch (physically impossible)
    sink = 1.0 - rng.uniform(0.025, 0.045) * np.clip(tt(n) / 1.6, 0, 1) ** 1.5
    fr, t6, am = material_modes("glass", f0 * 1.4142, rng, decay=1.2)
    wrong = modal(n, fr, t6, am, rng, glide=sink)
    hum = (np.sin(2 * np.pi * 110 * tt(n)) + np.sin(2 * np.pi * 111.7 * tt(n))) * env_ar(n, 0.2, 1.8)
    shimmer = 1 + 0.3 * np.sin(2 * np.pi * rng.uniform(5, 8) * tt(n))
    ring = norm(glass) + 0.5 * norm(wrong) * shimmer + 0.035 * norm(hum)
    return pick_impact(rng, ring, 0.9, 0.2, 0.55, 0.3, dur=d)


@S("pick_hit_blackstone", variants=3, dur=0.4, desc="Pickaxe on blackstone: dead, dull, swallowed thud, almost no ring.")
def pick_hit_blackstone(rng, v):
    n = ns(0.45)
    dull = strike("stone", rng.uniform(280, 420), 0.45, rng, hardness=0.55, decay=0.25, noise=0.2, n_modes=12)
    dull = lp(dull, 2200, n=2)
    th = thump(0.45, rng, 120, 48, 0.12, 0.6, 500)
    y = mix(norm(dull), 0.9 * norm(th))
    # swallowed: unnaturally fast choke after the hit, then a faint sub drop
    choke = env_pts(len(y), [(0, 1), (0.03, 1), (0.06, 0.12), (0.45, 0.0)])
    sub = np.sin(2 * np.pi * phase_cycles(env_pts(n, [(0, 55), (0.4, 32)]))) * env_pts(n, [(0, 0), (0.05, 0.25), (0.4, 0)])
    return mix(y * choke, 0.3 * sub)


@S("pick_hit_anomalous", variants=3, dur=1.4, desc="Pickaxe on anomalous ore: wet organic squelch with a low unnatural throbbing tone.")
def pick_hit_anomalous(rng, v):
    d = 1.6
    n = ns(d)
    hit = strike("stone", rng.uniform(500, 700), 0.2, rng, hardness=0.75, decay=0.5, noise=0.3)
    wet = wet_squelch(0.6, rng, 280, 950, 5.0, 9, 0.005)
    f0 = env_pts(n, [(0, rng.uniform(62, 70)), (d, rng.uniform(48, 54))])
    groan = formant(glottal(f0, rng, 0.02, 0.15, 0.7, 0.1, 0.2), vowel_tracks(n, [(0, "o"), (d, "u")], 0.5))
    throb = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(5, 7) * tt(n))
    tone = (norm(groan) + 0.6 * np.sin(2 * np.pi * phase_cycles(f0 * 1.01))) * env_ar(n, 0.05, 1.4) * throb
    out = mix(0.7 * norm(hit), norm(wet), 0.6 * norm(tone))
    return early_reflections(out, rng, 4, 0.02, 0.15)


@S("pick_miss_metal", variants=2, dur=0.45, desc="Pick glancing off metal: short screeching scrape.")
def pick_miss_metal(rng, v):
    d = 0.5
    s = scrape(d, rng, [(0, 1), (0.25, 0.55), (0.45, 0.0)], "metal", rng.uniform(900, 1300),
               rng.uniform(1500, 2200), 0.4, 0.4, (2000, 12000), 0.5)
    hit = strike("metal", rng.uniform(1100, 1500), 0.6, rng, hardness=0.95, decay=0.35)
    out = mix(norm(hit) * 0.7, norm(s))
    return out


@S("ore_break", variants=3, dur=0.8, desc="Ore deposit stage breaking: crack + crumble of chunks.")
def ore_break(rng, v):
    out = np.zeros(ns(1.0))
    place(out, norm(rock_crack(rng, rng.uniform(450, 650), 0.3)), 0)
    place(out, 0.7 * norm(thump(0.4, rng, 140, 60, 0.12, 0.8, 900)), 0)
    place(out, 0.8 * crumble(0.75, rng, [(0, 1), (0.15, 0.8), (0.75, 0)], 120, 0.08, 0.6), 0.02)
    return early_reflections(out, rng, 4, 0.025, 0.18)


@S("ore_break_final", variants=2, dur=1.5, desc="Ore deposit final collapse: big crack, rumble and rubble.")
def ore_break_final(rng, v):
    d = 1.6
    out = np.zeros(ns(d + 0.3))
    place(out, norm(rock_crack(rng, rng.uniform(380, 520), 0.4)), 0)
    place(out, 0.6 * norm(rock_crack(rng, rng.uniform(600, 900), 0.3)), rng.uniform(0.05, 0.1))
    place(out, 0.9 * norm(thump(0.8, rng, 110, 45, 0.4, 0.9, 700)), 0)
    place(out, 0.9 * crumble(d, rng, [(0, 1), (0.35, 1), (d, 0)], 170, 0.15, 0.9, dust=0.35), 0.03)
    n = ns(d)
    rum = lp(white(n, rng), 220, n=2) * env_pts(n, [(0, 0), (0.05, 1), (0.6, 0.6), (d, 0)])
    place(out, 0.35 * norm(rum), 0)
    return early_reflections(out, rng, 5, 0.03, 0.2)


@S("ore_pickup", variants=3, dur=0.3, desc="Picking up an ore chunk: stone clink against stone.")
def ore_pickup(rng, v):
    out = np.zeros(ns(0.35))
    f = rng.uniform(1600, 2600)
    a = strike("stone", f, 0.2, rng, hardness=0.9, decay=2.2, noise=0.3, n_modes=14)
    b = strike("stone", f * rng.uniform(1.2, 1.5), 0.15, rng, hardness=0.9, decay=1.8, noise=0.3, n_modes=12)
    place(out, norm(a), 0.01)
    place(out, 0.5 * norm(b), rng.uniform(0.05, 0.09))
    place(out, 0.25 * fabric(0.15, rng, [(0, 0), (0.01, 1), (0.15, 0)], 200, 400, 4000), 0)
    return out


# --------------------------------------------------------------------- flashlight
@S("flashlight_on", dur=0.12, desc="Flashlight tail-switch click on.")
def flashlight_on(rng, v):
    out = np.zeros(ns(0.15))
    place(out, 0.7 * click(rng, "plastic", 2100, 0.06, 0.85, 0.7, body_f=300), 0)
    place(out, click(rng, "metal", 4200, 0.05, 0.98, 0.3), 0.011)
    return out


@S("flashlight_off", dur=0.12, desc="Flashlight tail-switch click off (lower, softer).")
def flashlight_off(rng, v):
    out = np.zeros(ns(0.15))
    place(out, click(rng, "metal", 3500, 0.05, 0.95, 0.3), 0)
    place(out, 0.6 * click(rng, "plastic", 1700, 0.06, 0.8, 0.7, body_f=260), 0.009)
    return out


@S("flashlight_flicker_loop", loop=True, dur=2.0, desc="Failing flashlight: intermittent contact buzz and crackle (seamless 2 s loop).")
def flashlight_flicker_loop(rng, v):
    L, X = ns(2.0), ns(0.12)
    n = L + X
    gate = rand_walk01(n, 7.0, rng)
    gate = np.clip((gate - 0.45) * 6, 0, 1)
    gate = lp(gate, 60)
    exc = stick_slip(n, 120 + 40 * smooth_rand(n, 3, rng), rng, 0.25, 0.6)
    buzz = bw(sps.fftconvolve(exc, resonator_ir("metal_thin", 1300, rng, 0.02, 0.3))[:n], "bandpass", (500, 9000), 2)
    crack = grit(n / SR, rng, 40 + 300 * np.abs(np.gradient(gate)) * SR / 50, 2000, 12000)[:n]
    hum = np.sin(2 * np.pi * 120 * tt(n)) * 0.3 + np.sin(2 * np.pi * 240 * tt(n)) * 0.15
    hiss = band_noise(n, rng, 2000, 10000) * 0.03
    y = norm(buzz) * gate + 0.3 * norm(crack) + 0.15 * hum * gate + hiss
    return loopify(y, L, X)


@S("battery_low", dur=0.35, desc="Weak, sagging double beep: battery low.", norm=("peak", -4.0))
def battery_low(rng, v):
    out = np.zeros(ns(0.4))
    place(out, beep(1800, 0.09, rng, "tri", 0.004, 0.04, droop=0.06), 0)
    place(out, 0.8 * beep(1350, 0.13, rng, "tri", 0.004, 0.07, droop=0.1), 0.16)
    wob = 1 - 0.3 * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * tt(len(out))))
    return out * wob


# --------------------------------------------------------------------- spear
@S("spear_stab_flesh", variants=3, dur=0.5, desc="Spear stab into flesh: swish, wet puncture, gristle crunch.")
def spear_stab_flesh(rng, v):
    out = np.zeros(ns(0.7))
    place(out, 0.35 * whoosh(0.18, rng, 0.8, 300, 2000, 1.2, 0.05), 0)
    t0 = 0.12
    place(out, norm(thump(0.3, rng, rng.uniform(140, 170), 60, 0.12, 0.8, 600)), t0)
    place(out, 0.9 * norm(wet_squelch(0.4, rng, 700, 220, 4.0, 4, 0.004)), t0)
    for _ in range(rng.integers(2, 5)):
        place(out, 0.35 * click(rng, "bone", rng.uniform(1000, 2600), 0.04, 0.9, 1.0), t0 + rng.uniform(0.0, 0.08))
    tear = band_noise(ns(0.12), rng, 800, 5000) * env_ar(ns(0.12), 0.01, 0.08) * stick_slip(ns(0.12), 300, rng, 0.8, 0.8).clip(0) * 5
    place(out, 0.3 * norm(lp(tear + 1e-9, 5000)), t0 + 0.01)
    return out


@S("spear_hit_hard", variants=2, dur=0.5, desc="Spear tip striking stone/hard surface; shaft buzzes in the hand.")
def spear_hit_hard(rng, v):
    out = np.zeros(ns(0.7))
    place(out, 0.7 * norm(rock_crack(rng, rng.uniform(800, 1200), 0.2)), 0)
    place(out, 0.5 * norm(strike("metal_bar", rng.uniform(2400, 3000), 0.4, rng, 0.98, 0.25)), 0)
    shaft = strike("wood", rng.uniform(130, 180), 0.5, rng, hardness=0.8, decay=1.6, noise=0.0)
    buzz = ks_pluck(rng.uniform(85, 110), 0.5, rng, 0.93, 0.6)
    place(out, 0.6 * norm(shaft), 0)
    place(out, 0.25 * norm(lp(buzz, 2500)), 0.002)
    return out


@S("spear_hit_wood", variants=2, dur=0.6, desc="Spear thunking into wood; shaft wobbles.")
def spear_hit_wood(rng, v):
    d = 0.7
    n = ns(d)
    hit = strike("wood", rng.uniform(200, 300), d, rng, hardness=0.85, decay=1.2, noise=0.3)
    th = thump(0.3, rng, 170, 90, 0.07, 0.6, 900)
    twang = lp(ks_pluck(rng.uniform(110, 150), d, rng, 0.955, 0.55), 1800)
    wob = 1 + 0.6 * np.sin(2 * np.pi * rng.uniform(17, 24) * tt(n)) * env_exp(n, 0.5)
    return mix(norm(hit), 0.6 * norm(th), 0.35 * norm(twang) * wob)


# --------------------------------------------------------------------- light sources
@S("glowstick_crack", dur=0.7, desc="Glowstick bent: plastic creak, inner glass vial snaps, liquid shake.")
def glowstick_crack(rng, v):
    out = np.zeros(ns(0.8))
    place(out, 0.4 * creak(0.16, rng, [(0, 60), (0.16, 220)], "plastic", 900, decay=0.5), 0)
    snap = mix(norm(strike("glass", rng.uniform(3000, 4000), 0.15, rng, 1.0, 0.08, 0.6)),
               0.6 * rustle(0.06, rng, [(0, 1), (0.06, 0)], 3000, 3000, 12000, 0.2))
    place(out, snap, 0.15)
    place(out, 0.5 * norm(strike("glass", rng.uniform(4000, 5200), 0.1, rng, 1.0, 0.06, 0.5)), 0.24)
    slosh = wet_squelch(0.3, rng, 900, 1600, 3.0, 5, 0.05, bub_f=(800, 2500))
    place(out, 0.15 * norm(slosh), 0.38)
    return out


@S("flare_ignite", dur=1.2, desc="Road flare struck: scratch, fwoomph ignition, sputtering into hiss.")
def flare_ignite(rng, v):
    d = 1.3
    n = ns(d)
    out = np.zeros(n)
    place(out, 0.7 * scrape(0.16, rng, [(0, 1), (0.16, 0.3)], "stone", 1200, 2500, 0.8, 1.0, (1500, 12000), 0.3), 0)
    t1 = 0.14
    m = n - ns(t1)
    cf = env_pts(m, [(0, 300), (0.08, 3000), (1.2, 5000)])
    fw = tvf(white(m, rng), "lp", cf, 0.8) * env_pts(m, [(0, 0), (0.03, 1), (0.25, 0.45), (1.2, 0.35)])
    hiss = band_noise(m, rng, 2500, 13000) * env_pts(m, [(0, 0), (0.1, 0.4), (0.3, 0.7), (1.2, 0.7)]) * (0.6 + 0.4 * rand_walk01(m, 25, rng))
    pops = grit(m / SR, rng, lambda t: 25 + 150 * np.exp(-t / 0.25), 1500, 8000)[:m]
    place(out, norm(fw) + 0.5 * norm(hiss) + 0.35 * norm(pops), t1)
    return out


@S("flare_burn_loop", loop=True, dur=3.0, desc="Burning flare: hissing, sputtering crackle (seamless 3 s loop).")
def flare_burn_loop(rng, v):
    L, X = ns(3.0), ns(0.2)
    n = L + X
    hiss = band_noise(n, rng, 2000, 14000, -1) * (0.7 + 0.3 * rand_walk01(n, 20, rng))
    roar = lp(white(n, rng), 600, n=2) * (0.5 + 0.5 * rand_walk01(n, 9, rng))
    pops = grit(n / SR, rng, 60, 1500, 9000)[:n]
    sput = stick_slip(n, 18, rng, 0.8, 0.9)
    sput = sps.fftconvolve(sput, norm(band_noise(ns(0.01), rng, 800, 6000)) * env_exp(ns(0.01), 0.008))[:n]
    y = norm(hiss) + 0.6 * norm(roar) + 0.4 * norm(pops) + 0.3 * norm(sput)
    return loopify(y, L, X)


@S("noisemaker_rattle", variants=3, dur=1.1, desc="Tin can full of bolts shaken hard: loud metallic rattle.")
def noisemaker_rattle(rng, v):
    strokes = int(rng.integers(3, 6))
    d = 0.2 * strokes + 0.4
    n = ns(d)
    exc = np.zeros(n)
    bolts = np.zeros(n)
    bbank = [strike("metal_bar", rng.uniform(2200, 4800), 0.15, rng, 0.98, 0.2, 0.2) for _ in range(8)]
    t = 0.0
    for k in range(strokes):
        period = rng.uniform(0.17, 0.23)
        for _ in range(int(rng.integers(8, 16))):
            ti = t + abs(rng.normal(0.012, 0.018))
            a = rng.uniform(0.3, 1.0)
            i = ns(ti)
            if i < n:
                exc[i] += a
                place(bolts, bbank[rng.integers(8)] * a * 0.5, ti)
        exc[min(ns(t), n - 1)] += 2.0  # can wall reversal knock
        t += period
    can_ir = resonator_ir("metal_thin", rng.uniform(520, 700), rng, 0.4, 0.7)
    can = sps.fftconvolve(exc, can_ir)[:n]
    y = norm(can) + 0.6 * norm(bolts)
    return sat(norm(y), 1.5)


# --------------------------------------------------------------------- electronics
@S("scanner_beep", dur=0.15, desc="Ore scanner ping (electronic).")
def scanner_beep(rng, v):
    n = ns(0.2)
    b = beep(1400, 0.06, rng, "sine", 0.003, 0.02, harm=0.25)
    tail = np.sin(2 * np.pi * 1400 * tt(n)) * env_exp(n, 0.12, 0.05) * 0.25
    return mix(b, speaker(tail, drive=1.1) * 0.4)


@S("scanner_beep_strong", dur=0.2, desc="Ore scanner strong signal: brighter rapid double beep.")
def scanner_beep_strong(rng, v):
    out = np.zeros(ns(0.22))
    for k in range(2):
        place(out, beep(2100, 0.05, rng, "square", 0.002, 0.012, harm=0.1), 0.09 * k)
    return out


@S("rope_unroll", dur=2.0, desc="Climbing rope thrown down / unrolling: fibre rustle and coil flops.")
def rope_unroll(rng, v):
    d = 2.0
    out = np.zeros(ns(d + 0.2))
    place(out, 0.6 * fabric(d, rng, [(0, 0), (0.1, 1), (1.3, 0.8), (1.8, 0.2), (2.0, 0)], 260, 300, 3500), 0)
    t, gap = 0.12, 0.11
    while t < 1.75:
        th = mix(norm(thump(0.15, rng, 150, 80, 0.05, 1.0, 500)), 0.5 * fabric(0.1, rng, [(0, 1), (0.1, 0)], 300, 300, 3000))
        place(out, th * rng.uniform(0.3, 0.6), t)
        t += gap * rng.uniform(0.8, 1.2)
        gap *= 1.12
    place(out, 0.9 * mix(norm(thump(0.25, rng, 130, 60, 0.1, 1.0, 700)), 0.6 * fabric(0.2, rng, [(0, 1), (0.2, 0)], 400)), 1.82)
    return out


@S("medkit_use", dur=1.5, desc="Medkit: latches snap, lid opens, bandage wrapped, tape torn.")
def medkit_use(rng, v):
    out = np.zeros(ns(1.6))
    place(out, click(rng, "metal", 3200, 0.06, 0.95, 0.4, body_f=400), 0)
    place(out, 0.9 * click(rng, "metal", 3500, 0.06, 0.95, 0.4, body_f=420), 0.07)
    place(out, 0.3 * creak(0.2, rng, [(0, 40), (0.2, 90)], "plastic", 700, decay=0.5), 0.12)
    place(out, 0.5 * fabric(0.3, rng, [(0, 0), (0.05, 1), (0.3, 0)], 250, 500, 6000), 0.32)
    for k in range(3):
        place(out, 0.55 * rustle(0.22, rng, [(0, 0), (0.06, 1), (0.22, 0)], 700, 2500, 11000, 0.5), 0.6 + 0.2 * k)
    n = ns(0.18)
    rip = band_noise(n, rng, 1500, 9000) * stick_slip(n, 450, rng, 0.6, 0.6).clip(0) * 6 + band_noise(n, rng, 2000, 8000) * 0.4
    place(out, 0.6 * norm(rip * env_pts(n, [(0, 0), (0.02, 1), (0.18, 0)])), 1.25)
    return out


@S("marker_deploy", dur=0.6, desc="Marker beacon stuck into the ground (thunk) then arming beep.")
def marker_deploy(rng, v):
    out = np.zeros(ns(0.6))
    place(out, norm(thump(0.25, rng, 180, 80, 0.08, 0.9, 1000)), 0)
    place(out, 0.4 * click(rng, "plastic", 1200, 0.1, 0.8, 0.8), 0)
    place(out, 0.15 * grit(0.15, rng, lambda t: 300 * np.exp(-t / 0.04)), 0)
    n = ns(0.16)
    f = env_pts(n, [(0, 1200), (0.07, 1250), (0.08, 1800), (0.16, 1800)])
    b = speaker(np.sin(2 * np.pi * phase_cycles(f)) * env_pts(n, [(0, 0), (0.004, 1), (0.14, 1), (0.16, 0)]), drive=1.2)
    place(out, 0.5 * b, 0.32)
    return out


@S("marker_blip", dur=0.12, desc="Marker beacon periodic soft blip.", norm=("peak", -3.0))
def marker_blip(rng, v):
    n = ns(0.14)
    f = env_pts(n, [(0, 900), (0.03, 1400), (0.14, 1450)])
    x = np.sin(2 * np.pi * phase_cycles(f)) * env_ar(n, 0.003, 0.1)
    return speaker(x, drive=1.1)


# --------------------------------------------------------------------- drops
def drop(rng, mat, f0, dur, bounces=3, gap=0.2, e=0.5, hardness=0.85, decay=1.0, floor_amt=0.4, settle=0,
         grit_amt=0.0, noise=0.3):
    out = np.zeros(ns(dur))
    modes = material_modes(mat, f0, rng, decay=decay)
    ts, gs = bounce_times(rng, 0.0, gap, e, bounces)
    for t, g in zip(ts, gs):
        fr, t6, am = modes
        am2 = am * rng.uniform(0.3, 1.3, len(am))  # different contact point each bounce
        hit = strike(mat, f0, dur - t, rng, hardness, noise=noise, modes=(fr, t6, am2))
        fl = thump(0.15, rng, 180, 90, 0.04, 0.7, 1200)
        place(out, g * mix(norm(hit), floor_amt * norm(fl)), t)
        if grit_amt:
            place(out, g * grit_amt * norm(grit(0.15, rng, lambda tt_: 300 * np.exp(-tt_ / 0.03))), t)
    t = ts[-1]
    for k in range(settle):
        t += rng.uniform(0.02, 0.04)
        fr, t6, am = modes
        place(out, 0.08 * norm(strike(mat, f0, 0.3, rng, hardness, noise=noise, modes=(fr, t6 * 0.5, am * rng.uniform(0.2, 1, len(am))))), t)
    return out


@S("item_drop_metal", variants=3, dur=1.0, desc="Small metal item dropped: clank and bounces.")
def item_drop_metal(rng, v):
    return drop(rng, "metal", rng.uniform(520, 1100), 1.4, int(rng.integers(3, 5)), rng.uniform(0.16, 0.24), 0.5,
                0.9, rng.uniform(0.35, 0.6), 0.3, settle=3)


@S("item_drop_wood", variants=2, dur=0.6, desc="Wooden item dropped: knock and bounces.")
def item_drop_wood(rng, v):
    return drop(rng, "wood", rng.uniform(260, 420), 0.8, 3, rng.uniform(0.12, 0.17), 0.45, 0.8, 1.1, 0.5, settle=2)


@S("item_drop_soft", variants=2, dur=0.35, desc="Soft item (food / cloth) dropped: padded thump.")
def item_drop_soft(rng, v):
    out = np.zeros(ns(0.45))
    place(out, norm(thump(0.3, rng, rng.uniform(140, 190), 70, 0.08, 1.2, 600)), 0)
    place(out, 0.5 * fabric(0.25, rng, [(0, 1), (0.25, 0)], 300, 300, 4000), 0)
    place(out, 0.25 * norm(thump(0.15, rng, 170, 90, 0.04, 1.2, 600)), rng.uniform(0.07, 0.1))
    return out


@S("item_drop_stone", variants=3, dur=0.6, desc="Stone / ore chunk dropped: knock, bounce, grit.")
def item_drop_stone(rng, v):
    return drop(rng, "stone", rng.uniform(550, 950), 0.8, 3, rng.uniform(0.1, 0.15), 0.4, 0.9, 1.6, 0.8,
                grit_amt=0.15, noise=0.5)
