"""Falsekin - the revealed form of the rabbit mimic.
Rest pose = risen hunched quasi-humanoid (~1.3 m). The 'folded' disguise is a rabbit-sized crouched ball
produced by a uniform scale on `hips` (allowed for this creature) plus folding rotations.
Run: <python-with-bpy> creature_falsekin.py -- [--no-preview]
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

NAME = "Falsekin"
MATS = ["MNF_FurRabbitMangy", "MNF_SkinDecayed", "MNF_Flesh", "MNF_Teeth", "MNF_EyeWet"]
FUR, SKIN, FLESH, TEETH, EYE = MATS

P = dict(
    hips=(0, 0.15, 0.62), spine=(0, 0.12, 0.78), chest=(0, 0.04, 0.93), neck=(0, -0.10, 1.07),
    head=(0, -0.22, 1.18), head_t=(0, -0.44, 1.16),
    jaw=(0.012, -0.29, 1.15), jaw_t=(0.03, -0.45, 1.14),
    ear=(0.032, -0.235, 1.265), ear_t=(0.06, -0.17, 1.47),
    shoulder=(0.13, -0.04, 1.00), elbow=(0.2, 0.09, 0.64), wrist=(0.185, -0.2, 0.26),
    knuckle=(0.18, -0.27, 0.13), ftip=(0.17, -0.38, 0.03),
    thigh=(0.09, 0.17, 0.59), knee=(0.12, -0.03, 0.38), ankle=(0.11, 0.22, 0.13), toe=(0.11, 0.0, 0.015),
)
EYE_POS = np.array((0.066, -0.305, 1.225))


def bones():
    b = [
        BoneDef("root", (0, 0, 0), (0, 0, 0.15), None, deform=False),
        BoneDef("hips", P["hips"], P["spine"], "root"),
        BoneDef("spine", P["spine"], P["chest"], "hips", connect=True),
        BoneDef("chest", P["chest"], P["neck"], "spine", connect=True),
        BoneDef("neck", P["neck"], P["head"], "chest", connect=True),
        BoneDef("head", P["head"], P["head_t"], "neck", connect=True),
        BoneDef("jaw", (0, -0.27, 1.095), (0, -0.37, 1.065), "head"),
        BoneDef("jaw.L", P["jaw"], P["jaw_t"], "head"),
        BoneDef("ear.L", P["ear"], P["ear_t"], "head"),
        BoneDef("upperarm.L", P["shoulder"], P["elbow"], "chest"),
        BoneDef("forearm.L", P["elbow"], P["wrist"], "upperarm.L", connect=True),
        BoneDef("hand.L", P["wrist"], P["knuckle"], "forearm.L", connect=True),
        BoneDef("fingers.L", P["knuckle"], P["ftip"], "hand.L", connect=True),
        BoneDef("thigh.L", P["thigh"], P["knee"], "hips"),
        BoneDef("shin.L", P["knee"], P["ankle"], "thigh.L", connect=True),
        BoneDef("foot.L", P["ankle"], P["toe"], "shin.L", connect=True),
    ]
    return K.mirror_bones(b)


IK = [("thigh.L", "shin.L"), ("thigh.R", "shin.R"), ("upperarm.L", "forearm.L"), ("upperarm.R", "forearm.R")]


def M(p, s):
    return np.array(p, float) * np.array([s, 1, 1])


def build(nz):
    F = K.Field((-0.34, -0.56, -0.02), (0.34, 0.36, 1.56), 0.0052)
    pt = K.Parts()
    rng = np.random.RandomState(17)
    # --- emaciated torso
    F.add(Ellipsoid((0, 0.17, 0.62), (0.135, 0.13, 0.115), (20, 0, 0), FUR, "hips", "pelvis"), k=0.06)
    F.add(Capsule((0, 0.14, 0.66), (0, 0.07, 0.86), 0.065, 0.075, SKIN, "spine", "belly"), k=0.05)
    rc = EllipsoidBetween((0, 0.09, 0.80), (0, -0.07, 1.04), 0.115, 0.095, FUR, "chest", "ribcage",
                          y_hint=(0, -1, -0.6))
    F.add(rc, k=0.05)
    # spine ridge (vertebrae poking through) along the back
    for i in range(9):
        t = i / 8
        c = np.array((0, 0.235 - 0.17 * t, 0.62 + 0.42 * t))
        F.add(Ellipsoid(c, (0.018, 0.016, 0.016), (0, 0, 0), SKIN, "spine" if t < 0.5 else "chest", "vert"), k=0.018)
    # ribs
    rcc = rc.c
    for s in (1, -1):
        for zl in (-0.06, -0.01, 0.04, 0.09):
            pts = []
            for q, phi in enumerate(np.linspace(math.radians(30), math.radians(150), 5)):
                z2 = zl - 0.04 * q / 4
                sc = math.sqrt(max(0.0, 1 - (z2 / 0.14) ** 2))
                lp = np.array((0.115 * sc * math.sin(phi) * s, -0.095 * sc * math.cos(phi), z2))
                pts.append(rcc + rc.R @ lp)
            for a, b in zip(pts[:-1], pts[1:]):
                F.add(Capsule(a, b, 0.0085, 0.0085, SKIN, "chest", "rib"), k=0.012)
    # --- long thin neck, rabbit-like but wrong skull
    F.add(Capsule((0, -0.06, 1.03), (0, -0.23, 1.17), 0.048, 0.04, FUR, "neck", "neck"), k=0.04)
    F.add(Ellipsoid((0, -0.29, 1.205), (0.072, 0.115, 0.078), (10, 0, 0), FUR, "head", "head"), k=0.035)
    F.add(Ellipsoid((0, -0.385, 1.165), (0.05, 0.068, 0.052), (14, 0, 0), FUR, "head", "snout"), k=0.03)
    F.add(Ellipsoid((0.042, -0.33, 1.16), (0.04, 0.05, 0.04), (0, 0, 0), FUR, "head", "cheek"), k=0.025, mirror=True)
    # vertical torn mouth: thin slab through snout and chin, flesh lined
    F.sub(Ellipsoid((0, -0.395, 1.135), (0.0055, 0.085, 0.072), (0, 0, 0), FLESH), k=0.003)
    F.sub(Ellipsoid((0, -0.33, 1.105), (0.0045, 0.06, 0.05), (0, 0, 0), FLESH), k=0.003)
    F.sub(Ellipsoid((0, -0.335, 1.135), (0.016, 0.045, 0.05), (0, 0, 0), FLESH), k=0.006)  # throat pit
    # eye sockets
    F.sub(Ellipsoid(EYE_POS * [1, 1, 1] + [0.006, 0, 0], 0.026), k=0.008, keep=False, mirror=True)
    # ears
    for s in (1, -1):
        e0, e1 = M(P["ear"], s), M(P["ear_t"], s)
        tag = "ear.L" if s > 0 else "ear.R"
        F.add(EllipsoidBetween(e0 + [0, 0.006, -0.02], e1, 0.036, 0.012, FUR, tag, tag, y_hint=(0.3 * s, -1, 0)),
              k=0.02)
        mid = e0 + (e1 - e0) * 0.58 + np.array([0, -0.012, 0])
        F.sub(EllipsoidBetween(mid - (e1 - e0) * 0.3, mid + (e1 - e0) * 0.3, 0.02, 0.008, SKIN,
                               y_hint=(0.3 * s, -1, 0)), k=0.004, keep=False)
    F.sub(Ellipsoid((-0.07, -0.16, 1.43), 0.02), k=0.004, keep=False)  # torn notch in the right ear
    # --- long front limbs
    for s in (1, -1):
        sh, el, wr, kn = M(P["shoulder"], s), M(P["elbow"], s), M(P["wrist"], s), M(P["knuckle"], s)
        F.add(Ellipsoid(sh + [0, 0.01, 0.01], (0.05, 0.05, 0.05), (0, 0, 0), FUR, "chest", "shoulder"), k=0.04)
        F.add(Capsule(sh, el, 0.038, 0.024, FUR, None, "upperarm"), k=0.03)
        F.add(Capsule(el, wr, 0.024, 0.017, SKIN, None, "forearm"), k=0.015)
        F.add(Ellipsoid(el + [0, 0.012, 0], 0.025, (0, 0, 0), SKIN, None, "elbow"), k=0.012)
        F.add(FlatCapsule(wr, kn, 0.022, 0.024, up=(0, 1, 1), flat=0.5, mat=SKIN, tag="palm"), k=0.012)
        K.add_digits(F, pt, kn, along=(0, -0.75, -1), spread_dir=(1, 0, 0), curl_dir=(0, 0.3, -1), n=4,
                     length=0.15, r0=0.0095, r1=0.0065, spread=0.045, curl=30, mat=SKIN, nail_mat=TEETH,
                     nail_len=0.03, seed=3 + s, tag="fingers", fan=10)
        # hind legs (digitigrade, long rabbit feet)
        th, kq, an, to = M(P["thigh"], s), M(P["knee"], s), M(P["ankle"], s), M(P["toe"], s)
        F.add(Ellipsoid(th + (kq - th) * 0.4, (0.055, 0.07, 0.12), (-45, 0, 0), FUR, None, "thigh"), k=0.05)
        F.add(Capsule(th, kq, 0.045, 0.03, FUR, None, "thigh"), k=0.03)
        F.add(Capsule(kq, an, 0.03, 0.02, FUR, None, "shin"), k=0.02)
        F.add(FlatCapsule(an + [0, 0, 0.0], to + [0, 0, 0.01], 0.022, 0.017, up=(0, 0, 1), flat=0.6, mat=FUR,
                          tag="foot"), k=0.015)
        K.add_digits(F, pt, to + [0, 0.012, 0.006], along=(0, -1, -0.2), spread_dir=(1, 0, 0), curl_dir=(0, 0, -1),
                     n=3, length=0.05, r0=0.01, r1=0.007, spread=0.03, curl=15, mat=FUR, nail_mat=TEETH,
                     nail_len=0.018, seed=9 + s, tag="foot", segs=2)
    # tail stub
    F.add(Ellipsoid((0, 0.255, 0.64), (0.04, 0.035, 0.04), (0, 0, 0), FUR, "hips", "tail"), k=0.03)

    # --- eyes (large, black, lateral like a rabbit)
    for s in (1, -1):
        pt.ellipsoid(EYE_POS * [s, 1, 1], (0.024, 0.026, 0.024), EYE, segs=10, rings=7, bone="head")
    # --- rows of small uneven teeth along both edges of the vertical tear
    for s, jb in ((1, "jaw.L"), (-1, "jaw.R")):
        for row, depth in ((0, 0.0), (1, 0.012)):
            n = 15
            for i in range(n):
                a = math.pi * (0.12 + 0.76 * i / (n - 1))  # around the front of the slit ellipse
                # slit ellipse in the YZ plane centred (y,z) = (-0.395, 1.135), radii (0.085, 0.072)
                y = -0.395 - 0.072 * math.sin(a) - 0.004 + depth
                z = 1.135 + 0.06 * math.cos(a)
                if y < -0.445 + depth * 0.5:
                    y = -0.445 + depth * 0.5
                base = np.array((0.0075 * s, y + 0.012 + rng.uniform(-0.004, 0.004), z))
                L = rng.uniform(0.011, 0.02) * (1.5 if rng.rand() < 0.2 else 1)
                d = np.array((-s, rng.uniform(-0.4, 0.2), rng.uniform(-0.3, 0.3)))
                d /= np.linalg.norm(d)
                pt.cone(Vector(base + [0.006 * s, 0, 0]), Vector(base + d * L), rng.uniform(0.003, 0.0045), TEETH,
                        segs=4, bone=jb, twist=rng.uniform(0, 3))
    return F, pt


def displacement(nz):
    def fn(co, nr):
        d = 0.0025 * nz.fbm(co, 4, 3)
        d += 0.0035 * np.maximum(nz(co, 9, (2, 2, 2)), 0)  # mangy clumps
        return d
    return fn


def mat_rules(nz):
    def rules(C, N, mats, owners):
        bald = nz.fbm(C, 3.0, 2) > 0.25
        for i, o in enumerate(owners):
            if mats[i] == FUR and bald[i] and o.tag not in ("ear.L", "ear.R"):
                mats[i] = SKIN
        return mats
    return [rules]


# ---------------------------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------------------------
FOLD_S = 0.5


def folded_pose(u=0.0, breath=True):
    """Rabbit-sized crouched ball, authored with world aim directions."""
    p = Pose()
    p.s("hips", FOLD_S)
    p.l("hips", 0, -0.085, 0.078 - 0.62)
    p.a("hips", 0, -1, 0.45)
    p.a("spine", 0, -1, 0.05)
    p.a("chest", 0, -1, -0.05)
    p.a("neck", 0, -0.25, 1)
    p.a("head", 0, -1, -0.4)
    for s in "LR":
        sg = 1 if s == "L" else -1
        p.s("upperarm." + s, 0.36)
        p.s("thigh." + s, 0.62)
        p.a("thigh." + s, 0.1 * sg, -1, -0.12)
        p.a("shin." + s, 0, 0.92, -0.4)
        p.a("foot." + s, 0, -1, -0.02)
        p.a("upperarm." + s, 0.12 * sg, 0.85, -0.5)
        p.a("forearm." + s, 0, -0.9, -0.4)
        p.a("hand." + s, 0, -1, -0.02)
        p.a("fingers." + s, 0, -1, 0.0)
        # rabbit ears: upright, slightly back
        p.a("ear." + s, 0.15 * sg, 0.75, 1)
    if breath:
        b = math.sin(2 * math.pi * 4 * u)
        p.r("chest", 2.0 * b)
        p.r("spine", -1.2 * b)
        tw = pulse(u, 0.3, 0.33, 0.36, 0.4) + pulse(u, 0.72, 0.74, 0.77, 0.8)
        p.r("head", 4 * tw * math.sin(2 * math.pi * 20 * u))
        p.r("ear.R", -14 * pulse(u, 0.55, 0.57, 0.6, 0.64))
    return p


def risen_pose(u, mouth=18):
    """Risen predatory stance: hunched, swaying, ears bent in opposing wrong directions."""
    p = Pose()
    sway = math.sin(2 * math.pi * u)
    p.l("hips", 0.015 * sway, 0, 0.004 * math.sin(4 * math.pi * u))
    p.r("hips", 4, 0, 0)
    p.r("spine", 4, 3 * sway, 0)
    p.r("chest", 10, 4 * sway, 2 * sway)
    p.r("neck", -12, -6 * sway, 0)
    p.r("head", -10 + 3 * pnoise(u, 5), 14 + 6 * sway, 4 * pnoise(u, 6))
    p.r("ear.L", 95, 0, 40)      # flopped forward and down over the face
    p.r("ear.R", -70, 0, -55)    # bent back the wrong way
    m = mouth + 5 * pnoise(u, 7, (2, 3))
    p.r("jaw.L", 0, 0, m)
    p.r("jaw.R", 0, 0, -m * 0.9)
    p.r("jaw", 0.3 * m)
    for s in "LR":
        sg = 1 if s == "L" else -1
        p.r("upperarm." + s, 6 + 3 * math.sin(2 * math.pi * u + sg), 0, 0)
        p.r("fingers." + s, 8 * pnoise(u, 10 + sg))
    return p


def make_clips(rig):
    feet = {s: rig.tail("shin." + s) for s in "LR"}
    POLE_K = Vector((0, -1, 0))

    def plant(p, w=1.0):
        for s in "LR":
            p.ik("thigh." + s, feet[s], POLE_K, w)
            p.w("foot." + s)
        return p

    def folded(u, t):
        return folded_pose(u)

    # ---- unfold: sudden and wrong
    UNF = 27

    def unfold(u, t):
        f = t * K.FPS
        a = folded_pose(0.0)
        b = plant(risen_pose(0.0, 24))
        # anticipation: shiver + compress (f0-6)
        shiver = ramp(f, 1, 6) * (1 - ramp(f, 6, 7)) * math.sin(f * 2.7)
        x = ease_out(ramp(f, 6, 13), 3.0)  # violent unfolding
        over = pulse(f, 10, 13, 14, 20)
        p = K.combo([a, b], [1 - x, x])
        # the scale snaps open slightly ahead of the limbs and overshoots
        sc = FOLD_S + (1 - FOLD_S) * ease_out(ramp(f, 5, 11), 2.5) + 0.05 * over
        p.s("hips", sc)
        p.r("chest", 5 * shiver, 0, 4 * shiver)
        p.r("head", 8 * shiver)
        p.r("spine", -18 * over)
        p.r("chest", -14 * over)
        p.r("neck", 20 * over)
        # limbs unfold with a lag / wrong order (left arm first)
        lagR = ease_out(ramp(f, 8, 14), 3.0)
        p.r("upperarm.R", -40 * (x - lagR), 0, 0)
        p.r("forearm.R", -90 * (x - lagR))
        p.r("upperarm.L", -55 * over, 0, -15 * over)
        p.r("upperarm.R", -45 * pulse(f, 12, 15, 16, 22), 0, 15 * pulse(f, 12, 15, 16, 22))
        # mouth tears open after the body is up
        m = 46 * ease_out(ramp(f, 11, 15), 2) - 18 * ramp(f, 17, 27)
        p.r("jaw.L", 0, 0, m)
        p.r("jaw.R", 0, 0, -m)
        p.r("jaw", 0.35 * m)
        # head judder
        p.r("head", 10 * pulse(f, 14, 15, 16, 18) * math.sin(f * 3.1), 0, 12 * pulse(f, 15, 16, 17, 19))
        p.r("ear.L", -95 * (1 - ease_out(ramp(f, 9, 16), 2)))
        p.r("ear.R", 70 * (1 - ease_out(ramp(f, 12, 18), 2)))
        return p

    def idle(u, t):
        return plant(risen_pose(u, 18))

    # ---- run: fast low skitter on all fours, 7 m/s
    RUN_F = 12
    RT = RUN_F / K.FPS
    run_v = 7.0

    def run(u, t):
        p = Pose()
        ph = 2 * math.pi * u
        p.l("hips", 0, 0.1, -0.24 + 0.02 * math.sin(2 * ph))
        p.r("hips", 34 + 3 * math.sin(2 * ph))
        p.r("spine", 22, 4 * math.sin(ph), 5 * math.sin(ph))
        p.r("chest", 18, -4 * math.sin(ph), -6 * math.sin(ph))
        p.r("neck", -55)
        p.r("head", -16 + 3 * math.sin(2 * ph))
        p.r("ear.L", 60, 0, 30)
        p.r("ear.R", -90, 0, -30)
        p.r("jaw.L", 0, 0, 14)
        p.r("jaw.R", 0, 0, -14)
        seq = {"thigh.L": 0.0, "upperarm.L": 0.27, "thigh.R": 0.5, "upperarm.R": 0.77}
        for up, off in seq.items():
            s = up[-1]
            sg = 1 if s == "L" else -1
            if up.startswith("thigh"):
                r = feet[s] + Vector((0.07 * sg, 0.06, 0))
                tgt, contact, ss = foot_track(u, off, 0.32, run_v * 0.32 * RT, 0.1, r)
                p.ik(up, tgt, POLE_K, 1.0)
                p.w("foot." + s, 0 if contact else 35 * math.sin(math.pi * ss))
            else:
                r = Vector((0.26 * sg, -0.62, 0.14))
                tgt, contact, ss = foot_track(u, off, 0.32, run_v * 0.32 * RT, 0.14, r)
                p.ik(up, tgt, Vector((0.6 * sg, 1, 0.3)), 1.0)
                p.w("hand." + s, 40 if contact else 10)
                p.r("fingers." + s, -20 if contact else 30 * math.sin(math.pi * ss))
        return p

    # ---- lunge 0.8 s: coil, explode forward with the mouth torn wide (hit f14)
    HIT = 14

    def lunge(u, t):
        f = t * K.FPS
        base = plant(risen_pose(0.0, 18))
        coil = Pose().l("hips", 0, 0.08, -0.1).r("hips", 16).r("spine", 14).r("chest", 10).r("neck", -10)
        coil.r("upperarm.L", 30).r("upperarm.R", 30).r("forearm.L", -30).r("forearm.R", -30)
        ext = Pose().l("hips", 0, -0.32, -0.12).r("hips", 38).r("spine", 18).r("chest", 12).r("neck", -40)
        ext.r("head", -10).r("jaw.L", 0, 0, 30).r("jaw.R", 0, 0, -30).r("jaw", 12)
        ext.r("upperarm.L", -75, 0, -10).r("upperarm.R", -75, 0, 10).r("forearm.L", -25).r("forearm.R", -25)
        ext.r("hand.L", -30).r("hand.R", -30).r("fingers.L", 35).r("fingers.R", 35)
        rec = Pose().l("hips", 0, -0.15, -0.05).r("hips", 20).r("spine", 8).r("neck", -18).r("jaw.L", 0, 0, 10)
        rec.r("jaw.R", 0, 0, -10).r("upperarm.L", -20).r("upperarm.R", -20)
        d = keyed(f, [(0, Pose()), (7, coil), (HIT, ext), (18, ext.add(Pose().r("chest", 4))), (24, rec)], mode='cr')
        p = base.add(d)
        # hind feet stay planted then get dragged forward on landing
        drag = smoothstep(ramp(f, 14, 22))
        for s in "LR":
            p.ik("thigh." + s, feet[s] + Vector((0, -0.25 * drag, 0)), POLE_K, 1.0)
        return p

    # ---- retreat: low crawl, 3 m/s
    RET_F = 18
    RET_T = RET_F / K.FPS

    def retreat(u, t):
        p = Pose()
        ph = 2 * math.pi * u
        p.l("hips", 0, 0.05, -0.36 + 0.015 * math.sin(2 * ph))
        p.r("hips", 50, 0, 6 * math.sin(ph))
        p.r("spine", 20, 0, -8 * math.sin(ph))
        p.r("chest", 14, 0, -6 * math.sin(ph))
        p.r("neck", -60)
        p.r("head", -20, 8 * math.sin(ph), 0)
        p.r("ear.L", 100, 0, 20)
        p.r("ear.R", -40, 0, -70)
        seq = {"thigh.L": 0.0, "upperarm.R": 0.12, "thigh.R": 0.5, "upperarm.L": 0.62}
        for up, off in seq.items():
            s = up[-1]
            sg = 1 if s == "L" else -1
            if up.startswith("thigh"):
                r = Vector((0.24 * sg, 0.1, 0.07))
                tgt, contact, ss = foot_track(u, off, 0.55, 3.0 * 0.55 * RET_T, 0.07, r)
                p.ik(up, tgt, Vector((0.5 * sg, -1, 0.5)), 1.0)
                p.w("foot." + s, 0 if contact else 20 * math.sin(math.pi * ss))
            else:
                r = Vector((0.33 * sg, -0.55, 0.1))
                tgt, contact, ss = foot_track(u, off, 0.55, 3.0 * 0.55 * RET_T, 0.09, r)
                p.ik(up, tgt, Vector((1.0 * sg, 0.6, 0.6)), 1.0)
                p.w("hand." + s, 30)
                p.r("fingers." + s, -15 if contact else 25)
        return p

    # ---- death 1.0 s: convulses, mouth gapes, collapses on its side and curls
    def death(u, t):
        f = t * K.FPS
        base = plant(risen_pose(0.0, 18), w=1.0 - smoothstep(ramp(f, 4, 14)))
        conv = pulse(f, 0, 2, 6, 10)
        fall = ease_in(ramp(f, 6, 18), 2)
        bounce = pulse(f, 18, 20, 21, 24)
        p = base
        p.r("chest", -25 * conv, 0, 10 * conv * math.sin(f * 2.5))
        p.r("head", -30 * conv + 20 * fall, 0, 0)
        p.r("jaw.L", 0, 0, 30 * conv + 8 * fall)
        p.r("jaw.R", 0, 0, -30 * conv - 6 * fall)
        p.l("hips", 0.05 * fall, 0.05 * fall, -0.5 * fall + 0.03 * bounce)
        p.r("hips", 30 * fall, 85 * fall, 0)
        p.r("spine", 20 * fall)
        p.r("chest", 25 * fall)
        p.r("neck", -20 * fall)
        curl = smoothstep(ramp(f, 16, 30))
        for s in "LR":
            sg = 1 if s == "L" else -1
            p.r("upperarm." + s, -40 * curl - 20 * conv, 0, 20 * sg * conv)
            p.r("forearm." + s, -80 * curl)
            p.r("fingers." + s, 70 * curl)
            p.r("thigh." + s, -50 * curl)
            p.r("shin." + s, 60 * curl)
        return p

    return [
        Clip("folded", 60, folded, loop=True, speed=0.0),
        Clip("unfold", UNF, unfold, loop=False, notes="Starts exactly on the folded pose, ends on the idle pose."),
        Clip("idle", 60, idle, loop=True, speed=0.0),
        Clip("run", RUN_F, run, loop=True, speed=run_v),
        Clip("lunge", 24, lunge, loop=False, events={"hit": [HIT]}),
        Clip("retreat", RET_F, retreat, loop=True, speed=3.0),
        Clip("death", 30, death, loop=False),
    ]


def main():
    K.reset_scene()
    nz = K.Noise3(303)
    F, pt = build(nz)
    imp = K.importance_spheres([((0, -0.33, 1.17), 0.12, 1.0)])
    body = K.body_from_field(NAME + "_Body", F, 6000, displacement(nz), smooth_iter=2, importance_fn=imp)
    K.assign_body_materials(body, F, MATS, mat_rules(nz))
    arm = K.build_armature(NAME, bones())
    W = K.skin_body(body, arm)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    co = K.get_verts(body)
    W = K.side_cleanup(W, deform, co, eps=0.01)
    K.auto_assign_prim_bones(F, arm)
    W = K.refine_weights(arm, co, F, W, deform, sigma=0.012, own_mix=0.35)
    W = K.smooth_weights(body, W, iterations=2, factor=0.5)
    # vertical mouth halves: snout in front of the tear's back edge goes to jaw.L / jaw.R
    front = np.clip((-0.30 - co[:, 1]) / 0.05, 0, 1) * np.clip((1.26 - co[:, 2]) / 0.03, 0, 1) * \
        np.clip((co[:, 2] - 1.03) / 0.03, 0, 1)
    side = np.clip(co[:, 0] / 0.006, -1, 1)
    W = K.override_weights(W, deform, "jaw.L", front * np.clip(side, 0, 1))
    W = K.override_weights(W, deform, "jaw.R", front * np.clip(-side, 0, 1))
    # standard `jaw`: drags the throat / underside of the skull below the tear
    throat = np.clip((1.1 - co[:, 2]) / 0.03, 0, 1) * np.clip((co[:, 1] + 0.24) / -0.04, 0, 1) * \
        np.clip((co[:, 1] + 0.42) / 0.04, 0, 1) * np.clip(1 - np.abs(co[:, 0]) / 0.06, 0, 1) * (1 - front)
    W = K.override_weights(W, deform, "jaw", 0.75 * throat)
    for s in ("L", "R"):
        w = K.prim_ownership_weight(co, F, {"ear." + s}, 0.012) * np.clip((co[:, 2] - 1.26) / 0.03, 0, 1)
        W = K.override_weights(W, deform, "ear." + s, w)
    K.write_weights(body, deform, W)
    K.add_tufts(body, pt, MATS, FUR, count=70, seed=8, length=(0.025, 0.06), radius=(0.007, 0.012), droop=0.6)
    pobj = pt.build(NAME + "_Parts", MATS)
    K.finalize_join(body, pobj, pt, arm)
    K.uv_unwrap(body, repeat_m=0.35)
    rig = K.Rig(arm)
    clips = make_clips(rig)
    entry = K.finish_creature(NAME, arm, [body], clips, IK, eye_height=float(EYE_POS[2]), scale_bones=("hips", "upperarm.L", "upperarm.R", "thigh.L", "thigh.R"),
                              preview_kwargs={"contact_view": (-1.0, -0.5, 0.3), "fog_clip": "idle"},
                              extra_manifest={"notes": "Rest/bind pose is the risen form. 'folded' uses a uniform "
                                                       "scale of %.2f on hips plus 0.36 on upperarm.L/R and 0.62 on thigh.L/R (scale keys only on these bones; 1.0 in all other clips)." % FOLD_S})
    K.log("DONE", NAME, entry["tris"], "tris")


if __name__ == "__main__":
    main()
