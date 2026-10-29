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

## Verification status

### Tested / verified here
- **C# compilation:** all 121 C# files compile with **0 errors and 0 warnings**, in two assemblies (runtime and editor). This was done with `dotnet` against the UnityEngine/UnityEditor reference assemblies from **Unity 2021**, not 2022.3, so a few API differences could still appear. Packages were unavailable offline, so the XR-package code in `XRSetup.cs` is behind `#if` guards and was **not compiled**.
- **Static checks:**
  - `Tools/common/validate_scripts.py`: every MonoBehaviour/ScriptableObject is in a file with a matching name, and runtime code has no UnityEditor usage.
  - `Tools/common/check_references.py`: every sound name referenced from code exists, and the animation clips used by AI code exist on the models. The script reports a few cross-model warnings; they are harmless, because the Falsekin plays rabbit clips only on its rabbit disguise model.
- **Marker cross-reference:** every level marker resolves to a known kit prop, light preset, horror event type, lore id, item id or sound.
- **Assets:** each pipeline re-imported its own FBX files and checked node names, helpers, materials, UVs, scale and tri budgets. I inspected the preview renders of the levels, creatures, props and textures by eye. Props and creatures build deterministically.

### Implemented but NOT verified
Unity and a headset were not available in this environment.

- The project has **never been opened in Unity**. The first import, the one-click builder, prefab and scene generation, the NavMesh bake and the lighting have not been executed.
- **No gameplay has run.** That includes locomotion feel and tuning, IK quality on the real rig, grabbing, holsters, buttons and levers, the gate, the terminal UI, mining strike validation, AI behaviour and its fairness tuning, horror event pacing, audio mix and occlusion, and save/load round-trips.
- **No hardware testing:** OpenXR on Quest 2/3/Pro, Index or Vive; controller bindings for each interaction profile; floor tracking origin and recentering; comfort; Quest performance (fps, draw calls, fill rate with fog and foliage).
- XR plug-in configuration (`XRSetup.cs`) has not been compiled or run.
- Creature animation in Unity: the legacy clip import, the `|` prefix stripping and the jaw overlay masking.
- Material and texture appearance under Unity lighting. The Blender previews use approximate materials (rock shows untextured in the mine previews).

## Known risks / needs attention
1. **Performance on Quest:** the forest has about 710 trees at 1.9k–3.9k tris each. Mitigations: far clip tied to fog, distance culling of small props, and static batching. Profile with the Unity Profiler and OVR Metrics. Tree LODs may be needed.
2. **Locomotion tuning** (`MonkeyLocomotion` inspector values) must be tuned on hardware: arm length multiplier, max speed, jump multiplier, slide friction.
3. **NavMesh coverage** in the generated mine and forest: check the baked areas, especially the ramps, the elevator and the bridge.
4. **AI difficulty and fairness numbers** in the `CreatureProfile` assets are first-pass values.
5. **Generated audio and textures** are procedural placeholders of decent quality. Replace them with recorded or authored assets for release.

## How to test
See `README.md`:
1. Open the project in Unity 2022.3.
2. Run **Monkey No Fear > Build Game (Full)**.
3. Read `Logs/MonkeyNoFear_Validation.txt`.
4. Press Play, either with a headset over Link or SteamVR, or with the desktop debug controls (F1 overlay, F6 teleports between the bunker, forest and mine levels).

Suggested first smoke-test route:
1. Spawn in the bunker and buy a flashlight at the terminal.
2. Open the gate with the button.
3. Walk with your arms up the ramp to the forest.
4. Find the rabbit clearing and look for the Falsekin tells.
5. Enter the mine and mine iron in the hall.
6. Take the elevator after resetting the breaker.
7. Return and sell.
8. Sleep to save, then restart Play and confirm the progress loaded.
