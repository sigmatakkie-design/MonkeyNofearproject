using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>Index of every top-level object in the prop kit FBX files, so builders can copy one object
    /// (with its children, helpers and mesh references) into a new prefab.</summary>
    public static class KitLibrary
    {
        static Dictionary<string, GameObject> _objects;
        public static readonly string[] Kits = { "Kit_Tools", "Kit_Deposits", "Kit_Bunker", "Kit_Forest", "Kit_Mine" };

        public static void Refresh()
        {
            _objects = new Dictionary<string, GameObject>();
            foreach (var kit in Kits)
            {
                var model = AssetDatabase.LoadAssetAtPath<GameObject>($"{MNFPaths.Props}/{kit}.fbx");
                if (!model) { Debug.LogWarning($"[MNF] Kit {kit}.fbx not found — its props will use fallbacks."); continue; }
                foreach (Transform t in model.transform) _objects[t.name] = t.gameObject;
            }
        }

        public static bool Has(string name) { if (_objects == null) Refresh(); return _objects.ContainsKey(name); }
        public static IEnumerable<string> Names { get { if (_objects == null) Refresh(); return _objects.Keys; } }

        /// <summary>Scene copy of a kit object at the origin (no prefab link to the FBX), or null.</summary>
        public static GameObject Copy(string name)
        {
            if (_objects == null) Refresh();
            if (!_objects.TryGetValue(name, out var src)) return null;
            var go = Object.Instantiate(src);
            go.name = name;
            go.transform.localPosition = Vector3.zero;
            go.transform.localRotation = Quaternion.identity;
            go.transform.localScale = Vector3.one;
            return go;
        }

        public static Transform FindDeep(Transform root, string name)
        {
            if (root.name == name) return root;
            foreach (Transform c in root)
            {
                var r = FindDeep(c, name);
                if (r) return r;
            }
            return null;
        }

        public static Transform FindPrefix(Transform root, string prefix)
        {
            foreach (var t in root.GetComponentsInChildren<Transform>(true)) if (t.name.StartsWith(prefix)) return t;
            return null;
        }

        /// <summary>Renderer whose materials include the named catalog material.</summary>
        public static Renderer RendererWithMaterial(GameObject root, string materialName)
        {
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials)
                    if (m && m.name == materialName) return r;
            return null;
        }

        public static Bounds RenderBounds(GameObject root)
        {
            var rs = root.GetComponentsInChildren<Renderer>(true);
            if (rs.Length == 0) return new Bounds(root.transform.position, Vector3.one * 0.2f);
            var b = rs[0].bounds;
            foreach (var r in rs) if (!r.name.StartsWith("COL_")) b.Encapsulate(r.bounds);
            return b;
        }
    }
}
