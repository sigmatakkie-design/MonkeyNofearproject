using System.Collections.Generic;
using UnityEngine;

namespace MonkeyNoFear.Data
{
    /// <summary>Permanent equipment (one physical instance each, lives on the bunker tool rack).</summary>
    [System.Serializable]
    public class ToolEntry
    {
        public string id;
        public ItemDefinition item;
        [Tooltip("Tool rack socket index this tool returns to.")]
        public int rackSlot;
    }

    /// <summary>Lookup tables for every item, mineral and tool. One asset, referenced by GameRoot.</summary>
    [CreateAssetMenu(menuName = "Monkey No Fear/Item Database", fileName = "ItemDatabase")]
    public class ItemDatabase : ScriptableObject
    {
        public List<ItemDefinition> items = new List<ItemDefinition>();
        public List<MineralDefinition> minerals = new List<MineralDefinition>();
        public List<ToolEntry> tools = new List<ToolEntry>();
        [Tooltip("Tools every new save starts with.")]
        public List<string> startingTools = new List<string> { "pickaxe_t1", "flashlight" };
        public int startingCurrency = 25;

        Dictionary<string, ItemDefinition> _items;
        Dictionary<string, ToolEntry> _tools;

        void Build()
        {
            _items = new Dictionary<string, ItemDefinition>();
            foreach (var i in items) if (i && !string.IsNullOrEmpty(i.id)) _items[i.id] = i;
            _tools = new Dictionary<string, ToolEntry>();
            foreach (var t in tools) if (t != null && !string.IsNullOrEmpty(t.id)) _tools[t.id] = t;
        }

        public ItemDefinition GetItem(string id)
        {
            if (_items == null) Build();
            return id != null && _items.TryGetValue(id, out var d) ? d : null;
        }

        public ToolEntry GetTool(string id)
        {
            if (_tools == null) Build();
            return id != null && _tools.TryGetValue(id, out var t) ? t : null;
        }

        public ToolEntry GetToolForItem(ItemDefinition item)
        {
            foreach (var t in tools) if (t.item == item) return t;
            return null;
        }

        void OnValidate() { _items = null; _tools = null; }
    }
}
