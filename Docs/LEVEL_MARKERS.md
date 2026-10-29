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
