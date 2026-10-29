"""Rabbit - ordinary huntable wildlife and the Falsekin disguise rig.
Run: <python-with-bpy> creature_rabbit.py -- [--no-preview]
"""
import bpy  # noqa: F401  (must come before mathutils)
import os
import sys
import math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from mathutils import Vector
import mnf_creaturekit as K
from mnf_creaturekit import (Capsule, Ellipsoid, FlatCapsule, BoneDef, Pose, Clip, smoothstep, pulse, ramp,
                             pnoise, foot_track)

NAME = "Rabbit"
MATS = ["MNF_FurRabbit", "MNF_EyeWet", "MNF_Flesh"]
FUR, EYE, FLESH = MATS

# ---------------------------------------------------------------------------------------------
# Skeleton (rest = relaxed crouch, facing -Y)
# ---------------------------------------------------------------------------------------------
P = dict(
    hip=(0, 0.085, 0.105), spine=(0, 0.02, 0.108), chest=(0, -0.05, 0.102), neck=(0, -0.092, 0.118),
    head=(0, -0.128, 0.152), head_t=(0, -0.19, 0.150), nose=(0, -0.183, 0.146), nose_t=(0, -0.207, 0.143),
    ear=(0.013, -0.133, 0.188), ear_t=(0.03, -0.098, 0.283),
    eye=(0.034, -0.153, 0.166),
    shoulder=(0.03, -0.062, 0.088), elbow=(0.031, -0.052, 0.046), wrist=(0.029, -0.083, 0.013),
    ftoe=(0.029, -0.108, 0.006),
    thigh=(0.036, 0.088, 0.098), knee=(0.05, 0.028, 0.062), hock=(0.044, 0.106, 0.016),
    htoe=(0.040, 0.004, 0.008),
)


def bones():
    b = [
        BoneDef("root", (0, 0, 0), (0, 0, 0.06), None, deform=False),
        BoneDef("hips", P["hip"], P["spine"], "root"),
        BoneDef("spine", P["spine"], P["chest"], "hips", connect=True),
        BoneDef("chest", P["chest"], P["neck"], "spine", connect=True),
        BoneDef("neck", P["neck"], P["head"], "chest", connect=True),
        BoneDef("head", P["head"], P["head_t"], "neck", connect=True),
        BoneDef("nose", P["nose"], P["nose_t"], "head"),
        BoneDef("ear.L", P["ear"], P["ear_t"], "head"),
        BoneDef("eyelid.L", P["eye"], Vector(P["eye"]) + Vector((0, -0.02, 0)), "head"),
        BoneDef("upperarm.L", P["shoulder"], P["elbow"], "chest"),
        BoneDef("forearm.L", P["elbow"], P["wrist"], "upperarm.L", connect=True),
        BoneDef("hand.L", P["wrist"], P["ftoe"], "forearm.L", connect=True),
        BoneDef("thigh.L", P["thigh"], P["knee"], "hips"),
        BoneDef("shin.L", P["knee"], P["hock"], "thigh.L", connect=True),
        BoneDef("foot.L", P["hock"], P["htoe"], "shin.L", connect=True),
    ]
    return K.mirror_bones(b)


IK = [("upperarm.L", "forearm.L"), ("upperarm.R", "forearm.R"), ("thigh.L", "shin.L"), ("thigh.R", "shin.R")]


# ---------------------------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------------------------
def build_field():
    F = K.Field((-0.085, -0.235, -0.012), (0.085, 0.205, 0.31), 0.0024)
    # torso: rump, belly, chest
    F.add(Ellipsoid((0, 0.072, 0.098), (0.068, 0.082, 0.078), (8, 0, 0), FUR, "hips", "hips"), k=0.03)
    F.add(Ellipsoid((0, 0.005, 0.094), (0.058, 0.085, 0.066), (-4, 0, 0), FUR, "spine", "spine"), k=0.04)
    F.add(Ellipsoid((0, -0.062, 0.092), (0.048, 0.055, 0.062), (-18, 0, 0), FUR, "chest", "chest"), k=0.035)
    # neck + head
    F.add(Capsule((0, -0.085, 0.112), (0, -0.128, 0.148), 0.036, 0.032, FUR, "neck", "neck"), k=0.03)
    F.add(Ellipsoid((0, -0.147, 0.156), (0.037, 0.05, 0.041), (12, 0, 0), FUR, "head", "head"), k=0.02)
    F.add(Ellipsoid((0, -0.186, 0.142), (0.025, 0.03, 0.026), (8, 0, 0), FUR, "nose", "snout"), k=0.02)
    F.add(Ellipsoid((0.021, -0.163, 0.138), (0.021, 0.026, 0.022), (0, 0, 0), FUR, "head", "head"), k=0.015,
          mirror=True)
    # ears: wide spoon-shaped ellipsoids with a cupped front (flesh lined)
    for s in (1, -1):
        e0 = np.array(P["ear"]) * [s, 1, 1]
        e1 = np.array(P["ear_t"]) * [s, 1, 1]
        tag = "ear.L" if s > 0 else "ear.R"
        F.add(K.EllipsoidBetween(e0 + [0, 0.004, -0.012], e1 + [0, 0.002, 0.004], 0.0175, 0.0062, FUR, tag, tag,
                                 y_hint=(0.3 * s, -1, 0)), k=0.012)
        mid = e0 + (e1 - e0) * 0.58 + np.array([0.0, -0.0065, 0])
        cav = K.EllipsoidBetween(mid - (e1 - e0) * 0.33, mid + (e1 - e0) * 0.3, 0.0105, 0.0042, FLESH,
                                 y_hint=(0.3 * s, -1, 0))
        F.sub(cav, k=0.003)
    # front legs
    for s in (1, -1):
        m = np.array([s, 1, 1])
        F.add(Capsule(np.array(P["shoulder"]) * m, np.array(P["elbow"]) * m, 0.02, 0.014, FUR,
                      tag="upperarm"), k=0.02)
        F.add(Capsule(np.array(P["elbow"]) * m, np.array(P["wrist"]) * m, 0.012, 0.0095, FUR, tag="forearm"),
              k=0.008)
        F.add(Ellipsoid((np.array(P["wrist"]) + np.array(P["ftoe"])) / 2 * m + [0, 0, -0.002],
                        (0.011, 0.018, 0.0085), (0, 0, 0), FUR, tag="hand"), k=0.008)
        # hind legs
        F.add(Ellipsoid(np.array((0.043, 0.06, 0.082)) * m, (0.036, 0.052, 0.05), (25, 0, 0), FUR, tag="thigh"),
              k=0.03)
        F.add(Capsule(np.array(P["knee"]) * m, np.array(P["hock"]) * m, 0.018, 0.011, FUR, tag="shin"), k=0.012)
        F.add(FlatCapsule(np.array(P["hock"]) * m + [0, 0, 0.002], np.array(P["htoe"]) * m + [0, 0, 0.003],
                          0.012, 0.011, up=(0, 0, 1), flat=0.7, mat=FUR, tag="foot"), k=0.01)
    # tail puff
    F.add(Ellipsoid((0, 0.152, 0.112), (0.022, 0.018, 0.022), (0, 0, 0), FUR, tag="tail"), k=0.012)
    return F


def displacement(nz):
    def fn(co, nr):
        return 0.0007 * nz.fbm(co, 60, 2) + 0.0012 * nz(co, 18)
    return fn


def mat_rules():
    def inner_ear(C, N, mats, owners):
        for i, o in enumerate(owners):
            if o.tag in ("ear.L", "ear.R"):
                # front face of the ear, away from the base
                if N[i, 1] < -0.55 and C[i, 2] > 0.2:
                    mats[i] = FLESH
        return mats

    def nose(C, N, mats, owners):
        d = np.linalg.norm(C - np.array([0, -0.211, 0.147]), axis=1)
        mats[d < 0.0075] = FLESH
        return mats
    return [nose]


def build_parts():
    pt = K.Parts()
    for s, side in ((1, "L"), (-1, "R")):
        eye = Vector(P["eye"]) * 1
        eye.x *= s
        pt.ellipsoid(eye, (0.0125, 0.0135, 0.0125), EYE, segs=10, rings=7, bone="head")
        # eyelid: spherical cap shell, rest = open (pulled up and inward into the head)
        lid_r = 0.0142
        pole = Vector((-0.62 * s, 0.05, 0.78)).normalized()
        cap_pts = []
        segs, rings, ext = 10, 4, math.radians(88)
        # local frame for the cap around pole
        x = pole.cross(Vector((0, 1, 0))).normalized()
        y = pole.cross(x).normalized()
        verts = [eye + pole * lid_r]
        for j in range(1, rings + 1):
            th = ext * j / rings
            for i in range(segs):
                ph = 2 * math.pi * i / segs
                d = pole * math.cos(th) + (x * math.cos(ph) + y * math.sin(ph)) * math.sin(th)
                verts.append(eye + d * lid_r)
        faces = []
        for i in range(segs):
            faces.append([0, 1 + i, 1 + (i + 1) % segs])
        for j in range(rings - 1):
            for i in range(segs):
                a = 1 + j * segs + i
                b = 1 + j * segs + (i + 1) % segs
                c = 1 + (j + 1) * segs + (i + 1) % segs
                d = 1 + (j + 1) * segs + i
                faces.append([a, d, c])
                faces.append([a, c, b])
        pt._add(verts, faces, FUR, bone="eyelid." + side)
        # claws (tiny) on the front paws, tufts of fur on the cheeks
        toe = Vector(P["ftoe"])
        toe.x *= s
        for k in (-1, 0, 1):
            b0 = toe + Vector((0.004 * k, 0.002, 0.003))
            pt.cone(b0, b0 + Vector((0.002 * k, -0.007, -0.003)), 0.002, FLESH, segs=4, bone="hand." + side)
    # whiskers (very thin, few)
    for s in (1, -1):
        for k in range(3):
            b0 = Vector((0.016 * s, -0.198, 0.138 - 0.003 * k))
            tip = b0 + Vector((0.045 * s, 0.01 + 0.008 * k, -0.006 + 0.006 * k))
            pt.tube([b0, (b0 + tip) / 2, tip], [0.0007, 0.0005, 0.0002], FUR, segs=3, bone="nose", cap=False)
    return pt


# ---------------------------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------------------------
def make_clips(rig):
    rest = {n: rig.tail(n) for n in ("forearm.L", "forearm.R", "shin.L", "shin.R")}
    POLE_F = Vector((0, 1, 0))
    POLE_H = Vector((0, -1, 0.2))

    def plant(p, wf=1.0, wh=1.0, offs=None):
        offs = offs or {}
        for n, up in (("forearm.L", "upperarm.L"), ("forearm.R", "upperarm.R")):
            p.ik(up, rest[n] + offs.get(up, Vector()), POLE_F, wf)
        for n, up in (("shin.L", "thigh.L"), ("shin.R", "thigh.R")):
            p.ik(up, rest[n] + offs.get(up, Vector()), POLE_H, wh)
            p.w("foot." + up[-1])
        return p

    def breathing(p, u, n=6, amp=1.0):
        b = math.sin(2 * math.pi * n * u)
        p.r("spine", 1.2 * amp * b)
        p.r("chest", -1.6 * amp * b)
        p.l("hips", 0, 0, 0.0008 * amp * b)
        return p

    def nose_twitch(p, u, env):
        p.r("nose", 7 * env * math.sin(2 * math.pi * 30 * u), 0, 0)
        return p

    # ---- idle (3 s)
    def idle(u, t):
        p = Pose()
        breathing(p, u)
        env = pulse(u, 0.05, 0.08, 0.25, 0.3) + pulse(u, 0.55, 0.58, 0.7, 0.74)
        nose_twitch(p, u, env)
        p.r("head", 2.5 * pnoise(u, 3), 3 * pnoise(u, 4), 4 * pnoise(u, 5))
        p.r("neck", 1.5 * pnoise(u, 6))
        flick = pulse(u, 0.42, 0.45, 0.47, 0.53)
        p.r("ear.R", -25 * flick, 0, -20 * flick)
        p.r("ear.L", 4 * pnoise(u, 7), 0, 5 * pnoise(u, 8))
        p.r("ear.R", 3 * pnoise(u, 9))
        return plant(p)

    # ---- graze (2.5 s): head down nibbling, one look-up mid cycle
    def graze(u, t):
        p = Pose()
        breathing(p, u, n=4, amp=0.6)
        down = 1 - pulse(u, 0.42, 0.52, 0.62, 0.74)  # lifts head once
        p.l("hips", 0, 0, -0.012 * down)
        p.r("hips", 6 * down)
        p.r("spine", 6 * down)
        p.r("chest", 10 * down)
        p.r("neck", 16 * down - 6 * (1 - down))
        p.r("head", 22 * down + 3 * math.sin(2 * math.pi * 12 * u) * down, 0, 8 * (1 - down) * math.sin(2 * math.pi * u))
        nose_twitch(p, u, 0.5 + 0.5 * down)
        p.r("ear.L", -30 * down + 8 * (1 - down), 0, -8 * down)
        p.r("ear.R", -26 * down + 8 * (1 - down), 0, 8 * down)
        # front paws shuffle slightly forward with the reach
        o = {"upperarm.L": Vector((0, -0.012 * down, 0)), "upperarm.R": Vector((0, -0.008 * down, 0))}
        return plant(p, offs=o)

    # ---- hop: one hop 14 frames, 1.6 m/s
    HOP_F = 14
    hop_T = HOP_F / K.FPS
    hop_v = 1.6

    def hopfn(u, t):
        p = Pose()
        # vertical: flight arc between hind push-off (u=0) and front landing (u=0.5)
        fl = math.sin(math.pi * min(u / 0.5, 1.0)) if u < 0.5 else 0.0
        comp = pulse(u, 0.5, 0.62, 0.75, 1.0)  # crouch while gathered
        p.l("hips", 0, 0, 0.045 * fl - 0.012 * comp)
        # body pitch: nose up at push off, nose down at landing
        pitch = -7 * math.sin(2 * math.pi * u) + 4 * comp
        p.r("hips", pitch)
        p.r("spine", -8 * fl + 10 * comp)
        p.r("chest", 6 * math.sin(2 * math.pi * (u - 0.15)))
        p.r("neck", -0.6 * pitch)
        p.r("head", -0.4 * pitch)
        p.r("ear.L", 25 * fl + 5)
        p.r("ear.R", 25 * fl + 5)
        for side, off in (("L", 0.5), ("R", 0.535)):
            tgt, contact, s = foot_track(u, off, 0.22, hop_v * 0.22 * hop_T, 0.035, rest["forearm." + side])
            p.ik("upperarm." + side, tgt, POLE_F, 1.0)
            p.r("hand." + side, -40 * (0 if contact else math.sin(math.pi * s)))
        for side, off in (("L", 0.68), ("R", 0.69)):
            tgt, contact, s = foot_track(u, off, 0.3, hop_v * 0.3 * hop_T, 0.05, rest["shin." + side])
            p.ik("thigh." + side, tgt, POLE_H, 1.0)
            p.w("foot." + side, (0 if contact else 55 * math.sin(math.pi * s ** 0.7)), 0, 0)
        return p

    # ---- run: bounding gallop, 10 frames, 6 m/s
    RUN_F = 10
    run_T = RUN_F / K.FPS
    run_v = 6.0

    def runfn(u, t):
        p = Pose()
        fl = math.sin(2 * math.pi * (u - 0.1))
        p.l("hips", 0, 0, 0.022 + 0.03 * max(0, math.sin(2 * math.pi * (u + 0.1))))
        # spine flex / extension (gather and stretch)
        flex = math.sin(2 * math.pi * u)
        p.r("hips", -10 * flex)
        p.r("spine", 14 * flex)
        p.r("chest", 8 * flex)
        p.r("neck", -10 - 6 * flex)
        p.r("head", 14 + 4 * flex)
        p.r("ear.L", 55)
        p.r("ear.R", 52)
        for side, off in (("L", 0.45), ("R", 0.5)):
            r = rest["forearm." + side] + Vector((0, -0.03, 0))
            tgt, contact, s = foot_track(u, off, 0.14, run_v * 0.14 * run_T, 0.05, r)
            p.ik("upperarm." + side, tgt, POLE_F, 1.0)
            p.r("hand." + side, -60 * (0 if contact else math.sin(math.pi * s)))
        for side, off in (("L", 0.82), ("R", 0.86)):
            r = rest["shin." + side] + Vector((0, -0.04, 0.01))
            tgt, contact, s = foot_track(u, off, 0.14, run_v * 0.14 * run_T, 0.06, r)
            p.ik("thigh." + side, tgt, POLE_H, 1.0)
            p.w("foot." + side, (0 if contact else 70 * math.sin(math.pi * s ** 0.6)), 0, 0)
        return p

    # ---- alert (2 s): sits up, ears up, scanning
    def alert(u, t):
        p = Pose()
        breathing(p, u, n=5, amp=1.4)
        p.r("hips", -42)
        p.l("hips", 0, 0.004, 0.035)
        p.r("spine", -16)
        p.r("chest", -10)
        p.r("neck", 32)
        p.r("head", 30 + 3 * pnoise(u, 11))
        look = 22 * pnoise(u, 12, (1, 2))
        p.r("neck", 0, 0, look * 0.5)
        p.r("head", 0, 0, look * 0.7)
        # ears straight up and swivelling
        p.r("ear.L", 28, 0, -10 + 18 * pnoise(u, 13))
        p.r("ear.R", 28, 0, 10 + 18 * pnoise(u, 14))
        nose_twitch(p, u, 0.7 + 0.3 * math.sin(2 * math.pi * 2 * u))
        # front paws tucked to the chest
        for side in ("L", "R"):
            p.r("upperarm." + side, -45)
            p.r("forearm." + side, 70)
            p.r("hand." + side, 40)
        for n, up in (("shin.L", "thigh.L"), ("shin.R", "thigh.R")):
            p.ik(up, rest[n], POLE_H, 1.0)
            p.w("foot." + up[-1])
        return p

    # ---- blink (eyelids only)
    def blink(u, t):
        p = Pose()
        c = math.sin(math.pi * u) ** 0.6
        p.w("eyelid.L", 0, 72 * c, 0)
        p.w("eyelid.R", 0, -72 * c, 0)
        return p

    # ---- death (0.8 s): kicks, falls on its side
    def death(u, t):
        p = Pose()
        fall = smoothstep(ramp(t, 0.08, 0.55))
        jerk = pulse(t, 0.0, 0.05, 0.1, 0.25)
        p.l("hips", -0.02 * fall, 0, 0.015 * jerk - 0.036 * fall)
        p.r("hips", -10 * jerk, -88 * fall, 0)
        p.r("spine", 0, -6 * fall, 0)
        p.r("chest", 8 * fall)
        p.r("neck", -15 * jerk + 25 * fall, -10 * fall)
        p.r("head", 25 * fall, -15 * fall, 10 * fall)
        settle = pulse(t, 0.5, 0.58, 0.62, 0.78)
        p.r("ear.L", 30 * fall)
        p.r("ear.R", 45 * fall)
        for side, sg in (("L", 1), ("R", -1)):
            p.r("upperarm." + side, -25 * fall + 10 * settle)
            p.r("forearm." + side, 30 * fall)
            p.r("thigh." + side, -20 * jerk + 35 * fall)
            p.r("shin." + side, 20 * fall - 25 * settle)
            p.r("foot." + side, -30 * fall)
        # last twitch of a hind leg
        tw = pulse(t, 0.6, 0.65, 0.67, 0.75)
        p.r("thigh.L", -18 * tw)
        return p

    clips = [
        Clip("idle", 90, idle, loop=True, speed=0.0),
        Clip("graze", 75, graze, loop=True, speed=0.0),
        Clip("hop", HOP_F, hopfn, loop=True, speed=hop_v,
             events={"land": [int(round(0.5 * HOP_F))], "pushoff": [0]}),
        Clip("run", RUN_F, runfn, loop=True, speed=run_v, events={"land": [int(round(0.45 * RUN_F))]}),
        Clip("alert", 60, alert, loop=True, speed=0.0),
        Clip("blink", 8, blink, loop=False, bones={"eyelid.L", "eyelid.R"},
             notes="Only eyelid.L/R animate; FBX bake writes constant rest curves for other bones - play on a masked layer."),
        Clip("death", 24, death, loop=False),
    ]
    return clips


def main():
    K.reset_scene()
    nz = K.Noise3(101)
    F = build_field()
    body = K.body_from_field(NAME + "_Body", F, 4200, displacement(nz), smooth_iter=2)
    K.assign_body_materials(body, F, MATS, mat_rules())
    arm = K.build_armature(NAME, bones())
    K.skin_body(body, arm)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    W = K.weight_matrix(body, deform)
    co = K.get_verts(body)
    W = K.side_cleanup(W, deform, co, eps=0.004)
    K.auto_assign_prim_bones(F, arm)
    W = K.refine_weights(arm, co, F, W, deform, sigma=0.006, own_mix=0.5)
    W = K.smooth_weights(body, W, iterations=2, factor=0.5)
    # ears and nose rigid-ish
    for tagset, bone in (({"ear.L"}, "ear.L"), ({"ear.R"}, "ear.R")):
        w = K.prim_ownership_weight(co, F, tagset, 0.01)
        w = w * np.clip((co[:, 2] - 0.19) / 0.02, 0, 1)
        W = K.override_weights(W, deform, bone, w)
    # eyelid bones must not drive skin
    for b in ("eyelid.L", "eyelid.R"):
        W[:, deform.index(b)] = 0
    K.write_weights(body, deform, W)
    pts = build_parts()
    pobj = pts.build(NAME + "_Parts", MATS)
    K.finalize_join(body, pobj, pts, arm)
    K.uv_unwrap(body, repeat_m=0.18)
    rig = K.Rig(arm)
    clips = make_clips(rig)
    eye_h = P["eye"][2]
    entry = K.finish_creature(NAME, arm, [body], clips, IK, eye_h,
                              extra_manifest={"notes": "Falsekin disguise reuses this rig (bone-scale tweaks + MNF_FurRabbitMangy)."})
    K.log("DONE", NAME, entry["tris"], "tris")


if __name__ == "__main__":
    main()
