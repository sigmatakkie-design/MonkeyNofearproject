"""kitB_validate - re-import Kit_Forest.fbx / Kit_Mine.fbx and validate them against the manifests and the spec.

usage: python kitB_validate.py -- [Kit_Forest Kit_Mine]
Checks per top-level object: present in manifest and vice versa, raw FBX node names exact (no '~' / '.001'
suffixes, required children/helpers present by exact name), root at the origin, no negative scales anywhere,
every mesh has a 'UVMap', all materials in the catalog, triangle count == manifest and within budget,
COL_* helpers are meshes, SOCKET_* are empties.  Prints a report (also saved to
Docs/previews/props/kitB_validation_report.txt) and exits non-zero on errors.
"""
import bpy, sys, os, json, re
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import propkit_b_helpers as H

REQUIRED = {   # exact child / helper names the game code & level builder look up
    'Tree_Pine_A': ['COL_Trunk'], 'Tree_Pine_B': ['COL_Trunk'], 'Tree_Pine_C': ['COL_Trunk'],
    'Tree_Dead_A': ['COL_Trunk'], 'Tree_Dead_B': ['COL_Trunk'], 'Tree_Dead_C': ['COL_Trunk'],
    'Tree_Gnarled': ['COL_Trunk'], 'FallenTree': ['COL_Log'], 'SignPost': ['Board'], 'WarningBoard': ['Board'],
    'Campfire': ['SOCKET_Fire'], 'CampLantern': ['Bulb'], 'MineEntrance': ['Board'],
    'MineLamp': ['Bulb'], 'LampString': ['Bulb_0', 'Bulb_1', 'Bulb_2', 'Bulb_3'], 'Walkway': ['COL_Floor'],
    'Elevator_Platform': ['COL_Floor'], 'Sign_Level': ['Board'], 'TunnelMarker_Red': ['Plate'],
    'TunnelMarker_Yellow': ['Plate'], 'TunnelMarker_Green': ['Plate'],
}
REQUIRED_PREFIX = {'Elevator_Platform': ['COL_Rail_'], 'Cabin_Ruin': ['COL_'], 'Watchtower': ['COL_'],
                   'Bridge_Broken': ['COL_'], 'MineEntrance': ['COL_']}
TREES = {'Tree_Pine_A', 'Tree_Pine_B', 'Tree_Pine_C', 'Tree_Dead_A', 'Tree_Dead_B', 'Tree_Dead_C', 'Tree_Gnarled'}
LARGE = {'Cabin_Ruin', 'Watchtower', 'Bridge_Broken', 'MineEntrance', 'CliffChunk_A', 'CliffChunk_B', 'Boulder_Large',
         'FallenTree', 'SupportFrame', 'SupportFrame_Broken', 'Elevator_Platform', 'Elevator_Frame', 'LooseRockWall',
         'BorerHole', 'RubblePile_A', 'RubblePile_B', 'ScratchedPlate', 'PipeRun', 'Workstation', 'Generator_Small',
         'Minecart', 'Minecart_Abandoned', 'Rail_Curve', 'Rail_End', 'Rail_Straight', 'LampString'}


def budget(name):
    if name in TREES:
        return 4000
    if name in LARGE:
        return 5000
    return 1500


def raw_fbx_models(path):
    """Model node names + parent links straight from the binary FBX (no importer renaming)."""
    from io_scene_fbx import parse_fbx
    root, ver = parse_fbx.parse(path)
    objects = next(e for e in root.elems if e.id == b'Objects')
    conns = next(e for e in root.elems if e.id == b'Connections')
    models = {}
    for e in objects.elems:
        if e.id == b'Model':
            uid = e.props[0]
            name = e.props[1].split(b'\x00\x01')[0].decode()
            models[uid] = (name, e.props[2].decode())
    parent = {}
    for c in conns.elems:
        if c.props[0] == b'OO' and c.props[1] in models:
            parent[c.props[1]] = c.props[2]
    tree = defaultdict(list)
    tops = []
    for uid, (name, kind) in models.items():
        p = parent.get(uid, 0)
        if p in models:
            tree[models[p][0]].append((name, kind))
        else:
            tops.append(name)
    return tops, tree


def descendants(o):
    out = []
    for c in o.children:
        out.append(c)
        out.extend(descendants(c))
    return out


def validate(kit, lines):
    errors = 0
    fbx = os.path.join(H.PROPS_OUT, kit + '.fbx')
    man = json.load(open(os.path.join(H.PROPS_OUT, 'props_manifest_%s.json' % kit)))
    lines.append('=' * 100)
    lines.append('%s  (%s, %.1f MB)' % (kit, fbx, os.path.getsize(fbx) / 1e6))
    lines.append('=' * 100)
    # --- raw names ---
    tops_raw, tree = raw_fbx_models(fbx)
    bad = [n for n in tops_raw + [c for v in tree.values() for c, _ in v] if '~' in n or re.search(r'\.\d{3}$', n)]
    if bad:
        errors += 1
        lines.append('ERROR raw FBX node names with suffixes: %s' % bad[:10])
    missing = sorted(set(man) - set(tops_raw))
    extra = sorted(set(tops_raw) - set(man))
    if missing or extra:
        errors += 1
        lines.append('ERROR manifest/FBX mismatch: missing=%s extra=%s' % (missing, extra))
    # --- reimport ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    objs = {o.name: o for o in bpy.data.objects}
    tops = [o for o in bpy.data.objects if o.parent is None]
    neg = [o.name for o in bpy.data.objects if min(o.matrix_world.to_scale()) <= 0 or o.matrix_world.determinant() <= 0]
    if neg:
        errors += 1
        lines.append('ERROR negative/zero scale: %s' % neg)
    lines.append('%-22s %6s %6s %-28s %-22s %s' % ('object', 'tris', 'budget', 'size xyz (m)', 'materials', 'children / helpers'))
    total = 0
    for name in sorted(man, key=lambda n: list(man).index(n)):
        o = objs.get(name)
        e = []
        if o is None:
            lines.append('%-22s MISSING after import' % name)
            errors += 1
            continue
        if o.location.length > 1e-4:
            e.append('not at origin %s' % tuple(round(v, 3) for v in o.location))
        tris = 0
        mats = set()
        for d in [o] + descendants(o):
            if d.type == 'MESH':
                if 'UVMap' not in d.data.uv_layers:
                    e.append('%s has no UVMap' % d.name)
                en = re.sub(r'\.\d{3}$', '', d.name)
                if en.startswith('COL_'):
                    continue
                tris += sum(len(p.vertices) - 2 for p in d.data.polygons)
                for m in d.data.materials:
                    if m is not None:
                        mats.add(re.sub(r'\.\d{3}$', '', m.name))
        bad_m = [m for m in mats if m not in H.CATALOG]
        if bad_m:
            e.append('non-catalog materials %s' % bad_m)
        if tris != man[name]['tris']:
            e.append('tris %d != manifest %d' % (tris, man[name]['tris']))
        if tris > budget(name):
            e.append('over budget')
        raw_children = tree.get(name, [])
        for c, kind in raw_children:
            if c.startswith('COL_') and kind != 'Mesh':
                e.append('%s is not a mesh' % c)
            if c.startswith('SOCKET_') and kind != 'Null':
                e.append('%s is not an empty' % c)
        names = [c for c, _ in raw_children]
        for req in REQUIRED.get(name, []):
            if req not in names:
                e.append('missing required child %s' % req)
        for pre in REQUIRED_PREFIX.get(name, []):
            if not any(n.startswith(pre) for n in names):
                e.append('missing %s* helper' % pre)
        sz = man[name]['bounds_size']
        total += tris
        lines.append('%-22s %6d %6d %-28s %-22s %s' % (name, tris, budget(name), '%.2f x %.2f x %.2f' % tuple(sz),
                                                       ','.join(m.replace('MNF_', '') for m in sorted(mats))[:22],
                                                       ' '.join(names)))
        for x in e:
            lines.append('    ERROR ' + x)
        errors += len(e)
    lines.append('-> %d objects, %d tris total, %d error(s)' % (len(man), total, errors))
    return errors


def main():
    kits = H.args_after_dashdash() or ['Kit_Forest', 'Kit_Mine']
    lines = []
    errs = 0
    for k in kits:
        errs += validate(k, lines)
    lines.append('VALIDATION %s' % ('PASSED' if errs == 0 else 'FAILED (%d errors)' % errs))
    txt = '\n'.join(lines)
    print(txt)
    os.makedirs(H.PREV_OUT, exist_ok=True)
    with open(os.path.join(H.PREV_OUT, 'kitB_validation_report.txt'), 'w') as fh:
        fh.write(txt + '\n')
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
