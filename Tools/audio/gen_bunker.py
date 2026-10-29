"""Bunker sounds (Bunker/): ambience, ventilation, lights, gate machinery, terminal, trade."""
from __future__ import annotations

import numpy as np
import scipy.signal as sps

from mnf_dsp import *  # noqa: F401,F403
from mnf_sfx import *  # noqa: F401,F403
from mnf_registry import category

S = category("Bunker")


def peaks_shape(centres, width, gain):
    def shape(f):
        g = np.ones_like(f)
        for c in centres:
            g = g + gain * np.exp(-0.5 * ((f - c) / width) ** 2)
        return g
    return shape


# --------------------------------------------------------------------- ambience
@S("amb_bunker_bed", stereo=True, loop=True, dur=20.0,
   desc="Bunker room tone: ventilation rumble, distant machinery thrum, faint mains tone (stereo 20 s loop).")
def amb_bunker_bed(rng, v):
    L = ns(20.0)
    t = tt(L)
    duct = peaks_shape([85, 170, 255, 340], 9.0, 2.5)
    common = shaped_noise(L, rng, -6.0, 22, 600, duct)
    chans = []
    for c in range(2):
        own = shaped_noise(L, rng, -5.0, 22, 700, duct)
        air = shaped_noise(L, rng, -3.0, 250, 5000) * (0.7 + 0.3 * rand_walk01(L, 0.3, rng))
        chans.append(0.7 * common + 0.6 * own + 0.12 * air)
    rumble = np.stack(chans, 1)
    rumble *= (0.85 + 0.15 * smooth_rand(L, 0.15, rng))[:, None]
    # distant machinery thrum (2.5 Hz chug, periodic in 20 s) + 33.35 Hz tone
    thr = np.zeros(L)
    pulse = lp(white(ns(0.25), rng), 120, n=2) * env_ar(ns(0.25), 0.02, 0.2)
    for k in range(50):
        place_circ(thr, norm(pulse) * (0.8 + 0.2 * np.sin(2 * np.pi * k / 50 * 3)), ns(k * 0.4) + 7)
    thr += 0.5 * np.sin(2 * np.pi * 33.35 * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.1 * t))
    mains = (np.sin(2 * np.pi * 100 * t) + 0.6 * np.sin(2 * np.pi * 100.05 * t + 1)
             + 0.4 * np.sin(2 * np.pi * 150 * t) + 0.25 * np.sin(2 * np.pi * 200 * t))
    # sparse distant clanks with reverb, wrapped around the loop
    events = np.zeros((L, 2))
    for k in range(3):
        f0 = rng.uniform(70, 140)
        cl = lp(strike("metal", f0, 2.0, rng, hardness=0.5, decay=1.2), 700, n=2)
        cl = space(cl, rng, "hall", wet=1.2, stereo=True)
        cl = cl * np.array([rng.uniform(0.4, 1.0), rng.uniform(0.4, 1.0)])
        tk = rng.uniform(0, 20)
        for ch in range(2):
            place_circ(events[:, ch], norm(cl[:, ch]), ns(tk))
    y = (norm(rumble) + 0.25 * norm(thr)[:, None] + 0.035 * norm(mains)[:, None] + 0.12 * events)
    return y


@S("vent_loop", loop=True, dur=6.0, desc="Air vent: duct hiss, fan blade tone and a loose louver rattle (6 s loop).")
def vent_loop(rng, v):
    L = ns(6.0)
    t = tt(L)
    air = shaped_noise(L, rng, -2.0, 60, 9000, peaks_shape([140 * k for k in range(1, 12)], 14.0, 1.8))
    air *= 0.85 + 0.15 * smooth_rand(L, 0.8, rng)
    blade = np.zeros(L)
    for k, a in enumerate([1.0, 0.5, 0.35, 0.2, 0.1], 1):
        blade += a * np.sin(2 * np.pi * 90 * k * t + rng.uniform(0, 6))
    blade *= 1 + 0.25 * np.sin(2 * np.pi * 15 * t)
    rattle = np.zeros(L)
    bank = [strike("metal_thin", rng.uniform(700, 1300), 0.08, rng, 0.9, 0.3) for _ in range(6)]
    for burst in range(2):
        t0 = rng.uniform(0, 6)
        for k in range(int(rng.integers(6, 14))):
            place_circ(rattle, bank[rng.integers(6)] * rng.uniform(0.3, 1.0), ns(t0 + k / 15.0 + rng.normal(0, 0.003)))
    return norm(air) + 0.18 * norm(blade) + 0.12 * norm(rattle)


@S("fluorescent_hum_loop", loop=True, dur=4.0, desc="Fluorescent tube: 100 Hz mains hum + ballast buzz (4 s loop).")
def fluorescent_hum_loop(rng, v):
    L = ns(4.0)
    y = mains_hum(L, rng, 50.0, buzz=0.35)
    return y + 0.02 * band_noise(L, rng, 3000, 12000)


@S("fluorescent_flicker", variants=3, dur=0.8, desc="Fluorescent tube flickering: starter tick + stuttering buzz bursts.")
def fluorescent_flicker(rng, v):
    d = rng.uniform(0.6, 1.0)
    n = ns(d + 0.2)
    out = np.zeros(n)
    hum = mains_hum(n, rng, 50.0, buzz=0.8, buzz_f=(1500, 9000))
    gate = np.zeros(n)
    t = 0.03
    while t < d:
        on = rng.uniform(0.02, 0.12)
        gate[ns(t):ns(t + on)] = rng.uniform(0.5, 1.0)
        t += on + rng.uniform(0.02, 0.1)
    gate = lp(gate, 250)
    out += hum * gate
    place(out, 0.8 * click(rng, "metal", 3800, 0.04, 0.98, 0.2), 0.0)
    place(out, 0.5 * click(rng, "glass", 5200, 0.06, 0.95, 0.3), rng.uniform(0.05, 0.2))
    crack = grit(d, rng, lambda tt_: 60 * np.ones_like(tt_), 3000, 12000)
    return mix(out, 0.15 * norm(crack) * 0.5)


@S("spark", variants=3, dur=0.5, desc="Electrical spark: sharp snap with arcing crackle tail.")
def spark(rng, v):
    d = rng.uniform(0.4, 0.6)
    n = ns(d)
    snap = hp(white(ns(0.004), rng), 1200) * env_exp(ns(0.004), 0.003)
    arc_n = ns(rng.uniform(0.06, 0.15))
    exc = stick_slip(arc_n, rng.uniform(150, 320), rng, 0.6, 0.8)
    arc = bw(sps.fftconvolve(exc, norm(band_noise(ns(0.003), rng, 1500, 14000)))[:arc_n], "highpass", 900, 2)
    arc = sat(norm(arc) * 2, 2.5) * env_pts(arc_n, [(0, 1), (arc_n / SR, 0.2)])
    tail = grit(d, rng, lambda t: 700 * np.exp(-t / 0.08) + 15, 2500, 14000)
    out = np.zeros(n)
    place(out, norm(snap), 0)
    place(out, 0.6 * arc, 0.002)
    place(out, 0.35 * norm(tail), 0.01)
    return early_reflections(out, rng, 4, 0.02, 0.2)


# --------------------------------------------------------------------- machinery loops
@S("generator_loop", loop=True, dur=4.0, desc="Diesel generator idling (750 rpm 4-cyl thrum, injector clatter, 4 s loop).")
def generator_loop(rng, v):
    L = ns(4.0)
    t = tt(L)
    out = np.zeros(L)
    cyl_amp = rng.uniform(0.75, 1.0, 4)
    exhaust_ir = resonator_ir("pipe", 92, rng, 0.25, 0.25)
    block_ir = resonator_ir("metal", 380, rng, 0.08, 0.15)
    pulse = np.zeros(L)
    tick = np.zeros(L)
    tick_g = norm(strike("metal_bar", 3600, 0.02, rng, 0.98, 0.1, 0.5))
    for k in range(100):  # 25 firings/s
        i = ns(k * 0.04 + 0.02) + int(rng.normal(0, 8))
        pulse[i % L] += cyl_amp[k % 4] * rng.uniform(0.9, 1.1)
        place_circ(tick, tick_g * rng.uniform(0.6, 1.0), i + ns(0.012))
    comb_ = circ_conv(pulse, exhaust_ir) + 0.4 * circ_conv(pulse, block_ir)
    exhaust = shaped_noise(L, rng, -3, 40, 2500) * (0.5 + 0.5 * np.maximum(np.sin(2 * np.pi * 25 * t), 0) ** 2)
    tone = np.sin(2 * np.pi * 25 * t) * 0.6 + np.sin(2 * np.pi * 50 * t) * 0.5 + np.sin(2 * np.pi * 12.5 * t) * 0.3
    y = norm(comb_) + 0.35 * norm(exhaust) + 0.25 * norm(tone) + 0.12 * norm(tick)
    return sat(norm(y), 1.4)


def chain_layer(L, rng, rate=9.0, amp=1.0):
    out = np.zeros(L)
    bank = [strike("metal_bar", rng.uniform(1200, 2600), 0.12, rng, 0.95, 0.35, 0.3) for _ in range(8)]
    count = int(round(rate * L / SR))
    for k in range(count):
        i = int(k * L / count + rng.normal(0, 60))
        place_circ(out, bank[rng.integers(8)] * rng.uniform(0.4, 1.0) * amp, i)
        if rng.random() < 0.4:
            place_circ(out, bank[rng.integers(8)] * rng.uniform(0.2, 0.5) * amp, i + int(rng.uniform(0.01, 0.03) * SR))
    return out


@S("gate_motor_loop", loop=True, dur=3.0, desc="Heavy gate drive: electric motor whine, gearbox, chain rattle, rolling rumble (3 s loop).")
def gate_motor_loop(rng, v):
    L = ns(3.0)
    t = tt(L)
    mot = motor(L, rng, 25.0, 30, slot=(12, 24), whine=0.6)
    gear = np.sin(2 * np.pi * 600 * t) * (1 + 0.3 * np.sin(2 * np.pi * 25 * t)) * 0.4
    chain = chain_layer(L, rng, 9.0)
    roll = shaped_noise(L, rng, -5, 30, 900) * (0.7 + 0.3 * np.sin(2 * np.pi * 3 * t) ** 2)
    y = norm(mot) * 0.6 + 0.25 * gear + 0.6 * norm(chain) + 0.6 * norm(roll)
    return circ(lambda z: lp(z, 7000), y)


@S("gate_start", dur=1.5, desc="Gate start: relay contactor clunk then motor spinning up, chain engages.")
def gate_start(rng, v):
    d = 1.6
    n = ns(d)
    out = np.zeros(n)
    place(out, norm(mix(click(rng, "metal", 2600, 0.1, 0.95, 0.6, body_f=180, body_amt=0.8),
                        0.5 * strike("metal", 240, 0.4, rng, 0.8, 0.4))), 0)
    buzz = mains_hum(ns(0.15), rng, 50, buzz=1.0) * env_ar(ns(0.15), 0.002, 0.12)
    place(out, 0.25 * buzz, 0.005)
    m = n - ns(0.08)
    f = 25.0 * np.clip(tt(m) / 1.0, 0, 1) ** 0.7 + 0.5
    amps = [1 / k ** 0.8 for k in range(1, 31)]
    amps[11] *= 2.4
    amps[23] *= 2.4
    mot = harmonic_tone(f, amps, rng=rng)
    gear = np.sin(2 * np.pi * phase_cycles(f * 24)) * 0.4
    env = env_pts(m, [(0, 0), (0.1, 0.4), (0.9, 1.0), (d, 1.0)])
    ch = np.zeros(m)
    ts = 0.35
    while ts < d - 0.1:
        rate = 9.0 * min(1, (ts - 0.2) / 0.8)
        place(ch, norm(strike("metal_bar", rng.uniform(1200, 2600), 0.12, rng, 0.95, 0.35, 0.3)) * rng.uniform(0.4, 1.0), ts)
        ts += 1 / max(rate, 3) * rng.uniform(0.8, 1.2)
    roll = lp(white(m, rng), 600, n=2) * env_pts(m, [(0, 0), (0.4, 0), (1.0, 1), (d, 1)])
    y = (0.6 * norm(mot) + 0.25 * gear) * env + 0.5 * norm(ch) + 0.5 * norm(roll)
    place(out, y, 0.08)
    place(out, 0.6 * norm(lp(strike("metal", 110, 1.0, rng, 0.6, 0.8), 1500)), 0.45)
    return early_reflections(out, rng, 5, 0.03, 0.2)


@S("gate_stop", dur=2.0, desc="Gate stop: motor winds down, heavy reverberant steel clank.")
def gate_stop(rng, v):
    d = 1.2
    m = ns(d)
    f = 25.0 * np.clip(1 - tt(m) / 0.45, 0, 1) ** 1.3 + 0.1
    amps = [1 / k ** 0.8 for k in range(1, 31)]
    mot = harmonic_tone(f, amps, rng=rng) * env_pts(m, [(0, 1), (0.45, 0.0), (d, 0)])
    out = np.zeros(ns(2.2))
    place(out, 0.2 * norm(mot), 0)
    t0 = 0.33
    clank = mix(norm(strike("metal", rng.uniform(85, 120), 2.0, rng, 0.75, 1.4, 0.5)),
                0.6 * norm(strike("metal", rng.uniform(300, 420), 1.2, rng, 0.9, 0.7)),
                0.8 * norm(thump(0.6, rng, 90, 40, 0.3, 0.6, 500)))
    place(out, clank, t0)
    for k in range(4):
        place(out, 0.15 * norm(strike("metal_bar", rng.uniform(1500, 2500), 0.1, rng, 0.95, 0.3)), t0 + 0.05 + 0.05 * k)
    return space(out, rng, "bunker", wet=0.55, rt=1.6)


@S("gate_alarm", loop=True, dur=1.0, desc="Gate warning: two-tone alarm beep through a horn speaker (exactly 1 s, loopable).")
def gate_alarm(rng, v):
    L = ns(1.0)
    t = tt(L)
    h = ns(0.5)
    y = np.zeros(L)
    for seg, f in ((0, 880.0), (1, 660.0)):
        tt_ = t[:h]
        w = np.zeros(h)
        for k in (1, 3, 5, 7, 9, 11):
            if f * k < 15000:
                w += np.sin(2 * np.pi * f * k * tt_) / k
        y[seg * h:(seg + 1) * h] = w
    env = np.ones(L)
    r = ns(0.006)
    for b in (0, h):
        idx = (np.arange(-r, r) + b) % L
        env[idx] = np.minimum(env[idx], 0.25 + 0.75 * np.abs(np.arange(-r, r)) / r)
    y = y * env
    return circ(lambda z: speaker(z, 400, 5000, 2.0, 1500), y)


# --------------------------------------------------------------------- controls / terminal
@S("button_press", dur=0.15, desc="Chunky industrial push-button press.")
def button_press(rng, v):
    out = np.zeros(ns(0.18))
    place(out, 0.4 * click(rng, "plastic", 1100, 0.05, 0.6, 0.6), 0)
    place(out, click(rng, "plastic", 1600, 0.08, 0.92, 0.8, body_f=220, body_amt=0.7), 0.016)
    place(out, 0.3 * click(rng, "metal", 3300, 0.05, 0.98, 0.3), 0.017)
    return out


@S("button_release", dur=0.12, desc="Push-button spring release (lighter click).")
def button_release(rng, v):
    out = np.zeros(ns(0.14))
    place(out, click(rng, "plastic", 2300, 0.06, 0.9, 0.6), 0)
    place(out, 0.25 * click(rng, "metal", 4200, 0.04, 0.98, 0.3), 0.004)
    return out


@S("lever_pull", dur=1.0, desc="Heavy lever pulled: ratchet pawl clicks then a solid clunk.")
def lever_pull(rng, v):
    out = np.zeros(ns(1.1))
    t = 0.02
    gaps = np.linspace(0.085, 0.05, 9)
    for g in gaps:
        place(out, 0.5 * click(rng, "metal", rng.uniform(2600, 3400), 0.05, 0.97, 0.4, body_f=600, body_amt=0.2), t)
        t += g * rng.uniform(0.9, 1.1)
    place(out, 0.25 * scrape(t, rng, [(0, 0.5), (t, 0.6)], "metal", 700, 300, 0.5, 0.6, (800, 5000), 0.3), 0.0)
    clunk = mix(norm(strike("metal", 210, 0.6, rng, 0.85, 0.6)), 0.8 * norm(thump(0.3, rng, 160, 70, 0.1, 0.5, 900)))
    place(out, clunk, t + 0.02)
    return early_reflections(out, rng, 5, 0.025, 0.2)


@S("terminal_boot", dur=2.0, desc="Old CRT terminal boot: relay, degauss thoom, flyback whine, POST beeps.")
def terminal_boot(rng, v):
    d = 2.1
    n = ns(d)
    out = np.zeros(n)
    place(out, 0.6 * click(rng, "metal", 2400, 0.08, 0.95, 0.5, body_f=200), 0)
    dg = mains_hum(ns(0.8), rng, 50, buzz=0.9) * env_pts(ns(0.8), [(0, 0), (0.05, 1), (0.25, 0.7), (0.8, 0)])
    place(out, 0.7 * sat(dg * 1.5, 2.0), 0.05)
    place(out, 0.5 * norm(thump(0.5, rng, 70, 45, 0.3, 0.3, 300)), 0.05)
    m = n - ns(0.25)
    whine = np.sin(2 * np.pi * phase_cycles(env_pts(m, [(0, 14000), (0.4, 15734), (2, 15734)]))) * env_pts(m, [(0, 0), (0.4, 1), (d, 1)])
    stat = grit(m / SR, rng, lambda t: 80 * np.exp(-t / 0.5) + 5, 4000, 14000)[:m]
    place(out, 0.05 * whine + 0.1 * norm(stat), 0.25)
    place(out, 0.06 * band_noise(n, rng, 200, 2000) * env_pts(n, [(0, 0), (0.3, 1), (d, 1)]), 0)
    place(out, 0.55 * beep(1000, 0.16, rng, "square", 0.003, 0.01, harm=0.0), 1.15)
    place(out, 0.45 * beep(1400, 0.07, rng, "square", 0.003, 0.01, harm=0.0), 1.5)
    place(out, 0.45 * beep(1870, 0.09, rng, "square", 0.003, 0.01, harm=0.0), 1.6)
    return out


@S("terminal_select", dur=0.08, desc="Terminal soft key beep.", norm=("peak", -3.0))
def terminal_select(rng, v):
    out = np.zeros(ns(0.09))
    place(out, 0.3 * click(rng, "plastic", 2200, 0.03, 0.9, 0.5), 0)
    place(out, beep(1200, 0.045, rng, "tri", 0.002, 0.015), 0.003)
    return out


@S("terminal_confirm", dur=0.25, desc="Terminal confirm: rising two-note chirp.")
def terminal_confirm(rng, v):
    out = np.zeros(ns(0.25))
    place(out, beep(880, 0.08, rng, "square", 0.002, 0.01, harm=0.0), 0)
    place(out, beep(1320, 0.12, rng, "square", 0.002, 0.04, harm=0.0), 0.09)
    return out


@S("terminal_error", dur=0.4, desc="Terminal error: low double buzz.")
def terminal_error(rng, v):
    out = np.zeros(ns(0.42))
    for k in range(2):
        b = osc(np.full(ns(0.14), 140.0), "square") * env_pts(ns(0.14), [(0, 0), (0.003, 1), (0.13, 1), (0.14, 0)])
        place(out, speaker(b, 250, 4000, 2.4), 0.2 * k)
    return out


@S("terminal_type", variants=3, dur=0.12, desc="Single mechanical keyboard keystroke (down + bottom-out + release).")
def terminal_type(rng, v):
    out = np.zeros(ns(0.16))
    place(out, 0.6 * click(rng, "plastic", rng.uniform(1900, 2800), 0.03, 0.95, 0.4), 0)
    place(out, click(rng, "plastic", rng.uniform(500, 800), 0.06, 0.8, 0.8, body_f=180, body_amt=0.5), rng.uniform(0.007, 0.014))
    place(out, 0.35 * click(rng, "plastic", rng.uniform(2200, 3200), 0.03, 0.95, 0.4), rng.uniform(0.07, 0.1))
    return out


# --------------------------------------------------------------------- trade
@S("purchase", dur=1.0, desc="Mechanical cash register 'ka-chunk', drawer roll and bell.")
def purchase(rng, v):
    out = np.zeros(ns(1.3))
    place(out, 0.6 * click(rng, "metal", 2800, 0.06, 0.95, 0.4), 0)
    chunk = mix(norm(strike("metal", 300, 0.4, rng, 0.85, 0.5)), 0.9 * norm(thump(0.25, rng, 180, 80, 0.08, 0.6, 900)),
                0.3 * norm(strike("metal_thin", 900, 0.3, rng, 0.9, 0.4)))
    place(out, chunk, 0.07)
    n = ns(0.24)
    roll = lp(stick_slip(n, 140, rng, 0.4, 0.5) + 0.3 * white(n, rng), 1500) * env_pts(n, [(0, 0), (0.03, 1), (0.24, 0.6)])
    place(out, 0.4 * norm(roll), 0.12)
    place(out, 0.6 * norm(strike("bell", 2100, 1.1, rng, 0.98, 0.35, 0.1)), 0.18)
    place(out, 0.6 * norm(mix(strike("metal", 260, 0.3, rng, 0.8, 0.4), thump(0.2, rng, 150, 70, 0.06, 0.6, 800))), 0.36)
    return early_reflections(out, rng, 4, 0.02, 0.15)


@S("sell_vacuum", dur=1.5, desc="Pneumatic tube suction: seal pop, roaring whoosh away, distant thunk.")
def sell_vacuum(rng, v):
    d = 1.6
    n = ns(d)
    out = np.zeros(n)
    place(out, 0.6 * norm(mix(bp(white(ns(0.03), rng), 800, 1.0) * env_exp(ns(0.03), 0.02), thump(0.1, rng, 200, 100, 0.03))), 0)
    m = ns(1.3)
    e = env_pts(m, [(0, 0), (0.05, 1), (0.35, 0.8), (1.1, 0.1), (1.3, 0)])
    src = pink(m, rng)
    tube = comb(src, 1 / 175.0, 0.8, 0.4)
    cf = env_pts(m, [(0, 2500), (0.4, 1500), (1.3, 500)])
    sw = tvf(tube, "lp", cf, 0.9) * e
    place(out, norm(sw), 0.02)
    far_thunk = lp(norm(mix(strike("metal", 400, 0.3, rng, 0.8, 0.4), thump(0.2, rng, 150, 80, 0.05))), 700)
    place(out, 0.25 * far_thunk, 1.2)
    return out


@S("coin_tick", dur=0.06, desc="Counter tick (mechanical number wheel advancing).", norm=("peak", -3.0))
def coin_tick(rng, v):
    out = np.zeros(ns(0.07))
    place(out, click(rng, "metal", 3100, 0.04, 0.97, 0.4), 0)
    place(out, 0.3 * click(rng, "plastic", 1400, 0.03, 0.9, 0.5), 0.003)
    return out


@S("dispenser_thunk", dur=0.9, desc="Pneumatic tube canister arriving: rising rush, thunk, air release hiss.")
def dispenser_thunk(rng, v):
    d = 1.0
    out = np.zeros(ns(d))
    m = ns(0.5)
    rush = comb(pink(m, rng), 1 / 160.0, 0.75, 0.4)
    rush = tvf(rush, "lp", env_pts(m, [(0, 400), (0.5, 3000)]), 0.8) * env_pts(m, [(0, 0), (0.45, 1), (0.5, 0.6)])
    place(out, 0.5 * norm(rush), 0)
    th = mix(norm(strike("plastic", 420, 0.3, rng, 0.8, 1.0)), 0.6 * norm(strike("metal", 900, 0.4, rng, 0.85, 0.4)),
             norm(thump(0.25, rng, 160, 70, 0.08, 0.7, 800)))
    place(out, th, 0.5)
    k = ns(0.4)
    hiss = band_noise(k, rng, 1500, 10000) * env_pts(k, [(0, 0), (0.02, 1), (0.4, 0)])
    place(out, 0.3 * norm(hiss), 0.55)
    return early_reflections(out, rng, 4, 0.02, 0.15)


# --------------------------------------------------------------------- radio
@S("radio_static_loop", loop=True, dur=4.0, desc="Radio static: band-limited hiss, crackle and a wandering heterodyne whistle (4 s loop).")
def radio_static_loop(rng, v):
    L = ns(4.0)
    t = tt(L)
    hiss = shaped_noise(L, rng, -1, 250, 3800) * (0.75 + 0.25 * smooth_rand(L, 3, rng))
    crack = np.zeros(L)
    bank = [norm(band_noise(ns(0.004), rng, 800, 6000)) * env_exp(ns(0.004), 0.003) for _ in range(10)]
    for _ in range(80):
        place_circ(crack, bank[rng.integers(10)] * rng.lognormal(0, 0.6), int(rng.uniform(0, L)))
    phase = 1250 * t + (180 / 0.5) * np.sin(2 * np.pi * 0.5 * t) / (2 * np.pi)
    whistle = np.sin(2 * np.pi * phase) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.25 * t) ** 2)
    y = norm(hiss) + 0.5 * norm(crack) + 0.05 * whistle
    return circ(lambda z: speaker(z, 300, 3600, 1.4, 1600), y)


def babble(dur, rng, f0_base=115.0, rate=5.0, scale=1.0):
    """Garbled speech-like formant babble: random vowels/consonants with intonation."""
    n = ns(dur)
    seq = []
    amp_pts = []
    t = 0.0
    vowels = ["a", "e", "i", "o", "u", "uh", "ae", "er"]
    while t < dur:
        syl = rng.uniform(0.6, 1.4) / rate
        seq.append((t + syl * 0.3, vowels[rng.integers(len(vowels))]))
        amp_pts += [(t, 0.05), (t + syl * 0.2, 1.0), (t + syl * 0.75, 0.8), (t + syl * 0.95, 0.1)]
        t += syl
    f0 = env_pts(n, [(0, f0_base * 1.1), (dur * 0.4, f0_base * 1.25), (dur, f0_base * 0.85)])
    f0 *= 1 + 0.08 * smooth_rand(n, 3, rng)
    src = glottal(f0, rng, 0.02, 0.1, 0.6, 0.08)
    voice = formant(src, vowel_tracks(n, seq, scale))
    amp = env_pts(n, amp_pts)
    cons = breath_noise(n, "s", rng) * np.clip(1.0 - amp, 0, 1) ** 4 * (rng.random() * 0.5 + 0.3)
    return norm(voice * amp) + 0.3 * norm(cons)


@S("radio_burst", variants=3, dur=2.5, desc="Radio interference burst with garbled, voice-like babble that warps unsettlingly.")
def radio_burst(rng, v):
    d = rng.uniform(2.2, 2.9)
    n = ns(d)
    vo = babble(d - 0.5, rng, rng.uniform(95, 130), rng.uniform(4.5, 6.0))
    if v == 0:    # voice slows and sinks mid-sentence
        vo = varispeed(vo, lambda t: np.where(t < 0.9, 1.0, np.maximum(0.45, 1.0 - (t - 0.9) * 0.8)))
    elif v == 1:  # a chunk plays backwards
        a, b = int(len(vo) * 0.35), int(len(vo) * 0.65)
        vo[a:b] = vo[a:b][::-1]
    else:         # second voice underneath, detuned and lower
        vo2 = resample_ratio(babble(d - 0.5, rng, 80, 4.0, 0.85), 0.92)
        vo = mix(vo, 0.6 * vo2)
    out = np.zeros(n)
    place(out, vo, 0.25)
    gate = np.clip(rand_walk01(n, 6, rng) * 2.5 - 0.4, 0, 1)
    hiss = band_noise(n, rng, 300, 3800) * (0.35 + 0.65 * (1 - gate))
    het = np.sin(2 * np.pi * phase_cycles(env_pts(n, [(0, 2400), (0.3, 900), (d, 1300)]))) * env_pts(n, [(0, 0.6), (0.4, 0.05), (d, 0.1)])
    y = out * gate + 0.5 * norm(hiss) + 0.12 * het
    y = speaker(y, 300, 3200, 2.6, 1500)
    y = crush(y, 7, 2)
    y *= env_pts(n, [(0, 0), (0.03, 1), (d - 0.05, 1), (d, 0)])
    sq = band_noise(ns(0.08), rng, 500, 6000) * env_exp(ns(0.08), 0.06)
    return place(np.concatenate([y, np.zeros(ns(0.1))]), 0.5 * norm(sq), d - 0.05)


# --------------------------------------------------------------------- structure
@S("distant_impact", variants=3, dur=3.0, desc="Deep structural boom from far away, long dark tail.")
def distant_impact(rng, v):
    boom = mix(norm(thump(2.5, rng, rng.uniform(55, 70), rng.uniform(26, 32), 1.4, 0.6, 300, 0.08)),
               0.5 * norm(lp(strike("metal", rng.uniform(55, 80), 2.5, rng, 0.4, 1.5), 600)),
               0.25 * norm(lp(crumble(1.2, rng, [(0, 0), (0.2, 1), (1.2, 0)], 60, 0.2, 0.7), 1500)))
    boom = lp(boom, 900, n=2)
    return space(boom, rng, "hall", wet=0.9, rt=3.0)


@S("structural_creak", variants=3, dur=2.0, desc="Metal structure under stress: slow stick-slip groan.")
def structural_creak(rng, v):
    d = rng.uniform(1.8, 2.4)
    r0 = rng.uniform(20, 32)
    rate = [(0, r0), (d * 0.3, r0 * 1.7), (d * 0.55, r0 * 1.2), (d * 0.75, r0 * rng.uniform(4, 9)), (d * 0.85, r0), (d, r0 * 0.6)]
    pres = [(0, 0), (0.15, 0.7), (d * 0.5, 1.0), (d * 0.8, 0.8), (d, 0)]
    g = creak(d, rng, rate, "metal", rng.uniform(110, 190), pres, 0.3, decay=0.8, hiss=0.02)
    return space(g, rng, "bunker", wet=0.3, rt=1.4)


@S("pipe_knock", variants=3, dur=1.2, desc="Knocking travelling inside the pipes.")
def pipe_knock(rng, v):
    f0 = rng.uniform(170, 320)
    pattern = {0: [0, 0.32, 0.64], 1: [0, 0.14, 0.62], 2: [0, 0.2, 0.42, 0.66, 0.92]}[v]
    out = np.zeros(ns(pattern[-1] + 1.2))
    for k, t in enumerate(pattern):
        hit = strike("pipe", f0 * rng.uniform(0.97, 1.03), 1.0, rng, 0.75, 0.8, 0.3)
        hit = mix(hit, 0.4 * comb(hit, 1 / (f0 * 0.5), 0.85, 0.5))
        dist = k / max(1, len(pattern) - 1) if v == 2 else 0.0
        hit = lp(hit, 6000 / (1 + 3 * dist))
        place(out, norm(hit) * (1 - 0.6 * dist) * rng.uniform(0.8, 1.0), t)
    return space(out, rng, "bunker", wet=0.18)


@S("water_drip_bunker", variants=3, dur=0.2, desc="Water drip in the bunker (puddle / on metal).")
def water_drip_bunker(rng, v):
    out = np.zeros(ns(0.4))
    if v == 1:
        place(out, 0.8 * norm(strike("metal", rng.uniform(2400, 3400), 0.3, rng, 0.9, 0.25, 0.2)), 0)
        place(out, 0.4 * bubble(rng.uniform(1500, 2000), 0.05, rng, 1.5), 0.004)
    else:
        f0 = rng.uniform(900, 1400) if v == 0 else rng.uniform(550, 750)
        place(out, 0.3 * norm(band_noise(ns(0.01), rng, 2000, 10000) * env_exp(ns(0.01), 0.006)), 0)
        place(out, bubble(f0, 0.12, rng, rng.uniform(1.0, 1.6)), 0.003)
    return early_reflections(out, rng, 5, 0.03, 0.3, 4000)
