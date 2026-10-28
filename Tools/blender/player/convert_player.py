"""Convert the supplied player monkey (.blend) into a Unity-ready FBX.

Run:  blender -b -P Tools/blender/player/convert_player.py -- <project_root>
  or  python convert_player.py -- <project_root>   (with the `bpy` module)

What it does (non-destructive: the original files in SourceArt/Player are only read):
  * opens SourceArt/Player/monkeybigfera.blend (the source rig: 9 bones, 1 skinned mesh)
  * the mesh "right arm mesh" carries a NEGATIVE X scale (-0.166, 0.166, 0.166). Negative scales on
    skinned meshes break Unity's skinning/normal handling, so the object transform is applied and the
    face winding is verified to still point outward
  * uniformly scales the whole rig to real-world size (arm length shoulder->fingertip = ARM_LENGTH_M)
  * renames the anonymous materials to the project catalog names, drops unused materials
  * re-links the two textures that ship embedded in the supplied FBX (the .blend references missing
    external files) and saves them as PNG next to the exported model
  * exports FBX without leaf bones; prints a rig report (bone world positions) used by PlayerAvatar
"""
import bpy, bmesh, sys, os, json
from mathutils import Vector

ARM_LENGTH_M = 0.74          # shoulder -> fingertip in meters for the default avatar scale

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
root = os.path.abspath(argv[0] if argv else os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_blend = os.path.join(root, 'SourceArt', 'Player', 'monkeybigfera.blend')
src_fbx = os.path.join(root, 'SourceArt', 'Player', 'monkeysbiggestnightmarerig.fbx')
out_dir = os.path.join(root, 'Assets', 'MonkeyNoFear', 'Art', 'Models', 'Player')
os.makedirs(out_dir, exist_ok=True)

# --- 1. pull the embedded textures out of the supplied FBX ------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src_fbx)
tex_out = {}
for img in bpy.data.images:
    if img.size[0] == 0:
        continue
    key = 'player_face' if 'face' in img.name.lower() else 'player_fur'
    path = os.path.join(out_dir, key + '.png')
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    tex_out[key] = (path, tuple(img.size))
print('textures:', tex_out)

# --- 2. open the source rig ---------------------------------------------------------------------------
bpy.ops.wm.open_mainfile(filepath=src_blend)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
print('source mesh scale', tuple(mesh.scale), 'armature scale', tuple(arm.scale))


def outward_ratio(obj):
    """Fraction of faces whose world-space normal points away from the mesh centre."""
    mw = obj.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    me = obj.data
    centre = sum((mw @ v.co for v in me.vertices), Vector()) / len(me.vertices)
    good = 0
    for p in me.polygons:
        n = (nm @ p.normal).normalized()
        c = mw @ p.center
        if n.dot(c - centre) > 0:
            good += 1
    return good / len(me.polygons)


before = outward_ratio(mesh)

# --- 3. apply the mesh transform (removes the negative scale) -----------------------------------------
for o in bpy.context.selected_objects:
    o.select_set(False)
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
after = outward_ratio(mesh)
if after < 0.5 <= before or (before >= 0.5 and after < before - 0.2):
    # winding got inverted by the mirror: flip it back so normals face outward again
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(mesh.data); bm.free()
    after = outward_ratio(mesh)
print(f'outward normals: before={before:.2f} after={after:.2f}')

# --- 4. uniform rescale to real-world size ------------------------------------------------------------
bones = arm.data.bones
shoulder = bones['left backarm'].head_local
hand_tail = bones['left hand'].tail_local
mesh_extent = max(v.co.x for v in mesh.data.vertices)          # fingertip (mesh is mirrored-symmetric)
arm_len_units = max(hand_tail.x, mesh_extent) - shoulder.x
s = ARM_LENGTH_M / arm_len_units
print(f'arm length {arm_len_units:.3f} units -> scale {s:.4f}')

for o in (arm, mesh):
    o.select_set(True)
bpy.context.view_layer.objects.active = arm
arm.scale = (s, s, s)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
# mesh inherited the scale through parenting; make sure it is applied on the mesh as well
for o in bpy.context.selected_objects:
    o.select_set(False)
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# --- 5. materials ---------------------------------------------------------------------------------------
rename = {'Material.001': 'MNF_Player_Fur', 'Material.002': 'MNF_Player_Face', 'Material.003': 'MNF_Player_Dark'}
for slot in mesh.material_slots:
    if slot.material and slot.material.name in rename:
        slot.material.name = rename[slot.material.name]
for m in list(bpy.data.materials):
    if m.users == 0 or m.name in ('Dots Stroke', 'Material'):
        bpy.data.materials.remove(m)
# relink textures (for previews / for anyone opening the converted .blend)
for slot in mesh.material_slots:
    m = slot.material
    if not m or not m.use_nodes:
        continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE':
            key = 'player_face' if m.name.endswith('Face') else 'player_fur'
            if key in tex_out:
                n.image = bpy.data.images.load(tex_out[key][0], check_existing=True)
mesh.data.name = 'MonkeyPlayerMesh'
mesh.name = 'MonkeyBody'
arm.name = 'MonkeyRig'

# --- 6. validation ---------------------------------------------------------------------------------------
assert all(abs(c - 1) < 1e-5 for c in mesh.scale) and all(abs(c - 1) < 1e-5 for c in arm.scale), 'scale not applied'
unweighted = sum(1 for v in mesh.data.vertices if not v.groups)
assert unweighted == 0, f'{unweighted} unweighted vertices'
groups = {g.name for g in mesh.vertex_groups}
missing = [b.name for b in arm.data.bones if b.name not in groups]
print('bones without vertex group:', missing)

report = {'scale_applied': s, 'arm_length_m': ARM_LENGTH_M, 'bones': {}}
for b in arm.data.bones:
    report['bones'][b.name] = {
        'parent': b.parent.name if b.parent else None,
        'head': [round(c, 4) for c in b.head_local], 'tail': [round(c, 4) for c in b.tail_local],
        'length': round(b.length, 4)}
xs = [v.co for v in mesh.data.vertices]
report['mesh_bounds_min'] = [round(min(v[i] for v in xs), 4) for i in range(3)]
report['mesh_bounds_max'] = [round(max(v[i] for v in xs), 4) for i in range(3)]
report['tris'] = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
report['materials'] = [s.material.name for s in mesh.material_slots]
print(json.dumps(report, indent=1))
with open(os.path.join(out_dir, 'player_rig_report.json'), 'w') as f:
    json.dump(report, f, indent=1)

# --- 7. save + export -------------------------------------------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(root, 'SourceArt', 'Player', 'MonkeyPlayer_unity.blend'))
for o in bpy.context.selected_objects:
    o.select_set(False)
arm.select_set(True); mesh.select_set(True)
bpy.ops.export_scene.fbx(
    filepath=os.path.join(out_dir, 'MonkeyPlayer.fbx'), use_selection=True,
    object_types={'ARMATURE', 'MESH'}, apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z', axis_up='Y', bake_space_transform=False, use_mesh_modifiers=False,
    mesh_smooth_type='FACE', add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
    armature_nodetype='NULL', bake_anim=False, path_mode='STRIP')
print('exported', os.path.join(out_dir, 'MonkeyPlayer.fbx'))
