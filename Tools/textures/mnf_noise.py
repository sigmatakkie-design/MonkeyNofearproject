"""mnf_noise - tileable procedural noise toolkit for MONKEY NO FEAR textures.

Every generator in this module is defined on a torus: the output of size N x N wraps
seamlessly in both directions (frequencies are integer lattice counts per tile and all
filters / samplers use wrap-around boundaries).

Conventions
-----------
* Arrays are float32/float64 shaped (rows, cols) == (y, x); row 0 is the TOP of the image.
* Frequencies are given as an int or a (fy, fx) tuple (lattice cells per tile along y / x).
* Most generators return values normalised to [0, 1].
* Seeds are plain ints; use ``seed_of("set", "layer")`` for stable, readable seeds.
"""
from __future__ import annotations

import zlib

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

TAU = 2.0 * np.pi


# --------------------------------------------------------------------------- utilities
def seed_of(*parts) -> int:
    """Stable 31-bit seed from any parts (independent of PYTHONHASHSEED)."""
    return zlib.crc32("/".join(str(p) for p in parts).encode("utf8")) & 0x7FFFFFFF


def rng(*parts) -> np.random.Generator:
    if len(parts) == 1 and isinstance(parts[0], (int, np.integer)):
        return np.random.default_rng(int(parts[0]))
    return np.random.default_rng(seed_of(*parts))


def _f2(freq):
    if np.isscalar(freq):
        return int(freq), int(freq)
    return int(freq[0]), int(freq[1])


def grid(size):
    """Pixel-centre coordinates (y, x) in [0, 1)."""
    c = (np.arange(size) + 0.5) / size
    return np.meshgrid(c, c, indexing="ij")


def norm01(a, lo_pct=0.5, hi_pct=99.5):
    lo, hi = np.percentile(a, [lo_pct, hi_pct])
    if hi - lo < 1e-9:
        return np.zeros_like(a)
    return np.clip((a - lo) / (hi - lo), 0.0, 1.0)


def minmax01(a):
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / (hi - lo + 1e-12)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-12), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def remap(x, a0, a1, b0=0.0, b1=1.0, clip=True):
    t = (x - a0) / (a1 - a0 + 1e-12)
    if clip:
        t = np.clip(t, 0.0, 1.0)
    return b0 + (b1 - b0) * t


def fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def pdelta(a, b, period=1.0):
    """Shortest periodic difference a - b."""
    d = a - b
    return d - period * np.round(d / period)


# --------------------------------------------------------------------------- filtering / sampling
def blur(a, sigma):
    if np.isscalar(sigma) and sigma <= 0:
        return a
    if a.ndim == 3:
        return np.stack([ndimage.gaussian_filter(a[..., c], sigma, mode="wrap") for c in range(a.shape[2])], -1)
    return ndimage.gaussian_filter(a, sigma, mode="wrap")


def sample(field, py, px, order=1):
    """Sample ``field`` at fractional pixel coords (py, px) with wrap-around."""
    if field.ndim == 3:
        return np.stack([sample(field[..., c], py, px, order) for c in range(field.shape[2])], -1)
    return ndimage.map_coordinates(field, [py, px], order=order, mode="grid-wrap", prefilter=order > 1)


def warp(field, dy, dx, order=1):
    """Displace ``field`` by per-pixel offsets (dy, dx) given in pixels."""
    n_y, n_x = field.shape[:2]
    yy, xx = np.meshgrid(np.arange(n_y, dtype=np.float64), np.arange(n_x, dtype=np.float64), indexing="ij")
    return sample(field, yy + dy, xx + dx, order)


def roll2(a, dy, dx):
    return np.roll(np.roll(a, dy, axis=0), dx, axis=1)


def downsample(a, factor):
    """Box-filter downsample by an integer factor (keeps tiling)."""
    if factor == 1:
        return a
    h, w = a.shape[:2]
    shp = (h // factor, factor, w // factor, factor) + a.shape[2:]
    return a.reshape(shp).mean(axis=(1, 3))


def upsample(a, size, order=3):
    """Periodic resample of a small tileable array to ``size``."""
    n = a.shape[0]
    c = (np.arange(size) + 0.5) * n / size - 0.5
    yy, xx = np.meshgrid(c, c, indexing="ij")
    return sample(a, yy, xx, order=order)


# --------------------------------------------------------------------------- lattice noises
def _axis(size, f, off):
    u = np.arange(size) * (f / size) + off
    i0 = np.floor(u).astype(np.int64)
    t = u - i0
    return i0 % f, (i0 + 1) % f, t


def value(size, freq, seed):
    """Periodic value noise in [0, 1]."""
    fy, fx = _f2(freq)
    r = rng(seed)
    g = r.random((fy, fx))
    oy, ox = r.random(2) * np.array([fy, fx])
    y0, y1, ty = _axis(size, fy, oy)
    x0, x1, tx = _axis(size, fx, ox)
    sy, sx = fade(ty)[:, None], fade(tx)[None, :]
    a, b = g[np.ix_(y0, x0)], g[np.ix_(y0, x1)]
    c, d = g[np.ix_(y1, x0)], g[np.ix_(y1, x1)]
    top = a + (b - a) * sx
    bot = c + (d - c) * sx
    return top + (bot - top) * sy


def perlin(size, freq, seed):
    """Periodic gradient (Perlin) noise, roughly in [-1, 1]."""
    fy, fx = _f2(freq)
    r = rng(seed)
    ang = r.random((fy, fx)) * TAU
    gx, gy = np.cos(ang), np.sin(ang)
    oy, ox = r.random(2) * np.array([fy, fx])
    y0, y1, ty = _axis(size, fy, oy)
    x0, x1, tx = _axis(size, fx, ox)

    def corner(yi, xi, dy, dx):
        return gx[np.ix_(yi, xi)] * (tx - dx)[None, :] + gy[np.ix_(yi, xi)] * (ty - dy)[:, None]

    n00, n01 = corner(y0, x0, 0, 0), corner(y0, x1, 0, 1)
    n10, n11 = corner(y1, x0, 1, 0), corner(y1, x1, 1, 1)
    sx, sy = fade(tx)[None, :], fade(ty)[:, None]
    a = n00 + (n01 - n00) * sx
    b = n10 + (n11 - n10) * sx
    return (a + (b - a) * sy) * 1.414


def fbm(size, freq, octaves=5, seed=0, gain=0.5, lacunarity=2, kind="perlin", mode="fbm", normalize=True):
    """Fractal sum of periodic noise.

    kind: 'perlin' | 'value'.  mode: 'fbm' | 'ridged' | 'turb' (billow).
    """
    fy, fx = _f2(freq)
    total = np.zeros((size, size))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        if fy > size // 2 or fx > size // 2:
            break
        s = seed * 31 + o * 7919 + 13
        n = perlin(size, (fy, fx), s) if kind == "perlin" else value(size, (fy, fx), s) * 2.0 - 1.0
        if mode == "ridged":
            n = 1.0 - np.abs(n)
            n = n * n
        elif mode == "turb":
            n = np.abs(n)
        total += n * amp
        norm += amp
        amp *= gain
        fy *= lacunarity
        fx *= lacunarity
    total /= max(norm, 1e-9)
    return norm01(total) if normalize else total


def warped_fbm(size, freq, octaves=5, seed=0, warp_freq=None, warp_amt=0.08, warp_oct=4, **kw):
    """fBm sampled through an fBm displacement field (classic domain warping).

    warp_amt is a fraction of the tile size.
    """
    warp_freq = warp_freq or freq
    base = fbm(size, freq, octaves, seed, **kw)
    wy = (fbm(size, warp_freq, warp_oct, seed + 101) - 0.5) * 2.0 * warp_amt * size
    wx = (fbm(size, warp_freq, warp_oct, seed + 202) - 0.5) * 2.0 * warp_amt * size
    return warp(base, wy, wx, order=1)


def warp_field(size, freq, amt_px, seed, octaves=4):
    """Return a (dy, dx) displacement field in pixels."""
    wy = (fbm(size, freq, octaves, seed + 11) - 0.5) * 2.0 * amt_px
    wx = (fbm(size, freq, octaves, seed + 22) - 0.5) * 2.0 * amt_px
    return wy, wx


# --------------------------------------------------------------------------- cellular noise
class Cells:
    """Result of a periodic Worley query."""

    def __init__(self, f1, f2, f3, idx, dy, dx, npts):
        self.f1, self.f2, self.f3 = f1, f2, f3
        self.idx = idx            # nearest feature-point id per pixel
        self.dy, self.dx = dy, dx  # periodic offset from nearest feature point (tile units)
        self.n = npts

    @property
    def edge(self):
        """F2 - F1: 0 on cell borders, grows towards cell centres."""
        return self.f2 - self.f1

    def per_cell(self, values):
        """Broadcast a per-cell value array (len n) to pixels."""
        return np.asarray(values)[self.idx]


def worley(size, n, seed, aspect=(1.0, 1.0), k=3, warp_px=None, points=None):
    """Periodic Worley / Voronoi noise.

    n        number of feature points per tile.
    aspect   (ay, ax): points live in an [0,ay)x[0,ax) torus; ax>ay => cells tall & narrow.
    warp_px  optional (dy, dx) per-pixel displacement (in pixels) applied to the lookup.
    Distances are normalised by the mean point spacing so ~1.0 is a typical cell radius*2.
    """
    ay, ax = float(aspect[0]), float(aspect[1])
    r = rng(seed)
    pts = r.random((n, 2)) * np.array([ay, ax]) if points is None else np.asarray(points) * np.array([ay, ax])
    n = len(pts)
    tree = cKDTree(pts, boxsize=[ay, ax])
    yy, xx = grid(size)
    if warp_px is not None:
        yy = yy + warp_px[0] / size
        xx = xx + warp_px[1] / size
    qy = np.mod(yy * ay, ay)
    qx = np.mod(xx * ax, ax)
    q = np.stack([qy.ravel(), qx.ravel()], 1)
    q = np.minimum(q, np.array([ay, ax]) - 1e-9)
    d, i = tree.query(q, k=k)
    scale = np.sqrt(ay * ax / n)
    d = d.reshape(size, size, k) / scale
    i = i.reshape(size, size, k)
    nearest = pts[i[..., 0]]
    dy = pdelta(qy, nearest[..., 0], ay) / ay
    dx = pdelta(qx, nearest[..., 1], ax) / ax
    f3 = d[..., 2] if k > 2 else d[..., -1]
    return Cells(d[..., 0], d[..., 1], f3, i[..., 0], dy, dx, n)


def jittered_points(nx, ny, jitter, seed):
    """Points on a jittered grid in [0,1)^2 (more even than uniform)."""
    r = rng(seed)
    gy, gx = np.meshgrid((np.arange(ny) + 0.5) / ny, (np.arange(nx) + 0.5) / nx, indexing="ij")
    p = np.stack([gy.ravel(), gx.ravel()], 1)
    p += (r.random(p.shape) - 0.5) * jitter * np.array([1.0 / ny, 1.0 / nx])
    return np.mod(p, 1.0)


# --------------------------------------------------------------------------- directional
def streaks(size, fx, fy, seed, octaves=3, sharpness=1.0):
    """Vertical streaks: high frequency along x, low along y."""
    s = fbm(size, (fy, fx), octaves, seed, gain=0.55)
    return np.clip(s, 0, 1) ** sharpness


def wave_lines(size, nx, ny, warp_px=None, phase=0.0):
    """Periodic straight line field 0..1 = frac(nx*x + ny*y). nx, ny must be ints."""
    yy, xx = grid(size)
    if warp_px is not None:
        yy = yy + warp_px[0] / size
        xx = xx + warp_px[1] / size
    return np.mod(nx * xx + ny * yy + phase, 1.0)


def lic(src, vy, vx, length=16, step=0.8, both=True, taper=True):
    """Line integral convolution of ``src`` along the (vy, vx) flow field (wrap)."""
    n_y, n_x = src.shape
    yy, xx = np.meshgrid(np.arange(n_y, dtype=np.float64), np.arange(n_x, dtype=np.float64), indexing="ij")
    acc = src.astype(np.float64).copy()
    wsum = np.ones_like(acc)
    for sgn in ((1.0, -1.0) if both else (1.0,)):
        py, px = yy.copy(), xx.copy()
        for i in range(length):
            dy = sample(vy, py, px)
            dx = sample(vx, py, px)
            py += sgn * dy * step
            px += sgn * dx * step
            w = (1.0 - i / length) if taper else 1.0
            acc += w * sample(src, py, px)
            wsum += w
    return acc / wsum


# --------------------------------------------------------------------------- height derived maps
def gradient(h):
    """Periodic central differences: (dh/dx, dh/dy_image) in height units per pixel."""
    gx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    gy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    return gx, gy


def sobel_gradient(h):
    gx = ndimage.sobel(h, axis=1, mode="wrap") / 8.0
    gy = ndimage.sobel(h, axis=0, mode="wrap") / 8.0
    return gx, gy


def height_to_normal(h, strength=4.0, sobel=True):
    """Tangent-space normal (OpenGL / +Y up) from a height field.

    ``strength`` scales height (0..1 range) per pixel slope. Returns float (H,W,3) in [-1, 1].
    """
    gx, gy = sobel_gradient(h) if sobel else gradient(h)
    nx = -gx * strength
    ny = gy * strength            # image rows grow downward, +V points up => flip sign
    nz = np.ones_like(h)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx * inv, ny * inv, nz * inv], -1)


def combine_normals(n1, n2):
    """Reoriented-ish (UDN) blend of two tangent normals in [-1,1]."""
    x = n1[..., 0] + n2[..., 0]
    y = n1[..., 1] + n2[..., 1]
    z = n1[..., 2]
    inv = 1.0 / np.sqrt(x * x + y * y + z * z)
    return np.stack([x * inv, y * inv, z * inv], -1)


def cavity(h, sigma=4.0):
    """Positive where the surface is lower than its neighbourhood (crevices)."""
    return blur(h, sigma) - h


def convexity(h, sigma=2.0):
    """Positive on ridges / convex edges."""
    return h - blur(h, sigma)


def ambient_occlusion(h, radii=(2, 6, 16), strength=2.5, depth=1.0):
    """Cheap multi-scale height-based AO in [0,1] (1 = unoccluded)."""
    occ = np.zeros_like(h)
    for r in radii:
        occ += np.clip(blur(h, r) - h, 0, None) / np.sqrt(r)
    occ *= strength * depth / len(radii) * 4.0
    return np.clip(1.0 - occ, 0.0, 1.0)


def slope(h):
    gx, gy = sobel_gradient(h)
    return np.sqrt(gx * gx + gy * gy)


# --------------------------------------------------------------------------- wrapped stamping
def stamp(canvas, sprite, cy, cx, alpha=None, op="over"):
    """Composite ``sprite`` centred at (cy, cx) into ``canvas`` with wrap-around.

    op: 'over' (alpha blend, needs alpha), 'max', 'add', 'min', 'mul'.
    """
    h, w = sprite.shape[:2]
    n_y, n_x = canvas.shape[:2]
    ys = (np.arange(h) + int(round(cy)) - h // 2) % n_y
    xs = (np.arange(w) + int(round(cx)) - w // 2) % n_x
    ix = np.ix_(ys, xs)
    region = canvas[ix]
    if op == "over":
        a = alpha if sprite.ndim == alpha.ndim else alpha[..., None]
        canvas[ix] = region * (1.0 - a) + sprite * a
    elif op == "max":
        canvas[ix] = np.maximum(region, sprite)
    elif op == "min":
        canvas[ix] = np.minimum(region, sprite)
    elif op == "add":
        canvas[ix] = region + sprite
    elif op == "mul":
        canvas[ix] = region * sprite
    return ix


def wrap_offsets(xs, ys, size):
    """Offsets (ox, oy) needed so that a shape with coords xs/ys covers the torus correctly."""
    xs, ys = np.asarray(xs), np.asarray(ys)
    oxs = [0]
    oys = [0]
    if xs.min() < 0:
        oxs.append(size)
    if xs.max() >= size:
        oxs.append(-size)
    if ys.min() < 0:
        oys.append(size)
    if ys.max() >= size:
        oys.append(-size)
    return [(ox, oy) for ox in oxs for oy in oys]


def soft_disc(radius, sharp=0.6, pad=1):
    """Square sprite with a soft round falloff (0..1)."""
    r = int(np.ceil(radius)) + pad
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    d = np.sqrt(yy * yy + xx * xx) / max(radius, 1e-6)
    return smoothstep(1.0, sharp, d)


def dome(radius, power=1.0):
    r = int(np.ceil(radius)) + 1
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    d = np.clip(1.0 - (yy * yy + xx * xx) / (radius * radius), 0, 1)
    return d ** (0.5 * power)
