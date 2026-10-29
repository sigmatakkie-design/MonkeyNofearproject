using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>
    /// Creates the data assets (ScriptableObjects) the game is balanced with. Everything here is plain
    /// Inspector data afterwards: re-running the builder only fills in assets that do not exist yet,
    /// unless "overwrite" is passed, so hand-tuned values survive.
    /// </summary>
    public static class DataFactory
    {
        public const string Items = MNFPaths.Data + "/Items";
        public const string Minerals = MNFPaths.Data + "/Minerals";
        public const string Creatures = MNFPaths.Data + "/Creatures";
        public const string Atmos = MNFPaths.Data + "/Atmosphere";

        static bool _overwrite;

        public static void BuildAll(bool overwrite)
        {
            _overwrite = overwrite;
            MNFPaths.Ensure(Items); MNFPaths.Ensure(Minerals); MNFPaths.Ensure(Creatures); MNFPaths.Ensure(Atmos);
            var db = MNFPaths.CreateOrReplace<ItemDatabase>(MNFPaths.Data + "/ItemDatabase.asset");
            BuildItems(db);
            BuildMinerals(db);
            BuildTools(db);
            BuildShop();
            BuildCreatureProfiles();
            BuildAtmospheres();
            BuildLore();
            EditorUtility.SetDirty(db);
            AssetDatabase.SaveAssets();
            Debug.Log($"[MNF] Data: {db.items.Count} items, {db.minerals.Count} minerals, {db.tools.Count} tools");
        }

        static T Asset<T>(string path, out bool fresh) where T : ScriptableObject
        {
            var a = AssetDatabase.LoadAssetAtPath<T>(path);
            fresh = a == null || _overwrite;
            if (!a) { a = ScriptableObject.CreateInstance<T>(); AssetDatabase.CreateAsset(a, path); }
            return a;
        }

        // ------------------------------------------------------------------ items
        static ItemDefinition Item(ItemDatabase db, string id, string name, ItemCategory cat, int value, float mass, Color col,
            int rarity = 0, SurfaceKind surf = SurfaceKind.Rock, bool sellable = true, bool storable = true, float vigor = 0f, float heal = 0f, string desc = "")
        {
            var d = Asset<ItemDefinition>($"{Items}/Item_{id}.asset", out bool fresh);
            if (fresh)
            {
                d.id = id; d.displayName = name; d.category = cat; d.sellValue = value; d.mass = mass;
                d.terminalColor = col; d.rarity = rarity; d.dropSurface = surf; d.sellable = sellable; d.storable = storable;
                d.foodVigor = vigor; d.foodHeal = heal; d.description = desc;
            }
            EditorUtility.SetDirty(d);
            if (!db.items.Contains(d)) db.items.Add(d);
            return d;
        }

        static void BuildItems(ItemDatabase db)
        {
            db.items.RemoveAll(i => !i);
            Item(db, "ore_iron", "Iron Ore", ItemCategory.Mineral, 8, 1.2f, new Color(0.68f, 0.68f, 0.72f), 0, SurfaceKind.Rock, desc: "Dark iron-bearing ore. Common near the mine entrance.");
            Item(db, "ore_copper", "Copper Ore", ItemCategory.Mineral, 18, 1.0f, new Color(0.95f, 0.55f, 0.3f), 1, desc: "Reddish-orange veins. Worth hauling back.");
            Item(db, "ore_crystal", "Luminous Crystal", ItemCategory.Mineral, 45, 0.6f, new Color(0.5f, 0.92f, 1f), 2, SurfaceKind.Crystal, desc: "Glows faintly from inside. Found deeper underground.");
            Item(db, "ore_blackstone", "Blackstone", ItemCategory.Mineral, 110, 1.6f, new Color(0.66f, 0.55f, 0.85f), 3, desc: "Dense, almost light-absorbing. Needs a tempered pick.");
            Item(db, "ore_anomalous", "Anomalous Core", ItemCategory.Mineral, 400, 1.0f, new Color(1f, 0.32f, 0.25f), 4, SurfaceKind.Flesh, desc: "Warm. Heavier than it should be. It hums.");
            Item(db, "rabbit_meat", "Rabbit Meat", ItemCategory.Food, 6, 0.4f, new Color(0.9f, 0.6f, 0.55f), 0, SurfaceKind.Flesh, vigor: 0.25f, heal: 10f, desc: "Hold it to your mouth to eat.");
            Item(db, "boar_meat", "Boar Meat", ItemCategory.Food, 15, 0.9f, new Color(0.85f, 0.45f, 0.4f), 1, SurfaceKind.Flesh, vigor: 0.5f, heal: 20f, desc: "A proper meal.");
            Item(db, "food_can", "Canned Ration", ItemCategory.Food, 3, 0.4f, new Color(0.8f, 0.8f, 0.7f), 0, SurfaceKind.Metal, vigor: 0.35f, heal: 5f, desc: "Bunker 7 standard issue. Tastes of tin.");
            Item(db, "falsekin_gland", "Falsekin Gland", ItemCategory.Valuable, 90, 0.3f, new Color(1f, 0.4f, 0.6f), 3, SurfaceKind.Flesh, desc: "Still pulsing. Someone will pay for it.");
            Item(db, "miner_tag", "Miner's Tag", ItemCategory.Valuable, 12, 0.05f, new Color(0.8f, 0.8f, 0.8f), 1, SurfaceKind.Metal, desc: "A dog tag from one of the missing miners.");
            Item(db, "glowstick", "Glowstick", ItemCategory.Consumable, 2, 0.08f, new Color(0.4f, 1f, 0.5f), 0, SurfaceKind.Foliage, desc: "Crack with the trigger. Marks a route for ten minutes.");
            Item(db, "flare", "Emergency Flare", ItemCategory.Consumable, 5, 0.2f, new Color(1f, 0.4f, 0.3f), 0, SurfaceKind.Foliage, desc: "Trigger to strike. Bright, loud light for 90 s. Throw it as a decoy.");
            Item(db, "noisemaker", "Rattle Can", ItemCategory.Consumable, 3, 0.35f, new Color(0.8f, 0.8f, 0.6f), 0, SurfaceKind.Metal, desc: "Throw it: sound hunters investigate the noise.");
            Item(db, "medkit", "First-Aid Tin", ItemCategory.Consumable, 10, 0.4f, new Color(1f, 0.5f, 0.5f), 0, SurfaceKind.Metal, desc: "Hold the trigger to heal.");
            Item(db, "battery", "Battery Pack", ItemCategory.Consumable, 6, 0.3f, new Color(0.9f, 0.9f, 0.4f), 0, SurfaceKind.Metal, desc: "Hold the trigger: recharges every light you carry.");
            Item(db, "rope_coil", "Climbing Rope", ItemCategory.Consumable, 8, 1.0f, new Color(0.8f, 0.7f, 0.5f), 0, SurfaceKind.Foliage, desc: "Trigger over a drop: hangs an 18 m climbable rope.");
            Item(db, "marker_beacon", "Marker Beacon", ItemCategory.Consumable, 5, 0.4f, new Color(1f, 0.3f, 0.2f), 0, SurfaceKind.Metal, desc: "Arm with the trigger, then drop. Blinks and blips so you can find your way back.");
            Item(db, "lore_tape", "Recovered Tape", ItemCategory.Lore, 0, 0.1f, new Color(1f, 0.9f, 0.6f), 0, SurfaceKind.Metal, sellable: false, desc: "Someone recorded this down here.");
            Item(db, "lore_note", "Recovered Note", ItemCategory.Lore, 0, 0.05f, new Color(1f, 0.9f, 0.6f), 0, SurfaceKind.Foliage, sellable: false, desc: "A page left behind.");
            // permanent tools (not sellable, never in the stash)
            Item(db, "pickaxe_t1", "Rusty Pick", ItemCategory.Tool, 0, 1.6f, Color.white, 0, SurfaceKind.Metal, false, false, desc: "Tier 1. Iron, copper, crystal.");
            Item(db, "pickaxe_t2", "Tempered Pick", ItemCategory.Tool, 0, 1.8f, Color.white, 1, SurfaceKind.Metal, false, false, desc: "Tier 2. Mines faster; breaks Blackstone.");
            Item(db, "pickaxe_t3", "Resonance Pick", ItemCategory.Tool, 0, 1.9f, Color.white, 2, SurfaceKind.Metal, false, false, desc: "Tier 3. Quiet strikes; the only pick that opens an Anomalous core.");
            Item(db, "spear", "Spear", ItemCategory.Tool, 0, 1.4f, Color.white, 0, SurfaceKind.Wood, false, false, desc: "Stab or throw. Hunts animals; buys time against worse things.");
            Item(db, "flashlight", "Flashlight", ItemCategory.Tool, 0, 0.6f, Color.white, 0, SurfaceKind.Metal, false, false, desc: "Trigger: on/off. Primary: wide/focused beam. Recharges in the bunker.");
            Item(db, "headlamp", "Headlamp", ItemCategory.Tool, 0, 0.3f, Color.white, 1, SurfaceKind.Metal, false, false, desc: "Wear it: release it at your forehead. X toggles it.");
            Item(db, "scanner", "Ore Scanner", ItemCategory.Tool, 0, 0.5f, Color.white, 1, SurfaceKind.Metal, false, false, desc: "Beeps faster near deposits. Primary: rare minerals only.");
        }

        static void BuildMinerals(ItemDatabase db)
        {
            db.minerals.RemoveAll(m => !m);
            Mineral(db, "iron", "Iron", "ore_iron", 60, 1, 2, 3, 0.5f, "pick_hit_iron", new Color(0.35f, 0.33f, 0.32f), Color.black, 0f, 65, 25, 5, 0);
            Mineral(db, "copper", "Copper", "ore_copper", 80, 1, 2, 4, 0.5f, "pick_hit_copper", new Color(0.6f, 0.35f, 0.2f), Color.black, 0f, 35, 45, 15, 0);
            Mineral(db, "crystal", "Luminous Crystal", "ore_crystal", 100, 1, 2, 3, 0.65f, "pick_hit_crystal", new Color(0.5f, 0.85f, 1f), new Color(0.4f, 0.85f, 1f), 0.9f, 0, 30, 45, 0);
            Mineral(db, "blackstone", "Blackstone", "ore_blackstone", 160, 2, 2, 3, 0.4f, "pick_hit_blackstone", new Color(0.08f, 0.07f, 0.1f), Color.black, 0f, 0, 0, 35, 0);
            Mineral(db, "anomalous", "Anomalous Core", "ore_anomalous", 220, 3, 1, 2, 0.9f, "pick_hit_anomalous", new Color(0.5f, 0.1f, 0.08f), new Color(1f, 0.25f, 0.15f), 1.1f, 0, 0, 3, 100);
        }

        static void Mineral(ItemDatabase db, string id, string name, string item, float durability, int tier, int dmin, int dmax, float noise,
            string hit, Color particle, Color glow, float glowI, float ws, float wm, float wd, float wa)
        {
            var m = Asset<MineralDefinition>($"{Minerals}/Mineral_{id}.asset", out bool fresh);
            if (fresh)
            {
                m.id = id; m.displayName = name; m.durability = durability; m.requiredTier = tier; m.dropCount = new Vector2Int(dmin, dmax);
                m.strikeNoise = noise; m.hitSound = hit; m.breakSound = "ore_break"; m.finalBreakSound = "ore_break_final";
                m.particleColor = particle; m.glowColor = glow; m.glowIntensity = glowI;
                m.weightShallow = ws; m.weightMid = wm; m.weightDeep = wd; m.weightAnomalous = wa;
            }
            m.chunkItem = db.GetItem(item) ?? AssetDatabase.LoadAssetAtPath<ItemDefinition>($"{Items}/Item_{item}.asset");
            EditorUtility.SetDirty(m);
            if (!db.minerals.Contains(m)) db.minerals.Add(m);
        }

        static void BuildTools(ItemDatabase db)
        {
            db.tools.Clear();
            string[] ids = { "pickaxe_t1", "flashlight", "spear", "pickaxe_t2", "scanner", "headlamp", "pickaxe_t3" };
            for (int i = 0; i < ids.Length; i++)
                db.tools.Add(new ToolEntry { id = ids[i], item = AssetDatabase.LoadAssetAtPath<ItemDefinition>($"{Items}/Item_{ids[i]}.asset"), rackSlot = i % 6 });
            db.startingTools = new List<string> { "pickaxe_t1", "flashlight" };
            db.startingCurrency = 25;
        }

        // ------------------------------------------------------------------ shop
        static void BuildShop()
        {
            var cat = Asset<ShopCatalog>(MNFPaths.Data + "/ShopCatalog.asset", out bool fresh);
            if (fresh)
            {
                cat.entries = new List<ShopEntry>
                {
                    E("spear", "Spear", ShopEntryKind.Tool, 40, "spear", "Stab or throw. One clean hit brings down a rabbit. Monsters only flinch."),
                    E("glowsticks", "Glowsticks", ShopEntryKind.Consumable, 15, "glowstick", "Mark your route home. Quiet and dim.", 3, 0),
                    E("flare", "Emergency Flare", ShopEntryKind.Consumable, 25, "flare", "Huge red light for 90 s. Keeps ceiling things off. Draws other things in.", 1, 0),
                    E("noisemaker", "Rattle Can", ShopEntryKind.Consumable, 20, "noisemaker", "Throw it away from you. Hunters that listen will follow the noise.", 1, 0),
                    E("ration", "Canned Rations", ShopEntryKind.Consumable, 20, "food_can", "Restores vigor. Hold to your mouth.", 2, 0),
                    E("medkit", "First-Aid Tin", ShopEntryKind.Consumable, 45, "medkit", "Hold the trigger to heal 50.", 1, 0),
                    E("battery", "Battery Pack", ShopEntryKind.Consumable, 25, "battery", "Full recharge for every light you carry.", 1, 0),
                    E("marker", "Marker Beacon", ShopEntryKind.Consumable, 30, "marker_beacon", "Blinking, blipping waypoint. Follow the sound back.", 1, 0),
                    E("rope", "Climbing Rope", ShopEntryKind.Consumable, 60, "rope_coil", "Hang an 18 m rope over a shaft. Climb down — and back up.", 1, 0),
                    E("scanner", "Ore Scanner", ShopEntryKind.Tool, 120, "scanner", "Beeps faster near deposits. Shows mineral and distance."),
                    E("battery_up", "Extended Cells", ShopEntryKind.Upgrade, 150, "battery_1", "Doubles flashlight and headlamp battery life."),
                    E("headlamp", "Headlamp", ShopEntryKind.Tool, 180, "headlamp", "Hands-free light. Wear it on your forehead."),
                    E("pack1", "Bigger Backpack", ShopEntryKind.Upgrade, 180, "backpack_1", "+4 backpack slots (10)."),
                    E("armor", "Padded Vest", ShopEntryKind.Upgrade, 260, "armor_1", "Takes 30% off every hit. Does not help with falls."),
                    E("pick2", "Tempered Pick", ShopEntryKind.Tool, 300, "pickaxe_t2", "Tier 2: mines faster and breaks Blackstone."),
                    E("pack2", "Expedition Pack", ShopEntryKind.Upgrade, 420, "backpack_2", "+6 more slots (16).", requires: "backpack_1", label: "BIGGER BACKPACK"),
                    E("pick3", "Resonance Pick", ShopEntryKind.Tool, 900, "pickaxe_t3", "Tier 3: quiet strikes. Opens Anomalous cores.", requires: "pickaxe_t2", label: "TEMPERED PICK"),
                };
            }
            EditorUtility.SetDirty(cat);
        }

        static ShopEntry E(string id, string name, ShopEntryKind kind, int price, string grant, string desc, int qty = 1, int max = 1, string requires = null, string label = null)
            => new ShopEntry { id = id, displayName = name, kind = kind, price = price, grantId = grant, description = desc, quantity = qty, maxPurchases = max, requires = requires, requiresLabel = label };

        // ------------------------------------------------------------------ creatures
        public static CreatureProfile Profile(string id) => AssetDatabase.LoadAssetAtPath<CreatureProfile>($"{Creatures}/Creature_{id}.asset");

        static void BuildCreatureProfiles()
        {
            P("hollowback", "Hollowback", false, 300, 30, 0.7f, 1.5f, 5.2f, 160, 1.25f, 26, 120, 2.5f, 2.6f, 40, 3f, 1.6f, 110,
              "A rotten monkey grown far too tall. It hunts by sound. If you hear scraping in the trees, stop moving. It cannot climb.");
            P("falsekin", "Falsekin", true, 60, 20, 0.6f, 2f, 7f, 720, 1f, 25, 300, 2f, 1.5f, 28, 4f, 1f, 70,
              "It wears a rabbit. Watch for one that does not blink, does not run, and never looks away.");
            P("rabbit", "Rabbit", true, 15, 5, 1.2f, 2f, 6f, 600, 1.2f, 22, 300, 3f, 0.5f, 0, 5f, 1f, 60, "Food. Approach slowly and quietly.");
            P("boar", "Boar", true, 60, 25, 1.0f, 2f, 6.5f, 300, 1.1f, 24, 240, 3f, 1.6f, 18, 4f, 1f, 70, "Bigger meal. Bites back when cornered.");
            P("gloomrat", "Gloomrat", true, 8, 5, 1f, 2f, 4f, 600, 1.3f, 14, 300, 2f, 0.4f, 0, 5f, 1f, 45, "Pale-eyed burrower. Harmless. Probably.");
            P("ceilingclerk", "Ceiling Clerk", false, 150, 999, 1.3f, 2f, 3.2f, 360, 0.8f, 20, 160, 2f, 1.3f, 9, 30f, 2f, 45,
              "It counts from above. Listen for tapping. Light freezes it — but not forever.");
            P("borer", "Borer", false, 400, 25, 1.3f, 2f, 4.5f, 120, 1.4f, 5, 120, 4f, 2.8f, 65, 3.5f, 2f, 90,
              "Mining wakes it. Two impacts from below are your warning. Stand still: it feels movement, not sight.");
            P("lanternmourner", "Lantern Mourner", false, 999, 999, 0.9f, 1f, 3.6f, 120, 0.6f, 40, 140, 3f, 4f, 45, 6f, 2f, 80,
              "Do not follow the light. It is drawn to yours — turn it off and it loses interest.");
        }

        static void P(string id, string name, bool killable, float hp, float stagger, float walk, float alert, float run, float turn,
            float hearing, float sight, float fov, float prox, float range, float dmg, float cooldown, float recovery, float activation, string bestiary)
        {
            var p = Asset<CreatureProfile>($"{Creatures}/Creature_{id}.asset", out bool fresh);
            if (fresh)
            {
                p.id = id; p.displayName = name; p.killable = killable; p.maxHealth = hp; p.staggerThreshold = stagger;
                p.walkSpeed = walk; p.alertSpeed = alert; p.runSpeed = run; p.turnSpeed = turn; p.acceleration = 10f;
                p.hearingSensitivity = hearing; p.sightRange = sight; p.sightFov = fov; p.proximitySense = prox;
                p.attackRange = range; p.attackDamage = dmg; p.attackCooldown = cooldown; p.postHitRecovery = recovery;
                p.activationDistance = activation; p.bestiaryEntry = bestiary;
            }
            EditorUtility.SetDirty(p);
        }

        // ------------------------------------------------------------------ atmosphere
        public static AtmosphereProfile Atmosphere(AreaId a) => AssetDatabase.LoadAssetAtPath<AtmosphereProfile>($"{Atmos}/Atmosphere_{a}.asset");

        static void BuildAtmospheres()
        {
            // Art direction: readable colour (teal forest fog, teal-to-violet mine), a bright clean safe bunker and
            // fog that leaves landmarks usable (forest: ~60 m to 8 % visibility). Darkness comes from lights, not fog.
            A(AreaId.Bunker, "Bunker 7", 0, new Color(0.6f, 0.64f, 0.68f), 0.006f, new Color(0.62f, 0.64f, 0.68f), new Color(0.42f, 0.43f, 0.45f), new Color(0.22f, 0.22f, 0.23f), 0f, 60f,
              new[] { "amb_bunker_bed" }, new string[0], AudioReverbPreset.Room, 0f, true);
            A(AreaId.Corridor, "Exit Corridor", 0, new Color(0.25f, 0.27f, 0.29f), 0.012f, new Color(0.36f, 0.37f, 0.4f), new Color(0.24f, 0.24f, 0.26f), new Color(0.12f, 0.12f, 0.13f), 0f, 70f,
              new[] { "amb_bunker_bed" }, new string[0], AudioReverbPreset.Hallway, 0f, true);
            A(AreaId.Forest, "Haunted Forest", 0, new Color(0.21f, 0.33f, 0.32f), 0.026f, new Color(0.3f, 0.42f, 0.42f), new Color(0.2f, 0.28f, 0.27f), new Color(0.1f, 0.12f, 0.1f), 1f, 110f,
              new[] { "amb_forest_bed" }, new[] { "amb_forest_insects_loop" }, AudioReverbPreset.Forest, 1f, false);
            A(AreaId.MineShallow, "Mine - Level 1", 1, new Color(0.05f, 0.1f, 0.1f), 0.03f, new Color(0.2f, 0.32f, 0.32f), new Color(0.13f, 0.2f, 0.2f), new Color(0.06f, 0.09f, 0.09f), 0f, 75f,
              new[] { "amb_mine_bed" }, new string[0], AudioReverbPreset.Cave, 1.1f, false);
            A(AreaId.MineMid, "Mine - Level 2", 2, new Color(0.04f, 0.08f, 0.085f), 0.034f, new Color(0.15f, 0.25f, 0.26f), new Color(0.1f, 0.15f, 0.16f), new Color(0.05f, 0.06f, 0.06f), 0f, 70f,
              new[] { "amb_mine_bed" }, new string[0], AudioReverbPreset.Cave, 1.2f, false);
            A(AreaId.MineDeep, "Mine - Level 3", 3, new Color(0.05f, 0.05f, 0.08f), 0.038f, new Color(0.1f, 0.12f, 0.18f), new Color(0.06f, 0.07f, 0.1f), new Color(0.03f, 0.03f, 0.04f), 0f, 70f,
              new[] { "amb_mine_deep_bed" }, new string[0], AudioReverbPreset.Cave, 1.35f, false);
        }

        // fog densities of the first-pass profiles: an asset still carrying one of these was never hand-tuned
        static readonly float[] LegacyFogDensities = { 0.012f, 0.02f, 0.055f, 0.035f, 0.04f, 0.045f };

        static void A(AreaId id, string name, int depth, Color fog, float density, Color sky, Color eq, Color ground, float moon, float far,
            string[] beds, string[] life, AudioReverbPreset reverb, float drain, bool safe)
        {
            var p = Asset<AtmosphereProfile>($"{Atmos}/Atmosphere_{id}.asset", out bool fresh);
            bool legacy = !fresh && System.Array.IndexOf(LegacyFogDensities, p.fogDensity) >= 0 && p.fogColor.r < 0.1f;
            if (fresh || legacy)
            {
                p.area = id; p.displayName = name; p.depthLevel = depth; p.fogColor = fog; p.fogDensity = density;
                p.ambientSky = sky; p.ambientEquator = eq; p.ambientGround = ground; p.moonIntensity = moon; p.farClip = far;
                p.ambienceBeds = beds; p.lifeLayers = life; p.reverb = reverb; p.vigorDrainMultiplier = drain; p.isSafeZone = safe;
            }
            EditorUtility.SetDirty(p);
        }

        // ------------------------------------------------------------------ lore
        static void BuildLore()
        {
            var db = Asset<LoreDatabase>(MNFPaths.Data + "/LoreDatabase.asset", out bool fresh);
            if (!fresh && db.entries.Count > 0) return;
            db.entries = new List<LoreEntry>
            {
                L("lore_welcome", "Bunker 7 - Occupancy Notice", "Note",
                  "GREYROCK MINING CO. SURVIVOR SHELTER 7. In the event of an incident, remain inside. Keep the security gate CLOSED. Rations are for registered employees and families only. Do not open the gate for anyone you cannot see clearly."),
                L("lore_quota", "Shift Memo #44", "Note",
                  "Level 3 crews: the core-sample quota is doubled effective immediately. Bonus for every intact sample brought to the assay room. Reports of 'warmth' from the samples are noted and are NOT a reason to stop work. - Management"),
                L("lore_knocking", "Diary, Page 12", "Note",
                  "Knocking under the floor of Level 2 again tonight. Three knocks, a pause, three knocks. Ollie knocked back with his pick, as a joke. It answered. It was closer."),
                L("lore_tally", "Tally Sheet", "Note",
                  "Head count, night shift: 31. The clerk's marks keep going past the bottom of the page and onto the back. 31. 31. 31. 32. 33. They are still counting us. Nobody new came down."),
                L("lore_rabbits", "Camp Note", "Note",
                  "The rabbits by the camp don't run anymore. One sat at the edge of the fire all evening and watched us eat. It didn't blink. When Bram stood up it walked backwards into the ferns, still looking at us."),
                L("lore_missing", "Missing Poster", "Note",
                  "HAVE YOU SEEN OUR LITTLE ONE? Pip, 7 years. Last seen by the mine fence the night everything went quiet. Brown fur, white patch on the left hand. Please. We hear him calling at night."),
                L("lore_foreman", "Foreman's Recording", "Tape",
                  "...lamps going out one by one down on three. I can see Teo's light at the end of the drift, he's walking away from me. Why is he walking away... I'm going down for them. If you find this, if you see my light - don't follow it. Don't-"),
                L("lore_radio", "Radio Log", "Note",
                  "02:10 Valley relay silent. 02:40 Northgate silent. 03:05 Both orchards silent. Every station went quiet within an hour. The last thing Northgate sent was the sound of something tapping on the microphone."),
                L("lore_assay", "Assay Report: Sample 7-C", "Note",
                  "Core sample 7-C. Temperature 39 C, rising when observed. Mass varies by up to 6% between weighings. Emits a low tone at night. Recommendation: HALT ALL L3 WORK. Response stamped: DENIED - QUOTA."),
                L("lore_tall", "Torn Page", "Note",
                  "Tomas stayed down for three shifts. When he came up he was too tall. His back had swollen, his arms nearly touched the ground. He didn't speak. He just stood between the trees with his head tilted, listening. We stopped talking when he was near."),
                L("lore_borer", "Drill Crew Log", "Note",
                  "The big drill rig was taken off L2 after the operator vanished. Something keeps re-digging the collapsed side drifts. Fresh scratches every morning, and rubble pushed OUTWARD. Never mine near the scratched supports."),
                L("lore_last", "Last Entry", "Tape",
                  "We sealed level three and cut the lift power. You can still hear it breathing up the shaft. If anyone comes after us: the breaker is at the bottom. Leave it off. Please leave it off."),
                L("lore_chasm", "Survey Sketch", "Note",
                  "Deep chasm below L3, no bottom found with 200 m of line. Something walks down there. We saw its shape cross the light of our dropped flare. It was taller than the headframe."),
                L("lore_children", "Crayon Drawing", "Note",
                  "A child's drawing: a bunker, a forest, and a tall monkey shape with a light in its chest, holding out its long arms. Written underneath: 'the lamp man wants to find his friends'."),
                // bestiary (unlocked by sighting)
                L("creature_hollowback", "Bestiary: Hollowback", "Bestiary",
                  "Hunts by sound. Freezes, listens, then comes. Running and loud slaps draw it into a charge; a still monkey behind cover is hard for it to find. It cannot climb - get high. A rattle can thrown away from you pulls it off your trail."),
                L("creature_falsekin", "Bestiary: Falsekin", "Bestiary",
                  "It wears a rabbit. Tells: never blinks, never flicks its ears, breathes too slowly, stays when other rabbits run, backs away facing you, seems to skip closer when you look away. It strikes once at close range and retreats. It can be killed."),
                L("creature_ceilingclerk", "Bestiary: Ceiling Clerk", "Bestiary",
                  "Lives above the beams. Moves only when unwatched - listen for tiny taps. Light freezes it, but each time for less long. Clicking from above means it is about to drop: move. If it grabs you, hit it or shine your light in its face."),
                L("creature_borer", "Bestiary: Borer", "Bestiary",
                  "Mining, carts and metal noise wake it. Two deep impacts from below are the warning. It feels movement through the ground and barely sees. Stand still and it loses you. Its back is armour; only a hit to the face while it winds up hurts it."),
                L("creature_lanternmourner", "Bestiary: Lantern Mourner", "Bestiary",
                  "Rare. Keeps its distance and leads followers toward danger. Drawn to artificial light and makes torches stutter as it nears. It only reaches for those whose light is on: switch it off, or throw a flare away from you."),
                L("creature_gaunt", "Bestiary: The Gaunt", "Bestiary", "Something enormous walks the bottom of the chasm. It looked up."),
                L("creature_rabbit", "Bestiary: Rabbit", "Bestiary", "Food. Approach slowly, crouched, and quietly. Most rabbits are only rabbits."),
                L("creature_boar", "Bestiary: Boar", "Bestiary", "More meat, harder to approach. Wounded boars charge."),
                // minerals
                L("mineral_iron", "Mineral: Iron Ore", "Mineral", "Common near the entrance. Low value, easy to mine with any pick."),
                L("mineral_copper", "Mineral: Copper Ore", "Mineral", "Reddish-orange veins. The backbone of early upgrades."),
                L("mineral_crystal", "Mineral: Luminous Crystal", "Mineral", "Glows from inside. Found on levels 2 and 3. Strikes chime loudly."),
                L("mineral_blackstone", "Mineral: Blackstone", "Mineral", "Deep only. Too hard for a rusty pick - bring a tempered one."),
                L("mineral_anomalous", "Mineral: Anomalous Core", "Mineral", "Warm, humming, connected to whatever happened. Only a Resonance pick opens one. Worth a fortune."),
            };
            EditorUtility.SetDirty(db);
        }

        static LoreEntry L(string id, string title, string kind, string text) => new LoreEntry { id = id, title = title, kind = kind, text = text };
    }
}
