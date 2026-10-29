"""Creature sounds (Creatures/).

Sonic identities:
  Hollowback    - big, wet, rattling airways; ragged choking vocals (formant scale ~0.6); palm-slap gallop.
  Rabbit        - tiny, nasal sniffs, soft thumps, harrowing high squeal.
  Falsekin      - mimicry gone wrong: slowed / detuned copies, chitin clicks, ring-modulated screech.
  Boar          - nasal grunts, pig squeal, snorting gallop.
  Gloomrat      - high chirp squeaks, tiny claws.
  Ceiling Clerk - fingernail taps, jaw clicks, dry raspy inhaled screech.
  Borer         - sub-bass, rock grinding, enormous low formants (scale ~0.38).
  Lantern Mourner - breathy nasal hum that wavers, electrical interference, distant sad wail.
  Gaunt         - colossal, far away, long reverb.
"""
from __future__ import annotations

import numpy as np
import scipy.signal as sps

from mnf_dsp import *  # noqa: F401,F403
from mnf_sfx import *  # noqa: F401,F403
from mnf_registry import category

S = category("Creatures")


def voiced(dur, f0_pts, seq, rng, scale=1.0, amp_pts=None, bw_scale=1.0, **gkw):
    n = ns(dur)
    f0 = env_pts(n, f0_pts) if isinstance(f0_pts, list) else f0_pts
    src = glottal(f0, rng, **gkw)
    seq_ = seq if isinstance(seq, list) else [(0, seq)]
    y = formant(src, vowel_tracks(n, seq_, scale, bw_scale))
    if amp_pts:
        y = y * env_pts(n, amp_pts)
    return norm(y)


def rattle_env(n, rng, rate=24.0, depth=0.6):
    """Wet airway flutter: irregular amplitude interruptions at ~rate Hz."""
    imp = stick_slip(n, rate, rng, 0.35, 0.4)
    sm = lp(np.abs(imp), rate * 1.5, n=2)
    sm = sm / (peak(sm) + 1e-9)
    return 1 - depth * np.clip(sm * 1.8, 0, 1)


def gurgle(dur, rng, rate=40.0, f=(180, 700)):
    out = np.zeros(ns(dur + 0.1))
    for t in event_times(dur, rate, rng):
        place(out, bubble(rng.uniform(*f), 0.06, rng, rng.uniform(0.5, 2.0)) * rng.uniform(0.3, 1.0), t)
    return out


def bone_click(rng, f0=2500.0, hard=0.95):
    return click(rng, "bone", f0, 0.04, hard, 1.0)


# ===================================================================== HOLLOWBACK
def hb_inhale(d, rng, rate=24.0):
    n = ns(d)
    x = breath(d, rng, [(0, "h"), (d, "o")], [(0, 0), (d * 0.6, 1), (d, 0.15)], scale=0.6, tilt=-3)
    x = norm(x) * rattle_env(n, rng, rate, 0.65)
    return mix(x, 0.35 * norm(gurgle(d, rng, 25)))


def hb_exhale(d, rng, voice=0.25, rate=20.0):
    n = ns(d)
    x = breath(d, rng, [(0, "a"), (d, "uh")], [(0, 0), (0.08, 1), (d * 0.5, 0.7), (d, 0)], scale=0.6, tilt=-3.5)
    x = norm(x) * rattle_env(n, rng, rate, 0.55)
    f0 = env_pts(n, [(0, rng.uniform(58, 66)), (d, rng.uniform(48, 54))])
    g = formant(glottal(f0, rng, 0.03, 0.3, 0.6, 0.3, 0.4, creak=0.25), vowel_tracks(n, "o", 0.6))
    g = norm(g) * env_pts(n, [(0, 0), (0.1, 1), (d, 0)])
    return mix(x + voice * g, 0.5 * norm(gurgle(d, rng, 35)))


@S("hb_breath_loop", loop=True, dur=6.0, desc="Hollowback: slow, wet, rattling breaths (6 s loop).")
def hb_breath_loop(rng, v):
    L = ns(6.0)
    out = np.zeros(L)
    t = -0.5
    for k, (ci, ce) in enumerate([(1.1, 1.65), (1.05, 1.7)]):
        place_circ(out, 0.75 * hb_inhale(ci, rng), int(t * SR))
        place_circ(out, hb_exhale(ce, rng), int((t + ci + 0.12) * SR))
        t += ci + ce + 0.25
    # idle airway: a faint wet rattle between breaths so the loop never goes dead
    idle = shaped_noise(L, rng, -3, 150, 2500) * (0.6 + 0.4 * rand_walk01(L, 20, rng))
    out = out + 0.03 * peak(out) * norm(idle)
    return circ(lambda z: hp(z, 60), out)


@S("hb_scrape", variants=3, dur=1.5, desc="Hollowback dragging long nails down tree bark.")
def hb_scrape(rng, v):
    d = rng.uniform(1.3, 1.7)
    out = np.zeros(ns(d + 0.3))
    nails = int(rng.integers(3, 5))
    for k in range(nails):
        sp = [(0, 0), (0.1, 0.6), (d * 0.5, 1.0), (d * 0.85, 0.7), (d - 0.05, 0)]
        s = scrape(d - 0.05 * k, rng, sp, "wood", rng.uniform(380, 700), rng.uniform(600, 1100), 0.7, 0.7,
                   (1800, 11000), 0.6, grit_rate=0)
        place(out, norm(s) * rng.uniform(0.5, 1.0), 0.015 * k + rng.uniform(0, 0.02))
    flakes = np.zeros(ns(d + 0.3))
    for t in np.sort(rng.uniform(0.1, d, int(rng.integers(5, 10)))):
        place(flakes, wood_snap_small(rng) * rng.uniform(0.3, 1.0), t)
    place(out, 0.5 * norm(flakes), 0)
    place(out, 0.3 * rustle(d, rng, [(0, 0), (0.2, 0.5), (d, 1.0), (d + 0.2, 0)], 300, 1500, 8000), 0)
    return out


def wood_snap_small(rng):
    out = np.zeros(ns(0.1))
    for k in range(int(rng.integers(2, 5))):
        place(out, norm(strike("wood", rng.uniform(800, 2000), 0.06, rng, 1.0, 0.4, 0.7)) * rng.uniform(0.4, 1), k * rng.uniform(0.002, 0.006))
    return out


@S("hb_step", variants=4, dur=0.5, desc="Hollowback heavy, soft, padded footfall.")
def hb_step(rng, v):
    out = np.zeros(ns(0.6))
    n = ns(0.5)
    th = thump(0.5, rng, rng.uniform(65, 80), rng.uniform(36, 44), 0.18, 0.0, 400, 0.025)
    pad = lp(white(n, rng), 450, n=2) * env_ar(n, 0.015, 0.12)
    place(out, norm(th) + 0.7 * norm(pad), 0)
    place(out, 0.18 * norm(lp(crumble(0.3, rng, [(0, 1), (0.3, 0)], 50, 0.05, 0.35), 3500)), 0.01)
    place(out, 0.15 * rustle(0.3, rng, [(0, 0), (0.02, 1), (0.3, 0)], 500), 0.005)
    return out


@S("hb_slap", variants=4, dur=0.2, desc="Hollowback palm slapping the ground while galloping: wet fleshy 'pa-tap' (signature).")
def hb_slap(rng, v):
    out = np.zeros(ns(0.4))
    skin = bp(white(ns(0.008), rng), 2500, 0.5) * env_exp(ns(0.008), 0.006)
    n = ns(0.12)
    flesh = bp(white(n, rng), rng.uniform(380, 600), 1.2) * env_ar(n, 0.001, 0.06)
    smack = bp(white(n, rng), rng.uniform(1100, 1500), 2.0) * env_ar(n, 0.0005, 0.03)
    th = thump(0.3, rng, rng.uniform(100, 120), 55, 0.06, 0.5, 700)
    place(out, norm(skin), 0)
    place(out, 0.9 * norm(flesh), 0)
    place(out, 0.7 * norm(smack), 0)
    place(out, 0.3 * norm(th), 0)
    # fingers land a beat after the palm -> distinctive double slap
    t2 = rng.uniform(0.014, 0.026)
    place(out, 0.55 * norm(skin) + 0.0, t2)
    place(out, 0.4 * norm(bp(white(n, rng), rng.uniform(700, 1000), 1.5) * env_ar(n, 0.001, 0.035)), t2)
    place(out, 0.3 * norm(wet_squelch(0.12, rng, 900, 400, 4.0, 2, 0.003)), 0.004)
    place(out, 0.15 * norm(grit(0.15, rng, lambda t: 300 * np.exp(-t / 0.03))), 0.005)
    return early_reflections(out, rng, 3, 0.015, 0.15)


@S("hb_alert", dur=0.6, desc="Hollowback alert: sharp wet rattling intake then a teeth click.")
def hb_alert(rng, v):
    out = np.zeros(ns(0.65))
    d = 0.3
    n = ns(d)
    inh = breath(d, rng, [(0, "h"), (d, "i")], [(0, 0), (d * 0.85, 1), (d, 0.3)], scale=0.65, tilt=-1.5)
    inh = norm(inh) * rattle_env(n, rng, 30, 0.6)
    place(out, inh, 0)
    place(out, 0.4 * norm(gurgle(d, rng, 50, (300, 900))), 0.02)
    place(out, bone_click(rng, rng.uniform(2600, 3400), 1.0), d + 0.03)
    place(out, 0.7 * bone_click(rng, rng.uniform(2200, 3000), 1.0), d + 0.058)
    place(out, 0.3 * norm(thump(0.1, rng, 200, 120, 0.03, 0.5, 900)), d + 0.03)
    return out


@S("hb_listen_click", variants=2, dur=1.0, norm=("peak", -4.0), desc="Hollowback listening: quiet palatal clicks.")
def hb_listen_click(rng, v):
    d = rng.uniform(0.9, 1.3)
    out = np.zeros(ns(d + 0.1))
    t = 0.02
    while t < d:
        n = ns(0.03)
        imp = np.zeros(n)
        imp[0] = 1
        c = bp(imp, rng.uniform(1500, 2600), rng.uniform(6, 10)) + 0.5 * bp(imp, rng.uniform(600, 900), 4)
        place(out, norm(c) * rng.uniform(0.5, 1.0), t)
        if rng.random() < 0.4:
            place(out, 0.6 * norm(c), t + rng.uniform(0.04, 0.07))
        t += rng.uniform(0.12, 0.32)
    place(out, 0.12 * hb_exhale(d, rng, 0.0), 0)
    return out


@S("hb_warning", dur=1.5, desc="Hollowback warning: low gurgling growl rising in pitch and intensity.")
def hb_warning(rng, v):
    d = 1.6
    n = ns(d)
    g = voiced(d, [(0, 52), (0.8, 70), (d, 98)], [(0, "o"), (0.9, "uh"), (d, "a")], rng, 0.6,
               [(0, 0), (0.3, 0.5), (1.3, 1.0), (d, 0.0)], 1.3,
               jitter=0.04, shimmer=0.3, oq=0.6, breath=0.3, rough=0.45, subharm=0.4, creak=0.12)
    g = g * rattle_env(n, rng, 22, 0.45)
    g = np.tanh(2.5 * g)
    w = mix(sat_asym(g, 2.0, 0.25), 0.22 * norm(gurgle(d, rng, 35)) * env_pts(n + ns(0.1), [(0, 0.3), (d, 1)]))
    return w


@S("hb_attack", variants=2, dur=1.0, desc="Hollowback lunge: ragged, choking roar with wet stutters (not a scream).")
def hb_attack(rng, v):
    d = 1.05
    n = ns(d)
    out = np.zeros(ns(d + 0.2))
    gasp = breath(0.1, rng, [(0, "h"), (0.1, "a")], [(0, 0), (0.08, 1), (0.1, 0.5)], scale=0.65)
    place(out, 0.5 * norm(gasp), 0)
    f0 = [(0, 120), (0.15, 165 + 15 * v), (0.6, 150), (d, 105)]
    r = voiced(d, f0, [(0, "a"), (0.5, "ah"), (d, "uh")], rng, 0.65, [(0, 0), (0.04, 1), (0.7, 0.9), (d, 0)], 2.0,
               jitter=0.05, shimmer=0.3, oq=0.5, breath=0.35, rough=0.45, subharm=0.5, creak=0.06)
    choke = np.ones(n)
    for t in np.sort(rng.uniform(0.2, d - 0.1, int(rng.integers(3, 6)))):
        a, b = ns(t), ns(t + rng.uniform(0.03, 0.06))
        choke[a:b] = 0.12
    choke = lp(choke, 70)
    r = r * choke * rattle_env(n, rng, 26, 0.35)
    r = sat_asym(np.tanh(3.0 * norm(r)), 2.0, 0.3)  # heavy drive: dense, ragged body
    place(out, r, 0.08)
    place(out, 0.12 * norm(gurgle(d, rng, 30, (200, 800))), 0.1)
    place(out, 0.25 * bone_click(rng, 2800, 1.0), d + 0.06)
    return out


@S("hb_hurt", variants=2, dur=0.6, desc="Hollowback hurt: choked yelp breaking upwards, wet cough.")
def hb_hurt(rng, v):
    d = 0.5
    out = np.zeros(ns(0.8))
    y = voiced(d, [(0, 140), (0.06, 290), (0.2, 240), (d, 110)], [(0, "a"), (d, "uh")], rng, 0.65,
               [(0, 0), (0.02, 1), (0.25, 0.8), (0.3, 0.2), (0.34, 0.7), (d, 0)], 1.6,
               jitter=0.05, shimmer=0.3, oq=0.5, breath=0.4, rough=0.5, subharm=0.3)
    place(out, sat_asym(y, 2.5), 0)
    cough = breath(0.15, rng, [(0, "h"), (0.15, "uh")], [(0, 0), (0.01, 1), (0.15, 0)], scale=0.6, tilt=-2)
    place(out, 0.6 * norm(cough), d + 0.03)
    place(out, 0.3 * norm(gurgle(0.2, rng, 60)), d + 0.05)
    return out


@S("hb_chase_loop", loop=True, dur=3.0, desc="Hollowback chasing: fast, ragged, wet panting with grunts (3 s loop).")
def hb_chase_loop(rng, v):
    L = ns(3.0)
    out = np.zeros(L)
    cyc = rng.uniform(0.9, 1.1, 6)
    cyc = cyc / cyc.sum() * 3.0
    t = -0.08
    for c in cyc:
        ti = c * 0.38
        place_circ(out, 0.6 * hb_inhale(ti, rng, 30), int(t * SR))
        place_circ(out, hb_exhale(c - ti + 0.03, rng, 0.5, 26), int((t + ti) * SR))
        t += c
    return circ(lambda z: hp(z, 60), out)


# ===================================================================== RABBIT
def sniff(rng, scale=1.0):
    d = rng.uniform(0.035, 0.06)
    n = ns(d)
    x = band_noise(n, rng, 2500 * scale, 9000) * env_pts(n, [(0, 0), (d * 0.3, 1), (d, 0)])
    return norm(peq(x, 4500 * scale, 6, 2.0))


@S("rabbit_sniff", variants=2, dur=0.7, norm=("peak", -3.0), desc="Rabbit: quick nasal sniffing.")
def rabbit_sniff(rng, v):
    out = np.zeros(ns(0.8))
    t = 0.01
    for k in range(int(rng.integers(4, 8))):
        place(out, sniff(rng) * rng.uniform(0.6, 1.0), t)
        t += rng.uniform(0.1, 0.15)
    return out


@S("rabbit_hop", variants=3, dur=0.25, norm=("peak", -2.0), desc="Rabbit hop: soft double thump on the forest floor.")
def rabbit_hop(rng, v):
    out = np.zeros(ns(0.3))
    for k in range(2):
        th = thump(0.15, rng, rng.uniform(160, 200), 90, 0.04, 1.0, 800)
        place(out, norm(th) * (1 - 0.35 * k), k * rng.uniform(0.03, 0.05))
    place(out, 0.3 * rustle(0.15, rng, [(0, 1), (0.15, 0)], 500, 1500, 8000), 0)
    return out


@S("rabbit_squeal", variants=2, dur=0.7, desc="Rabbit hurt: harrowing high squeal.")
def rabbit_squeal(rng, v):
    d = rng.uniform(0.55, 0.8)
    out = np.zeros(ns(d * (2 if v else 1) + 0.2))
    for k in range(1 + v):
        y = voiced(d, [(0, 1300), (0.08, 1900), (d * 0.6, 1700), (d, 1150)], [(0, "i"), (d * 0.5, "e"), (d, "i")],
                   rng, 2.6, [(0, 0), (0.02, 1), (d * 0.7, 0.85), (d, 0)], 1.5,
                   jitter=0.04, shimmer=0.25, oq=0.5, breath=0.25, rough=0.3)
        place(out, sat(y, 1.8) * (1 - 0.3 * k), k * (d + 0.12))
        if v:
            place(out, 0.3 * norm(breath(0.1, rng, "h", [(0, 0), (0.05, 1), (0.1, 0)], 2.0)), d + 0.01)
    return out


@S("rabbit_thump", dur=0.3, desc="Rabbit warning: hard hind-foot thump on the ground.")
def rabbit_thump(rng, v):
    out = np.zeros(ns(0.35))
    place(out, norm(thump(0.3, rng, 140, 60, 0.11, 0.9, 700, 0.015)), 0)
    place(out, 0.2 * norm(grit(0.15, rng, lambda t: 300 * np.exp(-t / 0.03))), 0.002)
    return out


# ===================================================================== FALSEKIN
def chitter(rng, n_sq=4, f=1500.0):
    out = np.zeros(ns(0.35))
    t = 0.0
    for _ in range(n_sq):
        d = rng.uniform(0.02, 0.04)
        y = voiced(d, [(0, f), (d * 0.5, f * 1.3), (d, f * 0.9)], "i", rng, 2.4, [(0, 0), (0.005, 1), (d, 0)],
                   jitter=0.03, breath=0.2)
        place(out, y * rng.uniform(0.4, 0.9), t)
        t += rng.uniform(0.04, 0.07)
    return out


@S("fk_mimic", variants=2, dur=1.8, desc="Falsekin mimicking a rabbit: sniff/chitter that slows, detunes and goes wrong.")
def fk_mimic(rng, v):
    base = np.zeros(ns(1.3))
    t = 0.0
    for k in range(7):
        place(base, sniff(rng) * rng.uniform(0.6, 1.0), t)
        t += rng.uniform(0.11, 0.15)
    place(base, 0.6 * chitter(rng, 4, rng.uniform(1300, 1700)), 0.45 if v == 0 else 0.2)
    last = np.flatnonzero(np.abs(base) > 1e-3 * peak(base))[-1]
    base = base[: last + ns(0.02)]
    # slows down and sinks after the first few sniffs (mimicry slipping)
    sp = lambda tt_: np.where(tt_ < 0.35, 1.0, np.maximum(0.45, 1.0 - (tt_ - 0.35) * 0.7))
    a = varispeed(base, sp)
    b = varispeed(base, lambda tt_: sp(tt_) * 0.965)  # detuned double -> wrong beating
    y = mix(a, 0.75 * b)
    out = np.zeros(len(y) + ns(0.7))
    place(out, y, 0)
    deep = breath(0.6, rng, [(0, "h"), (0.6, "o")], [(0, 0), (0.25, 1), (0.6, 0)], scale=0.7, tilt=-3)
    last = np.flatnonzero(np.abs(y) > 1e-3 * peak(y))[-1]
    place(out, 0.5 * norm(deep), last / SR - 0.05)
    return out


@S("fk_reveal", dur=1.2, desc="Falsekin reveal (key sound): stretching, tearing, wet bone cracks, then a rising ring-modulated screech.")
def fk_reveal(rng, v):
    d = 1.3
    n = ns(d)
    out = np.zeros(ns(d + 0.3))
    # stretching flesh / gristle creak with rising tension
    st = creak(0.6, rng, [(0, 18), (0.3, 60), (0.6, 140)], "wood", 210, [(0, 0.3), (0.5, 1), (0.6, 0.6)], 0.4, 0.8)
    place(out, 0.5 * st, 0)
    # tearing: crackly noise gated by an irregular slip train
    m = ns(0.65)
    tear = band_noise(m, rng, 600, 7000) * np.clip(stick_slip(m, env_pts(m, [(0, 200), (0.65, 900)]), rng, 0.9, 0.9), 0, None)
    tear = lp(tear, 7000) * env_pts(m, [(0, 0.2), (0.4, 1), (0.65, 0.3)])
    place(out, 0.6 * norm(tear + 1e-12), 0.05)
    # wet bone cracks
    for t in np.sort(rng.uniform(0.12, 0.62, 5)):
        crack = mix(norm(strike("wood", rng.uniform(500, 1200), 0.15, rng, 1.0, 0.4, 0.6)),
                    0.6 * norm(wet_squelch(0.15, rng, 700, 300, 4, 2, 0.002)))
        place(out, crack * rng.uniform(0.5, 1.0), t)
    place(out, 0.5 * norm(wet_squelch(0.5, rng, 250, 900, 5, 8, 0.02)), 0.1)
    # rising screech
    sd = 0.8
    k = ns(sd)
    f0 = 330 * np.exp(np.log(1700 / 330) * np.clip(tt(k) / 0.7, 0, 1) ** 1.6)
    a = formant(glottal(f0, rng, 0.03, 0.2, 0.5, 0.3, 0.3), vowel_tracks(k, [(0, "a"), (sd, "i")], 1.4, 1.3))
    b = formant(glottal(f0 * 1.06, rng, 0.03, 0.2, 0.5, 0.3, 0.3), vowel_tracks(k, [(0, "ae"), (sd, "i")], 1.5, 1.3))
    sc = norm(a) + 0.6 * norm(b)
    sc = mix(sc, 0.5 * norm(ring(sc, 73.0)))[:k]
    sc = sat(norm(sc), 2.5) * env_pts(k, [(0, 0), (0.2, 0.4), (0.65, 1.0), (sd - 0.05, 1.0), (sd, 0)])
    place(out, 0.95 * sc, 0.45)
    return early_reflections(out, rng, 3, 0.015, 0.12)


@S("fk_skitter_loop", loop=True, dur=2.0, desc="Falsekin skittering: very fast clicky multi-leg footsteps (2 s loop).")
def fk_skitter_loop(rng, v):
    L = ns(2.0)
    out = np.zeros(L)
    bank = [bone_click(rng, rng.uniform(1800, 5000), 1.0) for _ in range(12)]
    count = 22  # clusters per loop (11 Hz gait)
    for k in range(count):
        t0 = int((k + 0.5) * L / count + rng.normal(0, 150))
        for leg in range(3):
            place_circ(out, bank[rng.integers(12)] * rng.uniform(0.4, 1.0), t0 + int(rng.uniform(0, 0.016) * SR))
    rus = shaped_noise(L, rng, -1, 2000, 9000) * (0.5 + 0.5 * rand_walk01(L, 10, rng)) * 0.08
    return out + rus


@S("fk_shriek", variants=2, dur=0.9, desc="Falsekin shriek: harsh, detuned, ring-modulated scream.")
def fk_shriek(rng, v):
    d = rng.uniform(0.8, 1.0)
    n = ns(d)
    f0 = env_pts(n, [(0, 1000), (0.1, 1500), (d * 0.6, 1350), (d, 850)]) * (1 + 0.03 * np.sin(2 * np.pi * 18 * tt(n)))
    a = formant(glottal(f0, rng, 0.03, 0.2, 0.45, 0.3, 0.35), vowel_tracks(n, [(0, "e"), (d, "i")], 1.5, 1.4))
    b = formant(glottal(f0 * 1.07, rng, 0.03, 0.2, 0.45, 0.3, 0.35), vowel_tracks(n, "i", 1.6, 1.4))
    y = norm(a) + 0.7 * norm(b)
    y = mix(y, 0.6 * ring(y, rng.uniform(90, 130)))
    y = sat(norm(y), 2.8) * env_pts(n, [(0, 0), (0.03, 1), (d * 0.7, 0.8), (d, 0)])
    return early_reflections(y, rng, 3, 0.015, 0.12)


def mandible_rattle(d, rng, rate=40.0, amp_pts=None):
    n = ns(d)
    exc = stick_slip(n, rate, rng, 0.4, 0.5, env_pts(n, amp_pts) if amp_pts else None)
    ir = resonator_ir("bone", 2200, rng, 0.03, 1.0)
    return sps.fftconvolve(exc, ir)[:n]


@S("fk_hiss", variants=2, dur=0.9, desc="Falsekin hiss with a chitinous mandible rattle.")
def fk_hiss(rng, v):
    d = rng.uniform(0.8, 1.1)
    pts = [(0, 0), (0.08, 1), (d * 0.7, 0.8), (d, 0)]
    h = breath(d, rng, [(0, "sh"), (d * 0.5, "s"), (d, "sh")], pts, 1.0, tilt=0)
    r = mandible_rattle(d, rng, rng.uniform(35, 48), pts)
    return norm(h) + 0.45 * norm(r)


@S("fk_death", dur=1.5, desc="Falsekin death: shriek collapsing into a gurgle, last twitching clicks.")
def fk_death(rng, v):
    d = 1.6
    out = np.zeros(ns(d + 0.3))
    sd = 0.8
    k = ns(sd)
    f0 = env_pts(k, [(0, 1300), (0.15, 1100), (sd, 280)])
    a = formant(glottal(f0, rng, 0.05, 0.3, 0.5, 0.3, 0.5), vowel_tracks(k, [(0, "i"), (sd, "o")], 1.4, 1.4))
    a = mix(norm(a), 0.5 * ring(norm(a), 80))[:k] * env_pts(k, [(0, 0), (0.02, 1), (sd, 0)])
    place(out, sat(norm(a), 2.2), 0)
    place(out, 0.6 * norm(wet_squelch(0.6, rng, 700, 200, 4, 10, 0.05)), 0.55)
    place(out, 0.5 * norm(gurgle(0.6, rng, 50, (200, 700))), 0.6)
    place(out, 0.6 * norm(thump(0.4, rng, 120, 50, 0.15, 0.8, 700)), 0.75)
    for t in (1.1, 1.25, 1.33, 1.5):
        place(out, 0.25 * bone_click(rng, rng.uniform(2000, 4000)), t)
    return out


# ===================================================================== BOAR
def boar_voice(rng, d, f0a, f0b, rough=0.45):
    n = ns(d)
    f0 = env_pts(n, [(0, f0a), (d * 0.3, f0a * 1.08), (d, f0b)])
    src = glottal(f0, rng, 0.05, 0.3, 0.55, 0.25, rough, subharm=0.3, creak=0.15)
    nasal = [(np.full(n, 320.0), np.full(n, 90.0), 1.0), (np.full(n, 950.0), np.full(n, 180.0), 0.45),
             (np.full(n, 2300.0), np.full(n, 300.0), 0.15)]
    y = formant(src, nasal) + 0.5 * formant(src, vowel_tracks(n, "o", 0.75))
    return sat_asym(norm(y) * env_pts(n, [(0, 0), (0.02, 1), (d * 0.6, 0.8), (d, 0)]), 2.0)


def snort(rng, d=0.14):
    n = ns(d)
    x = band_noise(n, rng, 400, 5000) * env_pts(n, [(0, 0), (0.01, 1), (d, 0)])
    x = peq(peq(x, 1000, 8, 2), 2500, 4, 2) * rattle_env(n, rng, 60, 0.5)
    return norm(x)


@S("boar_grunt", variants=3, dur=0.6, desc="Boar: low nasal grunts, sometimes with a snort.")
def boar_grunt(rng, v):
    out = np.zeros(ns(0.9))
    t = 0.0
    if v == 1:
        place(out, 0.7 * snort(rng), 0)
        t = 0.15
    for k in range(1 if v == 0 else 2):
        place(out, boar_voice(rng, rng.uniform(0.22, 0.35), rng.uniform(95, 125), rng.uniform(70, 85)), t)
        t += rng.uniform(0.3, 0.4)
    return out


@S("boar_squeal", variants=2, dur=0.8, desc="Boar squeal: shrill, harsh pig scream.")
def boar_squeal(rng, v):
    d = rng.uniform(0.7, 0.9)
    y = voiced(d, [(0, 650), (0.08, 1050), (d * 0.6, 950), (d, 700)], [(0, "e"), (d * 0.5, "i"), (d, "e")], rng, 1.5,
               [(0, 0), (0.03, 1), (d * 0.75, 0.9), (d, 0)], 1.6, jitter=0.04, shimmer=0.3, oq=0.45, breath=0.25, rough=0.4)
    return sat(y, 2.4)


@S("boar_charge", dur=2.0, desc="Boar charging: snorting rush and drumming hooves, angry grunts, getting closer.")
def boar_charge(rng, v):
    d = 2.1
    n = ns(d)
    out = np.zeros(ns(d + 0.3))
    place(out, 0.8 * boar_voice(rng, 0.3, 120, 85, 0.6), 0)
    t = 0.25
    stride = 0.19
    k = 0
    while t < d - 0.1:
        prox = 0.35 + 0.65 * (t / d)
        for off in (0.0, 0.035, 0.09, 0.12):  # four-beat gallop
            hoof = mix(norm(thump(0.15, rng, rng.uniform(130, 170), 70, 0.05, 0.9, 1000)),
                       0.3 * norm(grit(0.08, rng, lambda tt_: 400 * np.exp(-tt_ / 0.02))))
            place(out, hoof * prox * rng.uniform(0.6, 1.0), t + off)
        if k % 2 == 0:
            place(out, snort(rng, rng.uniform(0.1, 0.16)) * prox * 0.8, t + 0.05)
        if k % 4 == 3:
            place(out, 0.6 * boar_voice(rng, 0.2, 130, 95, 0.6) * prox, t + 0.1)
        t += stride * rng.uniform(0.95, 1.05)
        k += 1
    place(out, 0.25 * rustle(d, rng, [(0, 0), (0.3, 0.4), (d, 1)], 500), 0)
    return out


# ===================================================================== GLOOMRAT
@S("rat_squeak", variants=3, dur=0.25, desc="Gloomrat: short high chirping squeaks.")
def rat_squeak(rng, v):
    out = np.zeros(ns(0.45))
    t = 0.0
    for k in range(v + 1):
        d = rng.uniform(0.05, 0.12)
        f = rng.uniform(3000, 4300)
        y = voiced(d, [(0, f * 0.85), (d * 0.4, f * 1.15), (d, f * 0.9)], "i", rng, 3.0,
                   [(0, 0), (0.008, 1), (d, 0)], jitter=0.03, oq=0.4, breath=0.15, rough=0.2)
        place(out, y * rng.uniform(0.7, 1.0), t)
        t += d + rng.uniform(0.03, 0.08)
    return out


@S("rat_scurry", variants=2, dur=1.0, norm=("peak", -2.0), desc="Gloomrat scurrying: tiny claws ticking and scratching.")
def rat_scurry(rng, v):
    d = rng.uniform(0.8, 1.2)
    n = ns(d)
    e = np.clip(rand_walk01(n, 4, rng) * 1.6 - 0.3, 0, 1)
    bank = [click(rng, "bone", rng.uniform(3000, 7000), 0.02, 1.0, 0.6) for _ in range(10)]
    out = np.zeros(n + ns(0.05))
    for t in event_times(d, 45 * e, rng):
        place(out, bank[rng.integers(10)] * rng.uniform(0.3, 1.0), t)
    scr = shaped_noise(n, rng, 0, 3000, 11000) * e * 0.15
    return mix(norm(out), scr)


# ===================================================================== CEILING CLERK
def nail_tap(rng, surface="wood"):
    if surface == "wood":
        body = strike("wood", rng.uniform(600, 1000), 0.12, rng, 0.98, 0.6, 0.3)
    else:
        body = strike("stone", rng.uniform(1500, 2500), 0.08, rng, 0.98, 0.7, 0.4, 16)
    nail = click(rng, "bone", rng.uniform(3000, 4500), 0.03, 1.0, 0.8)
    return norm(mix(norm(body), 0.6 * nail))


@S("clerk_tap", variants=6, dur=0.1, norm=("peak", -3.0), desc="Ceiling Clerk: a single fingernail tap (1-3 wood, 4-6 stone).")
def clerk_tap(rng, v):
    return nail_tap(rng, "wood" if v < 3 else "stone")


@S("clerk_skitter", variants=2, dur=1.0, desc="Ceiling Clerk: rapid finger-drumming tapping run (wood / stone).")
def clerk_skitter(rng, v):
    surface = "wood" if v == 0 else "stone"
    out = np.zeros(ns(1.2))
    t = 0.0
    groups = int(rng.integers(3, 5))
    for g in range(groups):
        gap = rng.uniform(0.022, 0.034) * (1 - 0.15 * g)
        for f in range(4):
            place(out, nail_tap(rng, surface) * rng.uniform(0.5, 1.0) * (0.7 + 0.1 * f), t)
            t += gap
        t += rng.uniform(0.08, 0.2) * (1 - 0.2 * g)
    return out


@S("clerk_click_loop", loop=True, dur=2.0, desc="Ceiling Clerk: soft wet jaw clicking (2 s loop).")
def clerk_click_loop(rng, v):
    L = ns(2.0)
    out = np.zeros(L)
    count = 15
    for k in range(count):
        i = int(k * L / count + rng.normal(0, 900))
        c = mix(click(rng, "bone", rng.uniform(1200, 2200), 0.04, 0.8, 0.8),
                0.3 * norm(wet_squelch(0.04, rng, 1500, 800, 5, 1, 0.001)))
        place_circ(out, c * rng.uniform(0.4, 1.0), i)
    air = shaped_noise(L, rng, -2, 300, 4000) * (0.5 + 0.5 * rand_walk01(L, 2, rng)) * 0.04
    return out + air


@S("clerk_jaw_drop", dur=0.9, desc="Ceiling Clerk unhinging its jaw: wet click then a long cartilage creak.")
def clerk_jaw_drop(rng, v):
    out = np.zeros(ns(1.0))
    smack = mix(norm(bp(white(ns(0.02), rng), 1500, 2.5) * env_exp(ns(0.02), 0.012)), 0.6 * bubble(1200, 0.05, rng, 2.0))
    place(out, smack, 0)
    place(out, 0.8 * click(rng, "bone", 1800, 0.04, 0.9), 0.008)
    cr = creak(0.65, rng, [(0, 16), (0.3, 11), (0.65, 5)], "wood", 320, [(0, 0.5), (0.3, 1), (0.65, 0.4)], 0.4, 0.7, 0.02)
    place(out, 0.8 * cr, 0.06)
    place(out, 0.4 * norm(wet_squelch(0.2, rng, 600, 1200, 5, 4, 0.01, bub_f=(800, 2200))), 0.68)
    return out


@S("clerk_drop", dur=0.8, desc="Ceiling Clerk dropping from the ceiling: rush, heavy body thud, limbs clattering.")
def clerk_drop(rng, v):
    out = np.zeros(ns(0.9))
    place(out, 0.3 * whoosh(0.18, rng, 0.85, 200, 1500, 1.0, 0.05), 0)
    t0 = 0.16
    place(out, norm(thump(0.5, rng, 85, 36, 0.25, 0.9, 600)), t0)
    place(out, 0.4 * fabric(0.2, rng, [(0, 1), (0.2, 0)], 400, 300, 3000, 1.0), t0)
    for t in np.sort(rng.uniform(0.0, 0.25, 8)):
        place(out, 0.3 * bone_click(rng, rng.uniform(1500, 3500), 0.9), t0 + t)
    place(out, 0.2 * norm(grit(0.3, rng, lambda t: 300 * np.exp(-t / 0.05))), t0)
    return out


@S("clerk_screech", dur=1.2, desc="Ceiling Clerk grab: dry, raspy, inhaled vocal-fry screech with clicks.")
def clerk_screech(rng, v):
    d = 1.15
    n = ns(d)
    out = np.zeros(ns(d + 0.15))
    for k in range(4):
        place(out, 0.5 * bone_click(rng, rng.uniform(1500, 2500)), k * 0.035)
    f0 = env_pts(n, [(0, 600), (0.25, 900), (0.8, 820), (d, 700)])
    vo = formant(glottal(f0, rng, 0.04, 0.4, 0.35, 0.8, 0.5, creak=0.25), vowel_tracks(n, [(0, "i"), (0.4, "ae"), (d, "a")], 1.2, 1.8))
    air = breath_noise(n, [(0, "i"), (d, "a")], rng, 1.2, 1.4, 0)
    fry = 0.55 + 0.45 * np.sign(np.sin(2 * np.pi * phase_cycles(env_pts(n, [(0, 45), (d, 60)]))))
    fry = lp(fry, 400)
    y = (norm(vo) + 0.7 * norm(air)) * fry
    y = sat(norm(y), 2.0) * env_pts(n, [(0, 0), (0.25, 1.0), (d - 0.03, 0.9), (d, 0)])
    place(out, y, 0.12)
    return out


@S("clerk_hiss", variants=2, dur=0.9, desc="Ceiling Clerk hiss: breathy throat hiss with jaw clicks.")
def clerk_hiss(rng, v):
    d = rng.uniform(0.8, 1.0)
    out = np.zeros(ns(d + 0.1))
    h = breath(d, rng, [(0, "h"), (d * 0.4, "sh"), (d, "h")], [(0, 0), (0.1, 1), (d * 0.8, 0.7), (d, 0)], 0.9, tilt=-1)
    place(out, norm(h) * 0.9, 0)
    for t in np.sort(rng.uniform(0.05, d, int(rng.integers(3, 6)))):
        place(out, 0.5 * click(rng, "bone", rng.uniform(1200, 2000), 0.04, 0.85, 0.8), t)
    return out


@S("clerk_hurt", dur=0.5, desc="Ceiling Clerk hurt: raspy yelp and rapid jaw clicks.")
def clerk_hurt(rng, v):
    d = 0.35
    n = ns(d)
    out = np.zeros(ns(0.6))
    vo = formant(glottal(env_pts(n, [(0, 700), (0.05, 1000), (d, 550)]), rng, 0.05, 0.4, 0.35, 0.7, 0.5, creak=0.2),
                 vowel_tracks(n, [(0, "ae"), (d, "a")], 1.2, 1.8))
    place(out, sat(norm(vo), 2.0) * env_pts(n, [(0, 0), (0.02, 1), (d, 0)]), 0)
    for k in range(5):
        place(out, 0.45 * bone_click(rng, rng.uniform(1500, 2500)), d + 0.02 + k * 0.03)
    return out


# ===================================================================== BORER
def sub_boom(rng, dur=2.5, f_hi=50, f_lo=22, t60=1.2):
    return thump(dur, rng, f_hi, f_lo, t60, 0.5, 150, 0.06)


@S("borer_impact_deep", variants=3, dur=2.5, desc="Borer: huge low thump from beneath the floor, sub-bass with falling grit.")
def borer_impact_deep(rng, v):
    d = 2.6
    n = ns(d)
    out = np.zeros(ns(d + 0.2))
    boom = lp(mix(norm(sub_boom(rng)), 0.4 * norm(lp(white(n, rng), 120, n=2) * env_ar(n, 0.04, 1.3))), 400, n=2)
    place(out, boom, 0)
    debris = mix(0.6 * crumble(d - 0.3, rng, [(0, 0), (0.15, 1), (d - 0.3, 0)], 40, 0.03, 0.35, dust=0.6),
                 0.5 * grit(d - 0.3, rng, lambda t: 250 * np.exp(-t / 0.7)))
    place(out, 0.2 * norm(debris), 0.08)
    return out


@S("borer_impact_close", variants=2, dur=2.5, desc="Borer: closer, louder impact under the floor - rock crack and heavy debris fall.")
def borer_impact_close(rng, v):
    d = 2.6
    n = ns(d)
    out = np.zeros(ns(d + 0.2))
    boom = lp(mix(norm(sub_boom(rng, d, 62, 25, 1.0)), 0.5 * norm(lp(white(n, rng), 200, n=2) * env_ar(n, 0.02, 1.0))), 700, n=2)
    place(out, boom, 0)
    cr = lp(mix(norm(strike("stone", 300, 0.5, rng, 0.95, 1.5, 0.8)), 0.6 * norm(strike("stone", 600, 0.4, rng, 0.95, 1.2, 0.8))), 3500)
    place(out, 0.5 * cr, 0.005)
    debris = crumble(d - 0.2, rng, [(0, 0.5), (0.1, 1), (d - 0.2, 0)], 140, 0.05, 0.7, dust=0.6)
    place(out, 0.45 * norm(debris), 0.04)
    return early_reflections(out, rng, 5, 0.03, 0.2)


def grind_texture(n, rng, density=900, f=(200, 3000)):
    """Rock-on-rock grinding: dense low pebble grains + rough band noise."""
    bank = [lp(pebble(rng, s), f[1]) for s in rng.uniform(0.3, 0.8, 16)]
    out = np.zeros(n + ns(0.3))
    for t in event_times(n / SR, density, rng):
        place(out, bank[rng.integers(16)] * rng.lognormal(-0.5, 0.6), t)
    nz = shaped_noise(n, rng, -3, f[0], f[1]) * (0.5 + 0.5 * rand_walk01(n, 12, rng))
    return norm(out[:n]) + 0.5 * norm(nz)


def borer_voice(d, rng, f0_pts, seq, rough=0.8, scale=0.38):
    n = ns(d)
    f0 = env_pts(n, f0_pts)
    src = glottal(f0, rng, 0.05, 0.4, 0.55, 0.3, rough, subharm=0.55, creak=0.15, oversample=1)
    y = formant(src, vowel_tracks(n, seq, scale, 1.8))
    sub = np.sin(2 * np.pi * phase_cycles(f0 * 0.5))
    return hp(sat_asym(norm(y) + 0.15 * sub, 3.0, 0.3), 30)


@S("borer_grind_loop", loop=True, dur=3.0, desc="Borer: deep vibrating grinding vocal with rock grind (3 s loop).")
def borer_grind_loop(rng, v):
    L, X = ns(3.0), ns(0.3)
    n = L + X
    d = n / SR
    vo = borer_voice(d, rng, [(0, 40), (1.2, 44), (2.2, 38), (d, 40)], [(0, "o"), (1.5, "uh"), (d, "o")], 0.8)
    vib = 0.7 + 0.3 * np.sin(2 * np.pi * 9 * tt(n))
    gr = grind_texture(n, rng, 700)
    y = norm(vo) * vib + 0.45 * gr * (0.8 + 0.2 * vib)
    y = lp(y, 5000)
    return loopify(y, L, X)


@S("borer_emerge", dur=2.5, desc="Borer bursting out of the rock: explosion of stone, rubble cascade, roar onset.")
def borer_emerge(rng, v):
    d = 2.6
    n = ns(d)
    out = np.zeros(ns(d + 0.3))
    burst = lp(white(ns(0.8), rng), 3000, n=2) * env_ar(ns(0.8), 0.005, 0.4)
    place(out, sat(norm(burst) * 1.5, 2.0), 0)
    place(out, norm(sub_boom(rng, 2.0, 70, 28, 0.9)), 0)
    for t in (0.0, 0.03, 0.08):
        place(out, 0.6 * norm(strike("stone", rng.uniform(250, 500), 0.5, rng, 0.98, 1.6, 0.8)), t)
    place(out, 0.9 * crumble(d - 0.1, rng, [(0, 1), (0.6, 0.8), (d - 0.1, 0)], 230, 0.15, 1.0, dust=0.5), 0.05)
    roar = borer_voice(1.6, rng, [(0, 35), (0.8, 55), (1.6, 48)], [(0, "uh"), (1.6, "a")])
    place(out, 0.45 * roar * env_pts(len(roar), [(0, 0), (0.6, 1), (1.6, 0)]), 0.9)
    return early_reflections(out, rng, 6, 0.04, 0.25)


@S("borer_roar", variants=2, dur=2.0, desc="Borer roar: enormous grinding, distorted bellow.")
def borer_roar(rng, v):
    d = rng.uniform(1.9, 2.2)
    n = ns(d)
    vo = borer_voice(d, rng, [(0, 52), (0.5, 76 + 6 * v), (1.4, 70), (d, 48)], [(0, "o"), (0.4, "a"), (1.4, "ah"), (d, "uh")])
    gr = grind_texture(n, rng, 1100, (300, 4000))
    e = env_pts(n, [(0, 0), (0.15, 0.8), (0.5, 1), (1.5, 0.85), (d, 0)])
    y = (norm(vo) + 0.4 * gr) * e
    return space(y, rng, "cave", wet=0.2, rt=1.6)


@S("borer_step", variants=3, dur=1.2, desc="Borer footfall: very heavy, ground-shaking crunch.")
def borer_step(rng, v):
    out = np.zeros(ns(1.3))
    place(out, norm(thump(1.2, rng, rng.uniform(48, 58), 22, 0.5, 0.7, 300, 0.05)), 0)
    place(out, 0.4 * norm(lp(crumble(0.5, rng, [(0, 1), (0.5, 0)], 90, 0.1, 0.6), 4000)), 0.005)
    place(out, 0.15 * norm(grit(0.8, rng, lambda t: 200 * np.exp(-t / 0.3))), 0.05)
    return early_reflections(out, rng, 4, 0.03, 0.2)


@S("borer_dig_loop", loop=True, dur=2.0, desc="Borer digging: rhythmic churning crunch of rock (2 s loop).")
def borer_dig_loop(rng, v):
    L = ns(2.0)
    t = tt(L)
    out = np.zeros(L)
    for k in range(8):
        c = mix(lp(crumble(0.3, rng, [(0, 1), (0.3, 0)], 160, 0.1, 0.7), 3000), 0.6 * norm(thump(0.3, rng, 70, 35, 0.12, 0.6, 300)))
        place_circ(out, norm(c) * rng.uniform(0.7, 1.0), int((k + 0.5) * L / 8 + rng.normal(0, 200)))
    churn = shaped_noise(L, rng, -5, 25, 1500) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t) ** 2)
    gr = np.zeros(L)
    bank = [lp(pebble(rng, s), 2500) for s in rng.uniform(0.2, 0.6, 12)]
    for _ in range(600):
        place_circ(gr, bank[rng.integers(12)] * rng.lognormal(-1, 0.6), int(rng.uniform(0, L)))
    return norm(out) + 0.5 * norm(churn) + 0.3 * norm(gr)


@S("dust_fall", variants=3, dur=1.2, desc="Sprinkle of grit and dust falling from the ceiling.")
def dust_fall(rng, v):
    d = rng.uniform(1.0, 1.5)
    n = ns(d)
    e = lambda t: 450 * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5
    g = grit(d, rng, e, 2500, 12000)
    out = np.zeros(len(g))
    place(out, norm(g), 0)
    for t in np.sort(rng.uniform(0.1, d, int(rng.integers(2, 5)))):
        place(out, 0.35 * pebble(rng, rng.uniform(0.1, 0.3)), t)
    hiss = band_noise(n, rng, 4000, 14000) * env_pts(n, [(0, 0), (d * 0.4, 1), (d, 0)])
    place(out, 0.12 * norm(hiss), 0)
    return out


@S("borer_hurt", dur=1.2, desc="Borer hurt: grinding bellow breaking upward, rock shudder.")
def borer_hurt(rng, v):
    d = 1.2
    n = ns(d)
    vo = borer_voice(d, rng, [(0, 55), (0.15, 120), (0.5, 95), (d, 45)], [(0, "a"), (0.4, "ah"), (d, "o")], 0.9, 0.42)
    gr = grind_texture(n, rng, 900, (300, 4000))
    y = (norm(vo) + 0.35 * gr) * env_pts(n, [(0, 0), (0.05, 1), (0.8, 0.7), (d, 0)])
    return space(y, rng, "cave", wet=0.2, rt=1.6)


# ===================================================================== LANTERN MOURNER
def mourner_voice(n, rng, f0, seq, breath_amt=0.6, scale=1.0):
    src = glottal(f0, rng, 0.006, 0.05, 0.8, breath_amt, 0.05)
    tracks = vowel_tracks(n, seq, scale, 1.2)
    return norm(formant(src, tracks))


@S("mourner_hum_loop", loop=True, dur=6.0, desc="Lantern Mourner: eerie breathy nasal hum, pitch slowly wavering (6 s loop).")
def mourner_hum_loop(rng, v):
    L, X = ns(6.0), ns(0.4)
    n = L + X
    t = tt(n)
    f0 = 138 * (1 + 0.03 * np.sin(2 * np.pi * t / 6.0) + 0.012 * np.sin(2 * np.pi * 3 * t / 6.0 + 1.3)
                + 0.004 * np.sin(2 * np.pi * 5.1 * t))
    hum = mourner_voice(n, rng, f0, [(0, "m"), (3.0, "u"), (n / SR, "m")], 0.6)
    ghost = np.sin(2 * np.pi * phase_cycles(f0 * 2.013)) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 3.0))
    air = breath_noise(n, "u", rng, 1.0) * 0.35
    y = norm(hum) + 0.08 * ghost + 0.25 * norm(air)
    return loopify(y, L, X)


@S("mourner_clink", variants=4, dur=0.6, desc="Lantern Mourner: broken lamp glass and metal fragments clinking.")
def mourner_clink(rng, v):
    out = np.zeros(ns(0.9))
    t = 0.0
    for k in range(int(rng.integers(2, 5))):
        if rng.random() < 0.55:
            c = strike("glass", rng.uniform(2500, 5000), 0.4, rng, 1.0, 0.18, 0.3)
        else:
            c = strike("metal", rng.uniform(900, 1700), 0.5, rng, 0.95, 0.3, 0.2)
        place(out, norm(c) * rng.uniform(0.4, 1.0), t)
        t += rng.uniform(0.06, 0.25)
    return out


@S("mourner_wail", variants=2, dur=4.0, desc="Lantern Mourner: very distant, sad, falling wail.")
def mourner_wail(rng, v):
    d = 3.2
    n = ns(d)
    if v == 0:
        pts = [(0, 330), (0.5, 345), (1.2, 311), (1.6, 311), (2.4, 247), (d, 220)]
    else:
        pts = [(0, 294), (0.6, 311), (1.0, 294), (1.8, 262), (2.6, 233), (d, 196)]
    f0 = env_pts(n, pts) * (1 + 0.015 * np.sin(2 * np.pi * 4.5 * tt(n)))
    vo = mourner_voice(n, rng, f0, [(0, "o"), (1.2, "a"), (2.4, "o"), (d, "u")], 0.4, 1.15)
    vo = vo * env_pts(n, [(0, 0), (0.4, 1), (2.5, 0.8), (d, 0)])
    return far(vo, rng, 90, "cave", wet=1.2)


@S("mourner_buzz_loop", loop=True, dur=2.0, desc="Lantern Mourner: electrical interference buzz near the creature (2 s loop).")
def mourner_buzz_loop(rng, v):
    L = ns(2.0)
    t = tt(L)
    ph = (217.0 * t) % 1.0
    pulses = (ph < 0.12).astype(float)
    frame = ((8.5 * t + 0.31) % 1.0 < 0.62).astype(float)
    frame = circ(lambda z: lp(z, 200), frame)
    tdma = circ(lambda z: bw(z, "bandpass", (180, 6000), 2), pulses) * frame
    hum = mains_hum(L, rng, 50, buzz=0.6)
    crack = np.zeros(L)
    for _ in range(30):
        place_circ(crack, norm(band_noise(ns(0.003), rng, 2000, 12000)) * rng.uniform(0.2, 1.0), int(rng.uniform(0, L)))
    y = norm(tdma) + 0.4 * norm(hum) * (0.6 + 0.4 * smooth_rand(L, 3, rng) ** 2) + 0.3 * crack
    return circ(lambda z: sat(z, 1.5), y)


@S("mourner_reach", dur=1.6, desc="Lantern Mourner reaching: the hum rises into a thin, whistling shriek.")
def mourner_reach(rng, v):
    d = 1.6
    n = ns(d)
    k = np.clip(tt(n) / 1.45, 0, 1) ** 2.2
    f0 = 138 * np.exp(np.log(1100 / 138) * k) * (1 + 0.01 * np.sin(2 * np.pi * 6 * tt(n)))
    src = glottal(f0, rng, 0.008, 0.05, 0.75, 0.6 + 0.6 * float(np.mean(k)), 0.05)
    seq = [(0, "m"), (0.4, "u"), (1.0, "e"), (d, "i")]
    vo = formant(src, vowel_tracks(n, seq, 1.0, 1.2))
    whistle = tvf(white(n, rng), "bp", f0 * 2.0, 25) * k
    buzz = mains_hum(n, rng, 50, buzz=0.8) * k * 0.5
    y = norm(vo) + 0.4 * norm(whistle) + 0.15 * norm(buzz)
    return y * env_pts(n, [(0, 0), (0.15, 0.6), (1.2, 1.0), (d - 0.05, 1.0), (d, 0)])


@S("mourner_recoil", dur=0.8, desc="Lantern Mourner recoiling: electric crackle and a pained falling moan.")
def mourner_recoil(rng, v):
    out = np.zeros(ns(0.9))
    m = ns(0.25)
    exc = stick_slip(m, 260, rng, 0.7, 0.8)
    arc = sat(norm(bw(sps.fftconvolve(exc, norm(band_noise(ns(0.003), rng, 1500, 12000)))[:m], "highpass", 900, 2)) * 2, 2.2)
    place(out, 0.6 * arc * env_pts(m, [(0, 1), (0.25, 0)]), 0)
    d = 0.7
    n = ns(d)
    f0 = env_pts(n, [(0, 320), (0.08, 360), (d, 150)])
    vo = mourner_voice(n, rng, f0, [(0, "a"), (d, "o")], 0.4)
    place(out, vo * env_pts(n, [(0, 0), (0.03, 1), (d, 0)]), 0.04)
    return out


# ===================================================================== GAUNT
@S("gaunt_step", variants=2, dur=4.0, desc="Gaunt: enormous distant footfall rolling through the valley.")
def gaunt_step(rng, v):
    d = 2.5
    n = ns(d)
    out = np.zeros(n)
    place(out, norm(thump(d, rng, rng.uniform(38, 44), 18, 1.5, 0.6, 120, 0.1)), 0)
    place(out, 0.35 * norm(lp(crumble(1.2, rng, [(0, 1), (1.2, 0)], 60, 0.4, 1.0), 900)), 0.02)
    place(out, 0.2 * norm(lp(creak(1.2, rng, [(0, 8), (1.2, 14)], "wood", 150, [(0, 1), (1.2, 0)], 0.4, 1.0), 900)), 0.1)
    return far(out, rng, 150, "valley", wet=1.3)


@S("gaunt_groan", dur=6.0, desc="Gaunt: huge, distant, horn-like groan.")
def gaunt_groan(rng, v):
    d = 4.2
    n = ns(d)
    f0 = env_pts(n, [(0, 30), (1.5, 37), (3.0, 34), (d, 26)]) * (1 + 0.01 * smooth_rand(n, 1.0, rng))
    src = glottal(f0, rng, 0.02, 0.15, 0.6, 0.2, 0.3, subharm=0.2, oversample=1)
    vo = formant(src, vowel_tracks(n, [(0, "o"), (2, "a"), (3.5, "o"), (d, "u")], 0.3, 1.6))
    horn = lp(osc(f0 * 2, "saw") + 0.6 * osc(f0 * 3.01, "saw"), 450, n=2)
    y = (norm(vo) + 0.5 * norm(horn)) * env_pts(n, [(0, 0), (1.0, 0.8), (2.2, 1.0), (3.4, 0.7), (d, 0)])
    return far(y, rng, 150, "valley", wet=1.1)
