#!/usr/bin/env python
"""Verify the generated audio set and render spectrogram contact sheets.

Checks (FAIL = must fix, WARN = look at it):
  * every sound/variant in the registry exists, is listed in the manifest, 44.1 kHz,
    mono/stereo as required
  * finite samples, not silent, decoded peak <= -0.5 dBFS
  * duration sensible (loops within 15 % of the brief, one-shots loosely)
  * loops: sample discontinuity at the wrap comparable to normal sample-to-sample steps,
    RMS of the last/first 50 ms similar, no internal gaps (drop-outs)
  * variants actually differ from each other
  * total size budget
Contact sheets: Docs/previews/audio/<Category>_NN.png (loops drawn twice with the wrap marked).

Usage: python Tools/audio/verify_audio.py [--no-sheets] [--only REGEX]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mnf_registry import SOUNDS, file_names, load_all  # noqa: E402

PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
AUDIO = os.path.join(PROJECT, "Assets", "MonkeyNoFear", "Audio")
PREV = os.path.join(PROJECT, "Docs", "previews", "audio")
SR = 44100
SIZE_BUDGET_MB = 45.0

FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def font(sz):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def dbv(x):
    return 20 * np.log10(max(float(x), 1e-12))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)) + 1e-20))


def check_loop(x, name, issues):
    m = x.mean(axis=1) if x.ndim == 2 else x
    chans = [x[:, c] for c in range(x.shape[1])] if x.ndim == 2 else [x]
    for c, ch in enumerate(chans):
        steps = np.abs(np.diff(ch))
        p999 = np.percentile(steps, 99.9)
        jump = abs(float(ch[0]) - float(ch[-1]))
        # 0.008 (~-42 dBFS) ~ Vorbis q0.45 quantisation noise: independent codec error at both ends
        if jump > max(1.5 * p999, 8e-3):
            issues.append(("FAIL", name, "loop wrap jump %.4f > 1.5 x p99.9 step %.4f (ch%d)" % (jump, p999, c)))
    w = int(0.015 * SR)
    a, b = rms(m[-w:]), rms(m[:w])
    tot = rms(m)
    if max(a, b) > tot * 0.03 and abs(dbv(a) - dbv(b)) > 6.0:
        issues.append(("FAIL", name, "loop edge (15 ms) RMS mismatch end %.1f dB vs start %.1f dB" % (dbv(a), dbv(b))))
    w2 = int(0.5 * SR)
    if len(m) > 4 * w2:
        a2, b2 = rms(m[-w2:]), rms(m[:w2])
        if abs(dbv(a2) - dbv(b2)) > 8.0:
            issues.append(("WARN", name, "loop 0.5 s end/start RMS differ by %.1f dB" % abs(dbv(a2) - dbv(b2))))
    # gaps: 100 ms windows far below overall level
    w3 = int(0.1 * SR)
    nb = len(m) // w3
    if nb >= 3:
        blocks = m[: nb * w3].reshape(nb, w3)
        br = np.sqrt(np.mean(blocks ** 2, axis=1))
        if np.min(br) < tot * 10 ** (-40 / 20):
            issues.append(("FAIL", name, "loop has a drop-out (100 ms block %.1f dB below RMS)" % (dbv(np.min(br)) - dbv(tot))))
    return abs(float(m[0]) - float(m[-1]))


# ----------------------------------------------------------------------------- sheets
STOPS = [(0.0, (0, 0, 4)), (0.15, (28, 16, 68)), (0.35, (101, 26, 128)), (0.55, (183, 55, 121)),
         (0.75, (241, 105, 76)), (0.9, (253, 182, 104)), (1.0, (252, 253, 191))]


def cmap(v):
    v = np.clip(v, 0, 1)
    xs = np.array([s[0] for s in STOPS])
    out = np.zeros(v.shape + (3,), np.uint8)
    for c in range(3):
        out[..., c] = np.interp(v, xs, [s[1][c] for s in STOPS]).astype(np.uint8)
    return out


def spectro(x, W, H, fmin=40.0, fmax=20000.0):
    d = len(x) / SR
    nfft = 256 if d < 1.2 else (512 if d < 5 else 1024)
    if len(x) < nfft:
        x = np.pad(x, (0, nfft - len(x)))
    hop = max(16, (len(x) - nfft) // max(W, 1) + 1)
    frames = 1 + (len(x) - nfft) // hop
    idx = np.arange(nfft)[None, :] + hop * np.arange(frames)[:, None]
    win = np.hanning(nfft)
    S = np.abs(np.fft.rfft(x[idx] * win, axis=1)) + 1e-9
    f = np.fft.rfftfreq(nfft, 1 / SR)
    rows = np.geomspace(fmin, fmax, H)[::-1]
    Sl = np.stack([np.interp(rows, f, s) for s in S], axis=1)  # H x frames
    dbS = 20 * np.log10(Sl)
    dbS = dbS - dbS.max()
    cols = np.linspace(0, frames - 1, W)
    img = np.stack([np.interp(cols, np.arange(frames), r) for r in dbS], 0)
    return cmap((img + 80) / 80)


def wave_strip(x, W, H):
    img = np.full((H, W, 3), 18, np.uint8)
    n = len(x)
    edges = np.linspace(0, n, W + 1).astype(int)
    mid = H // 2
    for i in range(W):
        seg = x[edges[i]:max(edges[i + 1], edges[i] + 1)]
        lo, hi = float(seg.min()), float(seg.max())
        y0, y1 = int(mid - hi * (H / 2 - 1)), int(mid - lo * (H / 2 - 1))
        img[max(0, y0):min(H, y1 + 1), i] = (150, 200, 230)
    clip = int((H / 2 - 1) * 10 ** (-0.5 / 20))
    img[mid - clip, :] = (90, 40, 40)
    img[mid + clip, :] = (90, 40, 40)
    return img


def render_sheets(cat, entries):
    CW, SH, WH, TH = 360, 112, 30, 18
    cols, rows = 4, 7
    per = cols * rows
    f = font(11)
    os.makedirs(PREV, exist_ok=True)
    pages = []
    for p in range(0, len(entries), per):
        chunk = entries[p:p + per]
        img = Image.new("RGB", (cols * CW, rows * (SH + WH + TH)), (8, 8, 10))
        d = ImageDraw.Draw(img)
        for i, (name, spec, datas) in enumerate(chunk):
            if not datas:
                continue
            cx, cy = (i % cols) * CW, (i // cols) * (SH + WH + TH)
            segs, marks = [], []
            for x in datas:
                m = x.mean(axis=1) if x.ndim == 2 else x
                if spec["loop"]:
                    marks.append(sum(len(s) for s in segs) + len(m))
                    m = np.concatenate([m, m])
                segs.append(m)
                segs.append(np.zeros(int(0.02 * SR)))
            cat_x = np.concatenate(segs[:-1])
            W = CW - 4
            sp = spectro(cat_x, W, SH)
            wv = wave_strip(cat_x, W, WH)
            img.paste(Image.fromarray(sp), (cx + 2, cy + TH))
            img.paste(Image.fromarray(wv), (cx + 2, cy + TH + SH))
            for mk in marks:
                px = cx + 2 + int(mk / len(cat_x) * W)
                d.line([(px, cy + TH), (px, cy + TH + SH + WH)], fill=(0, 255, 120), width=1)
            durs = ",".join("%.2f" % (len(x) / SR) for x in datas[:4])
            tag = ("L " if spec["loop"] else "") + ("ST " if spec["stereo"] else "")
            d.text((cx + 3, cy + 2), "%s %s[%ss]" % (name, tag, durs), fill=(230, 230, 230), font=f)
        path = os.path.join(PREV, "%s_%02d.png" % (cat, p // per + 1))
        img.save(path)
        pages.append(path)
    return pages


def render_focus(entries, path):
    """Large per-file spectrograms (one row per file) for close inspection."""
    W, H, WH, TH = 1400, 200, 40, 18
    rows = [(n, i, x) for n, spec, datas in entries for i, x in enumerate(datas)]
    img = Image.new("RGB", (W + 4, len(rows) * (H + WH + TH)), (8, 8, 10))
    d = ImageDraw.Draw(img)
    f = font(12)
    for r, (n, i, x) in enumerate(rows):
        m = x.mean(axis=1) if x.ndim == 2 else x
        y0 = r * (H + WH + TH)
        img.paste(Image.fromarray(spectro(m, W, H, 50.0, 18000.0)), (2, y0 + TH))
        img.paste(Image.fromarray(wave_strip(m, W, WH)), (2, y0 + TH + H))
        d.text((4, y0 + 2), "%s #%d  %.2fs   (log freq 50 Hz - 18 kHz)" % (n, i + 1, len(m) / SR), fill=(230, 230, 230), font=f)
    img.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sheets", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--focus", default=None, help="regex: also render large spectrograms of matching sounds")
    args = ap.parse_args()
    load_all()
    issues = []
    man_path = os.path.join(AUDIO, "audio_manifest.json")
    manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
    if not manifest:
        issues.append(("FAIL", "manifest", "missing audio_manifest.json"))
    names = sorted(SOUNDS)
    if args.only:
        names = [n for n in names if re.search(args.only, n)]
    for n in manifest:
        if n not in SOUNDS:
            issues.append(("WARN", n, "in manifest but not in registry"))
    by_cat = {}
    nfiles = 0
    for name in names:
        spec = SOUNDS[name]
        datas = []
        m = manifest.get(name)
        if m is None:
            issues.append(("FAIL", name, "not in manifest"))
        for fn in file_names(spec):
            rel = spec["category"] + "/" + fn
            path = os.path.join(AUDIO, spec["category"], fn)
            if m is not None and rel not in m["files"]:
                issues.append(("FAIL", name, "manifest missing file " + rel))
            if not os.path.exists(path):
                issues.append(("FAIL", name, "missing file " + rel))
                continue
            nfiles += 1
            x, sr = sf.read(path, dtype="float64", always_2d=False)
            if sr != SR:
                issues.append(("FAIL", rel, "sample rate %d" % sr))
            ch = 1 if x.ndim == 1 else x.shape[1]
            if ch != (2 if spec["stereo"] else 1):
                issues.append(("FAIL", rel, "channels %d" % ch))
            if not np.all(np.isfinite(x)):
                issues.append(("FAIL", rel, "non-finite samples"))
                continue
            pk = dbv(np.max(np.abs(x)))
            r = dbv(rms(x))
            dur = len(x) / SR
            if pk > -0.5:
                issues.append(("FAIL", rel, "peak %.2f dBFS > -0.5" % pk))
            if r < -60 or pk < -20:
                issues.append(("FAIL", rel, "near silent (rms %.1f, peak %.1f dBFS)" % (r, pk)))
            if not (0.03 <= dur <= 40):
                issues.append(("FAIL", rel, "duration %.2f s" % dur))
            hint = spec["dur"]
            if hint:
                if spec["loop"] and abs(dur - hint) / hint > 0.15:
                    issues.append(("FAIL", rel, "loop length %.2f s vs brief %.2f s" % (dur, hint)))
                elif not spec["loop"] and not (0.4 * hint <= dur <= 2.6 * hint + 0.3):
                    issues.append(("WARN", rel, "duration %.2f s vs brief ~%.2f s" % (dur, hint)))
            mono = x.mean(axis=1) if x.ndim == 2 else x
            onset = np.flatnonzero(np.abs(mono) > np.max(np.abs(mono)) * 0.05)
            if len(onset) and onset[0] / SR > 0.35 and not spec["loop"]:
                issues.append(("WARN", rel, "late onset %.2f s" % (onset[0] / SR)))
            if spec["loop"]:
                check_loop(x, rel, issues)
            if not spec["loop"]:
                tail = np.abs(mono[-int(0.003 * SR):]).max()
                if tail > 0.05:
                    issues.append(("WARN", rel, "non-zero end (%.3f) - click?" % tail))
            datas.append(x)
        # variants must differ
        for i in range(len(datas)):
            for j in range(i + 1, len(datas)):
                a, b = datas[i], datas[j]
                k = min(len(a), len(b))
                if k and np.allclose(a[:k], b[:k], atol=1e-4):
                    issues.append(("FAIL", name, "variants %d and %d identical" % (i + 1, j + 1)))
        by_cat.setdefault(spec["category"], []).append((name, spec, datas))
    total = 0
    for root, _d, files in os.walk(AUDIO):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files if f.endswith(".ogg"))
    if total / 1e6 > SIZE_BUDGET_MB:
        issues.append(("FAIL", "size", "total %.1f MB > %.0f MB" % (total / 1e6, SIZE_BUDGET_MB)))
    pages = []
    if not args.no_sheets:
        for cat in sorted(by_cat):
            pages += render_sheets(cat, by_cat[cat])
    if args.focus:
        sel = [e for cat in sorted(by_cat) for e in by_cat[cat] if re.search(args.focus, e[0])]
        if sel:
            pages.append(render_focus(sel, os.path.join(PREV, "focus.png")))
    fails = [i for i in issues if i[0] == "FAIL"]
    warns = [i for i in issues if i[0] == "WARN"]
    lines = ["sounds checked: %d, files: %d, total size: %.2f MB" % (len(names), nfiles, total / 1e6),
             "FAIL: %d  WARN: %d" % (len(fails), len(warns))]
    lines += ["%s  %-40s %s" % i for i in fails + warns]
    lines += ["sheet: " + p for p in pages]
    txt = "\n".join(lines)
    print(txt)
    if not args.only:
        os.makedirs(PREV, exist_ok=True)
        with open(os.path.join(PREV, "verify_report.txt"), "w") as f:
            f.write(txt + "\n")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
