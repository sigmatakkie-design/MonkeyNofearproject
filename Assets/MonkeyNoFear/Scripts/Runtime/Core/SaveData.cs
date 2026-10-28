using System;
using System.Collections.Generic;

namespace MonkeyNoFear.Core
{
    /// <summary>Everything that persists between sessions. Temporary world state (creature positions,
    /// deposits, dropped items) is intentionally not saved; each expedition re-rolls it.</summary>
    [Serializable]
    public class SaveData
    {
        public const int CurrentVersion = 2;

        public int version = CurrentVersion;
        public int currency;
        public List<string> ownedTools = new List<string>();
        public List<string> upgrades = new List<string>();
        public List<ItemStack> stash = new List<ItemStack>();
        public List<string> discoveries = new List<string>();
        public List<string> lore = new List<string>();
        public List<string> flags = new List<string>();          // world progression, e.g. "elevator_powered"
        public List<ItemStack> purchases = new List<ItemStack>(); // purchase counts per shop entry id
        public PlayerStats stats = new PlayerStats();
        public SettingsData settings = new SettingsData();

        public static SaveData CreateNew(int startingCurrency, IEnumerable<string> startingTools)
        {
            var d = new SaveData { currency = startingCurrency };
            if (startingTools != null) d.ownedTools.AddRange(startingTools);
            return d;
        }

        /// <summary>Repairs nulls from old or hand-edited files and upgrades older versions.</summary>
        public void Sanitize(int startingCurrency, IEnumerable<string> startingTools)
        {
            ownedTools ??= new List<string>();
            upgrades ??= new List<string>();
            stash ??= new List<ItemStack>();
            discoveries ??= new List<string>();
            lore ??= new List<string>();
            flags ??= new List<string>();
            purchases ??= new List<ItemStack>();
            stats ??= new PlayerStats();
            settings ??= new SettingsData();
            stash.RemoveAll(s => s == null || string.IsNullOrEmpty(s.id) || s.count <= 0);
            if (currency < 0) currency = 0;

            if (version < 2)
            {
                // v1 saves had no starting tools recorded; grant them so nobody is soft-locked.
                if (startingTools != null)
                    foreach (var t in startingTools)
                        if (!ownedTools.Contains(t)) ownedTools.Add(t);
            }
            version = CurrentVersion;
        }

        public int GetCount(List<ItemStack> list, string id)
        {
            foreach (var s in list) if (s.id == id) return s.count;
            return 0;
        }

        public void AddCount(List<ItemStack> list, string id, int delta)
        {
            for (int i = 0; i < list.Count; i++)
            {
                if (list[i].id != id) continue;
                list[i].count += delta;
                if (list[i].count <= 0) list.RemoveAt(i);
                return;
            }
            if (delta > 0) list.Add(new ItemStack { id = id, count = delta });
        }
    }

    [Serializable]
    public class ItemStack
    {
        public string id;
        public int count;
    }

    [Serializable]
    public class PlayerStats
    {
        public int expeditions;
        public int deaths;
        public int deepestLevel;
        public int totalEarned;
        public int oreMined;
        public int animalsHunted;
        public int itemsSold;
        public float playSeconds;
        public float longestExpeditionSeconds;
    }

    [Serializable]
    public class SettingsData
    {
        public bool snapTurn = true;
        public float snapTurnDegrees = 45f;
        public bool joystickLocomotion = false;   // accessibility: optional, off by default
        public bool comfortVignette = true;
        public float avatarScale = 1f;
        public bool dominantLeft = false;
    }
}
