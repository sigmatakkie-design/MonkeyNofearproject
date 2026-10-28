using System;
using System.Collections.Generic;
using UnityEngine;

namespace MonkeyNoFear.Data
{
    public enum ShopEntryKind { Tool, Consumable, Upgrade }

    [Serializable]
    public class ShopEntry
    {
        public string id;
        public string displayName;
        [TextArea] public string description;
        public ShopEntryKind kind;
        [Min(0)] public int price = 50;
        [Tooltip("Tool: tool id granted. Consumable: item id dispensed. Upgrade: upgrade id applied.")]
        public string grantId;
        [Min(1)] public int quantity = 1;
        [Tooltip("0 = unlimited (consumables). Tools and upgrades are normally 1.")]
        [Min(0)] public int maxPurchases = 1;
        [Tooltip("Optional: tool/upgrade/flag/discovery id that must be owned first.")]
        public string requires;
        [Tooltip("Shown when locked.")]
        public string requiresLabel;
    }

    [CreateAssetMenu(menuName = "Monkey No Fear/Shop Catalog", fileName = "ShopCatalog")]
    public class ShopCatalog : ScriptableObject
    {
        public List<ShopEntry> entries = new List<ShopEntry>();

        public ShopEntry Find(string id)
        {
            foreach (var e in entries) if (e.id == id) return e;
            return null;
        }
    }
}
