"""Boar - dark bristly wild boar (huntable, harder to approach).
Quadruped mapping: front legs use upperarm/forearm/hand, hind legs thigh/shin/foot.
Run: <python-with-bpy> creature_boar.py -- [--no-preview]
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

NAME = "Boar"
MATS = ["MNF_FurBoar", "MNF_Teeth", "MNF_EyeWet", "MNF_Flesh"]
FUR, TEETH, EYE, FLESH = MATS

P = dict(
    hips=(0, 0.36, 0.55), spine=(0, 0.06, 0.60), chest=(0, -0.24, 0.60), neck=(0, -0.36, 0.55),
    head=(0, -0.47, 0.49), head_t=(0, -0.72, 0.34),
    jaw=(0, -0.50, 0.40), jaw_t=(0, -0.68, 0.30),
    ear=(0.075, -0.44, 0.60), ear_t=(0.105, -0.40, 0.69),
    shoulder=(0.12, -0.25, 0.47), elbow=(0.125, -0.19, 0.285), wrist=(0.12, -0.235, 0.085), hoof=(0.12, -0.265, 0.0),
    thigh=(0.12, 0.33, 0.47), knee=(0.13, 0.22, 0.29), hock=(0.12, 0.35, 0.14), hhoof=(0.12, 0.32, 0.0),
)


def bones():
    b = [
        BoneDef("root", (0, 0, 0), (0, 0, 0.15), None, deform=False),
        BoneDef("hips", P["hips"], P["spine"], "root"),
        BoneDef("spine", P["spine"], P["chest"], "hips", connect=True),
        BoneDef("chest", P["chest"], P["neck"], "spine", connect=True),
        BoneDef("neck", P["neck"], P["head"], "chest", connect=True),
        BoneDef("head", P["head"], P["head_t"], "neck", connect=True),
        BoneDef("jaw", P["jaw"], P["jaw_t"], "head"),
        BoneDef("ear.L", P["ear"], P["ear_t"], "head"),
        BoneDef("upperarm.L", P["shoulder"], P["elbow"], "chest"),
        BoneDef("forearm.L", P["elbow"], P["wrist"], "upperarm.L", connect=True),
        BoneDef("hand.L", P["wrist"], P["hoof"], "forearm.L", connect=True),
        BoneDef("thigh.L", P["thigh"], P["knee"], "hips"),
        BoneDef("shin.L", P["knee"], P["hock"], "thigh.L", connect=True),
        BoneDef("foot.L", P["hock"], P["hhoof"], "shin.L", connect=True),
    ]
    return K.mirror_bones(b)


IK = [("upperarm.L", "forearm.L"), ("upperarm.R", "forearm.R"), ("thigh.L", "shin.L"), ("thigh.R", "shin.R")]


def M(p, s):
    return np.array(p, float) * np.array([s, 1, 1])


def build(nz):
    F = K.Field((-0.3, -0.82, -0.02), (0.3, 0.6, 0.86), 0.0055)
    pt = K.Parts()
    rng = np.random.RandomState(91)
    # front-heavy barrel body with a high shoulder hump
    F.add(Ellipsoid((0, 0.3, 0.5), (0.15, 0.17, 0.16), (10, 0, 0), FUR, "hips", "rump"), k=0.06)
    F.add(Ellipsoid((0, 0.05, 0.5), (0.17, 0.27, 0.19), (0, 0, 0), FUR, "spine", "barrel"), k=0.08)
    F.add(Ellipsoid((0, -0.2, 0.53), (0.165, 0.17, 0.2), (-10, 0, 0), FUR, "chest", "chest"), k=0.08)
    F.add(Ellipsoid((0, -0.17, 0.66), (0.1, 0.16, 0.09), (-10, 0, 0), FUR, "chest", "hump"), k=0.08)
    # thick neck, long wedge head with a snout disc
    F.add(Capsule((0, -0.3, 0.55), (0, -0.48, 0.47), 0.13, 0.1, FUR, "neck", "neck"), k=0.06)
    F.add(EllipsoidBetween((0, -0.42, 0.5), (0, -0.7, 0.36), 0.085, 0.075, FUR, "head", "head", y_hint=(0, 0, 1)),
          k=0.05)
    F.add(Capsule((0, -0.62, 0.38), (0, -0.74, 0.34), 0.045, 0.04, FUR, "head", "snout"), k=0.03)
    F.add(EllipsoidBetween((0, -0.745, 0.342), (0, -0.775, 0.335), 0.042, 0.035, FLESH, "head", "disc",
                           y_hint=(0, 0, 1)), k=0.012)
    for s in (1, -1):
        F.sub(Ellipsoid(M((0.016, -0.778, 0.338), s), (0.007, 0.01, 0.009)), k=0.003, keep=False)  # nostrils
    F.add(EllipsoidBetween((0, -0.5, 0.41), (0, -0.67, 0.32), 0.06, 0.035, FUR, "jaw", "jaw", y_hint=(0, 0, 1)),
          k=0.025)
    F.sub(Ellipsoid((0, -0.62, 0.34), (0.045, 0.08, 0.006), (-22, 0, 0)), k=0.004, keep=False)
    eye = np.array((0.06, -0.53, 0.5))
    # ears
    for s in (1, -1):
        e0, e1 = M(P["ear"], s), M(P["ear_t"], s)
        tag = "ear.L" if s > 0 else "ear.R"
        F.add(EllipsoidBetween(e0 + [0, 0, -0.01], e1, 0.03, 0.01, FUR, tag, tag, y_hint=(0.2 * s, -1, 0)), k=0.015)
    # legs (slender, hooved)
    for s in (1, -1):
        sh, el, wr, hf = M(P["shoulder"], s), M(P["elbow"], s), M(P["wrist"], s), M(P["hoof"], s)
        F.add(Ellipsoid(sh + [0, 0.02, 0.0], (0.07, 0.1, 0.13), (0, 0, 0), FUR, None, "upperarm"), k=0.05)
        F.add(Capsule(sh + [0, 0.01, -0.05], el, 0.06, 0.036, FUR, None, "upperarm"), k=0.04)
        F.add(Capsule(el, wr, 0.034, 0.024, FUR, None, "forearm"), k=0.02)
        F.add(Capsule(wr, hf + [0, 0, 0.012], 0.024, 0.022, FUR, None, "hand"), k=0.01)
        th, kq, hk, hh = M(P["thigh"], s), M(P["knee"], s), M(P["hock"], s), M(P["hhoof"], s)
        F.add(Ellipsoid(th + (kq - th) * 0.45, (0.075, 0.1, 0.13), (-20, 0, 0), FUR, None, "thigh"), k=0.05)
        F.add(Capsule(th + [0, 0, -0.03], kq, 0.065, 0.038, FUR, None, "thigh"), k=0.04)
        F.add(Capsule(kq, hk, 0.035, 0.024, FUR, None, "shin"), k=0.02)
        F.add(Capsule(hk, hh + [0, 0, 0.012], 0.023, 0.021, FUR, None, "foot"), k=0.01)
        for c, b in ((hf, "hand"), (hh, "foot")):
            # split hooves
            for k in (-1, 1):
                pt.cone(Vector(c + [0.009 * k, 0.0, 0.03]), Vector(c + [0.012 * k, -0.025, 0.0]), 0.014, TEETH,
                        segs=5, flat=0.7, bone=b + (".L" if s > 0 else ".R"))
    # tail
    F.add(Capsule((0, 0.45, 0.58), (0, 0.5, 0.45), 0.018, 0.01, FUR, "hips", "tail"), k=0.02)
    # eyes, tusks
    for s in (1, -1):
        pt.ellipsoid(Vector(eye * [s, 1, 1]), 0.012, EYE, segs=8, rings=5, bone="head")
        base = np.array((0.038 * s, -0.63, 0.345))
        pts = [base, base + [0.012 * s, -0.025, 0.03], base + [0.03 * s, -0.03, 0.06]]
        pt.tube([Vector(p) for p in pts], [0.011, 0.008, 0.003], TEETH, segs=5, bone="jaw")
    # bristle crest along the spine (stiff, upright)
    for i in range(26):
        t = i / 25
        c = np.array((rng.uniform(-0.02, 0.02), -0.38 + 0.68 * t, 0.0))
        c[2] = 0.62 + 0.1 * math.sin(math.pi * min(1, t * 1.6)) - 0.06 * t
        h = 0.07 * (1 - 0.6 * t) + rng.uniform(0, 0.03)
        d = np.array((rng.uniform(-0.25, 0.25), 0.35, 1.0))
        d /= np.linalg.norm(d)
        pt.cone(Vector(c - d * 0.02), Vector(c + d * h), rng.uniform(0.012, 0.018), FUR, segs=4, anchor=Vector(c),
                flat=0.5)
    return F, pt


def displacement(nz):
    def fn(co, nr):
        return 0.003 * nz.fbm(co, 4, 3) + 0.003 * np.maximum(nz(co * [1, 0.4, 1], 16, (1, 1, 1)), 0)
    return fn


def make_clips(rig):
    fr = {s: rig.tail("forearm." + s) for s in "LR"}
    hd = {s: rig.tail("shin." + s) for s in "LR"}
    PF = Vector((0, 1, 0))
    PH = Vector((0, -1, 0))

    def plant(p, offs=None):
        offs = offs or {}
        for s in "LR":
            p.ik("upperarm." + s, fr[s] + offs.get("f" + s, Vector()), PF, 1.0)
            p.w("hand." + s)
            p.ik("thigh." + s, hd[s] + offs.get("h" + s, Vector()), PH, 1.0)
            p.w("foot." + s)
        return p

    def breathe(p, u, n=4, a=1.0):
        b = math.sin(2 * math.pi * n * u)
        p.r("chest", -1.5 * a * b)
        p.r("spine", 0.8 * a * b)
        p.l("hips", 0, 0, 0.003 * a * b)
        return p

    def ears(p, u, seed, amp=8):
        p.r("ear.L", amp * pnoise(u, seed), 0, amp * pnoise(u, seed + 1))
        p.r("ear.R", amp * pnoise(u, seed + 2), 0, amp * pnoise(u, seed + 3))
        return p

    def idle(u, t):
        p = breathe(Pose(), u)
        p.r("neck", 3 * pnoise(u, 1), 0, 5 * pnoise(u, 2))
        p.r("head", 4 * pnoise(u, 3), 3 * pnoise(u, 4), 6 * pnoise(u, 5))
        tw = pulse(u, 0.6, 0.63, 0.66, 0.7)
        p.r("ear.L", -20 * tw)
        ears(p, u, 10, 6)
        sn = pulse(u, 0.2, 0.25, 0.4, 0.45)
        p.r("head", 4 * sn * math.sin(2 * math.pi * 18 * u))
        return plant(p)

    def graze(u, t):
        p = breathe(Pose(), u, 3, 0.6)
        root_ = 1 - pulse(u, 0.55, 0.65, 0.72, 0.82)
        p.l("hips", 0, 0, -0.02 * root_)
        p.r("chest", 8 * root_)
        p.r("neck", 28 * root_)
        p.r("head", 22 * root_ + 6 * root_ * math.sin(2 * math.pi * 6 * u), 0, 6 * root_ * math.sin(2 * math.pi * 3 * u))
        p.r("jaw", 6 * root_ * max(0, math.sin(2 * math.pi * 9 * u)))
        ears(p, u, 20, 8)
        return plant(p, {"fL": Vector((0, -0.03 * root_, 0)), "fR": Vector((0, -0.01 * root_, 0))})

    def quad(u, frames, speed, duty, lift_f, lift_h, low, seq, flex=0.0, pitch=0.0, bob=0.012):
        T = frames / K.FPS
        p = Pose()
        ph = 2 * math.pi * u
        p.l("hips", 0, 0, -low + bob * math.cos(2 * ph))
        p.r("hips", pitch - flex * math.sin(ph), 0, 3 * math.sin(ph))
        p.r("spine", flex * 1.2 * math.sin(ph), 0, -2 * math.sin(ph))
        p.r("chest", flex * 0.6 * math.sin(ph + 0.4))
        p.r("neck", -pitch * 0.5 + 2 * math.cos(2 * ph))
        p.r("head", -2 * math.cos(2 * ph))
        for key, off in seq.items():
            s = key[1]
            if key[0] == "f":
                tgt, contact, ss = foot_track(u, off, duty, speed * duty * T, lift_f, fr[s])
                p.ik("upperarm." + s, tgt, PF, 1.0)
                p.w("hand." + s, 0 if contact else -50 * math.sin(math.pi * ss))
            else:
                tgt, contact, ss = foot_track(u, off, duty, speed * duty * T, lift_h, hd[s])
                p.ik("thigh." + s, tgt, PH, 1.0)
                p.w("foot." + s, 0 if contact else 45 * math.sin(math.pi * ss))
        return p

    WK_F, RUN_F, CH_F = 18, 11, 10

    def walk(u, t):
        p = quad(u, WK_F, 1.0, 0.62, 0.06, 0.06, 0.045, {"hL": 0.0, "fL": 0.25, "hR": 0.5, "fR": 0.75})
        ears(p, u, 30, 5)
        return p

    def run(u, t):
        p = quad(u, RUN_F, 6.5, 0.2, 0.12, 0.12, 0.07, {"hL": 0.0, "hR": 0.08, "fL": 0.45, "fR": 0.55}, flex=10,
                 bob=0.03)
        p.r("ear.L", -35)
        p.r("ear.R", -35)
        return p

    def charge(u, t):
        p = quad(u, CH_F, 7.0, 0.2, 0.1, 0.12, 0.09, {"hL": 0.0, "hR": 0.06, "fL": 0.44, "fR": 0.52}, flex=8,
                 pitch=4, bob=0.03)
        p.r("neck", 12)
        p.r("head", 14)  # head low, tusks forward
        p.r("ear.L", -45, 0, 10)
        p.r("ear.R", -45, 0, -10)
        p.r("jaw", 6)
        return p

    def alert(u, t):
        p = breathe(Pose(), u, 5, 1.3)
        p.l("hips", 0, 0.01, 0.01)
        p.r("chest", -4)
        p.r("neck", -22)
        p.r("head", -12 + 3 * pnoise(u, 41), 0, 14 * pnoise(u, 42, (1, 2)))
        sn = 0.5 + 0.5 * math.sin(2 * math.pi * 4 * u)
        p.r("head", 3 * sn)
        p.r("ear.L", 25, 0, -15 + 6 * pnoise(u, 43))
        p.r("ear.R", 25, 0, 15 + 6 * pnoise(u, 44))
        return plant(p)

    def death(u, t):
        f = t * K.FPS
        fall = ease_in(ramp(f, 3, 16), 2)
        buck = pulse(f, 0, 3, 5, 9)
        settle = pulse(f, 16, 18, 19, 24)
        p = Pose()
        p.l("hips", 0.05 * fall, 0, 0.02 * buck - 0.33 * fall + 0.015 * settle)
        p.r("hips", -8 * buck, 86 * fall, 0)
        p.r("chest", 6 * fall, 4 * fall, 0)
        p.r("neck", -15 * buck + 12 * fall, 6 * fall)
        p.r("head", 10 * fall, 10 * fall, 8 * fall)
        p.r("jaw", 14 * fall)
        p.r("ear.L", 30 * fall)
        p.r("ear.R", 30 * fall)
        limp = smoothstep(ramp(f, 10, 26))
        kick = pulse(f, 20, 23, 25, 29)
        w = 1 - smoothstep(ramp(f, 2, 8))
        for s in "LR":
            p.ik("upperarm." + s, fr[s], PF, w)
            p.ik("thigh." + s, hd[s], PH, w)
            p.r("upperarm." + s, -25 * limp)
            p.r("forearm." + s, 20 * limp)
            p.r("thigh." + s, 30 * limp)
            p.r("shin." + s, -15 * limp)
        p.r("thigh.L", -25 * kick)
        return p

    return [
        Clip("idle", 90, idle, loop=True, speed=0.0),
        Clip("graze", 90, graze, loop=True, speed=0.0),
        Clip("walk", WK_F, walk, loop=True, speed=1.0, events={"step": [0, WK_F // 2]}),
        Clip("run", RUN_F, run, loop=True, speed=6.5),
        Clip("alert", 60, alert, loop=True, speed=0.0),
        Clip("charge", CH_F, charge, loop=True, speed=7.0),
        Clip("death", 30, death, loop=False),
    ]


def main():
    K.reset_scene()
    nz = K.Noise3(707)
    F, pt = build(nz)
    imp = K.importance_spheres([((0, -0.62, 0.4), 0.14, 0.8)])
    body = K.body_from_field(NAME + "_Body", F, 5200, displacement(nz), smooth_iter=2, importance_fn=imp)
    K.assign_body_materials(body, F, MATS, [])
    arm = K.build_armature(NAME, bones())
    W = K.skin_body(body, arm)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    co = K.get_verts(body)
    W = K.side_cleanup(W, deform, co, eps=0.015)
    K.auto_assign_prim_bones(F, arm)
    W = K.refine_weights(arm, co, F, W, deform, sigma=0.012, own_mix=0.35)
    W = K.smooth_weights(body, W, iterations=2, factor=0.5)
    W = K.override_weights(W, deform, "jaw", K.prim_ownership_weight(co, F, {"jaw"}, 0.008))
    for s in "LR":
        w = K.prim_ownership_weight(co, F, {"ear." + s}, 0.008) * np.clip((co[:, 2] - 0.6) / 0.02, 0, 1)
        W = K.override_weights(W, deform, "ear." + s, w)
    K.write_weights(body, deform, W)
    K.add_tufts(body, pt, MATS, FUR, count=110, seed=19, length=(0.025, 0.05), radius=(0.007, 0.012), droop=0.35,
                max_nz=1.1, normal_mix=1.0)
    pobj = pt.build(NAME + "_Parts", MATS)
    K.finalize_join(body, pobj, pt, arm)
    K.uv_unwrap(body, repeat_m=0.35)
    rig = K.Rig(arm)
    entry = K.finish_creature(NAME, arm, [body], make_clips(rig), IK, eye_height=0.5,
                              preview_kwargs={"contact_view": (-1.0, -0.55, 0.3)})
    K.log("DONE", NAME, entry["tris"], "tris")


if __name__ == "__main__":
    main()
