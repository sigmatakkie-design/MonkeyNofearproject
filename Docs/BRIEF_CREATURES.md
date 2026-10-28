# Creature Modeling & Animation Brief

Read `Docs/ASSET_SPEC.md` first (conventions, export settings, material catalog, bone naming).
Output: `Assets/MonkeyNoFear/Art/Models/Creatures/<Name>.fbx`, manifest
`Assets/MonkeyNoFear/Art/Models/Creatures/creatures_manifest.json`, scripts in `Tools/blender/creatures/`,
previews in `Docs/previews/creatures/` (turnaround: front / side / 3-4 view, plus a contact sheet showing 3–4 key
frames of every clip). Look at every preview yourself and iterate until silhouettes read clearly.

Game context: VR horror-survival. Stylised, readable **monkey** characters (Gorilla-Tag-like proportions for the
player) in detailed atmospheric environments. Monsters are *rotten, infected, mutated monkeys* and mimics. They
must be original designs (no copying of other games' assets). Horror comes from silhouette, anatomy that is
"physically wrong", and movement. Each creature must be recognisable as a silhouette in thick fog.

Modelling approach suggestion: Skin modifier on a vertex skeleton (or metaball/sculpt-like displacement) →
apply → remesh/decimate to budget → add details (teeth = small cones, nails, eyes, ribs, growths) as separate
mesh parts joined into the body or parented to bones → UV (Smart UV Project) → armature (bones named per
spec) → automatic weights (`parent_set(type='ARMATURE_AUTO')`), fix with manual weights for rigid parts (teeth/eyes
100% to head/jaw) → keyframe clips as Actions → export. A single skinned mesh per creature is preferred (one
SkinnedMeshRenderer), multiple materials are fine (≤ 5 per creature). Rigid attachments (lamp cluster) may be
separate meshes parented to a bone.

General rig rules: `root` at origin on the ground, no deform. Bone names exactly as listed. Keep bone roll sane
(consistent), no scale keys except where stated (Falsekin unfold may use scale). Clips are in place.
Loop clips: first and last frame identical. 30 fps. Record clip lengths + authored ground speed in the manifest.
Also record in the manifest: overall height, length, eye height, and the world-space rest position of `head`.

---------------------------------------------------------------------------------------------------------
## 1. Hollowback  (`Hollowback.fbx`) — forest hunter, sound-sensitive
Appearance: a rotten monkey grown far too tall and thin. Arms almost reach the ground. Torso bends forward in a
permanent unnatural hunch; the back is swollen into a huge **asymmetrical hump** under patches of damaged skin and
dirty matted fur. Head too small for the body; narrow, partially misaligned jaw with missing teeth and others
protruding at strange angles. One eye clouded (MNF_EyeClouded), the other dark and wet (MNF_EyeWet). Elongated
fingers with damaged nails. Some ribs visible under a decayed torso. Diseased and physically wrong, not a clean
skeleton. Silhouette: hunched hump + long hanging arms + small head that tilts when listening.
Size: standing hunched ~2.4 m tall (top of hump), head at ~2.0 m, arms reach to ~0.15 m above ground.
Materials: MNF_FurRotten (fur patches), MNF_SkinDecayed (exposed skin/ribs/face), MNF_Teeth, MNF_Gums, MNF_Nails,
MNF_EyeWet, MNF_EyeClouded.
Extra bones: `hump` (child of chest), eyes are rigid to head.
Clips (lengths are guides):
* `idle` (loop ~4 s) — almost motionless, slow breathing in the hump, tiny finger twitches.
* `listen` (loop ~3 s) — head tilts to one side slowly, then the other; body frozen.
* `walk` (loop, slow stalking ~0.7 m/s) — long slow strides, arms swing loosely, knuckles brush the ground.
* `follow` (loop ~1.4 m/s) — risen slightly out of the hunch, head forward, deliberate.
* `run` (loop ~5.5 m/s) — aggressive gallop, long arms slap the ground alternately (record the frames where each
  hand hits the ground in the manifest as `events: {"slap": [frames...]}`).
* `alert` (one-shot ~0.8 s) — freezes, then head snaps toward the sound (head turn to its left).
* `inspect` (loop ~3 s) — leans sideways as if peering around a tree trunk.
* `attack` (one-shot ~1.2 s) — short windup (rears up, jaw opens wide), then a long-armed downward swipe;
  record the hit frame in the manifest (`events: {"hit": [frame]}`).
* `stagger` (one-shot ~1.0 s) — recoils after being stabbed.

## 2. Rabbit  (`Rabbit.fbx`) — ordinary huntable wildlife AND the Falsekin disguise
A believable wild rabbit (stylised, ~0.4 m long, 0.25 m tall). Materials: MNF_FurRabbit, MNF_EyeWet, MNF_Flesh (nose
inner ear). Bones: `root` → `hips` → `spine` → `chest` → `neck` → `head` (+ `ear.L`, `ear.R`, `nose`, `eyelid.L`,
`eyelid.R` for blinking), front legs `upperarm.L/R` → `forearm.L/R` → `hand.L/R`, hind legs `thigh.L/R` →
`shin.L/R` → `foot.L/R`.
Clips: `idle` (loop 3 s, breathing, nose twitch, one ear flick), `graze` (loop 2.5 s, head down nibbling),
`hop` (loop, 1 hop ~0.45 s, ~1.6 m/s), `run` (loop, fast bounding ~6 m/s), `alert` (loop 2 s, sits up, ears up),
`blink` (one-shot 0.25 s eyelids only), `death` (one-shot 0.8 s, falls on side).
(The Falsekin disguise reuses this rig in Unity with bone-scale tweaks, a mangy material and "wrong" timing.)

## 3. Falsekin  (`Falsekin.fbx`) — the revealed form of the mimic
At rest it was folded into a rabbit-sized shape. When it reveals itself the jaw opens far beyond what a skull allows:
the skin around the mouth stretches into a **torn vertical opening** exposing rows of small uneven teeth; long
front limbs unfold from beneath the body; the silhouette abruptly changes from harmless animal to a thin, predatory,
hunched quasi-humanoid (~1.3 m tall when risen, ~1.6 m long when lunging). Irregular bald patches reveal dark
stretched skin. Ears remain but bend in opposing wrong directions. Not a "giant rabbit" — it is something that was
never a rabbit.
Materials: MNF_FurRabbitMangy, MNF_SkinDecayed, MNF_Flesh, MNF_Teeth, MNF_EyeWet.
Bones: standard set plus `ear.L`, `ear.R`, and a vertical mouth split: `jaw.L`, `jaw.R` (children of head; rotating
them apart opens the vertical tear; teeth weighted to them).
Clips:
* `folded` (loop 2 s) — compact rabbit-sized crouched ball (bounding box ≈ rabbit: 0.45 m long, 0.3 m tall),
  limbs folded under, mouth closed. Must match the Rabbit's silhouette and scale closely.
* `unfold` (one-shot ~0.9 s) — from `folded` to the risen predatory pose: front limbs unfold, body stretches up,
  vertical mouth tears open. The most important animation of this creature — make it sudden and wrong.
* `idle` (loop 2 s) — risen, swaying, mouth half open.
* `run` (loop, fast low skitter on all fours ~7 m/s).
* `lunge` (one-shot ~0.8 s; hit frame in manifest events).
* `retreat` (loop, low crawl ~3 m/s).
* `death` (one-shot ~1.0 s).

## 4. Ceiling Clerk  (`CeilingClerk.fbx`) — overhead stalker in the mines
A monkey stretched and compressed in the wrong directions: unnaturally narrow torso (~1.5 m long), very long arms
ending in **oversized hands** with long fingers; legs folded tight against the body, used to cling. Dark dusty fur
(MNF_FurDark), almost the colour of mine grime. Face pressed close to the skull, flat brow, mouth held shut by several
thin dark tendons (small cylinders across the mouth); when the mouth opens the lower jaw drops far and stays
suspended. Eyes reflect light as two small points (MNF_EyeGlint).
**Modelled crawling on a horizontal surface, belly toward the surface (−Z), back up (+Z)**. Unity mounts it upside-down
on ceilings by aligning the creature's up axis with the surface normal, so clips must look right in that local frame.
Materials: MNF_FurDark, MNF_SkinDecayed, MNF_Teeth, MNF_Gums, MNF_EyeGlint, MNF_Nails.
Bones: standard set (`jaw` important), fingers per hand as one chain `fingers.L/R`.
Clips: `cling` (loop 3 s, still, flattened against the surface, fingers re-gripping one at a time),
`crawl` (loop, ~1.2 m/s, finger-over-finger, hands release and reconnect in rapid succession — record finger tap
frames as events `tap`), `freeze` (loop 1 s, rigid, head turned toward the viewer), `jaw_open` (one-shot 0.6 s,
lower jaw drops too far and stays), `drop` (one-shot 0.5 s, releases surface and flips, limbs spread),
`grab` (loop 1.5 s, clutching something in front of it at chest height of a standing monkey, jaw open),
`flee` (loop, fast crawl ~3 m/s).

## 5. Borer  (`Borer.fbx`) — tunnelling brute
Massive, low-slung monkey-like creature: broad torso, very thick forelimbs, head shaped by pressure beneath the
earth (flattened, wedge-like). Back covered in hard mineral growths and broken stone (MNF_MineralCrust), several
piercing the flesh with crusted wounds. Oversized forearms with blunt shovel-like hands and thick cracked nails.
Mouth hidden behind a **vertical split beneath the nose** with fleshy vibrating structures inside (bones
`mouth.L`, `mouth.R`). Small recessed eyes. Silhouette: weight, strength, a battering ram.
Size: ~1.5 m tall at the shoulders, ~3.0 m long. Materials: MNF_SkinDecayed, MNF_MineralCrust, MNF_FurDark,
MNF_Nails, MNF_Flesh, MNF_EyeWet.
Clips: `idle` (loop 4 s, heavy breathing, head swaying, sniffing the ground), `sense` (loop 3 s, presses a palm to the
ground, head low — "feeling vibrations"), `walk` (loop ~1.3 m/s), `charge` (loop ~4.5 m/s), `attack` (one-shot ~1.4 s,
rears up then slams both forearms down; hit frame event), `emerge` (one-shot ~2.0 s, starts with the whole body below
ground level — below z=0 — and claws its way up to standing on z=0), `burrow` (one-shot ~2.0 s, reverse: digs
down until below ground), `stagger` (one-shot 1.0 s).

## 6. Lantern Mourner  (`LanternMourner.fbx`) — rare intelligent stalker attracted to light
Tall (~2.7 m), frail, thin torso, very long limbs, shoulders hanging unevenly, head leaning toward one side.
Grey-brown skin stretched tight across the face (MNF_MournerSkin); eyes covered by dark swollen tissue leaving only
narrow wet slits (MNF_EyeWet). The chest contains a **hollow cavity** surrounded by cracked bone-like structures
(MNF_Teeth works as bone) with a dim sickly light inside (MNF_MournerGlow surface inside the cavity; add an empty
bone `socket_chestlight` at the cavity centre, child of `chest`, for a Unity point light). It carries/drags a cluster
of broken mining lamps, wires and metal fragments hanging from its right hand (separate meshes parented to a bone
`lamps`, child of `hand.R`; lamp glass MNF_Glass, metal MNF_MetalRusted, a bulb MNF_BulbWarm that Unity dims).
Clips: `idle` (loop 4 s, swaying, lamps swinging slightly), `walk` (loop, slow ~0.9 m/s, dragging feel),
`retreat` (loop, walking backwards ~1.2 m/s while facing forward), `turn_head` (one-shot 1.5 s, head rolls toward
the light source on its left), `reach` (one-shot ~1.6 s, slow embrace/reach attack with both long arms; hit event),
`recoil` (one-shot 1.0 s, flinches away and covers the cavity).

## 7. The Gaunt  (`Gaunt.fbx`) — enormous deep-mine background entity (not fought)
A colossal emaciated monkey-shaped figure (~14 m tall) glimpsed far below in the deep chasm. Extremely thin limbs,
very long fingers, head bowed. Low detail is fine (≤ 4k tris) — it is seen through fog at distance. Materials:
MNF_SkinDecayed, MNF_FurDark, MNF_EyeGlint. Clips: `walk` (loop, very slow ~1.0 m/s, heavy), `stand` (loop 6 s,
head slowly turns), `look_up` (one-shot 4 s, slowly raises its head toward the viewer high above).

## 8. Boar  (`Boar.fbx`) — larger forest animal, harder to approach (huntable)
Dark bristly wild boar (~1.1 m long, 0.7 m at shoulder), small tusks. Materials: MNF_FurBoar, MNF_Teeth, MNF_EyeWet,
MNF_Flesh. Bones: standard quadruped mapping (front legs use the arm chain names, hind legs leg chain names),
`ear.L/R`. Clips: `idle`, `graze`, `walk` (~1.0 m/s), `run` (~6.5 m/s), `alert`, `charge` (~7 m/s), `death`.

## 9. Gloomrat  (`Gloomrat.fbx`) — small burrow creature (mines & forest burrows), flees
Small pale-eyed rat-like rodent (~0.25 m). Materials: MNF_FurDark, MNF_EyeGlint, MNF_Flesh. Clips: `idle`, `run`
(~4 m/s), `peek` (one-shot: rises out of a hole and sniffs), `hide` (one-shot: ducks down).

## Manifest format
```json
{
 "Hollowback": {
   "file": "Hollowback.fbx", "height": 2.4, "length": 1.1, "eye_height": 2.0, "tris": 7400,
   "materials": ["MNF_FurRotten", "..."], "bones": ["root","hips","..."],
   "clips": {"walk": {"length": 1.6, "loop": true, "speed": 0.7, "events": {}}, "attack": {"length":1.2,"loop":false,"events":{"hit":[22]}}}
 }
}
```
