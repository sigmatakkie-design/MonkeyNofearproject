"""Borer - massive tunnelling brute (battering-ram silhouette, crusted back).
Run: <python-with-bpy> creature_borer.py -- [--no-preview]
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

NAME = "Borer"
MATS = ["MNF_SkinDecayed", "MNF_MineralCrust", "MNF_FurDark", "MNF_Nails", "MNF_Flesh", "MNF_EyeWet"]
SKIN, CRUST, FUR, NAILS, FLESH, EYE = MATS

P = dict(
    hips=(0, 0.85, 1.00), spine=(0, 0.25, 1.17), chest=(0, -0.38, 1.28), neck=(0, -0.82, 1.12),
    head=(0, -1.04, 0.95), head_t=(0, -1.52, 0.84),
    jaw=(0, -1.12, 0.80), jaw_t=(0, -1.44, 0.74),
    mouth=(0.035, -1.30, 0.83), mouth_t=(0.035, -1.47, 0.82),
    shoulder=(0.52, -0.52, 1.18), elbow=(0.70, -0.55, 0.66), wrist=(0.62, -0.78, 0.24),
    knuckle=(0.62, -0.97, 0.09), ftip=(0.62, -1.16, 0.045),
    thigh=(0.38, 0.82, 0.88), knee=(0.48, 0.42, 0.50), ankle=(0.44, 0.88, 0.13), toe=(0.44, 0.56, 0.035),
)


def bones():
    b = [
        BoneDef("root", (0, 0, 0), (0, 0, 0.4), None, deform=False),
        BoneDef("hips", P["hips"], P["spine"], "root"),
        BoneDef("spine", P["spine"], P["chest"], "hips", connect=True),
        BoneDef("chest", P["chest"], P["neck"], "spine", connect=True),
        BoneDef("neck", P["neck"], P["head"], "chest", connect=True),
        BoneDef("head", P["head"], P["head_t"], "neck", connect=True),
        BoneDef("jaw", P["jaw"], P["jaw_t"], "head"),
        BoneDef("mouth.L", P["mouth"], P["mouth_t"], "head"),
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


BACK_ROCKS = []


def build(nz):
    F = K.Field((-1.15, -1.72, -0.03), (1.15, 1.45, 1.78), 0.0125)
    pt = K.Parts()
    rng = np.random.RandomState(31)
    # --- massive torso, shoulders higher than hips
    F.add(Ellipsoid((0, 0.85, 0.98), (0.42, 0.38, 0.36), (10, 0, 0), FUR, "hips", "pelvis"), k=0.12)
    F.add(Ellipsoid((0, 0.25, 1.02), (0.5, 0.52, 0.42), (5, 0, 0), SKIN, "spine", "belly"), k=0.16)
    F.add(Ellipsoid((0, -0.4, 1.08), (0.62, 0.6, 0.5), (-8, 0, 0), FUR, "chest", "chest"), k=0.16)
    # shoulder hump / trapezius mass rising above the head
    F.add(Ellipsoid((0, -0.45, 1.32), (0.55, 0.45, 0.22), (-10, 0, 0), CRUST, "chest", "hump"), k=0.16)
    for s in (1, -1):
        F.add(Ellipsoid(M((0.5, -0.52, 1.2), s), (0.28, 0.3, 0.3), (0, 0, 0), FUR, "chest", "deltoid"), k=0.12)
    # short neck, wedge head shaped by pressure (flattened, driven forward)
    F.add(Capsule((0, -0.7, 1.12), (0, -1.06, 0.95), 0.3, 0.22, FUR, "neck", "neck"), k=0.12)
    F.add(EllipsoidBetween((0, -0.98, 0.98), (0, -1.5, 0.84), 0.24, 0.12, SKIN, "head", "head",
                           y_hint=(0, 0, 1)), k=0.08)
    F.add(EllipsoidBetween((0, -0.95, 1.04), (0, -1.42, 0.92), 0.2, 0.06, CRUST, "head", "brow",
                           y_hint=(0, 0, 1)), k=0.06)
    F.add(Ellipsoid((0, -1.44, 0.86), (0.09, 0.08, 0.06), (0, 0, 0), SKIN, "head", "nose"), k=0.05)
    # lower jaw - heavy, under the wedge
    F.add(EllipsoidBetween((0, -1.1, 0.80), (0, -1.42, 0.74), 0.16, 0.06, SKIN, "jaw", "jaw", y_hint=(0, 0, 1)),
          k=0.05)
    # vertical split beneath the nose (flesh lined)
    F.sub(Ellipsoid((0, -1.43, 0.785), (0.022, 0.12, 0.085), (0, 0, 0), FLESH), k=0.008)
    F.sub(Ellipsoid((0, -1.36, 0.79), (0.05, 0.07, 0.06), (0, 0, 0), FLESH), k=0.01)
    # recessed eyes
    eye = np.array((0.13, -1.27, 0.95))
    F.sub(Ellipsoid(eye + [0.01, -0.01, 0.005], 0.04), k=0.02, keep=False, mirror=True)
    # --- thick forelimbs, shovel hands
    for s in (1, -1):
        sh, el, wr, kn = M(P["shoulder"], s), M(P["elbow"], s), M(P["wrist"], s), M(P["knuckle"], s)
        F.add(Capsule(sh, el, 0.21, 0.16, FUR, None, "upperarm"), k=0.1)
        F.add(Capsule(el, wr, 0.19, 0.14, SKIN, None, "forearm"), k=0.08)
        F.add(Ellipsoid(el + (wr - el) * 0.35, (0.21, 0.2, 0.3), (-30, 0, 0), FUR, None, "forearm"), k=0.1)
        F.add(FlatCapsule(wr + [0, -0.02, 0.0], kn + [0, 0, -0.02], 0.15, 0.15, up=(0, 0.6, 1), flat=0.5,
                          mat=SKIN, tag="palm"), k=0.06)
        K.add_digits(F, pt, kn + [0, 0, -0.02], along=(0, -1, -0.45), spread_dir=(1, 0, 0), curl_dir=(0, 0.2, -1),
                     n=4, length=0.17, r0=0.055, r1=0.048, spread=0.26, curl=35, mat=SKIN, nail_mat=None,
                     seed=70 + s, tag="fingers", fan=5, segs=2, k=0.03)
        for i in range(4):
            f = i / 3 - 0.5
            c = kn + np.array([f * 0.26, -0.21, -0.055])
            pt.rock(Vector(c), (0.045, 0.06, 0.03), NAILS, seed=300 + i + 10 * s, rot=(-25, 0, 0))
        # hind legs
        th, kq, an, to = M(P["thigh"], s), M(P["knee"], s), M(P["ankle"], s), M(P["toe"], s)
        F.add(Capsule(th, kq, 0.22, 0.14, FUR, None, "thigh"), k=0.1)
        F.add(Capsule(kq, an, 0.13, 0.09, SKIN, None, "shin"), k=0.06)
        F.add(FlatCapsule(an + [0, 0, -0.04], to, 0.1, 0.1, up=(0, 0, 1), flat=0.5, mat=SKIN, tag="foot"), k=0.05)
        for i in range(4):
            f = i / 3 - 0.5
            c = to + np.array([f * 0.18, -0.1, -0.005])
            pt.rock(Vector(c), (0.035, 0.05, 0.025), NAILS, seed=400 + i + 10 * s)
    # --- crust ridges on the back (SDF) + loose stones (parts)
    for i in range(7):
        t = i / 6
        c = np.array((rng.uniform(-0.1, 0.1), 0.9 - 1.55 * t, 1.33 + 0.1 * math.sin(math.pi * t)))
        F.add(Ellipsoid(c, (rng.uniform(0.12, 0.2), 0.14, 0.09), (rng.uniform(-20, 20), 0, rng.uniform(-30, 30)),
                        CRUST, None, "crust"), k=0.08)
    # eyes
    for s in (1, -1):
        pt.ellipsoid(eye * [s, 1, 1], 0.026, EYE, segs=8, rings=6, bone="head")
    # fleshy vibrating structures inside the split (rigid to mouth.L / mouth.R)
    for s, mb in ((1, "mouth.L"), (-1, "mouth.R")):
        for i in range(5):
            z = 0.84 - i * 0.03
            c = np.array((0.016 * s, -1.42 + 0.025 * abs(i - 2), z))
            pt.ellipsoid(Vector(c), (0.018, 0.035, 0.016), FLESH, rot=(0, 0, 10 * s), segs=6, rings=4, bone=mb,
                         jitter=0.2, seed=i + (10 if s > 0 else 0))
    return F, pt


def add_back_rocks(body, pt, count=30, seed=77):
    """Hard mineral growths / broken stone piercing the back."""
    rng = np.random.RandomState(seed)
    C = K.face_centers(body)
    N = K.face_normals(body)
    ok = np.nonzero((N[:, 2] > 0.45) & (C[:, 2] > 0.9) & (C[:, 1] > -1.05))[0]
    pick = rng.choice(ok, size=count, replace=False)
    for k, i in enumerate(pick):
        c, n = C[i], N[i]
        big = k < 12
        r = rng.uniform(0.09, 0.16) if big else rng.uniform(0.04, 0.08)
        elong = rng.uniform(1.0, 2.4)
        tilt = np.degrees(np.arccos(np.clip(n[2], -1, 1)))
        rot = (rng.uniform(-25, 25) + (tilt if n[1] < 0 else -tilt) * 0.5, rng.uniform(-25, 25), rng.uniform(0, 360))
        center = c + n * r * 0.35
        pt.rock(Vector(center), (r, r * rng.uniform(0.7, 1.0), r * elong * 0.8), CRUST, seed=500 + k, rot=rot,
                anchor=Vector(c), detail=1 if big else 0)
        if big:
            BACK_ROCKS.append((c, r))


def displacement(nz):
    def fn(co, nr):
        d = 0.012 * nz.fbm(co, 1.0, 3)
        back = np.clip((co[:, 2] - 1.15) / 0.15, 0, 1)
        d += back * 0.03 * np.maximum(nz(co, 2.2, (4, 4, 4)), -0.3)  # crusted lumps
        return d
    return fn


def mat_rules(nz):
    def rules(C, N, mats, owners):
        crusty = nz.fbm(C, 1.4, 2) > 0.1
        for i, o in enumerate(owners):
            if N[i, 2] > 0.55 and C[i, 2] > 1.1 and crusty[i]:
                mats[i] = CRUST
            if o.tag in ("belly", "chest", "pelvis") and N[i, 2] < -0.5:
                mats[i] = SKIN
        # crusted wounds: flesh ring around big back stones
        for c, r in BACK_ROCKS:
            d = np.linalg.norm(C - c, axis=1)
            ring = (d > r * 0.7) & (d < r * 1.05)
            mats[ring] = FLESH
        return mats
    return [rules]


def make_clips(rig):
    hands = {s: rig.tail("forearm." + s) for s in "LR"}
    feet = {s: rig.tail("shin." + s) for s in "LR"}
    pole_a = lambda s: Vector((0.5 if s == "L" else -0.5, 1.0, 0.0))
    pole_l = lambda s: Vector((0.2 if s == "L" else -0.2, -1.0, 0.0))

    def plant(p, offs=None, w=1.0):
        offs = offs or {}
        for s in "LR":
            p.ik("upperarm." + s, hands[s] + offs.get("h" + s, Vector()), pole_a(s), w)
            p.w("hand." + s)
            p.ik("thigh." + s, feet[s] + offs.get("f" + s, Vector()), pole_l(s), w)
            p.w("foot." + s)
        return p

    def mouth_vibe(p, t, amp=1.0, freq=11.0, length=None):
        # loop-safe: an integer number of vibration cycles over the clip when its length is given
        if length:
            n = max(1, round(freq * length))
            v = math.sin(2 * math.pi * n * (t / length))
        else:
            v = math.sin(2 * math.pi * freq * t)
        p.r("mouth.L", 0, 0, (4 + 3 * v) * amp)
        p.r("mouth.R", 0, 0, -(4 - 3 * v) * amp)
        return p

    # ---- idle 4 s: heavy breathing, head swaying, sniffing the ground
    def idle(u, t):
        p = Pose()
        b = math.sin(2 * math.pi * 3 * u)
        p.l("hips", 0, 0, 0.012 * b)
        p.r("chest", -2.5 * b)
        p.r("spine", 1.0 * b)
        sniff = pulse(u, 0.5, 0.62, 0.8, 0.92)
        p.r("neck", 6 * sniff + 2 * pnoise(u, 3), 0, 8 * pnoise(u, 4))
        p.r("head", 18 * sniff + 3 * sniff * math.sin(2 * math.pi * 14 * u), 3 * pnoise(u, 5), 6 * pnoise(u, 6))
        p.r("jaw", 3 + 2 * b)
        mouth_vibe(p, t, 0.5 + sniff, length=4.0)
        p.l("hips", 0, -0.04 * sniff, -0.05 * sniff)
        return plant(p)

    # ---- sense 3 s: presses a palm flat on the ground, head low, feeling vibrations
    def sense(u, t):
        p = Pose()
        press = smoothstep(ramp(u, 0.0, 0.18)) * (1 - smoothstep(ramp(u, 0.85, 1.0)))
        lift = math.sin(math.pi * ramp(u, 0.0, 0.18)) + math.sin(math.pi * ramp(u, 0.85, 1.0))
        p.l("hips", 0.05 * press, -0.06 * press, -0.12 * press)
        p.r("hips", 4 * press)
        p.r("chest", 8 * press, 0, -6 * press)
        p.r("neck", 18 * press, 0, -10 * press)
        listen = math.sin(2 * math.pi * 2 * u) * press
        p.r("head", 22 * press, 12 * press + 4 * listen, -8 * press)
        mouth_vibe(p, t, 1.2 * press + 0.3, 17, length=3.0)
        plant(p, {"hR": Vector((0.1, -0.25 * press, 0.25 * lift)), "hL": Vector((0, 0.05 * press, 0))})
        # right palm flattened, fingers spread and pressing; occasional pulse
        tremor = 0.5 + 0.5 * math.sin(2 * math.pi * 6 * u)
        p.w("hand.R", -60 * press, 0, 0)
        p.r("fingers.R", 50 * press - 6 * tremor * press)
        return p

    # ---- walk 1.3 m/s: knuckle-walk, lateral sequence
    WK_F = 36
    CH_F = 18

    def quad(u, frames, speed, duty, lift_h, lift_f, low, pitch, seq, sway=1.0):
        T = frames / K.FPS
        p = Pose()
        ph = 2 * math.pi * u
        p.l("hips", 0.03 * math.sin(ph) * sway, 0, -low + 0.03 * math.cos(2 * ph))
        p.r("hips", pitch, 0, 5 * math.sin(ph) * sway)
        p.r("spine", 2 * math.cos(2 * ph), 0, -4 * math.sin(ph) * sway)
        p.r("chest", 2 * math.cos(2 * ph + 0.6), 4 * math.sin(ph) * sway, -5 * math.sin(ph + 0.4) * sway)
        p.r("neck", -pitch * 0.4, 0, 6 * math.sin(ph + 1.0) * sway)
        p.r("head", -2 * math.cos(2 * ph), 0, -4 * math.sin(ph + 1.3) * sway)
        for key, off in seq.items():
            s = key[1]
            if key[0] == "h":
                tgt, contact, ss = foot_track(u, off, duty, speed * duty * T, lift_h, hands[s])
                p.ik("upperarm." + s, tgt, pole_a(s), 1.0)
                p.w("hand." + s, 0 if contact else 25 * math.sin(math.pi * ss))
                p.r("fingers." + s, 0 if contact else 15 * math.sin(math.pi * ss))
            else:
                tgt, contact, ss = foot_track(u, off, duty, speed * duty * T, lift_f, feet[s])
                p.ik("thigh." + s, tgt, pole_l(s), 1.0)
                p.w("foot." + s, 0 if contact else 20 * math.sin(math.pi * ss))
        return p

    def walk(u, t):
        p = quad(u, WK_F, 1.3, 0.66, 0.18, 0.14, 0.03, 2, {"fL": 0.0, "hL": 0.25, "fR": 0.5, "hR": 0.75})
        mouth_vibe(p, t, 0.6, length=WK_F / K.FPS)
        return p

    def charge(u, t):
        p = quad(u, CH_F, 4.5, 0.36, 0.35, 0.28, 0.12, 8, {"fL": 0.0, "fR": 0.08, "hL": 0.48, "hR": 0.58},
                 sway=0.4)
        ph = 2 * math.pi * u
        p.r("spine", 6 * math.sin(ph))
        p.r("chest", 5 * math.sin(ph + 0.5))
        p.r("neck", 10)
        p.r("head", 8)  # wedge head down like a ram
        p.r("jaw", 10)
        mouth_vibe(p, t, 1.5, 15, length=CH_F / K.FPS)
        return p

    # ---- attack 1.4 s: rears up, then slams both forearms down (hit f28)
    HIT = 28

    def attack(u, t):
        f = t * K.FPS
        base = Pose()
        rear = Pose().l("hips", 0, 0.25, 0.2).r("hips", -38).r("spine", -12).r("chest", -10).r("neck", 20).r("head", 12)
        rear.r("jaw", 25)
        for s in "LR":
            sg = 1 if s == "L" else -1
            rear.r("upperarm." + s, -150, 0, -10 * sg).r("forearm." + s, -40).r("hand." + s, -20)
        slam = Pose().l("hips", 0, -0.15, -0.12).r("hips", 8).r("spine", 6).r("chest", 8).r("neck", -6).r("head", -4)
        slam.r("jaw", 18)
        rec = Pose().l("hips", 0, -0.05, -0.04).r("hips", 2).r("chest", 2)
        d = keyed(f, [(0, base), (6, base.add(Pose().l("hips", 0, -0.05, -0.08).r("chest", 4))), (18, rear),
                      (22, rear.add(Pose().r("upperarm.L", -10).r("upperarm.R", -10))), (HIT, slam), (32, slam),
                      (42, rec)], mode='cr')
        p = d
        # arms: FK during the rear-up, IK onto the slam points for the impact
        ikw = smoothstep(ramp(f, 24, HIT)) * (1 - smoothstep(ramp(f, 34, 42))) + smoothstep(ramp(f, 34, 42)) + \
            (1 - smoothstep(ramp(f, 4, 12)))
        ikw = min(1.0, ikw)
        for s in "LR":
            sg = 1 if s == "L" else -1
            slam_pt = hands[s] + Vector((-0.12 * sg, -0.35, 0.0)) * smoothstep(ramp(f, 20, HIT)) * \
                (1 - smoothstep(ramp(f, 32, 42)))
            p.ik("upperarm." + s, slam_pt, pole_a(s), ikw)
            if ikw > 0.5:
                p.w("hand." + s)
            p.ik("thigh." + s, feet[s], pole_l(s), 1.0)
            p.w("foot." + s)
        mouth_vibe(p, t, 1.0 + pulse(f, 20, 26, 30, 36) * 2)
        return p

    # ---- emerge 2.0 s: from fully below ground, claws its way up to standing on z=0
    def emerge(u, t):
        f = t * K.FPS
        rise = keyed(f, [(0, Pose().l("hips", 0, 0.1, -3.3)), (14, Pose().l("hips", 0, 0.05, -2.3)),
                         (30, Pose().l("hips", 0, 0, -1.15)), (46, Pose().l("hips", 0, 0, -0.3)),
                         (60, Pose())], mode='cr')
        p = rise
        up = 1 - smoothstep(ramp(f, 40, 60))
        p.r("hips", -30 * up * (1 - ramp(f, 30, 50)) - 10 * up)
        p.r("chest", -10 * up)
        p.r("neck", 20 * up)
        p.r("head", 10 * up + 6 * math.sin(f * 0.9) * pulse(f, 12, 18, 30, 40))
        p.r("jaw", 30 * pulse(f, 10, 16, 28, 40))
        # hands burst up through the surface and slam down on it, then pull
        for s, off in (("L", 0), ("R", 5)):
            sg = 1 if s == "L" else -1
            reach = pulse(f, 4 + off, 12 + off, 14 + off, 20 + off)
            p.r("upperarm." + s, -160 * reach * (1 - ramp(f, 18 + off, 22 + off)), 0, -10 * sg * reach)
            p.r("forearm." + s, -20 * reach)
            grabw = smoothstep(ramp(f, 18 + off, 22 + off))
            anchor = hands[s] + Vector((0.15 * sg, -0.35, 0.0))
            anchor = anchor.lerp(hands[s], smoothstep(ramp(f, 46, 60)))
            p.ik("upperarm." + s, anchor, pole_a(s), grabw)
            if grabw > 0.5:
                p.w("hand." + s)
        legw = smoothstep(ramp(f, 44, 54))
        for s in "LR":
            sg = 1 if s == "L" else -1
            p.r("thigh." + s, -40 * (1 - legw))
            p.r("shin." + s, 40 * (1 - legw))
            p.ik("thigh." + s, feet[s], pole_l(s), legw)
            if legw > 0.5:
                p.w("foot." + s)
        mouth_vibe(p, t, 1.5)
        return p

    # ---- burrow 2.0 s: digs down head first until below ground
    def burrow(u, t):
        f = t * K.FPS
        sink = keyed(f, [(0, Pose()), (12, Pose().l("hips", 0, -0.05, -0.15)), (30, Pose().l("hips", 0, -0.2, -0.8)),
                         (46, Pose().l("hips", 0, -0.3, -1.7)), (60, Pose().l("hips", 0, -0.3, -2.9))], mode='cr')
        p = sink
        dive = smoothstep(ramp(f, 6, 30))
        p.r("hips", 30 * dive)
        p.r("spine", 12 * dive)
        p.r("chest", 14 * dive)
        p.r("neck", 20 * dive)
        p.r("head", 18 * dive)
        p.r("jaw", 12 * dive)
        # alternating scooping strokes with the shovel hands
        for s, off in (("L", 0.0), ("R", 0.5)):
            sg = 1 if s == "L" else -1
            dig = dive * (1 - ramp(f, 50, 60))
            ph = 2 * math.pi * (f / 15.0 + off)
            p.r("upperarm." + s, (-50 + 45 * math.sin(ph)) * dig, 0, -15 * sg * dig)
            p.r("forearm." + s, (-20 - 30 * math.cos(ph)) * dig)
            p.r("hand." + s, -30 * dig)
            w = 1 - smoothstep(ramp(f, 4, 12))
            p.ik("upperarm." + s, hands[s], pole_a(s), w)
            kick = math.sin(2 * math.pi * (f / 12.0 + off)) * smoothstep(ramp(f, 24, 36))
            legw = 1 - smoothstep(ramp(f, 20, 30))
            p.ik("thigh." + s, feet[s], pole_l(s), legw)
            p.r("thigh." + s, 30 * kick)
            p.r("shin." + s, -20 * kick)
        mouth_vibe(p, t, 1.5)
        return p

    # ---- stagger 1.0 s
    def stagger(u, t):
        f = t * K.FPS
        k1 = Pose().l("hips", 0, 0.2, 0.05).r("hips", -12, 0, 6).r("spine", -6, 4, 0).r("chest", -10, 6, 10)
        k1.r("neck", 12, 0, -14).r("head", 16, -10, -10).r("jaw", 30)
        k2 = Pose().l("hips", 0, 0.12, -0.15).r("hips", 8, 0, -4).r("chest", 10, -4, -6).r("neck", -8).r("head", -6)
        k2.r("jaw", 10)
        p = keyed(f, [(0, Pose()), (4, k1), (14, k2), (30, Pose())], mode='cr')
        back = smoothstep(ramp(f, 2, 8)) * (1 - smoothstep(ramp(f, 16, 30)))
        lift = math.sin(math.pi * ramp(f, 2, 9))
        plant(p, {"hL": Vector((0, 0.25 * back, 0.2 * lift)), "hR": Vector((0, 0.12 * back, 0.1 * lift))})
        mouth_vibe(p, t, 2.0)
        return p

    return [
        Clip("idle", 120, idle, loop=True, speed=0.0),
        Clip("sense", 90, sense, loop=True, speed=0.0),
        Clip("walk", WK_F, walk, loop=True, speed=1.3, events={"step": [0, WK_F // 2]}),
        Clip("charge", CH_F, charge, loop=True, speed=4.5, events={"step": [0, int(round(0.48 * CH_F))]}),
        Clip("attack", 42, attack, loop=False, events={"hit": [HIT]}),
        Clip("emerge", 60, emerge, loop=False, notes="Frame 0: whole body below z=0; ends standing on z=0."),
        Clip("burrow", 60, burrow, loop=False, notes="Ends with the whole body below z=0."),
        Clip("stagger", 30, stagger, loop=False),
    ]


def main():
    K.reset_scene()
    nz = K.Noise3(505)
    F, pt = build(nz)
    imp = K.importance_spheres([((0, -1.32, 0.85), 0.2, 1.0)])
    body = K.body_from_field(NAME + "_Body", F, 5900, displacement(nz), smooth_iter=2, importance_fn=imp)
    add_back_rocks(body, pt)
    K.assign_body_materials(body, F, MATS, mat_rules(nz))
    arm = K.build_armature(NAME, bones())
    W = K.skin_body(body, arm)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    co = K.get_verts(body)
    W = K.side_cleanup(W, deform, co, eps=0.05)
    K.auto_assign_prim_bones(F, arm)
    W = K.refine_weights(arm, co, F, W, deform, sigma=0.04, own_mix=0.35)
    W = K.smooth_weights(body, W, iterations=2, factor=0.5)
    wj = K.prim_ownership_weight(co, F, {"jaw"}, 0.03)
    W = K.override_weights(W, deform, "jaw", wj)
    # split lips around the vertical mouth follow mouth.L / mouth.R
    lips = np.clip((-1.36 - co[:, 1]) / 0.05, 0, 1) * np.clip(1 - np.abs(co[:, 2] - 0.79) / 0.1, 0, 1) * \
        np.clip(1 - np.abs(co[:, 0]) / 0.09, 0, 1)
    W = K.override_weights(W, deform, "mouth.L", lips * (co[:, 0] > 0.002))
    W = K.override_weights(W, deform, "mouth.R", lips * (co[:, 0] < -0.002))
    K.write_weights(body, deform, W)
    pobj = pt.build(NAME + "_Parts", MATS)
    K.finalize_join(body, pobj, pt, arm)
    K.uv_unwrap(body, repeat_m=0.9)
    rig = K.Rig(arm)
    clips = make_clips(rig)
    entry = K.finish_creature(NAME, arm, [body], clips, IK, eye_height=0.95,
                              preview_kwargs={"contact_view": (-1.0, -0.6, 0.35)},
                              extra_manifest={"shoulder_height": 1.5})
    K.log("DONE", NAME, entry["tris"], "tris")


if __name__ == "__main__":
    main()
