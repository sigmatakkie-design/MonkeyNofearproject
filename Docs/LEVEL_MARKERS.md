# Level marker grammar

Levels are authored in Blender by `Tools/blender/levels/build_*.py` and exported as `Assets/MonkeyNoFear/Art/Models/Levels/<Level>.fbx`.
`Scripts/Editor/LevelAssembler.cs` turns them into gameplay objects when you run **Monkey No Fear > Steps > 6 Assemble World**.

Blender duplicate suffixes (`.001`) are stripped before parsing. Fields are separated by `_`. A marker's forward direction is the empty's local −Y in Blender, which becomes +Z in Unity.

## Geometry objects (meshes)

| Name pattern | Result |
|---|---|
| *(any mesh)* | Static MeshCollider, `Surface` (kind derived from material), Environment layer, contributes GI |
| `…NOCOL_…` | Visual only, no collider |
| `…COLONLY_…` | Collider only, renderer disabled |
| `…NOCLIMB_…` | NoClimb layer, slipperiness 1 (hands slide and cannot anchor) |
| `WATER_…` | MNF_Water material, no collider |
| `UNSTABLE_…` | Non-static `UnstableFloor` that collapses under the player |
| `ZONE_<AreaId>_<priority>` | Box trigger `AreaZone` (Bunker, Corridor, Forest, MineShallow, MineMid, MineDeep) |
| `KILL_…` | Box `KillVolume` (respawn at the last safe position, with damage) |
| `GAUNTVIEW…` | Low-priority MineDeep zone used to decide when the Gaunt is visible |

Flags combine; for example `COLONLY_NOCLIMB_Bounds` is an invisible, unclimbable boundary.

Generated pieces that use these flags:

| Object | What it is |
|---|---|
| `NOCLIMB_TerrainEdge_i_j` (Forest) | Outer boundary cliffs and the north cliff face. These are terrain faces on the NoClimb layer, so players slide back down long before they reach the `COLONLY_NOCLIMB_Bounds` safety wall. |
| `NOCOL_Backdrop` (Forest) | The mountain ring rising beyond every map edge, plus its treeline. It is seamless with the terrain edge and has no collider or shadows. No reachable spot can see past it. |
| `NOCOL_DECAL_<cell>` (Mine) | Decals as meshes projected onto the rock (7 × 7 grid, 12 mm off the surface). A flat atlas quad cannot sit on curved rock. |
| `MineDressing` (Mine) | Timber backing planks behind every rock-mounted sign, and walkway support posts down to the floor. |

## Markers (empties named `MK_<TYPE>_…`)

| Marker | Meaning |
|---|---|
| `MK_SPAWN_Player` / `MK_SPAWN_<x>` | Player start / respawn points (also debug teleports) |
| `MK_PROP_<KitObject>` | Instance of a kit prefab (any object in `props_manifest_*.json`) or `Item_<name>` prefab |
| `MK_LIGHT_<Preset>` | Fluor, FluorBad (flicker), Cage, Emergency, Red, MineLamp, MineLampDim, String, Crystal, Camp, Spot |
| `MK_ORE_<Shallow\|Mid\|Deep\|Anomalous>[_Wall]` | `OreSpawnPoint`; the `ResourceDistributor` rerolls deposits each expedition |
| `MK_WILD_<Creature>_<count>_<radius>[_FK]` | Wildlife spawn area; `_FK` lets Falsekin replace rabbits there |
| `MK_FALSEKIN_…`, `MK_FKNEST_…` | Falsekin spawn / nest (the nest also places the Nest prop) |
| `MK_HB_SPAWN…`, `MK_HB_<x>` | Hollowback spawn / patrol and listen points |
| `MK_COVER_…` | Hide spots used by fairness rules and AI search |
| `MK_CLERK_SPAWN`, `MK_CLERK_NODE` | Ceiling Clerk spawn / ceiling nodes it travels between |
| `MK_BORER_SPAWN_<radius>`, `MK_BORER_HOLE[_Plug]` | Borer territory / emergence holes (a `_Plug` hole is sealed by a LooseRockWall) |
| `MK_MOURNER_SPAWN`, `MK_MOURNER_POINT`, `MK_MOURNER_LURE` | Lantern Mourner spawn / wander points / lure points |
| `MK_GAUNT_SPAWN`, `MK_GAUNT_PATH_<i>` | Deep-mine Gaunt and its walk path below the chasm |
| `MK_EVENT_<HorrorEventType>` | `HorrorAnchor` for the event director (PhantomFootsteps, MinecartNudge, WallScratch, LightTurnsOn, DeadRoomHum, PARecording, PeripheralSilhouette, …) |
| `MK_SOUND_<name>` | `AmbientEmitter`: a loop if the name ends in `_loop`, otherwise random one-shots |
| `MK_SIGN_<cell>_<w>_<h>`, `MK_DECAL_<cell>_<size>` | Atlas quads (MNF_Signs / MNF_Decals cells) |
| `MK_LORE_<loreId>[_Tape]` | Lore note or tape (`LoreDatabase` id) |
| `MK_ITEM_<itemId>` | Pickup placed from `Item_<itemId>.asset` |
| `MK_STATION_<Terminal\|SellMachine\|StorageLocker\|ToolRack\|Dispenser\|Bed\|Gate\|…>` | Bunker stations |
| `MK_ELEV_<Top\|Bottom\|CallTop\|CallBottom\|Breaker>` | Service elevator stops, call buttons and power breaker |
| `MK_ROPE_<length>` | Fixed climbing rope hanging down from the marker |
| `MK_FOGBANK_…` | Local fog volume particles |
| `MK_TELEPORT_<name>` | Debug teleport target (F6) |

When the assembler cannot resolve a marker, it logs `[MNF] Unknown marker …` or `[MNF] No prop prefab for …` and counts it in the build summary.

## Placement rules the generators guarantee

Both `Tools/blender/levels/assemble_world.py --audit` and the generators check these rules. The emulator re-imports the exported FBX files, places everything the way `LevelAssembler` does, and reports problems.

- **Axis export:** static models are exported with `bake_space_transform=True`, so every marker's `transform.forward` is its Blender −Y. `Tools/common/fbx_audit.py` checks this.
- **Wall-mounted props:** this covers lamps, PA speakers, `_Wall` ore, wall-scratch plates, elevator call buttons and the breaker. Each pivot sits on the wall face.
  - In the mine, `build_mine.snap_markers` ray-casts the generated rock and turns each prop along the surface normal.
  - Lamps and ores are moved along the wall out of timber-frame posts.
- **Floor props and items:** each one rests on the real floor.
  - Items use their rest height above the floor: 0.006 m for notes and tags, 0.065 m for cans, 0.205 m for the medkit, which hangs from its handle.
  - Anything on furniture uses the furniture's top height. Examples: `TABLE_TOP` in the bunker and the 0.06 m diamond plate under the workbench.
- **Long props on slopes:** rails are pitched along the slope. Logs and the fallen tree are tilted so both ends touch the ground (`rest_long`).
- **Forest scatter:** an occupancy grid keeps trunks, rocks, logs and cliff chunks from interpenetrating. Free-standing structures reserve their footprint before scatter.
- **Signs and decals:** they are flush with a surface: no corner overhangs into the air or is buried. Overlapping decals never share a depth.
- **Coplanar faces:** coplanar, same-facing faces only occur where they share a mesh, material and world UVs. Everywhere else, 2–3 cm offsets keep them apart. Examples: the gate header recessed behind the frame face, and the portal hazard band above the lintel underside.
