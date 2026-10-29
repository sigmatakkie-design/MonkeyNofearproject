"""Mid-level sound recipes shared by the category generators (rustle, grit, crumble,
whoosh, creak, scrape, zipper, beeps, wet squelch, breaths, spaces ...)."""
from __future__ import annotations

import numpy as np
import scipy.signal as sps

from mnf_dsp import *  # noqa: F401,F403
import mnf_dsp as D

# ---------------------------------------------------------------------------
# spaces (reverb presets)
# ---------------------------------------------------------------------------
SPACES = {
    "room": dict(rt60=0.7, hf=0.5, early=8, early_span=0.03, bright=9000),
    "bunker": dict(rt60=1.1, hf=0.45, early=10, early_span=0.045, bright=8000),
    "hall": dict(rt60=2.0, hf=0.4, early=10, early_span=0.06, bright=7000),
    "tunnel": dict(rt60=2.4, hf=0.35, early=14, early_span=0.09, bright=6500, density_ms=8),
    "cave": dict(rt60=3.2, hf=0.3, early=12, early_span=0.12, bright=6000),
    "forest": dict(rt60=1.3, hf=0.3, early=3, early_span=0.08, bright=6000, density_ms=30),
    "valley": dict(rt60=4.5, hf=0.25, early=4, early_span=0.25, bright=4000, density_ms=60, predelay=0.04),
}


def space(x, rng, kind="room", wet=0.3, stereo=False, rt=None):
    kw = dict(SPACES[kind])
    rt60 = rt or kw.pop("rt60")
    kw.pop("rt60", None)
    return reverb(x, rt60, rng, wet=wet, stereo=stereo, **kw)


def far(x, rng, dist=40.0, kind="forest", wet=None, stereo=False):
    kw = dict(SPACES[kind])
    rt60 = kw.pop("rt60")
    return distance(x, rng, dist=dist, rt60=rt60, wet=wet, stereo=stereo, **kw)


# ---------------------------------------------------------------------------
# granular textures
# ---------------------------------------------------------------------------
def _crinkle_grain(rng, f_lo, f_hi, dmin=0.004, dmax=0.02, clicks=(1, 5)):
    n = ns(rng.uniform(dmin, dmax))
    x = np.zeros(n)
    for _ in range(rng.integers(clicks[0], clicks[1])):
        i = int(rng.integers(0, max(1, n // 2)))
        L = n - i
        x[i:] += rng.standard_normal(L) * np.exp(-np.arange(L) / (SR * rng.uniform(0.0005, 0.003))) * rng.uniform(0.3, 1)
    c = np.exp(rng.uniform(np.log(f_lo), np.log(f_hi)))
    x = bp(x, c, rng.uniform(0.7, 2.5))
    return x / (peak(x) + 1e-12)


def rustle(dur, rng, pts, density=400.0, f_lo=1200.0, f_hi=9000.0, body=0.35, bank_n=40):
    """Leaf / foliage rustle: crinkle grains + continuous brushing noise, following envelope pts."""
    n = ns(dur)
    e = np.clip(env_pts(n, pts), 0, None)
    bank = [_crinkle_grain(rng, f_lo, f_hi) for _ in range(bank_n)]
    out = np.zeros(n + ns(0.05))
    for t in event_times(dur, density * e ** 1.3, rng):
        g = bank[rng.integers(len(bank))]
        a = e[min(ns(t), n - 1)] * rng.lognormal(0, 0.5)
        place(out, g * a, t)
    out = out[:n]
    bed = shaped_noise(n, rng, -1.0, f_lo * 0.4, f_hi) * e ** 1.5 * (0.55 + 0.45 * rand_walk01(n, 35.0, rng))
    return norm(out) + body * norm(bed)


def rustle_arr(env, rng, density=300.0, f_lo=1200.0, f_hi=9000.0, body=0.35, circular=False, bank_n=40):
    """Rustle following an arbitrary envelope array (0..1). circular=True wraps grains (loops)."""
    n = len(env)
    e = np.clip(env, 0, None)
    bank = [_crinkle_grain(rng, f_lo, f_hi) for _ in range(bank_n)]
    out = np.zeros(n if circular else n + ns(0.05))
    for t in event_times(n / SR, density * e ** 1.3, rng):
        i = min(int(t * SR), n - 1)
        g = bank[rng.integers(bank_n)] * e[i] * rng.lognormal(0, 0.5)
        if circular:
            place_circ(out, g, i)
        else:
            place(out, g, idx=i)
    out = out[:n]
    bed = shaped_noise(n, rng, -1.0, f_lo * 0.4, f_hi) * e ** 1.5
    return norm(out) + body * norm(bed)


def fabric(dur, rng, pts, density=160.0, f_lo=350.0, f_hi=5000.0, body=0.6):
    """Cloth / canvas / fur rustle: softer, longer grains + brushed noise."""
    n = ns(dur)
    e = np.clip(env_pts(n, pts), 0, None)
    bank = [_crinkle_grain(rng, f_lo, f_hi, 0.01, 0.04, (2, 7)) for _ in range(30)]
    out = np.zeros(n + ns(0.06))
    for t in event_times(dur, density * e, rng):
        place(out, bank[rng.integers(len(bank))] * e[min(ns(t), n - 1)] * rng.lognormal(0, 0.4), t)
    bed = shaped_noise(n, rng, -2.0, f_lo, f_hi) * e ** 1.3 * (0.5 + 0.5 * rand_walk01(n, 18.0, rng))
    return norm(out[:n]) * 0.8 + body * norm(bed)


def pebble(rng, size=0.3, dur=None):
    """One small stone impact; size 0 (grit) .. 1 (fist-sized)."""
    f0 = lerp(5200.0, 380.0, size ** 0.7) * rng.uniform(0.85, 1.15)
    d = dur or lerp(0.03, 0.22, size)
    x = strike("stone", f0, d, rng, hardness=lerp(0.95, 0.7, size), decay=lerp(0.6, 1.6, size),
               noise=lerp(0.5, 0.3, size), n_modes=int(lerp(10, 26, size)))
    if size > 0.45:
        x = mix(x, 0.6 * size * norm(thump(d, rng, 220 * (1.4 - size), 90, 0.06 + 0.1 * size, 0.6, 900)))
    return norm(x)


def pebble_bank(rng, count, smin, smax):
    sizes = np.sort(rng.uniform(smin, smax, count))
    return [(s, pebble(rng, s)) for s in sizes]


def grit(dur, rng, rate, f_lo=2500, f_hi=11000, bank_n=24):
    """Fine grit / dust sprinkle (tiny stone ticks). rate: scalar/array/callable (events/s)."""
    bank = []
    for _ in range(bank_n):
        f0 = np.exp(rng.uniform(np.log(f_lo), np.log(f_hi * 0.6)))
        g = strike("stone", f0, 0.02, rng, hardness=0.95, decay=0.4, noise=0.6, n_modes=8, noise_f=(f_lo, 16000))
        bank.append(norm(g))
    out = np.zeros(ns(dur + 0.05))
    for t in event_times(dur, rate, rng):
        place(out, bank[rng.integers(bank_n)] * rng.lognormal(-0.3, 0.6), t)
    return out


def bounce_times(rng, t0, first_gap, e=0.55, n=4, jitter=0.15):
    ts, gs = [t0], [1.0]
    gap, g = first_gap, 1.0
    for _ in range(n - 1):
        t0 += gap * rng.uniform(1 - jitter, 1 + jitter)
        g *= e * rng.uniform(0.8, 1.15)
        gap *= e * rng.uniform(0.85, 1.1)
        ts.append(t0)
        gs.append(g)
    return ts, gs


def crumble(dur, rng, pts, rate=80.0, smin=0.05, smax=0.6, dust=0.25, bank_n=28):
    """Rock crumbling: granular pebble impacts (with small bounces) + dust hiss."""
    n = ns(dur)
    e = np.clip(env_pts(n, pts), 0, None)
    bank = pebble_bank(rng, bank_n, smin, smax)
    out = np.zeros(n + ns(0.4))
    for t in event_times(dur, rate * e, rng):
        s, g = bank[rng.integers(bank_n)]
        a = e[min(ns(t), n - 1)] * rng.lognormal(0, 0.45) * (0.6 + s)
        if rng.random() < 0.35:  # small bounce
            for tb, gb in zip(*bounce_times(rng, t, rng.uniform(0.03, 0.09), 0.45, 2)):
                place(out, g * a * gb, tb)
        else:
            place(out, g * a, t)
    hiss = shaped_noise(n, rng, -1.0, 1800, 12000) * e ** 2 * (0.4 + 0.6 * rand_walk01(n, 25, rng))
    return mix(norm(out), dust * norm(hiss))


# ---------------------------------------------------------------------------
# motion
# ---------------------------------------------------------------------------
def whoosh(dur, rng, peak_t=0.5, f_lo=250.0, f_hi=2200.0, q=1.3, tone=0.12, width=0.18, rumble=0.4):
    """Air swish: band-pass noise tracking a bell-shaped velocity curve."""
    n = ns(dur)
    t = tt(n) / dur
    sig = np.where(t < peak_t, width * 0.8, width * 1.25)
    v = np.exp(-0.5 * ((t - peak_t) / sig) ** 2)
    src = pink(n, rng)
    cf = f_lo + (f_hi - f_lo) * v
    y = tvf(src, "bp", cf, q) * v ** 2
    y2 = lp(white(n, rng), 500, n=2) * v ** 2.5
    y3 = tvf(white(n, rng), "bp", cf * 1.8, 9.0) * v ** 3
    return norm(y) + rumble * norm(y2) + tone * norm(y3)


# ---------------------------------------------------------------------------
# friction
# ---------------------------------------------------------------------------
def resonator_ir(mat, f0, rng, dur=0.5, decay=1.0, n_modes=None):
    fr, t6, am = material_modes(mat, f0, rng, n_modes, decay)
    return modal(ns(dur), fr, t6, am, rng)


def creak(dur, rng, rate_pts, mat="wood", f0=280.0, pressure_pts=None, irregular=0.25, decay=0.4,
          hiss=0.05, n_modes=None):
    """Stick-slip creak / groan: slip impulses at `rate` Hz exciting a modal body."""
    n = ns(dur)
    rate = env_pts(n, rate_pts)
    pres = env_pts(n, pressure_pts) if pressure_pts else np.ones(n)
    exc = stick_slip(n, rate, rng, irregular=irregular, amp_var=0.45, pressure=pres)
    exc = exc + 0.15 * lp(white(n, rng), 3000) * pres * 0.05
    ir = resonator_ir(mat, f0, rng, dur=0.6, decay=decay, n_modes=n_modes)
    y = sps.fftconvolve(exc, ir)[:n]
    if hiss:
        y = norm(y) + hiss * norm(bp(white(n, rng), 3000, 0.7) * pres)
    return norm(y)


def scrape(dur, rng, speed_pts, mat="metal", f0=600.0, base_rate=900.0, irregular=0.6, noise_amt=0.5,
           noise_f=(1500, 9000), decay=0.6, grit_rate=0.0):
    """Sliding friction: dense irregular slip train + speed-modulated noise through a body."""
    n = ns(dur)
    sp = np.clip(env_pts(n, speed_pts), 0, None)
    exc = stick_slip(n, base_rate * (0.3 + sp), rng, irregular=irregular, amp_var=0.8, pressure=sp)
    nz = shaped_noise(n, rng, 0, noise_f[0], noise_f[1]) * sp * (0.5 + 0.5 * rand_walk01(n, 60, rng))
    ir = resonator_ir(mat, f0, rng, 0.8, decay)
    body = sps.fftconvolve(exc + 0.02 * nz, ir)[:n]
    y = norm(body) + noise_amt * norm(nz)
    if grit_rate:
        y = mix(y, 0.5 * norm(grit(dur, rng, grit_rate * sp)))[:n]
    return y


def zipper(dur, rng, pts, rate=220.0, f_c=3200.0):
    """Zip: one tiny click per tooth; rate (teeth/s) follows envelope pts (0..1)."""
    n = ns(dur)
    e = np.clip(env_pts(n, pts), 0, None)
    exc = stick_slip(n, rate * (0.25 + e), rng, irregular=0.15, amp_var=0.3, pressure=e)
    ir = resonator_ir("plastic", f_c * 0.6, rng, 0.03, 0.35)
    y = sps.fftconvolve(exc, ir)[:n]
    buzz = bp(white(n, rng), f_c, 1.2) * e * 0.3
    return norm(norm(y) + buzz)


# ---------------------------------------------------------------------------
# mechanical / electronic
# ---------------------------------------------------------------------------
def click(rng, mat="plastic", f0=2500.0, dur=0.06, hardness=0.9, decay=1.0, body_f=None, body_amt=0.4):
    x = strike(mat, f0, dur, rng, hardness=hardness, decay=decay, noise=0.35)
    if body_f:
        x = mix(norm(x), body_amt * norm(thump(dur, rng, body_f * 1.6, body_f, dur * 0.5, 0.3, 1200, 0.01)))
    return norm(x)


def speaker(x, lo=320.0, hi=4800.0, drive=1.6, cone=1800.0):
    y = bw(x, "bandpass", (lo, hi), 2)
    y = peq(y, cone, 5.0, 1.5)
    return sat(norm(y), drive)


def beep(freq, dur, rng, shape="sine", att=0.004, rel=0.03, spk=True, harm=0.2, droop=0.0):
    n = ns(dur)
    f = freq * (1 - droop * tt(n) / dur) if droop else np.full(n, float(freq))
    x = osc(f, shape) + harm * osc(f * 2, "sine") * 0.5
    x = x * env_pts(n, [(0, 0), (att, 1), (max(dur - rel, att), 1), (dur, 0)])
    if spk:
        x = speaker(x * 0.8, drive=1.3)
        x = x + 0.004 * bp(white(n, rng), 3000, 0.5)
    return x


def mains_hum(n, rng, f=50.0, amps=None, buzz=0.3, buzz_f=(1800, 7000), flutter=0.15):
    """Mains-locked hum: harmonics of f (integer cycles per loop when n*f/SR integer) + ballast buzz."""
    amps = amps if amps is not None else [0.3, 1.0, 0.45, 0.5, 0.2, 0.25, 0.1, 0.12]
    t = tt(n)
    x = np.zeros(n)
    for k, a in enumerate(amps, 1):
        x += a * np.sin(2 * np.pi * f * k * t + rng.uniform(0, 6.28))
    # buzz: clipped 2f waveform -> rich odd/even harmonics
    raw = np.sin(2 * np.pi * 2 * f * t + rng.uniform(0, 6.28))
    b = np.sign(raw) * np.abs(raw) ** 0.15
    b = bw(np.concatenate([b, b, b]), "bandpass", buzz_f, 2)[n:2 * n]
    fl = 1 + flutter * smooth_rand(n, 6.0, rng)
    return norm(x) * 0.7 + buzz * norm(b) * fl


def motor(n, rng, f_rot=25.0, harmonics=24, slot=(12, 18), whine=0.3, rough=0.2):
    """Electric motor tone: rotation harmonics + slot/gear whine (periodic if n*f_rot/SR integer)."""
    t = tt(n)
    x = np.zeros(n)
    for k in range(1, harmonics + 1):
        a = (1.0 / k ** 0.8) * rng.uniform(0.5, 1.0)
        if k in slot:
            a *= 4 * whine
        if f_rot * k < NYQ * 0.9:
            x += a * np.sin(2 * np.pi * f_rot * k * t + rng.uniform(0, 6.28))
    return norm(x)


# ---------------------------------------------------------------------------
# wet / organic
# ---------------------------------------------------------------------------
def wet_squelch(dur, rng, f_from=350.0, f_to=1500.0, q=5.0, bubbles=6, att=0.01, t60=None, bub_f=(300, 1600)):
    n = ns(dur)
    t60 = t60 or dur * 0.7
    e = env_ar(n, att, t60)
    src = pink(n, rng)
    cf = np.exp(np.linspace(np.log(f_from), np.log(f_to), n))
    y = tvf(src, "bp", cf, q) + 0.6 * tvf(src, "bp", cf * 2.3, q * 0.8)
    fl = 0.4 + 0.6 * rand_walk01(n, 45, rng)
    y = norm(y * e * fl)
    out = y
    for _ in range(bubbles):
        bt = rng.uniform(0, dur * 0.7)
        b = bubble(rng.uniform(*bub_f), 0.05, rng, rise=rng.uniform(0.8, 2.5))
        out = place(out, b * rng.uniform(0.2, 0.6), bt)
    return out


def breath(dur, rng, seq, pts, scale=1.0, tilt=-2.0, bw_scale=1.6):
    n = ns(dur)
    return breath_noise(n, seq, rng, scale, bw_scale, tilt) * np.clip(env_pts(n, pts), 0, None)


def ghost_f0(n, base, pts=None, vib=0.0, vib_rate=5.0, drift=0.0, rng=None, drift_rate=1.0):
    """Pitch contour helper: base * env(pts) * (1 + vibrato + drift)."""
    f = base * (env_pts(n, pts) if pts else np.ones(n))
    if vib:
        f = f * (1 + vib * np.sin(2 * np.pi * vib_rate * tt(n)))
    if drift and rng is not None:
        f = f * (1 + drift * smooth_rand(n, drift_rate, rng))
    return f
