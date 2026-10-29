"""Hollowback - tall, hunched, sound-sensitive forest hunter.
Run: <python-with-bpy> creature_hollowback.py -- [--no-preview]
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
                             pulse, ramp, pnoise, tnoise, foot_track, keyed)

NAME = "Hollowback"
MATS = ["MNF_FurRotten", "MNF_SkinDecayed", "MNF_Teeth", "MNF_Gums", "MNF_Nails", "MNF_EyeWet", "MNF_EyeClouded"]
FUR, SKIN, TEETH, GUMS, NAILS, EYEW, EYEC = MATS

# ---------------------------------------------------------------------------------------------
# Skeleton (rest = permanent hunch; faces -Y)
# ---------------------------------------------------------------------------------------------
P = dict(
    hips=(0, 0.17, 1.08), spine=(0, 0.13, 1.30), chest=(0, 0.0, 1.52), neck=(0, -0.30, 1.84),
    head=(0, -0.52, 1.99), head_t=(0, -0.71, 1.97),
    jaw=(0.006, -0.555, 1.945), jaw_t=(0.022, -0.705, 1.895),
    hump=(0.04, -0.02, 1.80), hump_t=(0.09, 0.06, 2.16),
    shoulder=(0.30, -0.27, 1.78), elbow=(0.36, -0.25, 1.10), wrist=(0.38, -0.30, 0.52),
    knuckle=(0.385, -0.33, 0.34), ftip=(0.375, -0.37, 0.12),
    thigh=(0.165, 0.19, 1.04), knee=(0.21, -0.02, 0.58), ankle=(0.205, 0.15, 0.115),
    toe=(0.205, -0.13, 0.03),
)


def bones():
    b = [
        BoneDef("root", (0, 0, 0), (0, 0, 0.25), None, deform=False),
        BoneDef("hips", P["hips"], P["spine"], "root"),
        BoneDef("spine", P["spine"], P["chest"], "hips", connect=True),
        BoneDef("chest", P["chest"], P["neck"], "spine", connect=True),
        BoneDef("hump", P["hump"], P["hump_t"], "chest"),
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


IK = [("thigh.L", "shin.L"), ("thigh.R", "shin.R"), ("upperarm.L", "forearm.L"), ("upperarm.R", "forearm.R")]


def M(p, s):
    return np.array(p, float) * np.array([s, 1, 1])


# ---------------------------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------------------------
def build(nz):
    F = K.Field((-0.62, -0.86, -0.02), (0.62, 0.55, 2.47), 0.0078)
    pt = K.Parts()
    rng = np.random.RandomState(7)

    # --- pelvis, gaunt abdomen, ribcage (torso pitched far forward: permanent hunch)
    F.add(Ellipsoid((0, 0.17, 1.08), (0.185, 0.14, 0.13), (14, 0, 0), FUR, "hips", "pelvis"), k=0.05)
    F.add(Capsule((0, 0.16, 1.12), (0, 0.07, 1.42), 0.115, 0.13, SKIN, "spine", "belly"), k=0.06)
    rc_a = np.array((0, 0.07, 1.42))
    rc_b = np.array((0, -0.25, 1.80))
    rc_c = (rc_a + rc_b) / 2
    rc = EllipsoidBetween(rc_a, rc_b, 0.20, 0.165, SKIN, "chest", "ribcage", y_hint=(0, -1, -1.2), extend=1.05)
    F.add(rc, k=0.07)
    F.sub(Ellipsoid((0, -0.02, 1.30), (0.10, 0.07, 0.08), (0, 0, 0)), k=0.05, keep=False)  # sunken belly
    # back muscles under the hump and the shoulder girdle / trapezius
    F.add(EllipsoidBetween((0, 0.16, 1.48), (0, -0.14, 1.86), 0.21, 0.17, FUR, "chest", "back",
                           y_hint=(0, 1, 1)), k=0.07)
    for s in (1, -1):
        F.add(Capsule(M((0.08, -0.12, 1.88), s), M(P["shoulder"], s) + [0, 0, 0.03], 0.09, 0.075, FUR, "chest",
                      "shoulder"), k=0.07)
    # --- asymmetric hump: big lopsided mass + lumps (bigger on the left)
    F.add(Ellipsoid((0.06, 0.06, 1.98), (0.31, 0.35, 0.24), (-38, 10, 8), FUR, "hump", "hump"), k=0.16)
    F.add(Ellipsoid((0.18, -0.04, 2.1), (0.19, 0.18, 0.17), (20, 0, 0), FUR, "hump", "hump"), k=0.12)
    F.add(Ellipsoid((-0.12, 0.12, 1.94), (0.15, 0.16, 0.13), (-30, 0, 0), FUR, "hump", "hump"), k=0.12)
    lumps = [((0.24, -0.08, 2.14), 0.07), ((0.05, 0.08, 2.26), 0.075), ((0.27, 0.1, 1.99), 0.06),
             ((-0.08, -0.07, 2.15), 0.055), ((0.14, 0.18, 2.1), 0.06), ((-0.18, 0.03, 2.02), 0.05),
             ((0.31, 0.0, 2.07), 0.045), ((0.1, -0.02, 2.31), 0.05)]
    for c, r in lumps:
        F.add(Ellipsoid(c, (r, r * 0.9, r * 0.85), (rng.uniform(-30, 30), 0, 0), FUR, "hump", "hump"), k=0.035)
    # vertebrae ridge running down the lower back
    for i in range(6):
        t = i / 5
        c = np.array((0.0, 0.29 - 0.08 * t, 1.12 + 0.36 * t))
        F.add(Ellipsoid(c, (0.03, 0.025, 0.028), (0, 0, 0), SKIN, "spine", "vert"), k=0.03)
    # ribs under decayed skin, sloping down toward the front; more exposed on the right side
    rcR = rc.R
    rz = np.linalg.norm(rc_b - rc_a) / 2 * 1.05
    for s in (1, -1):
        for j, zl in enumerate((-0.10, -0.03, 0.04, 0.11)):
            pts = []
            for q, phi in enumerate(np.linspace(math.radians(30), math.radians(155), 6)):
                z2 = zl - 0.07 * q / 5
                sc = math.sqrt(max(0.0, 1 - (z2 / rz) ** 2))
                lp = np.array((0.2 * sc * math.sin(phi) * s * 1.0, -0.165 * sc * math.cos(phi), z2))
                pts.append(rc_c + rcR @ lp)
            rr = 0.017 if s < 0 else 0.012
            for a, b in zip(pts[:-1], pts[1:]):
                F.add(Capsule(a, b, rr, rr, SKIN, "chest", "rib"), k=0.018)

    # --- neck (thin, forward from the front of the hump) and small head
    F.add(Capsule((0, -0.22, 1.80), (0, -0.50, 1.975), 0.095, 0.06, SKIN, "neck", "neck"), k=0.07)
    F.add(Capsule((0, -0.16, 1.92), (0, -0.40, 2.01), 0.08, 0.05, FUR, "neck", "neck"), k=0.06)
    F.add(Ellipsoid((0, -0.575, 2.01), (0.082, 0.095, 0.088), (8, 0, -6), SKIN, "head", "head"), k=0.04)
    F.add(Ellipsoid((0.0, -0.58, 2.065), (0.07, 0.07, 0.045), (0, 0, 0), FUR, "head", "head"), k=0.03)
    # brow ridge, skewed
    F.add(Capsule((0.05, -0.655, 2.035), (-0.055, -0.648, 2.025), 0.022, 0.02, SKIN, "head", "head"), k=0.02)
    # muzzle (upper jaw) - narrow, protruding
    F.add(Ellipsoid((0.0, -0.675, 1.965), (0.05, 0.07, 0.045), (14, 0, -4), SKIN, "head", "muzzle"), k=0.03)
    # cheek bones (one hollow)
    F.add(Ellipsoid((0.055, -0.62, 1.975), (0.03, 0.04, 0.03), (0, 0, 0), SKIN, "head", "head"), k=0.02)
    # lower jaw - narrow, misaligned to the left
    F.add(Capsule((0.012, -0.57, 1.925), (0.025, -0.705, 1.902), 0.036, 0.024, SKIN, "jaw", "jaw"), k=0.025)
    # mouth slit (gum-lined) between muzzle and jaw
    F.sub(Ellipsoid((0.012, -0.668, 1.928), (0.04, 0.062, 0.009), (8, 0, -6), GUMS), k=0.006)
    # eye sockets
    eyeL = np.array((0.036, -0.658, 2.008))
    eyeR = np.array((-0.034, -0.652, 1.996))
    F.sub(Ellipsoid(eyeL + [0, -0.004, 0], (0.022, 0.02, 0.02), (0, 0, 0), SKIN), k=0.01, keep=False)
    F.sub(Ellipsoid(eyeR + [0, -0.004, 0], (0.024, 0.02, 0.022), (0, 0, 0), SKIN), k=0.01, keep=False)
    # ears: small, chewed
    for s, sz in ((1, 1.0), (-1, 0.75)):
        F.add(EllipsoidBetween(M((0.07, -0.55, 2.02), s), M((0.11, -0.53, 2.06), s), 0.032 * sz, 0.012, SKIN,
                               "head", "ear", y_hint=(0, -1, 0)), k=0.015)
    F.sub(Ellipsoid((0.11, -0.54, 2.075), 0.018), k=0.005, keep=False)  # bite out of left ear

    # --- arms
    for s in (1, -1):
        side = "L" if s > 0 else "R"
        sh, el, wr, kn = M(P["shoulder"], s), M(P["elbow"], s), M(P["wrist"], s), M(P["knuckle"], s)
        F.add(Capsule(sh, el, 0.07, 0.048, FUR, None, "upperarm"), k=0.04)
        F.add(Ellipsoid(sh + (el - sh) * 0.3, (0.075, 0.07, 0.15), (0, 4 * s, 0), FUR, None, "upperarm"), k=0.05)
        F.add(Capsule(el, wr, 0.05, 0.034, FUR, None, "forearm"), k=0.03)
        F.add(Ellipsoid(el + (wr - el) * 0.25, (0.052, 0.05, 0.12), (0, 0, 0), SKIN, None, "forearm"), k=0.04)
        F.add(Ellipsoid(el + [0, 0.035, 0], 0.045, (0, 0, 0), SKIN, None, "elbow"), k=0.02)
        # palm (flattened, palm facing the body)
        F.add(FlatCapsule(wr, kn, 0.042, 0.045, up=(1, 0, 0), flat=0.5, mat=SKIN, tag="palm"), k=0.025)
        tips = K.add_digits(F, pt, kn + [0, 0, 0.01], along=(-0.03 * s, -0.12, -1), spread_dir=(0, 1, 0),
                            curl_dir=(-s * 0.7, -0.6, 0), n=4, length=0.235, r0=0.017, r1=0.011, spread=0.075,
                            curl=32, mat=SKIN, nail_mat=NAILS, nail_len=0.035, seed=11 + s,
                            broken=(1,) if s > 0 else (0, 3), tag="fingers")
        # thumb
        tb = wr + (kn - wr) * 0.55 + np.array([-0.012 * s, -0.04, 0])
        K.add_digits(F, pt, tb, along=(-0.25 * s, -0.5, -1), spread_dir=(0, 1, 0), curl_dir=(-s, 0, 0), n=1,
                     length=0.13, r0=0.017, r1=0.012, spread=0, curl=20, mat=SKIN, nail_mat=NAILS,
                     nail_len=0.025, seed=21 + s, tag="palm", segs=2)

    # --- legs
    for s in (1, -1):
        th, kn, an, to = M(P["thigh"], s), M(P["knee"], s), M(P["ankle"], s), M(P["toe"], s)
        F.add(Capsule(th, kn, 0.085, 0.055, FUR, None, "thigh"), k=0.05)
        F.add(Ellipsoid(th + (kn - th) * 0.35, (0.085, 0.09, 0.17), (-20, 0, 0), FUR, None, "thigh"), k=0.05)
        F.add(Capsule(kn, an, 0.05, 0.035, SKIN, None, "shin"), k=0.03)
        F.add(Ellipsoid(kn + (an - kn) * 0.3, (0.05, 0.055, 0.13), (-20, 0, 0), SKIN, None, "shin"), k=0.04)
        F.add(Ellipsoid(kn + [0, -0.03, 0.0], 0.05, (0, 0, 0), SKIN, None, "knee"), k=0.02)
        # long ape foot
        F.add(FlatCapsule(an + [0, 0.03, -0.04], an + (to - an) * 0.62 + [0, 0, -0.06], 0.05, 0.048,
                          up=(0, 0, 1), flat=0.55, mat=SKIN, tag="foot"), k=0.03)
        K.add_digits(F, pt, an + (to - an) * 0.62 + [0, 0, -0.065], along=(0, -1, -0.15), spread_dir=(1, 0, 0),
                     curl_dir=(0, 0, -1), n=4, length=0.11, r0=0.018, r1=0.013, spread=0.08, curl=25, mat=SKIN,
                     nail_mat=NAILS, nail_len=0.02, seed=31 + s, tag="foot", segs=2, fan=4)
        # big toe, splayed inward like an ape's
        K.add_digits(F, pt, an + (to - an) * 0.45 + [-0.045 * s, 0, -0.07], along=(-0.5 * s, -1, -0.1),
                     spread_dir=(1, 0, 0), curl_dir=(0, 0, -1), n=1, length=0.09, r0=0.022, r1=0.016, spread=0,
                     curl=10, mat=SKIN, nail_mat=NAILS, nail_len=0.02, seed=41 + s, tag="foot", segs=2)

    # --- detail parts: eyes, teeth, matted fur clumps
    pt.ellipsoid(eyeL, (0.016, 0.015, 0.0155), EYEW, segs=10, rings=7, bone="head")
    pt.ellipsoid(eyeR, (0.0165, 0.0155, 0.016), EYEC, segs=10, rings=7, bone="head")
    # teeth: crooked, missing, some protruding at strange angles
    def mouth_pt(t, upper):
        # t in [-1, 1] along the narrow mouth arc
        x = 0.036 * t + 0.008
        y = -0.71 + 0.075 * t * t
        z = 1.932 if upper else 1.922
        return np.array((x, y, z))
    up_missing = {2, 6}
    lo_missing = {1, 4, 7}
    for i, t in enumerate(np.linspace(-1, 1, 10)):
        if i not in up_missing:
            b = mouth_pt(t, True)
            L = 0.016 + rng.uniform(0, 0.008)
            d = np.array((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.1), -1.0))
            if i in (3, 8):  # protruding fangs, pushed out through the lips
                L = 0.045
                d = np.array((0.35 * np.sign(t + 1e-3), -0.75, -0.7))
            d /= np.linalg.norm(d)
            pt.cone(Vector(b + [0, 0, 0.006]), Vector(b + d * L), 0.0058 if L < 0.03 else 0.0075, TEETH, segs=5,
                    bone="head", twist=rng.uniform(0, 3))
        if i not in lo_missing:
            b = mouth_pt(t, False) + np.array((0.006, 0.004, 0))
            L = 0.014 + rng.uniform(0, 0.008)
            d = np.array((rng.uniform(-0.35, 0.35), rng.uniform(-0.4, 0.2), 1.0))
            if i in (0, 5):
                L = 0.04
                d = np.array((0.5 * np.sign(t + 1e-3), -0.8, 0.55))
            d /= np.linalg.norm(d)
            pt.cone(Vector(b - [0, 0, 0.006]), Vector(b + d * L), 0.0055 if L < 0.03 else 0.007, TEETH, segs=5,
                    bone="jaw", twist=rng.uniform(0, 3))
    return F, pt


def displacement(nz):
    def fn(co, nr):
        d = 0.005 * nz.fbm(co, 2.2, 3)
        # sinewy lumps everywhere, heavy tumorous lumps on the hump
        hump_w = np.clip((co[:, 2] - 1.85) / 0.15, 0, 1) * np.clip((co[:, 1] + 0.12) / 0.15, 0, 1)
        d += hump_w * (0.022 * np.maximum(nz(co, 1.6, (3, 1, 2)), -0.4) + 0.008 * nz(co, 5, (1, 7, 3)))
        # wrinkled skin streaks
        d += 0.0025 * nz(co * np.array([1, 1, 0.25]), 9, (5, 5, 5))
        return d
    return fn


def mat_rules(nz):
    def rules(C, N, mats, owners):
        bald = nz.fbm(C, 1.7, 2) > 0.55
        for i, o in enumerate(owners):
            if mats[i] == FUR and bald[i]:
                mats[i] = SKIN
            if o.tag in ("back", "pelvis") and N[i, 1] < -0.35:
                mats[i] = SKIN  # bare belly / chest front
            if o.tag == "shoulder" and N[i, 1] < -0.6:
                mats[i] = SKIN
        return mats
    return [rules]


# ---------------------------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------------------------
def make_clips(rig):
    feet = {s: rig.tail("shin." + s) for s in "LR"}
    wrists = {s: rig.tail("forearm." + s) for s in "LR"}
    POLE_K = Vector((0, -1, 0))
    POLE_E = lambda s: Vector((0.4 * (1 if s == "L" else -1), 1, 0))

    def plant(p, offs=None, w=1.0):
        offs = offs or {}
        for s in "LR":
            p.ik("thigh." + s, feet[s] + offs.get(s, Vector()), POLE_K, w)
            p.w("foot." + s, 0, 0, 0)
        return p

    def breathe(p, u, n, amp=1.0):
        b = math.sin(2 * math.pi * n * u)
        p.r("hump", -2.5 * amp * b, 0, 0.8 * amp * b)
        p.r("chest", -1.2 * amp * b)
        p.r("spine", 0.5 * amp * b)
        p.r("neck", 0.8 * amp * b)
        p.l("hips", 0, 0, 0.004 * amp * b)
        return p

    def hang_arms(p, u, amp=1.0, seed=0):
        for s in "LR":
            sg = 1 if s == "L" else -1
            p.r("upperarm." + s, 2 * amp * pnoise(u, seed + (1 if s == "L" else 2)), 0, 0)
            p.r("forearm." + s, 6 + 1.5 * amp * pnoise(u, seed + 3), 0, 0)
            p.r("hand." + s, 4, 0, 0)
        return p

    def twitch(p, u, s, at, width=0.03, amp=18):
        e = pulse(u, at, at + width * 0.3, at + width * 0.5, at + width)
        p.r("fingers." + s, -amp * e * (1 if s == "L" else 1), 0, 0)
        return p

    # ---- idle 4 s: nearly motionless, slow hump breathing, tiny finger twitches
    def idle(u, t):
        p = Pose()
        breathe(p, u, 2)
        hang_arms(p, u, 0.6, 10)
        p.r("head", 1.5 * pnoise(u, 20), 2.5 * pnoise(u, 21), 2 * pnoise(u, 22))
        twitch(p, u, "L", 0.18)
        twitch(p, u, "L", 0.24, 0.02, 10)
        twitch(p, u, "R", 0.63)
        p.r("jaw", 2 + 1.5 * pnoise(u, 23))
        return plant(p)

    # ---- listen 3 s: head tilts slowly one way, then the other; body frozen
    def listen(u, t):
        p = Pose()
        breathe(p, u, 1, 0.4)
        tilt = math.sin(2 * math.pi * u)
        tilt = math.copysign(abs(tilt) ** 0.6, tilt)
        p.r("neck", 3, 6 * tilt, 4 * tilt)
        p.r("head", -4, 28 * tilt, 10 * tilt)
        p.r("jaw", 3 + 3 * max(0, math.sin(4 * math.pi * u)))
        hang_arms(p, u, 0.2, 30)
        twitch(p, u, "R", 0.4, 0.03, 12)
        return plant(p)

    # ---- gait builder (biped stalking walk / follow)
    def biped(u, speed, frames, duty, lift, hips_drop, chest_pitch, arm_amp, head_pitch, bob, rise=0.0,
              stride_scale=1.0):
        T = frames / K.FPS
        p = Pose()
        travel = speed * duty * T
        for s, off in (("L", 0.0), ("R", 0.5)):
            tgt, contact, ss = foot_track(u, off, duty, travel, lift, feet[s] + Vector((0, -0.02, 0)))
            p.ik("thigh." + s, tgt, POLE_K, 1.0)
            pitch = 0.0 if contact else (25 * math.sin(math.pi * ss) - 10 * math.sin(2 * math.pi * ss))
            if contact:
                pitch = -8 * max(0.0, (ss - 0.75) / 0.25)  # heel peels off at the end of stance
            p.w("foot." + s, pitch, 0, 0)
        ph = 2 * math.pi * u
        p.l("hips", 0.02 * math.sin(ph), 0, -hips_drop + bob * math.cos(2 * ph))
        p.r("hips", 2.0, 0, 6 * math.sin(ph))
        p.r("hips", 0, 3 * math.sin(ph), 0)
        p.r("spine", 2 * math.cos(2 * ph), 0, -4 * math.sin(ph))
        p.r("chest", chest_pitch + 1.5 * math.cos(2 * ph + 0.5), -2 * math.sin(ph), -5 * math.sin(ph))
        p.r("hump", -1.5 * math.cos(2 * ph + 1.0))
        p.r("neck", head_pitch * 0.5, 0, 4 * math.sin(ph))
        p.r("head", head_pitch * 0.5 - 1.5 * math.cos(2 * ph), 0, 3 * math.sin(ph))
        for s, sg in (("L", 1), ("R", -1)):
            # arms swing opposite to the legs, forearm/hands lag behind (loose)
            sw = math.sin(ph + (0 if s == "L" else math.pi))
            lag = math.sin(ph - 0.9 + (0 if s == "L" else math.pi))
            p.r("upperarm." + s, arm_amp * sw, 0, 0)
            p.r("forearm." + s, 8 + 0.6 * arm_amp * max(0, -lag) + 4, 0, 0)
            p.r("hand." + s, 6 + 0.5 * arm_amp * lag, 0, 0)
            # knuckles brush the ground at the back of the swing -> fingers drag and curl
            p.r("fingers." + s, -18 * max(0.0, lag) + 8, 0, 0)
        return p

    WALK_F = 48

    def walk(u, t):
        p = biped(u, 0.7, WALK_F, 0.62, 0.11, 0.09, 4, 16, 2, 0.02)
        return p

    FOLLOW_F = 33

    def follow(u, t):
        p = biped(u, 1.4, FOLLOW_F, 0.58, 0.13, 0.12, -16, 22, 6, 0.03)
        p.r("spine", -6)
        p.r("neck", 16)
        p.r("head", 8)
        return p

    # ---- run: aggressive gallop, long arms slap the ground alternately
    RUN_F = 18
    RT = RUN_F / K.FPS
    run_v = 5.5
    slapR, slapL = 0.40, 0.56

    def run(u, t):
        p = Pose()
        ph = 2 * math.pi * u
        # torso pitched far forward, rocking with the gallop
        p.l("hips", 0, 0.05, -0.2 + 0.06 * math.sin(ph - 0.6))
        p.r("hips", 22 + 8 * math.sin(ph + 0.4))
        p.r("spine", 12 + 6 * math.sin(ph + 1.2))
        p.r("chest", 6 + 6 * math.sin(ph + 1.8), 0, 0)
        p.r("hump", -4 * math.sin(ph + 2.0))
        p.r("neck", -38 + 6 * math.sin(ph + 2.2))
        p.r("head", -14 - 5 * math.sin(ph + 2.4), 0, 0)
        p.r("jaw", 14 + 8 * math.sin(ph))
        # hind legs
        for s, off in (("L", 0.0), ("R", 0.09)):
            r = feet[s] + Vector((0, 0.12, 0))
            tgt, contact, ss = foot_track(u, off, 0.24, run_v * 0.24 * RT, 0.3, r)
            p.ik("thigh." + s, tgt, POLE_K, 1.0)
            p.w("foot." + s, (0 if contact else 40 * math.sin(math.pi * ss)), 0, 0)
        # arms: IK during contact (slap), FK swing otherwise
        for s, off in (("R", slapR), ("L", slapL)):
            sg = 1 if s == "L" else -1
            r = Vector((0.36 * sg, -0.55, 0.215))
            tgt, contact, ss = foot_track(u, off, 0.2, run_v * 0.2 * RT, 0.5, r, lift_pow=0.8)
            # IK through the whole cycle: the swing arc lifts the hand clear of the ground
            w = 1.0
            cw = 1.0 if contact else max(0.0, 1 - ss * 5) + max(0.0, (ss - 0.85) * 6.6)
            cw = min(1.0, cw)
            p.ik("upperarm." + s, tgt, Vector((0.3 * sg, 1, 0.2)), w)
            # knuckle gallop: hand vertical, fingers curled back under the palm on contact
            if contact:
                p.w("hand." + s, -10, 0, 0)
            else:
                p.r("hand." + s, 35 * math.sin(math.pi * ss))
            p.r("fingers." + s, 95 * cw + (1 - cw) * 25 * math.sin(math.pi * ss))
        return p

    run_events = {"slap": sorted([int(round(slapR * RUN_F)) % RUN_F, int(round(slapL * RUN_F)) % RUN_F])}

    # ---- alert 0.8 s: freeze, then the head snaps to its left
    def alert(u, t):
        p = idle(0.0, 0.0)
        frz = smoothstep(ramp(t, 0.0, 0.12))
        p.r("chest", -3 * frz)
        p.r("hump", -2 * frz)
        snap = smoothstep(ramp(t, 0.32, 0.42))
        over = pulse(t, 0.38, 0.43, 0.46, 0.6)
        p.r("neck", -4 * snap, 6 * snap, 24 * snap)
        p.r("head", -8 * snap, 10 * snap, 48 * snap + 8 * over)
        p.r("jaw", 6 * snap)
        for s in "LR":
            p.r("fingers." + s, -14 * frz)
        p.r("spine", 0, 0, 6 * snap)
        return p

    # ---- inspect 3 s: leans sideways to peer around a trunk (to its right)
    def inspect(u, t):
        p = Pose()
        lean = smoothstep(ramp(u, 0.05, 0.35)) * (1 - smoothstep(ramp(u, 0.75, 0.97)))
        peer = lean * (0.5 + 0.5 * math.sin(2 * math.pi * 3 * u))
        p.l("hips", -0.05 * lean, 0, -0.03 * lean)
        p.r("hips", 0, -4 * lean, 0)
        p.r("spine", 0, -8 * lean, -4 * lean)
        p.r("chest", 4 * lean, -12 * lean, -8 * lean)
        p.r("neck", 0, 10 * lean, -8 * lean)
        p.r("head", 4 * peer, 16 * lean, -4 * lean + 5 * peer)
        # right hand braces on the 'trunk', left arm hangs
        p.r("upperarm.R", -40 * lean, 16 * lean, 0)
        p.r("forearm.R", -45 * lean)
        p.r("hand.R", -25 * lean)
        p.r("fingers.R", 25 * lean + 10 * peer)
        p.r("upperarm.L", 6 * lean, 6 * lean, 0)
        p.r("forearm.L", 10 * lean)
        breathe(p, u, 1, 0.5)
        return plant(p, {"R": Vector((-0.08 * lean, 0, 0))})

    # ---- attack 1.2 s: rears up with jaw wide, then long downward swipe (right arm)
    HIT = 22

    def attack(u, t):
        f = t * K.FPS
        k0 = Pose()
        k1 = Pose()  # windup / rear up (f 14)
        k1.l("hips", 0, 0.05, 0.05).r("hips", -12).r("spine", -12).r("chest", -18, 0, 10).r("hump", 4)
        k1.r("neck", 10).r("head", 18).r("jaw", 34)
        k1.r("upperarm.R", -150, -20, 0).r("forearm.R", 40).r("hand.R", 20).r("fingers.R", 25)
        k1.r("upperarm.L", -30, 10, 0).r("forearm.L", 30)
        k2 = Pose()  # swipe through (f 22 = hit)
        k2.l("hips", 0, -0.06, -0.08).r("hips", 14).r("spine", 14).r("chest", 18, 0, -16).r("hump", -3)
        k2.r("neck", -18).r("head", -10).r("jaw", 26)
        k2.r("upperarm.R", -45, 25, 0).r("forearm.R", 15).r("hand.R", -20).r("fingers.R", -10)
        k2.r("upperarm.L", 20, 0, 0).r("forearm.L", 10)
        k3 = Pose()  # follow-through (f 27)
        k3.l("hips", 0, -0.04, -0.1).r("hips", 16).r("spine", 12).r("chest", 12, 0, -20)
        k3.r("neck", -10).r("jaw", 14)
        k3.r("upperarm.R", 5, 30, 0).r("forearm.R", 25).r("fingers.R", -25)
        k3.r("upperarm.L", 15)
        p = keyed(f, [(0, k0), (5, k0.add(Pose().r("chest", -4).r("jaw", 4))), (14, k1), (17, k1.add(Pose().r("upperarm.R", -8))),
                      (HIT, k2), (27, k3), (36, k0)], mode='cr')
        hold = pulse(f, 0, 3, 12, 14)
        p.r("head", 0, 0, 0)
        return plant(p, {"R": Vector((0, -0.06 * smoothstep(ramp(f, 14, 22)) * (1 - smoothstep(ramp(f, 28, 36))), 0))})

    # ---- stagger 1.0 s: recoils after being stabbed
    def stagger(u, t):
        f = t * K.FPS
        k0 = Pose()
        k1 = Pose()  # impact (f 4)
        k1.l("hips", 0, 0.08, -0.03).r("hips", -10, 0, 8).r("spine", -14, -8, 6).r("chest", -20, 6, 10)
        k1.r("hump", 6).r("neck", 18, 0, -10).r("head", 25, -15, -18).r("jaw", 30)
        k1.r("upperarm.L", -45, 25, 0).r("forearm.L", 40).r("upperarm.R", -35, -30, 0).r("forearm.R", 55)
        k1.r("fingers.L", 30).r("fingers.R", 30)
        k2 = Pose()  # buckle (f 12)
        k2.l("hips", 0, 0.1, -0.12).r("hips", 12, 0, -6).r("spine", 10, 6, -4).r("chest", 14, -4, -6)
        k2.r("neck", -10, 8, 6).r("head", -10, 12, 10).r("jaw", 16)
        k2.r("upperarm.L", 10, 10, 0).r("forearm.L", 30).r("upperarm.R", -10, -10, 0).r("forearm.R", 40)
        k2.r("fingers.L", -20).r("fingers.R", -25)
        p = keyed(f, [(0, k0), (4, k1), (12, k2), (20, k2.add(k0, 0).add(Pose().r("chest", 4), 1)), (30, k0)],
                  mode='cr')
        p.r("head", 4 * tnoise(t, 3, 3) * (1 - ramp(f, 10, 30)), 0, 0)
        step = smoothstep(ramp(f, 3, 10))
        back = smoothstep(ramp(f, 3, 9)) * (1 - smoothstep(ramp(f, 18, 30)))
        lift = math.sin(math.pi * ramp(f, 3, 10)) * 0.12
        return plant(p, {"R": Vector((0, 0.18 * back, lift)), "L": Vector((0, 0.02 * step * (1 - ramp(f, 20, 30)), 0))})

    clips = [
        Clip("idle", 120, idle, loop=True, speed=0.0),
        Clip("listen", 90, listen, loop=True, speed=0.0),
        Clip("walk", WALK_F, walk, loop=True, speed=0.7, events={"step": [0, WALK_F // 2]}),
        Clip("follow", FOLLOW_F, follow, loop=True, speed=1.4, events={"step": [0, int(round(FOLLOW_F / 2))]}),
        Clip("run", RUN_F, run, loop=True, speed=run_v, events=run_events),
        Clip("alert", 24, alert, loop=False),
        Clip("inspect", 90, inspect, loop=True, speed=0.0),
        Clip("attack", 36, attack, loop=False, events={"hit": [HIT]}),
        Clip("stagger", 30, stagger, loop=False),
    ]
    return clips


def main():
    K.reset_scene()
    nz = K.Noise3(202)
    F, pt = build(nz)
    imp = K.importance_spheres([((0, -0.62, 1.98), 0.13, 1.0)] +
                               [(M(P["knuckle"], s) + [0, -0.02, -0.08], 0.12, 0.6) for s in (1, -1)])
    body = K.body_from_field(NAME + "_Body", F, 6600, displacement(nz), smooth_iter=2, importance_fn=imp)
    K.assign_body_materials(body, F, MATS, mat_rules(nz))
    arm = K.build_armature(NAME, bones())
    W = K.skin_body(body, arm)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    co = K.get_verts(body)
    W = K.side_cleanup(W, deform, co, eps=0.03)
    K.auto_assign_prim_bones(F, arm)
    W = K.refine_weights(arm, co, F, W, deform, sigma=0.02, own_mix=0.35)
    W = K.smooth_weights(body, W, iterations=2, factor=0.5)
    # rigid jaw
    wj = K.prim_ownership_weight(co, F, {"jaw"}, 0.012)
    W = K.override_weights(W, deform, "jaw", wj)
    K.write_weights(body, deform, W)
    K.add_tufts(body, pt, MATS, FUR, count=90, seed=5, length=(0.05, 0.13), radius=(0.014, 0.024))
    pobj = pt.build(NAME + "_Parts", MATS)
    K.finalize_join(body, pobj, pt, arm)
    K.uv_unwrap(body, repeat_m=0.6)
    rig = K.Rig(arm)
    clips = make_clips(rig)
    entry = K.finish_creature(NAME, arm, [body], clips, IK, eye_height=2.0,
                              preview_kwargs={"contact_view": (-1.0, -0.5, 0.25)})
    K.log("DONE", NAME, entry["tris"], "tris")


if __name__ == "__main__":
    main()
