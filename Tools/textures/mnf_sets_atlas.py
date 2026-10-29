"""mnf_sets_atlas - signs_atlas (worn industrial signage with real text) and decals_atlas (alpha decals).

Both atlases are 1024x1024, 4x4 cells of 256x256, cell index = row*4 + col, row 0 = top (Docs/ASSET_SPEC.md 2.1/2.2).
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

import mnf_noise as mn
import mnf_texio as tio
from mnf_noise import seed_of, smoothstep
from mnf_registry import texset
from mnf_sets_hard import rust_colour

TAU = 2 * np.pi
CELL = 256
SS = 2                  # supersampling for drawing
CW = CELL * SS          # drawing resolution of one cell


# =========================================================================== text / shape helpers
def text_mask(text, box_w, box_h, font_name="DejaVuSans-Bold.ttf", min_squeeze=0.72, line_gap=0.18,
              align="center"):
    """Render (multi-line) text as an 'L' mask fitted into box_w x box_h (pixels).

    The text is rendered large, cropped to its ink, then scaled uniformly to fit; if it is too wide it may be
    horizontally condensed down to ``min_squeeze`` before shrinking further.
    """
    f = tio.font(200, name=font_name)
    lines = text.split("\n")
    imgs = []
    for ln in lines:
        bb = f.getbbox(ln)
        im = Image.new("L", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), 0)
        ImageDraw.Draw(im).text((10 - bb[0], 10 - bb[1]), ln, font=f, fill=255)
        im = im.crop(im.getbbox())
        imgs.append(im)
    cap_h = max(im.height for im in imgs)
    gap = int(cap_h * line_gap)
    W = max(im.width for im in imgs)
    H = sum(im.height for im in imgs) + gap * (len(imgs) - 1)
    block = Image.new("L", (W, H), 0)
    y = 0
    for im in imgs:
        x = (W - im.width) // 2 if align == "center" else 0
        block.paste(im, (x, y))
        y += im.height + gap
    sy = box_h / H                                  # height-limited scale
    if W * sy <= box_w:
        sx = sy
    elif W * sy * min_squeeze <= box_w:              # condense horizontally to fit
        sx = box_w / W
    else:                                           # condense fully, then shrink both
        sx = box_w / W
        sy = sx / min_squeeze
    out = block.resize((max(1, int(W * sx)), max(1, int(H * sy))), Image.LANCZOS)
    return out


def paste_text(img, hmap, text, box, colour, height_val=None, **kw):
    """Draw fitted text centred in box=(x0,y0,x1,y1) onto RGB img (+ optional height map)."""
    x0, y0, x1, y1 = box
    m = text_mask(text, x1 - x0, y1 - y0, **kw)
    ox = x0 + ((x1 - x0) - m.width) // 2
    oy = y0 + ((y1 - y0) - m.height) // 2
    img.paste(Image.new("RGB", m.size, tuple(colour)), (ox, oy), m)
    if hmap is not None and height_val is not None:
        hmap.paste(Image.new("L", m.size, height_val), (ox, oy), m)
    return (ox, oy, ox + m.width, oy + m.height)


def arrow_poly(cx, cy, length, width, direction):
    """Bold arrow polygon; direction in {'right','left','up','down'}."""
    hl = length * 0.42                  # head length
    hw = width * 1.0                    # head half-width
    sw = width * 0.38                   # shaft half-width
    pts = [(-length / 2, -sw), (length / 2 - hl, -sw), (length / 2 - hl, -hw), (length / 2, 0),
           (length / 2 - hl, hw), (length / 2 - hl, sw), (-length / 2, sw)]
    rot = {"right": 0, "down": np.pi / 2, "left": np.pi, "up": -np.pi / 2}[direction]
    c, s = np.cos(rot), np.sin(rot)
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


class SignCell:
    def __init__(self, bg, kind="metal", seed=0):
        self.img = Image.new("RGB", (CW, CW), tuple(bg))
        self.h = Image.new("L", (CW, CW), 128)
        self.d = ImageDraw.Draw(self.img)
        self.dh = ImageDraw.Draw(self.h)
        self.kind = kind
        self.seed = seed
        self.bolts = []

    def rect(self, box, col, hv=None, radius=0):
        if radius:
            self.d.rounded_rectangle(box, radius=radius, fill=tuple(col))
            if hv is not None:
                self.dh.rounded_rectangle(box, radius=radius, fill=hv)
        else:
            self.d.rectangle(box, fill=tuple(col))
            if hv is not None:
                self.dh.rectangle(box, fill=hv)

    def border(self, inset, width, col, radius=18):
        self.d.rounded_rectangle([inset, inset, CW - inset, CW - inset], radius=radius, outline=tuple(col),
                                 width=width)
        self.dh.rounded_rectangle([inset, inset, CW - inset, CW - inset], radius=radius, outline=140, width=width)

    def text(self, t, box, col, hv=134, **kw):
        return paste_text(self.img, self.h, t, box, col, hv, **kw)

    def add_bolts(self, inset=26, r=11):
        for (x, y) in ((inset, inset), (CW - inset, inset), (inset, CW - inset), (CW - inset, CW - inset)):
            self.bolts.append((x, y, r))

    def poly(self, pts, col, hv=None):
        self.d.polygon(pts, fill=tuple(col))
        if hv is not None:
            self.dh.polygon(pts, fill=hv)


# =========================================================================== individual signs
RED, WHITE, BLACK = (168, 34, 30), (216, 212, 200), (26, 25, 24)
YELLOW, GREEN, BLUE = (206, 164, 34), (34, 92, 56), (36, 66, 104)


def sign_danger(s):
    c = SignCell(WHITE, seed=s)
    c.rect([0, 0, CW, 190], BLACK)
    c.rect([40, 30, CW - 40, 160], RED, radius=60)
    c.d.rounded_rectangle([40, 30, CW - 40, 160], radius=60, outline=WHITE, width=6)
    c.text("DANGER", (70, 52, CW - 70, 138), WHITE)
    c.text("AUTHORIZED\nPERSONNEL\nONLY", (44, 218, CW - 44, CW - 40), BLACK, line_gap=0.22)
    c.add_bolts(20, 9)
    return c


def sign_gate(s):
    c = SignCell(WHITE, seed=s)
    c.border(14, 16, RED, 24)
    c.text("KEEP\nGATE\nCLOSED", (60, 64, CW - 60, CW - 64), RED, line_gap=0.2)
    c.add_bolts(30, 10)
    return c


def sign_bunker(s):
    c = SignCell(GREEN, seed=s)
    c.border(16, 8, (200, 204, 190), 16)
    c.text("SURVIVOR\nBUNKER", (50, 44, CW - 50, 210), (214, 214, 198), line_gap=0.2)
    c.text("7", (150, 228, CW - 150, CW - 50), (214, 214, 198))
    c.add_bolts(30, 10)
    return c


def sign_mine_access(s):
    c = SignCell(YELLOW, seed=s)
    c.border(14, 10, BLACK, 12)
    c.text("MINE\nACCESS", (46, 50, CW - 46, 300), BLACK, line_gap=0.18)
    c.poly(arrow_poly(CW / 2, 400, 330, 70, "right"), BLACK, 136)
    c.add_bolts(28, 10)
    return c


def sign_high_voltage(s):
    c = SignCell(YELLOW, seed=s)
    c.border(14, 10, BLACK, 12)
    tri = [(CW / 2, 40), (CW / 2 + 150, 300), (CW / 2 - 150, 300)]
    c.poly(tri, BLACK, 136)
    tri_in = [(CW / 2, 84), (CW / 2 + 112, 278), (CW / 2 - 112, 278)]
    c.poly(tri_in, YELLOW)
    bolt = [(CW / 2 + 16, 116), (CW / 2 - 34, 206), (CW / 2 - 2, 206), (CW / 2 - 22, 270), (CW / 2 + 36, 182),
            (CW / 2 + 4, 182), (CW / 2 + 24, 116)]
    c.poly(bolt, BLACK, 136)
    c.text("HIGH\nVOLTAGE", (44, 322, CW - 44, CW - 40), BLACK, line_gap=0.16)
    c.add_bolts(26, 9)
    return c


def sign_level(s, n):
    c = SignCell(BLUE, seed=s)
    c.border(16, 8, (196, 200, 204), 14)
    c.text("LEVEL", (60, 56, CW - 60, 170), (214, 216, 214))
    c.text(str(n), (150, 196, CW - 150, CW - 60), (214, 216, 214))
    c.add_bolts(30, 10)
    return c


def sign_level3(s):
    c = SignCell(RED, seed=s)
    c.border(16, 8, WHITE, 14)
    c.text("LEVEL 3", (50, 50, CW - 50, 200), WHITE)
    c.rect([40, 232, CW - 40, 250], WHITE, 136)
    c.text("NO\nENTRY", (70, 278, CW - 70, CW - 50), WHITE, line_gap=0.16)
    c.add_bolts(26, 9)
    return c


def sign_evac(s):
    c = SignCell(GREEN, seed=s)
    c.border(14, 8, (210, 214, 200), 14)
    c.text("EVACUATION\nROUTE", (40, 56, CW - 40, 270), (220, 222, 210), line_gap=0.2)
    c.poly(arrow_poly(CW / 2, 384, 340, 72, "left"), (220, 222, 210), 136)
    c.add_bolts(26, 9)
    return c


def sign_word(s, words, bg, fg, border=None, kind="metal"):
    c = SignCell(bg, kind=kind, seed=s)
    if border:
        c.border(16, 8, border, 14)
    c.text(words, (50, 120, CW - 50, CW - 120), fg, line_gap=0.25)
    c.add_bolts(30, 10)
    return c


def sign_missing(s):
    r = mn.rng(seed_of("missing", s))
    c = SignCell((196, 188, 160), kind="paper", seed=s)
    c.text("MISSING", (30, 22, CW - 30, 112), (30, 28, 26))
    # photo box with a crude photocopied monkey portrait
    px0, py0, px1, py1 = 110, 128, CW - 110, 352
    c.rect([px0, py0, px1, py1], (60, 58, 54))
    ph = Image.new("L", (px1 - px0, py1 - py0), 150)
    d = ImageDraw.Draw(ph)
    w, h = ph.size
    d.ellipse([w * 0.08, h * 0.30, w * 0.28, h * 0.52], fill=70)            # ears
    d.ellipse([w * 0.72, h * 0.30, w * 0.92, h * 0.52], fill=70)
    d.ellipse([w * 0.12, h * 0.1, w * 0.88, h * 0.95], fill=60)             # head
    d.ellipse([w * 0.24, h * 0.36, w * 0.76, h * 0.9], fill=176)            # face
    d.ellipse([w * 0.3, h * 0.24, w * 0.7, h * 0.52], fill=170)
    d.ellipse([w * 0.33, h * 0.4, w * 0.45, h * 0.5], fill=20)              # eyes
    d.ellipse([w * 0.55, h * 0.4, w * 0.67, h * 0.5], fill=20)
    d.ellipse([w * 0.37, h * 0.42, w * 0.41, h * 0.46], fill=210)
    d.ellipse([w * 0.59, h * 0.42, w * 0.63, h * 0.46], fill=210)
    d.ellipse([w * 0.44, h * 0.6, w * 0.48, h * 0.64], fill=60)             # nostrils
    d.ellipse([w * 0.52, h * 0.6, w * 0.56, h * 0.64], fill=60)
    d.line([(w * 0.4, h * 0.75), (w * 0.6, h * 0.76)], fill=40, width=4)               # flat mouth
    d.rectangle([0, 0, w, h * 0.12], fill=90)                                         # dark photo top
    pa = np.asarray(ph, dtype=np.float64) / 255.0
    pa = ndimage.gaussian_filter(pa, 2.2)
    pa = pa * (0.75 + 0.5 * mn.fbm(pa.shape[0], 6, 3, 77)[:pa.shape[0], :pa.shape[1]]) if pa.shape[0] == pa.shape[1] \
        else pa
    pa = pa + (r.random(pa.shape) - 0.5) * 0.35
    pa = pa * (1 - 0.35 * (np.arange(pa.shape[1])[None, :] / pa.shape[1]))             # uneven copier toner
    pa = np.clip((pa - 0.35) * 1.8 + 0.35, 0, 1)                           # harsh photocopy contrast
    ph = Image.fromarray((pa * 255).astype(np.uint8)).convert("RGB").resize((w - 12, h - 12), Image.LANCZOS)
    c.img.paste(ph, (px0 + 6, py0 + 6))
    c.text("HAVE YOU SEEN\nTHIS MONKEY?", (36, 366, CW - 36, 440), (30, 28, 26), line_gap=0.2)
    # tear-off phone tabs
    for i in range(8):
        x0 = 20 + i * ((CW - 40) / 8)
        c.d.line([(x0, 452), (x0, CW - 6)], fill=(150, 142, 118), width=2)
        tab = Image.new("L", (56, 14), 0)
        ImageDraw.Draw(tab).text((0, 0), "555-0137", font=tio.font(12), fill=255)
        tab = tab.rotate(90, expand=True)
        c.img.paste(Image.new("RGB", tab.size, (40, 38, 36)), (int(x0 + 16), 460), tab)
    # tape corners
    for (x, y, a) in ((10, 0, 0.3), (CW - 80, 0, -0.3)):
        c.rect([x, y, x + 70, y + 26], (200, 196, 170))
    return c


def sign_scrawl(s):
    r = mn.rng(seed_of("scrawl", s))
    c = SignCell((96, 96, 92), kind="concrete", seed=s)
    lines = ["DO NOT", "FOLLOW", "THE", "LIGHT"]
    ink = Image.new("L", (CW, CW), 0)
    di = ImageDraw.Draw(ink)
    y = 40
    for li, ln in enumerate(lines):
        size = int(r.uniform(88, 104)) if li != 2 else 70
        f = tio.font(size, name="DejaVuSans-Bold.ttf")
        widths = [f.getbbox(ch)[2] - f.getbbox(ch)[0] + 8 for ch in ln]
        x = (CW - sum(widths)) / 2 + r.uniform(-20, 20)
        for ch, wdt in zip(ln, widths):
            g = Image.new("L", (size * 2, size * 2), 0)
            ImageDraw.Draw(g).text((size * 0.4, size * 0.2), ch, font=f, fill=255)
            g = g.rotate(r.uniform(-12, 12), resample=Image.BICUBIC)
            ink.paste(255, (int(x - size * 0.4 + r.uniform(-4, 4)), int(y + r.uniform(-8, 8) - size * 0.2)), g)
            x += wdt * r.uniform(0.95, 1.1)
        y += size * 1.12
    a = np.asarray(ink, dtype=np.float64) / 255.0
    wy, wx = mn.warp_field(CW, 8, 5, seed_of("scrawl", "w"))
    a = mn.warp(a, wy, wx)
    a = ndimage.grey_dilation(a, size=(5, 5)) * 0.6 + a * 0.4
    # drips running down from the bottom of strokes
    drips = np.zeros_like(a)
    cols = r.choice(CW, 40, replace=False)
    for x in cols:
        ys = np.nonzero(a[:, x] > 0.5)[0]
        if len(ys) == 0:
            continue
        y0 = ys[r.integers(len(ys))]
        L = int(r.uniform(15, 90))
        w = int(r.integers(2, 5))
        drips[y0:min(CW, y0 + L), max(0, x - w // 2):x + w // 2 + 1] = 1.0
        yy_end = min(CW - 1, y0 + L)
        drips[max(0, yy_end - 4):yy_end + 1, max(0, x - w):x + w + 1] = 1.0
    a = np.clip(a + ndimage.gaussian_filter(drips, 0.8), 0, 1)
    rough = mn.fbm(CW, 32, 3, seed_of("scrawl", "r"))
    a = a * smoothstep(0.15, 0.45, rough + 0.3 * a)
    paint = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    c.img.paste(Image.new("RGB", (CW, CW), (84, 18, 14)), (0, 0), paint)
    c.h.paste(Image.new("L", (CW, CW), 132), (0, 0), paint)
    return c


def sign_marker(s):
    c = SignCell((30, 30, 28), seed=s)
    c.rect([34, 34, CW - 34, CW - 34], YELLOW, 134, radius=20)
    c.d.rounded_rectangle([60, 60, CW - 60, CW - 60], radius=14, outline=BLACK, width=10)
    c.text("03", (100, 120, CW - 100, CW - 120), BLACK, font_name="DejaVuSansMono-Bold.ttf")
    c.add_bolts(18, 8)
    return c


def sign_trail(s):
    r = mn.rng(seed_of("trail", s))
    c = SignCell((92, 70, 48), kind="wood", seed=s)
    # three horizontal boards
    for i in range(3):
        y0 = 40 + i * 150
        c.rect([8, y0, CW - 8, y0 + 140], (int(96 + r.uniform(-10, 10)), int(74 + r.uniform(-8, 8)),
                                           int(50 + r.uniform(-6, 6))), 140)
        c.d.line([(8, y0 + 140), (CW - 8, y0 + 140)], fill=(30, 22, 16), width=6)
        c.dh.line([(8, y0 + 140), (CW - 8, y0 + 140)], fill=60, width=6)
    c.rect([0, 0, CW, 40], (40, 32, 26), 60)
    c.rect([0, CW - 22, CW, CW], (40, 32, 26), 60)
    c.text("MINE", (80, 62, CW - 80, 172), (214, 206, 182), hv=120)
    c.text("400m", (90, 210, CW - 90, 322), (214, 206, 182), hv=120)
    c.poly(arrow_poly(CW / 2, 404, 120, 50, "up"), (214, 206, 182), 120)
    for (x, y) in ((40, 110), (CW - 40, 110), (40, 260), (CW - 40, 260), (40, 410), (CW - 40, 410)):
        c.bolts.append((x, y, 9))
    return c


SIGNS = [
    lambda: sign_danger(0), lambda: sign_gate(1), lambda: sign_bunker(2), lambda: sign_mine_access(3),
    lambda: sign_high_voltage(4), lambda: sign_level(5, 1), lambda: sign_level(6, 2), lambda: sign_level3(7),
    lambda: sign_evac(8),
    lambda: sign_word(9, "ASSAY\n/\nTRADE", (120, 92, 56), (232, 220, 196), (228, 214, 186)),
    lambda: sign_word(10, "EQUIPMENT", (82, 88, 92), (222, 222, 214), (212, 212, 204)),
    lambda: sign_word(11, "STORAGE", (82, 88, 92), (222, 222, 214), (212, 212, 204)),
    lambda: sign_missing(12), lambda: sign_scrawl(13), lambda: sign_marker(14), lambda: sign_trail(15),
]


def _wear_cell(c: SignCell, idx):
    """Downsample a drawn cell and apply fading, dirt, scratches, rust, chips. Returns float layers."""
    rgb = np.asarray(c.img, dtype=np.float64) / 255.0
    h = np.asarray(c.h, dtype=np.float64) / 255.0
    rgb = mn.downsample(rgb, SS)
    h = mn.downsample(h, SS)
    S = CELL
    sd = seed_of("sign", idx)
    yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
    edge = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    n1 = mn.fbm(S, 4, 5, sd + 1)
    n2 = mn.fbm(S, 16, 4, sd + 2)
    n3 = mn.fbm(S, 48, 3, sd + 3)
    metal = np.zeros((S, S))
    smooth = np.full((S, S), 0.32)
    grime = np.clip(smoothstep(0.35, 0.95, n1 * 0.7 + n2 * 0.3) * 0.5 + smoothstep(0.4, 1.0, yy) * 0.35, 0, 1)
    if c.kind == "metal":
        # sun / age fade towards a chalky desaturated tone
        fade = smoothstep(0.2, 0.9, n1) * 0.4 + 0.18
        rgb = tio.mix(rgb, tio.desaturate(rgb, 0.6) * 0.9 + 0.08, fade)
        # paint chips concentrated on edges and around bolts
        bolt_d = np.full((S, S), 9.0)
        for (bx, by, br) in c.bolts:
            bolt_d = np.minimum(bolt_d, np.sqrt((xx - bx / CW) ** 2 + (yy - by / CW) ** 2))
        chip_f = n3 * 0.4 + n2 * 0.6 + smoothstep(0.08, 0.0, edge) * 0.5 + smoothstep(0.09, 0.03, bolt_d) * 0.35
        chip = smoothstep(0.8, 0.82, chip_f)
        rust_amt = smoothstep(0.5, 0.8, n2) * 0.5 + 0.5
        under = tio.mix(np.ones((S, S, 3)) * tio.rgb(110, 110, 108), rust_colour(S, sd + 5), rust_amt)
        rgb = tio.mix(rgb, under, chip)
        # scratches
        r = mn.rng(sd + 7)
        cv = Image.new("L", (S * 2, S * 2), 0)
        dcv = ImageDraw.Draw(cv)
        for _ in range(int(r.integers(25, 60))):
            x0, y0 = r.random(2) * S * 2
            a = r.uniform(0, np.pi)
            L = r.uniform(10, 80)
            dcv.line([(x0, y0), (x0 + np.cos(a) * L, y0 + np.sin(a) * L)], fill=int(r.uniform(120, 255)),
                     width=int(r.integers(1, 3)))
        scr = mn.downsample(np.asarray(cv, dtype=np.float64) / 255.0, 2)
        rgb = tio.mix(rgb, tio.rgb(150, 148, 144), scr * 0.6)
        # rust streaks bleeding down from bolts and chips
        src = np.zeros((S, S))
        for (bx, by, br) in c.bolts:
            src = np.maximum(src, smoothstep(br / CW * 1.6, 0, np.sqrt((xx - bx / CW) ** 2 + (yy - by / CW) ** 2)))
        src = np.maximum(src, chip * rust_amt * 0.5)
        run = np.zeros_like(src)
        for k in range(1, 70, 2):
            run += np.roll(src, k, axis=0) * np.exp(-k / 26.0) * (np.arange(S)[:, None] >= k)
        streak_mod = mn.fbm(S, (4, 40), 3, sd + 9)
        run = np.clip(run / 6.0, 0, 1) * smoothstep(0.3, 0.7, streak_mod)
        rgb = tio.mix(rgb, tio.rgb(110, 62, 34), run * 0.6)
        # bolts
        for (bx, by, br) in c.bolts:
            d = np.sqrt((xx - bx / CW) ** 2 + (yy - by / CW) ** 2) * S
            rr = br / SS
            dome = np.sqrt(np.clip(1 - (d / rr) ** 2, 0, 1))
            m = d < rr
            bc = tio.mix(np.ones((S, S, 3)) * tio.rgb(84, 82, 80), rust_colour(S, sd + 11), 0.6)
            rgb = np.where(m[..., None], bc * (0.6 + 0.5 * dome)[..., None], rgb)
            h = np.where(m, 0.6 + 0.3 * dome, h)
            metal = np.where(m, 0.5, metal)
        metal = np.maximum(metal, chip * (1 - rust_amt) * 0.9 + scr * 0.5)
        h = h - 0.04 * chip - 0.02 * scr
        smooth = 0.38 - 0.15 * fade - 0.2 * chip * rust_amt - 0.12 * grime + 0.1 * scr
        rgb = rgb * (1 - 0.35 * grime)[..., None]
    elif c.kind == "paper":
        fade = smoothstep(0.2, 0.9, n1) * 0.25
        rgb = tio.mix(rgb, tio.rgb(196, 188, 160), fade)
        stain, rim = (smoothstep(0.62, 0.7, mn.warped_fbm(S, 3, 5, sd + 4, warp_amt=0.1)), None)
        rgb = tio.mix(rgb, tio.rgb(150, 124, 80), stain * 0.35)
        fold = smoothstep(0.006, 0.0, np.abs(yy - 0.47)) + smoothstep(0.006, 0.0, np.abs(xx - 0.5))
        rgb = rgb * (1 - 0.15 * np.clip(fold, 0, 1))[..., None]
        streak = mn.fbm(S, (3, 30), 3, sd + 6)
        rgb = rgb * (1 - 0.25 * smoothstep(0.55, 0.9, streak) * smoothstep(0.7, 0.0, yy))[..., None]   # water runs
        # torn bottom-right corner + ragged tabs (darken = wall behind)
        torn = (xx + (1 - yy) < 0.22 + 0.03 * n3) | ((yy > 0.88) & (n3 > 0.62))
        rgb = np.where(torn[..., None], tio.rgb(70, 70, 66) * (0.8 + 0.3 * n2)[..., None], rgb)
        h = h + 0.03 * (n3 - 0.5) - 0.03 * np.clip(fold, 0, 1) - 0.1 * torn
        smooth = np.full((S, S), 0.12) + 0.05 * stain
        rgb = rgb * (1 - 0.25 * grime)[..., None]
    elif c.kind == "wood":
        grain = 0.5 + 0.5 * np.sin(TAU * (yy * 60 + 2.0 * mn.fbm(S, (1, 3), 3, sd + 4)))
        fib = mn.fbm(S, (96, 4), 3, sd + 5)
        rgb = rgb * (0.82 + 0.12 * grain + 0.15 * (fib - 0.5))[..., None]
        flake = smoothstep(0.6, 0.65, n3 * 0.6 + n2 * 0.4)
        bright = tio.luminance(rgb) > 0.5
        rgb = np.where((bright & (flake > 0.5))[..., None], rgb * 0.5 + tio.rgb(46, 34, 24), rgb)
        h = h + 0.05 * (grain - 0.5) + 0.04 * (fib - 0.5)
        for (bx, by, br) in c.bolts:
            d = np.sqrt((xx - bx / CW) ** 2 + (yy - by / CW) ** 2) * S
            m = d < br / SS
            rgb = np.where(m[..., None], tio.rgb(60, 58, 56), rgb)
            metal = np.where(m, 0.6, metal)
        smooth = np.full((S, S), 0.16) + 0.04 * fib
        rgb = rgb * (1 - 0.3 * grime)[..., None]
    else:  # concrete
        conc = tio.gradient_map(np.clip(n2 * 0.6 + n3 * 0.4, 0, 1), [(0, (70, 72, 70)), (1, (112, 112, 106))])
        is_paint = (rgb[..., 0] - rgb[..., 1] > 0.12).astype(float)
        rgb = tio.mix(conc, rgb, ndimage.gaussian_filter(is_paint, 0.5))
        pores = smoothstep(0.92, 0.98, mn.value(S, 128, sd + 8))
        rgb = rgb * (1 - 0.4 * pores)[..., None]
        h = 0.5 + 0.05 * (n2 - 0.5) + 0.03 * (n3 - 0.5) - 0.1 * pores + 0.01 * is_paint
        smooth = 0.2 + 0.2 * is_paint
        rgb = rgb * (1 - 0.3 * grime)[..., None]
    return np.clip(rgb, 0, 1), np.clip(h, 0, 1), np.clip(metal, 0, 1), np.clip(smooth, 0.03, 0.9)


@texset("signs_atlas", None, size=1024, notes="4x4 sign atlas (256px cells, index=row*4+col, row 0 top): "
        "0 DANGER/AUTHORIZED PERSONNEL ONLY, 1 KEEP GATE CLOSED, 2 SURVIVOR BUNKER 7, 3 MINE ACCESS ->, "
        "4 HIGH VOLTAGE, 5 LEVEL 1, 6 LEVEL 2, 7 LEVEL 3 - NO ENTRY, 8 EVACUATION ROUTE <-, 9 ASSAY / TRADE, "
        "10 EQUIPMENT, 11 STORAGE, 12 MISSING poster, 13 DO NOT FOLLOW THE LIGHT (scrawl), 14 marker 03, "
        "15 trail sign MINE 400m ^. Opaque.")
def signs_atlas(S):
    A = np.zeros((S, S, 3))
    H = np.zeros((S, S))
    Mt = np.zeros((S, S))
    Sm = np.zeros((S, S))
    for i, fn in enumerate(SIGNS):
        cell = fn()
        rgb, h, metal, smooth = _wear_cell(cell, i)
        r0, c0 = (i // 4) * CELL, (i % 4) * CELL
        A[r0:r0 + CELL, c0:c0 + CELL] = rgb
        H[r0:r0 + CELL, c0:c0 + CELL] = h
        Mt[r0:r0 + CELL, c0:c0 + CELL] = metal
        Sm[r0:r0 + CELL, c0:c0 + CELL] = smooth
    # per-cell normals (no bleeding across cell borders)
    N = np.zeros((S, S, 3))
    AO = np.ones((S, S))
    for i in range(16):
        r0, c0 = (i // 4) * CELL, (i % 4) * CELL
        hc = H[r0:r0 + CELL, c0:c0 + CELL]
        gx = ndimage.sobel(hc, axis=1, mode="nearest") / 8.0
        gy = ndimage.sobel(hc, axis=0, mode="nearest") / 8.0
        n = np.stack([-gx * 6.0, gy * 6.0, np.ones_like(hc)], -1)
        N[r0:r0 + CELL, c0:c0 + CELL] = n / np.linalg.norm(n, axis=-1, keepdims=True)
        AO[r0:r0 + CELL, c0:c0 + CELL] = np.clip(1 - np.clip(ndimage.gaussian_filter(hc, 3, mode="nearest") - hc,
                                                             0, None) * 6, 0.4, 1)
    A = A * (0.8 + 0.2 * AO)[..., None]
    mask = tio.pack_mask(Mt, AO, H, Sm, S)
    return tio.TexSet(tio.clamp_albedo(A, 0.03, 0.92), N, mask)


# =========================================================================== decals
def _soft_window(S, margin=0.08):
    yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
    e = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    return smoothstep(0.0, margin, e)


def _radial_fall(S, rx=0.42, ry=0.42, cx=0.5, cy=0.5, sharp=0.5, warp=0.0, seed=0):
    yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    if warp:
        d = d + (mn.fbm(S, 4, 4, seed) - 0.5) * warp
    return smoothstep(1.0, sharp, d)


def _strokes(S, strokes, ss=4, blur=0.0):
    """Rasterise [(pts(list of (x,y) 0..1), width_px, value)] to a float mask."""
    im = Image.new("L", (S * ss, S * ss), 0)
    d = ImageDraw.Draw(im)
    for pts, w, v in strokes:
        d.line([(x * S * ss, y * S * ss) for x, y in pts], fill=int(255 * v), width=max(1, int(w * ss)),
               joint="curve")
    a = mn.downsample(np.asarray(im, dtype=np.float64) / 255.0, ss)
    return ndimage.gaussian_filter(a, blur) if blur else a


def _polys(S, polys, ss=4):
    im = Image.new("L", (S * ss, S * ss), 0)
    d = ImageDraw.Draw(im)
    for pts, v in polys:
        d.polygon([(x * S * ss, y * S * ss) for x, y in pts], fill=int(255 * v))
    return mn.downsample(np.asarray(im, dtype=np.float64) / 255.0, ss)


def _ellipse_poly(cx, cy, rx, ry, ang=0.0, n=28, jitter=0.0, r=None):
    pts = []
    for t in np.linspace(0, TAU, n, endpoint=False):
        j = 1 + (r.random() - 0.5) * jitter if r is not None else 1
        x, y = np.cos(t) * rx * j, np.sin(t) * ry * j
        pts.append((cx + x * np.cos(ang) - y * np.sin(ang), cy + x * np.sin(ang) + y * np.cos(ang)))
    return pts


def decal_cells():
    S = CELL
    out = []
    yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
    win = _soft_window(S)

    def N(freq, oc, *k):
        return mn.fbm(S, freq, oc, seed_of("decal", *k))

    # 0 crack
    rc = mn.rng(seed_of("decal", "crackwalk"))
    strokes = []

    def walk(p, ang, width, steps, depth):
        pts = [tuple(p)]
        a0 = ang
        for k in range(steps):
            ang += rc.normal(0, 0.28) + (a0 - ang) * 0.35          # jagged but keeps its heading
            p = p + np.array([np.cos(ang), np.sin(ang)]) * rc.uniform(0.008, 0.02)
            pts.append(tuple(p))
            w = width * (1 - k / steps) + 0.6
            strokes.append(([pts[-2], pts[-1]], w, 1.0))
            if depth < 2 and rc.random() < 0.08:
                walk(p.copy(), ang + rc.choice([-1, 1]) * rc.uniform(0.4, 0.9), w * 0.6, int(steps * 0.45), depth + 1)
    for ang in (rc.uniform(-0.5, -0.2), np.pi + rc.uniform(-0.3, 0.1), rc.uniform(1.3, 1.8)):
        walk(np.array([0.5, 0.48]), ang, 3.2, 30 if abs(np.sin(ang)) < 0.5 else 22, 0)
    cr = _strokes(S, strokes, blur=0.5)
    a = np.clip(cr + ndimage.gaussian_filter(cr, 2.5) * 0.35, 0, 1) * _radial_fall(S, 0.47, 0.47, sharp=0.3)
    out.append(dict(rgb=np.ones((S, S, 3)) * tio.rgb(22, 21, 20), a=a, h=0.5 - 0.4 * a, sm=0.2))
    # 1 water stain streaks
    st = mn.fbm(S, (3, 26), 4, seed_of("decal", "ws"))
    st2 = mn.fbm(S, (6, 60), 3, seed_of("decal", "ws2"))
    length = 0.45 + 0.5 * mn.fbm(S, (1, 8), 2, seed_of("decal", "wl"))
    vert = smoothstep(length, 0.05, yy) * smoothstep(0.0, 0.08, yy)
    a = np.clip(smoothstep(0.3, 0.7, st * 0.7 + st2 * 0.3) * vert * 0.95 + smoothstep(0.12, 0.05, np.abs(yy - 0.1))
                * 0.35, 0, 1) * smoothstep(0.0, 0.15, xx) * smoothstep(1.0, 0.85, xx)
    out.append(dict(rgb=np.ones((S, S, 3)) * tio.rgb(54, 46, 36), a=a, h=0.5 + 0.0 * a, sm=0.55))
    # 2 grime patch
    g = mn.warped_fbm(S, 4, 6, seed_of("decal", "grime"), warp_amt=0.1)
    a = np.clip(smoothstep(0.2, 0.7, g) * _radial_fall(S, 0.46, 0.42, sharp=0.0, warp=0.5, seed=2) * 1.3, 0, 0.95)
    rgb = tio.gradient_map(N(16, 4, "gc"), [(0, (26, 23, 20)), (1, (54, 47, 39))])
    out.append(dict(rgb=rgb, a=a, h=0.5 + 0.02 * a, sm=0.18))
    # 3 oil stain
    base = _radial_fall(S, 0.36, 0.3, sharp=0.6, warp=0.45, seed=3)
    rings = 0.5 + 0.5 * np.sin(base * 18)
    a = np.clip(base * 0.9 + smoothstep(0.02, 0.1, base) * (1 - base) * 0.4 * rings, 0, 1)
    for k in range(6):
        cx, cy = mn.rng(seed_of("oil", k)).uniform(0.15, 0.85, 2)
        a = np.maximum(a, _radial_fall(S, 0.04, 0.035, cx, cy, sharp=0.4))
    rgb = tio.gradient_map(base, [(0, (40, 34, 26)), (1, (14, 12, 10))])
    out.append(dict(rgb=rgb, a=a * win, h=0.5, sm=0.85))

    # 4/5 claw scratches
    def claws(n, deep, seed):
        r = mn.rng(seed)
        strokes_core, strokes_rim = [], []
        for i in range(n):
            off = (i - (n - 1) / 2) * 0.13
            p0 = np.array([0.22 + off * 0.6, 0.12 + abs(off) * 0.2])
            p2 = np.array([0.62 + off * 0.9, 0.9 - abs(off) * 0.3])
            p1 = (p0 + p2) / 2 + np.array([0.08, -0.02])
            t = np.linspace(0, 1, 30)[:, None]
            path = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2
            w = (7 if deep else 4) * r.uniform(0.8, 1.2)
            for k in range(29):
                taper = np.sin(np.pi * (k + 0.5) / 29) ** 0.6
                seg = [tuple(path[k]), tuple(path[k + 1])]
                strokes_rim.append((seg, w * taper + 3, 1.0))
                strokes_core.append((seg, max(1, w * taper * 0.55), 1.0))
        rim = _strokes(S, strokes_rim, blur=0.8)
        core = _strokes(S, strokes_core, blur=0.4)
        return core, rim
    for n, deep, sd in ((3, False, 4), (4, True, 5)):
        core, rim = claws(n, deep, seed_of("claw", sd))
        rough = N(40, 3, "claw", sd)
        rgb = np.ones((S, S, 3)) * (tio.rgb(150, 144, 134) if not deep else tio.rgb(36, 30, 26))
        rgb = tio.mix(rgb, tio.rgb(28, 24, 22) if not deep else tio.rgb(18, 14, 12), np.clip(rim - core, 0, 1))
        if deep:
            rgb = tio.mix(rgb, tio.rgb(120, 112, 100), np.clip(rim - core, 0, 1) * 0.4 * rough)
        a = np.clip(rim * 0.85 + core * 0.15, 0, 1) * smoothstep(0.15, 0.4, rough + rim * 0.3)
        out.append(dict(rgb=rgb, a=a, h=0.5 - (0.25 if not deep else 0.45) * core - 0.05 * rim, sm=0.25))

    # 6 monkey hand print / 7 long-fingered creature footprint
    def print_shape(kind, seed):
        r = mn.rng(seed)
        polys = []
        if kind == "hand":
            polys.append((_ellipse_poly(0.5, 0.62, 0.16, 0.2, 0, 30, 0.15, r), 1.0))
            for i, (ang, L) in enumerate(((-0.35, 0.26), (-0.12, 0.3), (0.1, 0.3), (0.32, 0.25))):
                bx = 0.42 + i * 0.055
                tx, ty = bx + np.sin(ang) * L, 0.46 - np.cos(ang) * L
                for t in np.linspace(0, 1, 5):
                    polys.append((_ellipse_poly(bx + (tx - bx) * t, 0.46 + (ty - 0.46) * t, 0.03, 0.035, ang, 14,
                                                0.2, r), 1.0))
            for t in np.linspace(0, 1, 4):         # thumb, low on the palm
                polys.append((_ellipse_poly(0.33 - 0.12 * t, 0.66 - 0.1 * t, 0.035, 0.03, 0.8, 14, 0.2, r), 1.0))
        else:
            polys.append((_ellipse_poly(0.5, 0.66, 0.085, 0.16, 0.05, 30, 0.15, r), 1.0))
            polys.append((_ellipse_poly(0.51, 0.84, 0.055, 0.1, 0.0, 20, 0.2, r), 1.0))
            for i, ang in enumerate((-0.42, -0.14, 0.12, 0.4)):
                bx = 0.44 + i * 0.04
                L = 0.38 if i in (1, 2) else 0.3
                for t in np.linspace(0, 1, 7):
                    polys.append((_ellipse_poly(bx + np.sin(ang) * L * t, 0.52 - np.cos(ang) * L * t,
                                                0.016 + 0.008 * (1 - t), 0.022, ang, 12, 0.2, r), 1.0))
                cx_, cy_ = bx + np.sin(ang) * (L + 0.04), 0.52 - np.cos(ang) * (L + 0.04)
                polys.append(([(cx_ - 0.01, cy_ + 0.02), (cx_ + 0.01, cy_ + 0.02),
                               (cx_ + np.sin(ang) * 0.07, cy_ - np.cos(ang) * 0.07)], 1.0))
        m = _polys(S, polys)
        m = ndimage.gaussian_filter(m, 1.2)
        tex = N(24, 4, "print", seed) * 0.6 + N(64, 2, "print2", seed) * 0.4
        return np.clip(m * smoothstep(0.25, 0.6, tex), 0, 1)
    for kind, sd in (("hand", 6), ("foot", 7)):
        a = print_shape(kind, seed_of("print", sd)) * 0.9
        rgb = tio.gradient_map(N(16, 3, "pc", sd), [(0, (38, 28, 20)), (1, (70, 54, 38))])
        out.append(dict(rgb=rgb, a=a, h=0.5 + 0.03 * a, sm=0.3))
    # 8 dark dried stain splatter
    r = mn.rng(seed_of("splat"))
    blob = _radial_fall(S, 0.2, 0.17, 0.45, 0.5, sharp=0.6, warp=0.9, seed=8)
    drops = np.zeros((S, S))
    for _ in range(60):
        ang = r.normal(0.3, 0.6)
        dist = r.uniform(0.15, 0.42)
        cx, cy = 0.45 + np.cos(ang) * dist, 0.5 + np.sin(ang) * dist
        rad = r.uniform(0.006, 0.025) * (1.2 - dist)
        drops = np.maximum(drops, _polys(S, [(_ellipse_poly(cx, cy, rad * 1.6, rad, ang, 12, 0.3, r), 1.0)]))
    a = np.clip(blob + drops, 0, 1) * win
    rgb = tio.gradient_map(N(12, 3, "sp"), [(0, (26, 9, 8)), (1, (48, 18, 13))])
    rgb = rgb * (1 - 0.35 * blob)[..., None]
    out.append(dict(rgb=rgb, a=a * 0.92, h=0.5 + 0.02 * a, sm=0.5))
    # 9 scrawled tally marks
    strokes = []
    r = mn.rng(seed_of("tally"))
    for grp in range(3):
        gx = 0.14 + grp * 0.27
        gy = 0.3 + (grp % 2) * 0.2 + r.uniform(-0.03, 0.03)
        for k in range(4 if grp < 2 else 3):
            x = gx + k * 0.045 + r.uniform(-0.008, 0.008)
            strokes.append(([(x, gy), (x + r.uniform(-0.02, 0.02), gy + 0.26)], r.uniform(4, 6.5), 1.0))
        if grp < 2:
            strokes.append(([(gx - 0.03, gy + 0.2), (gx + 0.2, gy + 0.06)], 5.5, 1.0))
    m = _strokes(S, strokes, blur=0.7) * smoothstep(0.1, 0.4, N(48, 3, "tal"))
    out.append(dict(rgb=np.ones((S, S, 3)) * tio.rgb(24, 22, 20), a=m * 0.9, h=0.5 + 0.01 * m, sm=0.1))
    # 10 scorch mark
    d = _radial_fall(S, 0.46, 0.46, sharp=0.0, warp=0.5, seed=10)
    soot = d ** 1.5 * (0.7 + 0.3 * N(12, 4, "soot"))
    rgb = tio.gradient_map(np.clip(d, 0, 1), [(0, (52, 44, 36)), (0.6, (24, 20, 18)), (1, (10, 9, 8))])
    out.append(dict(rgb=rgb, a=np.clip(soot * 1.1, 0, 1) * win, h=0.5, sm=0.08))
    # 11 moss patch
    cov = smoothstep(0.35, 0.65, mn.warped_fbm(S, 4, 5, seed_of("decal", "moss"), warp_amt=0.1)) * \
        _radial_fall(S, 0.44, 0.38, sharp=0.2, warp=0.6, seed=11)
    gran = mn.worley(S, 1600, seed_of("decal", "mg"))
    grains = np.clip(1 - gran.f1, 0, 1)
    rgb = tio.gradient_map(np.clip(grains * 0.6 + N(8, 3, "mc") * 0.4, 0, 1),
                           [(0, (26, 34, 16)), (0.6, (56, 70, 28)), (1, (86, 96, 40))])
    a = np.clip(cov * (0.6 + 0.5 * grains), 0, 1)
    out.append(dict(rgb=rgb, a=a, h=0.5 + 0.15 * cov * grains, sm=0.2))
    # 12 rust drip streaks
    src_x = [0.3, 0.52, 0.7]
    a = np.zeros((S, S))
    for i, sx in enumerate(src_x):
        wob = (N((4, 1), 2, "rd", i) - 0.5) * 0.03
        w = 0.012 + 0.012 * i % 2
        L = 0.5 + 0.15 * i
        prof = np.exp(-((xx - sx - wob) / w) ** 2) * smoothstep(L + 0.2, 0.1, yy) * smoothstep(0.06, 0.12, yy)
        a = np.maximum(a, prof * (0.6 + 0.4 * N((3, 30), 3, "rds", i)))
        a = np.maximum(a, _radial_fall(S, 0.035, 0.03, sx, 0.1, sharp=0.3) * 0.9)
    a = np.clip(a, 0, 1) * win
    rgb = tio.gradient_map(np.clip(yy * 1.2, 0, 1), [(0, (70, 36, 20)), (0.4, (110, 58, 30)), (1, (130, 80, 46))])
    out.append(dict(rgb=rgb, a=a, h=0.5, sm=0.25))

    # 13 painted orange arrow / 14 painted X  (spray paint with overspray and drips)
    def spray(mask_hard, colour, seed):
        over = ndimage.gaussian_filter(mask_hard, 5) * 0.35
        speck = (mn.rng(seed).random((S, S)) < 0.06) * ndimage.gaussian_filter(mask_hard, 9) * 0.6
        drips = np.zeros((S, S))
        r = mn.rng(seed + 1)
        for x in r.choice(np.arange(20, S - 20), 10, replace=False):
            ys = np.nonzero(mask_hard[:, x] > 0.5)[0]
            if len(ys):
                y0 = ys.max()
                L = int(r.uniform(8, 40))
                drips[y0:min(S - 1, y0 + L), x:x + 2] = 1.0
        hard = np.clip(mask_hard + ndimage.gaussian_filter(drips, 0.5), 0, 1)
        wear = smoothstep(0.2, 0.45, mn.fbm(S, 24, 4, seed + 2))
        a = np.clip(hard * (0.55 + 0.45 * wear) + over + speck, 0, 1) * win
        rgb = np.ones((S, S, 3)) * np.array(colour) / 255.0 * (0.85 + 0.2 * mn.fbm(S, 8, 3, seed + 3))[..., None]
        return rgb, a, hard
    ar = _polys(S, [([(x / CW, y / CW) for x, y in arrow_poly(CW / 2, CW / 2, CW * 0.72, CW * 0.17, "right")], 1.0)])
    rgb, a, hard = spray(ndimage.gaussian_filter(ar, 0.8), (214, 104, 30), seed_of("spray", 13))
    out.append(dict(rgb=rgb, a=a, h=0.5 + 0.01 * hard, sm=0.35))
    xm = _strokes(S, [([(0.22, 0.2), (0.78, 0.8)], 30, 1.0), ([(0.78, 0.22), (0.24, 0.78)], 28, 1.0)], blur=1.2)
    rgb, a, hard = spray(xm, (176, 36, 28), seed_of("spray", 14))
    out.append(dict(rgb=rgb, a=a, h=0.5 + 0.01 * hard, sm=0.35))
    # 15 drag marks
    strokes = []
    r = mn.rng(seed_of("drag"))
    for i in range(4):
        y = 0.36 + i * 0.08 + r.uniform(-0.02, 0.02)
        pts = [(x, y + 0.03 * np.sin(x * 5 + i)) for x in np.linspace(0.06, 0.94, 30)]
        strokes.append((pts, r.uniform(6, 14), r.uniform(0.6, 1.0)))
    m = _strokes(S, strokes, blur=2.5)
    streak = mn.fbm(S, (40, 3), 3, seed_of("decal", "drag"))
    fade = smoothstep(0.0, 0.25, xx) * smoothstep(1.0, 0.6, xx) * (0.5 + 0.5 * (1 - xx))
    a = np.clip(m * (0.5 + 0.7 * streak) * fade * 1.8, 0, 0.95) * win
    rgb = tio.gradient_map(streak, [(0, (40, 12, 10)), (1, (70, 34, 24))])
    out.append(dict(rgb=rgb, a=a, h=0.5 - 0.02 * m, sm=0.45))
    return out


@texset("decals_atlas", None, size=1024, cutout=False, notes="4x4 alpha-blended decal atlas (256px cells, "
        "row 0 top): 0 crack, 1 water stain streaks, 2 grime patch, 3 oil stain, 4 claw scratches x3, "
        "5 deep claw scratches x4, 6 dirty monkey hand print, 7 long-fingered creature footprint, "
        "8 dark dried stain splatter, 9 scrawled tally marks, 10 scorch mark, 11 moss patch, 12 rust drip streaks, "
        "13 painted orange arrow, 14 painted X, 15 drag marks. Alpha fades to 0 before every cell border.")
def decals_atlas(S):
    cells = decal_cells()
    A = np.zeros((S, S, 3))
    AL = np.zeros((S, S))
    H = np.full((S, S), 0.5)
    SM = np.zeros((S, S))
    N = np.zeros((S, S, 3))
    win = _soft_window(CELL, 0.03)
    for i, c in enumerate(cells):
        r0, c0 = (i // 4) * CELL, (i % 4) * CELL
        a = np.clip(c["a"] * win, 0, 1)
        h = np.broadcast_to(c["h"], (CELL, CELL)).astype(np.float64)
        A[r0:r0 + CELL, c0:c0 + CELL] = c["rgb"]
        AL[r0:r0 + CELL, c0:c0 + CELL] = a
        H[r0:r0 + CELL, c0:c0 + CELL] = h
        SM[r0:r0 + CELL, c0:c0 + CELL] = c["sm"]
        gx = ndimage.sobel(h, axis=1, mode="nearest") / 8.0
        gy = ndimage.sobel(h, axis=0, mode="nearest") / 8.0
        n = np.stack([-gx * 8.0, gy * 8.0, np.ones_like(h)], -1)
        N[r0:r0 + CELL, c0:c0 + CELL] = n / np.linalg.norm(n, axis=-1, keepdims=True)
    mask = tio.pack_mask(0.0, np.ones((S, S)), H, SM, S)
    return tio.TexSet(np.clip(A, 0.02, 0.92), N, mask, alpha=AL)
