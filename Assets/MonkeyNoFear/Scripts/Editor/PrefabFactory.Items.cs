using UnityEditor;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Items;
using MonkeyNoFear.Mining;

namespace MonkeyNoFear.EditorTools
{
    public static partial class PrefabFactory
    {
        static ItemDefinition Def(string id) => AssetDatabase.LoadAssetAtPath<ItemDefinition>($"{DataFactory.Items}/Item_{id}.asset");

        /// <summary>Builds every handheld item / tool prefab and links it to its ItemDefinition.</summary>
        public static void BuildItems()
        {
            MNFPaths.Ensure(ItemsDir);
            Tool("Pickaxe_T1", "pickaxe_t1", false, go => Pick(go, 1, 22f, 1f));
            Tool("Pickaxe_T2", "pickaxe_t2", false, go => Pick(go, 2, 36f, 0.9f));
            Tool("Pickaxe_T3", "pickaxe_t3", false, go => Pick(go, 3, 50f, 0.55f));
            Tool("Spear", "spear", false, go => { var s = go.AddComponent<Spear>(); s.tip = KitLibrary.FindDeep(go.transform, "TIP"); });
            Tool("Flashlight", "flashlight", true, go => Torch(go, false));
            Tool("Headlamp", "headlamp", false, go => Torch(go, true));
            Tool("Scanner", "scanner", true, go =>
            {
                var sc = go.AddComponent<Scanner>();
                var screen = KitLibrary.FindDeep(go.transform, "Screen");
                if (screen)
                {
                    var rot = TextRotationOnQuad(screen, out var n);
                    sc.screen = AddText(screen, "Readout", n * 0.002f, rot, 0.011f, TextAnchor.MiddleCenter, new Color(0.5f, 1f, 0.55f), "SCAN");
                }
                var lamp = KitLibrary.FindDeep(go.transform, "Lamp");
                sc.lamp = lamp ? lamp.GetComponent<Renderer>() : KitLibrary.RendererWithMaterial(go, "MNF_BulbGreen");
            });
            Tool("Glowstick", "glowstick", true, go =>
            {
                var g = go.AddComponent<Glowstick>();
                g.tube = KitLibrary.RendererWithMaterial(go, "MNF_BulbGreen");
                g.glow = AddLight(go.transform, "Glow", LightType.Point, g.color, 4.5f, 0.9f, Vector3.zero);
                g.glow.renderMode = LightRenderMode.ForceVertex;
            });
            Tool("Flare", "flare", true, go =>
            {
                var f = go.AddComponent<MonkeyNoFear.Items.Flare>();
                f.tip = KitLibrary.FindDeep(go.transform, "TIP");
                var at = f.tip ? f.tip.localPosition : Vector3.zero;
                f.flame = AddLight(go.transform, "Flame", LightType.Point, f.color, 14f, 2.6f, at);
                f.smoke = MakeFlareSmoke(go.transform, at);
            });
            Tool("Noisemaker", "noisemaker", true, go => go.AddComponent<Noisemaker>());
            Tool("RopeCoil", "rope_coil", false, go => go.AddComponent<RopeCoil>().ropeMaterial = MaterialFactory.Get("MNF_Rope"));
            Tool("Medkit", "medkit", true, go => { var c = go.AddComponent<Consumable>(); c.effect = Consumable.Effect.Heal; c.amount = 50f; });
            Tool("Battery", "battery", true, go => { var c = go.AddComponent<Consumable>(); c.effect = Consumable.Effect.RechargeLights; c.useSound = "flashlight_on"; c.holdSeconds = 0.8f; });
            Tool("MarkerBeacon", "marker_beacon", true, go =>
            {
                var m = go.AddComponent<MarkerBeacon>();
                var lamp = KitLibrary.FindDeep(go.transform, "Lamp");
                m.lamp = lamp ? lamp.GetComponent<Renderer>() : KitLibrary.RendererWithMaterial(go, "MNF_BulbRed");
                m.blink = AddLight(go.transform, "Blink", LightType.Point, new Color(1f, 0.15f, 0.1f), 5f, 1.4f, Vector3.up * 0.1f);
            });
            Plain("FoodCan", "food_can");
            Plain("RabbitMeat", "rabbit_meat");
            Plain("BoarMeat", "boar_meat");
            Plain("FalsekinGland", "falsekin_gland");
            Plain("MinerTag", "miner_tag");
            Plain("OreChunk_Iron", "ore_iron");
            Plain("OreChunk_Copper", "ore_copper");
            Plain("OreChunk_Crystal", "ore_crystal", go => AddLight(go.transform, "Glow", LightType.Point, new Color(0.4f, 0.85f, 1f), 1.5f, 0.5f, Vector3.zero).renderMode = LightRenderMode.ForceVertex);
            Plain("OreChunk_Blackstone", "ore_blackstone");
            Plain("OreChunk_Anomalous", "ore_anomalous", go => AddLight(go.transform, "Glow", LightType.Point, new Color(1f, 0.25f, 0.15f), 1.5f, 0.6f, Vector3.zero).renderMode = LightRenderMode.ForceVertex);
            LoreTape();
            LoreNote();
            AssetDatabase.SaveAssets();
        }

        static void Pick(GameObject go, int tier, float dmg, float noise)
        {
            var p = go.AddComponent<Pickaxe>();
            p.tier = tier; p.damage = dmg; p.noiseMultiplier = noise;
            p.tip = KitLibrary.FindDeep(go.transform, "TIP");
        }

        static void Torch(GameObject go, bool head)
        {
            var f = go.AddComponent<Flashlight>();
            f.headMounted = head;
            var lightAt = KitLibrary.FindDeep(go.transform, "LIGHT");
            var beam = AddLight(go.transform, "Beam", LightType.Spot, new Color(1f, 0.93f, 0.8f), head ? 13f : 17f, head ? 1.6f : 2.2f, lightAt ? lightAt.localPosition : Vector3.forward * 0.12f, true);
            beam.transform.localRotation = Quaternion.identity; // tool forward (+Z)
            beam.spotAngle = head ? 72f : 62f;
            beam.shadows = head ? LightShadows.None : LightShadows.Hard;
            beam.shadowStrength = 0.85f;
            f.spot = beam;
            f.castShadows = !head;
            if (head) { f.wideAngle = 72f; f.wideRange = 13f; f.wideIntensity = 1.6f; f.focusAngle = 40f; f.focusRange = 20f; f.focusIntensity = 2.2f; }
            f.bulbRenderer = KitLibrary.RendererWithMaterial(go, "MNF_BulbWarm") ?? KitLibrary.RendererWithMaterial(go, "MNF_Glass");
        }

        static ParticleSystem MakeFlareSmoke(Transform parent, Vector3 at)
        {
            var go = new GameObject("Smoke");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = at;
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.playOnAwake = false; main.loop = true; main.startLifetime = 2.5f; main.startSpeed = 0.4f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.1f, 0.35f); main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startColor = new Color(1f, 0.55f, 0.5f, 0.35f); main.gravityModifier = -0.05f; main.maxParticles = 80;
            var em = ps.emission; em.rateOverTime = 18f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Cone; sh.angle = 15f; sh.radius = 0.01f;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.gray, 1f) }, new[] { new GradientAlphaKey(0.6f, 0f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            var sz = ps.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0, 0.4f, 1, 1.6f));
            go.GetComponent<ParticleSystemRenderer>().sharedMaterial = MaterialFactory.Get("MNF_FX_Smoke");
            ps.Stop();
            return ps;
        }

        /// <summary>Common item setup: copy from kit (or fallback shape), rigidbody, colliders, grab, item link.</summary>
        static GameObject MakeItemBase(string kitName, ItemDefinition def, bool snap, bool holsterable)
        {
            var model = KitLibrary.Copy(kitName);
            var go = new GameObject("Item_" + kitName);
            if (model) { model.transform.SetParent(go.transform, false); }
            else
            {
                Debug.LogWarning($"[MNF] Kit object {kitName} missing — using a fallback shape for {def?.id}.");
                var p = Primitive(PrimitiveType.Cube, "Fallback", go.transform, Vector3.zero, Vector3.one * 0.12f, "MNF_MetalRusted");
                Object.DestroyImmediate(p.GetComponent<Collider>());
            }
            // lift helpers to the item root so code finds them directly
            foreach (var helper in new[] { "TIP", "GRIP", "GRIP2", "LIGHT" })
            {
                var h = KitLibrary.FindDeep(go.transform, helper);
                if (h && h.parent != go.transform) h.SetParent(go.transform, true);
            }
            AddDynamicColliders(go);
            var rb = go.AddComponent<Rigidbody>();
            rb.mass = def ? def.mass : 0.5f;
            rb.drag = 0.05f; rb.angularDrag = 0.2f;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            rb.collisionDetectionMode = CollisionDetectionMode.ContinuousSpeculative;
            var g = go.AddComponent<Grabbable>();
            g.mode = snap ? Grabbable.GrabMode.SnapToGrip : Grabbable.GrabMode.KeepOffset;
            g.holsterable = holsterable;
            g.gripPoint = KitLibrary.FindDeep(go.transform, "GRIP");
            var inst = go.AddComponent<ItemInstance>();
            inst.definition = def;
            Layers.SetLayerRecursive(go, Layers.Item);
            ShadowsFor(go, true);
            return go;
        }

        static void Tool(string kitName, string itemId, bool holsterable, System.Action<GameObject> extra)
        {
            var def = Def(itemId);
            var go = MakeItemBase(kitName, def, true, holsterable);
            go.GetComponent<ItemInstance>().toolId = def && def.category == ItemCategory.Tool ? itemId : null;
            extra?.Invoke(go);
            Layers.SetLayerRecursive(go, Layers.Item);
            var prefab = Save(go, ItemsDir, "Item_" + kitName);
            if (def) { def.prefab = prefab; EditorUtility.SetDirty(def); }
        }

        static void Plain(string kitName, string itemId, System.Action<GameObject> extra = null)
        {
            var def = Def(itemId);
            var go = MakeItemBase(kitName, def, false, false);
            extra?.Invoke(go);
            var prefab = Save(go, ItemsDir, "Item_" + kitName);
            if (def) { def.prefab = prefab; EditorUtility.SetDirty(def); }
        }

        static void LoreTape()
        {
            var def = Def("lore_tape");
            var go = MakeItemBase("LoreTape", def, false, true);
            var li = go.AddComponent<LoreItem>();
            li.isTape = true;
            li.readout = AddText(go.transform, "Readout", new Vector3(0f, 0.16f, 0f), Quaternion.identity, 0.012f, TextAnchor.LowerCenter, new Color(1f, 0.92f, 0.75f));
            var prefab = Save(go, ItemsDir, "Item_LoreTape");
            if (def) { def.prefab = prefab; EditorUtility.SetDirty(def); }
        }

        static void LoreNote()
        {
            var def = Def("lore_note");
            var go = new GameObject("Item_LoreNote");
            var paper = Primitive(PrimitiveType.Cube, "Paper", go.transform, Vector3.zero, new Vector3(0.15f, 0.002f, 0.21f), "MNF_Paper");
            Object.DestroyImmediate(paper.GetComponent<Collider>());
            var bc = go.AddComponent<BoxCollider>(); bc.size = new Vector3(0.15f, 0.01f, 0.21f);
            var rb = go.AddComponent<Rigidbody>(); rb.mass = 0.05f; rb.drag = 2f; rb.angularDrag = 2f;
            go.AddComponent<Grabbable>().mode = Grabbable.GrabMode.KeepOffset;
            go.AddComponent<ItemInstance>().definition = def;
            var li = go.AddComponent<LoreItem>();
            li.readout = AddText(go.transform, "Readout", new Vector3(0f, 0.17f, 0f), Quaternion.identity, 0.011f, TextAnchor.LowerCenter, new Color(1f, 0.92f, 0.75f));
            Layers.SetLayerRecursive(go, Layers.Item);
            var prefab = Save(go, ItemsDir, "Item_LoreNote");
            if (def) { def.prefab = prefab; EditorUtility.SetDirty(def); }
        }

        // ------------------------------------------------------------------ deposits
        public static void BuildDeposits()
        {
            MNFPaths.Ensure(MNFPaths.Prefabs + "/Deposits");
            string[] types = { "Iron", "Copper", "Crystal", "Blackstone", "Anomalous" };
            foreach (var t in types)
            {
                var mineral = AssetDatabase.LoadAssetAtPath<MineralDefinition>($"{DataFactory.Minerals}/Mineral_{t.ToLowerInvariant()}.asset");
                var floor = Deposit("Deposit_" + t, mineral);
                var wall = KitLibrary.Has($"Deposit_{t}_Wall") ? Deposit($"Deposit_{t}_Wall", mineral) : null;
                if (mineral) { mineral.depositPrefab = floor; mineral.wallDepositPrefab = wall; EditorUtility.SetDirty(mineral); }
            }
            AssetDatabase.SaveAssets();
        }

        static GameObject Deposit(string kitName, MineralDefinition mineral)
        {
            var go = new GameObject(kitName);
            var model = KitLibrary.Copy(kitName);
            if (model) model.transform.SetParent(go.transform, false);
            else
            {
                // fallback: a rock with 4 coloured lumps
                Primitive(PrimitiveType.Sphere, "Base", go.transform, Vector3.up * 0.35f, new Vector3(1f, 0.7f, 0.9f), "MNF_RockMine");
                for (int i = 0; i < 4; i++)
                    Primitive(PrimitiveType.Sphere, "Chunk_0" + i, go.transform, new Vector3(Mathf.Cos(i * 1.6f) * 0.35f, 0.55f, Mathf.Sin(i * 1.6f) * 0.3f), Vector3.one * 0.28f,
                        mineral ? "MNF_Ore" + mineral.displayName.Split(' ')[0] : "MNF_OreIron");
                foreach (var c in go.GetComponentsInChildren<Collider>()) Object.DestroyImmediate(c);
            }
            if (ConvertHelperColliders(go) == 0)
            {
                var b = KitLibrary.RenderBounds(go);
                var bc = go.AddComponent<BoxCollider>(); bc.center = b.center - go.transform.position; bc.size = b.size;
            }
            var dep = go.AddComponent<OreDeposit>();
            dep.mineral = mineral;
            foreach (var t in go.GetComponentsInChildren<Transform>(true)) if (t.name.StartsWith("Chunk_")) dep.chunks.Add(t);
            if (mineral && mineral.glowIntensity > 0f)
                dep.glow = AddLight(go.transform, "Glow", LightType.Point, mineral.glowColor, 3.5f, mineral.glowIntensity, Vector3.up * 0.6f);
            var s = go.AddComponent<World.Surface>();
            s.kind = mineral && mineral.id == "crystal" ? SurfaceKind.Crystal : SurfaceKind.Rock;
            Layers.SetLayerRecursive(go, Layers.Environment);
            return Save(go, MNFPaths.Prefabs + "/Deposits", kitName);
        }
    }
}
