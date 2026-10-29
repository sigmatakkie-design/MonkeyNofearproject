"""Orientation audit of every exported FBX (run with Blender's Python or the bpy module):

    blender -b --python-exit-code 1 -P Tools/common/fbx_audit.py -- [project_root]

Checks, per node, straight from the binary FBX (no Blender import, so nothing is "fixed up" on the way):
  * no negative or zero scale anywhere (mirroring / collapsed objects)
  * static models (Levels/, Props/): root meshes have identity rotation, empties only rotate about the up axis
    (Unity +Y) except wall ore markers (*_Wall) and decals, which may lie on floors/ceilings, i.e. the
    axis conversion is baked into the data (see ASSET_SPEC.md §1)
  * rigged models (Creatures/, Player/): armature/mesh roots carry exactly the -90° X conversion and nothing else,
    so the model faces Blender -Y = Unity +Z
Exit code 1 if anything fails.
"""
import bpy  # noqa: F401  (puts the bundled io_scene_fbx add-on on sys.path)
import importlib
import math
import os
import sys

parse_fbx = importlib.import_module('io_scene_fbx.parse_fbx')


def props70(elem):
    out = {}
    for c in elem.elems:
        if c.id == b'Properties70':
            for p in c.elems:
                out[p.props[0].decode()] = list(p.props[4:])
    return out


def nodes(path):
    root, _ = parse_fbx.parse(path)
    models, parents, links = {}, {}, []
    for e in root.elems:
        if e.id == b'Objects':
            for o in e.elems:
                if o.id == b'Model':
                    models[o.props[0]] = (o.props[1].split(b'\x00')[0].decode(), o.props[2].decode(), props70(o))
        if e.id == b'Connections':
            links = [(c.props[1], c.props[2]) for c in e.elems if c.props[0] == b'OO']
    # skin clusters also link to bones: keep only Model -> Model parenting
    for child, parent in links:
        if child in models and (parent in models or child not in parents):
            parents[child] = parent
    return models, parents


def near(a, b, eps=0.05):
    return abs(a - b) < eps


def audit(path, static):
    problems = []
    models, parents = nodes(path)
    for uid, (name, kind, pr) in models.items():
        rot = pr.get('Lcl Rotation', [0.0, 0.0, 0.0])
        scl = pr.get('Lcl Scaling', [1.0, 1.0, 1.0])
        if any(s <= 1e-6 for s in scl):
            problems.append(f'{name}: non-positive scale {scl}')
        is_root = parents.get(uid, 0) not in models
        if not is_root:
            continue
        if static:
            if kind == 'Mesh' and not all(near(r, 0.0) for r in rot):
                problems.append(f'{name}: root mesh rotated {[round(r, 1) for r in rot]} (axis conversion not baked)')
            if kind == 'Null' and not (near(rot[0], 0.0) or name.endswith('_Wall') or name.startswith('MK_DECAL_')):
                if not (near(abs(rot[0]), 180.0) and near(abs(rot[2]), 180.0)):   # yaw expressed as (180, y, 180)
                    problems.append(f'{name}: marker pitched {[round(r, 1) for r in rot]}')
        else:
            if not (near(rot[0], -90.0) and near(rot[1], 0.0) and near(rot[2], 0.0)):
                problems.append(f'{name}: rig root rotation {[round(r, 1) for r in rot]} (expected the -90 X conversion only)')
    return problems, len(models)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    root = argv[0] if argv else os.path.join(os.path.dirname(__file__), '..', '..')
    models_dir = os.path.join(root, 'Assets', 'MonkeyNoFear', 'Art', 'Models')
    failed = 0
    for sub, static in (('Levels', True), ('Props', True), ('Creatures', False), ('Player', False)):
        d = os.path.join(models_dir, sub)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not f.lower().endswith('.fbx'):
                continue
            problems, n = audit(os.path.join(d, f), static)
            status = 'OK ' if not problems else 'FAIL'
            print(f'{status} {sub}/{f}: {n} nodes' + ('' if not problems else f', {len(problems)} problems'))
            for p in problems[:12]:
                print('     ', p)
            failed += bool(problems)
    print('fbx audit:', 'PASS' if not failed else f'{failed} file(s) failed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
