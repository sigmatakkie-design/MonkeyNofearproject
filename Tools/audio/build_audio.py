#!/usr/bin/env python
"""MONKEY NO FEAR - build every procedural sound.

Usage:  python Tools/audio/build_audio.py [--only REGEX] [--jobs 4] [--no-clean]

Writes Assets/MonkeyNoFear/Audio/<Category>/<name>[_NN].ogg (44.1 kHz Vorbis) and
Assets/MonkeyNoFear/Audio/audio_manifest.json. Deterministic: each file is seeded from
crc32("<name>:<variant>").
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import zlib
from multiprocessing import Pool

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import mnf_dsp as D  # noqa: E402
from mnf_registry import SOUNDS, file_names, load_all  # noqa: E402

PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_ROOT = os.path.join(PROJECT, "Assets", "MonkeyNoFear", "Audio")
VORBIS_COMPRESSION = 0.55   # libsndfile: vorbis quality = 1 - compression_level -> q ~0.45
PEAK_LIMIT_DB = -0.5


def seed_for(name, v):
    return zlib.crc32(("%s:%d" % (name, v)).encode()) & 0xFFFFFFFF


def trim_tail(x, rel_db=-62.0, keep_min=0.05):
    mono = np.abs(x) if x.ndim == 1 else np.max(np.abs(x), axis=1)
    p = mono.max()
    if p <= 0:
        return x
    win = D.ns(0.01)
    nb = len(mono) // win
    if nb < 2:
        return x
    env = mono[: nb * win].reshape(nb, win).max(axis=1)
    above = np.flatnonzero(env > p * D.undb(rel_db))
    last = (above[-1] + 1) * win + D.ns(0.02) if len(above) else len(x)
    last = max(last, D.ns(keep_min))
    return x[: min(len(x), last)]


def finalize(x, spec):
    x = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise ValueError("non-finite samples in " + spec["name"])
    if spec["stereo"] and x.ndim == 1:
        x = np.stack([x, x], 1)
    if not spec["stereo"] and x.ndim == 2:
        x = x.mean(axis=1)
    if spec["loop"]:
        x = x - x.mean(axis=0)
        x = D.circ(lambda y: D.bw(y, "highpass", 16.0, 2), x)
    else:
        x = D.bw(x, "highpass", 16.0, 2)
        if spec["trim"]:
            x = trim_tail(x)
        fo = min(spec["fout"], len(x) / D.SR * 0.3)
        x = D.fade(x, spec["fin"], fo)
    mode = spec["norm"]
    if mode[0] == "peak":
        x = x * (D.undb(mode[1]) / (D.peak(x) + 1e-12))
    else:
        r = np.sqrt(np.mean(x ** 2))
        x = x * (D.undb(mode[1]) / (r + 1e-12))
        ceil = D.undb(mode[2])
        if D.peak(x) > ceil:
            x = D.soft_limit(x, ceil)
    return x


def write_ogg(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = x.astype(np.float32)
    for _ in range(5):
        sf.write(path, data, D.SR, format="OGG", subtype="VORBIS", compression_level=VORBIS_COMPRESSION)
        y, _sr = sf.read(path, dtype="float32")
        pk = float(np.max(np.abs(y)))
        if 20 * np.log10(pk + 1e-12) <= PEAK_LIMIT_DB - 0.05:
            return y
        data = data * (D.undb(PEAK_LIMIT_DB - 0.3) / pk)
    return y


def render_one(task):
    try:
        return _render_one(task)
    except Exception as e:  # make worker failures name the sound
        import traceback
        raise RuntimeError("%s[%d]: %r\n%s" % (task[0], task[1], e, traceback.format_exc()))


def _render_one(task):
    name, v = task
    spec = SOUNDS[name]
    rng = np.random.default_rng(seed_for(name, v))
    t0 = time.time()
    x = spec["fn"](rng, v)
    x = finalize(x, spec)
    fname = file_names(spec)[v]
    rel = spec["category"] + "/" + fname
    path = os.path.join(OUT_ROOT, spec["category"], fname)
    y = write_ogg(path, x)
    return dict(name=name, v=v, rel=rel, dur=len(y) / D.SR, secs=time.time() - t0,
                peak_db=float(20 * np.log10(np.max(np.abs(y)) + 1e-12)),
                rms_db=float(20 * np.log10(np.sqrt(np.mean(y.astype(np.float64) ** 2)) + 1e-12)),
                size=os.path.getsize(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="regex on sound name")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--no-clean", action="store_true")
    args = ap.parse_args()

    load_all()
    names = sorted(SOUNDS)
    if args.only:
        names = [n for n in names if re.search(args.only, n)]
    tasks = []
    for n in names:
        for v in range(max(1, SOUNDS[n]["variants"])):
            tasks.append((n, v))
    # heavy first for better load balance
    tasks.sort(key=lambda t: -(SOUNDS[t[0]]["dur"] or 1.0))
    t0 = time.time()
    if args.jobs > 1:
        with Pool(args.jobs) as pool:
            results = pool.map(render_one, tasks, chunksize=1)
    else:
        results = [render_one(t) for t in tasks]
    print("rendered %d files in %.1fs" % (len(results), time.time() - t0))
    slow = sorted(results, key=lambda r: -r["secs"])[:5]
    for r in slow:
        print("  slow: %-34s %.1fs" % (r["rel"], r["secs"]))

    # manifest (merge with existing when building a subset)
    man_path = os.path.join(OUT_ROOT, "audio_manifest.json")
    manifest = {}
    if args.only and os.path.exists(man_path):
        with open(man_path) as f:
            manifest = json.load(f)
    by_name = {}
    for r in results:
        by_name.setdefault(r["name"], []).append(r)
    for n in names:
        spec = SOUNDS[n]
        rs = sorted(by_name[n], key=lambda r: r["v"])
        manifest[n] = dict(
            category=spec["category"],
            files=[r["rel"] for r in rs],
            loop=bool(spec["loop"]),
            spatial=bool(spec["spatial"]),
            channels=2 if spec["stereo"] else 1,
            duration=round(float(np.mean([r["dur"] for r in rs])), 3),
            durations=[round(r["dur"], 3) for r in rs],
            description=spec["desc"],
        )
    manifest = {k: manifest[k] for k in sorted(manifest, key=lambda k: (manifest[k]["category"], k))}
    with open(man_path, "w") as f:
        json.dump(manifest, f, indent=1)

    if not args.only and not args.no_clean:
        wanted = {os.path.normpath(os.path.join(OUT_ROOT, f)) for m in manifest.values() for f in m["files"]}
        for root, _dirs, files in os.walk(OUT_ROOT):
            for fn in files:
                p = os.path.normpath(os.path.join(root, fn))
                if fn.endswith(".ogg") and p not in wanted:
                    os.remove(p)
                    print("  removed stale", p)
    total = 0
    for root, _dirs, files in os.walk(OUT_ROOT):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files if f.endswith(".ogg"))
    print("manifest: %d sounds, total audio size %.2f MB" % (len(manifest), total / 1e6))


if __name__ == "__main__":
    main()
