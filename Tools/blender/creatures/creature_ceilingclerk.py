"""Ceiling Clerk - overhead stalker in the mines.
Modelled crawling on a horizontal surface, belly toward the surface (-Z), back up (+Z). Unity mounts it
upside-down on ceilings by aligning the creature's up axis with the surface normal (local +Z then points
down toward the floor / the player).
Run: <python-with-bpy> creature_ceilingclerk.py -- [--no-preview]
"""
import bpy  # noqa: F401  (must come before mathutils)
import os
import sys
import math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
import mnf_creaturekit as K
from mnf_creaturekit import (Capsule, Ellipsoid, FlatCapsule, EllipsoidBetween, BoneDef, Pose, Clip, smoothstep,
                             pulse, ramp, pnoise, tnoise, foot_track, keyed, ease_out, ease_in)

NAME = "CeilingClerk"
MATS = ["MNF_FurDark", "MNF_SkinDecayed", "MNF_Teeth", "MNF_Gums", "MNF_EyeGlint", "MNF_Nails"]
FUR, SKIN, TEETH, GUMS, GLINT, NAILS = MATS

P = dict(
    hips=(0, 0.70, 0.20), spine=(0, 0.25, 0.215), chest=(0, -0.25, 0.215), neck=(0, -0.72, 0.20),
    head=(0, -0.92, 0.19), head_t=(0, -1.16, 0.17),
    jaw=(0, -0.97, 0.155), jaw_t=(0, -1.14, 0.125),
    shoulder=(0.12, -0.58, 0.22), elbow=(0.56, -0.74, 0.46), wrist=(0.76, -1.14, 0.065),
    knuckle=(0.80, -1.34, 0.03), ftip=(0.83, -1.66, 0.02),
    thigh=(0.11, 0.62, 0.17), knee=(0.30, 0.30, 0.20), ankle=(0.26, 0.74, 0.075), toe=(0.30, 1.0, 0.025),
)


def bones():
    b = [
        BoneDef("root", (0, 0, 0), (0, 0.3, 0), None, deform=False),
        BoneDef("hips", P["hips"], P["spine"], "root"),
        BoneDef("spine", P["spine"], P["chest"], "hips", connect=True),
        BoneDef("chest", P["chest"], P["neck"], "spine", connect=True),
        BoneDef("neck", P["neck"], P["head"], "chest", connect=True),
        BoneDef("head", P["head"], P["head_t"], "neck", connect=True),
        BoneDef("jaw", P["jaw"], P["jaw_t"], "head"),
        BoneDef("upperarm.L", P["shoulder"], P["elbow"], "chest"),
        BoneDef("forearm.L", P["elbow"], P["wrist"], "upperarm.L", connect=True),
        BoneDef("hand.L", P["wrist"], P["knuckle"], "forearm.L", connect=True),
        BoneDef("fingers.L", P["knuckle"], P["ftip"], "hand.L", connect=True),
        BoneDef("thigh.L", P["thigh"], P["knee"], "hips"),
        BoneDef("shin.L", P["knee"], P["ankle"], "thigh.L", connect=True),
        BoneDef("foot.L", P["ankle"], P["toe"], "shin.L", connect=True),
    ]
    return K.mirror_bones(b)


IK = [("upperarm.L", "forearm.L"), ("upperarm.R", "forearm.R"), ("thigh.L", "shin.L"), ("thigh.R", "shin.R")]


def M(p, s):
    return np.array(p, float) * np.array([s, 1, 1])


def build(nz):
    F = K.Field((-1.12, -1.95, -0.03), (1.12, 1.18, 0.62), 0.0085)
    pt = K.Parts()
    rng = np.random.RandomState(23)
    # --- narrow, flattened, stretched torso
    F.add(FlatCapsule((0, 0.78, 0.19), (0, 0.25, 0.215), 0.11, 0.12, up=(0, 0, 1), flat=0.62, mat=FUR, bone="hips",
                      tag="pelvis"), k=0.06)
    F.add(FlatCapsule((0, 0.3, 0.215), (0, -0.3, 0.215), 0.1, 0.12, up=(0, 0, 1), flat=0.58, mat=FUR, bone="spine",
                      tag="spine"), k=0.07)
    F.add(FlatCapsule((0, -0.2, 0.215), (0, -0.66, 0.21), 0.125, 0.115, up=(0, 0, 1), flat=0.6, mat=FUR,
                      bone="chest", tag="chest"), k=0.07)
    # spine ridge and shoulder blades
    for i in range(12):
        t = i / 11
        c = np.array((0, 0.75 - 1.4 * t, 0.275 - 0.01 * math.sin(math.pi * t)))
        F.add(Ellipsoid(c, (0.022, 0.03, 0.02), (0, 0, 0), FUR, None, "vert"), k=0.03)
    for s in (1, -1):
        F.add(Ellipsoid(M((0.1, -0.5, 0.27), s), (0.07, 0.11, 0.03), (0, 0, 20 * s), FUR, "chest", "blade"), k=0.04)
        F.add(Capsule(M((0.06, -0.55, 0.22), s), M(P["shoulder"], s) + [0.02 * s, 0, 0.01], 0.07, 0.06, FUR, "chest",
                      "shoulder"), k=0.05)
    # --- neck + face pressed against a flat skull
    F.add(Capsule((0, -0.62, 0.205), (0, -0.95, 0.19), 0.075, 0.06, FUR, "neck", "neck"), k=0.05)
    F.add(Ellipsoid((0, -1.02, 0.19), (0.11, 0.13, 0.07), (0, 0, 0), FUR, "head", "skull"), k=0.04)
    F.add(Ellipsoid((0, -1.1, 0.175), (0.085, 0.07, 0.055), (0, 0, 0), SKIN, "head", "face"), k=0.03)
    F.add(Capsule((0.075, -1.12, 0.215), (-0.075, -1.12, 0.215), 0.022, 0.022, SKIN, "head", "brow"), k=0.02)
    # lower jaw - long, hangs
    F.add(EllipsoidBetween((0, -0.98, 0.15), (0, -1.15, 0.13), 0.06, 0.028, SKIN, "jaw", "jaw", y_hint=(0, 0, 1)),
          k=0.025)
    F.sub(Ellipsoid((0, -1.1, 0.152), (0.055, 0.07, 0.008), (0, 0, 0), GUMS), k=0.005)
    # recessed eye pits
    eye = np.array((0.045, -1.135, 0.205))
    F.sub(Ellipsoid(eye + [0, -0.004, 0], 0.016), k=0.006, keep=False, mirror=True)
    # --- very long arms with oversized hands, fingers splayed flat on the surface
    for s in (1, -1):
        sh, el, wr, kn = M(P["shoulder"], s), M(P["elbow"], s), M(P["wrist"], s), M(P["knuckle"], s)
        F.add(Capsule(sh, el, 0.055, 0.04, FUR, None, "upperarm"), k=0.04)
        F.add(Capsule(el, wr, 0.04, 0.032, FUR, None, "forearm"), k=0.03)
        F.add(Ellipsoid(el, 0.045, (0, 0, 0), SKIN, None, "elbow"), k=0.02)
        F.add(FlatCapsule(wr, kn, 0.06, 0.095, up=(0, 0, 1), flat=0.36, mat=SKIN, tag="palm"), k=0.035)
        K.add_digits(F, pt, kn + [0, 0, 0.0], along=(0.05 * s, -1, -0.05), spread_dir=(1, 0, 0),
                     curl_dir=(0, 0, -1), n=4, length=0.44, r0=0.023, r1=0.014, spread=0.19, curl=30, mat=SKIN,
                     nail_mat=NAILS, nail_len=0.05, seed=40 + s, tag="fingers", fan=13, segs=3)
        K.add_digits(F, pt, wr + (kn - wr) * 0.5 + np.array([-0.06 * s, -0.02, 0]), along=(-0.8 * s, -0.6, -0.1),
                     spread_dir=(0, 1, 0), curl_dir=(0, 0, -1), n=1, length=0.26, r0=0.024, r1=0.015, spread=0,
                     curl=20, mat=SKIN, nail_mat=NAILS, nail_len=0.035, seed=50 + s, tag="palm", segs=2)
        # legs folded tight against the body
        th, kq, an, to = M(P["thigh"], s), M(P["knee"], s), M(P["ankle"], s), M(P["toe"], s)
        F.add(Capsule(th, kq, 0.065, 0.045, FUR, None, "thigh"), k=0.05)
        F.add(Capsule(kq, an, 0.042, 0.03, FUR, None, "shin"), k=0.03)
        F.add(FlatCapsule(an, to, 0.03, 0.04, up=(0, 0, 1), flat=0.45, mat=SKIN, tag="foot"), k=0.02)
        K.add_digits(F, pt, to, along=(0.2 * s, 1, -0.1), spread_dir=(1, 0, 0), curl_dir=(0, 0, -1), n=4,
                     length=0.13, r0=0.012, r1=0.009, spread=0.07, curl=30, mat=SKIN, nail_mat=NAILS,
                     nail_len=0.025, seed=60 + s, tag="foot", segs=2)
    # --- glinting eyes (tiny), teeth and the tendons holding the mouth shut
    for s in (1, -1):
        pt.ellipsoid(eye * [s, 1, 1], 0.0105, GLINT, segs=8, rings=5, bone="head")
    for i, t in enumerate(np.linspace(-1, 1, 12)):
        x = 0.048 * t
        y = -1.16 + 0.055 * t * t
        L = rng.uniform(0.018, 0.03)
        b = np.array((x, y, 0.162))
        d = np.array((rng.uniform(-0.2, 0.2), -0.25, -1))
        d /= np.linalg.norm(d)
        pt.cone(Vector(b), Vector(b + d * L), 0.0045, TEETH, segs=4, bone="head")
        b2 = np.array((x * 0.92 + 0.005, y + 0.01, 0.141))
        d2 = np.array((rng.uniform(-0.2, 0.2), -0.3, 1))
        d2 /= np.linalg.norm(d2)
        pt.cone(Vector(b2), Vector(b2 + d2 * L * 0.9), 0.0042, TEETH, segs=4, bone="jaw")
    for x in (-0.05, -0.022, 0.006, 0.033, 0.055):
        top = Vector((x, -1.155 + 0.03 * abs(x) / 0.05, 0.183))
        bot = Vector((x * 0.95, -1.15 + 0.03 * abs(x) / 0.05, 0.118))
        pt.tube([top, (top + bot) / 2, bot], [0.0055, 0.0045, 0.0055], GUMS, segs=4,
                weights=[{"head": 1.0}, {"head": 0.5, "jaw": 0.5}, {"jaw": 1.0}])
    return F, pt


def displacement(nz):
    def fn(co, nr):
        return 0.004 * nz.fbm(co, 3, 3) + 0.004 * np.maximum(nz(co, 7, (1, 1, 1)), 0)
    return fn


def mat_rules(nz):
    def rules(C, N, mats, owners):
        bald = nz.fbm(C, 2.0, 2) > 0.7
        for i, o in enumerate(owners):
            if mats[i] == FUR and (bald[i] or (N[i, 2] < -0.6 and o.tag in ("pelvis", "spine", "chest"))):
                mats[i] = SKIN  # bare grey belly + a few bald patches
        return mats
    return [rules]


def make_clips(rig):
    hands = {s: rig.tail("forearm." + s) for s in "LR"}
    feet = {s: rig.tail("shin." + s) for s in "LR"}
    pole_a = lambda s: Vector((1.0 if s == "L" else -1.0, 0.2, 1.2))
    pole_l = lambda s: Vector((1.0 if s == "L" else -1.0, -0.6, 0.6))

    def grip(p, offs=None, w=1.0, flat=True):
        offs = offs or {}
        for s in "LR":
            p.ik("upperarm." + s, hands[s] + offs.get("h" + s, Vector()), pole_a(s), w)
            p.ik("thigh." + s, feet[s] + offs.get("f" + s, Vector()), pole_l(s), w)
            if flat:
                p.w("hand." + s)
                p.w("foot." + s)
        return p

    # ---- cling 3 s: pressed flat, fingers re-grip one hand at a time
    def cling(u, t):
        p = Pose()
        b = math.sin(2 * math.pi * 2 * u)
        p.l("hips", 0, 0, -0.045 + 0.003 * b)
        p.r("spine", 0.6 * b)
        p.r("chest", -0.8 * b)
        p.r("neck", 3, 0, 2 * pnoise(u, 3))
        p.r("head", 4, 2 * pnoise(u, 4), 3 * pnoise(u, 5))
        offs = {}
        for s, at in (("L", 0.12), ("R", 0.45), ("L", 0.7), ("R", 0.88)):
            e = pulse(u, at, at + 0.03, at + 0.06, at + 0.1)
            p.r("fingers." + s, -35 * e)
            p.r("hand." + s, -8 * e)
            offs["h" + s] = offs.get("h" + s, Vector()) + Vector((0, 0, 0.04 * e))
        return grip(p, offs)

    # ---- crawl ~1.2 m/s, finger-over-finger, hands release / reconnect rapidly
    CR_F = 27

    def crawler(u, frames, speed, low=0.0, duty_h=0.62, duty_f=0.7, lift_h=0.16, lift_f=0.07, wiggle=1.0):
        T = frames / K.FPS
        p = Pose()
        ph = 2 * math.pi * u
        p.l("hips", 0.02 * math.sin(ph) * wiggle, 0, -0.02 - low + 0.01 * math.cos(2 * ph))
        p.r("hips", 0, 3 * math.sin(ph) * wiggle, 8 * math.sin(ph) * wiggle)
        p.r("spine", 0, -2 * math.sin(ph) * wiggle, -9 * math.sin(ph) * wiggle)
        p.r("chest", 0, 2 * math.sin(ph) * wiggle, -8 * math.sin(ph + 0.5) * wiggle)
        p.r("neck", 2, 0, 12 * math.sin(ph + 0.9) * wiggle)
        p.r("head", 4, 0, -8 * math.sin(ph + 1.2) * wiggle)
        seq = {"hL": 0.0, "fR": 0.18, "hR": 0.5, "fL": 0.68}
        for key, off in seq.items():
            s = key[1]
            if key[0] == "h":
                tgt, contact, ss = foot_track(u, off, duty_h, speed * duty_h * T, lift_h, hands[s], lift_pow=0.7)
                p.ik("upperarm." + s, tgt, pole_a(s), 1.0)
                # fingers peel off the surface and slap back down
                if contact:
                    p.w("hand." + s)
                    peel = ramp(ss, 0.85, 1.0)
                    p.r("fingers." + s, -45 * peel)
                else:
                    p.w("hand." + s, 25 * math.sin(math.pi * ss))
                    p.r("fingers." + s, -45 * (1 - ramp(ss, 0.0, 0.7)) + 20 * pulse(ss, 0.7, 0.85, 0.9, 1.0))
            else:
                tgt, contact, ss = foot_track(u, off, duty_f, speed * duty_f * T, lift_f, feet[s])
                p.ik("thigh." + s, tgt, pole_l(s), 1.0)
                p.w("foot." + s)
        return p

    def crawl(u, t):
        return crawler(u, CR_F, 1.2)

    tap_crawl = sorted([0, int(round(0.5 * CR_F))])

    # ---- freeze 1 s: rigid, head twisted round to face the viewer (local +Z = toward the floor)
    def freeze(u, t):
        p = Pose()
        p.l("hips", 0, 0, -0.03)
        tremble = 0.6 * math.sin(2 * math.pi * 7 * u)
        p.l("hips", 0, 0, -0.01)
        p.r("chest", -8)
        p.r("neck", -38, 8, 0)
        p.r("head", -52 + tremble, 28, 4 * pnoise(u, 9, (1, 2)))
        p.r("jaw", 3)
        for s in "LR":
            p.r("fingers." + s, -10)
        return grip(p)

    # ---- jaw_open 0.6 s: the lower jaw drops far too far and stays suspended
    def jaw_open(u, t):
        p = cling(0.0, 0.0)
        f = t * K.FPS
        o = ease_out(ramp(f, 2, 10), 2.5)
        hang = pulse(f, 9, 11, 12, 16)
        p.r("jaw", 78 * o + 6 * hang)
        p.r("chest", -6 * o)
        p.r("neck", -22 * o)
        p.r("head", -30 * o)
        return p

    # ---- drop 0.5 s: lets go, flips over (roll 180) with limbs spread
    def drop(u, t):
        f = t * K.FPS
        p = Pose()
        rel = ease_out(ramp(f, 0, 4), 2)
        flip = smoothstep(ramp(f, 2, 13))
        p.l("hips", 0, 0, 0.25 * math.sin(math.pi * min(1, f / 15)) + 0.12 * flip)
        p.r("hips", -10 * rel, 180 * flip, 0)
        p.r("spine", -12 * rel)
        p.r("chest", -10 * rel)
        p.r("neck", -20 * rel)
        p.r("head", -15 * rel)
        p.r("jaw", 30 * rel)
        spread = ease_out(ramp(f, 0, 6), 2)
        for s in "LR":
            sg = 1 if s == "L" else -1
            p.r("upperarm." + s, -20 * spread, 0, 15 * sg * spread)
            p.r("forearm." + s, -15 * spread, 0, 10 * sg * spread)
            p.r("fingers." + s, -30 * spread)
            p.r("thigh." + s, 0, 0, -45 * sg * spread)
            p.r("shin." + s, 0, 0, -30 * sg * spread)
            p.r("foot." + s, -20 * spread)
        return p

    # ---- grab 1.5 s loop: arches away from the surface, clutching in front at a standing monkey's chest
    def grab(u, t):
        p = Pose()
        ph = 2 * math.pi * u
        p.l("hips", 0, 0.05, -0.02)
        p.r("hips", 0, 0, 0)
        p.r("spine", -12)
        p.r("chest", -38 + 2 * math.sin(ph))
        p.r("neck", -15)
        p.r("head", 20 + 4 * math.sin(2 * ph), 0, 5 * math.sin(ph))
        p.r("jaw", 60 + 8 * math.sin(2 * ph))
        for s in "LR":
            sg = 1 if s == "L" else -1
            hold = Vector((0.16 * sg, -1.45, 0.95 + 0.04 * math.sin(ph + sg)))
            p.ik("upperarm." + s, hold, Vector((sg, 0.5, -0.5)), 1.0)
            p.w("hand." + s, -80, 0, -40 * sg)
            p.r("fingers." + s, 60 + 15 * math.sin(2 * ph + sg))
            p.ik("thigh." + s, feet[s], pole_l(s), 1.0)
            p.w("foot." + s)
        return p

    # ---- flee: fast crawl ~3 m/s
    FL_F = 15

    def flee(u, t):
        return crawler(u, FL_F, 3.0, low=0.02, duty_h=0.5, duty_f=0.55, lift_h=0.2, lift_f=0.09, wiggle=1.4)

    return [
        Clip("cling", 90, cling, loop=True, speed=0.0),
        Clip("crawl", CR_F, crawl, loop=True, speed=1.2, events={"tap": tap_crawl}),
        Clip("freeze", 30, freeze, loop=True, speed=0.0),
        Clip("jaw_open", 18, jaw_open, loop=False),
        Clip("drop", 15, drop, loop=False, notes="Ends rolled 180 deg about its forward axis (belly facing local +Z)."),
        Clip("grab", 45, grab, loop=True, speed=0.0,
             notes="Hands clutch ~1.0 m from the surface along local +Z, in front of the head."),
        Clip("flee", FL_F, flee, loop=True, speed=3.0, events={"tap": sorted([0, int(round(0.5 * FL_F))])}),
    ]


def main():
    K.reset_scene()
    nz = K.Noise3(404)
    F, pt = build(nz)
    imp = K.importance_spheres([((0, -1.08, 0.18), 0.12, 1.0)] +
                               [(M(P["knuckle"], s) + [0, -0.12, 0], 0.2, 0.6) for s in (1, -1)])
    body = K.body_from_field(NAME + "_Body", F, 6800, displacement(nz), smooth_iter=2, importance_fn=imp)
    K.assign_body_materials(body, F, MATS, mat_rules(nz))
    arm = K.build_armature(NAME, bones())
    W = K.skin_body(body, arm)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    co = K.get_verts(body)
    W = K.side_cleanup(W, deform, co, eps=0.03)
    K.auto_assign_prim_bones(F, arm)
    W = K.refine_weights(arm, co, F, W, deform, sigma=0.02, own_mix=0.35)
    W = K.smooth_weights(body, W, iterations=2, factor=0.5)
    wj = K.prim_ownership_weight(co, F, {"jaw"}, 0.01)
    W = K.override_weights(W, deform, "jaw", wj)
    K.write_weights(body, deform, W)
    K.add_tufts(body, pt, MATS, FUR, count=60, seed=12, length=(0.04, 0.09), radius=(0.012, 0.02), droop=0.3,
                max_nz=1.1, normal_mix=1.0)
    pobj = pt.build(NAME + "_Parts", MATS)
    K.finalize_join(body, pobj, pt, arm)
    K.uv_unwrap(body, repeat_m=0.55)
    rig = K.Rig(arm)
    clips = make_clips(rig)
    entry = K.finish_creature(NAME, arm, [body], clips, IK, eye_height=0.205,
                              preview_kwargs={"contact_view": (-0.8, -0.9, 0.9), "fog_view": (-0.9, -0.9, 0.35)},
                              extra_manifest={"notes": "Crawling frame: belly -Z toward the surface, back +Z. "
                                                       "eye_height is above the surface in that frame."})
    K.log("DONE", NAME, entry["tris"], "tris")


if __name__ == "__main__":
    main()
