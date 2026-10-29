"""Gloomrat - small pale-eyed burrow rodent (mines & forest burrows), flees.
Extra bones (not in the standard set): tail.01 -> tail.02 -> tail.03 (children of hips).
Run: <python-with-bpy> creature_gloomrat.py -- [--no-preview]
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

NAME = "Gloomrat"
MATS = ["MNF_FurDark", "MNF_EyeGlint", "MNF_Flesh"]
FUR, GLINT, FLESH = MATS

P = dict(
    hips=(0, 0.06, 0.05), spine=(0, 0.0, 0.056), chest=(0, -0.05, 0.053), neck=(0, -0.078, 0.05),
    head=(0, -0.098, 0.05), head_t=(0, -0.152, 0.034),
    jaw=(0, -0.105, 0.036), jaw_t=(0, -0.14, 0.026),
    t1=(0, 0.098, 0.04), t2=(0, 0.145, 0.028), t3=(0, 0.19, 0.018), t4=(0, 0.235, 0.012),
    shoulder=(0.019, -0.05, 0.04), elbow=(0.021, -0.043, 0.022), wrist=(0.02, -0.055, 0.007), paw=(0.02, -0.068, 0.002),
    thigh=(0.022, 0.055, 0.04), knee=(0.027, 0.034, 0.024), hock=(0.025, 0.07, 0.008), toe=(0.025, 0.04, 0.002),
)
EYE = np.array((0.0165, -0.117, 0.053))


def bones():
    b = [
        BoneDef("root", (0, 0, 0), (0, 0, 0.03), None, deform=False),
        BoneDef("hips", P["hips"], P["spine"], "root"),
        BoneDef("spine", P["spine"], P["chest"], "hips", connect=True),
        BoneDef("chest", P["chest"], P["neck"], "spine", connect=True),
        BoneDef("neck", P["neck"], P["head"], "chest", connect=True),
        BoneDef("head", P["head"], P["head_t"], "neck", connect=True),
        BoneDef("jaw", P["jaw"], P["jaw_t"], "head"),
        BoneDef("tail.01", P["t1"], P["t2"], "hips"),
        BoneDef("tail.02", P["t2"], P["t3"], "tail.01", connect=True),
        BoneDef("tail.03", P["t3"], P["t4"], "tail.02", connect=True),
        BoneDef("upperarm.L", P["shoulder"], P["elbow"], "chest"),
        BoneDef("forearm.L", P["elbow"], P["wrist"], "upperarm.L", connect=True),
        BoneDef("hand.L", P["wrist"], P["paw"], "forearm.L", connect=True),
        BoneDef("thigh.L", P["thigh"], P["knee"], "hips"),
        BoneDef("shin.L", P["knee"], P["hock"], "thigh.L", connect=True),
        BoneDef("foot.L", P["hock"], P["toe"], "shin.L", connect=True),
    ]
    return K.mirror_bones(b)


IK = [("upperarm.L", "forearm.L"), ("upperarm.R", "forearm.R"), ("thigh.L", "shin.L"), ("thigh.R", "shin.R")]


def M(p, s):
    return np.array(p, float) * np.array([s, 1, 1])


def build(nz):
    F = K.Field((-0.05, -0.175, -0.008), (0.05, 0.25, 0.095), 0.00115)
    pt = K.Parts()
    F.add(Ellipsoid((0, 0.045, 0.045), (0.031, 0.045, 0.035), (8, 0, 0), FUR, "hips", "rump"), k=0.015)
    F.add(Ellipsoid((0, -0.012, 0.046), (0.028, 0.05, 0.031), (-4, 0, 0), FUR, "spine", "body"), k=0.02)
    F.add(Ellipsoid((0, -0.06, 0.044), (0.022, 0.03, 0.026), (-15, 0, 0), FUR, "chest", "chest"), k=0.015)
    F.add(EllipsoidBetween((0, -0.085, 0.052), (0, -0.155, 0.033), 0.018, 0.017, FUR, "head", "head",
                           y_hint=(0, 0, 1)), k=0.012)
    F.add(Ellipsoid((0, -0.157, 0.032), (0.0055, 0.006, 0.005), (0, 0, 0), FLESH, "head", "nose"), k=0.004)
    F.add(EllipsoidBetween((0, -0.1, 0.037), (0, -0.14, 0.027), 0.009, 0.005, FUR, "jaw", "jaw", y_hint=(0, 0, 1)),
          k=0.005)
    for s in (1, -1):
        F.add(EllipsoidBetween(M((0.010, -0.092, 0.054), s), M((0.019, -0.088, 0.075), s), 0.009, 0.0028, FLESH,
                               "head", "ear", y_hint=(0.4 * s, -1, 0)), k=0.004)
        sh, el, wr, pw = M(P["shoulder"], s), M(P["elbow"], s), M(P["wrist"], s), M(P["paw"], s)
        F.add(Capsule(sh, el, 0.008, 0.005, FUR, None, "upperarm"), k=0.006)
        F.add(Capsule(el, wr, 0.0045, 0.0035, FUR, None, "forearm"), k=0.003)
        F.add(FlatCapsule(wr, pw, 0.0035, 0.004, up=(0, 0, 1), flat=0.6, mat=FLESH, tag="hand"), k=0.002)
        th, kq, hk, to = M(P["thigh"], s), M(P["knee"], s), M(P["hock"], s), M(P["toe"], s)
        F.add(Ellipsoid(th + (kq - th) * 0.4, (0.012, 0.017, 0.017), (-20, 0, 0), FUR, None, "thigh"), k=0.008)
        F.add(Capsule(th, kq, 0.009, 0.006, FUR, None, "thigh"), k=0.006)
        F.add(Capsule(kq, hk, 0.005, 0.0035, FUR, None, "shin"), k=0.003)
        F.add(FlatCapsule(hk, to, 0.004, 0.0045, up=(0, 0, 1), flat=0.6, mat=FLESH, tag="foot"), k=0.002)
    # naked tail
    F.add(Capsule(P["t1"] + np.array((0, -0.01, 0.003)), P["t2"], 0.0055, 0.0042, FLESH, "tail.01", "tail"), k=0.004)
    F.add(Capsule(P["t2"], P["t3"], 0.0042, 0.003, FLESH, "tail.02", "tail"), k=0.002)
    F.add(Capsule(P["t3"], P["t4"], 0.003, 0.0015, FLESH, "tail.03", "tail"), k=0.002)
    # big pale eyes
    F.sub(Ellipsoid(EYE * [1, 1, 1] + [0.002, 0, 0], 0.0062), k=0.002, keep=False, mirror=True)
    for s in (1, -1):
        pt.ellipsoid(Vector(EYE * [s, 1, 1]), (0.0058, 0.0062, 0.0058), GLINT, segs=8, rings=6, bone="head")
        for k in range(4):
            b0 = Vector((0.006 * s, -0.15, 0.036 - 0.002 * k))
            tip = b0 + Vector((0.03 * s, 0.006 + 0.004 * k, -0.004 + 0.003 * k))
            pt.tube([b0, (b0 + tip) / 2, tip], [0.0004, 0.0003, 0.0001], FUR, segs=3, bone="head", cap=False)
    return F, pt


def displacement(nz):
    def fn(co, nr):
        return 0.0004 * nz.fbm(co, 40, 2) + 0.0005 * np.maximum(nz(co, 90, (1, 1, 1)), 0)
    return fn


def make_clips(rig):
    fr = {s: rig.tail("forearm." + s) for s in "LR"}
    hd = {s: rig.tail("shin." + s) for s in "LR"}
    PF = Vector((0, 1, 0))
    PH = Vector((0, -1, 0))

    def plant(p, offs=None, w=1.0):
        offs = offs or {}
        for s in "LR":
            p.ik("upperarm." + s, fr[s] + offs.get("f" + s, Vector()), PF, w)
            p.w("hand." + s)
            p.ik("thigh." + s, hd[s] + offs.get("h" + s, Vector()), PH, w)
            p.w("foot." + s)
        return p

    def tail(p, u, amp=1.0, n=1, ph=0.0):
        for i, b in enumerate(("tail.01", "tail.02", "tail.03")):
            p.r(b, 2 * amp, 0, amp * 10 * math.sin(2 * math.pi * (n * u + ph) - i * 0.8))
        return p

    def sniff(p, u, n=12, amp=1.0):
        p.r("head", amp * 3 * math.sin(2 * math.pi * n * u), 0, 0)
        p.r("jaw", amp * 2 * max(0, math.sin(2 * math.pi * n * u)))
        return p

    def idle(u, t):
        p = Pose()
        b = math.sin(2 * math.pi * 8 * u)
        p.r("chest", 2 * b)
        p.l("hips", 0, 0, 0.0004 * b)
        look = pnoise(u, 3, (1, 2))
        p.r("neck", -6 * pulse(u, 0.4, 0.45, 0.6, 0.66), 0, 20 * look)
        p.r("head", -10 * pulse(u, 0.4, 0.45, 0.6, 0.66), 0, 12 * look)
        sniff(p, u, 15, 0.5 + 0.5 * pulse(u, 0.1, 0.13, 0.3, 0.35) + 0.5 * pulse(u, 0.7, 0.72, 0.85, 0.9))
        tail(p, u, 0.6, 1)
        return plant(p)

    RUN_F = 6

    def run(u, t):
        T = RUN_F / K.FPS
        p = Pose()
        ph = 2 * math.pi * u
        p.l("hips", 0, 0, 0.004 + 0.006 * max(0, math.sin(ph + 0.4)))
        p.r("hips", -10 * math.sin(ph))
        p.r("spine", 14 * math.sin(ph))
        p.r("chest", 8 * math.sin(ph + 0.4))
        p.r("neck", -6 * math.sin(ph + 0.8))
        p.r("head", 4 * math.sin(ph + 1.0))
        for key, off in {"hL": 0.0, "hR": 0.06, "fL": 0.5, "fR": 0.56}.items():
            s = key[1]
            if key[0] == "f":
                tgt, contact, ss = foot_track(u, off, 0.3, 4.0 * 0.3 * T * 0.25, 0.012, fr[s] + Vector((0, -0.01, 0)))
                p.ik("upperarm." + s, tgt, PF, 1.0)
                p.w("hand." + s, 0 if contact else -40 * math.sin(math.pi * ss))
            else:
                tgt, contact, ss = foot_track(u, off, 0.3, 4.0 * 0.3 * T * 0.25, 0.014, hd[s] + Vector((0, 0.008, 0)))
                p.ik("thigh." + s, tgt, PH, 1.0)
                p.w("foot." + s, 0 if contact else 50 * math.sin(math.pi * ss))
        for i, b in enumerate(("tail.01", "tail.02", "tail.03")):
            p.r(b, 6 + 6 * math.sin(ph - i), 0, 4 * math.sin(ph - i * 0.7))
        return p

    # peek / hide: the hole is centred under the creature's chest (origin); z<0 is inside the burrow
    def peek_end():
        p = Pose()
        p.l("hips", 0, 0.03, -0.075)
        p.r("hips", -55)
        p.r("spine", -10)
        p.r("chest", 20)
        p.r("neck", 30)
        p.r("head", 18)
        for s in "LR":
            p.ik("upperarm." + s, fr[s] + Vector((0, -0.02, 0.0)), PF, 1.0)
            p.w("hand." + s)
            p.r("thigh." + s, -40)
            p.r("shin." + s, 50)
        return p

    def peek(u, t):
        f = t * K.FPS
        end = peek_end()
        start = end.copy().l("hips", 0, 0, -0.16)
        p = keyed(f, [(0, start), (14, start.add(Pose().l("hips", 0, 0, 0.07))), (24, end), (60, end)], mode='cr')
        # paws hook over the rim once out
        w = smoothstep(ramp(f, 16, 24))
        for s in "LR":
            p.ik("upperarm." + s, fr[s] + Vector((0, -0.02, 0)), PF, w)
            p.r("upperarm." + s, -60 * (1 - w))
        look = math.sin(2 * math.pi * (f - 24) / 36) if f > 24 else 0
        p.r("neck", 0, 0, 25 * look * smoothstep(ramp(f, 24, 32)))
        sniff(p, f / 60.0, 30, smoothstep(ramp(f, 20, 26)))
        tail(p, f / 60.0, 0.3, 2)
        return p

    def hide(u, t):
        f = t * K.FPS
        a = peek_end()
        b = a.copy().l("hips", 0, -0.01, -0.17).r("hips", -25).r("neck", -30).r("head", -20)
        x = ease_in(ramp(f, 1, 9), 1.6)
        p = K.combo([a, b], [1 - x, x])
        for s in "LR":
            p.ik("upperarm." + s, fr[s] + Vector((0, -0.02, 0)), PF, 1 - smoothstep(ramp(f, 1, 5)))
            p.r("upperarm." + s, -50 * x)
        return p

    return [
        Clip("idle", 90, idle, loop=True, speed=0.0),
        Clip("run", RUN_F, run, loop=True, speed=4.0),
        Clip("peek", 60, peek, loop=False, notes="Starts fully below z=0 (inside the hole at the origin), ends "
                                                  "half out with front paws on the rim."),
        Clip("hide", 15, hide, loop=False, notes="Starts on the final pose of 'peek', ends fully below z=0."),
    ]


def main():
    K.reset_scene()
    nz = K.Noise3(808)
    F, pt = build(nz)
    imp = K.importance_spheres([((0, -0.12, 0.045), 0.03, 0.8)])
    body = K.body_from_field(NAME + "_Body", F, 3200, displacement(nz), smooth_iter=2, importance_fn=imp)
    K.assign_body_materials(body, F, MATS, [])
    arm = K.build_armature(NAME, bones())
    W = K.skin_body(body, arm)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    co = K.get_verts(body)
    W = K.side_cleanup(W, deform, co, eps=0.002)
    K.auto_assign_prim_bones(F, arm)
    W = K.refine_weights(arm, co, F, W, deform, sigma=0.003, own_mix=0.35)
    W = K.smooth_weights(body, W, iterations=2, factor=0.5)
    W = K.override_weights(W, deform, "jaw", K.prim_ownership_weight(co, F, {"jaw"}, 0.002))
    K.write_weights(body, deform, W)
    K.add_tufts(body, pt, MATS, FUR, count=40, seed=3, length=(0.005, 0.01), radius=(0.0015, 0.0025), droop=0.4,
                max_nz=1.1, normal_mix=1.0)
    pobj = pt.build(NAME + "_Parts", MATS)
    K.finalize_join(body, pobj, pt, arm)
    K.uv_unwrap(body, repeat_m=0.12)
    rig = K.Rig(arm)
    entry = K.finish_creature(NAME, arm, [body], make_clips(rig), IK, eye_height=float(EYE[2]),
                              preview_kwargs={"contact_view": (-1.0, -0.6, 0.45)},
                              extra_manifest={"extra_bones": ["tail.01", "tail.02", "tail.03"]})
    K.log("DONE", NAME, entry["tris"], "tris")


if __name__ == "__main__":
    main()
