# Props, Tools & Items Brief

Read `Docs/ASSET_SPEC.md` first. Each kit is one FBX in `Assets/MonkeyNoFear/Art/Models/Props/` containing many
independent top-level objects, each modelled **at the world origin** with the pivot convention from the spec
(objects may be spread out in the .blend for previewing, but must be moved to the origin before export, or export
each with its location zeroed). Manifest: `Assets/MonkeyNoFear/Art/Models/Props/props_manifest.json` (merge — other
kits write to the same file; read-modify-write it). Scripts in `Tools/blender/props/`. Previews in
`Docs/previews/props/` (contact sheets with a scale reference — a 1 m cube or a 1.7 m figure).

Quality bar: VR players see these up close. No naked primitives: bevel edges, add wear, layered shapes, plausible
construction (bolts, brackets, welds, rims, straps). Silhouettes matter more than micro-detail. Stay within budgets.
Assign catalog materials only (see spec §2). Give every object UVs suitable for tiling textures at the stated density.

Helper conventions: `COL_*` collision boxes (children), `TIP`, `GRIP`, `GRIP2`, `LIGHT`, `SOCKET_*` empties
(children). An empty's −Y axis is its forward. Moving parts must be **separate top-level objects** with their own
pivot (e.g. a lever handle pivots at its hinge) and listed in the manifest with notes.

## Kit_Tools.fbx — handheld tools & items (pivot = main grip, forward/tip along −Y, up +Z)
| Object | Size guide | Notes |
|---|---|---|
| Pickaxe_T1 | handle 0.75 m | "Rusty Pick": worn wooden handle (MNF_WoodHandle), rusted head (MNF_MetalRusted), rag-wrapped grip. Head at the far end (−Y), **pointed tip toward −Z**, blunt/adze end toward +Z. Empty `TIP` at the pointed tip; `COL_Handle`, `COL_Head`. Grip at 0.12 m from the butt. |
| Pickaxe_T2 | 0.8 m | "Tempered Pick": steel head (MNF_MetalBare) with yellow painted collar (MNF_MetalPainted_Yellow), rubber grip. Same helpers. |
| Pickaxe_T3 | 0.85 m | "Resonance Pick": dark alloy head with a small embedded luminous crystal (MNF_Crystal) and copper wire wrap. Same helpers. |
| Spear | 1.6 m | Improvised: wooden shaft, sharpened scrap-metal blade lashed with rope. Grip at 0.45 m from the butt; `TIP` at the point (−Y). `COL_Shaft`, `COL_Blade`. |
| Flashlight | 0.24 m | Chunky industrial torch (MNF_Plastic_Yellow body, rubber grip ring, glass lens MNF_Glass, bulb MNF_BulbWarm). `LIGHT` empty at the lens facing −Y. |
| Headlamp | strap + lamp | Lamp on an elastic strap; `LIGHT` empty. Pivot at the strap centre. |
| Glowstick | 0.15 m | Plastic tube (MNF_BulbGreen inner, MNF_Plastic_Gray caps). |
| Flare | 0.25 m | Red road flare (MNF_Plastic_Orange/MNF_Paper), striker cap, `TIP` at the burning end. |
| Noisemaker | 0.18 m | "Rattle can": tin can full of bolts, wired shut, taped. |
| Scanner | 0.2 m | Handheld ore scanner: casing (MNF_Plastic_Black), antenna, small screen object `Screen` (MNF_Screen, flat quad facing +Z, i.e. toward the user when held) and an indicator lamp `Lamp` (MNF_BulbGreen). |
| RopeCoil | 0.3 m | Coiled climbing rope (MNF_Rope) with a metal hook (`TIP` at the hook). |
| Medkit | 0.25 m | Dented metal first-aid tin (MNF_MetalPainted_Red, white cross from MNF_Paper). |
| MarkerBeacon | 0.2 m | Small deployable beacon with a red blinking dome (MNF_BulbRed object `Lamp`) and a spike at the bottom. |
| Backpack | 0.5 m | Worn canvas expedition backpack (MNF_FabricCanvas, straps MNF_Rubber, buckles MNF_MetalBare). Displayed over the player's shoulder. Pivot at the top strap. |
| Battery | 0.1 m | Chunky battery pack for the flashlight. |
| FoodCan | 0.12 m | Canned ration with paper label (MNF_Paper, MNF_MetalBare). |
| RabbitMeat | 0.15 m | Skinned rabbit haunch/leg (MNF_Meat). |
| BoarMeat | 0.25 m | Larger cut of meat on bone (MNF_Meat, MNF_Teeth for bone). |
| FalsekinGland | 0.12 m | Disgusting pulsing organ with dark veins (MNF_Flesh, MNF_Anomalous) — valuable. |
| LoreTape | 0.1 m | Cassette tape (MNF_Plastic_Black, MNF_Paper label). |
| MinerTag | 0.05 m | Dog-tag on a chain (MNF_MetalBare). |
| OreChunk_Iron / _Copper / _Crystal / _Blackstone / _Anomalous | 0.08–0.16 m | Collectible chunks dropped by deposits; must look distinct from each other (shape + material): iron = heavy dark lumpy nugget with metallic flecks; copper = rock with reddish-orange veins and green patina; crystal = a cluster of 2–4 hexagonal prisms; blackstone = angular, glassy-black shard; anomalous = a small rounded core with glowing veins wrapped in rock. Pivot at centre. |

## Kit_Deposits.fbx — mineable ore deposits (pivot at the bottom centre where it meets the floor/wall)
Each deposit is a top-level object with children `Base` (the host rock, stays) and `Chunk_00`…`Chunk_0N` (4–6
removable pieces; the builder hides one per mining stage), plus `COL_Body` box. Distinct mesh language per type:
* Deposit_Iron (~1.0 m): lumpy rock boulder with dark metallic nodules erupting through the surface.
* Deposit_Copper (~1.1 m): fractured rock with protruding reddish-orange vein ridges and green patina crust.
* Deposit_Crystal (~1.2 m): sharp clusters of hexagonal luminous prisms growing from rock at different angles.
* Deposit_Blackstone (~1.3 m): angular obsidian-like monolith shards jutting from the ground, light-absorbing.
* Deposit_Anomalous (~1.0 m): an organic, faintly pulsing core embedded in cracked rock, veins spreading outward
  into the surrounding stone — wrong, almost alive.
* Deposit_Iron_Wall, Deposit_Copper_Wall, Deposit_Crystal_Wall: wall-mounted variants (pivot at wall contact, −Y out).

## Kit_Bunker.fbx — survivor bunker furniture & machinery
| Object | Notes |
|---|---|
| Workbench | 2.2 m × 0.9 m heavy steel/wood bench with vice, scattered tools, pegboard back panel (1.2 m high) with tool outlines. Top surface at 0.95 m. |
| Terminal | Chunky industrial computer: CRT monitor (≈0.5 m) on a steel stand, keyboard, cables. Child `Screen` = flat quad (MNF_Screen), 0.42 × 0.32 m, facing −Y (toward the user), its pivot at the screen centre. Pivot of Terminal at floor/bench contact. |
| TerminalButton_Body + TerminalButton_Cap | Chunky square push button for the console (cap is separate, pivot at its base, presses along +Y into the console). 7 cm. |
| BigButton_Body + BigButton_Cap | Mushroom emergency button housing (yellow/black) and a red cap (separate object, presses along +Y). Wall-mounted pivot. |
| Lever_Base + Lever_Handle | Industrial wall lever; handle separate with pivot at its hinge, rotates about the X axis ±45°. |
| SecurityGate_Frame | Heavy steel frame for a 3.0 m wide × 2.8 m high opening, hazard-striped jambs (MNF_Hazard), motor housing on top. Pivot at the floor centre of the opening. |
| SecurityGate_Bars | The moving barred door: thick vertical bars with horizontal braces, 3.0 × 2.8 m, slides **upward (+Z)** into the frame's housing. Pivot at the bottom centre. `COL_Bars` box. |
| WarningBeacon | Rotating amber beacon with cage; child `Lamp` (MNF_BulbRed). Wall mount. |
| FluorescentFixture | 1.2 m tube fixture with grime, child `Tube` (MNF_BulbCold). Ceiling mount (pivot at top). |
| CageLamp | Wall-mounted caged bulb (MNF_BulbWarm `Bulb` child). |
| EmergencyLight | Red emergency light (MNF_BulbRed `Bulb`). |
| ToolRack | Wall rack 2.0 m wide with 6 hooks/brackets; empties `SOCKET_0`…`SOCKET_5` where tools hang. |
| ShelfUnit | 2.0 m tall steel shelving with boxes, jars, cans, coils. |
| StorageLocker | Heavy locker cabinet with an open hopper/drawer on top (1.2 m wide, 1.6 m tall); empty `SOCKET_Deposit` at the hopper centre. |
| SellMachine | "Assay & Trade" machine: hopper bin (top opening ~0.6 × 0.5 m at 1.0 m height; `SOCKET_Bin`), a screen quad `Screen` (MNF_Screen), pneumatic tube going up into the ceiling, hazard stripes. |
| Dispenser | Pneumatic delivery tube outlet with a small tray (`SOCKET_Out`). Wall mounted. |
| Bunkbed | Metal bunk bed with stained mattresses and blanket (MNF_FabricBlanket). |
| Generator | Large diesel generator, pipes, gauges, hazard stripes. |
| VentFan | Wall ventilation fan housing; child `Fan` (separate rotating blades, pivot at the hub). |
| Pipe_Straight (2 m), Pipe_Elbow, Pipe_Valve | Pipe kit, ~0.15 m diameter. |
| CableBundle | 2 m bundle of drooping cables. |
| Crate_A, Crate_B, Barrel, Chair, Table, Radio (with dial and antenna), Clipboard, Locker_Tall, FuseBox, Bucket | Clutter. |
| BlastDoor | Huge round/rectangular outer blast door (open position, swung against a wall) for the bunker exterior. |
| PosterBoard | Cork board with pinned notes (MNF_Paper). |

## Kit_Forest.fbx — haunted forest (pivot at the base)
| Object | Notes |
|---|---|
| Tree_Pine_A, _B, _C | Tall dark conifers 12–18 m, dense layered needle cards (MNF_FoliagePine) on a bark trunk (MNF_BarkPine); some dead lower branches. `COL_Trunk` (trunk only). ≤ 4k tris. |
| Tree_Dead_A, _B, _C | Twisted dead trees 8–12 m, bare clawing branches (MNF_BarkDead). Very strong, unsettling silhouettes. `COL_Trunk`. |
| Tree_Gnarled | Huge old twisted tree with roots, 10 m, trunk Ø 1.5 m, a hollow at its base. |
| Stump, Log, FallenTree (12 m long, usable as a bridge; `COL_Log` capsule-like box) | |
| Rock_A … Rock_E | Rocks 0.5–3 m, sharp and weathered (MNF_RockDry, some MNF_Moss on top faces). |
| Boulder_Large | 5–6 m climbable boulder. |
| CliffChunk_A, CliffChunk_B | 8–12 m tall rock wall pieces with ledges (for building cliffs; MNF_RockDry_Tri allowed). |
| Bush_A, Bush_B | Dense shrubs with leaf cards (MNF_FoliageLeaf). No collider. |
| Fern, GrassTuft, MushroomCluster | Ground detail cards. No colliders. |
| Fence_Section (2.5 m), Fence_Broken | Weathered wooden mining-company fence with barbed wire. |
| SignPost | Wooden post with a sign board; child `Board` is a quad that faces −Y (Unity puts the sign atlas on it). |
| WarningBoard | Large old warning board on two posts; child `Board` quad. |
| Tent | Collapsed/torn canvas tent (MNF_FabricCanvas). |
| Campfire | Stone ring with charred logs. Empty `SOCKET_Fire`. |
| CampLantern | Hanging oil lantern (MNF_BulbWarm `Bulb`). |
| Cabin_Ruin | Small ruined wooden cabin (4 × 5 m), partly collapsed roof, overgrown, door gap, interior walkable; `COL_*` boxes for walls. |
| Watchtower | 6 m wooden watchtower with ladder and platform (climbable). `COL_*` boxes. |
| Bridge_Broken | 10 m wooden plank bridge with a broken gap in the middle. `COL_*` boxes for the plank sections. |
| Minecart_Abandoned | Overturned rusty minecart. |
| Nest | Large twig nest bowl (1.2 m) with bones and fur. |
| Burrow | Earth mound with a dark hole (0.3 m) — rabbits vanish into it. |
| MineEntrance | Timber-framed mine portal (5 m wide, 4.5 m tall), heavy beams, rusted sign plate child `Board`, rail tracks leading in, scattered planks. Pivot at the bottom centre of the opening, −Y facing out toward the forest. |

## Kit_Mine.fbx — mine infrastructure (pivot at the base)
| Object | Notes |
|---|---|
| SupportFrame | Timber support set: two posts + header beam for a 3.5 m wide × 3.2 m tall tunnel (MNF_WoodBeam), iron brackets, some cracked. |
| SupportFrame_Broken | Same but collapsed on one side. |
| Rail_Straight (2 m), Rail_Curve (gentle), Rail_End | Narrow-gauge rails on sleepers (MNF_MetalRusted, MNF_WoodBeam). |
| Minecart | Rusty ore cart on wheels (separate object `Minecart_Wheels`? no — single object is fine), interior holds ore. `COL_*`. |
| MineLamp | Caged mining lamp on a bracket (`Bulb` child, MNF_BulbWarm). |
| LampString | 4 m string of bulbs sagging between hooks (`Bulb_0..3`). |
| Ladder (3 m) | Wooden ladder. |
| Walkway (2 m section) | Metal grated walkway section with railings (MNF_MetalGrate, MNF_MetalPainted_Yellow railing). `COL_Floor`. |
| Railing (2 m) | |
| Elevator_Platform | 3 × 3 m caged lift platform floor with railings (moves vertically). `COL_Floor`, `COL_Rail_*`. |
| Elevator_Frame | Headframe/guide rails for a 40 m shaft (can be one 8 m segment stacked by the builder). |
| Workstation | Abandoned miner desk with chair, helmet, thermos, papers. |
| Helmet | Miner helmet with lamp. |
| RubblePile_A, _B | Collapsed rock & timber rubble. |
| LooseRockWall | A 3.5 × 3.2 m plug of loose rubble that blocks a tunnel (used as Borer emergence points; the builder can hide it). |
| BorerHole | Large ragged burrow opening (2.5 m) surrounded by broken rock and deep scratches. Pivot at the centre of the opening floor. |
| PA_Speaker | Old horn loudspeaker on a bracket. |
| Crate_Mine, Barrel_Mine, ToolPile (broken shovels & picks) | Clutter. |
| Sign_Level | Metal plate on a post; child `Board` quad. |
| TunnelMarker | Painted colour-coded marker plate (child `Plate`, MNF_MetalPainted_Red/Yellow/Green variants as `TunnelMarker_Red/_Yellow/_Green`). |
| PipeRun (4 m) | Rusty ventilation duct/pipe run. |
| Generator_Small | Dead mine generator. |
| ScratchedPlate | A metal wall panel 2 × 2 m (used for the "scratches on the other side" event). |
