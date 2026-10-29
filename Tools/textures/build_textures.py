"""build_textures.py - generate every MONKEY NO FEAR texture procedurally (deterministic).

Usage:
    python build_textures.py                 # build everything + manifest + previews
    python build_textures.py --only rust,mud # rebuild selected sets (manifest is merged)
    python build_textures.py --jobs 4 --no-preview

Outputs: Assets/MonkeyNoFear/Art/Textures/  (see Docs/ASSET_SPEC.md section 2/3)
Previews: Docs/previews/textures/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "MonkeyNoFear", "Art", "Textures")
PREV = os.path.join(ROOT, "Docs", "previews", "textures")

import numpy as np  # noqa: E402

import mnf_texio as tio  # noqa: E402
from mnf_registry import REGISTRY  # noqa: E402
import mnf_sets_hard  # noqa: E402,F401
import mnf_sets_organic  # noqa: E402,F401
import mnf_sets_cards  # noqa: E402,F401
import mnf_sets_atlas  # noqa: E402,F401


# Art grade (Gorilla Tag fan-game look): brighter, cleaner, more saturated and more readable than the raw PBR
# generators. Applied to the sRGB albedo after generation. tint = colour the luminance is mapped onto (0..1),
# mix = how far toward it, lift/contrast/sat = basic grade around the mean.
GRADE = {
    "concrete_wall": dict(lift=0.16, contrast=0.62, sat=0.6),                                # clean pale bunker concrete
    "concrete_floor": dict(lift=0.10, contrast=0.75, sat=0.7),
    "rock_mine": dict(tint=(0.42, 0.66, 0.64), mix=0.7, lift=0.05, contrast=0.9),            # teal mine rock
    "rock_wet": dict(tint=(0.30, 0.52, 0.52), mix=0.6, lift=0.03),
    "forest_floor": dict(tint=(0.36, 0.52, 0.22), mix=0.55, lift=0.02, sat=1.15),           # mossy green litter
    "wood_beam": dict(tint=(0.86, 0.66, 0.34), mix=0.55, lift=0.10, sat=1.1),               # warm yellow timbers
    "wood_planks": dict(tint=(0.80, 0.62, 0.36), mix=0.4, lift=0.06),
    "foliage_pine": dict(sat=1.25, lift=0.02),
}


def grade(alb, g):
    a = np.asarray(alb, dtype=np.float32)
    rgb = a[..., :3]
    lum = (rgb * np.array([0.299, 0.587, 0.114], np.float32)).sum(-1, keepdims=True)
    if "tint" in g:
        # map luminance onto the tint colour, normalised so mid-grey keeps its brightness
        t = np.array(g["tint"], np.float32)
        tinted = lum * t / max(1e-3, float((t * np.array([0.299, 0.587, 0.114])).sum()))
        rgb = rgb * (1 - g.get("mix", 1.0)) + tinted * g.get("mix", 1.0)
        lum = (rgb * np.array([0.299, 0.587, 0.114], np.float32)).sum(-1, keepdims=True)
    if "sat" in g:
        rgb = lum + (rgb - lum) * g["sat"]
    if "contrast" in g:
        m = float(rgb.mean())
        rgb = m + (rgb - m) * g["contrast"]
    if "lift" in g:
        rgb = g["lift"] + rgb * (1 - g["lift"])
    out = a.copy()
    out[..., :3] = np.clip(rgb, 0, 1)
    return out


def build_one(name):
    t0 = time.time()
    meta = REGISTRY[name]
    res = meta["fn"](meta["size"])
    files = {}
    if meta["kind"] == "sprite":
        arr = res
        fn = f"{name}.png"
        tio.save_png(os.path.join(OUT, fn), tio.to8(arr))
        files["albedo"] = fn
    else:
        if name in GRADE and res.albedo is not None:
            res.albedo = grade(res.albedo, GRADE[name])
        files = tio.write_set(OUT, name, res, normal_only=meta["kind"] == "normal")
    return name, files, time.time() - t0


def manifest_entry(name, files):
    m = REGISTRY[name]
    return {
        "albedo": files.get("albedo"),
        "normal": files.get("normal"),
        "mask": files.get("mask"),
        "emission": files.get("emission"),
        "tiling_m": m["tiling_m"],
        "cutout": bool(m["cutout"]),
        "emission_enabled": bool(m["emission"]),
        "kind": m["kind"],
        "size": m["size"],
        "notes": m["notes"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma separated set names")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    names = [n for n in args.only.split(",") if n] or list(REGISTRY)
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        sys.exit(f"unknown sets: {unknown}")

    t0 = time.time()
    if args.jobs > 1 and len(names) > 1:
        with Pool(args.jobs) as pool:
            results = pool.map(build_one, names, chunksize=1)
    else:
        results = [build_one(n) for n in names]
    for n, files, dt in results:
        print(f"  {n:22s} {dt:6.1f}s  {', '.join(files.values())}")

    man_path = os.path.join(OUT, "textures_manifest.json")
    manifest = {}
    if os.path.exists(man_path) and args.only:
        with open(man_path) as f:
            manifest = json.load(f)
    for n, files, _ in results:
        manifest[n] = manifest_entry(n, files)
    manifest = {k: manifest[k] for k in REGISTRY if k in manifest}
    # Flat {set: {...}} layout as specified in Docs/ASSET_SPEC.md section 3.
    # Conventions: _A sRGB (alpha = opacity on cutout sets / decals), _N tangent space OpenGL (+Y up),
    # _M linear (R metallic, G AO, B height, A smoothness), _E sRGB emission; tiling_m = metres per repeat
    # (null for cards, sprites and atlases); "emission" is the _E file name or null.
    with open(man_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"built {len(results)} sets in {time.time() - t0:.1f}s")

    if not args.no_preview:
        import preview_textures
        preview_textures.main()


if __name__ == "__main__":
    main()
