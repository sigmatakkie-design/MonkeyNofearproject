# MONKEY NO FEAR

Arm-locomotion VR horror survival game (Unity 2022.3 LTS, Built-in Render Pipeline, OpenXR).

You are a monkey in a sealed bunker after the Monkopocalypse. Each expedition you go out through the security gate, cross the haunted forest and descend the mine. You mine ore, sell it at the bunker and buy better gear. The things out there hunt by sound, mimicry and light.

## First launch

1. Install **Unity 2022.3 LTS** (2022.3.20f1 or newer). Add the **Android Build Support** module (OpenJDK + SDK/NDK) if you target standalone Quest.
2. Open the `MonkeyNoFear` folder with Unity Hub. Unity resolves the packages in `Packages/manifest.json` (XR Plug-in Management 4.4, OpenXR 1.10) and imports every FBX, texture and sound. The first import takes several minutes.
3. A dialog offers to build the game. Choose **Build**, or run **Monkey No Fear > Build Game (Full)** at any time. The build runs in this order:
   1. Project settings: layers, collision matrix, physics rates, quality, player settings, XR loaders.
   2. Materials.
   3. Sound bank.
   4. Data assets: items, minerals, shop, creatures, atmospheres, lore.
   5. Prefabs.
   6. Assembles `Assets/MonkeyNoFear/Scenes/MonkeyNoFear_World.unity` from the Bunker, Forest and Mine level FBX files.
   7. Bakes the NavMesh.
   8. Runs **Validate Project**, which writes `Logs/MonkeyNoFear_Validation.txt`.

   Each stage is also available on its own under **Monkey No Fear > Steps**.
4. Press **Play**.
   - **With a headset:** connect it with Quest Link, Air Link or SteamVR, then check **Edit > Project Settings > XR Plug-in Management**. The OpenXR loader should be enabled, with the Oculus Touch, Valve Index and HTC Vive interaction profiles.
   - **Without a headset:** the desktop debug driver takes over automatically.
5. For a standalone Quest build, switch the platform to Android in **File > Build Settings**, then **Build And Run**. The world scene is already in the scene list.

## Playing in VR

- **Movement:** Gorilla-Tag style. Hands that touch a surface anchor to it; push against the ground or walls to move. When you let go, the hand's velocity becomes your jump. Climb anything that isn't marked as slippery.
- **Grab:** use the **grip** button to grab items. Holsters are on your hips and chest and the backpack sits over your shoulder; the head slot takes the headlamp or helmet.
- **Use:** the **trigger** uses the held item (flashlight, scanner, flare, noisemaker and so on). The **primary** button triggers item extras.
- **Pickaxe:** swing it at an ore deposit. A strike only counts with enough real impact speed and a good angle.
- **Bunker controls:** press buttons and pull levers with your hands. The terminal has a physical keypad.
  - Terminal pages: shop, storage, expedition, archive (lore and bestiary), stats and settings.
  - Settings include snap turn and **joystick movement (accessibility)**, which is off by default.
- **Wrist display:** shows health, vigor, the battery and the area.

## Desktop debug controls (Editor / development builds)

| Input | Action |
|---|---|
| Mouse / Tab | Look / toggle cursor lock |
| W A S D | Knuckle-walk (the hands paw the ground through the real arm locomotion) |
| Shift / Space / C | Faster paws / two-hand jump push / crouch |
| LMB / RMB | Right / left grip |
| E / Q | Right / left trigger |
| R / F | Right primary / secondary |
| Mouse wheel / hold Z | Right hand reach / left hand reaches forward |
| F1 | Debug overlay (fps, locomotion state, area, threat, AI states) |
| F5 / F6 / F7 | +500 currency / cycle teleport targets / heal |

Select any creature in the Scene view to see its debug gizmos: hearing and vision ranges, last-known player position and current state.

The save file is `monkeynofear_save.json` in `Application.persistentDataPath`. **Monkey No Fear > Delete Save File** resets progress.

## Project layout

```
Assets/MonkeyNoFear/
  Scripts/Runtime   game code (Core, Data, Audio, AI, Player, Interaction, Items, Mining, Bunker, World)
  Scripts/Editor    one-click builder (materials, prefabs, data, level assembly, navmesh, project setup, validator)
  Shaders           MNF/Triplanar, TerrainBlend, Foliage, Water, Particle, Decal, ScreenOverlay
  Art/Models        Player (converted from the supplied rig), Creatures (9), Props (5 kits), Levels (Bunker, Forest, Mine)
  Art/Textures      generated PBR sets and atlases     Audio/  generated sound library + manifest
Docs/               ASSET_SPEC.md, LEVEL_MARKERS.md, briefs, preview renders, DEVELOPMENT_REPORT.md
SourceArt/          .blend sources (player, creatures, prop kits, level previews)
Tools/              Blender/Python generators for every asset (re-runnable, deterministic) + validators
```

To regenerate assets you need Blender 4.x/5.x, or the `bpy` Python module, plus numpy and scikit-image. Examples:

```bash
blender -b -P Tools/blender/levels/build_mine.py -- .
```

```bash
python3 Tools/common/validate_scripts.py
```

## Offline validation (no Unity needed)

These checks run with Blender 4.2+/5.x (or the `bpy` Python module) and plain Python:

| Check | What it verifies |
|---|---|
| `Tools/common/fbx_audit.py` | Orientation of every exported FBX: the axis conversion is baked, no mirrored or zero scales, and the rigged roots are correct. |
| `Tools/blender/levels/assemble_world.py -- . --level Bunker\|Forest\|Mine\|Forest+Mine [--audit] [--views] [--backface]` | Re-imports the exported levels and kits and places everything the way the Unity builder does. **Audit** looks for floating, sunk, intersecting and duplicate props, coplanar z-fighting faces, and signs or decals that don't sit flush. **Views** renders player-eye views with the shipping look. **Backface** renders with back-face culling as Unity draws, so holes show magenta. Output goes to `Docs/previews/assembly/`. |
| `Tools/common/validate_scripts.py`, `Tools/common/check_references.py` | C# file/class rules, and that every sound and clip reference resolves. |

`--backface` uses Blender's Workbench engine. On a headless Linux box, install Mesa EGL (`libegl1 libegl-mesa0 libgl1-mesa-dri`) and set `EGL_PLATFORM=surfaceless`.

## Build without Unity (GitHub Actions)

`.github/workflows/build.yml` builds the Windows `.exe` and the Quest `.apk` on GitHub's servers, using GameCI and `CIBuild.Build`.

1. Push this project to a GitHub repository. Builds are free for public repositories; private ones use your Actions minutes.
2. In the repository, go to **Settings > Secrets and variables > Actions** and add three secrets:
   - `UNITY_EMAIL` and `UNITY_PASSWORD`: your free Unity account.
   - `UNITY_LICENSE`: the full text of your `Unity_lic.ulf`.

   Unity creates that file the first time you sign in to Unity Hub on any computer. On Windows it's at `C:\ProgramData\Unity\Unity_lic.ulf`, and on macOS at `/Library/Application Support/Unity/Unity_lic.ulf`. See https://game.ci/docs/github/activation for other ways to get it.
3. Open the **Actions** tab, choose **Build game**, then **Run workflow**. A run takes 30–60 minutes the first time.
4. Download the `MonkeyNoFear-StandaloneWindows64` and `MonkeyNoFear-Android` artifacts from the finished run.

The APK sideloads onto a Quest with Developer Mode enabled, using SideQuest or `adb install`.
