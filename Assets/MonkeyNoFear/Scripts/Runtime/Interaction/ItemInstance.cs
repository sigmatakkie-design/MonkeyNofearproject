using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Data;

namespace MonkeyNoFear.Interaction
{
    /// <summary>Links a physical object to its ItemDefinition. Keeps a registry of live items so stations
    /// and the tool recall can find them without scene searches.</summary>
    public class ItemInstance : MonoBehaviour
    {
        public static readonly List<ItemInstance> All = new List<ItemInstance>();

        public ItemDefinition definition;
        [Tooltip("Set on permanent tools: the id in ItemDatabase.tools.")]
        public string toolId;

        public bool IsTool => !string.IsNullOrEmpty(toolId);
        public Grabbable Grab => _grab ? _grab : (_grab = GetComponent<Grabbable>());
        Grabbable _grab;
        void OnEnable() { if (!All.Contains(this)) All.Add(this); }
        void OnDestroy() { All.Remove(this); }

        public static ItemInstance Spawn(ItemDefinition def, Vector3 pos, Quaternion rot)
        {
            if (!def) return null;
            GameObject go;
            if (def.prefab) go = Instantiate(def.prefab, pos, rot);
            else
            {
                // missing prefab: still give the player a usable physical item instead of nothing
                go = GameObject.CreatePrimitive(PrimitiveType.Cube);
                go.transform.SetPositionAndRotation(pos, rot);
                go.transform.localScale = Vector3.one * 0.12f;
                go.name = def.displayName + " (fallback)";
                go.AddComponent<Rigidbody>().mass = def.mass;
                go.AddComponent<ItemInstance>(); // before Grabbable, which links its item in Awake
                go.AddComponent<Grabbable>();
                Debug.LogWarning($"[Item] '{def.id}' has no prefab — spawned a fallback cube.");
            }
            var inst = go.GetComponent<ItemInstance>();
            if (!inst) inst = go.AddComponent<ItemInstance>();
            inst.definition = def;
            Core.Layers.SetLayerRecursive(go, Core.Layers.Item);
            return inst;
        }
    }
}
