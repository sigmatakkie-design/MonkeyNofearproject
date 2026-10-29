"""mnf_sets_cards - alpha-cutout foliage cards, FX particle sprites and the CRT scanline overlay."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

import mnf_noise as mn
import mnf_texio as tio
from mnf_noise import seed_of, smoothstep
from mnf_registry import texset

TAU = 2 * np.pi


# =========================================================================== card canvas
class Card:
    """Supersampled RGB + alpha + height drawing surface for non-tiling cards/sprites."""

    def __init__(self, size, ss=4):
        self.size, self.ss = size, ss
        self.W = size * ss
        self.rgb = Image.new("RGB", (self.W, self.W), (0, 0, 0))
        self.a = Image.new("L", (self.W, self.W), 0)
        self.h = Image.new("L", (self.W, self.W), 0)
        self.dr, self.da, self.dh = ImageDraw.Draw(self.rgb), ImageDraw.Draw(self.a), ImageDraw.Draw(self.h)

    def P(self, pts):
        return [(float(x) * self.W, float(y) * self.W) for x, y in pts]

    def line(self, pts, col, width, hv=200, alpha=255):
        w = max(1, int(round(width * self.ss)))
        P = self.P(pts)
        self.dr.line(P, fill=tuple(int(c) for c in col), width=w, joint="curve")
        self.da.line(P, fill=alpha, width=w, joint="curve")
        self.dh.line(P, fill=int(hv), width=w, joint="curve")

    def poly(self, pts, col, hv=200, alpha=255):
        P = self.P(pts)
        self.dr.polygon(P, fill=tuple(int(c) for c in col))
        self.da.polygon(P, fill=alpha)
        self.dh.polygon(P, fill=int(hv))

    def result(self):
        rgb = mn.downsample(np.asarray(self.rgb, dtype=np.float64) / 255.0, self.ss)
        a = mn.downsample(np.asarray(self.a, dtype=np.float64) / 255.0, self.ss)
        h = mn.downsample(np.asarray(self.h, dtype=np.float64) / 255.0, self.ss)
        rgb = np.where(a[..., None] > 1e-3, rgb / np.maximum(a[..., None], 1e-3), 0)   # un-premultiply edges
        return np.clip(rgb, 0, 1), a, h


def bezier(p0, p1, p2, n=24):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2 = map(np.asarray, (p0, p1, p2))
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2


def card_finish(rgb, a, h, smooth=0.3, nstrength=3.0, inner_ao=None):
    S = a.shape[0]
    yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
    e = np.minimum(np.minimum(xx, 1 - xx), yy)          # keep the bottom edge (stems enter there)
    a = a * smoothstep(0.0, 0.025, e)
    hb = ndimage.gaussian_filter(h * a, 1.0)
    n = mn.height_to_normal(hb, nstrength)
    # outside the card keep a flat normal
    n = n * a[..., None] + np.array([0, 0, 1.0]) * (1 - a[..., None])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    cov = ndimage.gaussian_filter(a, 10)
    ao = np.clip(1.0 - 0.55 * cov, 0.3, 1.0)
    if inner_ao is not None:
        ao = ao * inner_ao
    alb = rgb * (0.65 + 0.35 * ao)[..., None]
    return tio.finish(alb, h, 0.0, np.full((S, S), smooth) * (0.8 + 0.4 * h), ao=ao, normal=n, ao_strength=0.0,
                      alpha=np.clip(a, 0, 1))


def _shade(col, k, r=None, var=0.08):
    c = np.array(col, dtype=np.float64) * k
    if r is not None:
        c = c * (1 + (r.random(3) - 0.5) * var)
    return np.clip(c, 0, 255)


# =========================================================================== foliage cards
@texset("foliage_pine", None, cutout=True, notes="Alpha-cutout card (not tiling): dense dark conifer branch, stem "
        "enters at bottom centre and grows up. Two-sided, alpha test ~0.4.")
def foliage_pine(S):
    sd = "foliage_pine"
    r = mn.rng(seed_of(sd, "draw"))
    C = Card(S, 4)
    greens = [(26, 40, 28), (32, 48, 32), (38, 56, 36), (46, 64, 40), (30, 46, 36), (52, 68, 44)]

    def twig(path, needle_len, density, depth, base_k):
        path = np.asarray(path)
        seglen = np.linalg.norm(np.diff(path, axis=0), axis=1).sum()
        nN = int(seglen * density)
        d = np.gradient(path, axis=0)
        d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
        for k in range(nN):
            t = r.random()
            i = min(int(t * (len(path) - 1)), len(path) - 2)
            p = path[i] + (path[i + 1] - path[i]) * r.random()
            dirv = d[i]
            side = 1 if r.random() < 0.5 else -1
            ang = np.arctan2(dirv[1], dirv[0]) + side * r.uniform(0.55, 1.15)
            L = needle_len * r.uniform(0.7, 1.15) * (1.0 - 0.45 * t)
            q = p + np.array([np.cos(ang), np.sin(ang)]) * L
            g = greens[r.integers(len(greens))]
            kk = base_k * (0.75 + 0.5 * t) * r.uniform(0.85, 1.15)
            col = (_shade((88, 68, 44), 1.0, r) if r.random() < 0.04 else _shade(g, kk, r))
            C.line([tuple(p), tuple(q)], col, r.uniform(0.8, 1.25), hv=80 + depth * 50 + 60 * t)

    # main stem
    stem = bezier((0.5, 1.02), (0.44 + r.uniform(-0.05, 0.05), 0.5), (0.5 + r.uniform(-0.05, 0.05), 0.04), 40)
    for layer in range(2):
        base_k = 0.75 if layer == 0 else 1.05
        for k in range(18):
            t = 0.06 + 0.88 * k / 17 + r.uniform(-0.02, 0.02)
            i = int(t * (len(stem) - 1))
            p0 = stem[i]
            side = -1 if (k + layer) % 2 == 0 else 1
            L = (0.33 * (1 - t) + 0.1) * r.uniform(0.85, 1.05)
            ang = -np.pi / 2 + side * r.uniform(0.85, 1.35)
            p2 = p0 + np.array([np.cos(ang), np.sin(ang)]) * L
            p1 = p0 + np.array([np.cos(ang + side * 0.3), np.sin(ang + side * 0.3)]) * L * 0.5
            br = bezier(p0, p1, p2, 16)
            if layer == 0:
                C.line([tuple(x) for x in br], (40, 30, 24), 2.0 * (1 - t) + 0.8, hv=70)
            twig(br, 0.055, 900, layer, base_k)
            for j in range(4):          # sub-twigs
                tt = r.uniform(0.25, 0.85)
                q0 = br[int(tt * 15)]
                a2 = ang + r.choice([-1, 1]) * r.uniform(0.5, 0.9)
                q2 = q0 + np.array([np.cos(a2), np.sin(a2)]) * L * r.uniform(0.25, 0.45)
                sub = bezier(q0, (q0 + q2) / 2 + r.uniform(-0.01, 0.01, 2), q2, 10)
                twig(sub, 0.045, 900, layer, base_k * 0.95)
        if layer == 0:
            C.line([tuple(x) for x in stem], (44, 34, 27), 3.2, hv=90)
        twig(stem[4:], 0.06, 700, layer, base_k)
    rgb, a, h = C.result()
    yy, xx = np.mgrid[0:S, 0:S] / S
    inner = np.clip(1 - 0.4 * np.exp(-((xx - 0.5) / 0.15) ** 2), 0.5, 1)
    return card_finish(rgb, a, h, smooth=0.28, nstrength=4.0, inner_ao=inner)


def _leaf_shape(c, length, width, ang, r, n=18, jag=0.0):
    pts_l, pts_r = [], []
    d = np.array([np.cos(ang), np.sin(ang)])
    nrm = np.array([-d[1], d[0]])
    curl = r.uniform(-0.25, 0.25)
    for t in np.linspace(0, 1, n):
        w = np.sin(np.pi * t ** 0.75) * width * 0.5 * (1 + (r.random() - 0.5) * jag)
        bend = curl * t * t * length
        base = np.asarray(c) + d * t * length + nrm * bend
        pts_l.append(tuple(base + nrm * w))
        pts_r.append(tuple(base - nrm * w))
    mid = [tuple(np.asarray(c) + d * t * length + nrm * curl * t * t * length) for t in np.linspace(0, 1, n)]
    return pts_l + pts_r[::-1], mid, d, nrm


@texset("foliage_leaf", None, cutout=True, notes="Alpha-cutout card: twig with a cluster of dead/dark withered "
        "leaves (olive, brown, near-black), holes and curled tips.")
def foliage_leaf(S):
    sd = "foliage_leaf"
    r = mn.rng(seed_of(sd, "draw"))
    C = Card(S, 4)
    cols = [(54, 56, 32), (70, 52, 32), (40, 32, 24), (92, 60, 36), (60, 62, 38), (78, 46, 30), (48, 40, 28),
            (104, 78, 46)]
    stem = bezier((0.5, 1.02), (0.55, 0.6), (0.46, 0.08), 30)
    C.line([tuple(x) for x in stem], (46, 36, 28), 2.6, hv=90)
    twigs = [stem]
    for k in range(6):
        t = 0.2 + 0.7 * k / 5
        p0 = stem[int(t * 29)]
        side = -1 if k % 2 == 0 else 1
        ang = -np.pi / 2 + side * r.uniform(0.6, 1.0)
        L = r.uniform(0.18, 0.3) * (1.1 - t * 0.5)
        p2 = p0 + np.array([np.cos(ang), np.sin(ang)]) * L
        br = bezier(p0, (p0 + p2) / 2 + r.uniform(-0.03, 0.03, 2), p2, 12)
        C.line([tuple(x) for x in br], (48, 38, 30), 1.6, hv=90)
        twigs.append(br)
    leaves = []
    for tw in twigs:
        for j in range(int(len(tw) * 0.5) + 2):
            i = r.integers(2, len(tw))
            p = tw[i]
            d = tw[min(i + 1, len(tw) - 1)] - tw[i - 1]
            base_ang = np.arctan2(d[1], d[0])
            ang = base_ang + r.choice([-1, 1]) * r.uniform(0.5, 1.3)
            leaves.append((p, ang, r.uniform(0.09, 0.16)))
    order = r.permutation(len(leaves))
    for idx in order:
        p, ang, L = leaves[idx]
        col = np.array(cols[r.integers(len(cols))], dtype=np.float64) * r.uniform(0.8, 1.15)
        poly, mid, d, nrm = _leaf_shape(p, L, L * r.uniform(0.4, 0.55), ang, r, 20, jag=0.25)
        hv = r.uniform(130, 220)
        C.poly(poly, col, hv=hv)
        C.line(mid, col * 0.65, 0.8, hv=hv + 15)
        for t in np.linspace(0.2, 0.8, 4):          # side veins
            q = np.asarray(mid[int(t * 19)])
            for sgn in (-1, 1):
                C.line([tuple(q), tuple(q + (d * 0.4 + nrm * sgn) * L * 0.18)], col * 0.75, 0.5, hv=hv + 8)
        if r.random() < 0.3:                       # occasional insect hole / decay
            q = np.asarray(mid[int(r.uniform(0.3, 0.8) * 19)]) + nrm * r.uniform(-0.4, 0.4) * L * 0.3
            rr = r.uniform(0.003, 0.007)
            hole = [tuple((q + np.array([np.cos(a), np.sin(a)]) * rr * r.uniform(0.5, 1.2)) * C.W)
                    for a in np.linspace(0, TAU, 7)[:-1]]
            C.da.polygon(hole, fill=0)
        # dry brown edge
        C.dr.line(C.P(poly), fill=tuple(int(c) for c in col * 0.55), width=2)
    rgb, a, h = C.result()
    mott = mn.fbm(S, 24, 4, seed_of(sd, "mott"))
    rgb = rgb * (0.8 + 0.4 * mott)[..., None]
    return card_finish(rgb, a, h, smooth=0.3, nstrength=4.0)


@texset("fern", None, cutout=True, notes="Alpha-cutout card: arching fern fronds radiating from the bottom centre, "
        "dark green with browning tips.")
def fern(S):
    sd = "fern"
    r = mn.rng(seed_of(sd, "draw"))
    C = Card(S, 4)
    nf = 7
    for f in range(nf):
        spread = (f / (nf - 1) - 0.5) * 2
        base = np.array([0.5 + spread * 0.04, 1.0])
        tip = np.array([0.5 + spread * 0.46 + r.uniform(-0.04, 0.04), 0.08 + abs(spread) * 0.35 + r.uniform(0, 0.08)])
        ctrl = np.array([0.5 + spread * 0.25, 0.25 + abs(spread) * 0.05])
        rach = bezier(base, ctrl, tip, 60)
        green = np.array([(34, 54, 28), (40, 62, 32), (30, 48, 26), (46, 66, 34)][f % 4], dtype=np.float64)
        green *= r.uniform(0.85, 1.1)
        brown = np.array([88, 70, 42], dtype=np.float64)
        hv0 = 120 + 60 * (1 - abs(spread))
        d_all = np.gradient(rach, axis=0)
        for i in range(6, 60, 2):
            t = i / 59.0
            p = rach[i]
            d = d_all[i] / (np.linalg.norm(d_all[i]) + 1e-9)
            nrm = np.array([-d[1], d[0]])
            plen = 0.13 * np.sin(np.pi * min(1.0, t * 1.15) ** 0.8) * (1 - 0.3 * t) + 0.01
            dead = smoothstep(0.75, 1.0, t) * r.uniform(0.3, 1.0)
            for sgn in (-1, 1):
                ang_v = nrm * sgn + d * 0.55
                ang_v /= np.linalg.norm(ang_v)
                end = p + ang_v * plen
                n_lobes = 7
                pts_a, pts_b = [], []
                pn = np.array([-ang_v[1], ang_v[0]])
                for k in range(n_lobes + 1):
                    u = k / n_lobes
                    w = plen * 0.18 * (1 - u) * (0.7 + 0.3 * abs(np.sin(u * np.pi * n_lobes)))
                    q = p + ang_v * plen * u + d * plen * 0.12 * u * u
                    pts_a.append(tuple(q + pn * w))
                    pts_b.append(tuple(q - pn * w))
                col = green * (0.8 + 0.4 * t) * r.uniform(0.9, 1.1)
                col = col * (1 - dead) + brown * dead
                C.poly(pts_a + pts_b[::-1], col, hv=hv0 + 40 * t)
                C.line([tuple(p), tuple(end)], col * 0.7, 0.5, hv=hv0 + 45 * t)
        C.line([tuple(x) for x in rach], (40, 50, 28), 1.4, hv=hv0 + 50)
    rgb, a, h = C.result()
    rgb = rgb * (0.85 + 0.3 * mn.fbm(S, 16, 3, seed_of(sd, "m")))[..., None]
    yy, xx = np.mgrid[0:S, 0:S] / S
    inner = 0.6 + 0.4 * smoothstep(1.0, 0.6, yy)
    return card_finish(rgb, a, h, smooth=0.3, nstrength=4.0, inner_ao=np.clip(inner + 0.2, 0, 1))


@texset("grass", None, cutout=True, notes="Alpha-cutout card: wild grass tuft rooted along the bottom edge, "
        "muted green with dry yellowed blades.")
def grass(S):
    sd = "grass"
    r = mn.rng(seed_of(sd, "draw"))
    C = Card(S, 4)
    n = 110
    order = r.permutation(n)
    for i in order:
        x0 = 0.5 + r.normal(0, 0.12)
        x0 = float(np.clip(x0, 0.08, 0.92))
        h = r.uniform(0.35, 0.95) * (1 - abs(x0 - 0.5) * 0.8)
        lean = (x0 - 0.5) * 1.2 + r.normal(0, 0.15)
        p0 = np.array([x0, 1.01])
        p2 = np.array([x0 + lean * h * 0.6, 1.0 - h])
        p1 = np.array([x0 + lean * h * 0.15, 1.0 - h * 0.6])
        path = bezier(p0, p1, p2, 20)
        w0 = r.uniform(0.007, 0.014)
        poly = tio.taper_polygon(path, w0, w0 * 0.1)
        dry = r.random() < 0.3
        base_c = np.array((92, 92, 56) if dry else (46, 60, 32), dtype=np.float64) * r.uniform(0.75, 1.2)
        tip_c = np.array((128, 118, 76) if dry else (78, 88, 48), dtype=np.float64) * r.uniform(0.8, 1.1)
        depth = r.uniform(0, 1)
        # draw blade as 4 coloured segments (dark base -> lighter tip)
        for k in range(4):
            a0, a1 = k * 5, min(20, (k + 1) * 5 + 1)
            seg = path[a0:a1]
            w_a = w0 * (1 - 0.9 * a0 / 19)
            w_b = w0 * (1 - 0.9 * (a1 - 1) / 19)
            pp = tio.taper_polygon(seg, w_a, w_b)
            t = (k + 0.5) / 4
            col = (base_c * (1 - t) + tip_c * t) * (0.55 + 0.45 * t) * (0.8 + 0.3 * depth)
            C.poly([tuple(q) for q in pp], col, hv=60 + 120 * depth + 60 * t)
        mid = path[2:]
        C.line([tuple(q) for q in mid], base_c * 0.7, 0.35, hv=70 + 120 * depth)
    rgb, a, h = C.result()
    yy = np.mgrid[0:S, 0:S][0] / S
    inner = 0.45 + 0.55 * smoothstep(1.0, 0.55, yy)
    return card_finish(rgb, a, h, smooth=0.3, nstrength=3.0, inner_ao=inner)


# =========================================================================== FX sprites
def _radial(S, cx=0.5, cy=0.5):
    yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
    return np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2), yy, xx


def _sprite(rgb_col, alpha):
    S = alpha.shape[0]
    rgb = np.ones((S, S, 3)) * np.asarray(rgb_col) if np.ndim(rgb_col) == 1 else rgb_col
    return np.concatenate([np.clip(rgb, 0, 1), np.clip(alpha, 0, 1)[..., None]], -1)


def _edge_fade(S, margin=0.06):
    yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
    e = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    return smoothstep(0.0, margin, e)


@texset("fx_dust", None, kind="sprite", size=128, notes="Particle: soft dust mote (pale grey, alpha falloff).")
def fx_dust(S):
    d, yy, xx = _radial(S)
    n = mn.fbm(S, 4, 4, seed_of("fx_dust", "n"))
    a = np.exp(-(d / 0.14) ** 2 * (0.8 + 0.6 * n)) * 0.85
    a = a * _edge_fade(S)
    return _sprite(tio.rgb(214, 208, 196), a)


@texset("fx_spark", None, kind="sprite", size=128, notes="Particle: hot spark streak (white-yellow core, orange glow); "
        "use additive, stretched billboard.")
def fx_spark(S):
    yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
    dx, dy = (xx - 0.5), (yy - 0.5)
    core = np.exp(-(dx / 0.035) ** 2 - (dy / 0.22) ** 2)
    glow = np.exp(-(dx / 0.12) ** 2 - (dy / 0.38) ** 2) * 0.5
    a = np.clip(core + glow, 0, 1) * _edge_fade(S)
    t = np.clip(core * 1.2, 0, 1)[..., None]
    rgb = tio.rgb(255, 128, 36) * (1 - t) + tio.rgb(255, 240, 200) * t
    return _sprite(rgb, a)


@texset("fx_smoke", None, kind="sprite", size=128, notes="Particle: soft billowy grey smoke puff.")
def fx_smoke(S):
    d, yy, xx = _radial(S)
    n = mn.fbm(S, 3, 5, seed_of("fx_smoke", "n"))
    n2 = mn.fbm(S, 8, 4, seed_of("fx_smoke", "n2"))
    shape = smoothstep(0.5, 0.15, d + (n - 0.5) * 0.22)
    a = shape * (0.45 + 0.55 * n2) * 0.8 * _edge_fade(S, 0.1)
    rgb = np.ones((S, S, 3)) * (0.42 + 0.25 * n2)[..., None] * np.array([1.0, 0.99, 0.97])
    return _sprite(rgb, a)


@texset("fx_fog", None, kind="sprite", size=256, notes="Particle: very soft large fog cloud, low alpha (max ~0.5).")
def fx_fog(S):
    d, yy, xx = _radial(S)
    n = mn.fbm(S, 2, 5, seed_of("fx_fog", "n"))
    n2 = mn.fbm(S, 5, 4, seed_of("fx_fog", "n2"))
    shape = smoothstep(0.5, 0.05, d + (n - 0.5) * 0.25)
    a = shape ** 1.5 * (0.5 + 0.5 * n2) * 0.5 * _edge_fade(S, 0.15)
    a = ndimage.gaussian_filter(a, 3)
    return _sprite(tio.rgb(196, 202, 206), a)


@texset("fx_glow", None, kind="sprite", size=128, notes="Particle/flare: smooth radial falloff glow, white (tint in "
        "material).")
def fx_glow(S):
    d, _, _ = _radial(S)
    a = np.clip(1 - d / 0.5, 0, 1) ** 2.2
    a = a * 0.6 + np.exp(-(d / 0.08) ** 2) * 0.4
    return _sprite(np.array([1.0, 1.0, 1.0]), a * _edge_fade(S, 0.02))


@texset("fx_leaf", None, kind="sprite", size=128, notes="Particle: single falling dead leaf.")
def fx_leaf(S):
    r = mn.rng(seed_of("fx_leaf", "d"))
    C = Card(S, 4)
    poly, mid, d, nrm = _leaf_shape((0.12, 0.62), 0.78, 0.34, -0.45, r, 24, jag=0.15)
    C.poly(poly, (86, 62, 40))
    C.line(mid, (70, 46, 28), 1.2)
    C.line([(0.06, 0.66), (0.14, 0.61)], (70, 50, 34), 1.5)
    for t in np.linspace(0.15, 0.85, 6):
        q = np.asarray(mid[int(t * 23)])
        for sgn in (-1, 1):
            C.line([tuple(q), tuple(q + (d * 0.5 + nrm * sgn) * 0.08)], (84, 56, 32), 0.6)
    rgb, a, h = C.result()
    m = mn.fbm(S, 10, 4, seed_of("fx_leaf", "m"))
    rgb = rgb * (0.75 + 0.45 * m)[..., None]
    rgb = tio.mix(rgb, tio.rgb(60, 42, 30), smoothstep(0.65, 0.85, mn.fbm(S, 6, 3, seed_of("fx_leaf", "s"))))
    return _sprite(rgb, a)


@texset("fx_drip", None, kind="sprite", size=128, notes="Particle: falling water drip (translucent teardrop with "
        "highlight).")
def fx_drip(S):
    yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
    dx = xx - 0.5
    body = np.sqrt((dx / 0.16) ** 2 + ((yy - 0.66) / 0.2) ** 2)
    tail_w = 0.16 * smoothstep(0.15, 0.62, yy)
    tail = (np.abs(dx) < tail_w) & (yy > 0.15) & (yy < 0.66)
    shape = np.maximum(smoothstep(1.0, 0.85, body), tail.astype(float))
    shape = ndimage.gaussian_filter(shape, 1.0)
    rim = smoothstep(0.6, 1.0, body) * smoothstep(1.05, 0.9, body)
    hl = np.exp(-((xx - 0.44) / 0.035) ** 2 - ((yy - 0.6) / 0.06) ** 2)
    a = np.clip(shape * (0.35 + 0.4 * rim) + hl * 0.6, 0, 1)
    rgb = tio.rgb(150, 168, 176) * (1 - hl[..., None]) + np.array([1.0, 1.0, 1.0]) * hl[..., None]
    return _sprite(rgb, a)


@texset("fx_debris", None, kind="sprite", size=128, notes="Particle: small rock/concrete chips cluster (sheet of "
        "irregular fragments).")
def fx_debris(S):
    r = mn.rng(seed_of("fx_debris", "d"))
    C = Card(S, 4)
    for i in range(7):
        c = np.array([r.uniform(0.2, 0.8), r.uniform(0.2, 0.8)])
        rad = r.uniform(0.05, 0.12)
        k = int(r.integers(5, 8))
        angs = np.sort(r.uniform(0, TAU, k))
        pts = [tuple(c + np.array([np.cos(a), np.sin(a)]) * rad * r.uniform(0.6, 1.0)) for a in angs]
        g = r.uniform(70, 120)
        C.poly(pts, (g, g * 0.95, g * 0.88), hv=int(r.uniform(120, 230)))
    rgb, a, h = C.result()
    n = mn.height_to_normal(ndimage.gaussian_filter(h, 1.5), 6.0)
    shade = np.clip(0.55 + 0.6 * (n[..., 0] * -0.5 + n[..., 1] * 0.6), 0.3, 1.2)
    rgb = rgb * shade[..., None] * (0.85 + 0.3 * mn.fbm(S, 16, 3, seed_of("fx_debris", "m")))[..., None]
    return _sprite(rgb, a)


@texset("screen_scanlines", None, kind="sprite", size=256, notes="Tileable CRT overlay (alpha-blended): soft dark "
        "scanlines every 4 px, faint aperture grille, sparse static noise and a slow roll band.")
def screen_scanlines(S):
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64)
    lines = 0.5 + 0.5 * np.cos(TAU * yy / 4.0)                       # 64 lines per tile
    grille = 0.5 + 0.5 * np.cos(TAU * xx * 85 / S)                   # ~3 px aperture grille
    r = mn.rng(seed_of("scan", "noise"))
    noise = r.random((S, S))
    roll = mn.fbm(S, (2, 1), 3, seed_of("scan", "roll"))
    a = 0.32 * lines + 0.06 * grille + 0.08 * roll
    sparkle = (noise > 0.985).astype(float)
    a = a * (1 - sparkle) + sparkle * 0.25
    rgb = np.zeros((S, S, 3))
    rgb[sparkle > 0] = 0.9
    rgb[..., 1] += 0.02
    return _sprite(rgb, np.clip(a, 0, 1))
