using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.AI;
using MonkeyNoFear.AI;
using MonkeyNoFear.AI.Creatures;
using MonkeyNoFear.AI.Wildlife;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.EditorTools
{
    public static partial class PrefabFactory
    {
        static Dictionary<string, object> _cm;
        static Dictionary<string, object> CreatureInfo(string name)
        {
            if (_cm == null) _cm = MiniJson.Parse(MNFPaths.ReadText(MNFPaths.Creatures + "/creatures_manifest.json")).AsObj() ?? new Dictionary<string, object>();
            return _cm.Get(name).AsObj();
        }

        public static void BuildCreatures()
        {
            _cm = null;
            MNFPaths.Ensure(CreaturesDir);
            Hollowback();
            Wildlife("Rabbit", "rabbit", "rabbit_meat", 1, "rabbit_sniff", "rabbit_hop", "rabbit_squeal", "rabbit_thump", "hop", 9f, 5f, false);
            Wildlife("Boar", "boar", "boar_meat", 1, "boar_grunt", "", "boar_squeal", "boar_grunt", "walk", 14f, 8f, true);
            Wildlife("Gloomrat", "gloomrat", null, 0, "rat_squeak", "rat_scurry", "rat_squeak", "", "run", 6f, 3f, false);
            Falsekin();
            Clerk();
            Borer();
            Mourner();
            Gaunt();
            Silhouettes();
            AssetDatabase.SaveAssets();
        }

        /// <summary>Instantiates a creature model (nested FBX prefab) under a new root, or a crude stand-in
        /// so behaviour can still be tested when the model has not been delivered.</summary>
        static GameObject CreatureRoot(string name, out GameObject model, out Dictionary<string, object> info)
        {
            info = CreatureInfo(name);
            var root = new GameObject("Creature_" + name);
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>($"{MNFPaths.Creatures}/{name}.fbx");
            if (asset)
            {
                model = (GameObject)PrefabUtility.InstantiatePrefab(asset);
                model.name = "Model";
                model.transform.SetParent(root.transform, false);
            }
            else
            {
                Debug.LogWarning($"[MNF] Creature model {name}.fbx missing — using a stand-in body.");
                model = new GameObject("Model");
                model.transform.SetParent(root.transform, false);
                float h = info != null ? info.GetFloat("height", 1.5f) : 1.5f;
                var body = Primitive(PrimitiveType.Capsule, "StandIn", model.transform, Vector3.up * h * 0.5f, new Vector3(h * 0.35f, h * 0.5f, h * 0.35f), "MNF_Silhouette");
                Object.DestroyImmediate(body.GetComponent<Collider>());
                new GameObject("head").transform.SetParent(model.transform, false);
                model.transform.Find("head").localPosition = Vector3.up * h * 0.9f;
            }
            foreach (var r in model.GetComponentsInChildren<SkinnedMeshRenderer>(true)) { r.updateWhenOffscreen = false; r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On; }
            return root;
        }

        static CreatureAnimator SetupAnimator(GameObject host, GameObject model, Dictionary<string, object> info)
        {
            var ca = host.AddComponent<CreatureAnimator>();
            ca.anim = model.GetComponent<Animation>() ?? model.GetComponentInChildren<Animation>();
            if (ca.anim) { ca.anim.playAutomatically = true; ca.anim.cullingType = AnimationCullingType.BasedOnRenderers; }
            ca.visualRoot = model.transform;
            float fps = info != null ? info.GetFloat("fps", 30f) : 30f;
            var clips = info?.Get("clips").AsObj();
            if (clips != null)
                foreach (var kv in clips)
                {
                    var c = kv.Value.AsObj();
                    var ci = new ClipInfo { name = kv.Key, length = c.GetFloat("length", 1f), loop = c.GetBool("loop", true), authoredSpeed = c.GetFloat("speed", 0f) };
                    var ev = c.Get("events").AsObj();
                    if (ev != null)
                        foreach (var e in ev)
                            foreach (var f in e.Value.AsList())
                                ci.events.Add(new ClipEvent { name = e.Key, time = System.Convert.ToSingle(f) / fps });
                    ca.clips.Add(ci);
                }
            return ca;
        }

        static T SetupBody<T>(GameObject root, Dictionary<string, object> info, string profileId, float radius, float height, bool navAgent) where T : CreatureBase
        {
            var cap = root.AddComponent<CapsuleCollider>();
            cap.radius = radius; cap.height = Mathf.Max(height, radius * 2f); cap.center = Vector3.up * cap.height * 0.5f;
            var rb = root.AddComponent<Rigidbody>(); rb.isKinematic = true; rb.useGravity = false;
            if (navAgent)
            {
                var ag = root.AddComponent<NavMeshAgent>();
                ag.radius = Mathf.Min(radius, 0.9f); ag.height = height; ag.baseOffset = 0f; ag.stoppingDistance = 0.3f;
                ag.obstacleAvoidanceType = ObstacleAvoidanceType.LowQualityObstacleAvoidance;
                ag.autoTraverseOffMeshLink = true;
            }
            var c = root.AddComponent<T>();
            c.profile = DataFactory.Profile(profileId);
            c.agent = root.GetComponent<NavMeshAgent>();
            Layers.SetLayerRecursive(root, Layers.Creature);
            return c;
        }

        static Transform Bone(GameObject model, string name) => KitLibrary.FindDeep(model.transform, name);

        static void Hollowback()
        {
            var root = CreatureRoot("Hollowback", out var model, out var info);
            var ca = SetupAnimator(root, model, info);
            var hb = SetupBody<Hollowback>(root, info, "hollowback", 0.45f, info != null ? info.GetFloat("height", 2.35f) : 2.35f, true);
            hb.animator = ca; hb.voiceLoop = "hb_breath_loop"; hb.eyes = Bone(model, "head");
            Save(root, CreaturesDir, "Creature_Hollowback");
        }

        static void Wildlife(string name, string profile, string food, int foodCount, string idleS, string moveS, string hurtS, string alertS, string moveClip,
            float alertR, float fleeR, bool charges)
        {
            var root = CreatureRoot(name, out var model, out var info);
            var ca = SetupAnimator(root, model, info);
            float h = info != null ? info.GetFloat("height", 0.3f) : 0.3f;
            float len = info != null ? info.GetFloat("length", 0.4f) : 0.4f;
            var wa = SetupBody<WildAnimal>(root, info, profile, Mathf.Max(0.12f, len * 0.35f), Mathf.Max(0.25f, h), true);
            wa.animator = ca; wa.eyes = Bone(model, "head");
            wa.foodDrop = string.IsNullOrEmpty(food) ? null : Def(food);
            wa.foodCount = foodCount;
            wa.idleSound = idleS; wa.moveSound = moveS; wa.hurtSound = hurtS; wa.alertSound = alertS; wa.moveClip = moveClip;
            wa.alertRadius = alertR; wa.fleeRadius = fleeR; wa.chargesWhenHurt = charges;
            wa.usesBurrows = name != "Boar";
            wa.blinkRate = name == "Rabbit" ? 0.3f : 0f;
            Save(root, CreaturesDir, "Creature_" + name);
        }

        static void Falsekin()
        {
            var root = new GameObject("Creature_Falsekin");
            // disguise: the real rabbit rig, subtly wrong
            var rabbitAsset = AssetDatabase.LoadAssetAtPath<GameObject>($"{MNFPaths.Creatures}/Rabbit.fbx");
            var rabbitInfo = CreatureInfo("Rabbit");
            GameObject disguise = rabbitAsset ? (GameObject)PrefabUtility.InstantiatePrefab(rabbitAsset) : new GameObject("Disguise");
            disguise.name = "Disguise";
            disguise.transform.SetParent(root.transform, false);
            foreach (var r in disguise.GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++) if (mats[i] && mats[i].name == "MNF_FurRabbit") mats[i] = MaterialFactory.Get("MNF_FurRabbitMangy");
                r.sharedMaterials = mats;
            }
            foreach (var bn in new[] { "thigh.L", "thigh.R", "shin.L", "shin.R" }) { var b = Bone(disguise, bn); if (b) b.localScale = Vector3.one * 1.12f; }
            var earL = Bone(disguise, "ear.L"); if (earL) earL.localRotation *= Quaternion.Euler(22f, 0f, 10f);
            var earR = Bone(disguise, "ear.R"); if (earR) earR.localRotation *= Quaternion.Euler(-28f, 0f, -12f);
            var dAnim = SetupAnimator(disguise, disguise, rabbitInfo);
            dAnim.anim = disguise.GetComponent<Animation>();

            var fkAsset = AssetDatabase.LoadAssetAtPath<GameObject>($"{MNFPaths.Creatures}/Falsekin.fbx");
            var fkInfo = CreatureInfo("Falsekin");
            GameObject revealed = fkAsset ? (GameObject)PrefabUtility.InstantiatePrefab(fkAsset) : new GameObject("Revealed");
            revealed.name = "Revealed";
            revealed.transform.SetParent(root.transform, false);
            var rAnim = SetupAnimator(revealed, revealed, fkInfo);
            rAnim.anim = revealed.GetComponent<Animation>();
            revealed.SetActive(false);

            var fk = SetupBody<Falsekin>(root, fkInfo, "falsekin", 0.25f, 0.7f, true);
            fk.disguiseModel = disguise; fk.disguiseAnimator = dAnim;
            fk.revealedModel = revealed; fk.revealedAnimator = rAnim;
            fk.animator = dAnim;
            fk.glandDrop = Def("falsekin_gland");
            Save(root, CreaturesDir, "Creature_Falsekin");
        }

        static void Clerk()
        {
            var root = CreatureRoot("CeilingClerk", out var model, out var info);
            var ca = SetupAnimator(root, model, info);
            var c = SetupBody<CeilingClerk>(root, info, "ceilingclerk", 0.35f, 0.6f, false);
            c.animator = ca; c.voiceLoop = "clerk_click_loop"; c.eyes = Bone(model, "head");
            Save(root, CreaturesDir, "Creature_CeilingClerk");
        }

        static void Borer()
        {
            var root = CreatureRoot("Borer", out var model, out var info);
            var ca = SetupAnimator(root, model, info);
            var b = SetupBody<Borer>(root, info, "borer", 0.9f, info != null ? info.GetFloat("height", 1.5f) : 1.5f, true);
            b.animator = ca; b.eyes = Bone(model, "head");
            Save(root, CreaturesDir, "Creature_Borer");
        }

        static void Mourner()
        {
            var root = CreatureRoot("LanternMourner", out var model, out var info);
            var ca = SetupAnimator(root, model, info);
            var m = SetupBody<LanternMourner>(root, info, "lanternmourner", 0.4f, info != null ? info.GetFloat("height", 2.7f) : 2.7f, true);
            m.animator = ca; m.voiceLoop = "mourner_hum_loop"; m.eyes = Bone(model, "head");
            var chest = Bone(model, "socket_chestlight") ?? Bone(model, "chest");
            if (chest) { m.chestLight = AddLight(chest, "ChestGlow", LightType.Point, new Color(0.74f, 0.86f, 0.34f), 6f, 0.9f, Vector3.zero); m.chestLight.renderMode = LightRenderMode.ForcePixel; }
            var lamps = Bone(model, "lamps") ?? Bone(model, "hand.R");
            if (lamps) m.lampLight = AddLight(lamps, "LampGlow", LightType.Point, new Color(1f, 0.7f, 0.4f), 3f, 0.4f, Vector3.zero);
            Save(root, CreaturesDir, "Creature_LanternMourner");
        }

        static void Gaunt()
        {
            var root = CreatureRoot("Gaunt", out var model, out var info);
            var ca = SetupAnimator(root, model, info);
            var g = root.AddComponent<Gaunt>();
            g.animator = ca;
            Save(root, CreaturesDir, "Creature_Gaunt");
        }

        /// <summary>Unlit-dark frozen figures for the peripheral-silhouette horror event.</summary>
        static void Silhouettes()
        {
            foreach (var name in new[] { "Hollowback", "LanternMourner" })
            {
                var asset = AssetDatabase.LoadAssetAtPath<GameObject>($"{MNFPaths.Creatures}/{name}.fbx");
                var root = new GameObject("Silhouette_" + name);
                if (asset)
                {
                    var m = (GameObject)PrefabUtility.InstantiatePrefab(asset);
                    m.transform.SetParent(root.transform, false);
                    var an = m.GetComponent<Animation>(); if (an) an.playAutomatically = true;
                    foreach (var r in m.GetComponentsInChildren<Renderer>(true))
                    {
                        var mats = r.sharedMaterials;
                        for (int i = 0; i < mats.Length; i++) mats[i] = MaterialFactory.Get("MNF_Silhouette");
                        r.sharedMaterials = mats;
                        r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    }
                }
                else Primitive(PrimitiveType.Capsule, "Figure", root.transform, Vector3.up * 1.2f, new Vector3(0.6f, 1.2f, 0.6f), "MNF_Silhouette");
                foreach (var c in root.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
                Save(root, CreaturesDir, "Silhouette_" + name);
            }
        }
    }
}
