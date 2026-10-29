"""kitB_previewtex - draw stand-in RGBA foliage card images for *preview renders only*.
They are written to SourceArt/Props/preview_tex/ and used only when the real texture set
(Assets/MonkeyNoFear/Art/Textures/<set>_A.png) does not exist yet.  Layout assumption shared with the
real textures: one cluster per image, attachment/base at the bottom centre (V=0), growing towards V=1.
Run with plain python (Pillow) or the Blender venv python."""
import os, math, random
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'SourceArt', 'Props', 'preview_tex'))
S = 512


def col(r, base, var):
    return tuple(max(0, min(255, int(base[i] + r.uniform(-var, var)))) for i in range(3)) + (255,)


def pine(r):
    im = Image.new('RGBA', (S, S), (20, 30, 18, 0))
    d = ImageDraw.Draw(im)
    # main stem: bottom centre to top
    stem = [(256 + 10 * math.sin(t * 3) * t, 505 - t * 470) for t in [i / 40 for i in range(41)]]
    twigs = []
    for i in range(1, 40):
        t = i / 40
        x, y = stem[i]
        env = math.sin(min(1, t * 1.25) * math.pi) ** 0.7 * 210 * (1 - 0.35 * t)
        for sgn in (-1, 1):
            if r.random() < 0.75:
                ln = env * r.uniform(0.6, 1.0)
                ang = math.radians(r.uniform(35, 60))
                ex = x + sgn * math.sin(ang) * ln
                ey = y - math.cos(ang) * ln
                twigs.append(((x, y), (ex, ey)))
    for (a, b) in twigs:
        d.line([a, b], fill=(45, 32, 22, 255), width=3)
    d.line(stem, fill=(50, 35, 24, 255), width=7)
    # needles along stem and twigs
    for (a, b) in twigs + [(stem[i], stem[i + 1]) for i in range(0, 40)]:
        n = int(math.dist(a, b) / 3) + 2
        for k in range(n):
            t = k / n
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            dirx, diry = (b[0] - a[0]), (b[1] - a[1])
            L = math.hypot(dirx, diry) + 1e-6
            dirx, diry = dirx / L, diry / L
            for sgn in (-1, 1):
                ang = math.radians(r.uniform(30, 65)) * sgn
                nx = dirx * math.cos(ang) - diry * math.sin(ang)
                ny = dirx * math.sin(ang) + diry * math.cos(ang)
                ln = r.uniform(14, 26) * (1 - 0.4 * t)
                c = col(r, (28, 48, 26), 12)
                d.line([(x, y), (x + nx * ln, y + ny * ln)], fill=c, width=2)
    return im.filter(ImageFilter.SMOOTH)


def leaf(r):
    im = Image.new('RGBA', (S, S), (30, 35, 15, 0))
    d = ImageDraw.Draw(im)
    branches = [((256, 510), (256 + r.uniform(-60, 60), 260))]
    for i in range(7):
        a = branches[0][0]
        t = r.uniform(0.2, 0.9)
        p = (a[0] + (branches[0][1][0] - a[0]) * t, a[1] + (branches[0][1][1] - a[1]) * t)
        branches.append((p, (p[0] + r.uniform(-200, 200), p[1] - r.uniform(80, 230))))
    for a, b in branches:
        d.line([a, b], fill=(45, 35, 25, 255), width=4)
    for _ in range(140):
        a, b = r.choice(branches)
        t = r.uniform(0.3, 1.0)
        x = a[0] + (b[0] - a[0]) * t + r.uniform(-30, 30)
        y = a[1] + (b[1] - a[1]) * t + r.uniform(-30, 30)
        w, h = r.uniform(16, 30), r.uniform(28, 46)
        ang = r.uniform(0, 360)
        leafim = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        ld = ImageDraw.Draw(leafim)
        c = col(r, (52, 62, 26), 18) if r.random() < 0.8 else col(r, (80, 60, 25), 15)
        ld.ellipse((32 - w / 2, 32 - h / 2, 32 + w / 2, 32 + h / 2), fill=c)
        ld.line([(32, 32 - h / 2), (32, 32 + h / 2)], fill=(30, 36, 16, 255), width=1)
        leafim = leafim.rotate(ang)
        im.alpha_composite(leafim, (int(x - 32), int(y - 32)))
    return im


def fern(r):
    im = Image.new('RGBA', (S, S), (25, 40, 15, 0))
    d = ImageDraw.Draw(im)
    for i in range(9):
        ang = math.radians(-70 + 140 * i / 8 + r.uniform(-8, 8))
        L = r.uniform(300, 430) * (1 - 0.25 * abs(math.sin(ang)))
        pts = []
        for k in range(30):
            t = k / 29
            a = ang * (0.4 + 1.2 * t)
            x = 256 + math.sin(a) * L * t
            y = 505 - math.cos(a) * L * t + (t * t) * L * 0.25 * abs(math.sin(ang))
            pts.append((x, y))
        d.line(pts, fill=(55, 60, 25, 255), width=3)
        for k in range(3, 29):
            t = k / 29
            x, y = pts[k]
            dx, dy = pts[k + 1][0] - x, pts[k + 1][1] - y
            ln = math.hypot(dx, dy) + 1e-6
            dx, dy = dx / ln, dy / ln
            lf = 40 * math.sin(t * math.pi) ** 0.8 + 4
            for sgn in (-1, 1):
                nx, ny = -dy * sgn, dx * sgn
                c = col(r, (40, 70, 25), 12)
                d.polygon([(x, y), (x + nx * lf + dx * lf * 0.4, y + ny * lf + dy * lf * 0.4),
                           (x + dx * 8, y + dy * 8)], fill=c)
    return im


def grass(r):
    im = Image.new('RGBA', (S, S), (40, 45, 20, 0))
    d = ImageDraw.Draw(im)
    for i in range(90):
        x0 = 256 + r.uniform(-90, 90)
        L = r.uniform(200, 480)
        lean = r.uniform(-1, 1) * 160
        base = (x0, 512)
        c = col(r, (70, 78, 32), 20) if r.random() < 0.7 else col(r, (95, 80, 45), 18)
        pts = []
        for k in range(12):
            t = k / 11
            pts.append((x0 + lean * t * t, 512 - L * t + abs(lean) * 0.25 * t * t))
        for k in range(11):
            w = int(6 * (1 - k / 11)) + 1
            d.line([pts[k], pts[k + 1]], fill=c, width=w)
    return im


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name, fn, seed in (('pine_card', pine, 1), ('leaf_card', leaf, 2), ('fern_card', fern, 3),
                           ('grass_card', grass, 4)):
        fn(random.Random(seed)).save(os.path.join(OUT, name + '.png'))
        print('wrote', name)
