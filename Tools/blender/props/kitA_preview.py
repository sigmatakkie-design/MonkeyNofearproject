"""kitA_preview.py - Cycles CPU preview tiles / contact sheets for prop artist A kits.

Each object is rendered alone on a checker floor (cell size printed on the tile) and, for large
props, next to a 1.7 m mannequin.  Tiles are combined into 640x480 sheets (2x2) with labels.
"""
import bpy
import math
import os
from mathutils import Vector

import propkit_a_helpers as H

SCRATCH = os.environ.get("KITA_SCRATCH", "/tmp/kitA_tiles")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

VIEWS = {
    "iso": (0.9, -1.5, 0.85),       # front-right, above
    "isol": (-0.9, -1.5, 0.85),     # front-left
    "side": (1.0, -0.12, 0.18),     # from +X (profile of tools lying along Y)
    "sidehi": (1.0, -0.35, 0.6),
    "front": (0.12, -1.0, 0.25),
    "top": (0.35, -0.6, 1.4),
    "back": (0.8, 1.3, 0.7),
    "under": (0.9, -1.2, -0.5),
}


def _pmat(name, color, rough=0.6):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def _floor_mat(cell):
    name = "PREVIEW_Floor_%g" % cell
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.8
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    acc = None
    for i in (0, 1):
        d = nt.nodes.new("ShaderNodeMath"); d.operation = "DIVIDE"; d.inputs[1].default_value = cell
        nt.links.new(sep.outputs[i], d.inputs[0])
        f = nt.nodes.new("ShaderNodeMath"); f.operation = "FLOOR"
        nt.links.new(d.outputs[0], f.inputs[0])
        if acc is None:
            acc = f
        else:
            a = nt.nodes.new("ShaderNodeMath"); a.operation = "ADD"
            nt.links.new(acc.outputs[0], a.inputs[0]); nt.links.new(f.outputs[0], a.inputs[1])
            acc = a
    mod = nt.nodes.new("ShaderNodeMath"); mod.operation = "FLOORED_MODULO"; mod.inputs[1].default_value = 2.0
    nt.links.new(acc.outputs[0], mod.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs[6].default_value = (0.22, 0.22, 0.23, 1)
    mix.inputs[7].default_value = (0.36, 0.36, 0.37, 1)
    nt.links.new(mod.outputs[0], mix.inputs[0])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    return m


def setup_scene(res=(320, 240), samples=16):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.cycles.max_bounces = 4
    sc.cycles.transmission_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.threads_mode = "FIXED"
    sc.render.threads = 4
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "None"
    except Exception:
        pass
    if sc.world is None:
        sc.world = bpy.data.worlds.new("PreviewWorld")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.09, 0.095, 0.105, 1)
    bg.inputs[1].default_value = 1.0
    col = bpy.data.collections.get("PREVIEW") or bpy.data.collections.new("PREVIEW")
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    if not bpy.data.objects.get("PV_Key"):
        for name, rot, en in (("PV_Key", (50, 10, -35), 1.6), ("PV_Fill", (65, 0, 150), 0.4), ("PV_Rim", (35, 0, 70), 0.8)):
            ld = bpy.data.lights.new(name, "SUN")
            ld.energy = en
            ld.angle = math.radians(4)
            lo = bpy.data.objects.new(name, ld)
            lo.rotation_euler = [math.radians(a) for a in rot]
            col.objects.link(lo)
    if not bpy.data.objects.get("PV_Cam"):
        cd = bpy.data.cameras.new("PV_Cam")
        cd.lens = 50
        cd.sensor_width = 36
        co = bpy.data.objects.new("PV_Cam", cd)
        col.objects.link(co)
        sc.camera = co
    return col


def make_floor(z, cell, col):
    fl = bpy.data.objects.get("PV_Floor")
    if fl is None:
        me = bpy.data.meshes.new("PV_Floor")
        s = 200
        me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        fl = bpy.data.objects.new("PV_Floor", me)
        col.objects.link(fl)
    fl.data.materials.clear()
    fl.data.materials.append(_floor_mat(cell))
    fl.location = (0, 0, z)
    return fl


def make_figure(col):
    """1.7 m neutral mannequin (preview only)."""
    fig = bpy.data.objects.get("PV_Figure")
    if fig:
        return fig
    mb = H.MB(1.0)
    mat = "MNF_Plastic_Gray"
    for sx in (-0.1, 0.1):
        mb.add(H.cyl(0.065, 0.82, 10, r2=0.075), mat, H.xf((sx, 0, 0.04)))
        mb.add(H.box(0.11, 0.24, 0.05, 0.015), mat, H.xf((sx, -0.05, 0.025)))
    mb.add(H.lathe([(0, 0.85), (0.17, 0.86), (0.19, 1.05), (0.21, 1.36), (0.12, 1.45), (0, 1.47)], 12, scale_xy=(1, 0.62)), mat)
    for sx in (-1, 1):
        pts = [(sx * 0.21, 0, 1.36), (sx * 0.25, 0, 1.08), (sx * 0.27, -0.02, 0.8)]
        mb.add(H.sweep(pts, 0.045, 8), mat)
    mb.add(H.cyl(0.05, 0.08, 8, z0=1.44), mat)
    mb.add(H.uvsphere(0.11, 12, 8, scale=(0.85, 1.0, 1.15)), mat, H.xf((0, 0, 1.585)))
    fig = mb.to_object("PV_Figure", collection=col)
    fig.data.materials.clear()
    fig.data.materials.append(_pmat("PREVIEW_Figure", (0.35, 0.4, 0.5), 0.5))
    return fig


def all_roots(scene_roots):
    return list(scene_roots)


def _show_only(roots, keep):
    keep_set = set()
    for r in keep:
        keep_set.add(r)
        keep_set.update(H.descendants(r))
    for r in roots:
        for o in [r] + H.descendants(r):
            hidden = o not in keep_set or H.clean_name(o.name).startswith("COL_") or o.type == "EMPTY"
            o.hide_render = hidden


def frame_camera(cam, mn, mx, direction, aspect, margin=0.86):
    c = (mn + mx) / 2
    d = Vector(direction).normalized()
    up = Vector((0, 0, 1))
    f = -d
    r = f.cross(up)
    if r.length < 1e-4:
        r = Vector((1, 0, 0))
    r.normalize()
    u = r.cross(f).normalized()
    th = math.tan(math.atan(18 / cam.data.lens)) * margin
    tv = th / aspect
    corners = [Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)]

    def ok(D):
        p0 = c + d * D
        for p in corners:
            q = p - p0
            dep = q.dot(f)
            if dep <= 0.01:
                return False
            if abs(q.dot(r)) > dep * th or abs(q.dot(u)) > dep * tv:
                return False
        return True

    lo, hi = 0.01, 500.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if ok(mid):
            hi = mid
        else:
            lo = mid
    cam.location = c + d * hi
    cam.rotation_euler = f.to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_start = max(0.001, hi * 0.01)
    cam.data.clip_end = hi * 50 + 50


def render_tile(roots, keep, path, view="iso", res=(320, 240), samples=16, cell=0.1, figure_at=None,
                floor=True, extra_bounds=None, focus=None, wall=False):
    col = setup_scene(res, samples)
    _show_only(roots, keep)
    meshes = []
    for r in keep:
        meshes += [o for o in [r] + H.descendants(r) if o.type == "MESH" and not H.clean_name(o.name).startswith("COL_")]
    mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
    for o in meshes:
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            for i in range(3):
                mn[i] = min(mn[i], p[i]); mx[i] = max(mx[i], p[i])
    fig = make_figure(col)
    if figure_at is not None:
        fig.hide_render = False
        fig.location = figure_at
        fmn = Vector(figure_at) + Vector((-0.3, -0.15, 0)); fmx = Vector(figure_at) + Vector((0.3, 0.15, 1.7))
        for i in range(3):
            mn[i] = min(mn[i], fmn[i]); mx[i] = max(mx[i], fmx[i])
    else:
        fig.hide_render = True
    if extra_bounds:
        for i in range(3):
            mn[i] = min(mn[i], extra_bounds[0][i]); mx[i] = max(mx[i], extra_bounds[1][i])
    floor_z = mn.z - 0.0005
    if focus is not None:
        mn, mx = Vector(focus[0]), Vector(focus[1])
    fl = make_floor(floor_z if floor else -1000, cell, col)
    fl.hide_render = not floor
    wl = bpy.data.objects.get("PV_Wall")
    if wl is None:
        me = bpy.data.meshes.new("PV_Wall")
        s_ = 100
        me.from_pydata([(-s_, 0, -s_), (s_, 0, -s_), (s_, 0, s_), (-s_, 0, s_)], [], [(0, 1, 2, 3)])
        wl = bpy.data.objects.new("PV_Wall", me)
        col.objects.link(wl)
        wl.data.materials.append(_pmat("PREVIEW_Wall", (0.2, 0.2, 0.21), 0.9))
    wl.location = (0, 0.002, 0)
    wl.hide_render = not wall
    cam = bpy.context.scene.camera
    frame_camera(cam, mn, mx, VIEWS.get(view, view), res[0] / res[1])
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path, (mx - mn)


def compose(tiles, out_path, cols=2, tile_res=(320, 240), title=None):
    """tiles: list of (png, label_lines)."""
    from PIL import Image, ImageDraw, ImageFont
    rows = max(1, math.ceil(len(tiles) / cols))
    W, Hh = cols * tile_res[0], rows * tile_res[1]
    sheet = Image.new("RGB", (W, Hh), (20, 20, 22))
    try:
        font = ImageFont.truetype(FONT, 11)
        fontb = ImageFont.truetype(FONT.replace("DejaVuSans", "DejaVuSans-Bold"), 12)
    except Exception:
        font = fontb = ImageFont.load_default()
    for i, (png, lines) in enumerate(tiles):
        im = Image.open(png).convert("RGB").resize(tile_res)
        x, y = (i % cols) * tile_res[0], (i // cols) * tile_res[1]
        sheet.paste(im, (x, y))
        d = ImageDraw.Draw(sheet)
        d.rectangle([x, y, x + tile_res[0] - 1, y + tile_res[1] - 1], outline=(60, 60, 64))
        ty = y + 3
        for j, ln in enumerate(lines):
            f = fontb if j == 0 else font
            d.text((x + 5, ty + 1), ln, fill=(0, 0, 0), font=f)
            d.text((x + 4, ty), ln, fill=(235, 235, 220) if j == 0 else (200, 200, 190), font=f)
            ty += 14
    if title:
        d = ImageDraw.Draw(sheet)
        d.text((W - 8 - d.textlength(title, font=font), Hh - 16), title, fill=(160, 160, 150), font=font)
    sheet.save(out_path)
    return out_path


def overview(roots, path, res=(640, 480), samples=20, spacing=0.15, cell=0.5, view="iso", figure=True, rows=1):
    """All roots side by side along X (temporarily moved), mannequin at the left."""
    col = setup_scene(res, samples)
    sizes = []
    for r in roots:
        mn, mx = H.bounds_of([o for o in [r] + H.descendants(r) if o.type == "MESH" and not H.clean_name(o.name).startswith("COL_")], r)
        sizes.append((mn, mx))
    per_row = math.ceil(len(roots) / rows)
    x = 0.6 if figure else 0.0
    y = 0.0
    orig = [r.location.copy() for r in roots]
    row_depth = 0
    for i, r in enumerate(roots):
        if i and i % per_row == 0:
            x = 0.6 if figure else 0.0
            y += row_depth + spacing * 3
            row_depth = 0
        mn, mx = sizes[i]
        r.location = (x - mn.x, y - mn.y, -mn.z)
        x += (mx.x - mn.x) + spacing
        row_depth = max(row_depth, mx.y - mn.y)
    bpy.context.view_layer.update()
    try:
        path, _ = render_tile(roots, roots, path, view=view, res=res, samples=samples, cell=cell,
                              figure_at=(0.2, 0, 0) if figure else None)
    finally:
        for r, l in zip(roots, orig):
            r.location = l
        bpy.context.view_layer.update()
    return path
