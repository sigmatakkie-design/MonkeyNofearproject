# Monkey No Fear: development report

## Starting point

There was no existing Unity project, only the two supplied model files: `monkeybigfera.blend` and `monkeysbiggestnightmarerig.fbx`.

I created a new **Unity 2022.3 LTS** project with the **Built-in Render Pipeline** in Linear color space. XR uses **OpenXR** through XR Plug-in Management, with Oculus Touch, Index and Vive profiles. This targets Quest standalone (Android) and PC VR.

The supplied rig was checked in Blender:
- One mesh skinned to an armature: torso, arms, hands and head.
- Fur and face textures.
- Usable for first-person arm IK.

I converted it to `Art/Models/Player/MonkeyPlayer.fbx`, scaled ×0.22 to a 0.74 m arm length, exported −Z-forward/Y-up. `player_rig_report.json` lists the bones, the rest frames and the head offset. In first person the head is collapsed, so only the arms and torso render for the local player.

## What was built

| Area | Implementation (`Assets/MonkeyNoFear/Scripts/Runtime/...`) |
|---|---|
| **Arm locomotion** | `Player/MonkeyLocomotion`, `PhysicsHand`, `PlayerRig`. Gorilla-Tag style: a hand touching a surface becomes an anchor and the body moves by anchor − hand. On release, hand-velocity history becomes a jump. Slipperiness comes from surface type or the NoClimb layer. Velocity is clamped. The swept capsule slides and depenetrates. Room-scale head collision fades the view when the head is in a wall. A safe-position ring buffer handles stuck/out-of-bounds recovery and the kill-Y. Moving platforms carry the player. Optional **joystick locomotion (accessibility)** and snap turn live in the terminal's SETTINGS page, off by default. |
| **Avatar** | `Player/PlayerAvatar`: two-bone arm IK onto the supplied rig, with hand rotation mapping and the torso following the head. |
| **Input** | `Player/PlayerInput` (XR InputDevices on the floor tracking origin) and `DesktopDebugInput`. Desktop input drives the *same* locomotion by synthesizing hand poses (knuckle-walk macro). |
| **Interaction** | `Interaction/*`: velocity-tracked grabbing and throwing; hip, chest and head holsters; tool-rack sockets; poke buttons; hinged levers with a physical grip; and a backpack inventory with weight and capacity. |
| **Bunker hub** | `Bunker/*`. The **security gate** has bars driven by a motor with audio, warning beacons, solid collision and a safety stop when something is under it, and power loss handling. It opens and closes from the inside button, the outside button, the terminal, or the manual override lever. The **terminal** has a physical keypad and pages for SHOP, STORAGE, EXPEDITION, ARCHIVE (lore, bestiary, discoveries), STATS and SETTINGS. Also: dispenser, sell machine (hopper, payout screen, SELL PACK), storage locker, tool rack, bunk bed (sleeping saves the game and starts a new expedition), generator and power flicker. |
| **Forest** | `Tools/blender/levels/build_forest.py` produces `Forest.fbx`: 300 × 300 m heightfield terrain with mud/moss/rock vertex blending, a river and a ford, a broken bridge, a plateau, a north cliff, a camp, a cabin ruin, a grotto, a watchtower, a rabbit clearing, and the mine entrance. About 710 trees plus scattered rocks and foliage. Fog banks, area zones and boundaries. |
| **Mine** | `build_mine.py` produces `Mine.fbx`. Its rock geometry was generated with an SDF and marching cubes (170k tris in 68 chunks). Three levels connected by ramps, a drop shaft and a **powered service elevator** with a breaker. The levels contain: a timbered entrance, the hall, the Clerk gallery loop, the Grinding Hall with Borer holes, a flooded gallery and pump room, a breaker room, the deep hub, the **chasm** (the Gaunt walks below), an unstable plank bridge over a pit, and an anomalous pocket. |
| **Creatures** | `AI/CreatureBase` provides a real state machine, hearing via `NoiseSystem` (wall transmission), and vision limited by FOV, fog and player visibility. Also last-known position, search, a NavMeshAgent, fairness rules (telegraphed attacks with cooldowns and post-hit recovery, a player invulnerability window after each hit, no omniscience because creatures only know the last-known position), and debug gizmos. Each creature: **Hollowback** (sound hunter, blind), **Falsekin** (wears a real rabbit model; tells are wrong breathing rate, staring, sliding hops and skipping closer while unwatched), **Ceiling Clerk**, **Borer**, **Lantern Mourner** (lure light), and the **Gaunt** (deep-mine escalation). |
| **Wildlife and food** | `AI/Wildlife/*`: rabbits (graze, alert, flee to burrows), boar and gloomrats. Hunting with the spear or thrown items. Meat and food restore vigor. |
| **Mining** | `Mining/*`. Strikes are physics-validated: they need impact speed, angle and pickaxe tier. Deposits crack visually and drop chunks. Minerals: iron, copper, luminous crystal, blackstone and anomalous core. Deposits are redistributed by depth each expedition. |
| **Economy** | `Core/Progression`, `Data/*`: currency, shop catalog and prices, tool tiers and upgrades. Items: pickaxe T1–T3, flashlight, headlamp, spear, scanner, glowsticks, flares, rope, medkit, noisemaker, batteries, backpack, armor and marker beacons. |
| **Audio** | 166 generated sounds (`Audio/audio_manifest.json`). `AudioManager` provides pooled 3D voices with raycast occlusion and low-pass. `AmbienceController` handles layered beds and threat ducking, so silence before encounters is deliberate. Also ambient emitters and a horror event director with anchors. |
| **Visuals** | Custom shaders (triplanar rock with moss and wetness, terrain blend, wind foliage, water, soft particles, decals, screen overlay). Generated PBR texture sets and atlases. Fog/atmosphere profiles blend per area. Fluorescent flicker, fire flicker and dust motes. |
| **Save/load** | `Core/SaveSystem`: JSON with an atomic write and a rolling backup, versioned `SaveData`. It covers currency, storage, unlocks, discoveries, lore, stats, settings and a lost pack recovered from the death location. |
| **Builder** | `Scripts/Editor/*`: one-click **Monkey No Fear > Build Game (Full)**. It creates layers and physics settings, materials (with FBX material remap), the sound bank, data assets, all prefabs, the world scene from the level FBX markers (see `Docs/LEVEL_MARKERS.md`), the NavMesh, and a validator report. |

## Assets created

- **Player:** `Art/Models/Player`, converted from the supplied rig.
- **Creatures:** 9 rigged and animated creatures in `Art/Models/Creatures`: 3.7k–7.9k tris each, 3–9 legacy clips each, with clip events.
- **Props:** 5 prop kits in `Art/Models/Props`, 139 objects in total, each with COL_/SOCKET_ helpers and a manifest.
- **Levels:** 3 level FBX files.
- **Textures and audio:** generated texture sets and 166 sounds.
- **Generators:** every asset is generated by deterministic, re-runnable scripts under `Tools/`. Sources are in `SourceArt/` and preview renders in `Docs/previews/`.

## Continuation pass: repair, finish, polish

The second pass started from the committed project. It audited what had actually been produced rather than trusting that features worked because their scripts existed. Every fix below came from a concrete check.

### Orientation, mirroring and inside-out geometry
- **Every static model imported rotated −90° in Unity.** Levels and prop kits were exported without baking the axis conversion, so each root node carried a −90° X rotation. In Unity that meant:
  - Every marker's `transform.forward` pointed up.
  - `KitLibrary.Copy`, which zeroes the root rotation, laid every prop on its back.

  Static models are now exported with the conversion baked in (`bake_space_transform=True`). The rigged creatures and the player keep their −90° on child nodes, which is correct because they are only ever instantiated whole. `Tools/common/fbx_audit.py` parses the raw FBX of all 18 models and now passes. The conventions are documented in `Docs/ASSET_SPEC.md` §1.
- **No mirroring:** I checked creature and player facing from the rigs. All heads are on the −Y side (Unity +Z), the left limbs are on +X, and the Unity handedness conversion is a proper rotation.
- **Inside-out prop meshes:** the second prop kit's beam and cylinder builders wound every face inwards. That covered timbers, planks, rails, ladders, fences, watchtower, bridge, signposts and support frames, so in Unity you would have seen their far faces.
  - Both builders are fixed (`propkit_b_helpers._flip_from`).
  - Every kit object now goes through `fix_winding`: closed parts get consistent outward normals, and open shells become double-sided. Open shells include the nest bowl, the tent cloth, the speaker horn and the campfire ash bed. Foliage cards, signs, screens and decals are left single-sided on purpose.
  - All 5 kits, the 9 creatures and the player were verified with back-face-culled renders (`Docs/previews/assembly/kit_backface_*.png`, `creatures_culled_*.png`).
- **Wall-mounted buttons:** the elevator's LIFT button used the wrong mounting mode, so it would have rendered sideways, floating at the open corner of the platform. It now sits on a control box on the cage rail.
- **Fake-null `??`:** `GetComponent(...) ?? GetComponentInChildren(...)` on a Unity object was replaced, because Unity's fake-null breaks `??` in the editor.

### Z-fighting and clipping
- **Coplanar faces:** the audit checks every level shell and every placed part for coplanar same-facing faces with different materials. Fixes:
  - The portal hazard band sat on the lintel underside.
  - The corridor-side hazard header was flush with the gate frame face.
  - Two claw decals on the Sector B door shared a depth.
  - A sign sat 2 cm behind a wall face and pointed into it.
  - Signs now sit 2 cm and decals 1 cm off their surface. The decal shader also has a depth offset.
- **Bunker placement errors:**
  - Signs and decals floated 3–8 cm off walls.
  - Two corridor signs were half-buried in the walls.
  - The KEEP GATE CLOSED sign overlapped the button panel.
  - The gate beacons floated 7 cm off the frame; the emergency lights cut into the frame.
  - The workbench and terminal were sunk 6 cm into the diamond-plate floor.
  - Items were embedded in or hovering over tables, and the glowsticks floated in mid-air. Physics items spawned inside colliders are what launch away.
  - The terminal's back was inside the new wall panels.
  - The new corridor conduit was routed into the beacon and the cage lamps.
- **Forest placement errors:**
  - Trees grew through boulders and cliff chunks. An occupancy grid now keeps trunks, rocks, logs and cliff chunks apart, and structures reserve their footprints.
  - Logs and the fallen tree hovered on slopes; they are now tilted to rest on both ends.
  - The medkit hung 6 m in the air; it now sits on the watchtower deck.
  - A food can was embedded in a crate, a camp log seat cut into the fire ring, and posters overhung broken fences.
  - The forest rails were offset 0.6 m from the mine rails at the junction.
- **Mine:** the rock is an SDF with noise, while markers had been laid out on the nominal tunnel. `build_mine.snap_markers` now:
  - ray-casts every wall prop onto the real rock and faces it along the surface normal;
  - puts floor props and items on the real floor;
  - pitches rails along ramps;
  - mounts rock signs on backing planks;
  - turns decals into meshes that follow the rock;
  - moves lamps and ores out of timber-frame posts;
  - rotates walkways to run along the flooded tunnel (they had been 90° wrong, with their ends in the rock) and gives them support posts;
  - pulls the chasm railings back onto the ledge (one hung 8.5 m over the drop).

### Finished maps
- **Mine entrance was blocked.** The forest terrain left steep quads spanning the tunnel mouth: a wall the player would have hit just inside the portal.
  - The terrain slot is now cut to the tunnel's width.
  - A rock headwall seals the cliff around the tunnel.
  - I verified from both sides with both levels loaded: no gaps in the culled render.
- **Forest boundary:** it used to be climbable 24 m cliffs, an invisible wall, and a terrain edge 6 m beyond it. Now:
  - The boundary band and the north cliff face are on the NoClimb layer, so players slide off well before the safety wall.
  - A mountain ring with a treeline rises beyond every edge, so no reachable spot sees the void.
  - Each river gorge at the map edges is closed by a debris jam.
  - The stacked cliff-chunk "towers" were replaced by a natural boulder talus.
- **Bunker:**
  - A blue canteen (tables and benches) fills the empty hall.
  - Painted dado panels line the hall and bunk room walls.
  - Yellow floor guide lines run from the gate.
  - An expedition map board sits by the gate.
  - The bunk room has footlockers, a rug and a chair.
  - The generator room has shelving, crates and barrels.
  - The exit corridor has a conduit run that follows the ramp, a hazard band at the ramp foot, and MINE ACCESS signage.

### Gorilla Tag fan-game art direction
- **Textures:** point-filtered 128 px environment and creature textures, 512 px for the sign/decal atlases, 256 px for the player. Configured in `ImportPostprocessor`.
- **Art grade:** applied in the texture generator (`Tools/textures/build_textures.py GRADE`):
  - pale clean bunker concrete;
  - teal mine rock with warm yellow timbers;
  - a mossy green forest floor;
  - more saturated pines.
- **Atmospheres retuned** (`DataFactory.BuildAtmospheres`, with migration of untouched first-pass assets):
  - The bunker is a bright, nearly fog-free safe zone.
  - The forest fog is teal, with about 60 m to 8 % visibility (it was under 30 m), so landmarks stay readable.
  - The mine is teal, shifting violet and darker with depth, with a raised ambient so it doesn't rely on darkness.
- **New material:** `MNF_MetalPainted_Blue`, for the canteen and the bunk room panels.

### Gameplay loop and creatures
These are code-level fixes. Nothing here has run in Unity.
- **Gate:**
  - The terminal now has a gate control.
  - The override lever no longer reverses the gate on its way back up.
  - The closed gate now carves the NavMesh, so creatures can't path through it.
  - The bars move smoothly.
- **Hands:** the palm no longer shoves or launches the items it reaches for.
- **Pickaxe:**
  - Pressing it into rock no longer counts as a strike; strikes use controller-driven tip velocity.
  - It checks the contact nearest the tip.
- **Death and expeditions:**
  - The lost pack spawns under the body.
  - The expedition reroll now reaches the inactive forest and mine areas (wildlife, Falsekin, Borer, Clerk, Mourner, Gaunt, unstable floor).
- **Creatures:**
  - **All:** re-seated onto the NavMesh, with path-stall guards, and attack cooldowns that can't be skipped.
  - **Hollowback:** investigate timeout, and the foot-slide fix.
  - **Falsekin:** its "skip closer" can't pass through walls, and it re-disguises out of view.
  - **Ceiling Clerk:** no longer frozen forever by light; it retreats node by node instead of through rock, uses a NavMeshAgent on the floor, and no longer ends upside down.
  - **Borer:** emerges and returns on the NavMesh, and its charge overshoots instead of sliding sideways.
  - **Mourner:** no longer appears in plain view.
  - **Gaunt:** no longer stands motionless forever, and faces its path.
- **Editor builder:**
  - Sign and decal sizes were parsed as 0, which made most of them invisible.
  - The lost-pack prefab was missing.
  - The fan was static so it never spun.
  - Collider sync for the NavMesh bake.
  - A shader-missing crash guard.
  - The build is refused in Play mode.
  - Quest OpenXR feature enable.

## Verification status

### Tested / verified here (no Unity, no headset)
- **C# compilation:** the runtime and editor assemblies compile with **0 errors and 0 warnings**. This was done with `dotnet` against UnityEngine/UnityEditor reference assemblies from **Unity 2021**, not 2022.3. `XRSetup.cs` is behind `#if` guards and was not compiled.
- **Static checks:**
  - `validate_scripts.py`: class/file names, and no editor API in runtime code.
  - `check_references.py`: all sound and clip references resolve. Its cross-model notes are expected: the Falsekin uses the rabbit model while disguised.
  - `fbx_audit.py`: orientation, scale and axis bake of all 18 FBX files. PASS.
- **Assembly emulator:** `Tools/blender/levels/assemble_world.py` re-imports the exported level and kit FBX files and places every marker, station part, button, lever, beacon, sign and light the way `LevelAssembler` and `PrefabFactory` do. It then:
  - **audits** for missing props, floating or sunk props, wall gaps, embedded props, duplicates, prop/prop and prop/level intersections, coplanar faces, and sign/decal overhang. Results are in `Docs/previews/assembly/*_audit.txt`; every remaining entry was reviewed and is intended or an artifact of the audit.
  - **renders** player-eye views with the shipping look: point-filtered textures, per-area fog and ambient (`Docs/previews/assembly/<Level>_<view>.png`).
  - **renders culled** views with real back-face culling, as Unity draws them (`*_culled.png`). The bunker and mine show no holes. The only magenta is at level exits where the neighbouring level isn't loaded in that pass.
  - The forest-to-mine junction was checked with both levels loaded together.
- **Assets:** the pipelines' own re-import validations; the kit and creature back-face sheets; and by-eye review of every render above.

### Implemented but NOT verified
- The project has still **never been opened in Unity**: first import, the one-click builder, prefab and scene generation, the NavMesh bake and lighting have not been executed. The emulator reproduces the builder's placement maths, not Unity itself.
- **No gameplay has run:** locomotion feel, IK on the real rig, grabbing, holsters, buttons, levers, gate, terminal UI, strike validation, AI behaviour, fairness and pacing, the audio mix, and save/load round-trips.
- **No hardware testing:**
  - OpenXR on Quest 2/3/Pro, Index or Vive.
  - Controller bindings.
  - Tracking origin and recentering.
  - Comfort.
  - Quest performance.
- **Exact Unity look:** lights in the emulator are approximations (energy conversion), so final brightness has to be judged in the editor.

## Known risks / needs attention
1. **Performance on Quest:**
   - The forest has about 700 scattered trees plus about 150 backdrop trees, at 1.9k–3.9k tris each. Far clip follows the fog distance, and static batching is on. There are **no LODs or distance culling yet**.
   - The mine shell is 170k tris.
   - Profile with the Unity Profiler and OVR Metrics. Add tree LODs and occlusion culling if needed.
2. **Locomotion and strike tuning** on hardware: `MonkeyLocomotion` values, and the pick and spear strike thresholds in `ToolStrike`.
3. **NavMesh coverage:** generated ramps, the elevator, bridges and the Clerk's floor routes. Gate obstacle carving is also unverified.
4. **AI difficulty and fairness numbers** in `CreatureProfile` are first-pass values.
5. **Generated audio and textures** are procedural placeholders of decent quality.
6. **Pop-out effects:** the Mourner's final vanish and the Falsekin hiding switch renderers off; they don't fade.

## How to test
See `README.md`:
1. Open the project in Unity 2022.3.
2. Run **Monkey No Fear > Build Game (Full)**.
3. Read `Logs/MonkeyNoFear_Validation.txt`.
4. Press Play, with a headset or with the desktop debug controls (F1 overlay, F6 teleports).

Smoke-test route:
1. In the bunker, buy a flashlight at the terminal.
2. Open the gate with the button. Then try the terminal's gate control and the override lever.
3. Climb the ramp to the forest using arm locomotion.
4. At the rabbit clearing, look for the Falsekin tells.
5. At the mine mouth, check that the forest and mine rails line up, and walk through the portal.
6. Mine iron in the hall, then reset the breaker and ride the elevator.
7. Return to the bunker and sell.
8. Sleep, restart Play, and confirm the progress loaded.

To re-run the offline checks:

```bash
python3 Tools/common/validate_scripts.py
```

```bash
python3 Tools/common/check_references.py
```

```bash
blender -b -P Tools/common/fbx_audit.py -- .
```

```bash
EGL_PLATFORM=surfaceless blender -b -P Tools/blender/levels/assemble_world.py -- . --level Bunker --audit --views --backface
```
