"""Mine sounds (Mine/): ambience beds, water, rock falls, machinery, PA recordings, phantoms."""
from __future__ import annotations

import numpy as np
import scipy.signal as sps

from mnf_dsp import *  # noqa: F401,F403
from mnf_sfx import *  # noqa: F401,F403
from mnf_registry import category
from gen_bunker import chain_layer, babble, peaks_shape

S = category("Mine")


def drip_sound(rng, f0=None, rise=None, double=False):
    out = np.zeros(ns(0.35))
    f0 = f0 or np.exp(rng.uniform(np.log(500), np.log(2200)))
    place(out, 0.25 * norm(band_noise(ns(0.008), rng, 2500, 12000) * env_exp(ns(0.008), 0.005)), 0)
    place(out, bubble(f0, 0.15, rng, rise if rise is not None else rng.uniform(0.8, 2.2)), 0.002)
    if double:
        place(out, 0.4 * bubble(f0 * rng.uniform(1.3, 1.8), 0.08, rng, 1.5), rng.uniform(0.06, 0.12))
    return out


def circ_events(L, rng, items, stereo=True):
    """items: list of (mono_signal_with_tail, t_sec, pan)."""
    out = np.zeros((L, 2)) if stereo else np.zeros(L)
    for x, t, p in items:
        if stereo:
            gl, gr = np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4)
            if x.ndim == 2:
                place_circ(out[:, 0], x[:, 0] * gl, ns(t))
                place_circ(out[:, 1], x[:, 1] * gr, ns(t))
            else:
                place_circ(out[:, 0], x * gl, ns(t))
                place_circ(out[:, 1], x * gr, ns(t))
        else:
            place_circ(out, x, ns(t))
    return out


@S("amb_mine_bed", stereo=True, loop=True, dur=30.0,
   desc="Mine tunnels: low rumble, distant cave drips, slow air movement (stereo 30 s loop).")
def amb_mine_bed(rng, v):
    L = ns(30.0)
    tunnel = peaks_shape([63, 126, 189, 252], 4.0, 3.0)
    common = shaped_noise(L, rng, -6, 18, 160)
    chans = []
    for c in range(2):
        rum = shaped_noise(L, rng, -6, 18, 180)
        air = shaped_noise(L, rng, -3, 120, 1800, tunnel) * (0.5 + 0.5 * rand_walk01(L, 0.12, rng))
        chans.append(0.7 * norm(common) + 0.5 * norm(rum) + 0.35 * norm(air))
    y = np.stack(chans, 1) * (0.85 + 0.15 * smooth_rand(L, 0.05, rng))[:, None]
    items = []
    for k in range(12):
        d = drip_sound(rng, double=rng.random() < 0.3)
        d = far(d, rng, rng.uniform(15, 50), "cave", stereo=True)
        items.append((norm(d) * rng.uniform(0.3, 1.0), rng.uniform(0, 30), rng.uniform(-0.9, 0.9)))
    drips = circ_events(L, rng, items)
    return y + 0.12 * drips


@S("amb_mine_deep_bed", stereo=True, loop=True, dur=30.0,
   desc="Deep mine: darker sub-bass pressure, faint distant metallic stress groans and pings (stereo 30 s loop).")
def amb_mine_deep_bed(rng, v):
    L = ns(30.0)
    t = tt(L)
    common = shaped_noise(L, rng, -7, 14, 90)
    swell = 0.7 + 0.3 * np.sin(2 * np.pi * t / 15.0) * np.sin(2 * np.pi * t / 30.0 + 0.7)
    chans = []
    for c in range(2):
        sub = shaped_noise(L, rng, -7, 14, 110)
        air = shaped_noise(L, rng, -4, 70, 700) * (0.5 + 0.5 * rand_walk01(L, 0.08, rng))
        chans.append((0.8 * norm(common) + 0.45 * norm(sub)) * swell + 0.2 * norm(air))
    y = np.stack(chans, 1)
    items = []
    for k in range(3):
        g = creak(rng.uniform(1.5, 2.5), rng, [(0, 14), (1.0, 26), (2.5, 12)], "metal", rng.uniform(80, 140),
                  [(0, 0), (0.5, 1), (2.0, 0.6), (2.5, 0)], 0.3, 0.9, 0.01)
        items.append((norm(far(g, rng, 70, "cave", stereo=True)), rng.uniform(0, 30), rng.uniform(-0.8, 0.8)))
    for k in range(3):
        p = lp(strike("metal", rng.uniform(300, 600), 1.5, rng, 0.8, 1.0), 2000)
        items.append((0.6 * norm(far(p, rng, 90, "cave", stereo=True)), rng.uniform(0, 30), rng.uniform(-0.9, 0.9)))
    for k in range(3):
        items.append((0.5 * norm(far(drip_sound(rng), rng, 50, "cave", stereo=True)), rng.uniform(0, 30), rng.uniform(-0.9, 0.9)))
    ev = circ_events(L, rng, items)
    return y + 0.1 * ev


@S("drip", variants=6, dur=0.15, desc="Cave water drip into a pool (short cave early reflections).")
def drip(rng, v):
    f0 = [700, 1100, 1600, 2100, 900, 1300][v] * rng.uniform(0.9, 1.1)
    x = drip_sound(rng, f0, double=v in (4, 5))
    return early_reflections(x, rng, 6, 0.06, 0.3, 3500)


@S("water_trickle_loop", loop=True, dur=5.0, desc="Thin trickle of water down rock (mono 5 s loop).")
def water_trickle_loop(rng, v):
    L = ns(5.0)
    out = np.zeros(L)
    bank = [bubble(np.exp(rng.uniform(np.log(800), np.log(4000))), rng.uniform(0.02, 0.05), rng, rng.uniform(0.3, 1.2)) for _ in range(80)]
    for _ in range(900):
        place_circ(out, bank[rng.integers(80)] * rng.lognormal(0, 0.7), int(rng.uniform(0, L)))
    film = shaped_noise(L, rng, -1, 800, 9000) * (0.7 + 0.3 * rand_walk01(L, 3, rng))
    return norm(out) + 0.2 * norm(film)


@S("rock_fall_small", variants=3, dur=1.0, desc="A few pebbles falling and bouncing.")
def rock_fall_small(rng, v):
    out = np.zeros(ns(1.3))
    for k in range(int(rng.integers(3, 8))):
        s = rng.uniform(0.1, 0.45)
        peb = pebble(rng, s)
        t0 = rng.uniform(0, 0.6)
        for tb, gb in zip(*bounce_times(rng, t0, rng.uniform(0.06, 0.15), 0.5, int(rng.integers(2, 4)))):
            place(out, peb * gb * rng.uniform(0.6, 1.0), tb)
    place(out, 0.15 * norm(grit(0.8, rng, lambda t: 150 * np.exp(-t / 0.3))), 0)
    return early_reflections(out, rng, 5, 0.04, 0.2)


@S("rock_fall_large", variants=2, dur=2.2, desc="Larger rockfall: heavy chunks, rumble and rubble.")
def rock_fall_large(rng, v):
    d = 2.2
    n = ns(d)
    out = np.zeros(ns(d + 0.3))
    for k in range(int(rng.integers(4, 7))):
        s = rng.uniform(0.6, 1.0)
        chunk = pebble(rng, s)
        t0 = rng.uniform(0, 1.0)
        for tb, gb in zip(*bounce_times(rng, t0, rng.uniform(0.1, 0.2), 0.4, 3)):
            place(out, chunk * gb, tb)
    place(out, 0.8 * crumble(d, rng, [(0, 0.3), (0.3, 1), (1.2, 0.6), (d, 0)], 150, 0.1, 0.7), 0)
    rum = lp(white(n, rng), 180, n=2) * env_pts(n, [(0, 0), (0.2, 1), (1.4, 0.5), (d, 0)])
    place(out, 0.5 * norm(rum), 0)
    return early_reflections(out, rng, 6, 0.05, 0.25)


def metal_bang(rng, f0=None):
    f0 = f0 or rng.uniform(120, 260)
    return mix(norm(strike("metal", f0, 2.5, rng, 0.9, 1.2, 0.4)), 0.6 * norm(strike("pipe", f0 * 1.7, 1.5, rng, 0.9, 0.8)),
               0.5 * norm(thump(0.4, rng, 140, 70, 0.1, 0.5, 900)))


@S("metal_impact_distant", variants=3, dur=3.0, desc="A metallic bang far away down the tunnels.")
def metal_impact_distant(rng, v):
    return far(metal_bang(rng), rng, rng.uniform(50, 80), "tunnel")


@S("metal_impact_repeat", dur=4.0, desc="Three identical metal bangs, each one farther away.")
def metal_impact_repeat(rng, v):
    bang = metal_bang(rng)
    out = np.zeros(ns(6.0))
    for k, (t, dist) in enumerate([(0.0, 25), (1.25, 55), (2.5, 100)]):
        r = np.random.default_rng(1234 + k)  # same tail character, different distance
        x = far(bang, r, dist, "tunnel")
        place(out, x * (1.0 / (1 + k * 0.9)), t)
    return out


@S("minecart_roll", dur=2.5, desc="Mine cart rolling past: rail joint clacks, rumble, wheel squeal, rattle.")
def minecart_roll(rng, v):
    d = 2.6
    n = ns(d)
    e = env_pts(n, [(0, 0), (0.6, 0.8), (1.3, 1.0), (2.1, 0.7), (d, 0)])
    rum = lp(white(n, rng), 400, n=2) * (0.7 + 0.3 * np.sin(2 * np.pi * 3.2 * tt(n)) ** 2)
    out = norm(rum) * e * 0.8
    t = 0.15
    while t < d - 0.2:
        for off in (0.0, 0.11):
            c = mix(norm(strike("metal", rng.uniform(400, 700), 0.3, rng, 0.9, 0.4)), 0.7 * norm(thump(0.15, rng, 160, 80, 0.04)))
            place(out, c * e[ns(t)] * rng.uniform(0.6, 1.0), t + off)
        t += rng.uniform(0.42, 0.5)
    sq = scrape(d, rng, [(0, 0), (0.7, 0), (0.9, 1), (1.3, 0.6), (1.5, 0), (1.9, 0.8), (2.2, 0)], "metal", 2100,
                2200, 0.08, 0.15, (2000, 8000), 1.2)
    out = out + 0.35 * norm(sq) * e
    rat = chain_layer(n, rng, 14.0)
    out = out + 0.3 * norm(rat) * e
    return early_reflections(out, rng, 6, 0.05, 0.2)


@S("electrical_buzz_loop", loop=True, dur=2.0, desc="Faulty junction box: harsh 100 Hz buzz with arcing crackle (2 s loop).")
def electrical_buzz_loop(rng, v):
    L = ns(2.0)
    y = mains_hum(L, rng, 50, amps=[0.2, 1.0, 0.6, 0.7, 0.4, 0.5, 0.3, 0.3], buzz=0.9, buzz_f=(900, 9000), flutter=0.3)
    crack = np.zeros(L)
    for _ in range(40):
        place_circ(crack, norm(band_noise(ns(0.004), rng, 1500, 12000)) * env_exp(ns(0.004), 0.003) * rng.uniform(0.2, 1.0), int(rng.uniform(0, L)))
    return circ(lambda z: sat(z, 1.6), norm(y) + 0.4 * crack)


@S("machinery_hum_loop", loop=True, dur=4.0, desc="Heavy mine machinery hum: motor, transformer, gear whine (4 s loop).")
def machinery_hum_loop(rng, v):
    L = ns(4.0)
    t = tt(L)
    mot = motor(L, rng, 25.0, 20, slot=(9, 18), whine=0.4)
    tr = np.sin(2 * np.pi * 100 * t) + 0.5 * np.sin(2 * np.pi * 150 * t) + 0.3 * np.sin(2 * np.pi * 300 * t)
    gear = np.sin(2 * np.pi * 1200 * t + 0.3 * np.sin(2 * np.pi * 25 * t)) * 0.15
    rum = shaped_noise(L, rng, -5, 25, 800) * (0.8 + 0.2 * smooth_rand(L, 1, rng))
    return norm(mot) + 0.3 * norm(tr) + gear + 0.5 * norm(rum)


def gravel_step(rng, heavy=0.6):
    out = np.zeros(ns(0.4))
    place(out, norm(thump(0.25, rng, 140, 70, 0.06, 0.8, 800)) * heavy, 0)
    place(out, 0.7 * crumble(0.2, rng, [(0, 1), (0.2, 0)], 220, 0.02, 0.25, dust=0.3), 0.005)
    return out


@S("footsteps_echo", variants=3, dur=2.0, desc="Phantom footsteps somewhere down the tunnel, reverberant.")
def footsteps_echo(rng, v):
    out = np.zeros(ns(2.2))
    steps = [3, 4, 4][v]
    t = 0.05
    for k in range(steps):
        place(out, gravel_step(rng) * rng.uniform(0.7, 1.0), t)
        t += rng.uniform(0.45, 0.6) * (1.25 if (v == 2 and k == steps - 2) else 1.0)  # hesitation
    return far(out, rng, rng.uniform(22, 35), "tunnel", wet=0.9)


@S("walkway_steps", variants=2, dur=1.4, desc="Footsteps on metal grating walkway: clang and rattle.")
def walkway_steps(rng, v):
    out = np.zeros(ns(1.6))
    f0 = rng.uniform(280, 420)
    modes = material_modes("metal", f0, rng, decay=0.5)
    t = 0.02
    for k in range(3):
        fr, t6, am = modes
        hit = strike("metal", f0, 0.6, rng, 0.75, modes=(fr, t6, am * rng.uniform(0.3, 1.3, len(am))))
        boot = thump(0.15, rng, 150, 90, 0.04, 0.8, 1500)
        step = mix(norm(hit), 0.6 * norm(boot))
        for r in range(2):
            step = place(step, 0.2 * norm(strike("metal_thin", f0 * rng.uniform(2, 4), 0.15, rng, 0.9, 0.3)), rng.uniform(0.015, 0.05))
        place(out, step * rng.uniform(0.7, 1.0), t)
        t += rng.uniform(0.42, 0.5)
    return early_reflections(out, rng, 6, 0.05, 0.25)


@S("warning_recording", variants=2, dur=3.5, desc="Old PA announcement: chime, then a distorted robotic voice babble that cuts off abruptly mid-word.")
def warning_recording(rng, v):
    d = 3.6
    out = np.zeros(ns(d))
    notes = [784, 659, 523] if v == 0 else [659, 784, 523]
    for k, f in enumerate(notes):
        place(out, 0.5 * norm(strike("bell", f * 2, 1.2, rng, 0.95, 0.4, 0.05)), 0.02 + 0.32 * k)
    vstart = 1.25
    cut = d - 0.65 + rng.uniform(-0.1, 0.1)
    vd = cut - vstart + 0.3
    n = ns(vd)
    f0 = np.full(n, 104.0 if v == 0 else 92.0)
    seq, amp = [], []
    t = 0.0
    vowels = ["a", "e", "i", "o", "u", "uh", "ae"]
    while t < vd:
        syl = rng.uniform(0.12, 0.2)
        seq.append((t + syl * 0.4, vowels[rng.integers(len(vowels))]))
        amp += [(t, 0.05), (t + syl * 0.25, 1), (t + syl * 0.8, 0.9), (t + syl, 0.1)]
        t += syl
    src = glottal(f0, rng, 0.0, 0.0, 0.5, 0.02, 0.0)
    voice = formant(src, vowel_tracks(n, seq, 1.0)) * env_pts(n, amp)
    voice = mix(norm(voice), 0.25 * ring(norm(voice), 31.0))
    cons = breath_noise(n, "s", rng) * np.clip(1 - env_pts(n, amp), 0, 1) ** 4
    voice = norm(voice[:n]) + 0.2 * norm(cons)
    place(out, voice, vstart)
    i_cut = ns(cut)
    out[i_cut:] = 0.0  # abrupt cut-off, mid-syllable
    pa = speaker(out, 450, 2600, 3.0, 1300)
    pa = crush(pa, 6, 3)
    pa = comb(pa, 0.0031, 0.35, 0.3)
    pa[i_cut:] = 0.0
    pop = norm(thump(0.05, rng, 200, 80, 0.02, 0.6, 2000)) * 0.4
    place(pa, pop, cut)
    hum = mains_hum(len(pa), rng, 50, buzz=0.3) * env_pts(len(pa), [(0, 0.0), (0.05, 1), (cut, 1), (cut + 0.001, 0), (d, 0)]) * 0.03
    pa = pa + hum
    return space(pa, rng, "tunnel", wet=0.3, rt=1.4)


@S("elevator_motor_loop", loop=True, dur=3.0, desc="Mine elevator hoist motor running, cable creak and cage rattle (3 s loop).")
def elevator_motor_loop(rng, v):
    L = ns(3.0)
    t = tt(L)
    mot = motor(L, rng, 20.0, 26, slot=(10, 20), whine=0.5)
    gear = np.sin(2 * np.pi * 800 * t) * (1 + 0.4 * np.sin(2 * np.pi * 20 * t)) * 0.2
    cable = np.zeros(L)
    for k in range(3):
        c = creak(0.4, rng, [(0, 30), (0.4, 45)], "metal_bar", rng.uniform(300, 500), [(0, 0), (0.1, 1), (0.4, 0)], 0.3, 0.6, 0.02)
        place_circ(cable, norm(c) * rng.uniform(0.5, 1.0), int((k + rng.uniform(0.2, 0.8)) * L / 3))
    rattle = chain_layer(L, rng, 6.0)
    rum = shaped_noise(L, rng, -5, 30, 600)
    return norm(mot) * 0.7 + gear + 0.35 * norm(cable) + 0.25 * norm(rattle) + 0.4 * norm(rum)


def cage_clank(rng):
    return mix(norm(strike("metal", rng.uniform(150, 240), 1.8, rng, 0.85, 1.0, 0.3)),
               0.6 * norm(strike("metal_thin", rng.uniform(500, 800), 0.8, rng, 0.9, 0.6)),
               0.7 * norm(thump(0.4, rng, 110, 50, 0.15, 0.6, 700)),
               0.4 * norm(chain_layer(ns(0.6), rng, 20.0)) * env_pts(ns(0.6), [(0, 1), (0.6, 0)]))


@S("elevator_clank", variants=2, dur=1.5, desc="Elevator cage clanking against its guides.")
def elevator_clank(rng, v):
    return early_reflections(cage_clank(rng), rng, 6, 0.05, 0.25)


@S("elevator_arrive", dur=2.0, desc="Elevator arrives: heavy cage stop clank, then the old arrival bell.")
def elevator_arrive(rng, v):
    out = np.zeros(ns(2.2))
    place(out, cage_clank(rng), 0)
    place(out, 0.7 * norm(strike("bell", 1250, 1.8, rng, 0.98, 0.7, 0.05)), 0.35)
    return early_reflections(out, rng, 6, 0.05, 0.25)


@S("scratch_metal", variants=3, dur=2.0, desc="Claws scraping the other side of a metal plate (muffled, ringing).")
def scratch_metal(rng, v):
    d = rng.uniform(1.8, 2.3)
    n = ns(d)
    plate = resonator_ir("metal", rng.uniform(110, 190), rng, 1.5, 1.0)
    exc = np.zeros(n)
    strokes = [(0.05, d * 0.55), (d * 0.6, d - 0.1)] if v != 1 else [(0.05, d - 0.1)]
    for a, b in strokes:
        for claw in range(3):
            m = ns(b - a)
            sp = env_pts(m, [(0, 0), (0.08, 1), ((b - a) * 0.7, 0.8), (b - a, 0)])
            ss = stick_slip(m, rng.uniform(250, 600) * (0.4 + sp), rng, 0.7, 0.8, sp)
            place(exc, ss + 0.05 * white(m, rng) * sp, a + claw * 0.012)
            exc[ns(a + claw * 0.012)] += 3.0  # claw tip contact
    y = sps.fftconvolve(exc, plate)[:n]
    y = lp(y, 3200, n=2)
    return norm(y)


@S("wall_knock", variants=2, dur=1.2, desc="Knocking on the rock wall from the other side.")
def wall_knock(rng, v):
    out = np.zeros(ns(1.4))
    knocks = 3 if v == 0 else 2
    t = 0.02
    for k in range(knocks):
        kn = mix(norm(strike("stone", rng.uniform(180, 260), 0.3, rng, 0.7, 2.5, 0.2, 14)), 0.9 * norm(thump(0.25, rng, 130, 70, 0.07, 0.6, 600)))
        place(out, lp(kn, 1400) * rng.uniform(0.8, 1.0), t)
        t += rng.uniform(0.3, 0.45)
    return space(out, rng, "tunnel", wet=0.2, rt=1.2)


@S("light_buzz_on", dur=1.0, desc="Work light switching on: relay click, filament surge buzz, thermal tink.")
def light_buzz_on(rng, v):
    d = 1.0
    n = ns(d)
    out = np.zeros(n)
    place(out, 0.6 * click(rng, "metal", 2800, 0.06, 0.95, 0.4, body_f=250), 0)
    m = n - ns(0.02)
    surge = mains_hum(m, rng, 50, buzz=0.9, buzz_f=(1200, 8000)) * env_pts(m, [(0, 0), (0.06, 1.6), (0.3, 0.8), (0.7, 0.55), (d, 0.0)])
    place(out, 0.6 * sat(surge, 1.5), 0.02)
    place(out, 0.3 * norm(strike("metal_bar", 6200, 0.3, rng, 1.0, 0.25)), 0.35)
    return out


@S("whisper_air", variants=2, dur=2.5, desc="Breathy air movement in the tunnel that could almost be a whisper.")
def whisper_air(rng, v):
    d = rng.uniform(2.2, 2.9)
    n = ns(d)
    seq, amp = [], []
    t = 0.3
    vowels = ["a", "e", "i", "o", "u", "uh", "sh", "s", "h"]
    amp.append((0, 0))
    while t < d - 0.4:
        syl = rng.uniform(0.18, 0.32)
        seq.append((t + syl * 0.5, vowels[rng.integers(len(vowels))]))
        amp += [(t, 0.15), (t + syl * 0.4, rng.uniform(0.6, 1.0)), (t + syl, 0.2)]
        t += syl + rng.uniform(0.0, 0.12)
    amp.append((d, 0))
    w = breath_noise(n, seq, rng, 1.0, 1.4, -1.5) * env_pts(n, amp)
    air = shaped_noise(n, rng, -3, 150, 6000) * env_pts(n, [(0, 0), (0.5, 0.7), (d - 0.5, 0.7), (d, 0)])
    y = norm(w) + 0.45 * norm(air)
    return space(y, rng, "tunnel", wet=0.35, rt=1.6)
