"""Stingers & tension (Music/): stereo, non-positional."""
from __future__ import annotations

import numpy as np

from mnf_dsp import *  # noqa: F401,F403
from mnf_sfx import *  # noqa: F401,F403
from mnf_registry import category

S = category("Music")


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def saw_voice(n, f, rng, detune=0.004, voices=3):
    y = np.zeros(n)
    for k in range(voices):
        dt = 1 + detune * (k - (voices - 1) / 2)
        y += osc(np.full(n, f * dt), "saw", phase0=rng.uniform(0, 1))
    return y / voices


def soft_tone(n, f, rng, harmonics=(1.0, 0.35, 0.15, 0.06), detune=0.002):
    y = np.zeros(n)
    for d in (1 - detune, 1 + detune):
        y += harmonic_tone(np.full(n, f * d), list(harmonics), rng=rng)
    return y


def spread(voices, rng, width=0.8):
    """voices: list of mono arrays -> stereo with alternating pans."""
    n = max(len(x) for x in voices)
    out = np.zeros((n, 2))
    for i, x in enumerate(voices):
        p = width * (-1 + 2 * i / max(1, len(voices) - 1)) if len(voices) > 1 else 0.0
        out[: len(x)] += pan(x, p)
    return out


@S("sting_dread", stereo=True, dur=5.0, desc="Low dread swell: dissonant low cluster crescendo with opening filter (stereo 5 s).")
def sting_dread(rng, v):
    d = 5.0
    n = ns(d)
    env = env_pts(n, [(0, 0), (1.0, 0.15), (3.5, 0.75), (4.5, 1.0), (4.65, 0.25), (d, 0)])
    cut = env_pts(n, [(0, 120), (3.0, 500), (4.5, 1600), (d, 300)])
    voices = []
    for m in (33, 34, 40, 45):  # A1, Bb1, E2, A2
        x = saw_voice(n, midi(m), rng, 0.006)
        voices.append(tvf(x, "lp", cut, 1.4) * env)
    swell = tvf(pink(n, rng), "lp", cut * 2, 0.7) * env ** 2
    glass = (np.sin(2 * np.pi * midi(81) * tt(n)) + np.sin(2 * np.pi * midi(82) * tt(n) + 1)) * env ** 3
    st = spread(voices, rng, 0.7) + 0.4 * np.stack([norm(swell)] * 2, 1) * 0.3 + spread([0.015 * glass, 0.015 * glass[::-1] * 0], rng, 0.5)
    hit = thump(1.5, rng, 60, 30, 0.9, 0.4, 200)
    st = mix(st, 0.5 * pan(norm(hit), 0.0) * 1.0)
    return reverb(st, 2.2, rng, wet=0.5, stereo=True, hf=0.4)


@S("sting_reveal", stereo=True, dur=2.5, desc="Dissonant reveal hit: impact, tritone brass cluster, screeching high strings (stereo 2.5 s).")
def sting_reveal(rng, v):
    d = 2.6
    n = ns(d)
    boom = mix(norm(thump(2.0, rng, 70, 30, 1.0, 0.6, 300)), 0.5 * norm(strike("metal", 90, 2.0, rng, 0.8, 1.2)),
               0.6 * norm(lp(white(ns(0.5), rng), 4000) * env_ar(ns(0.5), 0.001, 0.25)))
    cut = env_pts(n, [(0, 4500), (0.3, 1500), (d, 400)])
    brass = []
    for m in (36, 42, 43, 49):  # C2 F#2 G2 C#3
        x = saw_voice(n, midi(m), rng, 0.005)
        brass.append(tvf(x, "lp", cut, 1.2) * env_ar(n, 0.01, 2.2))
    strings = []
    for m in (84, 85, 90):  # C6 C#6 F#6
        f = midi(m) * (1 + 0.006 * np.sin(2 * np.pi * 6.3 * tt(n) + rng.uniform(0, 6)))
        x = osc(f, "saw")
        x = bw(x, "bandpass", (900, 7000), 2) * env_pts(n, [(0, 0), (0.05, 1), (1.2, 0.5), (d, 0)])
        strings.append(x)
    st = spread(brass, rng, 0.6) + 0.35 * spread(strings, rng, 0.9) + 0.9 * np.stack([boom[:n] if len(boom) >= n else pad_to(boom, n)] * 2, 1)
    st = sat(st / peak(st), 1.5)
    return reverb(st, 2.8, rng, wet=0.55, stereo=True, hf=0.45)


@S("sting_safe", stereo=True, dur=4.0, desc="Soft warm chord on returning to the bunker (stereo 4 s).")
def sting_safe(rng, v):
    d = 4.0
    n = ns(d)
    env = env_pts(n, [(0, 0), (0.7, 1.0), (2.6, 0.8), (d, 0)])
    voices = []
    for k, m in enumerate((50, 57, 61, 64, 66)):  # D3 A3 C#4 E4 F#4 (Dmaj9)
        x = soft_tone(n, midi(m), rng) * env_pts(n, [(0, 0), (0.15 * k + 0.6, 1.0), (2.6, 0.8), (d, 0)])
        voices.append(lp(x, 2500))
    st = spread(voices, rng, 0.6)
    st = st * env[:, None] ** 0.3
    return reverb(st, 2.2, rng, wet=0.45, stereo=True, hf=0.5)


@S("tension_drone_loop", stereo=True, loop=True, dur=12.0, spatial=False, norm=("rms", -20.0, -3.0),
   desc="Low pulsing chase drone (stereo 12 s seamless loop, 120 bpm pulse).")
def tension_drone_loop(rng, v):
    L = ns(12.0)
    t = tt(L)
    q = lambda f: round(f * 12.0) / 12.0  # integer cycles per loop -> seamless
    ph = (t * 2.0 + 0.5) % 1.0  # 2 Hz pulse, 24 per loop; wrap falls between pulses
    shape = (1 - np.exp(-ph / 0.025)) * np.exp(-ph / 0.18)
    pulse = 0.55 + 0.45 * shape / shape.max()
    cut = 250 + 350 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 12.0)) + 300 * shape / shape.max()
    chans = []
    for c in range(2):
        x = np.zeros(L)
        for f, a in ((q(55.0), 1.0), (q(55.25 if c == 0 else 54.75), 0.8), (q(58.27), 0.45), (q(82.41), 0.3)):
            x += a * osc(np.full(L, f), "saw", phase0=rng.uniform(0, 1))
        x = circ(lambda z: tvf(z, "lp", np.tile(cut, 3), 1.6), x)
        hi = (np.sin(2 * np.pi * q(880.0) * t + c) + 0.8 * np.sin(2 * np.pi * q(932.33) * t)) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 6.0 + c * 1.5))
        air = shaped_noise(L, rng, -3, 200, 3000) * pulse
        chans.append(norm(x) * pulse + 0.03 * hi + 0.05 * norm(air))
    y = np.stack(chans, 1)
    sub = np.zeros(L)
    th = thump(0.4, rng, 70, 40, 0.25, 0.0, 200)
    for k in range(24):
        place_circ(sub, norm(th), ns(k * 0.5 + 0.25) + 10)
    y = y + 0.4 * sub[:, None]
    ir = reverb_ir(2.0, rng, stereo=True, hf=0.4)
    wet = circ_conv(y, ir)
    return y + 0.25 * wet * (rms(y) / (rms(wet) + 1e-9))


@S("sting_purchase", stereo=True, dur=1.0, desc="Bright short purchase jingle: marimba / bell arpeggio (stereo 1 s).")
def sting_purchase(rng, v):
    out = np.zeros((ns(1.3), 2))
    for k, m in enumerate((72, 76, 79, 84)):
        x = mix(norm(strike("marimba", midi(m), 0.9, rng, 0.85, 0.7, 0.05)), 0.25 * norm(strike("glass", midi(m) * 2, 0.6, rng, 0.95, 0.3, 0.0)))
        st = pan(x, -0.6 + 0.4 * k)
        out[ns(0.06 * k): ns(0.06 * k) + len(st)] += st[: len(out) - ns(0.06 * k)]
    return reverb(out, 1.0, rng, wet=0.3, stereo=True)


@S("sting_lore", stereo=True, dur=3.0, desc="Mysterious lore sting: inharmonic glass bells over a soft unresolved pad (stereo 3 s).")
def sting_lore(rng, v):
    d = 3.2
    n = ns(d)
    out = np.zeros((n, 2))
    for k, (m, t) in enumerate(((74, 0.0), (77, 0.45), (80, 0.9), (73, 1.5))):  # D5 F5 G#5 C#5
        b = strike("bell", midi(m), d - t, rng, 0.9, 0.45, 0.02)
        place(out[:, 0], norm(b) * (0.8 if k % 2 else 1.0) * 0.6, t)
        place(out[:, 1], norm(b) * (1.0 if k % 2 else 0.8) * 0.6, t)
    pad = [soft_tone(n, midi(m), rng, (1.0, 0.2, 0.05)) * env_pts(n, [(0, 0), (1.2, 1), (2.4, 0.8), (d, 0)]) for m in (50, 56, 61)]
    st = out + 0.3 * spread([norm(p) for p in pad], rng, 0.7)
    sw = tvf(pink(n, rng), "bp", env_pts(n, [(0, 2000), (d, 6000)]), 2.0) * env_pts(n, [(0, 0), (1.5, 1), (d, 0)])
    st = st + 0.04 * widen(norm(sw), rng, 0.8)
    return reverb(st, 2.2, rng, wet=0.5, stereo=True, hf=0.5)
