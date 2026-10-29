"""preview_textures.py - contact sheets, tiling checks and seam metrics for the MNF textures.

Reads the files listed in textures_manifest.json and writes PNG sheets to Docs/previews/textures/.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mnf_texio as tio  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "MonkeyNoFear", "Art", "Textures")
PREV = os.path.join(ROOT, "Docs", "previews", "textures")
TH = 192


def load(fn, mode=None):
    if not fn:
        return None
    p = os.path.join(OUT, fn)
    if not os.path.exists(p):
        return None
    im = Image.open(p)
    if mode:
        im = im.convert(mode)
    return np.asarray(im, dtype=np.float64) / 255.0


def checker(h, w, cell=16):
    c = ((np.indices((h, w)).sum(0) // cell) % 2) * 0.18 + 0.32
    return np.stack([c] * 3, -1)


def over_checker(rgba):
    a = rgba[..., 3:4]
    return rgba[..., :3] * a + checker(*rgba.shape[:2]) * (1 - a)


def thumb(arr, size=TH):
    im = Image.fromarray(tio.to8(arr))
    return im.resize((size, size), Image.LANCZOS)


def seam_ratio(a):
    """Wrap-seam column/row difference relative to the 95th percentile of interior column/row differences.

    A tileable map gives values around or below 1; a visible seam gives values well above 1.
    """
    a = a[..., :3] if a.ndim == 3 else a
    dx = np.abs(np.diff(a, axis=1, append=a[:, :1]))
    dy = np.abs(np.diff(a, axis=0, append=a[:1]))
    colx = dx.reshape(a.shape[0], a.shape[1], -1).mean(axis=(0, 2))
    rowy = dy.reshape(a.shape[0], a.shape[1], -1).mean(axis=(1, 2))
    return colx[-1] / (np.percentile(colx[:-1], 95) + 1e-9), rowy[-1] / (np.percentile(rowy[:-1], 95) + 1e-9)


def contact_sheets(sets):
    names = [n for n, m in sets.items() if m["kind"] in ("pbr", "normal")]
    per = 6
    cols = ["albedo", "normal", "mask RGB", "smooth (M.a)", "lit", "2x2 lit / E"]
    for si in range(0, len(names), per):
        chunk = names[si:si + per]
        W = len(cols) * (TH + 6) + 6
        H = len(chunk) * (TH + 22) + 24
        sheet = Image.new("RGB", (W, H), (24, 24, 26))
        d = ImageDraw.Draw(sheet)
        f = tio.font(13)
        for ci, c in enumerate(cols):
            d.text((6 + ci * (TH + 6), 4), c, fill=(200, 200, 200), font=f)
        for ri, n in enumerate(chunk):
            m = sets[n]
            y = 24 + ri * (TH + 22)
            d.text((6, y), n, fill=(255, 220, 120), font=f)
            y += 16
            A = load(m["albedo"], "RGBA")
            N = load(m["normal"], "RGB")
            M = load(m["mask"], "RGBA")
            E = load(m["emission"], "RGB")
            tiles = []
            if A is not None:
                tiles.append(over_checker(A) if m["cutout"] else A[..., :3])
            else:
                tiles.append(np.full((8, 8, 3), 0.2))
            tiles.append(N if N is not None else np.full((8, 8, 3), 0.5))
            if M is not None:
                tiles.append(M[..., :3])
                tiles.append(np.stack([M[..., 3]] * 3, -1))
            else:
                tiles += [np.zeros((8, 8, 3))] * 2
            if A is not None and N is not None and M is not None:
                lit = tio.shade_preview(A[..., :3], N, M, E, A[..., 3] if m["cutout"] else None)
            elif N is not None:
                flat = np.zeros(N.shape[:2] + (4,))
                flat[..., 1] = 1
                flat[..., 3] = 0.9
                lit = tio.shade_preview(np.full(N.shape, 0.15), N, flat)
            else:
                lit = np.zeros((8, 8, 3))
            tiles.append(lit)
            if E is not None:
                tiles.append(E)
            elif not m["cutout"]:
                tiles.append(np.tile(lit, (2, 2, 1)))
            else:
                tiles.append(np.zeros((8, 8, 3)))
            for ci, t in enumerate(tiles):
                sheet.paste(thumb(t), (6 + ci * (TH + 6), y))
        sheet.save(os.path.join(PREV, f"sheet_{si // per + 1:02d}.png"))


def tiling_sheets(sets):
    names = [n for n, m in sets.items() if m["kind"] == "pbr" and not m["cutout"] and m["size"] == 512
             and m.get("tiling_m")]
    per = 2
    T = 360
    for si in range(0, len(names), per):
        chunk = names[si:si + per]
        sheet = Image.new("RGB", (per * 2 * T + 12, 2 * T + 30), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for ci, n in enumerate(chunk):
            m = sets[n]
            A = load(m["albedo"], "RGB")
            N = load(m["normal"], "RGB")
            M = load(m["mask"], "RGBA")
            lit = tio.shade_preview(A, N, M, load(m["emission"], "RGB"))
            tiled = np.tile(lit, (2, 2, 1))
            im = Image.fromarray(tio.to8(tiled)).resize((2 * T, 2 * T), Image.LANCZOS)
            sheet.paste(im, (ci * (2 * T + 12), 28))
            d.text((ci * (2 * T + 12) + 4, 6), f"{n} (2x2 tiled, lit)", fill=(255, 220, 120), font=tio.font(15))
        sheet.save(os.path.join(PREV, f"tiling_{si // per + 1:02d}.png"))


def card_sheet(sets):
    names = [n for n, m in sets.items() if m["kind"] in ("pbr",) and m["cutout"] and n != "metal_grate"]
    T = 300
    sheet = Image.new("RGB", (len(names) * (T + 8) + 8, 3 * (T + 8) + 30), (30, 30, 32))
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        m = sets[n]
        A = load(m["albedo"], "RGBA")
        N = load(m["normal"], "RGB")
        M = load(m["mask"], "RGBA")
        x = 8 + i * (T + 8)
        d.text((x, 6), n, fill=(255, 220, 120), font=tio.font(15))
        sheet.paste(thumb(over_checker(A), T), (x, 28))
        bg = np.ones_like(A[..., :3]) * np.array([0.55, 0.6, 0.65])
        comp = A[..., :3] * A[..., 3:4] + bg * (1 - A[..., 3:4])
        sheet.paste(thumb(comp, T), (x, 28 + T + 8))
        sheet.paste(thumb(tio.shade_preview(A[..., :3], N, M, None, A[..., 3]), T), (x, 28 + 2 * (T + 8)))
    sheet.save(os.path.join(PREV, "cards.png"))


def sprite_sheet(sets):
    names = [n for n, m in sets.items() if m["kind"] == "sprite"]
    T = 192
    sheet = Image.new("RGB", (len(names) * (T + 8) + 8, 2 * (T + 8) + 30), (30, 30, 32))
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        A = load(sets[n]["albedo"], "RGBA")
        x = 8 + i * (T + 8)
        d.text((x, 6), n, fill=(255, 220, 120), font=tio.font(13))
        dark = A[..., :3] * A[..., 3:4] + np.array([0.04, 0.045, 0.05]) * (1 - A[..., 3:4])
        sheet.paste(thumb(dark, T), (x, 28))
        sheet.paste(thumb(over_checker(A), T), (x, 28 + T + 8))
    sheet.save(os.path.join(PREV, "fx_sprites.png"))


def atlas_views(sets):
    for n in ("signs_atlas", "decals_atlas"):
        if n not in sets:
            continue
        m = sets[n]
        A = load(m["albedo"], "RGBA")
        N = load(m["normal"], "RGB")
        M = load(m["mask"], "RGBA")
        if n == "decals_atlas":
            conc = load("concrete_wall_A.png", "RGB")
            bg = np.tile(conc, (2, 2, 1)) if conc is not None else np.full_like(A[..., :3], 0.45)
            comp = A[..., :3] * A[..., 3:4] + bg * (1 - A[..., 3:4])
            Image.fromarray(tio.to8(comp)).save(os.path.join(PREV, "decals_on_concrete.png"))
            Image.fromarray(tio.to8(over_checker(A))).save(os.path.join(PREV, "decals_alpha.png"))
        else:
            Image.fromarray(tio.to8(A[..., :3])).save(os.path.join(PREV, "signs_albedo.png"))
            if N is not None and M is not None:
                lit = tio.shade_preview(A[..., :3], N, M)
                Image.fromarray(tio.to8(lit)).save(os.path.join(PREV, "signs_lit.png"))


def main():
    with open(os.path.join(OUT, "textures_manifest.json")) as f:
        sets = json.load(f)
    os.makedirs(PREV, exist_ok=True)
    contact_sheets(sets)
    tiling_sheets(sets)
    card_sheet(sets)
    sprite_sheet(sets)
    atlas_views(sets)
    # seam metrics
    lines = []
    for n, m in sets.items():
        if m["kind"] not in ("pbr", "normal") or m["cutout"] or not m.get("tiling_m"):
            continue
        for key in ("albedo", "normal", "mask"):
            a = load(m[key])
            if a is None:
                continue
            sx, sy = seam_ratio(a)
            flag = "  <-- CHECK" if max(sx, sy) > 1.6 else ""
            lines.append(f"{n:20s} {key:7s} seam/interior x={sx:4.2f} y={sy:4.2f}{flag}")
    with open(os.path.join(PREV, "seam_report.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    bad = [l for l in lines if "CHECK" in l]
    print(f"previews written to {PREV}; seam warnings: {len(bad)}")
    for l in bad:
        print("  " + l)


if __name__ == "__main__":
    main()
