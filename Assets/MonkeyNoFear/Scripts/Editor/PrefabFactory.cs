using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.World;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>Shared helpers for building prefabs from kit objects (colliders, layers, saving).</summary>
    public static partial class PrefabFactory
    {
        public const string ItemsDir = MNFPaths.Prefabs + "/Items";
        public const string PropsDir = MNFPaths.Prefabs + "/Props";
        public const string StationsDir = MNFPaths.Prefabs + "/Stations";
        public const string CreaturesDir = MNFPaths.Prefabs + "/Creatures";
        public const string SystemDir = MNFPaths.Prefabs + "/System";

        static readonly HashSet<string> FoliageMats = new HashSet<string> { "MNF_FoliagePine", "MNF_FoliageLeaf", "MNF_Fern", "MNF_Grass" };

        public static GameObject Save(GameObject go, string dir, string name)
        {
            MNFPaths.Ensure(dir);
            var path = $"{dir}/{name}.prefab";
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, path);
            Object.DestroyImmediate(go);
            return prefab;
        }

        public static GameObject Load(string dir, string name) => AssetDatabase.LoadAssetAtPath<GameObject>($"{dir}/{name}.prefab");

        /// <summary>Converts COL_* helper meshes into colliders (Box, or convex Mesh when named _CONVEX) and
        /// hides them. Returns the number of colliders created.</summary>
        public static int ConvertHelperColliders(GameObject root)
        {
            int n = 0;
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
            {
                if (!t.name.StartsWith("COL_")) continue;
                var mf = t.GetComponent<MeshFilter>();
                var mr = t.GetComponent<MeshRenderer>();
                if (mf && mf.sharedMesh)
                {
                    if (t.name.Contains("_CONVEX")) { var mc = t.gameObject.AddComponent<MeshCollider>(); mc.sharedMesh = mf.sharedMesh; mc.convex = true; }
                    else { var bc = t.gameObject.AddComponent<BoxCollider>(); bc.center = mf.sharedMesh.bounds.center; bc.size = Vector3.Max(mf.sharedMesh.bounds.size, Vector3.one * 0.01f); }
                    n++;
                }
                if (mr) Object.DestroyImmediate(mr);
                if (mf) Object.DestroyImmediate(mf);
            }
            return n;
        }

        /// <summary>Static scenery colliders: helper boxes if present, otherwise exact mesh colliders on
        /// every non-foliage renderer.</summary>
        public static void AddStaticColliders(GameObject root)
        {
            if (ConvertHelperColliders(root) > 0) return;
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                var r = mf.GetComponent<Renderer>();
                if (!mf.sharedMesh || (r && IsFoliage(r))) continue;
                if (mf.GetComponent<Collider>()) continue;
                var mc = mf.gameObject.AddComponent<MeshCollider>();
                mc.sharedMesh = mf.sharedMesh;
            }
        }

        public static bool IsFoliage(Renderer r)
        {
            foreach (var m in r.sharedMaterials) if (m && FoliageMats.Contains(m.name)) return true;
            return false;
        }

        /// <summary>Dynamic items: helper boxes, or one box around the renderers.</summary>
        public static void AddDynamicColliders(GameObject root)
        {
            if (ConvertHelperColliders(root) > 0) return;
            var b = KitLibrary.RenderBounds(root);
            var bc = root.AddComponent<BoxCollider>();
            bc.center = root.transform.InverseTransformPoint(b.center);
            bc.size = Vector3.Max(b.size, Vector3.one * 0.03f);
        }

        public static void SetStatic(GameObject root, bool isStatic)
        {
            var flags = isStatic
                ? StaticEditorFlags.BatchingStatic | StaticEditorFlags.OccluderStatic | StaticEditorFlags.OccludeeStatic | StaticEditorFlags.ReflectionProbeStatic
                : 0;
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
                GameObjectUtility.SetStaticEditorFlags(t.gameObject, flags);
        }

        public static void ShadowsFor(GameObject root, bool cast)
        {
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
                r.shadowCastingMode = cast ? UnityEngine.Rendering.ShadowCastingMode.On : UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        public static void SurfaceFromMaterials(GameObject root)
        {
            foreach (var c in root.GetComponentsInChildren<Collider>(true))
            {
                if (c.GetComponent<Surface>()) continue;
                var r = c.GetComponent<Renderer>() ?? c.GetComponentInParent<Renderer>() ?? root.GetComponentInChildren<Renderer>();
                if (!r || !r.sharedMaterial) continue;
                var s = c.gameObject.AddComponent<Surface>();
                s.kind = Surface.FromName(r.sharedMaterial.name);
            }
        }

        public static Light AddLight(Transform parent, string name, LightType type, Color color, float range, float intensity, Vector3 localPos, bool important = false)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var l = go.AddComponent<Light>();
            l.type = type; l.color = color; l.range = range; l.intensity = intensity;
            l.shadows = LightShadows.None;
            l.renderMode = important ? LightRenderMode.ForcePixel : LightRenderMode.Auto;
            return l;
        }

        public static TextMesh AddText(Transform parent, string name, Vector3 localPos, Quaternion localRot, float lineHeight, TextAnchor anchor, Color c, string text = "")
        {
            var tm = TextUtil.Create(parent, name, localPos, lineHeight, anchor, c);
            tm.transform.localRotation = localRot;
            tm.text = text;
            return tm;
        }

        /// <summary>Rotation for text lying on a flat screen quad: the quad's average mesh normal points at
        /// the viewer; TextMesh is readable looking along its +Z, so +Z must point into the screen.</summary>
        public static Quaternion TextRotationOnQuad(Transform quad, out Vector3 normalLocal)
        {
            normalLocal = Vector3.forward;
            var mf = quad ? quad.GetComponent<MeshFilter>() : null;
            if (mf && mf.sharedMesh && mf.sharedMesh.normals.Length > 0)
            {
                var sum = Vector3.zero;
                foreach (var n in mf.sharedMesh.normals) sum += n;
                if (sum.sqrMagnitude > 0.0001f) normalLocal = sum.normalized;
            }
            var up = Mathf.Abs(Vector3.Dot(normalLocal, Vector3.up)) > 0.9f ? Vector3.forward : Vector3.up;
            return Quaternion.LookRotation(-normalLocal, up);
        }

        /// <summary>Quad mesh whose UVs cover one cell of a 4×4 atlas (row 0 at the top).</summary>
        public static Mesh AtlasQuad(int cell, float width, float height)
        {
            MNFPaths.Ensure(MNFPaths.Generated + "/Meshes");
            string path = $"{MNFPaths.Generated}/Meshes/AtlasQuad_{cell}_{width:0.00}x{height:0.00}.asset";
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (existing) return existing;
            int col = cell % 4, row = cell / 4;
            float u0 = col * 0.25f, v1 = 1f - row * 0.25f, u1 = u0 + 0.25f, v0 = v1 - 0.25f;
            float pad = 0.004f;
            u0 += pad; u1 -= pad; v0 += pad; v1 -= pad;
            var m = new Mesh { name = "AtlasQuad_" + cell };
            float w = width * 0.5f, h = height * 0.5f;
            // faces +Z (the side a player standing in front of it sees)
            m.vertices = new[] { new Vector3(w, -h, 0), new Vector3(-w, -h, 0), new Vector3(-w, h, 0), new Vector3(w, h, 0) };
            m.uv = new[] { new Vector2(u0, v0), new Vector2(u1, v0), new Vector2(u1, v1), new Vector2(u0, v1) };
            m.triangles = new[] { 0, 2, 1, 0, 3, 2 };
            m.normals = new[] { Vector3.forward, Vector3.forward, Vector3.forward, Vector3.forward };
            m.tangents = new[] { new Vector4(-1, 0, 0, 1), new Vector4(-1, 0, 0, 1), new Vector4(-1, 0, 0, 1), new Vector4(-1, 0, 0, 1) };
            m.RecalculateBounds();
            AssetDatabase.CreateAsset(m, path);
            return m;
        }

        public static GameObject Primitive(PrimitiveType t, string name, Transform parent, Vector3 pos, Vector3 scale, string material)
        {
            var go = GameObject.CreatePrimitive(t);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            var r = go.GetComponent<Renderer>();
            if (r) r.sharedMaterial = MaterialFactory.GetOrFallback(material);
            return go;
        }
    }
}
