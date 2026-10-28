using UnityEditor;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.EditorTools
{
    public static partial class PrefabFactory
    {
        public static GameObject BuildPlayerRig()
        {
            MNFPaths.Ensure(SystemDir);
            var root = new GameObject("PlayerRig");
            root.layer = Layers.Player;
            var tracking = new GameObject("TrackingSpace").transform;
            tracking.SetParent(root.transform, false);

            // camera
            var camGo = new GameObject("HeadCamera");
            camGo.tag = "MainCamera";
            camGo.transform.SetParent(tracking, false);
            camGo.transform.localPosition = new Vector3(0f, 1.55f, 0f);
            var cam = camGo.AddComponent<Camera>();
            cam.nearClipPlane = 0.03f; cam.farClipPlane = 120f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.05f, 0.05f, 0.055f);
            cam.cullingMask = ~0;
            cam.allowHDR = false; cam.allowMSAA = true;
            camGo.AddComponent<AudioListener>();
            var fader = camGo.AddComponent<ScreenFader>();
            fader.overlay = OverlayQuad(camGo.transform, "FadeOverlay", 0.08f, "MNF_Overlay");
            fader.vignette = OverlayQuad(camGo.transform, "Vignette", 0.085f, "MNF_Vignette");

            // head slot (headlamp)
            var headSlot = new GameObject("HeadSlot").AddComponent<Holster>();
            headSlot.transform.SetParent(camGo.transform, false);
            headSlot.transform.localPosition = new Vector3(0f, 0.09f, 0.06f);
            headSlot.headSlot = true; headSlot.radius = 0.16f; headSlot.itemLocalEuler = Vector3.zero;

            // body capsule
            var body = new GameObject("Body");
            body.transform.SetParent(root.transform, false);
            body.layer = Layers.Player;
            var cap = body.AddComponent<CapsuleCollider>();
            cap.radius = 0.17f; cap.height = 1.6f; cap.center = Vector3.up * 0.8f;

            // hands
            var left = MakeHand(root.transform, "LeftHand", Hand.Left);
            var right = MakeHand(root.transform, "RightHand", Hand.Right);

            // body frame: holsters + backpack zone
            var frame = new GameObject("BodyFrame").transform;
            frame.SetParent(root.transform, false);
            MakeHolster(frame, "HipLeft", new Vector3(-0.24f, -0.78f, 0.05f), new Vector3(90f, 0f, 0f));
            MakeHolster(frame, "HipRight", new Vector3(0.24f, -0.78f, 0.05f), new Vector3(90f, 0f, 0f));
            MakeHolster(frame, "ChestStrap", new Vector3(-0.12f, -0.38f, 0.14f), new Vector3(60f, 0f, 0f));

            // systems on the root
            var loco = root.AddComponent<MonkeyLocomotion>();
            var rig = root.AddComponent<PlayerRig>();
            root.AddComponent<PlayerHealth>();
            root.AddComponent<PlayerVitals>();
            root.AddComponent<PlayerStealth>();
            var pack = root.AddComponent<Backpack>();
            pack.bodyFrame = frame;
            var rb = root.AddComponent<Rigidbody>(); rb.isKinematic = true; rb.useGravity = false;
            rig.trackingSpace = tracking; rig.headCamera = cam; rig.locomotion = loco; rig.bodyCollider = cap; rig.bodyFrame = frame;
            rig.leftHand = left.GetComponent<PhysicsHand>(); rig.rightHand = right.GetComponent<PhysicsHand>();
            rig.leftGrabber = left.GetComponent<HandGrabber>(); rig.rightGrabber = right.GetComponent<HandGrabber>();

            // avatar: the supplied monkey
            var avatarRoot = new GameObject("Avatar");
            avatarRoot.transform.SetParent(root.transform, false);
            var av = avatarRoot.AddComponent<PlayerAvatar>();
            av.rig = rig;
            var playerAsset = AssetDatabase.LoadAssetAtPath<GameObject>(MNFPaths.Player + "/MonkeyPlayer.fbx");
            if (playerAsset)
            {
                var model = (GameObject)PrefabUtility.InstantiatePrefab(playerAsset);
                model.name = "MonkeyModel";
                model.transform.SetParent(avatarRoot.transform, false);
                av.modelRoot = model.transform;
                foreach (var t in model.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = Layers.Default;
                // eye point from the converted rig: just in front of the head bone, 45% up the head
                var head = KitLibrary.FindDeep(model.transform, "head");
                if (head)
                {
                    var hp = model.transform.InverseTransformPoint(head.position);
                    av.eyeInModel = hp + new Vector3(0f, 0.1f, 0.06f);
                }
                // backpack on the back of the torso
                var torso = KitLibrary.FindDeep(model.transform, "torso");
                var packModel = KitLibrary.Copy("Backpack");
                if (torso && packModel)
                {
                    foreach (var c in packModel.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
                    ConvertHelperColliders(packModel);
                    var tp = torso.position;
                    packModel.transform.position = new Vector3(0f, tp.y + 0.05f, -0.16f) + model.transform.position;
                    packModel.transform.rotation = Quaternion.Euler(0f, 180f, 0f);
                    packModel.transform.localScale = Vector3.one * 0.8f;
                    packModel.transform.SetParent(torso, true);
                }
            }
            else Debug.LogError("[MNF] MonkeyPlayer.fbx missing — run Tools/blender/player/convert_player.py");

            // wrist readout
            var wrist = new GameObject("WristDisplay").AddComponent<WristDisplay>();
            wrist.transform.SetParent(root.transform, false);
            wrist.backingMaterial = MaterialFactory.Get("MNF_Silhouette");

            return Save(root, SystemDir, "PlayerRig");
        }

        static Renderer OverlayQuad(Transform cam, string name, float dist, string mat)
        {
            var q = GameObject.CreatePrimitive(PrimitiveType.Quad);
            q.name = name;
            Object.DestroyImmediate(q.GetComponent<Collider>());
            q.transform.SetParent(cam, false);
            q.transform.localPosition = Vector3.forward * dist;
            q.transform.localScale = Vector3.one * dist * 3f;
            var r = q.GetComponent<Renderer>();
            r.sharedMaterial = MaterialFactory.GetOrFallback(mat);
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            r.enabled = false;
            return r;
        }

        static GameObject MakeHand(Transform parent, string name, Hand side)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.layer = Layers.PlayerHand;
            var ph = go.AddComponent<PhysicsHand>();
            ph.hand = side;
            go.AddComponent<SphereCollider>().radius = 0.05f;
            var rb = go.AddComponent<Rigidbody>(); rb.isKinematic = true; rb.useGravity = false;
            go.AddComponent<HandGrabber>();
            return go;
        }

        static void MakeHolster(Transform frame, string name, Vector3 pos, Vector3 euler)
        {
            var h = new GameObject(name).AddComponent<Holster>();
            h.transform.SetParent(frame, false);
            h.transform.localPosition = pos;
            h.itemLocalEuler = euler;
            h.radius = 0.2f;
        }

        // ------------------------------------------------------------------ FX + systems
        public static GameObject BuildFX()
        {
            MNFPaths.Ensure(SystemDir);
            var root = new GameObject("FX");
            var fx = root.AddComponent<FXManager>();
            fx.effects.Add(Burst(root.transform, "debris", "MNF_FX_Debris", 0.015f, 0.05f, 0.7f, 1.3f, 1f, 3f, 0.6f));
            fx.effects.Add(Burst(root.transform, "dust", "MNF_FX_Dust", 0.25f, 0.7f, 1.8f, 3f, -0.01f, 0.4f, 1f));
            fx.effects.Add(Burst(root.transform, "sparks", "MNF_FX_Spark", 0.01f, 0.025f, 0.15f, 0.45f, 0.8f, 3.5f, 0.6f));
            fx.effects.Add(Burst(root.transform, "dust_fall", "MNF_FX_Dust", 0.04f, 0.12f, 2.5f, 3.5f, 0.15f, 0.2f, 0.4f));
            fx.effects.Add(Burst(root.transform, "blood", "MNF_FX_Drip", 0.02f, 0.05f, 0.5f, 0.9f, 1f, 2f, 0.6f));
            fx.effects.Add(Burst(root.transform, "fur", "MNF_FX_Leaf", 0.03f, 0.07f, 1.2f, 2.2f, 0.12f, 2.5f, 1f));

            // player-following ambient layers
            var amb = new GameObject("Ambient").AddComponent<AmbientParticles>();
            amb.transform.SetParent(root.transform, false);
            amb.layers = new[]
            {
                Ambient(amb.transform, "GroundFog", "MNF_FX_Fog", new Vector3(50f, 1.5f, 50f), 6f, 11f, 18f, 7f, 60, 0.18f, new Color(0.55f, 0.6f, 0.65f, 0.35f), new[] { AreaId.Forest }, false, new Vector3(0f, 0.6f, 0f)),
                Ambient(amb.transform, "FogBanks", "MNF_FX_Fog", new Vector3(80f, 6f, 80f), 14f, 22f, 25f, 2.5f, 40, 0.1f, new Color(0.5f, 0.55f, 0.6f, 0.25f), new[] { AreaId.Forest }, false, new Vector3(0f, 4f, 0f)),
                Ambient(amb.transform, "Leaves", "MNF_FX_Leaf", new Vector3(30f, 10f, 30f), 0.06f, 0.12f, 8f, 3f, 40, 0.5f, new Color(0.45f, 0.38f, 0.3f, 1f), new[] { AreaId.Forest }, true, new Vector3(0f, 4f, 0f), 0.08f),
                Ambient(amb.transform, "MineMotes", "MNF_FX_Dust", new Vector3(8f, 4f, 8f), 0.01f, 0.025f, 8f, 18f, 150, 0.06f, new Color(0.8f, 0.75f, 0.7f, 0.5f), new[] { AreaId.MineShallow, AreaId.MineMid, AreaId.MineDeep, AreaId.Corridor }, true, Vector3.zero),
                Ambient(amb.transform, "BunkerMotes", "MNF_FX_Dust", new Vector3(8f, 4f, 8f), 0.008f, 0.02f, 9f, 10f, 100, 0.04f, new Color(0.9f, 0.85f, 0.8f, 0.45f), new[] { AreaId.Bunker }, true, Vector3.zero),
            };
            return Save(root, SystemDir, "FX");
        }

        static FXManager.Effect Burst(Transform parent, string name, string mat, float sizeMin, float sizeMax, float lifeMin, float lifeMax, float gravity, float speed, float spread)
        {
            var go = new GameObject("FX_" + name);
            go.transform.SetParent(parent, false);
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.playOnAwake = true; main.loop = true; main.duration = 5f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(lifeMin, lifeMax);
            main.startSpeed = 0f;
            main.startSize = new ParticleSystem.MinMaxCurve(sizeMin, sizeMax);
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            main.gravityModifier = gravity;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = 600;
            var em = ps.emission; em.rateOverTime = 0f;
            var sh = ps.shape; sh.enabled = false;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) }, new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(1f, 0.6f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            var lim = ps.limitVelocityOverLifetime; lim.enabled = true; lim.dampen = 0.08f; lim.limit = 20f;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = MaterialFactory.Get(mat);
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            return new FXManager.Effect { name = name, system = ps, speed = speed, spread = spread };
        }

        static AmbientParticles.Layer Ambient(Transform parent, string name, string mat, Vector3 box, float sizeMin, float sizeMax, float life, float rate,
            int max, float speed, Color color, AreaId[] areas, bool followHead, Vector3 offset, float gravity = 0f)
        {
            var go = new GameObject("Ambient_" + name);
            go.transform.SetParent(parent, false);
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.loop = true; main.prewarm = true; main.startLifetime = life; main.startSpeed = speed;
            main.startSize = new ParticleSystem.MinMaxCurve(sizeMin, sizeMax);
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            main.startColor = color; main.maxParticles = max; main.gravityModifier = gravity;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var em = ps.emission; em.rateOverTime = rate; em.enabled = false;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Box; sh.scale = box; sh.randomDirectionAmount = 1f;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) }, new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.25f), new GradientAlphaKey(1f, 0.75f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            var noise = ps.noise; noise.enabled = true; noise.strength = speed * 0.5f + 0.05f; noise.frequency = 0.2f; noise.quality = ParticleSystemNoiseQuality.Low;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = MaterialFactory.Get(mat);
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.sortMode = ParticleSystemSortMode.Distance;
            return new AmbientParticles.Layer { system = ps, areas = areas, followHead = followHead, offset = offset };
        }
    }
}
