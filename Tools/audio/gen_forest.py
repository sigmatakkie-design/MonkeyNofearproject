"""Forest sounds (Forest/): wind bed, insects, frogs, branches, distant calls, stream."""
from __future__ import annotations

import numpy as np

from mnf_dsp import *  # noqa: F401,F403
from mnf_sfx import *  # noqa: F401,F403
from mnf_registry import category

S = category("Forest")


def whistle_shape(rng, k=5, lo=600, hi=2200, width=5.0, gain=6.0):
    cs = np.exp(rng.uniform(np.log(lo), np.log(hi), k))

    def shape(f):
        g = np.ones_like(f) * 0.15
        for c in cs:
            g = g + gain * np.exp(-0.5 * ((f - c) / width) ** 2)
        return g
    return shape


# --------------------------------------------------------------------- distant life (for the bed)
def bird_twitter(rng):
    out = np.zeros(ns(1.2))
    t = 0.0
    base = rng.uniform(3000, 4200)
    for _ in range(int(rng.integers(3, 6))):
        d = rng.uniform(0.05, 0.11)
        n = ns(d)
        f = env_pts(n, [(0, base * rng.uniform(0.9, 1.2)), (d * 0.5, base * rng.uniform(1.2, 1.5)), (d, base * rng.uniform(0.8, 1.0))])
        f = f * (1 + 0.04 * np.sin(2 * np.pi * rng.uniform(60, 90) * tt(n)))
        tw = (np.sin(2 * np.pi * phase_cycles(f)) + 0.15 * np.sin(4 * np.pi * phase_cycles(f))) * env_hann(n)
        place(out, tw, t)
        t += d + rng.uniform(0.04, 0.12)
    return out


def woodpecker(rng):
    out = np.zeros(ns(1.0))
    f0 = rng.uniform(700, 1000)
    for k in range(int(rng.integers(10, 16))):
        place(out, norm(strike("wood", f0, 0.06, rng, 0.95, 0.6, 0.3)) * (1 - k * 0.04), k / rng.uniform(14, 17))
    return out


@S("amb_forest_bed", stereo=True, loop=True, dur=30.0,
   desc="Night forest: gusting wind through branches and needles, leaf rustle, very sparse distant life (stereo 30 s loop).")
def amb_forest_bed(rng, v):
    L = ns(30.0)
    g = 0.3 + 0.7 * rand_walk01(L, 0.07, rng)
    chans = []
    common_rumble = shaped_noise(L, rng, -6, 20, 200)
    whistle = whistle_shape(rng)
    for c in range(2):
        gc = np.roll(g, ns(0.9) * c)
        wind = shaped_noise(L, rng, -4.0, 60, 2600) * gc
        needles = shaped_noise(L, rng, -1.0, 1800, 7000) * gc ** 2 * (0.6 + 0.4 * rand_walk01(L, 4, rng))
        wh = shaped_noise(L, rng, 0, 400, 3000, whistle) * gc ** 3
        leaves = rustle_arr(gc ** 2.5, rng, 160, 1300, 8000, 0.0, circular=True)
        ch = (norm(wind) + 0.25 * norm(needles) + 0.06 * norm(wh) + 0.12 * norm(leaves)
              + 0.4 * norm(common_rumble) * (0.5 + 0.5 * gc))
        chans.append(ch)
    y = np.stack(chans, 1)
    life = np.zeros((L, 2))
    makers = [bird_twitter, woodpecker, bird_twitter]
    for k, mk in enumerate(makers):
        ev = far(norm(mk(rng)), rng, rng.uniform(45, 80), "forest", stereo=True)
        p = rng.uniform(-0.8, 0.8)
        gl, gr = np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4)
        t0 = rng.uniform(0, 30)
        place_circ(life[:, 0], ev[:, 0] * gl, ns(t0))
        place_circ(life[:, 1], ev[:, 1] * gr, ns(t0))
    return y + 0.05 * life / (peak(life) + 1e-9) * peak(y)


def cricket_chirp(rng, f, pulses, pulse_len, pulse_rate):
    d = pulses / pulse_rate + 0.02
    out = np.zeros(ns(d))
    for p in range(pulses):
        n = ns(pulse_len)
        fr = f * (1 - 0.02 * tt(n) / pulse_len)
        x = (np.sin(2 * np.pi * phase_cycles(fr)) + 0.08 * np.sin(4 * np.pi * phase_cycles(fr))) * env_hann(n) ** 0.7
        place(out, x * rng.uniform(0.8, 1.0), p / pulse_rate)
    return out


@S("amb_forest_insects_loop", stereo=True, loop=True, dur=15.0, spatial=False, norm=("rms", -27.0, -4.0),
   desc="Crickets and insect chorus layer (stereo 15 s loop) - muted near threats.")
def amb_forest_insects_loop(rng, v):
    L = ns(15.0)
    t = tt(L)
    out = np.zeros((L, 2))
    for c in range(6):
        f = rng.uniform(3800, 5200)
        pulses = int(rng.integers(3, 6))
        chirp = cricket_chirp(rng, f, pulses, rng.uniform(0.012, 0.02), rng.uniform(30, 48))
        rate = rng.uniform(1.4, 2.8)
        count = int(round(15.0 * rate))
        gain = rng.uniform(0.25, 1.0)
        p = rng.uniform(-0.9, 0.9)
        gl, gr = np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4)
        start = rng.uniform(0, 1)
        for k in range(count):
            i = int((start + k) * L / count + rng.normal(0, 200))
            a = gain * rng.uniform(0.85, 1.0)
            place_circ(out[:, 0], chirp * a * gl, i)
            place_circ(out[:, 1], chirp * a * gr, i)
    for c in range(2):
        k1 = shaped_noise(L, rng, 0, 6000, 9000) * (0.5 + 0.5 * np.cos(2 * np.pi * 60 * t + c)) ** 8
        k2 = shaped_noise(L, rng, 0, 7500, 8800) * (0.5 + 0.5 * np.cos(2 * np.pi * 45 * t + 2 * c)) ** 6
        swell = 0.7 + 0.3 * np.sin(2 * np.pi * (1 / 15.0) * t + c)
        out[:, c] += (0.05 * norm(k1) + 0.035 * norm(k2)) * swell
    floor = np.stack([shaped_noise(L, rng, -3, 100, 3000) for _ in range(2)], 1) * 0.006
    return out + floor


def frog_ribbit(rng, f0, scale):
    pulses = int(rng.integers(2, 4))
    out = np.zeros(ns(0.4))
    for p in range(pulses):
        d = rng.uniform(0.03, 0.06)
        n = ns(d)
        f = env_pts(n, [(0, f0 * 0.9), (d * 0.5, f0 * 1.05), (d, f0 * 0.95)])
        src = glottal(f, rng, 0.03, 0.2, 0.4, 0.05, 0.4)
        x = formant(src, [(np.full(n, 700.0 * scale), np.full(n, 150.0), 1.0),
                          (np.full(n, 1900.0 * scale), np.full(n, 250.0), 0.5)])
        place(out, norm(x) * env_hann(n) ** 0.5, p * rng.uniform(0.06, 0.09))
    return out


@S("frogs_loop", loop=True, dur=8.0, norm=("peak", -3.0), desc="Frogs calling around a pond, near and far (mono 8 s loop).")
def frogs_loop(rng, v):
    L = ns(8.0)
    out = np.zeros(L)
    for fr in range(4):
        f0 = rng.uniform(150, 320)
        sc = rng.uniform(0.8, 1.3)
        gain = rng.uniform(0.3, 1.0)
        dist = rng.uniform(5, 40)
        count = int(rng.integers(3, 7))
        times = np.sort(rng.uniform(0, 8, count))
        for t in times:
            call = frog_ribbit(rng, f0, sc)
            call = lp(call, 9000 / (1 + dist / 15))
            place_circ(out, gain * norm(call), ns(t))
    # a couple of peepers
    for _ in range(6):
        n = ns(0.12)
        f = env_pts(n, [(0, 2600), (0.12, 3100)])
        pe = np.sin(2 * np.pi * phase_cycles(f)) * env_hann(n)
        place_circ(out, 0.15 * pe, int(rng.uniform(0, L)))
    chorus = shaped_noise(L, rng, -2, 400, 2500) * (0.5 + 0.5 * rand_walk01(L, 8, rng)) * 0.02
    y = out + chorus
    ir = reverb_ir(1.2, rng, **{k: v_ for k, v_ in SPACES["forest"].items() if k != "rt60"})
    return y + 0.35 * circ_conv(y, ir) * (rms(y) / (rms(circ_conv(y, ir)) + 1e-9))


@S("wind_gust", variants=3, dur=3.5, desc="A gust of wind swelling through the trees, leaves stirring.")
def wind_gust(rng, v):
    d = rng.uniform(3.0, 4.0)
    n = ns(d)
    pk = rng.uniform(0.35, 0.55) * d
    e = env_pts(n, [(0, 0), (pk * 0.6, 0.5), (pk, 1.0), (pk + d * 0.2, 0.6), (d, 0)])
    e = e * (0.8 + 0.2 * rand_walk01(n, 3, rng))
    wind = tvf(pink(n, rng), "lp", 250 + 1800 * e, 0.8) * e
    body = tvf(pink(n, rng), "bp", 300 + 1200 * e, 1.5) * e ** 1.5
    wh = shaped_noise(n, rng, 0, 400, 3000, whistle_shape(rng, 3)) * e ** 3
    leaves = rustle_arr(e ** 2, rng, 700, 1300, 9000, 0.3)[:n]
    rum = lp(white(n, rng), 120, n=2) * e
    return norm(wind) + 0.4 * norm(body) + 0.1 * norm(wh) + 0.35 * norm(leaves) + 0.3 * norm(rum)


def wood_fracture(rng, size=0.5):
    """Branch crack: cascade of micro-fractures + splinter crackle."""
    span = lerp(0.006, 0.05, size)
    out = np.zeros(ns(span + 0.4))
    cracks = int(lerp(3, 14, size))
    for k in range(cracks):
        t = span * (k / cracks) ** 1.5 + rng.uniform(0, 0.003)
        f0 = rng.uniform(lerp(900, 300, size), lerp(2200, 900, size))
        place(out, norm(strike("wood", f0, 0.25, rng, 1.0, 0.5, 0.7)) * rng.uniform(0.4, 1.0), t)
    place(out, 0.4 * rustle(0.1 + span, rng, [(0, 1), (0.1 + span, 0)], 2500, 2000, 10000, 0.2), 0)
    if size > 0.5:
        place(out, 0.6 * norm(thump(0.2, rng, 150, 80, 0.06, 0.6, 1500)), 0)
    return out


@S("branch_snap", variants=4, dur=1.0, desc="Twig / branch cracking somewhere out in the dark (near to far).")
def branch_snap(rng, v):
    size = [0.35, 0.2, 0.75, 0.6][v]
    dist = [10, 25, 40, 70][v]
    x = wood_fracture(rng, size)
    if v in (2, 3):  # bigger branches: debris settles after
        place(x, 0.3 * rustle(0.5, rng, [(0, 0), (0.05, 1), (0.5, 0)], 500, 1500, 8000), rng.uniform(0.15, 0.3))
    return far(x, rng, dist, "forest")


@S("tree_creak", variants=3, dur=2.5, desc="Wooden trunk swaying and groaning.")
def tree_creak(rng, v):
    d = rng.uniform(2.0, 3.0)
    r0 = rng.uniform(7, 14)
    rate = [(0, r0), (d * 0.3, r0 * 2.2), (d * 0.5, r0 * 1.4), (d * 0.7, r0 * 3.0), (d, r0)]
    pres = [(0, 0), (d * 0.2, 0.8), (d * 0.45, 1.0), (d * 0.7, 0.9), (d, 0)]
    c = creak(d, rng, rate, "wood", rng.uniform(110, 200), pres, 0.35, decay=1.4, hiss=0.03)
    trunk = lp(c, 500, n=2)
    return space(mix(norm(c), 0.6 * norm(trunk)), rng, "forest", wet=0.3)


@S("leaves_rustle", variants=3, dur=1.3, desc="Something brushing through leafy undergrowth.")
def leaves_rustle(rng, v):
    d = rng.uniform(1.0, 1.6)
    pts = [(0, 0)]
    t = 0.0
    while t < d - 0.2:
        t += rng.uniform(0.15, 0.4)
        pts += [(min(t, d - 0.1), rng.uniform(0.5, 1.0)), (min(t + 0.12, d - 0.05), rng.uniform(0.1, 0.4))]
    pts.append((d, 0))
    return rustle(d, rng, pts, 800, 1100, 9000, 0.4)


@S("distant_call", variants=4, dur=3.5, desc="Unidentifiable animal far away: owl-like, fox-like, a bark, and one that is slightly wrong.")
def distant_call(rng, v):
    if v == 0:   # owl-like hoots
        out = np.zeros(ns(2.2))
        for k, (t, d) in enumerate([(0.0, 0.42), (0.75, 0.2), (1.0, 0.22), (1.3, 0.6)]):
            n = ns(d)
            f0 = env_pts(n, [(0, 330), (d * 0.3, 360), (d, 300)])
            h = formant(glottal(f0, rng, 0.004, 0.02, 0.85, 0.12), vowel_tracks(n, "u", 0.95)) * env_hann(n) ** 0.6
            place(out, norm(h), t)
        return far(out, rng, 60, "forest")
    if v == 1:   # fox / vixen scream
        out = np.zeros(ns(2.2))
        for t in (0.0, 1.0):
            d = rng.uniform(0.5, 0.7)
            n = ns(d)
            f0 = env_pts(n, [(0, 700), (0.1, 1050), (d * 0.6, 900), (d, 600)])
            src = glottal(f0, rng, 0.03, 0.2, 0.5, 0.2, 0.5, subharm=0.35)
            x = formant(src, vowel_tracks(n, [(0, "e"), (d * 0.4, "a"), (d, "o")], 1.6, 1.4))
            place(out, sat(norm(x), 2.0) * env_pts(n, [(0, 0), (0.04, 1), (d * 0.7, 0.8), (d, 0)]), t)
        return far(out, rng, 50, "forest")
    if v == 2:   # sharp barks
        out = np.zeros(ns(2.0))
        for k in range(3):
            d = 0.16
            n = ns(d)
            f0 = env_pts(n, [(0, 650), (0.04, 720), (d, 420)])
            x = formant(glottal(f0, rng, 0.03, 0.2, 0.5, 0.35, 0.4), vowel_tracks(n, [(0, "h"), (0.03, "a"), (d, "o")], 1.3))
            place(out, sat(norm(x), 2.2) * env_pts(n, [(0, 0), (0.01, 1), (d, 0)]), k * rng.uniform(0.45, 0.6))
        return far(out, rng, 65, "forest")
    # v == 3: slightly wrong - hoots that sink too far, vowels drift towards a human 'ah... i'
    out = np.zeros(ns(3.2))
    specs = [(0.0, 0.5, 340, 300, [(0, "u")]), (0.8, 0.7, 320, 230, [(0, "u"), (0.7, "o")]),
             (1.75, 1.2, 300, 120, [(0, "o"), (0.5, "a"), (1.2, "i")])]
    for k, (t, d, fa, fb, seq) in enumerate(specs):
        n = ns(d)
        f0 = env_pts(n, [(0, fa), (d, fb)]) * (1 + 0.03 * np.sin(2 * np.pi * 1.3 * tt(n)))
        x = formant(glottal(f0, rng, 0.008, 0.04, 0.75, 0.15), vowel_tracks(n, seq, 0.95))
        e = env_hann(n) ** 0.6 if k < 2 else env_pts(n, [(0, 0), (d * 0.9, 1.0), (d, 0)])  # last one swells then stops dead
        place(out, norm(x) * e, t)
    return far(out, rng, 70, "forest")


@S("bird_flutter", variants=2, dur=1.2, desc="Bird startled off a branch: leaf rustle then wingbeats flying away.")
def bird_flutter(rng, v):
    out = np.zeros(ns(1.6))
    place(out, 0.5 * rustle(0.25, rng, [(0, 0), (0.02, 1), (0.25, 0)], 900), 0)
    t = 0.05
    rate = 14.0 if v == 0 else 9.0
    flaps = int(rng.integers(10, 16)) if v == 0 else int(rng.integers(7, 11))
    for k in range(flaps):
        d = 1.0 / rate * 0.8
        n = ns(d)
        f = band_noise(n, rng, 200 if v else 350, 3500 if v else 5000) * env_pts(n, [(0, 0), (d * 0.3, 1), (d, 0)])
        whump = lp(white(n, rng), 400, n=2) * env_pts(n, [(0, 0), (d * 0.35, 1), (d, 0)])
        a = (1 - k / flaps) ** 1.5
        flap = norm(f) + 0.6 * norm(whump)
        if v == 1 and k < 3:  # pigeon-like wing claps on take-off
            flap = mix(flap, 0.8 * norm(hp(white(ns(0.006), rng), 1000) * env_exp(ns(0.006), 0.005)))
        place(out, flap * a, t)
        t += 1.0 / rate * rng.uniform(0.9, 1.1)
        rate *= 0.97
    return out


@S("footsteps_foliage", variants=4, dur=0.8, desc="Something heavy stepping slowly into undergrowth.")
def footsteps_foliage(rng, v):
    d = rng.uniform(0.6, 0.85)
    out = np.zeros(ns(d + 0.2))
    place(out, norm(thump(0.4, rng, rng.uniform(75, 95), rng.uniform(40, 50), 0.2, 0.9, 500)), 0.03)
    place(out, 0.8 * rustle(d, rng, [(0, 0.3), (0.05, 1.0), (0.2, 0.6), (d, 0)], 1500, 900, 8000, 0.5), 0)
    if v % 2 == 0:
        place(out, 0.5 * wood_fracture(rng, 0.3), rng.uniform(0.05, 0.15))
    place(out, 0.3 * crumble(0.25, rng, [(0, 1), (0.25, 0)], 60, 0.02, 0.2), 0.04)
    return out


@S("stream_loop", loop=True, dur=6.0, desc="Babbling forest stream: bubbling water texture (mono 6 s loop).")
def stream_loop(rng, v):
    L = ns(6.0)
    out = np.zeros(L)
    bank = []
    for _ in range(120):
        f0 = np.exp(rng.uniform(np.log(250), np.log(2600)))
        bank.append(bubble(f0, rng.uniform(0.03, 0.09), rng, rng.uniform(0.1, 0.9)) / np.sqrt(f0 / 250))
    for _ in range(2200):
        place_circ(out, bank[rng.integers(len(bank))] * rng.lognormal(0, 0.6), int(rng.uniform(0, L)))
    rush = shaped_noise(L, rng, -2.0, 120, 7000) * (0.75 + 0.25 * rand_walk01(L, 1.5, rng))
    y = norm(out) + 0.35 * norm(rush)
    return circ(lambda z: lp(z, 9000), y)


@S("crow_caw", variants=2, dur=1.2, desc="Crow cawing from a tree: harsh, rough 'kaaw'.")
def crow_caw(rng, v):
    caws = 3 if v == 0 else 2
    out = np.zeros(ns(0.45 * caws + 0.3))
    for k in range(caws):
        d = rng.uniform(0.24, 0.34)
        n = ns(d)
        f0 = env_pts(n, [(0, 520), (0.05, 600), (d * 0.6, 520), (d, 400)]) * rng.uniform(0.9, 1.1)
        src = glottal(f0, rng, 0.04, 0.3, 0.45, 0.35, 0.6, subharm=0.45)
        x = formant(src, vowel_tracks(n, [(0, "ae"), (d * 0.5, "a"), (d, "o")], 1.45, 1.6))
        x = sat(norm(x), 2.5) * env_pts(n, [(0, 0), (0.02, 1), (d * 0.75, 0.8), (d, 0)])
        place(out, x, k * rng.uniform(0.38, 0.45))
    return far(out, rng, 15, "forest", wet=0.25)
