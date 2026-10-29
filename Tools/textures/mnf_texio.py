"""mnf_texio - colour, packing, drawing and preview helpers for the MNF texture pipeline."""
from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

import mnf_noise as mn

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation",
             "/usr/share/fonts/truetype/freefont"]


# --------------------------------------------------------------------------- colour
def rgb(*c):
    """sRGB 0..255 tuple -> float array 0..1."""
    if len(c) == 1:
        c = c[0]
    return np.array(c, dtype=np.float64) / 255.0


def gradient_map(t, stops):
    """Map scalar field t (0..1) through colour stops [(pos, (r,g,b) 0..255), ...]."""
    pos = np.array([s[0] for s in stops], dtype=np.float64)
    cols = np.array([s[1] for s in stops], dtype=np.float64) / 255.0
    out = np.empty(t.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(t, pos, cols[:, c])
    return out


def mix(a, b, t):
    """Blend colour/array a -> b by mask t (broadcast over channels)."""
    if np.ndim(t) == np.ndim(a) - 1 or (np.ndim(t) == 2 and np.ndim(a) == 3):
        t = t[..., None]
    return a + (b - a) * t


def solid(size, col):
    return np.ones((size, size, 3)) * rgb(col)


def tint_var(base, amount, seed, freq=4, size=None):
    """Multiply colour by low-frequency per-channel variation (subtle hue shifts)."""
    size = size or base.shape[0]
    v = np.stack([mn.fbm(size, freq, 4, seed + c) - 0.5 for c in range(3)], -1)
    return np.clip(base * (1.0 + v * amount), 0, 1)


def luminance(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def desaturate(c, amt):
    l = luminance(c)[..., None]
    return c + (l - c) * amt


def srgb_to_lin(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def clamp_albedo(c, lo=0.02, hi=0.94):
    """Keep albedo inside a physically plausible range (sRGB)."""
    return np.clip(c, lo, hi)


# --------------------------------------------------------------------------- packing
def to8(a):
    return (np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def encode_normal(n):
    return to8(n * 0.5 + 0.5)


def pack_mask(metal, ao, height, smooth, size):
    def full(v):
        return np.full((size, size), float(v)) if np.isscalar(v) else v
    return np.stack([full(metal), full(ao), full(height), full(smooth)], -1)


def dilate_rgb(rgb_arr, alpha, thresh=0.5):
    """Bleed opaque colour into transparent pixels (prevents dark mip halos on cutouts)."""
    inside = alpha > thresh
    if inside.all() or not inside.any():
        return rgb_arr
    _, (iy, ix) = ndimage.distance_transform_edt(~inside, return_indices=True)
    out = rgb_arr[iy, ix]
    # soften the bled colour a bit to an average so large empty areas are not streaky
    avg = rgb_arr[inside].mean(axis=0)
    dist = ndimage.distance_transform_edt(~inside)
    t = np.clip(dist / 24.0, 0, 1)[..., None]
    out = out * (1 - t) + avg * t
    out[inside] = rgb_arr[inside]
    return out


class TexSet:
    """Container for one finished texture set (float arrays 0..1)."""

    def __init__(self, albedo, normal=None, mask=None, emission=None, alpha=None, extra=None):
        self.albedo = albedo
        self.normal = normal
        self.mask = mask
        self.emission = emission
        self.alpha = alpha
        self.extra = extra or {}


def finish(albedo, height, metal=0.0, smooth=0.3, ao=None, nheight=None, nstrength=4.0,
           ao_strength=1.0, ao_radii=(2, 6, 16), emission=None, alpha=None, normal=None, clamp=True):
    """Build a TexSet from albedo + height (+ optional extras).

    height    0..1, stored in mask.B (also drives the normal unless ``nheight`` given).
    ao        extra AO multiplied with height-derived AO.
    """
    size = albedo.shape[0]
    nh = height if nheight is None else nheight
    if normal is None:
        normal = mn.height_to_normal(nh, nstrength)
    hao = mn.ambient_occlusion(height, ao_radii, strength=ao_strength) if ao_strength > 0 else np.ones_like(height)
    if ao is not None:
        hao = hao * ao
    if clamp:
        albedo = clamp_albedo(albedo)
    mask = pack_mask(metal, np.clip(hao, 0, 1), np.clip(height, 0, 1), np.clip(smooth, 0, 1), size)
    return TexSet(albedo, normal, mask, emission, alpha)


def save_png(path, arr8):
    mode = {2: "L", 3: "RGB", 4: "RGBA"}[arr8.shape[2] if arr8.ndim == 3 else 2]
    Image.fromarray(arr8, mode).save(path, optimize=True, compress_level=9)


def write_set(outdir, name, ts: TexSet, normal_only=False):
    """Write <name>_A/_N/_M/_E.png. Returns dict of written file names."""
    files = {}
    if not normal_only:
        alb = ts.albedo
        if ts.alpha is not None:
            alb = dilate_rgb(alb, ts.alpha)
            a8 = np.concatenate([to8(alb), to8(ts.alpha)[..., None]], -1)
        else:
            a8 = to8(alb)
        save_png(os.path.join(outdir, f"{name}_A.png"), a8)
        files["albedo"] = f"{name}_A.png"
    if ts.normal is not None:
        save_png(os.path.join(outdir, f"{name}_N.png"), encode_normal(ts.normal))
        files["normal"] = f"{name}_N.png"
    if ts.mask is not None and not normal_only:
        save_png(os.path.join(outdir, f"{name}_M.png"), quantize_mask(ts.mask))
        files["mask"] = f"{name}_M.png"
    if ts.emission is not None and not normal_only:
        save_png(os.path.join(outdir, f"{name}_E.png"), to8(ts.emission))
        files["emission"] = f"{name}_E.png"
    return files


def quantize_mask(mask):
    return to8(mask)


# --------------------------------------------------------------------------- PIL drawing helpers
def font(size, bold=True, name=None):
    cands = [name] if name else (["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "FreeSansBold.ttf"] if bold
                                 else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    for d in FONT_DIRS:
        for c in cands:
            p = os.path.join(d, c)
            if c and os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


class WrapCanvas:
    """PIL drawing surface that wraps shapes across a tileable (supersampled) square."""

    def __init__(self, size, ss=2, mode="L", fill=0):
        self.size, self.ss = size, ss
        self.W = size * ss
        self.img = Image.new(mode, (self.W, self.W), fill)
        self.draw = ImageDraw.Draw(self.img)

    def _offs(self, pts):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return mn.wrap_offsets(xs, ys, self.W)

    def polygon(self, pts, fill):
        """pts in tile units (0..1)."""
        P = [(x * self.W, y * self.W) for x, y in pts]
        for ox, oy in self._offs(P):
            self.draw.polygon([(x + ox, y + oy) for x, y in P], fill=fill)

    def line(self, pts, fill, width):
        P = [(x * self.W, y * self.W) for x, y in pts]
        w = max(1, int(round(width * self.ss)))
        for ox, oy in self._offs(P):
            self.draw.line([(x + ox, y + oy) for x, y in P], fill=fill, width=w, joint="curve")

    def ellipse(self, cx, cy, rx, ry, fill):
        P = [((cx - rx) * self.W, (cy - ry) * self.W), ((cx + rx) * self.W, (cy + ry) * self.W)]
        for ox, oy in self._offs(P):
            self.draw.ellipse([P[0][0] + ox, P[0][1] + oy, P[1][0] + ox, P[1][1] + oy], fill=fill)

    def array(self):
        a = np.asarray(self.img, dtype=np.float64) / 255.0
        return mn.downsample(a, self.ss)


def taper_polygon(path, w0, w1):
    """Polygon outline around a polyline ``path`` (N,2) tapering width w0 -> w1."""
    path = np.asarray(path, dtype=np.float64)
    n = len(path)
    d = np.gradient(path, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-12
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    w = np.linspace(w0, w1, n)[:, None] * 0.5
    left = path + nrm * w
    right = path - nrm * w
    return np.concatenate([left, right[::-1]], 0)


# --------------------------------------------------------------------------- fur strands
def draw_strands(size, roots, dirs_fn, length, width, colour_fn, ss=2, base_rgb=(0, 0, 0), segs=6,
                 curl=0.0, seed=0, height_gain=1.0, wrap=True):
    """Draw tapered hair strands on a tileable RGB + height canvas.

    roots      (n,2) array of (x,y) in tile units.
    dirs_fn    f(x, y) -> (dx, dy) unit flow direction (tile units).
    length     scalar or (n,) strand lengths in tile units.
    width      scalar or (n,) widths in output pixels.
    colour_fn  f(i, t) -> (r,g,b) 0..255 colour for strand i at fraction t (root 0 -> tip 1).
    Returns (rgb float (size,size,3), height float (size,size), coverage float (size,size)).
    """
    W = size * ss
    img = Image.new("RGB", (W, W), tuple(int(c) for c in base_rgb))
    himg = Image.new("L", (W, W), 0)
    cimg = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(img)
    dh = ImageDraw.Draw(himg)
    dc = ImageDraw.Draw(cimg)
    r = mn.rng(seed)
    n = len(roots)
    L = np.broadcast_to(np.asarray(length, dtype=np.float64), (n,))
    Wd = np.broadcast_to(np.asarray(width, dtype=np.float64), (n,))
    for i in range(n):
        x, y = roots[i]
        pts = [(x, y)]
        ang_bias = (r.random() - 0.5) * curl
        step = L[i] / segs
        for s in range(segs):
            dx, dy = dirs_fn(x, y)
            ca, sa = np.cos(ang_bias * (s + 1)), np.sin(ang_bias * (s + 1))
            dx, dy = dx * ca - dy * sa, dx * sa + dy * ca
            x += dx * step
            y += dy * step
            pts.append((x, y))
        P = np.array(pts) * W
        offs = mn.wrap_offsets(P[:, 0], P[:, 1], W) if wrap else [(0, 0)]
        for ox, oy in offs:
            for s in range(segs):
                t = s / segs
                col = colour_fn(i, t)
                w = max(1, int(round(Wd[i] * ss * (1.0 - 0.6 * t))))
                seg = [(P[s, 0] + ox, P[s, 1] + oy), (P[s + 1, 0] + ox, P[s + 1, 1] + oy)]
                d.line(seg, fill=col, width=w)
                hv = int(np.clip((60 + 195 * (0.35 + 0.65 * t)) * height_gain, 0, 255))
                dh.line(seg, fill=hv, width=w)
                dc.line(seg, fill=255, width=w)
    rgb_arr = mn.downsample(np.asarray(img, dtype=np.float64) / 255.0, ss)
    h = mn.downsample(np.asarray(himg, dtype=np.float64) / 255.0, ss)
    cov = mn.downsample(np.asarray(cimg, dtype=np.float64) / 255.0, ss)
    return rgb_arr, h, cov


# --------------------------------------------------------------------------- previews
def shade_preview(albedo, normal, mask, emission=None, alpha=None, light=(-0.55, 0.55, 0.63)):
    """Very small lit preview (flat plane under a raking light) for contact sheets."""
    a = srgb_to_lin(albedo[..., :3])
    n = normal * 2.0 - 1.0
    L = np.array(light, dtype=np.float64)
    L /= np.linalg.norm(L)
    V = np.array([0.0, 0.0, 1.0])
    H = (L + V) / np.linalg.norm(L + V)
    ndl = np.clip((n * L).sum(-1), 0, 1)
    ndh = np.clip((n * H).sum(-1), 0, 1)
    metal, ao, smooth = mask[..., 0], mask[..., 1], mask[..., 3]
    power = 2.0 ** (smooth * 10.0 + 1.0)
    spec = ndh ** power * (power + 2) / 8.0 * ndl
    f0 = 0.04 * (1 - metal)[..., None] + a * metal[..., None]
    diff = a * (1 - metal)[..., None]
    col = diff * (ndl[..., None] * 1.6 + 0.25 * ao[..., None]) + f0 * spec[..., None] * 1.2 \
        + f0 * 0.25 * ao[..., None]
    if emission is not None:
        col = col + srgb_to_lin(emission[..., :3])
    out = lin_to_srgb(col)
    if alpha is not None:
        chk = ((np.indices(alpha.shape).sum(0) // 16) % 2) * 0.15 + 0.35
        out = out * alpha[..., None] + chk[..., None] * (1 - alpha[..., None])
    return out
