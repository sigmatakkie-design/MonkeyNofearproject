"""kitA_validate.py - re-import validation for prop artist A kits.

Usage: python kitA_validate.py -- [Kit_Tools] [Kit_Deposits] [Kit_Bunker]

Checks, per kit FBX:
 * raw FBX node names / hierarchy (parsed directly, so the exact names Unity sees are verified - Blender's
   importer would re-suffix duplicate child names like `TIP.001`);
 * every object of the brief present as a top-level node, with its required children/helpers;
 * Blender re-import into an empty scene: no negative scales, top-level objects at the origin, every mesh
   has a `UVMap`, all materials in the catalog, triangle counts vs. manifest and budget.
Writes Docs/previews/props/<Kit>_validation.txt.
"""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402
import propkit_a_helpers as H  # noqa: E402

KITS = {"Kit_Tools": "kitA_tools", "Kit_Deposits": "kitA_deposits", "Kit_Bunker": "kitA_bunker"}


def raw_fbx(path):
    from io_scene_fbx import parse_fbx
    root, version = parse_fbx.parse(path)

    def find(elem, name):
        for e in elem.elems:
            if e.id == name:
                return e
        return None

    objs = find(root, b"Objects")
    conns = find(root, b"Connections")
    models, geoms, mats = {}, {}, {}
    for e in objs.elems:
        if e.id == b"Model":
            uid = e.props[0]
            nm = e.props[1].split(b"\x00\x01")[0].decode()
            models[uid] = (nm, e.props[2].decode())
        elif e.id == b"Geometry":
            uid = e.props[0]
            pvi = None
            for sub in e.elems:
                if sub.id == b"PolygonVertexIndex":
                    pvi = sub.props[0]
            tris = 0
            n = 0
            for idx in pvi:
                n += 1
                if idx < 0:
                    tris += n - 2
                    n = 0
            geoms[uid] = tris
        elif e.id == b"Material":
            mats[e.props[0]] = e.props[1].split(b"\x00\x01")[0].decode()
    parent = {}
    model_geom = {}
    model_mats = {}
    for c in conns.elems:
        if c.props[0] != b"OO":
            continue
        ch, pa = c.props[1], c.props[2]
        if ch in models and (pa in models or pa == 0):
            parent[ch] = pa
        elif ch in geoms and pa in models:
            model_geom[pa] = ch
        elif ch in mats and pa in models:
            model_mats.setdefault(pa, []).append(mats[ch])
    return models, parent, model_geom, geoms, model_mats


def validate(kit):
    mod = importlib.import_module(KITS[kit])
    fbx = os.path.join(H.MODEL_DIR, kit + ".fbx")
    man = json.load(open(os.path.join(H.MODEL_DIR, "props_manifest_%s.json" % kit)))
    lines = []
    errors = []
    warns = []

    def out(s=""):
        print(s)
        lines.append(s)

    out("=== %s validation (%s) ===" % (kit, os.path.relpath(fbx, H.PROJECT)))
    models, parent, model_geom, geoms, model_mats = raw_fbx(fbx)
    kids = {}
    for ch, pa in parent.items():
        kids.setdefault(pa, []).append(ch)

    def subtree(uid):
        res = []
        for c in kids.get(uid, []):
            res.append(c)
            res += subtree(c)
        return res

    roots = {models[u][0]: u for u in kids.get(0, [])}
    for nm, (n, t) in models.items():
        if "." in n and n.split(".")[-1].isdigit():
            errors.append("FBX node name has a Blender suffix: %s" % n)
    required = getattr(mod, "REQUIRED", {})
    expected = list(required) if required else list(man)
    for name in expected:
        if name not in roots:
            errors.append("missing top-level object %s" % name)
    for name in roots:
        if name not in man:
            warns.append("top-level %s not in manifest" % name)
    # --- Blender re-import ---
    H.reset_scene()
    bpy.ops.import_scene.fbx(filepath=fbx)
    bl_roots = [o for o in bpy.context.scene.objects if o.parent is None]
    budget = getattr(mod, "BUDGET", (0, 5000))
    budget_fn = getattr(mod, "budget_for", None)
    out("%-26s %6s %6s  %-10s %s" % ("object", "tris", "budget", "status", "children / helpers"))
    for name in sorted(roots, key=lambda n: expected.index(n) if n in expected else 999):
        uid = roots[name]
        st = subtree(uid)
        names = [models[u][0] for u in st]
        tri = 0
        mats = set()
        for u in [uid] + st:
            nm = models[u][0]
            if nm.startswith("COL_"):
                if models[u][1] != "Mesh":
                    errors.append("%s/%s is not a mesh" % (name, nm))
                continue
            if u in model_geom:
                tri += geoms[model_geom[u]]
            mats.update(model_mats.get(u, []))
        bad = [m for m in mats if m not in H.CATALOG]
        if bad:
            errors.append("%s: non-catalog materials %s" % (name, bad))
        for need in required.get(name, []):
            if need not in names:
                errors.append("%s: missing child/helper %s" % (name, need))
        for u in st:
            if models[u][0] in ("TIP", "GRIP", "GRIP2", "LIGHT") or models[u][0].startswith("SOCKET_"):
                if models[u][1] != "Null":
                    errors.append("%s/%s should be an empty" % (name, models[u][0]))
        lo, hi = budget_fn(name) if budget_fn else budget
        status = "ok"
        if tri > hi:
            status = "OVER"
            errors.append("%s: %d tris over budget %d" % (name, tri, hi))
        elif tri < lo:
            status = "low"
            warns.append("%s: %d tris below the %d guideline" % (name, tri, lo))
        if name in man and man[name]["tris"] != tri:
            warns.append("%s: manifest tris %d != fbx %d" % (name, man[name]["tris"], tri))
        if mats - set(man.get(name, {}).get("materials", [])):
            warns.append("%s: materials differ from manifest" % name)
        out("%-26s %6d %6d  %-10s %s" % (name, tri, hi, status, ", ".join(names)))
    # Blender-side checks
    for o in bpy.context.scene.objects:
        mw = o.matrix_world
        sc = mw.to_scale()
        if mw.determinant() < 0 or min(sc) <= 0:
            errors.append("negative/zero scale on %s %s" % (o.name, tuple(round(v, 3) for v in sc)))
        if o.type == "MESH":
            if not o.data.uv_layers or o.data.uv_layers[0].name != "UVMap":
                errors.append("%s has no UVMap" % o.name)
            for m in o.data.materials:
                if m and H.clean_name(m.name) not in H.CATALOG:
                    errors.append("%s uses non-catalog material %s" % (o.name, m.name))
    # inside-out check: closed components with negative signed volume
    import bmesh
    from mathutils import Vector
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or H.clean_name(o.name).startswith("COL_"):
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        seen = set()
        for f0 in bm.faces:
            if f0.index in seen:
                continue
            stack, comp = [f0], []
            seen.add(f0.index)
            while stack:
                g = stack.pop()
                comp.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in seen:
                            seen.add(h.index)
                            stack.append(h)
            closed = all(len(e.link_faces) == 2 for g in comp for e in g.edges)
            if not closed:
                continue
            c = sum((g.calc_center_median() for g in comp), Vector()) / len(comp)
            vol = sum((g.calc_center_median() - c).dot(g.normal) * g.calc_area() / 3 for g in comp)
            if vol < -1e-9:
                errors.append("%s: closed shell with inverted normals near %s" % (o.name, tuple(round(x, 3) for x in c)))
        bm.free()
    for o in bl_roots:
        if o.matrix_world.translation.length > 1e-4:
            errors.append("top-level %s not at origin %s" % (o.name, tuple(o.matrix_world.translation)))
    out("")
    out("top-level objects in FBX: %d (expected %d)" % (len(roots), len(expected)))
    out("Blender re-import: %d objects, %d top-level" % (len(bpy.context.scene.objects), len(bl_roots)))
    for w in warns:
        out("WARN  " + w)
    for e in errors:
        out("ERROR " + e)
    out("RESULT: %s (%d errors, %d warnings)" % ("PASS" if not errors else "FAIL", len(errors), len(warns)))
    os.makedirs(H.PREVIEW_DIR, exist_ok=True)
    with open(os.path.join(H.PREVIEW_DIR, "%s_validation.txt" % kit), "w") as f:
        f.write("\n".join(lines) + "\n")
    return not errors


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    kits = [a for a in argv if a in KITS] or list(KITS)
    ok = True
    for k in kits:
        ok &= validate(k)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
