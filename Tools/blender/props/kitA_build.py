"""kitA_build.py - build entry point for prop artist A kits (Kit_Tools, Kit_Deposits, Kit_Bunker).

Usage (bpy module or Blender):
    python kitA_build.py -- [Kit_Tools] [Kit_Deposits] [Kit_Bunker] [--no-render] [--only A,B] [--hero A,B]
    blender -b -P kitA_build.py -- Kit_Tools

For every kit: builds all objects at the world origin, saves SourceArt/Props/<Kit>.blend, exports
Assets/MonkeyNoFear/Art/Models/Props/<Kit>.fbx (ASSET_SPEC export settings, no animation), writes
props_manifest_<Kit>.json, renders preview contact sheets to Docs/previews/props/.
Validate afterwards with kitA_validate.py.
"""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402
import propkit_a_helpers as H  # noqa: E402

KITS = {"Kit_Tools": "kitA_tools", "Kit_Deposits": "kitA_deposits", "Kit_Bunker": "kitA_bunker"}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"kits": [], "render": True, "only": None, "hero": None, "sheets": True}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--no-render":
            opts["render"] = False
        elif a == "--no-sheets":
            opts["sheets"] = False
        elif a == "--only":
            opts["only"] = argv[i + 1].split(","); i += 1
        elif a == "--hero":
            opts["hero"] = argv[i + 1].split(","); i += 1
        elif a in KITS:
            opts["kits"].append(a)
        else:
            raise SystemExit("unknown arg %s" % a)
        i += 1
    if not opts["kits"]:
        opts["kits"] = list(KITS)
    return opts


def build_kit(kit, opts):
    H.reset_scene()
    mod = importlib.import_module(KITS[kit])
    entries = mod.build()
    roots = [e["root"] for e in entries]
    for r in roots:
        assert r.parent is None and r.location.length == 0, r.name
    os.makedirs(H.SOURCE_DIR, exist_ok=True)
    blend = os.path.join(H.SOURCE_DIR, kit + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    fbx = os.path.join(H.MODEL_DIR, kit + ".fbx")
    H.export_fbx(fbx, roots)
    manifest = {}
    for e in entries:
        manifest[e["root"].name] = H.object_record(e["root"], kit, e.get("notes", ""))
    mpath = os.path.join(H.MODEL_DIR, "props_manifest_%s.json" % kit)
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=1)
    print("[%s] %d objects -> %s" % (kit, len(roots), fbx))
    for n, rec in manifest.items():
        print("   %-24s tris %5d  size %s  helpers %s" % (n, rec["tris"], rec["bounds_size"], list(rec["helpers"])))
    if opts["render"]:
        render_kit(kit, entries, manifest, opts)
    return manifest


def render_kit(kit, entries, manifest, opts):
    import kitA_preview as P
    os.makedirs(H.PREVIEW_DIR, exist_ok=True)
    scratch = os.path.join(P.SCRATCH, kit)
    os.makedirs(scratch, exist_ok=True)
    roots = [e["root"] for e in entries]
    sel = [e for e in entries if opts["only"] is None or e["root"].name in opts["only"]]
    tiles = []
    for e in sel:
        r = e["root"]
        rec = manifest[r.name]
        sz = rec["bounds_size"]
        fig = e.get("figure")
        figure_at = None
        if fig:
            mn = rec["bounds_min"]
            figure_at = (mn[0] - 0.45, (rec["bounds_min"][1] + rec["bounds_max"][1]) / 2 if not e.get("wall") else -0.25, mn[2])
        png = os.path.join(scratch, r.name + ".png")
        if opts["sheets"]:
            P.render_tile(roots, [r], png, view=e.get("view", "iso"), res=(320, 240), samples=16, cell=e.get("cell", 0.1),
                          figure_at=figure_at, wall=e.get("wall", False))
            cell = e.get("cell", 0.1)
            lines = [r.name, "%d tris  %.2f x %.2f x %.2f m" % (rec["tris"], sz[0], sz[1], sz[2]),
                     "grid %g cm%s" % (cell * 100, "  fig 1.7 m" if fig else "")]
            tiles.append((png, lines))
        hero = (opts["hero"] is not None and r.name in opts["hero"]) or (opts["hero"] is None and e.get("hero"))
        if hero:
            shots = e.get("hero_shots") or [(e.get("view", "iso"), None), ("iso", None)]
            for k, (v, focus) in enumerate(shots):
                hp = os.path.join(H.PREVIEW_DIR, "%s_%s_%d.png" % (kit, r.name, k))
                P.render_tile(roots, [r], hp, view=v, res=(640, 480), samples=24, cell=e.get("cell", 0.1),
                              figure_at=figure_at if focus is None else None, focus=focus, wall=e.get("wall", False))
                print("hero", hp)
    if tiles:
        per = 4
        for s in range(0, len(tiles), per):
            out = os.path.join(H.PREVIEW_DIR, "%s_sheet_%02d.png" % (kit, s // per + (0 if opts["only"] is None else 50)))
            P.compose(tiles[s:s + per], out, cols=2, tile_res=(320, 240), title=kit)
            print("sheet", out)
    if opts["only"] is None:
        ov = os.path.join(H.PREVIEW_DIR, "%s_overview.png" % kit)
        mod = importlib.import_module(KITS[kit])
        rows = getattr(mod, "OVERVIEW_ROWS", 2)
        P.overview(roots, ov, res=(640, 480), samples=20, cell=getattr(mod, "OVERVIEW_CELL", 0.5), rows=rows,
                   view=getattr(mod, "OVERVIEW_VIEW", "iso"))
        print("overview", ov)


def main():
    opts = parse_args()
    for kit in opts["kits"]:
        build_kit(kit, opts)


if __name__ == "__main__":
    main()
