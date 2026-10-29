# MONKEY NO FEAR — Asset Production Specification

This document is the contract between the asset pipelines (Python/Blender generators in `Tools/`)
and the Unity runtime/editor code in `Assets/MonkeyNoFear/Scripts`. The Unity editor builder
(`Monkey No Fear > Build Game`) wires assets up **by name**, so names below are mandatory.

Project root: `/home/user/MonkeyNoFear` (Unity 2022.3 LTS, Built-in Render Pipeline, Linear color space).

## 0. Tooling available in this environment

* Blender 5.0 as a Python module: `/tmp/claude-0/-home-user/3d1e9a1c-872f-5743-82f9-43aeb22fc14e/scratchpad/venv/bin/python script.py -- args`
  (`import bpy`). **Never name a script after a stdlib module** (e.g. `inspect.py`, `random.py`) — bpy crashes.
  Scripts must also run in a normal Blender install: `blender -b -P script.py -- args`.
* The same venv has numpy, scipy, scikit-image, Pillow, soundfile (OGG/Vorbis write support). ffmpeg is installed.
* Rendering previews: Cycles on CPU (4 cores). Keep previews small (≤ 640×480, ≤ 32 samples, denoise on if available).
* All generator scripts go in `Tools/…` and must be deterministic (fixed random seeds) and re-runnable.

## 1. Global conventions

* Units: meters. Blender is Z-up. **Characters, props and tools face Blender −Y** (Blender "Front" view).
  In Unity this becomes +Z forward, +Y up.
* FBX export (all models): 
  ```python
  bpy.ops.export_scene.fbx(filepath=..., use_selection=True, object_types={'ARMATURE','MESH','EMPTY'},
      apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', bake_space_transform=False,
      use_mesh_modifiers=True, mesh_smooth_type='FACE', use_tspace=True, add_leaf_bones=False,
      primary_bone_axis='Y', secondary_bone_axis='X', armature_nodetype='NULL',
      bake_anim=<True for animated>, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
      bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, path_mode='STRIP')
  ```
  **Static models (levels, prop kits) use `bake_space_transform=True`** ("Apply Transform"): the axis
  conversion is baked into the mesh data, so every root node imports with identity rotation and empties carry
  only their real rotation (Blender −Y -> Unity `transform.forward`). With `False`, Blender writes a −90° X
  rotation into every root node; Unity keeps it (Bake Axis Conversion does not remove it for a Y-up file), so
  marker `transform.forward` would point up and `KitLibrary.Copy` (which zeroes the root rotation) would lay
  every prop on its back. **Rigged models (creatures, player) keep `False`** (the option is unreliable with
  armatures); they are only ever instantiated whole and parented with their imported child rotations intact.
  Check with `Tools/common/fbx_audit.py`.
* Apply all object transforms (rotation & scale) on meshes before export (armature objects too, except
  where noted). No negative scales anywhere.
* Every mesh must have a UV map named `UVMap` and sensible normals (auto smooth / weighted normals OK).
  Triangle budgets (Quest-class VR): creature 3k–9k tris, tool 150–1.5k, small prop 50–1.5k, large
  prop/structure ≤ 5k, tree ≤ 4k (incl. foliage cards).
* Texel density for tiling materials: about 1 texture repeat per 1.5–2.5 m on environment props, about 1 repeat per
  0.3–0.6 m on tools and small items. Use Smart UV Project / cube projection scaled accordingly.
* **Material names are mandatory** and must come from the catalog in §2. The Unity builder creates a Unity
  material per catalog name and remaps FBX materials by name. Unknown names fall back to grey and are
  reported as errors. Blender materials may use any node setup for previews; only the *name* matters.
* Helper objects (exported as FBX nulls / meshes, consumed by the Unity builder):
  * `COL_<anything>`: a collision helper **mesh** (box-like). Builder makes a BoxCollider from its
    bounds (or a convex MeshCollider if the name contains `_CONVEX`). Not rendered. If a model has no `COL_`
    children, the builder generates a collider automatically.
  * `TIP`, `GRIP`, `GRIP2`, `LIGHT`, `SOCKET_<name>`: empties marking special points (see per-asset notes).
    Empty orientation: the empty's local **−Y** axis is its "forward" (Unity +Z).
* Every pipeline writes a JSON manifest next to its outputs describing what was produced (see each section).
* Every pipeline writes preview renders to `Docs/previews/<pipeline>/` and visually checks them.

## 2. Material catalog (names used in Blender = Unity material names)

Texture sets live in `Assets/MonkeyNoFear/Art/Textures/` as `<set>_A.png` (albedo sRGB; alpha = opacity for
cutout sets), `<set>_N.png` (tangent-space normal map, **OpenGL convention / +Y up**), `<set>_M.png` (linear mask:
R = metallic, G = ambient occlusion, B = height/cavity, A = smoothness), optional `<set>_E.png` (emission, sRGB).

| Material name | Texture set | Notes |
|---|---|---|
| MNF_ConcreteWall | concrete_wall | damp dark concrete, cracks, water streaks, formwork seams |
| MNF_ConcreteFloor | concrete_floor | darker, scuffed, oil stains |
| MNF_MetalGrate | metal_grate | floor grating, alpha cutout holes |
| MNF_MetalDiamond | metal_diamond | worn diamond tread plate |
| MNF_MetalRusted | metal_rusted | heavy rust, pitting |
| MNF_MetalPainted_Green / _Gray / _Yellow / _Red / _Blue | metal_painted | worn industrial paint; Unity tints the (neutral-light) albedo |
| MNF_MetalBare | metal_bare | brushed/scratched steel (tool heads, rails) |
| MNF_Hazard | hazard_stripes | worn black/yellow 45° caution stripes, tile along U |
| MNF_Rubber | rubber | cables, grips, hoses |
| MNF_Plastic_Yellow / _Orange / _Black / _Gray | plastic | device casings; tinted in Unity |
| MNF_WoodCrate, MNF_WoodPlanks, MNF_WoodRotten, MNF_WoodBeam, MNF_WoodHandle | wood_crate, wood_planks, wood_rotten, wood_beam, wood_handle | |
| MNF_BarkPine, MNF_BarkDead | bark_pine, bark_dead | tile vertically along V |
| MNF_FoliagePine, MNF_FoliageLeaf, MNF_Fern, MNF_Grass | foliage_pine, foliage_leaf, fern, grass | alpha-cutout cards, two-sided, wind sway |
| MNF_ForestFloor, MNF_Mud, MNF_Moss | forest_floor, mud, moss | |
| MNF_Terrain | (forest_floor + mud + moss + rock_dry) | vertex-colour blend: R = mud, G = moss, B = rock |
| MNF_RockDry, MNF_RockWet, MNF_RockMine | rock_dry, rock_wet, rock_mine | UV'd props |
| MNF_RockDry_Tri, MNF_RockWet_Tri, MNF_RockMine_Tri | same sets | **triplanar** (no UVs needed): cliffs, caves, mine shell |
| MNF_OreIron, MNF_OreCopper, MNF_Crystal, MNF_Blackstone, MNF_Anomalous | ore_iron, ore_copper, crystal, blackstone, anomalous | crystal/anomalous have emission |
| MNF_FurRotten, MNF_SkinDecayed, MNF_FurRabbit, MNF_FurRabbitMangy, MNF_FurBoar, MNF_FurDark, MNF_MineralCrust, MNF_MournerSkin | fur_rotten, skin_decayed, fur_rabbit, fur_rabbit_mangy, fur_boar, fur_dark, mineral_crust, mourner_skin | creatures |
| MNF_Teeth, MNF_Gums, MNF_Nails, MNF_Flesh | (flat colour + noise) | yellowed teeth, dark gums, cracked nails, wet torn flesh |
| MNF_EyeWet | — | black, very glossy, catches light |
| MNF_EyeClouded | — | milky blue-grey, slightly translucent look |
| MNF_EyeGlint | — | tiny eye-shine points (Ceiling Clerk / animals): emissive faint |
| MNF_MournerGlow | — | sickly yellow-green emission inside the Mourner's chest cavity |
| MNF_FabricCanvas, MNF_FabricBlanket | fabric_canvas, fabric_blanket | |
| MNF_Glass | — | dirty glass, transparent |
| MNF_BulbWarm, MNF_BulbCold, MNF_BulbRed, MNF_BulbGreen | — | emissive light bulbs / tubes / indicators |
| MNF_Screen | — | CRT screen surface (Unity draws text on top) |
| MNF_Rope | rope | |
| MNF_Paper | paper | notes, posters, labels |
| MNF_Meat | meat | food items |
| MNF_Signs | signs_atlas (1024²) | see §2.1 |
| MNF_Decals | decals_atlas (1024²) | see §2.2 |
| MNF_Player_Fur, MNF_Player_Face, MNF_Player_Dark | supplied player textures | player only |

### 2.1 `signs_atlas` — 4×4 grid of 256×256 cells (cell index = row*4+col, row 0 = top)
0 "DANGER / AUTHORIZED PERSONNEL ONLY" · 1 "KEEP GATE CLOSED" · 2 "SURVIVOR BUNKER 7" · 3 "MINE ACCESS →" ·
4 "HIGH VOLTAGE" · 5 "LEVEL 1" · 6 "LEVEL 2" · 7 "LEVEL 3 — NO ENTRY" · 8 "EVACUATION ROUTE ←" ·
9 "ASSAY / TRADE" · 10 "EQUIPMENT" · 11 "STORAGE" · 12 "MISSING — HAVE YOU SEEN THIS MONKEY?" poster ·
13 "DO NOT FOLLOW THE LIGHT" (scrawled) · 14 numbered marker "03" · 15 trail sign "MINE 400m ↑".
Worn, faded, scratched industrial signage. Signs are applied in Unity as quads with atlas UVs.

### 2.2 `decals_atlas` — 4×4 grid, RGBA (alpha-blended)
0 crack · 1 water stain streaks · 2 grime patch · 3 oil stain · 4 claw scratches (3 parallel) ·
5 claw scratches (deep, 4) · 6 monkey hand print (dirty) · 7 creature footprint (long-fingered) ·
8 dark dried stain splatter · 9 scrawled tally marks · 10 scorch mark · 11 moss patch ·
12 rust drip streaks · 13 arrow (painted, orange) · 14 "X" (painted) · 15 drag marks.

## 3. Textures pipeline → `Tools/textures/`
Output: `Assets/MonkeyNoFear/Art/Textures/`, 512×512 (tiling, seamless) unless noted; atlases 1024×1024;
particle sprites 128×128 (`fx_dust`, `fx_spark`, `fx_smoke`, `fx_fog` (256, very soft cloud), `fx_glow` (radial),
`fx_leaf`, `fx_drip`, `fx_debris`). Manifest: `Assets/MonkeyNoFear/Art/Textures/textures_manifest.json`
(`{set: {albedo, normal, mask, emission, tiling_m, cutout:bool, notes}}`). Preview contact sheet in
`Docs/previews/textures/`.

## 4. Audio pipeline → `Tools/audio/`
Output: `Assets/MonkeyNoFear/Audio/<Category>/<name>[_NN].ogg`, 44.1 kHz. Mono for anything positional, stereo only
for `amb_*_bed` ambience beds and `sting_*`. Variants are numbered `_01.._NN`; Unity groups them by base name.
Loops (`*_loop`) must loop seamlessly. Manifest `Assets/MonkeyNoFear/Audio/audio_manifest.json`
(`{name: {category, files:[...], loop, spatial, duration, description}}`). (Full list in the audio brief.)

## 5. Creature models → `Tools/blender/creatures/`
Output `Assets/MonkeyNoFear/Art/Models/Creatures/<Name>.fbx` + manifest `creatures_manifest.json` + previews.

Rig conventions (bone names, exact):
`root` (at ground, no deform) → `hips` → `spine` → `chest` → `neck` → `head` → `jaw`;
arms `upperarm.L/R` → `forearm.L/R` → `hand.L/R` → `fingers.L/R`; legs `thigh.L/R` → `shin.L/R` → `foot.L/R`.
Creature-specific extras are listed in the creature brief (e.g. `hump`, `ear.L/R`, `jaw.L/R`, `socket_chestlight`).
Animations are **in place** (no root motion), named in lowercase (`idle`, `walk`, `run` …). Loop clips start and end
on the same pose. The manifest records each clip's length (s), whether it loops, and the ground speed
(m/s) the cycle was authored for, so Unity can sync playback speed to movement.

## 6. Props, tools, items → `Tools/blender/props/`
Kits are FBX files that contain many independent top-level objects, each at the world origin with its own
pivot convention. The Unity builder makes one prefab per top-level object (children such as `COL_*`, `TIP`, `Chunk_00`
are kept inside that prefab). Manifest `props_manifest.json`: `{object_name: {kit, bounds_size:[x,y,z] (Blender axes),
tris, materials:[...], helpers:[...], notes}}`.

Pivots: tools/items at the main grip point (handle centred on the origin, tool forward/tip along −Y, "up" +Z);
floor props at the bottom centre; wall-mounted props at the wall-contact centre with −Y pointing out of the wall;
ceiling props at the top contact point.

## 7. Levels → `Tools/blender/levels/` (built by the lead developer)
Level FBX files contain geometry plus empties named `MK_<Type>_<args…>` that the Unity builder turns into gameplay
objects (spawn points, ore spawns, AI anchors, lights, sound emitters, zones, prop instances `MK_PROP_<PrefabName>`).
