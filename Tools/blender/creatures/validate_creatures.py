"""Re-import every exported creature FBX into an empty scene and validate it against the brief + manifest:
bone names, clip (action) names, frame ranges / lengths, triangle budgets, material names, no negative scales,
no scale animation except where allowed (Falsekin fold). Prints a report and writes
Docs/previews/creatures/validation_report.txt. Exit code 1 on any failure.
Run: <python-with-bpy> validate_creatures.py
"""
import bpy
import os
import sys
import json
import math

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FBX_DIR = os.path.join(PROJECT, "Assets", "MonkeyNoFear", "Art", "Models", "Creatures")
REPORT = os.path.join(PROJECT, "Docs", "previews", "creatures", "validation_report.txt")
FPS = 30

ARM = ["upperarm", "forearm", "hand"]
LEG = ["thigh", "shin", "foot"]


def lr(names):
    return [n + s for n in names for s in (".L", ".R")]


STD = ["root", "hips", "spine", "chest", "neck", "head", "jaw"] + lr(ARM + ["fingers"]) + lr(LEG)
QUAD = ["root", "hips", "spine", "chest", "neck", "head", "jaw"] + lr(ARM) + lr(LEG)
REQUIRED = {
    "Hollowback": {"bones": STD + ["hump"],
                   "clips": ["idle", "listen", "walk", "follow", "run", "alert", "inspect", "attack", "stagger"],
                   "events": {"run": "slap", "attack": "hit"}, "tris": (3000, 9000)},
    "Rabbit": {"bones": ["root", "hips", "spine", "chest", "neck", "head", "ear.L", "ear.R", "nose", "eyelid.L",
                         "eyelid.R"] + lr(ARM) + lr(LEG),
               "clips": ["idle", "graze", "hop", "run", "alert", "blink", "death"], "tris": (3000, 9000)},
    "Falsekin": {"bones": STD + ["ear.L", "ear.R", "jaw.L", "jaw.R"],
                 "clips": ["folded", "unfold", "idle", "run", "lunge", "retreat", "death"],
                 "events": {"lunge": "hit"}, "tris": (3000, 9000),
                 "scale_ok": {"hips", "upperarm.L", "upperarm.R", "thigh.L", "thigh.R"}},
    "CeilingClerk": {"bones": STD, "clips": ["cling", "crawl", "freeze", "jaw_open", "drop", "grab", "flee"],
                     "events": {"crawl": "tap"}, "tris": (3000, 9000)},
    "Borer": {"bones": STD + ["mouth.L", "mouth.R"],
              "clips": ["idle", "sense", "walk", "charge", "attack", "emerge", "burrow", "stagger"],
              "events": {"attack": "hit"}, "tris": (3000, 9000)},
    "LanternMourner": {"bones": STD + ["socket_chestlight", "lamps"],
                       "clips": ["idle", "walk", "retreat", "turn_head", "reach", "recoil"],
                       "events": {"reach": "hit"}, "tris": (3000, 9000)},
    "Gaunt": {"bones": STD, "clips": ["walk", "stand", "look_up"], "tris": (500, 4000)},
    "Boar": {"bones": QUAD + ["ear.L", "ear.R"], "clips": ["idle", "graze", "walk", "run", "alert", "charge", "death"],
             "tris": (3000, 9000)},
    "Gloomrat": {"bones": QUAD, "clips": ["idle", "run", "peek", "hide"], "tris": (3000, 9000)},
}
CATALOG = {"MNF_FurRotten", "MNF_SkinDecayed", "MNF_FurRabbit", "MNF_FurRabbitMangy", "MNF_FurBoar", "MNF_FurDark",
           "MNF_MineralCrust", "MNF_MournerSkin", "MNF_Teeth", "MNF_Gums", "MNF_Nails", "MNF_Flesh", "MNF_EyeWet",
           "MNF_EyeClouded", "MNF_EyeGlint", "MNF_MournerGlow", "MNF_Glass", "MNF_MetalRusted", "MNF_BulbWarm",
           "MNF_Rubber", "MNF_Rope"}


def fcurves_of(act):
    out = []
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out.extend(cb.fcurves)
    except AttributeError:
        out = list(act.fcurves)
    return out


def validate(name, entry, lines):
    errs = []
    req = REQUIRED[name]
    path = os.path.join(FBX_DIR, entry["file"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    bpy.ops.import_scene.fbx(filepath=path)
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    if len(arms) != 1:
        errs.append("expected 1 armature, got %d" % len(arms))
        return errs
    arm = arms[0]
    bones = [b.name for b in arm.data.bones]
    missing = [b for b in req["bones"] if b not in bones]
    extra = [b for b in bones if b not in req["bones"]]
    if missing:
        errs.append("missing bones: %s" % missing)
    if set(bones) != set(entry["bones"]):
        errs.append("bones differ from manifest")
    root = arm.data.bones.get("root")
    if root is None or root.head_local.length > 1e-3:
        errs.append("root bone not at origin")
    # transforms
    for o in bpy.data.objects:
        if min(o.scale) <= 0 or o.matrix_world.determinant() <= 0:
            errs.append("negative/zero scale on %s %s" % (o.name, tuple(round(x, 3) for x in o.scale)))
    # triangles + materials
    tris = 0
    mats = set()
    for m in meshes:
        tris += sum(len(p.vertices) - 2 for p in m.data.polygons)
        mats |= {s.name for s in m.data.materials if s}
        if "UVMap" not in m.data.uv_layers:
            errs.append("mesh %s has no UVMap" % m.name)
    lo, hi = req["tris"]
    if not (lo <= tris <= hi):
        errs.append("tris %d outside budget %s" % (tris, req["tris"]))
    if tris != entry["tris"]:
        errs.append("tris %d != manifest %d" % (tris, entry["tris"]))
    bad = sorted(m for m in mats if m.split(".")[0] not in CATALOG)
    if bad:
        errs.append("non-catalog materials: %s" % bad)
    # clips
    acts = {}
    for a in bpy.data.actions:
        clip = a.name.split("|")[-1]
        acts[clip] = a
    for c in req["clips"]:
        if c not in acts:
            errs.append("missing clip %s" % c)
    clip_lines = []
    for c, a in acts.items():
        f0, f1 = a.frame_range
        frames = int(round(f1 - f0))
        me = entry["clips"].get(c)
        if me is None:
            errs.append("clip %s not in manifest" % c)
            continue
        if frames != me["frames"] or abs(frames / FPS - me["length"]) > 1e-3:
            errs.append("clip %s frames %d vs manifest %d" % (c, frames, me["frames"]))
        # scale animation only where allowed
        allowed = req.get("scale_ok", set())
        for fc in fcurves_of(a):
            if fc.data_path.endswith(".scale"):
                bone = fc.data_path.split('"')[1]
                vals = [k.co[1] for k in fc.keyframe_points]
                if vals and (max(vals) - min(vals) > 1e-3 or abs(vals[0] - 1) > 1e-3) and bone not in allowed:
                    errs.append("unexpected scale animation %s/%s" % (c, bone))
                    break
        # loop check: first and last frame identical (bone transforms)
        loop_ok = ""
        if me["loop"]:
            worst = 0.0
            for fc in fcurves_of(a):
                kp = fc.keyframe_points
                if len(kp) >= 2:
                    worst = max(worst, abs(kp[0].co[1] - kp[-1].co[1]))
            loop_ok = " loop-delta %.4f" % worst
            if worst > 1e-3:
                errs.append("clip %s loop endpoints differ (%.4f)" % (c, worst))
        ev = me.get("events") or {}
        clip_lines.append("    %-10s %3d f  %.3f s  loop=%-5s speed=%-4s events=%s%s" % (
            c, frames, frames / FPS, me["loop"], me.get("speed", "-"), json.dumps(ev), loop_ok))
    for c, ev in req.get("events", {}).items():
        if not entry["clips"].get(c, {}).get("events", {}).get(ev):
            errs.append("clip %s missing event %s" % (c, ev))
    lines.append("%s  (%s)" % (name, entry["file"]))
    lines.append("  tris %d   bones %d   materials %s" % (tris, len(bones), sorted(mats)))
    lines.append("  height %.2f  length %.2f  eye_height %.2f  head_rest %s" % (
        entry["height"], entry["length"], entry["eye_height"], entry["head_rest_position"]))
    if extra:
        lines.append("  extra bones (beyond brief list): %s" % extra)
    lines.extend(sorted(clip_lines))
    lines.append("  RESULT: %s" % ("OK" if not errs else "FAIL"))
    for e in errs:
        lines.append("   ! " + e)
    return errs


def main():
    with open(os.path.join(FBX_DIR, "creatures_manifest.json")) as fh:
        manifest = json.load(fh)
    lines = ["MONKEY NO FEAR creature FBX validation (re-imported into an empty scene)", ""]
    total_errs = 0
    for name in REQUIRED:
        if name not in manifest:
            lines.append("%s: MISSING from manifest" % name)
            total_errs += 1
            continue
        errs = validate(name, manifest[name], lines)
        total_errs += len(errs)
        lines.append("")
    lines.append("VALIDATION %s (%d problems)" % ("PASSED" if total_errs == 0 else "FAILED", total_errs))
    txt = "\n".join(lines)
    print(txt)
    with open(REPORT, "w") as fh:
        fh.write(txt + "\n")
    sys.exit(0 if total_errs == 0 else 1)


if __name__ == "__main__":
    main()
