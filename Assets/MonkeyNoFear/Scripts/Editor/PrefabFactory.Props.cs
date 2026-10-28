using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using MonkeyNoFear.AI.Wildlife;
using MonkeyNoFear.Core;
using MonkeyNoFear.World;

namespace MonkeyNoFear.EditorTools
{
    public static partial class PrefabFactory
    {
        /// <summary>Default sign-atlas cell for props that carry a sign board.</summary>
        static readonly Dictionary<string, int> BoardCells = new Dictionary<string, int>
        {
            { "SignPost", 15 }, { "WarningBoard", 0 }, { "MineEntrance", 3 }, { "Sign_Level", 5 },
        };

        static readonly HashSet<string> NoCollider = new HashSet<string>
        {
            "Bush_A", "Bush_B", "Fern", "GrassTuft", "MushroomCluster", "CableBundle", "LampString", "Clipboard", "PosterBoard",
        };

        /// <summary>Static scenery prefabs for every object in the environment kits.</summary>
        public static void BuildProps()
        {
            MNFPaths.Ensure(PropsDir);
            int n = 0;
            foreach (var name in new List<string>(KitLibrary.Names))
            {
                if (name.StartsWith("Pickaxe") || name.StartsWith("OreChunk") || name.StartsWith("Deposit_")) continue;
                if (AssetDatabase.LoadAssetAtPath<GameObject>($"{ItemsDir}/Item_{name}.prefab")) continue; // items
                BuildProp(name);
                n++;
            }
            AssetDatabase.SaveAssets();
            Debug.Log($"[MNF] Props: {n} prefabs");
        }

        public static GameObject Prop(string name) => Load(PropsDir, "Prop_" + name);

        static void BuildProp(string name)
        {
            var model = KitLibrary.Copy(name);
            if (!model) return;
            var go = new GameObject("Prop_" + name);
            model.transform.SetParent(go.transform, false);
            bool foliageOnly = NoCollider.Contains(name);
            if (foliageOnly) ConvertHelperColliders(go);
            else AddStaticColliders(go);

            if (name.StartsWith("Bush"))
            {
                // bushes are soft vision cover: creatures see through them badly
                var b = KitLibrary.RenderBounds(go);
                var sc = go.AddComponent<SphereCollider>();
                sc.isTrigger = true;
                sc.center = b.center - go.transform.position;
                sc.radius = Mathf.Max(b.extents.x, b.extents.z) * 0.85f;
            }
            if (BoardCells.TryGetValue(name, out int cell)) ApplySignToBoard(go, cell);
            if (name == "Burrow") go.AddComponent<Burrow>();
            if (name == "VentFan")
            {
                var fan = KitLibrary.FindDeep(go.transform, "Fan");
                if (fan) fan.gameObject.AddComponent<Spinner>().axis = Vector3.forward;
            }
            if (name == "Campfire")
            {
                var sock = KitLibrary.FindDeep(go.transform, "SOCKET_Fire");
                var at = sock ? sock.localPosition + Vector3.up * 0.3f : Vector3.up * 0.3f;
                var l = AddLight(go.transform, "Fire", LightType.Point, new Color(1f, 0.55f, 0.25f), 9f, 1.8f, at, true);
                l.shadows = LightShadows.Soft;
                var ff = l.gameObject.AddComponent<FireFlicker>(); ff.baseIntensity = 1.8f; ff.crackleLoop = "flare_burn_loop";
                MakeFire(go.transform, at - Vector3.up * 0.2f);
            }
            if (name == "CampLantern")
            {
                var bulb = KitLibrary.FindDeep(go.transform, "Bulb");
                var l = AddLight(go.transform, "Flame", LightType.Point, new Color(1f, 0.62f, 0.3f), 6f, 1.1f, bulb ? bulb.localPosition : Vector3.up * 0.2f);
                l.gameObject.AddComponent<FireFlicker>().baseIntensity = 1.1f;
            }

            var layerTarget = foliageOnly ? Layers.Default : Layers.Environment;
            Layers.SetLayerRecursive(go, layerTarget);
            foreach (var c in go.GetComponentsInChildren<Collider>(true)) if (c.isTrigger) c.gameObject.layer = Layers.Foliage;
            SurfaceFromMaterials(go);
            bool small = KitLibrary.RenderBounds(go).size.magnitude < 0.6f;
            ShadowsFor(go, !foliageOnly && !small);
            SetStatic(go, true);
            Save(go, PropsDir, "Prop_" + name);
        }

        static void ApplySignToBoard(GameObject go, int cell)
        {
            var board = KitLibrary.FindDeep(go.transform, "Board");
            if (!board) return;
            var mf = board.GetComponent<MeshFilter>();
            var mr = board.GetComponent<MeshRenderer>();
            if (!mf || !mf.sharedMesh || !mr) return;
            var src = mf.sharedMesh;
            MNFPaths.Ensure(MNFPaths.Generated + "/Meshes");
            string path = $"{MNFPaths.Generated}/Meshes/Board_{go.name}_{cell}.asset";
            var mesh = Object.Instantiate(src);
            var uv = mesh.uv;
            int col = cell % 4, row = cell / 4;
            for (int i = 0; i < uv.Length; i++)
                uv[i] = new Vector2(col * 0.25f + 0.004f + Mathf.Clamp01(uv[i].x) * 0.242f, 1f - (row + 1) * 0.25f + 0.004f + Mathf.Clamp01(uv[i].y) * 0.242f);
            mesh.uv = uv;
            var old = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (old) AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(mesh, path);
            mf.sharedMesh = mesh;
            var mats = mr.sharedMaterials;
            for (int i = 0; i < mats.Length; i++) mats[i] = MaterialFactory.Get("MNF_Signs");
            mr.sharedMaterials = mats;
        }

        static void MakeFire(Transform parent, Vector3 at)
        {
            var go = new GameObject("Flames");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = at;
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.loop = true; main.startLifetime = new ParticleSystem.MinMaxCurve(0.5f, 0.9f); main.startSpeed = new ParticleSystem.MinMaxCurve(0.3f, 0.8f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.15f, 0.4f); main.startColor = new Color(1f, 0.55f, 0.2f, 0.8f);
            main.simulationSpace = ParticleSystemSimulationSpace.World; main.maxParticles = 60; main.gravityModifier = -0.15f;
            var em = ps.emission; em.rateOverTime = 28f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Circle; sh.radius = 0.2f; sh.rotation = new Vector3(-90f, 0f, 0f);
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(new Color(1f, 0.8f, 0.4f), 0f), new GradientColorKey(new Color(0.8f, 0.2f, 0.05f), 1f) },
                      new[] { new GradientAlphaKey(0.9f, 0f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            go.GetComponent<ParticleSystemRenderer>().sharedMaterial = MaterialFactory.Get("MNF_FX_Glow");
        }
    }
}
