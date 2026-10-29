"""kitB_treegen - procedural tree generator for Kit_Forest (artist B).

Recursive branching: every branch is a smooth random walk (coherent noise wander, gravity sag, upturn,
twist about the parent axis and a 'claw' curl that bends the tip back on itself), swept into a tapered tube
with bark UVs (U = integer repeats around, V = arc length / tile so bark tiles vertically along V).
Children are spawned along the parent by arc length with golden-angle phyllotaxis or whorls.
Foliage = bent alpha cards with full 0..1 UVs (base of the cluster image at V=0) and custom normals
pointing out of the crown (soft, volumetric shading on cards).
Every function takes explicit seeds -> deterministic.
"""
import math
from mathutils import Vector, Quaternion, Matrix, noise
from propkit_b_helpers import MB, add_tube, add_card, add_beam, rng, _perp

GOLDEN = math.radians(137.508)
UP = Vector((0, 0, 1))


class Branch:
    def __init__(self, pts, radii, level, segs):
        self.pts = pts
        self.radii = radii
        self.level = level
        self.segs = segs
        self.cum = [0.0]
        for i in range(1, len(pts)):
            self.cum.append(self.cum[-1] + (pts[i] - pts[i - 1]).length)
        self.length = self.cum[-1]
        self.children = []

    def sample(self, t):
        s = max(0.0, min(1.0, t)) * self.length
        for i in range(1, len(self.pts)):
            if self.cum[i] >= s or i == len(self.pts) - 1:
                seg = self.cum[i] - self.cum[i - 1]
                f = 0.0 if seg < 1e-9 else (s - self.cum[i - 1]) / seg
                f = max(0.0, min(1.0, f))
                p = self.pts[i - 1].lerp(self.pts[i], f)
                tan = (self.pts[i] - self.pts[i - 1]).normalized()
                r = self.radii[i - 1] * (1 - f) + self.radii[i] * f
                return p, tan, r
        return self.pts[-1], (self.pts[-1] - self.pts[-2]).normalized(), self.radii[-1]


def walk(start, d, length, nseg, r, wander=0.15, freq=0.6, gravity=0.0, upturn=0.0, curl=0.0, hook=0.0,
         twist=0.0, twist_axis=None, keep_above=0.25, seed_off=None, kink=0.0, kink_ang=(0.25, 0.55)):
    """Random-walk polyline.  curl (rad/total, early part) bends towards +up of the branch plane,
    hook (rad/total, last 35%) bends back down: claw-like fingers."""
    d = Vector(d).normalized()
    off = seed_off if seed_off is not None else Vector((r.uniform(0, 500), r.uniform(0, 500), r.uniform(0, 500)))
    pts = [Vector(start)]
    step = length / nseg
    ax = d.cross(UP)
    if ax.length < 1e-3:
        ax = _perp(d)
    ax.normalize()
    for i in range(nseg):
        t = (i + 0.5) / nseg
        q = pts[-1] * freq + off
        # (mathutils.noise.noise_vector is not deterministic in Blender 5.0 -> use 3 offset scalar lookups)
        nv = Vector((noise.noise(q), noise.noise(q + Vector((31.7, 0, 0))), noise.noise(q + Vector((0, 57.3, 0)))))
        d = d + nv * wander
        d = d + Vector((0, 0, -1)) * gravity * (0.3 + t)
        d = d + UP * upturn * t * t
        if curl:
            d = Quaternion(ax, curl / nseg * (1.0 if t < 0.65 else 0.3)) @ d
        if hook and t > 0.62:
            d = Quaternion(ax, -hook / (nseg * 0.38)) @ d
        if twist and twist_axis is not None:
            d = Quaternion(twist_axis, twist / nseg) @ d
        if kink and i > 0 and r.random() < kink:
            d = Quaternion(_perp(d) if r.random() < 0.5 else d.cross(UP).normalized() if d.cross(UP).length > 1e-3
                           else _perp(d), r.uniform(*kink_ang) * (1 if r.random() < 0.5 else -1)) @ d
        d.normalize()
        nxt = pts[-1] + d * step
        if nxt.z < keep_above:
            d.z = abs(d.z) * 0.5 + 0.05
            d.normalize()
            nxt = pts[-1] + d * step
        pts.append(nxt)
    return pts


def taper(n, r0, r1, power=1.0):
    return [r0 + (r1 - r0) * ((i / (n - 1)) ** power) for i in range(n)]


def child_dir(tan, azim, angle, ref=None):
    """Direction at `angle` (rad) away from tangent `tan`, rotated `azim` about it."""
    p = _perp(tan) if ref is None else (Vector(ref) - tan * Vector(ref).dot(tan)).normalized()
    p = Quaternion(tan, azim) @ p
    return (tan * math.cos(angle) + p * math.sin(angle)).normalized()


def sweep(mb, br, mat, tile_v=2.0, noise_fn=None, apex=True, cap1=False, urep=None, face_mat_fn=None, v0=0.0):
    if urep is None:
        urep = max(1, round(2 * math.pi * br.radii[0] / 1.5))
    tipped = apex and br.radii[-1] < 0.02
    return add_tube(mb, br.pts, br.radii, br.segs, mat, tile_v=tile_v, urep=urep, cap0=False,
                    cap1=(cap1 and not tipped), smooth=True, noise_fn=noise_fn, apex=tipped,
                    face_mat_fn=face_mat_fn, v0=v0)


def bark_noise(amp=0.08, lobes=0, lobe_amp=0.0, seed=0, flare=0.0, flare_h=0.4, br=None, twist=0.0):
    off = seed * 13.7

    def fn(i, j, a, dv=None):
        z = br.pts[i].z if br is not None else 0.0
        f = 1.0 + amp * noise.noise(Vector((math.cos(a) * 1.5 + off, math.sin(a) * 1.5, z * 1.3)))
        if lobes:
            f += lobe_amp * math.sin(lobes * a + z * twist + off)
        if flare:
            f *= 1.0 + flare * math.exp(-max(0.0, z) / flare_h)
        return f
    return fn


def add_roots(mb, center, r0, n, seed, mat, length=(1.2, 2.2), rad=(0.3, 0.45), segs=5, rise=0.0, nseg=5,
              avoid=None):
    """avoid=(azimuth, half_angle): keep roots out of that sector (e.g. the hollow)."""
    r = rng(seed)
    base_az = r.uniform(0, 6.283)
    for k in range(n):
        if avoid:
            span = 2 * math.pi - 2 * avoid[1]
            az = avoid[0] + avoid[1] + span * (k + 0.5) / n + r.uniform(-0.2, 0.2) * span / n
        else:
            az = base_az + k * 2 * math.pi / n + r.uniform(-0.35, 0.35)
        dv = Vector((math.cos(az), math.sin(az), 0))
        L = r0 * 2 + r.uniform(*length)
        pts = []
        for i in range(nseg + 1):
            t = i / nseg
            dist = r0 * 0.3 + L * t
            z = 0.55 * r0 * 2.0 * (1 - t) ** 1.6 - 0.12 * t + rise * math.sin(t * math.pi) * (0.5 + r.random())
            side = noise.noise(Vector((t * 2.0, k * 3.3, seed))) * 0.12 * t * L * (0.3 if avoid else 1.0)
            pts.append(Vector(center) + dv * dist + Vector((-dv.y, dv.x, 0)) * side + Vector((0, 0, z)))
        rr = taper(nseg + 1, r0 * r.uniform(*rad), 0.035, 0.8)
        b = Branch(pts, rr, 1, segs)
        sweep(mb, b, mat, tile_v=1.5, apex=True)


# ------------------------------------------------------------------------------------------------
# Pine
# ------------------------------------------------------------------------------------------------
def make_pine(seed, height=15.0, r0=0.32, whorls=20, per_whorl=(5, 6), dead_frac=0.33, crown_w=3.0,
              card_scale=1.0, lean=0.03, max_tris=3900):
    """Dark dense conifer.  Returns (MB, trunk Branch).
    Foliage per live branch: (a) steep V pairs of 'shelf' cards along the branch (read from above/below),
    (b) one 'shell' card tangent to the crown cone (reads from the side, so branches pointing at the
    viewer are never edge-on), (c) a tip card.  Leader = 3 crossed vertical cards."""
    r = rng(seed)
    mb = MB()
    BARK = 'MNF_BarkPine'
    LEAF = 'MNF_FoliagePine'
    d0 = Vector((r.uniform(-lean, lean), r.uniform(-lean, lean), 1)).normalized()
    pts = walk((0, 0, -0.15), d0, height + 0.15, 18, r, wander=0.035, freq=0.25, keep_above=-1)
    trunk = Branch(pts, taper(len(pts), r0, 0.03, 0.85), 0, 10)
    sweep(mb, trunk, BARK, tile_v=1.5, noise_fn=bark_noise(0.06, 0, 0, seed, flare=0.45, flare_h=0.35, br=trunk),
          apex=True)
    add_roots(mb, (0, 0, 0), r0, 5, seed + 1, BARK, length=(0.5, 1.0), rad=(0.35, 0.45), segs=5, nseg=4)
    axis = trunk

    def crown_normal(p):
        c, _, _ = axis.sample(max(0.0, min(1.0, p.z / height)))
        o = Vector((p.x - c.x, p.y - c.y, 0))
        o = o.normalized() if o.length > 1e-4 else Vector((0, 0, 0))
        return (o * 0.8 + UP * 0.6).normalized()

    def card(p, up, side, L, w, bend):
        segs = 2 if L > 1.1 else 1
        add_card(mb, p, up, side, w, L, LEAF, bend=bend, segs=segs, cnormal=crown_normal)

    t_live = dead_frac
    az0 = r.uniform(0, 6.28)
    branches = []
    for wi in range(whorls):
        t = 0.09 + 0.88 * (wi + r.uniform(-0.3, 0.3)) / whorls
        t = min(0.975, max(0.07, t))
        p, tan, rad = trunk.sample(t)
        n = r.randint(*per_whorl)
        az0 += GOLDEN * 0.7
        for k in range(n):
            az = az0 + k * 2 * math.pi / n + r.uniform(-0.35, 0.35)
            if t < t_live:
                if r.random() < 0.4:
                    continue
                L = r.uniform(0.4, 1.5) * (0.5 + t / t_live * 0.6)
                ang = math.radians(r.uniform(80, 108))
                dirv = child_dir(tan, az, ang, ref=(1, 0, 0))
                bp = walk(p, dirv, L, 3, r, wander=0.35, freq=1.3, gravity=0.06)
                b = Branch(bp, taper(len(bp), max(0.025, rad * 0.22), 0.008, 1.0), 2, 3)
                sweep(mb, b, BARK, tile_v=1.0, apex=True)
                if L > 0.8 and r.random() < 0.6:
                    pp, pt, pr = b.sample(0.5)
                    tw = walk(pp, child_dir(pt, r.uniform(0, 6.28), 0.7), L * 0.45, 2, r, wander=0.4)
                    sweep(mb, Branch(tw, [pr * 0.8, pr * 0.5, 0.005], 3, 3), BARK, tile_v=1.0)
                continue
            u = (t - t_live) / (1 - t_live)
            L = crown_w * (1.0 - u) ** 0.85 * r.uniform(0.8, 1.15) + 0.4
            ang = math.radians(106 - 46 * u + r.uniform(-8, 8))
            dirv = child_dir(tan, az, ang, ref=(1, 0, 0))
            bp = walk(p, dirv, L, 3, r, wander=0.12, freq=0.8, gravity=0.12 * (1 - u), upturn=0.28)
            b = Branch(bp, taper(len(bp), max(0.02, rad * 0.24), 0.006, 1.0), 1, 3)
            sweep(mb, b, BARK, tile_v=1.0, apex=True)
            branches.append((b, L, u))
    # foliage (budgeted)
    r2 = rng(seed + 99)
    for b, L, u in branches:
        if mb.tris() > max_tris - 40:
            break
        out = b.pts[-1] - b.pts[0]
        outh = Vector((out.x, out.y, 0))
        outh = outh.normalized() if outh.length > 1e-4 else Vector((1, 0, 0))
        tang = UP.cross(outh).normalized()
        cs = card_scale * r2.uniform(0.9, 1.12)
        # (a) shelf V pairs
        nc = 2 if L > 1.5 else 1
        for c in range(nc):
            tc = 0.3 + 0.45 * c if nc > 1 else 0.45
            cp, ct, _ = b.sample(tc)
            yaw = (0.5 if c % 2 == 0 else -0.5) * r2.uniform(0.5, 1.0)
            cd = (Quaternion(UP, yaw) @ ct + Vector((0, 0, -0.1))).normalized()
            cl = min(2.0, max(0.85, L * 0.7)) * cs
            sv = cd.cross(UP).normalized()
            for roll in (0.75, -0.75):
                card(cp, cd, Quaternion(cd, roll + r2.uniform(-0.15, 0.15)) @ sv, cl, cl * 0.85, cl * 0.16)
        # (b) cone shell card: base near the trunk, running down-outwards along the crown surface
        cp, _, _ = b.sample(0.12)
        beta = math.radians(r2.uniform(28, 42))
        upv = (outh * math.cos(beta) - UP * math.sin(beta)).normalized()
        cl = min(2.4, max(1.0, L * 0.95)) * cs
        card(cp + UP * 0.15, upv, tang, cl, cl * 0.9, cl * 0.1)
        # (c) tip card
        cp, ct, _ = b.sample(0.62)
        cl = min(1.6, max(0.75, L * 0.5)) * cs
        card(cp, (ct + UP * 0.25).normalized(), tang, cl, cl * 0.85, cl * 0.08)
    # leader
    top, ttan, _ = trunk.sample(0.88)
    for k in range(3):
        a = k * math.pi / 3 + r.uniform(-0.1, 0.1)
        sv = Vector((math.cos(a), math.sin(a), 0))
        add_card(mb, top, ttan, sv, 1.1 * card_scale, height * 0.14, LEAF, bend=0.05, segs=2, cnormal=crown_normal)
    return mb, trunk


# ------------------------------------------------------------------------------------------------
# Dead / gnarled trees
# ------------------------------------------------------------------------------------------------
def make_dead(seed, height=10.0, r0=0.32, trunk_frac=0.58, leaders=3, leader_ang=(18, 42), leader_r=(0.75, 0.95),
              laterals=4, lat_start=0.3, lat_ang=(50, 82), lat_len=0.45, lat_r=(0.5, 0.68), broken_p=0.25,
              sub=(2, 4), twigs=(1, 3), claw=1.0, droop=0.0, lean=0.12, snapped=False, mat='MNF_BarkDead',
              hollow=None, lobes=0, lobe_amp=0.0, trunk_segs=9, roots=5, root_len=(0.8, 1.8), root_rise=0.0,
              leaf_tufts=0, trunk_wander=0.1, flare=0.6, sides=(7, 5, 4, 3), hands=0.6, max_tris=3950,
              kink=0.28, limb_taper=1.35, trunk_taper=1.3, tuft_size=1.0, leader_len=1.0):
    """Twisted dead tree.  The trunk ends thick at trunk_frac*height and splits into `leaders` that reach up
    and hook inwards at the tips (claw); `laterals` are reaching arms from the trunk (some snapped off).
    droop>0 makes limbs sag and hang (weeping / melting look).  snapped=True: jagged broken trunk top."""
    r = rng(seed)
    mb = MB()
    az_lean = r.uniform(0, 6.28)
    d0 = Vector((math.cos(az_lean) * lean, math.sin(az_lean) * lean, 1)).normalized()
    th = height * trunk_frac
    pts = walk((0, 0, -0.15), d0, th + 0.15, 16, r, wander=trunk_wander, freq=0.22, keep_above=-1)
    if hollow:   # denser rings around the hollow so the cavity reads cleanly
        dense = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]):
            if a.z < hollow[1] + 0.3:
                for k in (1, 2):
                    dense.append(a.lerp(b, k / 3))
            dense.append(b)
        pts = dense
    if snapped:
        tip_r = r0 * 0.5
    elif leaders:
        tip_r = r0 * 0.62
    else:
        tip_r = 0.03
    trunk = Branch(pts, taper(len(pts), r0, tip_r, trunk_taper), 0, trunk_segs)

    hollow_w = None
    if hollow:
        hz0, hz1, hdepth, hwidth = hollow   # hollow on the -Y side

        FRONT = Vector((0, -1, 0))

        def hollow_w(i, dv):
            """0..1 cavity weight: an arch-shaped opening facing -Y, steep walls."""
            z = trunk.pts[min(i, len(trunk.pts) - 1)].z
            zt = (z - hz0) / (hz1 - hz0)
            if zt < 0 or zt > 1:
                return 0.0
            hw = hwidth * (1 - 0.55 * zt * zt)
            wa = Vector((dv.x, dv.y, 0)).normalized().dot(FRONT)
            wa = max(0.0, (wa - math.cos(hw)) / (1 - math.cos(hw)))
            wz = 1.0 if zt < 0.7 else math.cos((zt - 0.7) / 0.3 * math.pi / 2)
            return min(1.0, wa ** 0.35 * wz)

    base_fn = bark_noise(0.09, lobes, lobe_amp, seed, flare=flare, flare_h=0.45, br=trunk, twist=1.3)

    def trunk_fn(i, j, a, dv):
        f = base_fn(i, j, a)
        if hollow_w:
            f *= 1.0 - hdepth * hollow_w(i, dv)
        return f

    face_fn = None
    if hollow_w:
        def face_fn(i, j, dv):
            return 'MNF_WoodRotten' if hollow_w(i, dv) > 0.3 or hollow_w(i + 1, dv) > 0.3 else mat
    rings = sweep(mb, trunk, mat, tile_v=1.5, noise_fn=trunk_fn, apex=(tip_r < 0.02), cap1=(tip_r >= 0.02),
                  face_mat_fn=face_fn)
    if snapped:   # splintered top
        for vi in rings[-1]:
            mb.v[vi] = mb.v[vi] + Vector((0, 0, r.uniform(-0.3, 0.7) * r0 * 2))
        mb.fm[-1] = mb.mi('MNF_WoodRotten')
    if roots:
        add_roots(mb, (0, 0, 0), r0, roots, seed + 7, mat, length=root_len, rad=(0.32, 0.45), segs=5,
                  rise=root_rise, nseg=6 if root_rise else 5,
                  avoid=(-math.pi / 2, hollow[3] * 1.25) if hollow else None)

    tips = []
    limbs = []
    ptop, ttop, rtop = trunk.sample(1.0)
    az = r.uniform(0, 6.28)
    for li in range(leaders):
        az = az + 2 * math.pi / leaders + r.uniform(-0.4, 0.4)
        ang = math.radians(r.uniform(*leader_ang))
        dirv = child_dir(ttop, az, ang, ref=(1, 0, 0))
        L = (height - th) * r.uniform(0.95, 1.2) * leader_len / max(0.72, math.cos(ang)) * (1.0 if not droop else 0.9)
        limbs.append((ptop - ttop * rtop * 0.5, dirv, L, rtop * r.uniform(*leader_r), True))
    for li in range(laterals):
        t = lat_start + (0.92 - lat_start) * (li + r.uniform(0, 0.8)) / max(1, laterals)
        p, tan, rad = trunk.sample(t)
        az += GOLDEN + r.uniform(-0.3, 0.3)
        dirv = child_dir(tan, az, math.radians(r.uniform(*lat_ang)), ref=(1, 0, 0))
        L = height * lat_len * r.uniform(0.7, 1.05) * (1.0 - 0.4 * (t - lat_start))
        limbs.append((p, dirv, L, rad * r.uniform(*lat_r), False))
    for (p, dirv, L, rl0, leader) in limbs:
        broken = (not leader) and r.random() < broken_p
        if broken:
            L *= r.uniform(0.2, 0.35)
        nseg = 9 if L > 3 else 6
        outh = Vector((dirv.x, dirv.y, 0))
        outh = outh.normalized() if outh.length > 1e-3 else Vector((1, 0, 0))
        bp = walk(p, dirv, L, nseg, r, wander=0.28, freq=0.45, gravity=0.04 + droop, upturn=0.0 if droop else 0.08,
                  curl=(-claw * 0.45 if leader else claw * 0.5) if not droop else -0.2,
                  hook=(-claw * 0.9 if (leader and not droop) else claw * (1.7 if droop else 1.0)), twist=0.5,
                  twist_axis=UP, kink=kink)
        b = Branch(bp, taper(len(bp), rl0, (rl0 * 0.55) if broken else 0.012, limb_taper), 1,
                   sides[0] if rl0 > 0.08 else sides[1])
        sweep(mb, b, mat, tile_v=1.6, noise_fn=bark_noise(0.07, 0, 0, seed + len(tips), br=b), apex=not broken,
              cap1=broken)
        if broken:
            mb.fm[-1] = mb.mi('MNF_WoodRotten')
            continue
        ns = r.randint(*sub)
        hand = r.random() < hands
        az2 = r.uniform(0, 6.28)
        for si in range(ns + (2 if hand else 0)):
            if mb.tris() > max_tris - 120:
                break
            fing = hand and si < 3
            t2 = r.uniform(0.74, 0.9) if fing else r.uniform(0.22, 0.8)
            p2, tan2, rad2 = b.sample(t2)
            az2 += GOLDEN
            dir2 = child_dir(tan2, az2, math.radians(r.uniform(22, 45) if fing else r.uniform(30, 62)), ref=UP)
            L2 = b.length * (r.uniform(0.22, 0.34) if fing else r.uniform(0.3, 0.5) * (1.0 - 0.4 * t2))
            bp2 = walk(p2, dir2, L2, 5, r, wander=0.4, freq=1.0, gravity=0.03 + droop * 1.6,
                       curl=(claw * 0.6 if not droop else 0), hook=claw * (2.0 if fing else 1.4), twist=0.7,
                       twist_axis=tan2, kink=kink * 0.8)
            b2 = Branch(bp2, taper(len(bp2), max(0.016, rad2 * 0.75), 0.005, 1.1), 2, sides[2])
            sweep(mb, b2, mat, tile_v=1.2, apex=True)
            tips.append(b2)
            if fing:
                continue
            for ti in range(r.randint(*twigs)):
                if mb.tris() > max_tris - 60:
                    break
                p3, tan3, rad3 = b2.sample(r.uniform(0.35, 0.85))
                dir3 = child_dir(tan3, r.uniform(0, 6.28), math.radians(r.uniform(30, 55)), ref=UP)
                L3 = b2.length * r.uniform(0.3, 0.5)
                bp3 = walk(p3, dir3, L3, 3, r, wander=0.5, freq=1.8, gravity=droop * 2, hook=claw * 1.4)
                sweep(mb, Branch(bp3, taper(len(bp3), max(0.01, rad3 * 0.7), 0.004), 3, sides[3]), mat, tile_v=1.0)
    if leaf_tufts and tips:
        for k in range(leaf_tufts):
            b = tips[r.randrange(len(tips))]
            p, tan, _ = b.sample(r.uniform(0.4, 0.9))
            for roll in (0.0, 1.3):
                sv = Quaternion(tan, roll + r.uniform(-0.3, 0.3)) @ _perp(tan)
                s = r.uniform(0.7, 1.1) * tuft_size
                add_card(mb, p - tan * 0.1, (tan + UP * 0.6).normalized(), sv, s, s, 'MNF_FoliageLeaf', bend=0.1,
                         segs=1, cnormal=lambda q: (UP * 0.8 + (q - Vector((0, 0, q.z))).normalized() * 0.6).normalized())
    return mb, trunk


def trunk_col_bounds(trunk, zmax, shrink=0.85):
    """AABB of the trunk below zmax (ring centres +- radius)."""
    mn = Vector((1e9, 1e9, 0)); mx = Vector((-1e9, -1e9, 0))
    top = 0
    for p, rr in zip(trunk.pts, trunk.radii):
        if p.z > zmax:
            break
        if p.z < 0.0:
            continue
        rs = rr * shrink
        mn.x = min(mn.x, p.x - rs); mn.y = min(mn.y, p.y - rs)
        mx.x = max(mx.x, p.x + rs); mx.y = max(mx.y, p.y + rs)
        top = p.z
    mx.z = min(zmax, max(top, 1.0))
    return mn, mx
