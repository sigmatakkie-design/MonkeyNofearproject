"""Lantern Mourner - tall, frail, light-seeking stalker with a glowing chest cavity and a cluster of broken
mining lamps hanging from its right hand (separate mesh skinned 100% to bone `lamps`, child of hand.R).
Run: <python-with-bpy> creature_lanternmourner.py -- [--no-preview]
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

NAME = "LanternMourner"
MATS = ["MNF_MournerSkin", "MNF_EyeWet", "MNF_Teeth", "MNF_MournerGlow"]
SKIN, EYE, BONE, GLOW = MATS
LAMP_MATS = ["MNF_MetalRusted", "MNF_Glass", "MNF_BulbWarm"]
METAL, GLASS, BULB = LAMP_MATS

# asymmetric skeleton: right shoulder hangs lower, head leans to its left
P = {
    "hips": (0, 0.05, 1.32), "spine": (0, 0.06, 1.62), "chest": (0, 0.0, 1.95), "neck": (0.0, -0.1, 2.28),
    "head": (0.05, -0.19, 2.44), "head_t": (0.1, -0.27, 2.64),
    "jaw": (0.05, -0.2, 2.42), "jaw_t": (0.065, -0.31, 2.38),
    "cavity": (0, -0.08, 1.9),
    "shoulder.L": (0.25, -0.04, 2.21), "elbow.L": (0.31, 0.02, 1.56), "wrist.L": (0.33, -0.04, 0.96),
    "knuckle.L": (0.33, -0.07, 0.79), "ftip.L": (0.32, -0.11, 0.57),
    "shoulder.R": (-0.23, -0.02, 2.07), "elbow.R": (-0.31, 0.03, 1.43), "wrist.R": (-0.34, -0.05, 0.84),
    "knuckle.R": (-0.34, -0.08, 0.67), "ftip.R": (-0.33, -0.12, 0.47),
    "thigh.L": (0.12, 0.07, 1.28), "knee.L": (0.145, -0.07, 0.68), "ankle.L": (0.135, 0.07, 0.10),
    "toe.L": (0.135, -0.17, 0.025),
}
for k in ("thigh", "knee", "ankle", "toe"):
    x, y, z = P[k + ".L"]
    P[k + ".R"] = (-x, y, z)
LAMP_HEAD = (-0.34, -0.1, 0.66)
LAMP_TAIL = (-0.34, -0.1, 0.36)


def bones():
    b = [
        BoneDef("root", (0, 0, 0), (0, 0, 0.3), None, deform=False),
        BoneDef("hips", P["hips"], P["spine"], "root"),
        BoneDef("spine", P["spine"], P["chest"], "hips", connect=True),
        BoneDef("chest", P["chest"], P["neck"], "spine", connect=True),
        BoneDef("socket_chestlight", P["cavity"], Vector(P["cavity"]) + Vector((0, -0.1, 0)), "chest", deform=False),
        BoneDef("neck", P["neck"], P["head"], "chest", connect=True),
        BoneDef("head", P["head"], P["head_t"], "neck", connect=True),
        BoneDef("jaw", P["jaw"], P["jaw_t"], "head"),
    ]
    for s in "LR":
        b += [
            BoneDef("upperarm." + s, P["shoulder." + s], P["elbow." + s], "chest"),
            BoneDef("forearm." + s, P["elbow." + s], P["wrist." + s], "upperarm." + s, connect=True),
            BoneDef("hand." + s, P["wrist." + s], P["knuckle." + s], "forearm." + s, connect=True),
            BoneDef("fingers." + s, P["knuckle." + s], P["ftip." + s], "hand." + s, connect=True),
            BoneDef("thigh." + s, P["thigh." + s], P["knee." + s], "hips"),
            BoneDef("shin." + s, P["knee." + s], P["ankle." + s], "thigh." + s, connect=True),
            BoneDef("foot." + s, P["ankle." + s], P["toe." + s], "shin." + s, connect=True),
        ]
    b.append(BoneDef("lamps", LAMP_HEAD, LAMP_TAIL, "hand.R"))
    return b


IK = [("thigh.L", "shin.L"), ("thigh.R", "shin.R"), ("upperarm.L", "forearm.L"), ("upperarm.R", "forearm.R")]


def A(k):
    return np.array(P[k], float)


def build(nz):
    F = K.Field((-0.6, -0.55, -0.02), (0.6, 0.45, 2.78), 0.0082)
    pt = K.Parts()
    rng = np.random.RandomState(61)
    # --- frail torso, thin waist, hollow chest
    F.add(Ellipsoid((0, 0.06, 1.3), (0.16, 0.12, 0.12), (8, 0, 0), SKIN, "hips", "pelvis"), k=0.05)
    F.add(Capsule((0, 0.06, 1.35), (0, 0.04, 1.72), 0.085, 0.1, SKIN, "spine", "waist"), k=0.06)
    rib = EllipsoidBetween((0, 0.05, 1.66), (0, -0.04, 2.16), 0.19, 0.135, SKIN, "chest", "ribcage",
                           y_hint=(0, -1, 0))
    F.add(rib, k=0.06)
    # uneven shoulders / clavicles
    for s in "LR":
        F.add(Capsule((0.0, -0.06, 2.14), A("shoulder." + s) + [0, 0, 0.02], 0.055, 0.06, SKIN, "chest", "clav"),
              k=0.05)
    # spine knobs along the back
    for i in range(9):
        t = i / 8
        c = np.array((0, 0.17 - 0.02 * t, 1.36 + 0.82 * t))
        F.add(Ellipsoid(c, (0.022, 0.02, 0.02), (0, 0, 0), SKIN, None, "vert"), k=0.022)
    # the hollow cavity (glow lined)
    F.sub(Ellipsoid((0, -0.12, 1.9), (0.1, 0.11, 0.15), (0, 0, 0), GLOW), k=0.015)
    # --- long neck, gaunt head leaning to its left
    F.add(Capsule((0, -0.06, 2.12), A("head") + [0, 0.02, 0], 0.06, 0.045, SKIN, "neck", "neck"), k=0.05)
    hc = np.array((0.07, -0.25, 2.53))
    F.add(EllipsoidBetween(hc + [-0.03, 0.04, -0.09], hc + [0.03, -0.04, 0.1], 0.075, 0.082, SKIN, "head", "skull",
                           y_hint=(0, -1, 0)), k=0.04)
    F.add(Ellipsoid(hc + [0, -0.06, -0.06], (0.05, 0.04, 0.06), (0, 12, 0), SKIN, "head", "face"), k=0.03)
    # swollen dark tissue over the eyes, leaving narrow slits
    for s in (1, -1):
        e = hc + np.array((0.032 * s, -0.075, 0.018))
        F.add(Ellipsoid(e + [0, 0, 0.012], (0.028, 0.018, 0.018), (0, 0, 0), SKIN, "head", "swell"), k=0.012)
        F.add(Ellipsoid(e + [0, 0.002, -0.014], (0.026, 0.017, 0.015), (0, 0, 0), SKIN, "head", "swell"), k=0.012)
        F.sub(Ellipsoid(e + [0, -0.012, 0], (0.02, 0.012, 0.0035), (0, 0, -8 * s)), k=0.003, keep=False)
        pt.ellipsoid(Vector(e + [0, -0.004, 0]), (0.017, 0.009, 0.004), EYE, rot=(0, 0, -8 * s), segs=8, rings=4,
                     bone="head")
    # small slack jaw
    F.add(EllipsoidBetween(A("jaw"), A("jaw_t"), 0.04, 0.02, SKIN, "jaw", "jaw", y_hint=(0, 0, 1)), k=0.02)
    # --- very long arms
    for s in "LR":
        sh, el, wr, kn = A("shoulder." + s), A("elbow." + s), A("wrist." + s), A("knuckle." + s)
        sg = 1 if s == "L" else -1
        F.add(Capsule(sh, el, 0.05, 0.034, SKIN, None, "upperarm"), k=0.035)
        F.add(Ellipsoid(el, 0.038, (0, 0, 0), SKIN, None, "elbow"), k=0.015)
        F.add(Capsule(el, wr, 0.034, 0.024, SKIN, None, "forearm"), k=0.02)
        F.add(FlatCapsule(wr, kn, 0.03, 0.033, up=(1, 0, 0), flat=0.45, mat=SKIN, tag="palm"), k=0.015)
        K.add_digits(F, pt, kn, along=(-0.02 * sg, -0.15, -1), spread_dir=(0, 1, 0), curl_dir=(-sg * 0.6, -0.8, 0),
                     n=4, length=0.22, r0=0.012, r1=0.008, spread=0.055, curl=40 if s == "R" else 25, mat=SKIN,
                     nail_mat=BONE, nail_len=0.02, seed=80 + sg, tag="fingers")
        th, kq, an, to = A("thigh." + s), A("knee." + s), A("ankle." + s), A("toe." + s)
        F.add(Capsule(th, kq, 0.07, 0.042, SKIN, None, "thigh"), k=0.04)
        F.add(Ellipsoid(kq + [0, -0.02, 0], 0.045, (0, 0, 0), SKIN, None, "knee"), k=0.015)
        F.add(Capsule(kq, an, 0.042, 0.03, SKIN, None, "shin"), k=0.02)
        F.add(FlatCapsule(an + [0, 0.02, -0.04], to + [0, 0, 0.0], 0.04, 0.03, up=(0, 0, 1), flat=0.5, mat=SKIN,
                          tag="foot"), k=0.02)
        K.add_digits(F, pt, to + [0, 0.02, 0.0], along=(0, -1, -0.2), spread_dir=(1, 0, 0), curl_dir=(0, 0, -1), n=4,
                     length=0.08, r0=0.013, r1=0.01, spread=0.06, curl=25, mat=SKIN, nail_mat=BONE, nail_len=0.015,
                     seed=90 + sg, tag="foot", segs=2)
    # --- cracked bone-like structures ringing the cavity (rigid to chest)
    for i in range(14):
        a = 2 * math.pi * i / 14 + rng.uniform(-0.1, 0.1)
        rim = np.array((0.1 * math.cos(a), -0.135 + 0.03 * abs(math.cos(a)), 1.9 + 0.145 * math.sin(a)))
        inward = np.array((-math.cos(a) * 0.8, -0.35, -math.sin(a) * 0.8))
        inward /= np.linalg.norm(inward)
        L = rng.uniform(0.04, 0.09)
        pt.cone(Vector(rim - inward * 0.03), Vector(rim + inward * L), rng.uniform(0.011, 0.018), BONE, segs=5,
                bone="chest", twist=rng.uniform(0, 3))
    # broken rib bars crossing the opening
    for z, w in ((1.98, 0.85), (1.88, 1.0), (1.79, 0.7)):
        a0 = np.array((-0.095 * w, -0.11, z + rng.uniform(-0.01, 0.01)))
        a1 = np.array((0.02 * w, -0.15, z - 0.02))
        pt.tube([Vector(a0), Vector((a0 + a1) / 2 + [0, -0.01, 0.005]), Vector(a1)], [0.011, 0.009, 0.006], BONE,
                segs=5, bone="chest")
    # glowing growths deep inside the cavity
    for i in range(4):
        c = np.array((rng.uniform(-0.05, 0.05), -0.05, 1.9 + rng.uniform(-0.07, 0.07)))
        pt.ellipsoid(Vector(c), rng.uniform(0.02, 0.035), GLOW, segs=8, rings=5, bone="chest", jitter=0.2, seed=i)
    return F, pt


def build_lamps():
    """Cluster of broken mining lamps, wires and metal fragments hanging from the right hand."""
    lp = K.Parts()
    rng = np.random.RandomState(71)
    hand = np.array(LAMP_HEAD)
    lamps = [((-0.30, -0.16, 0.38), 0.065, True), ((-0.42, -0.06, 0.30), 0.055, False),
             ((-0.35, 0.02, 0.22), 0.05, False), ((-0.26, -0.03, 0.47), 0.045, False)]
    for k, (c, r, lit) in enumerate(lamps):
        c = np.array(c)
        top = hand + np.array((rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), 0))
        mid = (top + c) / 2 + np.array((rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04), 0.03))
        lp.tube([Vector(top), Vector(mid), Vector(c + [0, 0, r * 1.6])], 0.0045, METAL, segs=4, bone="lamps")
        tilt = (rng.uniform(-35, 35), rng.uniform(-35, 35), rng.uniform(0, 360))
        from mathutils import Euler
        Rm = Euler([math.radians(x) for x in tilt], 'XYZ').to_matrix()
        up = Vector(Rm @ Vector((0, 0, 1)))
        cv = Vector(c)
        # housing: cage cylinder + cap
        lp.tube([cv + up * r * 1.3, cv + up * r * 0.9], [r * 0.7, r * 0.95], METAL, segs=8, bone="lamps")
        lp.tube([cv + up * r * 0.9, cv - up * r * 0.6], [r * 0.82, r * 0.82], GLASS, segs=8, bone="lamps")
        lp.tube([cv - up * r * 0.6, cv - up * r * 0.85], [r * 0.95, r * 0.6], METAL, segs=8, bone="lamps")
        # cage bars
        for b in range(4):
            a = 2 * math.pi * b / 4 + 0.4
            side = Vector(Rm @ Vector((math.cos(a), math.sin(a), 0)))
            lp.tube([cv + up * r * 0.9 + side * r * 0.9, cv - up * r * 0.6 + side * r * 0.9], 0.0035, METAL, segs=3,
                    bone="lamps")
        if lit:
            lp.ellipsoid(cv, r * 0.38, BULB, segs=8, rings=5, bone="lamps")
        elif k == 1:
            # broken: glass shards sticking out
            for j in range(3):
                d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.6))).normalized()
                lp.cone(cv + d * r * 0.7, cv + d * r * 1.4, r * 0.25, GLASS, segs=3, bone="lamps")
    # dangling loose wires and torn metal fragments
    for j in range(5):
        top = hand + np.array((rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), 0))
        end = top + np.array((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), -rng.uniform(0.2, 0.42)))
        mid = (top + end) / 2 + np.array((rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), 0.02))
        lp.tube([Vector(top), Vector(mid), Vector(end)], [0.004, 0.0035, 0.003], METAL, segs=3, bone="lamps")
    for j in range(5):
        c = hand + np.array((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), -rng.uniform(0.12, 0.35)))
        lp.box(Vector(c), (rng.uniform(0.03, 0.07), 0.004, rng.uniform(0.04, 0.09)), METAL,
               rot=(rng.uniform(0, 90), rng.uniform(0, 90), rng.uniform(0, 180)), bone="lamps")
    # bundle the hand clutches
    lp.tube([Vector(hand + [0, 0, 0.04]), Vector(hand - [0, 0, 0.06])], 0.022, METAL, segs=6, bone="lamps")
    return lp


def displacement(nz):
    def fn(co, nr):
        d = 0.003 * nz.fbm(co, 3, 3)
        d += 0.002 * nz(co * np.array([1, 1, 0.3]), 12, (2, 2, 2))  # tight stretched-skin creases
        return d
    return fn


def make_clips(rig):
    feet = {s: rig.tail("shin." + s) for s in "LR"}
    POLE_K = Vector((0, -1, 0))

    def plant(p, offs=None, w=1.0):
        offs = offs or {}
        for s in "LR":
            p.ik("thigh." + s, feet[s] + offs.get(s, Vector()), POLE_K, w)
            p.w("foot." + s)
        return p

    def lamp_swing(p, u, amp=1.0, phase=0.0, n=1):
        sw = math.sin(2 * math.pi * (n * u + phase))
        p.r("lamps", 6 * amp * sw, 0, 4 * amp * math.sin(2 * math.pi * (n * u + phase) + 1.3))
        return p

    def slump(p):
        p.r("spine", 4)
        p.r("chest", 12, -4, 0)
        p.r("neck", 12, 10, 0)
        p.r("head", 8, 14, 6)
        return p

    # ---- idle 4 s: swaying, lamps swinging slightly
    def idle(u, t):
        p = slump(Pose())
        sway = math.sin(2 * math.pi * u)
        b = math.sin(2 * math.pi * 2 * u)
        p.l("hips", 0.03 * sway, 0, 0.004 * b)
        p.r("hips", 0, 1.5 * sway, 0)
        p.r("spine", 1.2 * b, -2.5 * sway, 0)
        p.r("chest", -1.5 * b, -2 * sway, 1.5 * pnoise(u, 3))
        p.r("head", 2 * pnoise(u, 4), 3 * pnoise(u, 5), 3 * pnoise(u, 6))
        p.r("jaw", 4 + 2 * b)
        for s in "LR":
            p.r("upperarm." + s, -2 * sway * (1 if s == "L" else -1), 0, 0)
        lamp_swing(p, u, 1.0, 0.25)
        return plant(p)

    # ---- walk 0.9 m/s: slow, limping, the right foot drags
    WK_F = 60

    def walk(u, t):
        T = WK_F / K.FPS
        p = slump(Pose())
        ph = 2 * math.pi * u
        duty = 0.66
        for s, off, lift in (("L", 0.0, 0.1), ("R", 0.5, 0.035)):
            tgt, contact, ss = foot_track(u, off, duty, 0.9 * duty * T, lift, feet[s] + Vector((0, 0, 0)))
            p.ik("thigh." + s, tgt, POLE_K, 1.0)
            if s == "R":
                p.w("foot." + s, 0 if contact else -18 * math.sin(math.pi * ss))  # toes drag
            else:
                p.w("foot." + s, 0 if contact else 22 * math.sin(math.pi * ss))
        limp = max(0.0, math.sin(ph + math.pi))  # dips onto the bad leg
        p.l("hips", 0.035 * math.sin(ph), 0, -0.1 + 0.025 * math.cos(2 * ph) - 0.03 * limp)
        p.r("hips", 2, -3 * math.sin(ph), 5 * math.sin(ph))
        p.r("spine", 2, 2 * math.sin(ph), -4 * math.sin(ph))
        p.r("chest", 2 + 2 * math.cos(2 * ph), -3 * limp, -4 * math.sin(ph))
        p.r("neck", 0, 0, 3 * math.sin(ph + 0.6))
        p.r("head", -2 * math.cos(2 * ph), 3 * limp, 3 * math.sin(ph + 1.0))
        p.r("upperarm.L", 9 * math.sin(ph + math.pi), 0, 0)
        p.r("forearm.L", 6 + 6 * max(0.0, math.sin(ph + math.pi - 0.8)))
        p.r("upperarm.R", 5 * math.sin(ph), 0, 0)
        lamp_swing(p, u, 2.2, 0.15, 1)
        return p

    # ---- retreat 1.2 m/s: walks backwards while still facing forward
    RT_F = 40

    def retreat(u, t):
        T = RT_F / K.FPS
        p = slump(Pose())
        ph = 2 * math.pi * u
        duty = 0.62
        for s, off in (("L", 0.0), ("R", 0.5)):
            tgt, contact, ss = foot_track(u, off, duty, 1.2 * duty * T, 0.09, feet[s], fwd=(0, 1, 0))
            p.ik("thigh." + s, tgt, POLE_K, 1.0)
            p.w("foot." + s, 0 if contact else -15 * math.sin(math.pi * ss))
        p.l("hips", 0.03 * math.sin(ph), 0.04, -0.11 + 0.02 * math.cos(2 * ph))
        p.r("hips", -4, 0, 4 * math.sin(ph))
        p.r("chest", -6, 0, -3 * math.sin(ph))
        p.r("neck", 10)
        p.r("head", 8, 6, 0)
        # left hand held up in front of the cavity, guarding it
        p.ik("upperarm.L", Vector((0.12, -0.3, 1.72)), Vector((1, 0.3, -0.6)), 1.0)
        p.r("hand.L", -30, 0, -30).r("fingers.L", 25)
        p.r("upperarm.R", 8 * math.sin(ph))
        lamp_swing(p, u, 2.0, 0.3)
        return p

    # ---- turn_head 1.5 s: the head rolls toward a light on its left
    def turn_head(u, t):
        f = t * K.FPS
        p = idle(0.0, 0.0)
        r = smoothstep(ramp(f, 4, 34))
        hold = math.sin(f * 0.35) * pulse(f, 30, 36, 40, 45)
        p.r("neck", -10 * r, 22 * r, 30 * r)
        p.r("head", -18 * r, 38 * r + 2 * hold, 55 * r)
        p.r("jaw", 10 * r)
        p.r("chest", 0, 4 * r, 6 * r)
        lamp_swing(p, f / 45.0, 0.8, 0.25)
        return p

    # ---- reach 1.6 s: slow embrace with both long arms (hit f34)
    HIT = 34

    def reach(u, t):
        f = t * K.FPS
        p = idle(0.0, 0.0)
        lean = keyed(f, [(0, Pose()), (20, Pose().l("hips", 0, -0.05, -0.04).r("chest", 10).r("neck", 6).r("jaw", 18)),
                         (HIT, Pose().l("hips", 0, -0.14, -0.08).r("spine", 6).r("chest", 18).r("neck", 10)
                          .r("head", 10, -8, 0).r("jaw", 30)),
                         (40, Pose().l("hips", 0, -0.12, -0.07).r("spine", 5).r("chest", 16).r("jaw", 26)),
                         (48, Pose().r("chest", 4))], mode='cr')
        p = p.add(lean)
        rel = idle(0.0, 0.0)
        for s in "LR":
            sg = 1 if s == "L" else -1
            hang = rig.tail("forearm." + s)
            wide = Vector((0.85 * sg, -0.55, 1.55))
            hug = Vector((0.1 * sg, -0.95, 1.22))
            o = smoothstep(ramp(f, 2, 22))
            c = smoothstep(ramp(f, 24, HIT))
            back = smoothstep(ramp(f, 38, 48))
            tgt = hang.lerp(wide, o).lerp(hug, c).lerp(hang, back)
            p.ik("upperarm." + s, tgt, Vector((sg, 0.6, -0.3)), 1.0 - 0.0 * back)
            p.r("hand." + s, -30 * o * (1 - back), 0, 20 * sg * c * (1 - back))
            p.r("fingers." + s, (-20 * o + 60 * c) * (1 - back))
        p = plant(p)
        lamp_swing(p, f / 48.0, 2.5, 0.0)
        return p

    # ---- recoil 1.0 s: flinches away and covers the cavity
    def recoil(u, t):
        f = t * K.FPS
        base = idle(0.0, 0.0)
        k1 = Pose().l("hips", 0, 0.1, -0.05).r("hips", -6, 0, -10).r("spine", -8, 0, -6).r("chest", -14, 8, -14)
        k1.r("neck", 16, -10, -15).r("head", 22, -16, -20).r("jaw", 28)
        k1.r("upperarm.R", -25, 0, 15).r("forearm.R", -30)
        k2 = k1.add(Pose().r("chest", 4).r("head", 4))
        d = keyed(f, [(0, Pose()), (5, k1), (18, k2), (30, k2.add(k1, -0.35))], mode='cr')
        p = base.add(d)
        cover = smoothstep(ramp(f, 1, 6))
        # left forearm clamps across the cavity, right arm flung out with the lamps
        p.ik("upperarm.L", rig.tail("forearm.L").lerp(Vector((-0.02, -0.26, 1.82)), cover), Vector((1, 0, -0.4)),
             1.0)
        p.r("hand.L", -20 * cover, 0, -50 * cover).r("fingers.L", 40 * cover)
        p = plant(p, {"R": Vector((0, 0.14 * smoothstep(ramp(f, 2, 9)), 0.08 * math.sin(math.pi * ramp(f, 2, 9))))})
        lamp_swing(p, f / 30.0, 4.0 * (1 - ramp(f, 5, 30)), 0.0)
        return p

    return [
        Clip("idle", 120, idle, loop=True, speed=0.0),
        Clip("walk", WK_F, walk, loop=True, speed=0.9, events={"step": [0, WK_F // 2]}),
        Clip("retreat", RT_F, retreat, loop=True, speed=1.2, notes="Moves backwards (+Y in Blender / -Z in Unity) while facing forward."),
        Clip("turn_head", 45, turn_head, loop=False),
        Clip("reach", 48, reach, loop=False, events={"hit": [HIT]}),
        Clip("recoil", 30, recoil, loop=False),
    ]


def main():
    K.reset_scene()
    nz = K.Noise3(606)
    F, pt = build(nz)
    imp = K.importance_spheres([((0.07, -0.27, 2.52), 0.12, 1.0), ((0, -0.15, 1.9), 0.18, 0.7)])
    body = K.body_from_field(NAME + "_Body", F, 5600, displacement(nz), smooth_iter=2, importance_fn=imp)
    K.assign_body_materials(body, F, MATS, [])
    arm = K.build_armature(NAME, bones())
    W = K.skin_body(body, arm)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    co = K.get_verts(body)
    W = K.side_cleanup(W, deform, co, eps=0.04)
    K.auto_assign_prim_bones(F, arm)
    W = K.refine_weights(arm, co, F, W, deform, sigma=0.02, own_mix=0.35)
    W = K.smooth_weights(body, W, iterations=2, factor=0.5)
    W[:, deform.index("lamps")] = 0
    wj = K.prim_ownership_weight(co, F, {"jaw"}, 0.01)
    W = K.override_weights(W, deform, "jaw", wj)
    K.write_weights(body, deform, W)
    pobj = pt.build(NAME + "_Parts", MATS)
    K.finalize_join(body, pobj, pt, arm)
    K.uv_unwrap(body, repeat_m=0.6)
    # separate rigid lamp cluster skinned 100% to `lamps`
    lp = build_lamps()
    lamps = lp.build(NAME + "_Lamps", LAMP_MATS)
    vg = lamps.vertex_groups.new(name="lamps")
    vg.add(list(range(len(lamps.data.vertices))), 1.0, 'REPLACE')
    K.add_armature_modifier(lamps, arm)
    K.uv_unwrap(lamps, repeat_m=0.3)
    rig = K.Rig(arm)
    clips = make_clips(rig)
    entry = K.finish_creature(NAME, arm, [body, lamps], clips, IK, eye_height=2.47,
                              preview_kwargs={"contact_view": (-0.9, -0.8, 0.25)},
                              extra_manifest={"socket_chestlight": [round(x, 4) for x in P["cavity"]],
                                              "notes": "Lamp cluster is a separate mesh (LanternMourner_Lamps) "
                                                       "skinned 100% to bone 'lamps' (child of hand.R); "
                                                       "MNF_BulbWarm is the dimmable bulb. socket_chestlight is a "
                                                       "non-deforming bone at the cavity centre for a point light."})
    K.log("DONE", NAME, entry["tris"], "tris")


if __name__ == "__main__":
    main()
