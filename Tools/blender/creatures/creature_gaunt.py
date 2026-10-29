"""The Gaunt - colossal emaciated monkey-shaped figure glimpsed far below in the deep chasm (~14 m).
Low detail by design (<= 4k tris).
Run: <python-with-bpy> creature_gaunt.py -- [--no-preview]
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

NAME = "Gaunt"
S = 1.09  # the field below is authored at ~12.8 m; scaled after meshing so the figure stands ~14 m
MATS = ["MNF_SkinDecayed", "MNF_FurDark", "MNF_EyeGlint"]
SKIN, FUR, GLINT = MATS

P = dict(
    hips=(0, 0.25, 6.6), spine=(0, 0.25, 9.0), chest=(0, -0.05, 11.0), neck=(0, -0.55, 12.45),
    head=(0, -1.35, 12.55), head_t=(0, -2.05, 11.85),
    jaw=(0, -1.5, 12.05), jaw_t=(0, -2.0, 11.5),
    shoulder=(1.45, -0.35, 12.15), elbow=(1.85, -0.15, 8.4), wrist=(1.95, -0.6, 4.8),
    knuckle=(1.95, -0.8, 3.85), ftip=(1.9, -1.15, 2.0),
    thigh=(0.75, 0.25, 6.35), knee=(0.9, -0.45, 3.4), ankle=(0.85, 0.3, 0.5), toe=(0.85, -0.9, 0.12),
)


def bones():
    def sc(v):
        return tuple(x * S for x in v)
    b = [
        BoneDef("root", (0, 0, 0), (0, 0, 1.0 * S), None, deform=False),
        BoneDef("hips", sc(P["hips"]), sc(P["spine"]), "root"),
        BoneDef("spine", sc(P["spine"]), sc(P["chest"]), "hips", connect=True),
        BoneDef("chest", sc(P["chest"]), sc(P["neck"]), "spine", connect=True),
        BoneDef("neck", sc(P["neck"]), sc(P["head"]), "chest", connect=True),
        BoneDef("head", sc(P["head"]), sc(P["head_t"]), "neck", connect=True),
        BoneDef("jaw", sc(P["jaw"]), sc(P["jaw_t"]), "head"),
        BoneDef("upperarm.L", sc(P["shoulder"]), sc(P["elbow"]), "chest"),
        BoneDef("forearm.L", sc(P["elbow"]), sc(P["wrist"]), "upperarm.L", connect=True),
        BoneDef("hand.L", sc(P["wrist"]), sc(P["knuckle"]), "forearm.L", connect=True),
        BoneDef("fingers.L", sc(P["knuckle"]), sc(P["ftip"]), "hand.L", connect=True),
        BoneDef("thigh.L", sc(P["thigh"]), sc(P["knee"]), "hips"),
        BoneDef("shin.L", sc(P["knee"]), sc(P["ankle"]), "thigh.L", connect=True),
        BoneDef("foot.L", sc(P["ankle"]), sc(P["toe"]), "shin.L", connect=True),
    ]
    return K.mirror_bones(b)


IK = [("thigh.L", "shin.L"), ("thigh.R", "shin.R")]


def M(p, s):
    return np.array(p, float) * np.array([s, 1, 1])


def build(nz):
    F = K.Field((-2.7, -2.8, -0.1), (2.7, 1.3, 13.9), 0.036)
    pt = K.Parts()
    F.add(Ellipsoid((0, 0.3, 6.6), (0.85, 0.6, 0.6), (8, 0, 0), SKIN, "hips", "pelvis"), k=0.3)
    F.add(Capsule((0, 0.3, 6.9), (0, 0.15, 9.3), 0.42, 0.55, SKIN, "spine", "waist"), k=0.4)
    F.add(EllipsoidBetween((0, 0.2, 8.9), (0, -0.25, 12.0), 1.0, 0.75, SKIN, "chest", "ribcage", y_hint=(0, -1, 0)),
          k=0.4)
    F.sub(Ellipsoid((0, -0.75, 8.6), (0.55, 0.3, 0.6)), k=0.3, keep=False)  # sunken gut
    # ribs as ridges
    for z in (9.6, 10.15, 10.7, 11.2):
        for s in (1, -1):
            F.add(Capsule(M((0.55, -0.62, z), s), M((0.98, 0.0, z + 0.25), s), 0.09, 0.09, SKIN, "chest", "rib"),
                  k=0.15)
    # hunched upper back with dark matted fur, shoulder blades
    F.add(EllipsoidBetween((0, 0.45, 10.0), (0, -0.2, 12.6), 1.05, 0.55, FUR, "chest", "back", y_hint=(0, 1, 0)),
          k=0.45)
    for s in (1, -1):
        F.add(Capsule(M((0.3, -0.2, 12.3), s), M(P["shoulder"], s) + [0, 0, 0.15], 0.38, 0.33, FUR, "chest",
                      "shoulder"), k=0.35)
    # neck juts forward, head bowed low
    F.add(Capsule((0, -0.3, 12.2), (0, -1.3, 12.45), 0.36, 0.28, SKIN, "neck", "neck"), k=0.3)
    F.add(EllipsoidBetween((0, -1.25, 12.6), (0, -2.05, 11.85), 0.45, 0.45, SKIN, "head", "skull",
                           y_hint=(0, 0, 1)), k=0.2)
    F.add(Capsule((0.35, -1.9, 12.3), (-0.35, -1.9, 12.3), 0.12, 0.12, SKIN, "head", "brow"), k=0.12)
    F.add(EllipsoidBetween((0, -1.5, 12.0), (0, -2.0, 11.55), 0.25, 0.14, SKIN, "jaw", "jaw", y_hint=(0, 0, 1)),
          k=0.1)
    eye = np.array((0.2, -2.0, 12.15))
    F.sub(Ellipsoid(eye, 0.12), k=0.06, keep=False, mirror=True)
    # extremely thin limbs, long fingers
    for s in (1, -1):
        sh, el, wr, kn = M(P["shoulder"], s), M(P["elbow"], s), M(P["wrist"], s), M(P["knuckle"], s)
        F.add(Capsule(sh, el, 0.24, 0.15, SKIN, None, "upperarm"), k=0.18)
        F.add(Ellipsoid(el, 0.2, (0, 0, 0), SKIN, None, "elbow"), k=0.1)
        F.add(Capsule(el, wr, 0.15, 0.1, SKIN, None, "forearm"), k=0.08)
        F.add(FlatCapsule(wr, kn, 0.13, 0.15, up=(1, 0, 0), flat=0.5, mat=SKIN, tag="palm"), k=0.08)
        K.add_digits(F, None, kn, along=(-0.03 * s, -0.2, -1), spread_dir=(0, 1, 0), curl_dir=(-s * 0.6, -0.8, 0),
                     n=4, length=1.9, r0=0.075, r1=0.05, spread=0.3, curl=30, mat=SKIN, seed=5 + s, tag="fingers",
                     k=0.05)
        th, kq, an, to = M(P["thigh"], s), M(P["knee"], s), M(P["ankle"], s), M(P["toe"], s)
        F.add(Capsule(th, kq, 0.32, 0.18, SKIN, None, "thigh"), k=0.2)
        F.add(Ellipsoid(kq + [0, -0.12, 0], 0.22, (0, 0, 0), SKIN, None, "knee"), k=0.08)
        F.add(Capsule(kq, an, 0.17, 0.11, SKIN, None, "shin"), k=0.08)
        F.add(FlatCapsule(an + [0, 0.1, -0.2], to, 0.18, 0.13, up=(0, 0, 1), flat=0.5, mat=SKIN, tag="foot"), k=0.1)
        K.add_digits(F, None, to + [0, 0.05, 0], along=(0, -1, -0.2), spread_dir=(1, 0, 0), curl_dir=(0, 0, -1), n=4,
                     length=0.55, r0=0.07, r1=0.05, spread=0.32, curl=25, mat=SKIN, seed=9 + s, tag="foot", segs=2,
                     k=0.05)
    for s in (1, -1):
        pt.ellipsoid(Vector(eye * [s, 1, 1] + [0, 0.03, 0]), 0.085, GLINT, segs=8, rings=5, bone="head")
    return F, pt


def displacement(nz):
    def fn(co, nr):
        return 0.04 * nz.fbm(co, 0.4, 3)
    return fn


def mat_rules(nz):
    def rules(C, N, mats, owners):
        n = nz.fbm(C, 0.35, 3)
        for i, o in enumerate(owners):
            if mats[i] == FUR and n[i] < -0.15:
                mats[i] = SKIN
            elif mats[i] == SKIN and o.tag in ("skull", "neck", "upperarm") and n[i] > 0.55 and N[i, 1] > 0:
                mats[i] = FUR  # ragged dark hair clinging to the back of the head, neck and upper arms
        return mats
    return [rules]


def make_clips(rig):
    feet = {s: rig.tail("shin." + s) for s in "LR"}
    POLE = Vector((0, -1, 0))

    def plant(p, w=1.0):
        for s in "LR":
            p.ik("thigh." + s, feet[s], POLE, w)
            p.w("foot." + s)
        return p

    def breathe(p, u, n, a=1.0):
        b = math.sin(2 * math.pi * n * u)
        p.r("chest", -1.2 * a * b)
        p.l("hips", 0, 0, 0.03 * a * b)
        return p

    WK_F = 120

    def walk(u, t):
        T = WK_F / K.FPS
        p = breathe(Pose(), u, 1, 0.5)
        ph = 2 * math.pi * u
        duty = 0.7
        for s, off in (("L", 0.0), ("R", 0.5)):
            tgt, contact, ss = foot_track(u, off, duty, 1.0 * duty * T, 0.5, feet[s])
            p.ik("thigh." + s, tgt, POLE, 1.0)
            p.w("foot." + s, 0 if contact else 18 * math.sin(math.pi * ss))
        p.l("hips", 0.25 * math.sin(ph), 0, -0.25 + 0.1 * math.cos(2 * ph))
        p.r("hips", 2, -3 * math.sin(ph), 4 * math.sin(ph))
        p.r("spine", 1 + 1.5 * math.cos(2 * ph), 2 * math.sin(ph), -3 * math.sin(ph))
        p.r("chest", 1.5 * math.cos(2 * ph + 0.7), 2 * math.sin(ph), -3 * math.sin(ph))
        p.r("neck", -1.5 * math.cos(2 * ph + 1.2), 0, 2 * math.sin(ph + 0.8))
        p.r("head", -1 * math.cos(2 * ph + 1.5), 1.5 * math.sin(ph), 2 * math.sin(ph + 1.2))
        for s in "LR":
            sw = math.sin(ph + (math.pi if s == "L" else 0))
            lag = math.sin(ph - 0.8 + (math.pi if s == "L" else 0))
            p.r("upperarm." + s, 9 * sw, 0, 0)
            p.r("forearm." + s, 4 + 5 * max(0, lag))
            p.r("hand." + s, 3 * lag)
            p.r("fingers." + s, 6 + 6 * lag)
        return p

    def stand(u, t):
        p = breathe(Pose(), u, 1, 1.0)
        turn = math.sin(2 * math.pi * u)
        p.r("neck", 0, 4 * turn, 10 * turn)
        p.r("head", 2 * pnoise(u, 3), 6 * turn, 18 * turn)
        for s in "LR":
            p.r("fingers." + s, 4 * pnoise(u, 5 if s == "L" else 6))
        return plant(p)

    def look_up(u, t):
        p = breathe(Pose(), u, 1, 0.6)
        x = smootherstep_(ramp(t, 0.3, 3.4))
        p.r("hips", -3 * x)
        p.r("spine", -5 * x)
        p.r("chest", -12 * x)
        p.r("neck", -42 * x, 3 * x, 0)
        p.r("head", -60 * x + 1.5 * math.sin(t * 2.0) * x, 6 * x, 0)
        p.r("jaw", 10 * smoothstep(ramp(t, 2.8, 3.8)))
        for s in "LR":
            p.r("upperarm." + s, 6 * x)
            p.r("fingers." + s, -10 * x)
        return plant(p)

    return [
        Clip("walk", WK_F, walk, loop=True, speed=1.0, events={"step": [0, WK_F // 2]}),
        Clip("stand", 180, stand, loop=True, speed=0.0),
        Clip("look_up", 120, look_up, loop=False),
    ]


def smootherstep_(x):
    return K.smootherstep(x)


def main():
    K.reset_scene()
    nz = K.Noise3(909)
    F, pt = build(nz)
    imp = K.importance_spheres([((0, -1.7, 12.1), 0.8, 0.6)])
    body = K.body_from_field(NAME + "_Body", F, 3600, displacement(nz), smooth_iter=2, importance_fn=imp)
    K.set_verts(body, K.get_verts(body) * S)
    K.scale_field(F, S)
    pt.verts = [v * S for v in pt.verts]
    K.assign_body_materials(body, F, MATS, mat_rules(nz))
    arm = K.build_armature(NAME, bones())
    W = K.skin_body(body, arm)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    co = K.get_verts(body)
    W = K.side_cleanup(W, deform, co, eps=0.2)
    K.auto_assign_prim_bones(F, arm)
    W = K.refine_weights(arm, co, F, W, deform, sigma=0.25, own_mix=0.35)
    W = K.smooth_weights(body, W, iterations=2, factor=0.5)
    W = K.override_weights(W, deform, "jaw", K.prim_ownership_weight(co, F, {"jaw"}, 0.15))
    K.write_weights(body, deform, W)
    pobj = pt.build(NAME + "_Parts", MATS)
    K.finalize_join(body, pobj, pt, arm)
    K.uv_unwrap(body, repeat_m=3.0)
    rig = K.Rig(arm)
    entry = K.finish_creature(NAME, arm, [body], make_clips(rig), IK, eye_height=12.15 * S,
                              preview_kwargs={"contact_view": (-1.0, -0.7, 0.2)})
    K.log("DONE", NAME, entry["tris"], "tris")


if __name__ == "__main__":
    main()
