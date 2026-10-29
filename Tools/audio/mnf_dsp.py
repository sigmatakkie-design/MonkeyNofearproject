"""MONKEY NO FEAR - procedural audio DSP toolkit.

Small, dependency-light (numpy + scipy) building blocks used by the per-category
sound generators in this folder:

  * noise colours (FFT-shaped; FFT noise is circular, so it is loop-safe by construction)
  * RBJ biquads (static + block-wise time-varying), Butterworth helpers
  * envelopes, smooth random LFOs
  * oscillators (polyBLEP saw / square, sine), glottal pulse source
  * modal synthesis with material presets (metal, wood, stone, glass, plastic, bell ...)
  * contact excitation / strike, thumps, Minnaert bubbles
  * granular scattering, stick-slip friction excitation, Karplus-Strong / waveguide combs
  * formant filtering with a vowel table
  * synthetic reverb impulse responses, circular (loop-safe) convolution
  * saturation, bit-crush, distance model
  * loop helpers (circular processing, circular event placement, crossfade loopify)

All randomness goes through a numpy Generator passed in by the caller, so every
sound is deterministic for a given seed.
"""
from __future__ import annotations

import numpy as np
import scipy.signal as sps

SR = 44100
NYQ = SR / 2.0


# ---------------------------------------------------------------------------
# basics
# ---------------------------------------------------------------------------
def ns(seconds: float) -> int:
    """Seconds -> sample count."""
    return max(1, int(round(seconds * SR)))


def tt(n: int) -> np.ndarray:
    """Time axis (seconds) for n samples."""
    return np.arange(n) / SR


def db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-12))


def undb(d):
    return 10.0 ** (np.asarray(d) / 20.0)


def lerp(a, b, k):
    return a + (b - a) * k


def peak(x):
    return float(np.max(np.abs(x))) if len(x) else 0.0


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)) + 1e-20))


def norm(x, peak_val=1.0):
    p = peak(x)
    return x * (peak_val / p) if p > 0 else x


def pad_to(x, n):
    if len(x) >= n:
        return x[:n]
    shape = (n - len(x),) + x.shape[1:]
    return np.concatenate([x, np.zeros(shape)], axis=0)


def mix(*parts):
    """Sum arrays of different lengths (zero padded)."""
    parts = [p for p in parts if p is not None]
    n = max(len(p) for p in parts)
    out = np.zeros((n,) + parts[0].shape[1:])
    for p in parts:
        out[: len(p)] += p
    return out


def place(dst, src, t_sec=None, gain=1.0, idx=None):
    """Add src into dst at time t (in place, clipped to dst length). Returns dst."""
    i = ns(t_sec) if idx is None else int(idx)
    if i >= len(dst) or i + len(src) <= 0:
        return dst
    s0 = max(0, -i)
    e = min(len(dst), i + len(src))
    dst[max(i, 0):e] += gain * src[s0: s0 + (e - max(i, 0))]
    return dst


def place_circ(dst, src, idx, gain=1.0):
    """Add src into dst at sample idx, wrapping around the end (for seamless loops)."""
    n = len(dst)
    idx = int(idx) % n
    pos = 0
    while pos < len(src):
        start = (idx + pos) % n
        take = min(n - start, len(src) - pos)
        dst[start:start + take] += gain * src[pos:pos + take]
        pos += take
    return dst


def fade(x, fin=0.002, fout=0.01, shape="cos"):
    x = x.copy()
    n = len(x)
    a, b = min(ns(fin), n // 2) if fin > 0 else 0, min(ns(fout), n // 2) if fout > 0 else 0
    def ramp(m):
        r = np.linspace(0, 1, m)
        return 0.5 - 0.5 * np.cos(np.pi * r) if shape == "cos" else r
    if a > 0:
        x[:a] *= ramp(a).reshape((-1,) + (1,) * (x.ndim - 1))
    if b > 0:
        x[n - b:] *= ramp(b)[::-1].reshape((-1,) + (1,) * (x.ndim - 1))
    return x


def resample_ratio(x, ratio):
    """Varispeed: ratio > 1 plays faster (higher, shorter)."""
    n = len(x)
    m = max(2, int(n / ratio))
    pos = np.arange(m) * ratio
    return np.interp(pos, np.arange(n), x)


def varispeed(x, speed, max_ratio=8.0):
    """Time-varying playback speed. speed: callable(t_out_seconds) or array per output sample."""
    n = len(x)
    if callable(speed):
        m = int(n * max_ratio) + 1
        sp = np.maximum(speed(tt(m)), 1e-3)
    else:
        sp = np.asarray(speed, float)
    pos = np.concatenate([[0.0], np.cumsum(sp)[:-1]])
    pos = pos[pos < n - 1]
    return np.interp(pos, np.arange(n), x)


# ---------------------------------------------------------------------------
# noise
# ---------------------------------------------------------------------------
def shaped_noise(n, rng, slope=0.0, lo=None, hi=None, shape=None):
    """Gaussian noise shaped in the frequency domain.

    slope: dB/octave (0 white, -3 pink, -6 brown, +3 blue). lo/hi: 2nd-order-ish
    high/low-pass corners (Hz). shape: optional callable gain(f). The result is
    circular (period n) so it can be used directly as a seamless loop.
    """
    n = int(n)
    m = n // 2 + 1
    spec = rng.standard_normal(m) + 1j * rng.standard_normal(m)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    f1 = f.copy()
    f1[0] = f1[1] if m > 1 else 1.0
    g = (f1 / 1000.0) ** (slope / 6.0206)
    if lo:
        g = g / np.sqrt(1.0 + (lo / f1) ** 4)
    if hi:
        g = g / np.sqrt(1.0 + (f1 / hi) ** 4)
    if shape is not None:
        g = g * shape(f1)
    g[0] = 0.0
    x = np.fft.irfft(spec * g, n)
    s = np.std(x)
    return x / s if s > 0 else x


def white(n, rng):
    return rng.standard_normal(int(n))


def pink(n, rng, lo=None, hi=None):
    return shaped_noise(n, rng, -3.0, lo, hi)


def brown(n, rng, lo=None, hi=None):
    return shaped_noise(n, rng, -6.0, lo, hi)


def band_noise(n, rng, f_lo, f_hi, slope=0.0):
    return shaped_noise(n, rng, slope, f_lo, f_hi)


def smooth_rand(n, rate, rng):
    """Smooth random control signal (std 1) with energy below ~rate Hz. Circular."""
    n = int(n)
    m = n // 2 + 1
    f = np.fft.rfftfreq(n, 1.0 / SR)
    spec = rng.standard_normal(m) + 1j * rng.standard_normal(m)
    g = np.exp(-((f / max(rate, 1e-3)) ** 2))
    g[0] = 0.0
    if np.count_nonzero(g > 1e-3) < 2:  # very slow rate vs short signal: keep 2 lowest bins
        g[1:3] = 1.0
    x = np.fft.irfft(spec * g, n)
    s = np.std(x)
    return x / s if s > 0 else x


def rand_walk01(n, rate, rng):
    """Smooth random in [0,1]."""
    x = smooth_rand(n, rate, rng)
    return 0.5 + 0.5 * np.tanh(x * 0.8)


# ---------------------------------------------------------------------------
# filters
# ---------------------------------------------------------------------------
def biquad(kind, f, q=0.707, gain_db=0.0):
    f = float(np.clip(f, 5.0, SR * 0.49))
    q = max(float(q), 1e-3)
    w = 2 * np.pi * f / SR
    cw, sw = np.cos(w), np.sin(w)
    alpha = sw / (2 * q)
    A = 10 ** (gain_db / 40.0)
    if kind == "lp":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "hp":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "bp":  # 0 dB peak gain
        b = [alpha, 0.0, -alpha]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "notch":
        b = [1, -2 * cw, 1]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "peak":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind in ("ls", "hs"):
        sq = 2 * np.sqrt(A) * alpha
        if kind == "ls":
            b = [A * ((A + 1) - (A - 1) * cw + sq), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sq)]
            a = [(A + 1) + (A - 1) * cw + sq, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sq]
        else:
            b = [A * ((A + 1) + (A - 1) * cw + sq), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sq)]
            a = [(A + 1) - (A - 1) * cw + sq, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sq]
    else:
        raise ValueError(kind)
    b = np.array(b, float)
    a = np.array(a, float)
    return b / a[0], a / a[0]


def filt(x, kind, f, q=0.707, gain_db=0.0, n=1):
    b, a = biquad(kind, f, q, gain_db)
    for _ in range(n):
        x = sps.lfilter(b, a, x, axis=0)
    return x


def lp(x, f, q=0.707, n=1):
    return filt(x, "lp", f, q, n=n)


def hp(x, f, q=0.707, n=1):
    return filt(x, "hp", f, q, n=n)


def bp(x, f, q=1.0, n=1):
    return filt(x, "bp", f, q, n=n)


def peq(x, f, gain_db, q=1.0):
    return filt(x, "peak", f, q, gain_db)


def bw(x, kind, f, order=2):
    """Butterworth via SOS. kind: 'lowpass','highpass','bandpass' (f=(lo,hi))."""
    if isinstance(f, (tuple, list)):
        f = [min(max(v, 5.0), SR * 0.49) for v in f]
    else:
        f = min(max(f, 5.0), SR * 0.49)
    sos = sps.butter(order, f, btype=kind, fs=SR, output="sos")
    return sps.sosfilt(sos, x, axis=0)


def _as_env(v, n):
    if callable(v):
        return v(tt(n))
    v = np.asarray(v, float)
    if v.ndim == 0:
        return np.full(n, float(v))
    if len(v) != n:
        return np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(v)), v)
    return v


def tvf(x, kind, f, q=0.707, gain_db=0.0, block=64):
    """Time-varying biquad (block-wise coefficient update, state carried). Mono."""
    n = len(x)
    f = _as_env(f, n)
    q = _as_env(q, n)
    g = _as_env(gain_db, n)
    y = np.zeros(n)
    zi = np.zeros(2)
    for s in range(0, n, block):
        e = min(n, s + block)
        m = (s + e) // 2
        b, a = biquad(kind, f[m], q[m], g[m])
        y[s:e], zi = sps.lfilter(b, a, x[s:e], zi=zi)
    return y


def comb(x, delay_s, fb=0.7, damp=0.3):
    """Feedback comb with one-pole damping in the loop (waveguide-ish resonator)."""
    N = max(2, int(round(delay_s * SR)))
    # y[n] = x[n] + fb*((1-damp)*y[n-N] + damp*y[n-N-1])
    a = np.zeros(N + 2)
    a[0] = 1.0
    a[N] = -fb * (1 - damp)
    a[N + 1] = -fb * damp
    return sps.lfilter([1.0], a, x, axis=0)


def waveguide(x, f, fb=0.99, damp=0.5):
    """Karplus-Strong style string/tube resonator driven by excitation x."""
    return comb(x, 1.0 / f, fb, damp)


def allpass(x, delay_s, g=0.6):
    N = max(1, int(round(delay_s * SR)))
    b = np.zeros(N + 1)
    a = np.zeros(N + 1)
    b[0], b[N] = -g, 1.0
    a[0], a[N] = 1.0, -g
    return sps.lfilter(b, a, x, axis=0)


# ---------------------------------------------------------------------------
# envelopes
# ---------------------------------------------------------------------------
def env_pts(n, pts):
    """Piecewise-linear breakpoint envelope. pts: [(t_sec, value), ...]."""
    ts = np.array([p[0] for p in pts], float)
    vs = np.array([p[1] for p in pts], float)
    return np.interp(tt(n), ts, vs)


def env_exp(n, t60, delay=0.0):
    t = np.maximum(tt(n) - delay, 0.0)
    return np.power(10.0, -3.0 * t / max(t60, 1e-4))


def env_ar(n, attack, t60, curve=2.0):
    """Attack (raised-cosine) then exponential decay (t60 seconds to -60 dB)."""
    t = tt(n)
    a = max(attack, 1e-5)
    rise = np.where(t < a, (0.5 - 0.5 * np.cos(np.pi * np.clip(t / a, 0, 1))) ** (curve / 2), 1.0)
    dec = np.power(10.0, -3.0 * np.maximum(t - a, 0) / max(t60, 1e-4))
    return rise * dec


def env_adsr(n, a, d, s, r, hold=None):
    """Classic ADSR; release starts at n - r unless hold given."""
    tot = n / SR
    hold = tot - r if hold is None else hold
    return env_pts(n, [(0, 0), (a, 1), (a + d, s), (max(hold, a + d), s), (max(hold, a + d) + r, 0), (tot + 1, 0)])


def env_hann(n):
    return np.hanning(n) if n > 2 else np.ones(n)


# ---------------------------------------------------------------------------
# oscillators
# ---------------------------------------------------------------------------
def phase_cycles(freq):
    """Cumulative phase in cycles for a frequency array (Hz)."""
    return np.cumsum(freq) / SR


def _polyblep(t, dt):
    dt = np.maximum(dt, 1e-9)
    y = np.zeros_like(t)
    m1 = t < dt
    x = t[m1] / dt[m1]
    y[m1] = x + x - x * x - 1.0
    m2 = t > 1.0 - dt
    x = (t[m2] - 1.0) / dt[m2]
    y[m2] = x * x + x + x + 1.0
    return y


def osc(freq, shape="sine", n=None, phase0=0.0):
    """Band-limited oscillator. freq: scalar (needs n) or array of Hz."""
    if np.isscalar(freq):
        freq = np.full(int(n), float(freq))
    freq = np.asarray(freq, float)
    ph = phase_cycles(freq) + phase0
    t = ph % 1.0
    dt = np.abs(freq) / SR
    if shape == "sine":
        return np.sin(2 * np.pi * ph)
    if shape == "saw":
        return 2 * t - 1 - _polyblep(t, dt)
    if shape == "square":
        s1 = 2 * t - 1 - _polyblep(t, dt)
        t2 = (t + 0.5) % 1.0
        s2 = 2 * t2 - 1 - _polyblep(t2, dt)
        return 0.5 * (s1 - s2)
    if shape == "tri":
        out = np.zeros_like(ph)
        for k in range(1, 16, 2):
            mask = (k * np.abs(freq)) < NYQ * 0.95
            out += mask * ((-1) ** ((k - 1) // 2)) * np.sin(2 * np.pi * k * ph) / (k * k)
        return out * 8 / np.pi ** 2
    raise ValueError(shape)


def harmonic_tone(freq, amps, n=None, rng=None, detune=0.0):
    """Additive harmonic tone: amps[k] for harmonic k+1 (alias-safe)."""
    if np.isscalar(freq):
        freq = np.full(int(n), float(freq))
    ph = phase_cycles(freq)
    out = np.zeros_like(ph)
    for k, a in enumerate(amps, start=1):
        if a == 0:
            continue
        mask = (k * freq) < NYQ * 0.95
        off = rng.uniform(0, 1) if rng is not None else 0.0
        out += a * mask * np.sin(2 * np.pi * (k * ph * (1 + detune * (k - 1)) + off))
    return out


def glottal(f0, rng, jitter=0.01, shimmer=0.08, oq=0.6, breath=0.05, rough=0.0,
            subharm=0.0, creak=0.0, oversample=2):
    """Glottal-flow-derivative pulse train (Rosenberg-style) + aspiration.

    f0: array of fundamental frequency per sample (Hz).
    jitter: relative pitch wobble; shimmer: per-cycle amplitude randomness;
    oq: open quotient; breath: aspiration noise; rough: extra per-cycle chaos;
    subharm: alternate-cycle amplitude (period doubling -> growl);
    creak: probability of skipped/irregular cycles (vocal fry).
    """
    f0 = np.asarray(f0, float)
    n = len(f0)
    os_ = oversample
    m = n * os_
    f = np.interp(np.linspace(0, n - 1, m), np.arange(n), f0)
    sr2 = SR * os_
    jit = smooth_rand(m, 30.0, rng) * jitter + rng.standard_normal(m) * 0  # smooth jitter
    f = f * (1 + jit)
    if rough > 0:
        f = f * (1 + rough * 0.5 * smooth_rand(m, 120.0, rng))
    ph = np.cumsum(f) / sr2
    cyc = np.floor(ph).astype(np.int64)
    frac = ph - cyc
    ncyc = int(cyc[-1]) + 2
    amp_c = 1.0 + shimmer * rng.standard_normal(ncyc) + rough * rng.standard_normal(ncyc) * 0.6
    if subharm > 0:
        amp_c = amp_c * (1 - subharm * (np.arange(ncyc) % 2))
    if creak > 0:
        amp_c = amp_c * np.where(rng.random(ncyc) < creak, rng.uniform(0.0, 0.3, ncyc), 1.0)
    oq_c = np.clip(oq * (1 + 0.1 * rng.standard_normal(ncyc) * (jitter * 10 + rough)), 0.2, 0.95)
    oqs = oq_c[cyc]
    tp = oqs * 0.65
    tn = oqs * 0.35
    g = np.where(frac < tp, 0.5 * (1 - np.cos(np.pi * frac / tp)),
                 np.where(frac < tp + tn, np.cos(0.5 * np.pi * (frac - tp) / tn), 0.0))
    g = g * np.abs(amp_c[cyc])
    d = np.diff(g, prepend=g[0])
    d = d / (np.std(d) + 1e-12)
    if breath > 0:
        nz = shaped_noise(m, rng, 0.0, 400.0, None) if m > 8 else np.zeros(m)
        # aspiration is modulated by glottal opening
        d = d + breath * 3.0 * nz * (0.25 + g / (np.max(g) + 1e-9))
    if os_ > 1:
        d = sps.resample_poly(d, 1, os_)[:n]
        d = pad_to(d, n)
    return d


# ---------------------------------------------------------------------------
# vowels / formants
# ---------------------------------------------------------------------------
# (F1..F4 Hz, bandwidths Hz, gains dB) for an adult-ish vocal tract
VOWELS = {
    "a": ([730, 1090, 2440, 3400], [90, 110, 140, 180], [0, -4, -14, -20]),
    "ah": ([680, 1200, 2600, 3500], [100, 120, 150, 200], [0, -5, -14, -22]),
    "e": ([530, 1840, 2480, 3500], [70, 100, 150, 200], [0, -8, -12, -20]),
    "i": ([290, 2250, 3000, 3700], [50, 90, 150, 200], [0, -12, -10, -18]),
    "o": ([570, 840, 2410, 3400], [80, 90, 150, 200], [0, -3, -20, -28]),
    "u": ([310, 870, 2240, 3300], [50, 80, 150, 200], [0, -8, -26, -32]),
    "ae": ([660, 1720, 2410, 3400], [90, 110, 150, 200], [0, -4, -12, -20]),
    "uh": ([520, 1190, 2390, 3400], [80, 100, 150, 200], [0, -6, -16, -24]),
    "er": ([490, 1350, 1690, 3300], [80, 100, 120, 200], [0, -6, -8, -20]),
    "m": ([260, 1100, 2300, 3300], [60, 200, 250, 300], [0, -22, -30, -36]),
    "n": ([280, 1500, 2600, 3500], [70, 200, 250, 300], [0, -20, -26, -34]),
    "h": ([600, 1500, 2500, 3600], [300, 300, 300, 400], [0, -2, -4, -8]),
    "sh": ([1800, 2600, 3800, 5000], [400, 500, 600, 900], [-6, 0, -2, -6]),
    "s": ([4500, 6500, 8000, 9500], [1000, 1500, 1800, 2000], [-4, 0, -3, -6]),
}


def vowel_tracks(n, seq, scale=1.0, bw_scale=1.0):
    """Interpolated formant tracks. seq: [(t_sec, vowel_name), ...] -> list of (f, bw, gain_lin)."""
    if isinstance(seq, str):
        seq = [(0.0, seq)]
    ts = [s[0] for s in seq]
    t = tt(n)
    tracks = []
    for k in range(4):
        fs = [VOWELS[v][0][k] * scale for _, v in seq]
        bws = [VOWELS[v][1][k] * bw_scale * max(scale, 0.35) for _, v in seq]
        gs = [VOWELS[v][2][k] for _, v in seq]
        if len(seq) == 1:
            fa, ba, ga = np.full(n, fs[0]), np.full(n, bws[0]), np.full(n, gs[0])
        else:
            fa, ba, ga = np.interp(t, ts, fs), np.interp(t, ts, bws), np.interp(t, ts, gs)
        tracks.append((fa, ba, undb(ga)))
    return tracks


def formant(src, tracks, block=64, extra=None):
    """Parallel band-pass formant filter bank (time-varying)."""
    out = np.zeros(len(src))
    for f, bwid, g in tracks:
        q = np.clip(f / np.maximum(bwid, 1.0), 0.5, 60)
        y = tvf(src, "bp", f, q, block=block)
        out += y * _as_env(g, len(src))
    if extra:
        for f, bwid, g in extra:
            out += tvf(src, "bp", f, np.clip(f / bwid, 0.5, 80), block=block) * g
    return out


def vocal(f0, seq, rng, scale=1.0, bw_scale=1.0, **gkw):
    """Convenience: glottal source through vowel formant sequence."""
    src = glottal(f0, rng, **gkw)
    return formant(src, vowel_tracks(len(f0), seq, scale, bw_scale))


def breath_noise(n, seq, rng, scale=1.0, bw_scale=1.6, tilt=-2.0):
    """Unvoiced (whispered) formant-filtered noise."""
    src = shaped_noise(n, rng, tilt, 150.0, 12000.0)
    return formant(src, vowel_tracks(n, seq, scale, bw_scale))


# ---------------------------------------------------------------------------
# modal synthesis
# ---------------------------------------------------------------------------
_RATIOS = {
    "bar": [1.0, 2.756, 5.404, 8.933, 13.344, 18.64],
    "bell": [0.5, 1.0, 1.183, 1.506, 2.0, 2.514, 2.662, 3.011, 4.166, 5.433, 6.0, 6.65],
    "glass": [1.0, 2.32, 4.25, 6.63, 9.38, 12.6],
    "marimba": [1.0, 3.93, 9.22, 16.6],
}


def material_modes(mat, f0, rng, n_modes=None, decay=1.0):
    """Return (freqs, t60s, amps) for a material preset around base frequency f0."""
    r = rng
    if mat in ("metal", "metal_plate"):
        k = n_modes or 28
        ratios = np.sort(np.concatenate([[1.0], np.cumsum(r.uniform(0.18, 0.55, k - 1)) + 1.0]))
        freqs = f0 * ratios * (1 + r.normal(0, 0.01, k))
        t60 = 1.6 * decay * (f0 / freqs) ** 0.55 * r.uniform(0.6, 1.3, k)
        amps = r.uniform(0.3, 1.0, k) * (f0 / freqs) ** 0.25
    elif mat == "metal_thin":  # tin can, sheet: dense, rattly, shorter
        k = n_modes or 34
        ratios = np.sort(np.concatenate([[1.0], np.cumsum(r.uniform(0.08, 0.35, k - 1)) + 1.0]))
        freqs = f0 * ratios
        t60 = 0.45 * decay * (f0 / freqs) ** 0.4 * r.uniform(0.5, 1.4, k)
        amps = r.uniform(0.2, 1.0, k)
    elif mat == "metal_bar":
        rat = np.array(_RATIOS["bar"])
        freqs = f0 * rat * (1 + r.normal(0, 0.006, len(rat)))
        t60 = 2.5 * decay * (f0 / freqs) ** 0.5
        amps = np.array([1.0, 0.6, 0.4, 0.25, 0.15, 0.1])
    elif mat == "pipe":
        # cylindrical shell: near-harmonic bending modes + inharmonic shell modes
        k = n_modes or 18
        base = f0 * np.array([1.0, 2.04, 3.13, 4.27, 5.48, 6.71])
        extra = f0 * r.uniform(1.4, 9.0, k - 6)
        freqs = np.concatenate([base, extra])
        t60 = 1.2 * decay * (f0 / freqs) ** 0.45 * r.uniform(0.7, 1.2, len(freqs))
        amps = np.concatenate([[1, 0.7, 0.5, 0.35, 0.25, 0.2], r.uniform(0.05, 0.3, k - 6)])
    elif mat == "bell":
        rat = np.array(_RATIOS["bell"])
        freqs = f0 * rat * (1 + r.normal(0, 0.003, len(rat)))
        t60 = 3.0 * decay * (f0 / freqs) ** 0.6
        amps = np.array([0.5, 1.0, 0.7, 0.4, 0.6, 0.3, 0.3, 0.25, 0.2, 0.12, 0.1, 0.08])
    elif mat == "glass":
        rat = np.array(_RATIOS["glass"])
        f = f0 * rat * (1 + r.normal(0, 0.004, len(rat)))
        freqs = np.concatenate([f, f * (1 + r.uniform(0.002, 0.008, len(f)))])  # beating pairs
        t60 = 2.2 * decay * np.concatenate([(f0 / f) ** 0.5] * 2)
        amps = np.concatenate([[1, 0.6, 0.4, 0.3, 0.2, 0.15]] * 2) * r.uniform(0.6, 1.0, len(freqs))
    elif mat == "wood":
        k = n_modes or 10
        ratios = np.array([1.0, 1.58, 2.32, 3.1, 3.73, 4.6, 5.4, 6.4, 7.3, 8.1])[:k]
        freqs = f0 * ratios * (1 + r.normal(0, 0.04, k))
        t60 = 0.22 * decay * (f0 / freqs) ** 1.1 * r.uniform(0.7, 1.3, k)
        amps = r.uniform(0.4, 1.0, k) * (f0 / freqs) ** 0.3
    elif mat == "wood_hollow":
        k = n_modes or 9
        ratios = np.array([1.0, 1.9, 2.6, 3.5, 4.4, 5.6, 6.9, 8.3, 9.7])[:k]
        freqs = f0 * ratios * (1 + r.normal(0, 0.05, k))
        t60 = 0.35 * decay * (f0 / freqs) ** 0.9 * r.uniform(0.7, 1.3, k)
        amps = np.array([1.0, 0.8, 0.6, 0.5, 0.45, 0.4, 0.3, 0.25, 0.2])[:k] * r.uniform(0.6, 1.0, k)
    elif mat == "stone":
        k = n_modes or 30
        freqs = np.exp(r.uniform(np.log(f0), np.log(f0 * 9), k))
        t60 = 0.05 * decay * (f0 / freqs) ** 0.3 * r.uniform(0.5, 1.5, k)
        amps = r.uniform(0.3, 1.0, k)
    elif mat == "plastic":
        k = n_modes or 12
        freqs = np.exp(r.uniform(np.log(f0), np.log(f0 * 6), k))
        t60 = 0.07 * decay * (f0 / freqs) ** 0.5 * r.uniform(0.6, 1.4, k)
        amps = r.uniform(0.3, 1.0, k)
    elif mat == "bone":  # keratin / bone / chitin clicks
        k = n_modes or 10
        freqs = np.exp(r.uniform(np.log(f0), np.log(f0 * 4), k))
        t60 = 0.025 * decay * r.uniform(0.6, 1.4, k)
        amps = r.uniform(0.4, 1.0, k)
    elif mat == "marimba":
        rat = np.array(_RATIOS["marimba"])
        freqs = f0 * rat
        t60 = np.array([1.2, 0.4, 0.15, 0.08]) * decay
        amps = np.array([1.0, 0.35, 0.12, 0.05])
    else:
        raise ValueError(mat)
    keep = freqs < NYQ * 0.92
    return freqs[keep], t60[keep], amps[keep]


def modal(n, freqs, t60s, amps, rng=None, glide=None):
    """Sum of exponentially decaying sinusoids (modal impulse response).

    glide: optional array (len n) of frequency multipliers applied to every mode.
    """
    t = tt(n)
    out = np.zeros(n)
    if glide is not None:
        gph = np.cumsum(glide) / SR
    for f, T, A in zip(freqs, t60s, amps):
        if f >= NYQ * 0.95 or f <= 0:
            continue
        ph0 = rng.uniform(0, 2 * np.pi) if rng is not None else 0.0
        e = np.exp(-6.907755 * t / max(T, 1e-4))
        cut = np.searchsorted(-e, -1e-4)  # samples until -80 dB
        cut = max(cut, 16)
        arg = 2 * np.pi * f * (gph[:cut] if glide is not None else t[:cut]) + ph0
        out[:cut] += A * e[:cut] * np.sin(arg)
    return out


def contact(width_s, rng=None, kind="halfsine"):
    """Contact force pulse of given duration (softer = longer = darker)."""
    w = max(2, ns(width_s))
    x = np.sin(np.pi * np.arange(w) / w)
    if kind == "sharp":
        x = x ** 3
    return x / np.sum(x)


def strike(mat, f0, dur, rng, hardness=0.6, decay=1.0, noise=0.25, n_modes=None,
           noise_f=(800, 9000), glide=None, modes=None):
    """Physically-flavoured impact: contact pulse convolved with a modal body + contact noise."""
    n = ns(dur)
    fr, t6, am = modes if modes is not None else material_modes(mat, f0, rng, n_modes, decay)
    ir = modal(n, fr, t6, am, rng, glide=glide)
    w = lerp(0.006, 0.00015, np.clip(hardness, 0, 1))
    y = sps.fftconvolve(contact(w * rng.uniform(0.8, 1.25)), ir)[:n]
    y = y / (peak(y) + 1e-12)
    if noise > 0:
        nl = ns(0.03)
        nz = shaped_noise(nl, rng, 0.0, noise_f[0], noise_f[1]) * env_exp(nl, lerp(0.004, 0.012, 1 - hardness))
        nz = norm(nz)
        y = mix(y, nz * noise)
    return fade(pad_to(y, n), 0, min(0.025, dur * 0.2))


def thump(dur, rng, f_hi=110, f_lo=45, t60=0.25, noise_amt=0.5, noise_lp=500, sweep=0.03):
    """Low body/ground thump: pitch-dropping sine + low-passed noise."""
    n = ns(dur)
    t = tt(n)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / max(sweep, 1e-3))
    s = np.sin(2 * np.pi * phase_cycles(f)) * env_ar(n, 0.002, t60)
    nz = lp(white(n, rng), noise_lp, n=2) * env_ar(n, 0.001, t60 * 0.5)
    nz = norm(nz)
    return norm(s) + noise_amt * nz


def bubble(f0, dur, rng, rise=0.6, amp=1.0, damping=None):
    """Minnaert bubble / water drop: exponentially damped sine with rising pitch (van den Doel)."""
    n = ns(dur)
    t = tt(n)
    d = damping if damping is not None else 0.043 * f0 + 0.0014 * f0 ** 1.5
    sigma = rise * d
    f = f0 * (1 + sigma * t)
    f = np.minimum(f, NYQ * 0.9)
    e = np.exp(-d * t)
    x = np.sin(2 * np.pi * phase_cycles(f)) * e
    a = ns(0.0004)
    x[:a] *= np.linspace(0, 1, a)
    return amp * x


# ---------------------------------------------------------------------------
# granular / friction
# ---------------------------------------------------------------------------
def event_times(dur, rate, rng, t0=0.0):
    """Inhomogeneous Poisson event times. rate: scalar, array (per sample) or callable(t)."""
    n = ns(dur)
    if callable(rate):
        r = rate(tt(n))
    else:
        r = _as_env(rate, n)
    rmax = float(np.max(r)) if len(r) else 0.0
    if rmax <= 0:
        return np.array([])
    k = rng.poisson(rmax * dur)
    cand = np.sort(rng.uniform(0, dur, k))
    idx = np.minimum((cand * SR).astype(int), n - 1)
    keep = rng.random(k) < r[idx] / rmax
    return cand[keep] + t0


def scatter(dur, rate, grain_fn, rng, tail=0.5):
    """Granular scatter: grain_fn(rng, t) -> array, placed at Poisson times."""
    out = np.zeros(ns(dur + tail))
    for t in event_times(dur, rate, rng):
        g = grain_fn(rng, t)
        if g is not None:
            place(out, g, t)
    return out


def grain_bank(make, count, rng):
    return [make(rng, i) for i in range(count)]


def noise_grain(rng, f_lo, f_hi, dur=0.006, shape="exp"):
    n = max(8, ns(dur))
    g = shaped_noise(max(n, 64), rng, 0.0, f_lo, f_hi)[:n]
    e = env_exp(n, dur) if shape == "exp" else env_hann(n)
    return g * e


def stick_slip(n, rate, rng, irregular=0.3, amp_var=0.5, pressure=None):
    """Friction excitation: impulse train whose rate follows `rate` (Hz) with jitter."""
    r = _as_env(rate, n)
    j = 1 + irregular * smooth_rand(n, 25.0, rng)
    ph = np.cumsum(np.maximum(r * j, 0)) / SR
    k = np.floor(ph).astype(np.int64)
    ev = np.flatnonzero(np.diff(k, prepend=k[0]) > 0)
    x = np.zeros(n)
    x[ev] = 1.0 + amp_var * rng.standard_normal(len(ev))
    if pressure is not None:
        x *= _as_env(pressure, n)
    return x


def ks_pluck(f, dur, rng, fb=0.996, damp=0.5, excite=None):
    """Karplus-Strong plucked string / rod."""
    n = ns(dur)
    N = max(2, int(round(SR / f)))
    ex = excite if excite is not None else white(N, rng)
    x = np.zeros(n)
    x[: len(ex)] = ex[: n]
    return fade(comb(x, N / SR, fb, damp), 0, min(0.03, dur * 0.2))


# ---------------------------------------------------------------------------
# reverb / space
# ---------------------------------------------------------------------------
def reverb_ir(rt60, rng, dur=None, stereo=False, predelay=0.005, hf=0.45, lf=1.15,
              early=6, early_span=0.05, bright=8000.0, density_ms=12.0):
    """Synthetic IR: band-wise exponentially decaying noise + sparse early reflections.

    hf/lf: RT60 multipliers for high/low bands. Returns (n,) or (n,2).
    """
    dur = dur or rt60 * 1.15
    n = ns(dur)
    chans = 2 if stereo else 1
    out = np.zeros((n, chans))
    t = tt(n)
    bands = [("lowpass", 250, lf), ("bandpass", (250, 1500), 1.0),
             ("bandpass", (1500, 5000), lerp(1.0, hf, 0.5)), ("highpass", 5000, hf)]
    for c in range(chans):
        acc = np.zeros(n)
        for kind, f, mult in bands:
            nz = bw(white(n, rng), kind, f, 2)
            acc += nz * np.power(10.0, -3.0 * t / (rt60 * mult))
        acc = lp(acc, bright)
        # density build-up
        acc *= 1 - np.exp(-t / (density_ms / 1000.0))
        for _ in range(early):
            ti = predelay + rng.uniform(0.002, early_span)
            i = ns(ti)
            if i < n:
                acc[i] += rng.choice([-1, 1]) * rng.uniform(0.3, 1.0) * 6.0 * np.power(10, -3 * ti / rt60)
        d = ns(predelay)
        acc = np.concatenate([np.zeros(d), acc])[:n]
        out[:, c] = acc
    out /= np.sqrt(np.sum(out ** 2) / chans) + 1e-12
    return out if stereo else out[:, 0]


def reverb(x, rt60, rng, wet=0.3, dry=1.0, stereo=False, **kw):
    """Convolve with synthetic IR. Output length = len(x) + ir length."""
    ir = reverb_ir(rt60, rng, stereo=stereo, **kw)
    if stereo and x.ndim == 1:
        w = np.stack([sps.fftconvolve(x, ir[:, 0]), sps.fftconvolve(x, ir[:, 1])], 1)
        d = np.stack([x, x], 1)
    elif stereo:
        w = np.stack([sps.fftconvolve(x[:, 0], ir[:, 0]), sps.fftconvolve(x[:, 1], ir[:, 1])], 1)
        d = x
    else:
        w = sps.fftconvolve(x, ir)
        d = x
    w = w * (rms(d) / (rms(w) + 1e-12))
    return mix(d * dry, w * wet)


def early_reflections(x, rng, n_ref=4, span=0.025, gain=0.25, lpf=5000):
    """Very short early reflections only (for positional sounds)."""
    ir = np.zeros(ns(span + 0.003))
    for _ in range(n_ref):
        i = ns(rng.uniform(0.003, span))
        ir[i] += rng.uniform(0.3, 1.0) * gain * rng.choice([-1, 1])
    refl = lp(sps.fftconvolve(x, ir), lpf)
    return mix(x, refl)


def distance(x, rng, dist=30.0, rt60=1.8, wet=None, stereo=False, **kw):
    """Crude distance model: air absorption LPF + more reverberant energy."""
    fc = 16000.0 / (1.0 + dist / 12.0)
    y = lp(x, max(fc, 300.0), n=2)
    w = wet if wet is not None else np.clip(0.25 + dist / 60.0, 0.2, 1.6)
    return reverb(y, rt60, rng, wet=w, dry=1.0, stereo=stereo, **kw)


def circ_conv(x, ir):
    """Circular convolution (loop-safe reverb/filtering). x: (n,) or (n,c); ir same chans."""
    n = len(x)
    if ir.ndim == 1 and x.ndim == 2:
        ir = np.stack([ir] * x.shape[1], 1)
    m = len(ir)
    reps = int(np.ceil(m / n))
    irf = pad_to(ir, reps * n).reshape((reps, n) + ir.shape[1:]).sum(axis=0)
    X = np.fft.rfft(x, axis=0)
    H = np.fft.rfft(irf, axis=0)
    return np.fft.irfft(X * H, n, axis=0)


def circ(fn, x, reps=3):
    """Apply a (causal, finite-memory) process circularly: tile, process, take middle."""
    n = len(x)
    big = np.concatenate([x] * reps, axis=0)
    y = fn(big)
    k = reps // 2
    return y[k * n:(k + 1) * n]


def loopify(x, n_loop, xfade, power=True):
    """Crossfade the tail (beyond n_loop) back into the start -> seamless loop of n_loop."""
    X = min(int(xfade), len(x) - n_loop)
    y = x[:n_loop].copy()
    if X <= 0:
        return y
    r = np.linspace(0, 1, X)
    fi, fo = (np.sin(0.5 * np.pi * r), np.cos(0.5 * np.pi * r)) if power else (r, 1 - r)
    sh = (-1,) + (1,) * (x.ndim - 1)
    y[:X] = x[:X] * fi.reshape(sh) + x[n_loop:n_loop + X] * fo.reshape(sh)
    return y


def periodic_f0(f0, n_loop):
    """Scale an f0 contour so its total phase over the loop is an integer number of cycles."""
    cyc = np.sum(f0) / SR
    target = max(1, round(cyc))
    return f0 * (target / cyc)


# ---------------------------------------------------------------------------
# non-linear / colour
# ---------------------------------------------------------------------------
def sat(x, drive=2.0):
    return np.tanh(drive * x) / np.tanh(drive)


def sat_asym(x, drive=2.0, bias=0.2):
    y = np.tanh(drive * (x + bias)) - np.tanh(drive * bias)
    return y / (peak(y) + 1e-12) * peak(x)


def crush(x, bits=8, down=1):
    q = 2.0 ** (bits - 1)
    y = np.round(x * q) / q
    if down > 1:
        y = np.repeat(y[::down], down, axis=0)[: len(x)]
    return y


def ring(x, f, n=None):
    return x * np.sin(2 * np.pi * phase_cycles(_as_env(f, len(x))))


def soft_limit(x, ceiling=0.89):
    """Point-wise soft-knee limiter (loop safe, no memory)."""
    k = ceiling * 0.7
    a = np.abs(x)
    over = a > k
    y = x.copy()
    y[over] = np.sign(x[over]) * (k + (ceiling - k) * np.tanh((a[over] - k) / (ceiling - k)))
    return y


# ---------------------------------------------------------------------------
# stereo
# ---------------------------------------------------------------------------
def pan(x, p):
    """Constant-power pan, p in [-1, 1] (scalar or array)."""
    p = _as_env(p, len(x))
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1)


def widen(x, rng, amount=0.5):
    """Mono -> stereo via complementary all-pass decorrelation."""
    l = allpass(allpass(x, rng.uniform(0.003, 0.007), 0.5), rng.uniform(0.008, 0.013), 0.4)
    r = allpass(allpass(x, rng.uniform(0.003, 0.007), 0.5), rng.uniform(0.008, 0.013), 0.4)
    m = x
    return np.stack([lerp(m, l, amount), lerp(m, r, amount)], 1)


def stereo(l, r):
    n = max(len(l), len(r))
    return np.stack([pad_to(l, n), pad_to(r, n)], 1)


def to_mono(x):
    return x.mean(axis=1) if x.ndim == 2 else x
