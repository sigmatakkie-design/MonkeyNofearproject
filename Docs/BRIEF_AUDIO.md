# Audio Synthesis Brief

Read `Docs/ASSET_SPEC.md` §0, §4. There are no recorded sound assets available, so every sound is **synthesised
procedurally in Python** (numpy/scipy; soundfile writes OGG Vorbis). Scripts in `Tools/audio/` (deterministic seeds,
re-runnable: `python Tools/audio/build_audio.py`). Output `Assets/MonkeyNoFear/Audio/<Category>/<name>[_NN].ogg`
+ manifest `Assets/MonkeyNoFear/Audio/audio_manifest.json`.

Sound is the most important horror system in this game. Aim for organic, believable results, not beeps:
use layered filtered noise, physical-modelling tricks (modal synthesis for metal/wood/stone impacts: sums of decaying
damped sinusoids with inharmonic partials; Karplus-Strong for scrapes and plucks; granular textures for crumbling
rock, leaves and fur; formant filtering (vocal-tract resonances) on noise/pulse trains for creature breaths, growls and
vocalisations; convolution with synthetic impulse responses for room/cave reverb tails; pitch envelopes; slow
LFOs; distortion/saturation for aggression). Normalise sensibly (peak ≈ −1 dBFS for impacts, ambience beds
quieter: RMS ≈ −24 dBFS) and fade edges to avoid clicks. Loops must be seamless (crossfade the end into the start).
Positional sounds: mono, dry or with only a very short early reflection (Unity adds 3D spatialisation and
reverb zones). Ambience beds: stereo. Provide 2–4 variants where `xN` is given.

Write a small reusable DSP toolkit module (`Tools/audio/mnf_dsp.py`: noise colours, biquad filters, envelopes,
modal impacts, formant filter, granular, reverb, saturator, crossfade-loop) and one file per category.
Verify outputs: durations, no clipping, no NaN, loops seamless (check the sample discontinuity at the wrap), plus a
spectrogram contact sheet PNG in `Docs/previews/audio/` that you inspect.

Durations are guidance. `loop` = seamless loop.

## Player  (`Player/`)
hand_tap_ground x4 (soft dirt thump 0.25 s) · hand_tap_wood x3 (hollow knock) · hand_tap_metal x4 (ringing clank) ·
hand_tap_rock x3 (dull click/thud with grit) · hand_tap_foliage x3 (leafy rustle) · hand_tap_mud x2 (wet squelch) ·
land_thud x2 (body landing) · hurt_grunt x3 (short pained monkey vocal "hoo/ack", formant based) ·
heartbeat_loop (double-beat, ~70 bpm, 4 s) · breath_panic_loop (fast shaky breathing 4 s) · death_sting (0.0 → dark
impact + falling tone 3 s) · eat_munch x2 · backpack_store (zip/rustle) · backpack_take · holster_snap · grab x2
(soft hand on object) · whoosh x3 (fast arm/tool swing) · body_scrape (sliding along rock 1 s)

## Tools  (`Tools/`)
pick_hit_rock x4 (sharp stone crack, chips) · pick_hit_iron x3 (metallic ring + stone) · pick_hit_copper x3
(softer metallic) · pick_hit_crystal x3 (glassy, chiming, slightly wrong resonance) · pick_hit_blackstone x3 (dead,
dull, swallowed — almost no ring) · pick_hit_anomalous x3 (wet, organic, with a low unnatural tone) · pick_miss_metal
x2 (glancing scrape) · ore_break x3 (deposit stage crumble 0.8 s) · ore_break_final x2 (bigger collapse 1.5 s) ·
ore_pickup x3 (stone clink) · flashlight_on · flashlight_off · flashlight_flicker_loop (electrical buzz/crackle 2 s) ·
battery_low (weak beep) · spear_stab_flesh x3 · spear_hit_hard x2 · spear_hit_wood x2 · glowstick_crack ·
flare_ignite · flare_burn_loop (hissing crackle 3 s) · noisemaker_rattle x3 (loud tin can of bolts) · scanner_beep ·
scanner_beep_strong · rope_unroll (2 s) · medkit_use (latch + bandage rustle 1.5 s) · marker_deploy (thunk + beep) ·
marker_blip · item_drop_metal x3 · item_drop_wood x2 · item_drop_soft x2 · item_drop_stone x3

## Bunker  (`Bunker/`)
amb_bunker_bed (stereo loop 20 s: ventilation rumble, distant machinery, faint electrical tone) ·
vent_loop (mono 6 s) · fluorescent_hum_loop (mains-hum 50/100 Hz + buzz, 4 s) · fluorescent_flicker x3 (tick-buzz)
· spark x3 (electrical snap with crackle tail) · generator_loop (diesel thrum 4 s) · gate_motor_loop (heavy electric
motor + chain rattle 3 s) · gate_start (relay clunk + motor spin-up 1.5 s) · gate_stop (heavy metal clank
reverberant 2 s) · gate_alarm (two-tone warning beep 1 s, loopable) · button_press (chunky click) · button_release ·
lever_pull (ratchet + clunk) · terminal_boot (CRT whine + beeps 2 s) · terminal_select (soft key beep) ·
terminal_confirm (two-note) · terminal_error (low buzz) · terminal_type x3 (key clicks) · purchase (mechanical
cash register "ka-chunk" + bell 1 s) · sell_vacuum (pneumatic suction whoosh 1.5 s) · coin_tick (counter tick) ·
dispenser_thunk (pneumatic tube arrival) · radio_static_loop (4 s) · radio_burst x3 (interference with garbled
voice-like formant babble, 2–3 s, unsettling) · distant_impact x3 (deep structural boom from far away, 3 s) ·
structural_creak x3 (metal stress groan 2 s) · pipe_knock x3 (knocking inside pipes) · water_drip_bunker x3

## Forest  (`Forest/`)
amb_forest_bed (stereo loop 30 s: wind through branches, very sparse distant life) · amb_forest_insects_loop
(stereo 15 s, crickets/insects — this layer is muted near threats) · frogs_loop (mono 8 s) · wind_gust x3 (3–4 s) ·
branch_snap x4 (distant twig/branch cracks) · tree_creak x3 (wooden trunk groan 2–3 s) · leaves_rustle x3 ·
distant_call x4 (unidentifiable animal call far away: owl-like, fox-like, then one that sounds slightly wrong) ·
bird_flutter x2 · footsteps_foliage x4 (something heavy stepping in undergrowth) · stream_loop (mono 6 s) ·
crow_caw x2

## Creatures  (`Creatures/`)
Hollowback: hb_breath_loop (slow wet rattling breaths 6 s) · hb_scrape x3 (long nails dragged down bark 1.5 s) ·
hb_step x4 (heavy soft footfall) · hb_slap x4 (palm slapping the ground while galloping — distinctive) ·
hb_alert (sharp wet intake + teeth click 0.6 s) · hb_listen_click x2 (quiet clicking while listening) ·
hb_warning (low gurgling growl rising 1.5 s) · hb_attack x2 (lunge vocal, NOT a generic scream: ragged, choking roar
1 s) · hb_hurt x2 · hb_chase_loop (fast ragged panting 3 s)
Rabbit: rabbit_sniff x2 · rabbit_hop x3 (soft thumps) · rabbit_squeal x2 (hurt) · rabbit_thump (warning foot thump)
Falsekin: fk_mimic x2 (rabbit-ish sniff/chitter that goes subtly wrong — slowed, detuned) · fk_reveal (stretching,
tearing, wet cracking + rising screech 1.2 s — the key sound) · fk_skitter_loop (very fast clicky footsteps 2 s) ·
fk_shriek x2 · fk_hiss x2 · fk_death
Boar: boar_grunt x3 · boar_squeal x2 · boar_charge (snorting rush)
Gloomrat: rat_squeak x3 · rat_scurry x2
Ceiling Clerk: clerk_tap x6 (single finger tap on wood/stone, tiny) · clerk_skitter x2 (rapid tapping sequence 1 s) ·
clerk_click_loop (soft jaw clicking 2 s) · clerk_jaw_drop (wet click + creak) · clerk_drop (body thud) ·
clerk_screech (grab vocal 1.2 s) · clerk_hiss x2 · clerk_hurt
Borer: borer_impact_deep x3 (huge low thump from beneath the floor, sub-bass + debris 2.5 s) · borer_impact_close x2
(louder, closer, more debris) · borer_grind_loop (deep vibrating grinding vocal 3 s) · borer_emerge (rock bursting,
rubble cascade 2.5 s) · borer_roar x2 (grinding roar 2 s) · borer_step x3 (very heavy) · borer_dig_loop (2 s) ·
dust_fall x3 (sprinkle of grit) · borer_hurt
Lantern Mourner: mourner_hum_loop (eerie breathy hum, pitch slowly wavering 6 s) · mourner_clink x4 (broken lamps
and metal fragments clinking) · mourner_wail x2 (very distant, sad, 4 s) · mourner_buzz_loop (electrical interference
2 s) · mourner_reach (hum rising into a thin shriek 1.6 s) · mourner_recoil
Gaunt: gaunt_step x2 (enormous distant footfall with long reverb) · gaunt_groan (huge distant groan 6 s)

## Mine  (`Mine/`)
amb_mine_bed (stereo loop 30 s: low rumble, distant drips, air movement) · amb_mine_deep_bed (stereo loop 30 s:
darker, sub-bass pressure, faint metallic stress) · drip x6 · water_trickle_loop (mono 5 s) · rock_fall_small x3 ·
rock_fall_large x2 · metal_impact_distant x3 (a metallic bang far away) · metal_impact_repeat (three identical
bangs, each farther away 4 s) · minecart_roll (short roll with wheel squeal 2.5 s) · electrical_buzz_loop (2 s) ·
machinery_hum_loop (4 s) · footsteps_echo x3 (phantom footsteps in a tunnel, reverberant 2 s) · walkway_steps x2
(footsteps on metal grating) · warning_recording x2 (old PA announcement: tone chime followed by a heavily
band-limited, distorted robotic formant "voice" babble that **cuts off abruptly mid-word**; 3–4 s) · elevator_motor_loop
(3 s) · elevator_clank x2 · elevator_arrive (bell + clank) · scratch_metal x3 (claws scraping the other side of a
metal plate 2 s) · wall_knock x2 · light_buzz_on (filament surge) · whisper_air x2 (breathy air movement that could be
a voice)

## Stingers & tension  (`Music/`)
sting_dread (stereo low swell 5 s) · sting_reveal (stereo dissonant hit 2.5 s — used rarely) · sting_safe (stereo
soft warm chord when returning to the bunker 4 s) · tension_drone_loop (stereo 12 s, low pulsing drone used during
chases) · sting_purchase (bright short 1 s) · sting_lore (mysterious 3 s)
