"""Player sounds (Player/): hand taps on surfaces, body, vocals, inventory, swings."""
from __future__ import annotations

import numpy as np

from mnf_dsp import *  # noqa: F401,F403
from mnf_sfx import *  # noqa: F401,F403
from mnf_registry import category

S = category("Player")


# --------------------------------------------------------------------- hand taps
@S("hand_tap_ground", variants=4, dur=0.25, desc="Hand slapping soft dirt: low padded thump + grit.")
def hand_tap_ground(rng, v):
    d = 0.32
    th = thump(d, rng, f_hi=rng.uniform(130, 175), f_lo=rng.uniform(55, 75), t60=rng.uniform(0.07, 0.12),
               noise_amt=1.0, noise_lp=rng.uniform(650, 1100), sweep=0.012)
    palm = bp(white(ns(0.02), rng), rng.uniform(700, 1100), 0.7) * env_exp(ns(0.02), 0.012)
    dirt = grit(0.15, rng, lambda t: 500 * np.exp(-t / 0.025), 1800, 7000)
    litter = rustle(0.14, rng, [(0, 0), (0.005, 1), (0.13, 0)], 500, 1500, 7000, body=0.4)
    return mix(norm(th), 0.35 * norm(palm), 0.12 * norm(dirt), 0.1 * litter)


@S("hand_tap_wood", variants=3, dur=0.3, desc="Hollow wooden knock under a palm/knuckle.")
def hand_tap_wood(rng, v):
    f0 = rng.uniform(170, 260)
    body = strike("wood_hollow", f0, 0.45, rng, hardness=rng.uniform(0.4, 0.55), decay=rng.uniform(0.9, 1.3), noise=0.2)
    plank = strike("wood", f0 * rng.uniform(3.0, 4.2), 0.2, rng, hardness=0.6, noise=0.15)
    th = thump(0.2, rng, 150, 90, 0.05, 0.4, 600)
    return mix(norm(body), 0.5 * norm(plank), 0.3 * norm(th))


@S("hand_tap_metal", variants=4, dur=1.2, desc="Ringing clank of a hand hitting a metal panel.")
def hand_tap_metal(rng, v):
    f0 = rng.uniform(260, 520)
    ring = strike("metal", f0, 1.6, rng, hardness=rng.uniform(0.5, 0.65), decay=rng.uniform(0.55, 0.9), noise=0.2)
    clank = strike("metal_thin", f0 * rng.uniform(2.2, 3.4), 0.5, rng, hardness=0.7, decay=0.4, noise=0.3)
    out = mix(norm(ring), 0.45 * norm(clank), 0.25 * norm(thump(0.2, rng, 160, 90, 0.04, 0.5, 800)))
    # loose panel rattle a few ms later
    rat = strike("metal_thin", f0 * rng.uniform(1.4, 1.9), 0.3, rng, hardness=0.8, decay=0.25)
    return place(out, 0.2 * norm(rat), rng.uniform(0.015, 0.03))


@S("hand_tap_rock", variants=3, dur=0.25, desc="Dull click/thud on rock with a little grit.")
def hand_tap_rock(rng, v):
    click_ = strike("stone", rng.uniform(900, 1500), 0.15, rng, hardness=0.7, decay=0.8, noise=0.3)
    th = thump(0.2, rng, rng.uniform(140, 180), 80, 0.05, 0.6, 700)
    g = grit(0.25, rng, lambda t: 260 * np.exp(-t / 0.05), 2500, 9000)
    return mix(0.8 * norm(click_), norm(th), 0.18 * norm(g))


@S("hand_tap_foliage", variants=3, dur=0.45, desc="Hand pushing into leaves: leafy crinkle rustle.")
def hand_tap_foliage(rng, v):
    d = rng.uniform(0.4, 0.55)
    r = rustle(d, rng, [(0, 0), (0.012, 1), (0.1, 0.55), (d * 0.8, 0.12), (d, 0)], 1100, 1400, 9500, body=0.45)
    th = thump(0.15, rng, 140, 90, 0.04, 0.8, 500)
    return mix(r, 0.2 * norm(th))


@S("hand_tap_mud", variants=2, dur=0.5, desc="Wet squelch of a hand in mud, with suction release.")
def hand_tap_mud(rng, v):
    a = wet_squelch(0.35, rng, rng.uniform(220, 300), rng.uniform(800, 1100), 4.0, 5, 0.006)
    suck = wet_squelch(0.25, rng, 1100, 380, 6.0, 3, 0.04, bub_f=(400, 1200))
    th = thump(0.2, rng, 120, 60, 0.07, 1.0, 400)
    out = mix(norm(a), 0.5 * norm(th))
    return place(out, 0.45 * norm(suck), rng.uniform(0.18, 0.24))


@S("land_thud", variants=2, dur=0.6, desc="Monkey body landing on the ground: feet then hands, fur rustle.")
def land_thud(rng, v):
    main = thump(0.7, rng, rng.uniform(85, 100), rng.uniform(36, 44), 0.25, 1.0, 700, 0.02)
    second = thump(0.4, rng, 120, 55, 0.12, 0.8, 900)
    dirt = crumble(0.35, rng, [(0, 1), (0.3, 0)], 70, 0.02, 0.25, dust=0.4)
    fur = fabric(0.45, rng, [(0, 0), (0.02, 1), (0.4, 0)], 220, 400, 4500)
    out = mix(norm(main), 0.2 * norm(dirt), 0.18 * fur)
    return place(out, 0.5 * norm(second), rng.uniform(0.06, 0.09))


@S("hurt_grunt", variants=3, dur=0.35, desc="Short pained monkey vocal ('hoo' / 'ack'), formant synthesis.")
def hurt_grunt(rng, v):
    if v == 0:      # "hoo!"
        d = 0.38
        n = ns(d)
        f0 = env_pts(n, [(0, 400), (0.08, 540), (0.2, 470), (d, 310)])
        seq = [(0, "u"), (0.12, "u"), (0.3, "o")]
        amp = env_pts(n, [(0, 0), (0.02, 1), (0.22, 0.75), (d, 0)])
    elif v == 1:    # "ack" with glottal stop
        d = 0.24
        n = ns(d)
        f0 = env_pts(n, [(0, 620), (0.05, 700), (0.17, 520), (d, 480)])
        seq = [(0, "a"), (0.12, "ae")]
        amp = env_pts(n, [(0, 0), (0.01, 1), (0.16, 0.85), (0.175, 0.0), (d, 0)])
    else:           # pained "uh-HAH" with a pitch break
        d = 0.42
        n = ns(d)
        f0 = env_pts(n, [(0, 360), (0.1, 390), (0.12, 720), (0.25, 600), (d, 380)])
        seq = [(0, "uh"), (0.12, "a"), (0.35, "o")]
        amp = env_pts(n, [(0, 0), (0.02, 0.6), (0.11, 0.5), (0.13, 1.0), (0.3, 0.6), (d, 0)])
    src = glottal(f0, rng, jitter=0.025, shimmer=0.12, oq=0.55, breath=0.18, rough=0.15)
    y = formant(src, vowel_tracks(n, seq, scale=1.3)) * amp
    pre = breath(0.06, rng, "h", [(0, 0), (0.03, 1), (0.06, 0)], scale=1.3)
    y = sat(norm(y), 1.6)
    out = np.zeros(ns(0.05) + n)
    place(out, 0.25 * norm(pre), 0.0)
    place(out, y, 0.04)
    return early_reflections(out, rng, 3, 0.012, 0.15)


# --------------------------------------------------------------------- body loops
@S("heartbeat_loop", loop=True, dur=4.29, spatial=False,
   desc="Muffled double-beat heartbeat, 70 bpm, 5 beats (seamless loop, 4.29 s).")
def heartbeat_loop(rng, v):
    bpm = 70.0
    period = 60.0 / bpm
    L = ns(period * 5)
    out = np.zeros(L)
    for k in range(5):
        t = 0.25 + k * period + rng.normal(0, 0.004)
        a = rng.uniform(0.9, 1.05)
        lub = thump(0.5, rng, rng.uniform(68, 76), 40, 0.13, 0.7, 220, 0.02)
        dub = thump(0.4, rng, rng.uniform(88, 96), 52, 0.09, 0.6, 260, 0.015)
        flow = lp(white(ns(0.3), rng), 260, n=2) * env_ar(ns(0.3), 0.04, 0.2)
        place_circ(out, a * norm(lub), ns(t))
        place_circ(out, a * 0.62 * norm(dub), ns(t + rng.uniform(0.15, 0.17)))
        place_circ(out, a * 0.12 * norm(flow), ns(t + 0.02))
    floor = brown(L, rng, 20, 200) * 0.006
    y = out + floor
    # saturation adds audible harmonics on small headset drivers, keeps the "inside the chest" mud
    y = sat(norm(y), 2.2)
    y = circ(lambda z: lp(z, 900, n=2), y)
    return y


@S("breath_panic_loop", loop=True, dur=4.0, spatial=False,
   desc="Fast, shaky panicked breathing with small whimpers (seamless 4 s loop).")
def breath_panic_loop(rng, v):
    L = ns(4.0)
    out = np.zeros(L)
    cyc = rng.uniform(0.85, 1.15, 8)
    cyc = cyc / cyc.sum() * 4.0
    t = -0.12
    for k, c in enumerate(cyc):
        ti = c * rng.uniform(0.38, 0.45)
        te = c - ti
        di = ti * 0.95
        inh = breath(di, rng, [(0, "h"), (di, "i")], [(0, 0), (di * 0.3, 1), (di, 0.1)], scale=1.25, tilt=-1)
        trem = 1 + 0.45 * np.sin(2 * np.pi * rng.uniform(9, 13) * tt(len(inh)) + rng.uniform(0, 6))
        place_circ(out, 0.7 * norm(inh * trem), int(round(t * SR)))
        de = te * 0.95
        n = ns(de)
        exh = breath(de, rng, [(0, "a"), (de, "uh")], [(0, 0), (0.02, 1), (de, 0)], scale=1.2, tilt=-2.5)
        trem = 1 + 0.35 * np.sin(2 * np.pi * rng.uniform(8, 12) * tt(n) + rng.uniform(0, 6))
        ex = norm(exh * trem)
        if k % 3 == 1 or rng.random() < 0.3:  # whimper
            f0 = env_pts(n, [(0, rng.uniform(420, 500)), (de, rng.uniform(330, 380))])
            vo = formant(glottal(f0, rng, 0.03, 0.15, 0.5, 0.4, 0.1), vowel_tracks(n, "u", 1.3))
            ex = ex + 0.35 * norm(vo) * env_pts(n, [(0, 0), (0.03, 1), (de, 0)])
        place_circ(out, ex, int(round((t + ti) * SR)))
        t += c
    return circ(lambda z: hp(z, 120), out)


@S("death_sting", dur=3.0, spatial=False,
   desc="Player death: dark distorted impact followed by a falling detuned moan into darkness (3 s).")
def death_sting(rng, v):
    d = 3.2
    n = ns(d)
    sub = thump(2.5, rng, 85, 30, 1.3, 0.0, 300, 0.08)
    burst = sat(lp(white(ns(0.6), rng), 1800, n=2) * env_ar(ns(0.6), 0.002, 0.25) * 4, 3)
    clang = strike("metal", 72, 2.8, rng, hardness=0.5, decay=1.6, noise=0.1)
    hit = mix(0.7 * norm(sub), 0.35 * norm(burst), 0.35 * norm(clang))
    # falling detuned moan
    f0 = 210 * np.exp(np.log(42 / 210) * np.clip(tt(n) / 2.7, 0, 1) ** 0.8)
    tone = np.zeros(n)
    for det in (1.0, 1.006, 0.994, 1.059):
        tone += osc(f0 * det, "saw")
    cut = env_pts(n, [(0, 2600), (0.4, 1800), (d, 160)])
    tone = tvf(tone, "lp", cut, 1.2)
    tone = formant(tone, vowel_tracks(n, [(0, "o"), (d, "u")], 0.8)) * 0.7 + tone * 0.5
    tone = norm(tone) * env_pts(n, [(0, 0), (0.12, 0.4), (0.5, 1.0), (2.0, 0.7), (d, 0)])
    y = mix(0.8 * hit, 1.0 * tone)
    return space(y, rng, "hall", wet=0.35)


# --------------------------------------------------------------------- inventory / handling
@S("eat_munch", variants=2, dur=1.0, desc="Chewing: crunchy bites turning wet, heard from inside the head.")
def eat_munch(rng, v):
    out = np.zeros(ns(1.3))
    t = 0.02
    nb = 4 if v == 0 else 3
    for k in range(nb):
        crisp = 1.0 - k / nb
        bank = [click(rng, "plastic", rng.uniform(1800, 5000), 0.02, 0.95, 0.4) for _ in range(6)]
        cr = np.zeros(ns(0.14))
        for tg in event_times(0.09, 500 * crisp + 60, rng):
            place(cr, bank[rng.integers(6)] * rng.lognormal(0, 0.5), tg)
        wet = wet_squelch(0.16, rng, 500, 1200, 3.0, 2, 0.01)
        jaw = thump(0.12, rng, 150, 100, 0.04, 0.6, 500)
        bite = mix(crisp * norm(cr), (0.4 + 0.4 * (1 - crisp)) * norm(wet), 0.3 * norm(jaw))
        place(out, bite * rng.uniform(0.8, 1.0), t)
        t += rng.uniform(0.2, 0.28)
    y = peq(lp(out, 6500), 1000, 4, 1.0)
    return y


@S("backpack_store", dur=1.1, desc="Item pushed into canvas backpack, zip closes.")
def backpack_store(rng, v):
    out = np.zeros(ns(1.2))
    place(out, 0.7 * fabric(0.5, rng, [(0, 0), (0.05, 1), (0.3, 0.7), (0.5, 0)], 220), 0.0)
    place(out, 0.8 * zipper(0.45, rng, [(0, 0.2), (0.05, 1), (0.35, 0.8), (0.42, 0)], 240), 0.48)
    place(out, 0.4 * norm(thump(0.2, rng, 120, 70, 0.06, 1.0, 600)), 0.35)
    return out


@S("backpack_take", dur=1.0, desc="Backpack zip opens, rummage, item pulled out.")
def backpack_take(rng, v):
    out = np.zeros(ns(1.1))
    place(out, 0.8 * zipper(0.32, rng, [(0, 0), (0.03, 1), (0.28, 0.9), (0.32, 0)], 320), 0.0)
    place(out, 0.7 * fabric(0.55, rng, [(0, 0), (0.08, 1), (0.4, 0.6), (0.55, 0)], 260), 0.3)
    place(out, 0.35 * fabric(0.12, rng, [(0, 1), (0.12, 0)], 400, 800, 6000), 0.8)
    return out


@S("holster_snap", dur=0.3, desc="Tool clipped into holster: leather slap + metal press-stud snap.")
def holster_snap(rng, v):
    out = np.zeros(ns(0.35))
    slap = fabric(0.1, rng, [(0, 1), (0.1, 0)], 400, 300, 3000, body=1.0)
    place(out, 0.5 * slap + 0.4 * norm(thump(0.1, rng, 200, 120, 0.03, 1.0, 1500)), 0.0)
    for k, tt_ in enumerate((0.035, 0.041)):
        place(out, (0.9 - 0.3 * k) * click(rng, "metal", rng.uniform(2800, 3600), 0.06, 0.98, 0.2), tt_)
    return out


@S("grab", variants=2, dur=0.25, desc="Soft hand closing on an object.")
def grab(rng, v):
    n = ns(0.25)
    palm = lp(white(n, rng), rng.uniform(1200, 2200), n=2) * env_ar(n, rng.uniform(0.008, 0.015), 0.06)
    fur = fabric(0.2, rng, [(0, 0), (0.01, 1), (0.2, 0)], 250, 400, 5000)
    th = thump(0.15, rng, 180, 110, 0.03, 0.5, 900)
    return mix(norm(palm), 0.4 * fur, 0.3 * norm(th))


@S("whoosh", variants=3, dur=0.4, desc="Fast arm / tool swing through air.")
def whoosh_(rng, v):
    d = rng.uniform(0.33, 0.48)
    return whoosh(d, rng, rng.uniform(0.45, 0.55), rng.uniform(180, 300), rng.uniform(1500, 2700),
                  rng.uniform(0.9, 1.5), rng.uniform(0.06, 0.18))


@S("body_scrape", dur=1.0, desc="Monkey body sliding along rock: grit, fur and stone friction.")
def body_scrape(rng, v):
    d = 1.05
    sp = [(0, 0), (0.08, 1), (0.6, 0.8), (0.95, 0.15), (d, 0)]
    s = scrape(d, rng, sp, "stone", 420, 500, 0.8, 0.8, (700, 6000), 0.8, grit_rate=180)
    fur = fabric(d, rng, sp, 260, 400, 5000)
    n = ns(d)
    rumble = lp(white(n, rng), 300, n=2) * env_pts(n, sp)
    return mix(norm(s), 0.4 * fur, 0.35 * norm(rumble))
