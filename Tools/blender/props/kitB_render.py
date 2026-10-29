"""kitB_render - Cycles CPU contact sheets for Kit_Forest / Kit_Mine (artist B).

usage: python kitB_render.py -- <kit .blend> <out.png> [--only A,B,C] [--cols 5] [--size 320x240]
                               [--samples 20] [--showcol] [--view front|three]
Every top-level object of the kit collection is rendered alone at the origin next to a 1.7 m scale figure,
then the tiles are composed (PIL) into one labelled sheet.
"""
import bpy, sys, os, math
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import propkit_b_helpers as H


def preview_mat(name, col, alpha=1.0, emit=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Roughness'].default_value = 0.8
    b.inputs['Alpha'].default_value = alpha
    if emit:
        b.inputs['Emission Color'].default_value = (*col, 1)
        b.inputs['Emission Strength'].default_value = emit
    return m


def make_figure(coll):
    """1.7 m stylised human scale reference (preview only, never exported)."""
    mb = H.MB()
    H.get_mat('MNF_Plastic_Gray')
    fm = 'MNF_Plastic_Gray'
    for sx in (-0.1, 0.1):
        H.add_cyl(mb, (sx, 0, 0), (sx, 0, 0.82), 0.07, 0.085, 8, fm)
        H.add_cyl(mb, (sx * 2.2, 0, 1.42), (sx * 2.6, 0, 0.78), 0.05, 0.04, 8, fm)
    H.add_cyl(mb, (0, 0, 0.8), (0, 0, 1.45), 0.17, 0.2, 10, fm)
    H.add_cyl(mb, (0, 0, 1.45), (0, 0, 1.5), 0.08, 0.06, 8, fm)
    H.add_cyl(mb, (0, 0, 1.5), (0, 0, 1.7), 0.1, 0.085, 10, fm, rings=2)
    ob = mb.to_object('_scale_figure', coll)
    ob.data.materials.clear()
    ob.data.materials.append(preview_mat('_preview_figure', (0.55, 0.42, 0.3)))
    return ob


def setup_scene(samples, size):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    try:
        sc.cycles.use_denoising = True
    except Exception:
        pass
    sc.cycles.max_bounces = 4
    sc.cycles.transparent_max_bounces = 24
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    w = bpy.data.worlds.new('prev_world')
    sc.world = w
    bg = w.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.16, 0.18, 0.21, 1)
    bg.inputs['Strength'].default_value = 0.9
    coll = bpy.data.collections.new('_preview')
    sc.collection.children.link(coll)
    sun = bpy.data.lights.new('prev_sun', 'SUN')
    sun.energy = 3.2
    sun.angle = math.radians(4)
    sun.color = (1.0, 0.95, 0.88)
    so = bpy.data.objects.new('prev_sun', sun)
    so.rotation_euler = (math.radians(50), 0, math.radians(-35))
    coll.objects.link(so)
    # ground
    import bmesh
    me = bpy.data.meshes.new('prev_ground')
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=200)
    bm.to_mesh(me)
    g = bpy.data.objects.new('prev_ground', me)
    me.materials.append(preview_mat('_preview_ground', (0.11, 0.105, 0.1)))
    coll.objects.link(g)
    cam = bpy.data.cameras.new('prev_cam')
    cam.lens = 45
    cam.clip_end = 500
    co = bpy.data.objects.new('prev_cam', cam)
    coll.objects.link(co)
    sc.camera = co
    fig = make_figure(coll)
    me2 = bpy.data.meshes.new('prev_wall')
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=6)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=__import__('mathutils').Matrix.Rotation(math.radians(90), 3, 'X'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0.002, 0))
    bm.to_mesh(me2)
    wall = bpy.data.objects.new('prev_wall', me2)
    me2.materials.append(preview_mat('_preview_wall', (0.16, 0.15, 0.14)))
    coll.objects.link(wall)
    sc['_wall'] = wall.name
    return sc, co, fig


def fit_camera(sc, cam, pts, view):
    c = Vector((0, 0, 0))
    for p in pts:
        c += p
    c /= len(pts)
    mn = Vector([min(p[k] for p in pts) for k in range(3)])
    mx = Vector([max(p[k] for p in pts) for k in range(3)])
    c = (mn + mx) / 2
    if view == 'front':
        d = Vector((0.12, -1.0, 0.18)).normalized()
    elif view == 'top':
        d = Vector((0.2, -0.6, 1.0)).normalized()
    else:
        d = Vector((0.62, -1.0, 0.42)).normalized()
    R = max((mx - mn).length / 2, 0.2)
    lo, hi = R * 0.3, R * 12
    for _ in range(22):
        dist = (lo + hi) / 2
        cam.location = c + d * dist
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.view_layer.update()
        ok = True
        for p in pts:
            v = world_to_camera_view(sc, cam, p)
            if v.z <= 0 or v.x < 0.04 or v.x > 0.96 or v.y < 0.05 or v.y > 0.92:
                ok = False
                break
        if ok:
            hi = dist
        else:
            lo = dist
    dist = hi
    cam.location = c + d * dist
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()


def main():
    args = H.args_after_dashdash()
    blend, out = args[0], args[1]
    only = None
    cols, size, samples, showcol, view = 5, (320, 240), 20, False, 'three'
    i = 2
    while i < len(args):
        a = args[i]
        if a == '--only':
            only = args[i + 1].split(','); i += 1
        elif a == '--cols':
            cols = int(args[i + 1]); i += 1
        elif a == '--size':
            size = tuple(int(x) for x in args[i + 1].split('x')); i += 1
        elif a == '--samples':
            samples = int(args[i + 1]); i += 1
        elif a == '--showcol':
            showcol = True
        elif a == '--view':
            view = args[i + 1]; i += 1
        i += 1
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc, cam, fig = setup_scene(samples, size)
    tops = [o for o in bpy.data.objects if o.parent is None and o.get('mnf_top')]
    tops.sort(key=lambda o: o.get('mnf_order', 0))
    all_tops = list(tops)
    if only:
        tops = [o for o in tops if o.name in only]
    colmat = preview_mat('_preview_col', (1.0, 0.1, 0.05), alpha=0.35, emit=0.3)
    import tempfile
    tmpdir = os.path.join(tempfile.gettempdir(), 'kitB_tiles')
    os.makedirs(tmpdir, exist_ok=True)
    tiles = []
    for t in tops:
        for o in all_tops:
            vis = (o == t)
            for d in [o] + H.descendants(o):
                isc = H.export_name(d.name).startswith('COL_')
                d.hide_render = (not vis) or (isc and not showcol)
                if isc and showcol and d.type == 'MESH':
                    d.data.materials.clear()
                    d.data.materials.append(colmat)
                    d.visible_shadow = False
        mn, mx = H.obj_bounds(t)
        wall = bpy.data.objects[sc['_wall']]
        wall.hide_render = t.get('mnf_mount') != 'wall'
        gz = 0.0 if t.get('mnf_mount') is None else mn.z - (0.9 if t.get('mnf_mount') == 'wall' else 1.6)
        bpy.data.objects['prev_ground'].location.z = gz
        fig.location = (mx.x + 0.45, max(mn.y, min(mx.y, 0.0)) if mx.y - mn.y < 4 else mn.y + 0.5, gz)
        pts = []
        for x in (mn.x, mx.x):
            for y in (mn.y, mx.y):
                for z in (mn.z, mx.z):
                    pts.append(Vector((x, y, z)))
        fl = Vector(fig.location)
        small = max(mx - mn) < 0.9
        if small:   # frame the prop; the figure stands right behind it as scale reference
            fig.location = (mx.x + 0.25, mx.y + 0.35, gz)
        else:
            pts += [fl + Vector((0.3, 0.3, 1.75)), fl + Vector((-0.3, -0.3, 0))]
        fit_camera(sc, cam, pts, view)
        path = os.path.join(tmpdir, '%s.png' % t.name)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        tiles.append((t.name, H.obj_tris(t), path, mx - mn))
        print('rendered', t.name, flush=True)
    from PIL import Image, ImageDraw, ImageFont
    rows = (len(tiles) + cols - 1) // cols
    W, Hh = size
    sheet = Image.new('RGB', (cols * W, rows * Hh), (20, 20, 20))
    font = ImageFont.load_default(size=13)
    for k, (name, tris, path, dims) in enumerate(tiles):
        im = Image.open(path).convert('RGB')
        d = ImageDraw.Draw(im)
        label = '%s  %d tris  %.1fx%.1fx%.1fm' % (name, tris, dims.x, dims.y, dims.z)
        d.rectangle((0, 0, W, 17), fill=(0, 0, 0))
        d.text((4, 2), label, fill=(255, 230, 160), font=font)
        sheet.paste(im, ((k % cols) * W, (k // cols) * Hh))
    sheet.save(out)
    print('wrote', out)


if __name__ == '__main__':
    main()
