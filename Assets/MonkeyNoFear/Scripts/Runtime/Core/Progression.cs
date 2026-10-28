using System.Collections.Generic;
using MonkeyNoFear.Data;

namespace MonkeyNoFear.Core
{
    /// <summary>Currency, stash, owned equipment, upgrades, flags, discoveries and lore — a facade over
    /// SaveData so gameplay code never edits the save directly.</summary>
    public class Progression
    {
        readonly SaveSystem _save;
        readonly ItemDatabase _db;
        SaveData D => _save.Data;

        public Progression(SaveSystem save, ItemDatabase db) { _save = save; _db = db; }

        // ---------------- currency ----------------
        public int Currency => D.currency;

        public void AddCurrency(int amount)
        {
            if (amount <= 0) return;
            D.currency += amount;
            D.stats.totalEarned += amount;
            _save.MarkDirty();
            GameEvents.RaiseCurrencyChanged(D.currency, amount);
        }

        public bool TrySpend(int amount)
        {
            if (amount < 0 || D.currency < amount) return false;
            D.currency -= amount;
            _save.MarkDirty();
            GameEvents.RaiseCurrencyChanged(D.currency, -amount);
            return true;
        }

        // ---------------- stash (storage locker) ----------------
        public int StashCount(string itemId) => D.GetCount(D.stash, itemId);
        public IReadOnlyList<ItemStack> Stash => D.stash;

        public void AddToStash(string itemId, int count = 1)
        {
            D.AddCount(D.stash, itemId, count);
            _save.MarkDirty();
            GameEvents.RaiseInventoryChanged();
        }

        public bool TakeFromStash(string itemId, int count = 1)
        {
            if (StashCount(itemId) < count) return false;
            D.AddCount(D.stash, itemId, -count);
            _save.MarkDirty();
            GameEvents.RaiseInventoryChanged();
            return true;
        }

        public int StashValue()
        {
            int v = 0;
            foreach (var s in D.stash)
            {
                var def = _db ? _db.GetItem(s.id) : null;
                if (def && def.sellable) v += def.sellValue * s.count;
            }
            return v;
        }

        // ---------------- equipment ----------------
        public bool OwnsTool(string toolId) => D.ownedTools.Contains(toolId);
        public IReadOnlyList<string> OwnedTools => D.ownedTools;

        public void GrantTool(string toolId)
        {
            if (OwnsTool(toolId)) return;
            D.ownedTools.Add(toolId);
            _save.MarkDirty();
            GameEvents.RaiseInventoryChanged();
        }

        public bool HasUpgrade(string id) => D.upgrades.Contains(id);

        public void GrantUpgrade(string id)
        {
            if (HasUpgrade(id)) return;
            D.upgrades.Add(id);
            _save.MarkDirty();
            GameEvents.RaiseInventoryChanged();
        }

        public int PurchaseCount(string entryId) => D.GetCount(D.purchases, entryId);
        public void RecordPurchase(string entryId) { D.AddCount(D.purchases, entryId, 1); _save.MarkDirty(); }

        // ---------------- upgrade effects (single place for the numbers) ----------------
        public int BackpackCapacity => 6 + (HasUpgrade("backpack_1") ? 4 : 0) + (HasUpgrade("backpack_2") ? 6 : 0);
        public float BatteryMultiplier => HasUpgrade("battery_1") ? 2f : 1f;
        public float DamageTakenMultiplier => HasUpgrade("armor_1") ? 0.7f : 1f;
        public int BestPickaxeTier => OwnsTool("pickaxe_t3") ? 3 : OwnsTool("pickaxe_t2") ? 2 : 1;

        // ---------------- flags / discoveries / lore ----------------
        public bool HasFlag(string f) => D.flags.Contains(f);
        public void SetFlag(string f) { if (!HasFlag(f)) { D.flags.Add(f); _save.MarkDirty(); } }

        public bool IsDiscovered(string id) => D.discoveries.Contains(id);
        public IReadOnlyList<string> Discoveries => D.discoveries;

        /// <summary>Returns true the first time.</summary>
        public bool Discover(string id)
        {
            if (string.IsNullOrEmpty(id) || IsDiscovered(id)) return false;
            D.discoveries.Add(id);
            _save.MarkDirty();
            GameEvents.RaiseDiscovery(id);
            return true;
        }

        public bool HasLore(string id) => D.lore.Contains(id);
        public IReadOnlyList<string> Lore => D.lore;

        public bool UnlockLore(string id)
        {
            if (string.IsNullOrEmpty(id) || HasLore(id)) return false;
            D.lore.Add(id);
            _save.MarkDirty();
            GameEvents.RaiseLore(id);
            return true;
        }

        /// <summary>Generic requirement check used by the shop: a tool, upgrade, flag or discovery id.</summary>
        public bool MeetsRequirement(string req)
        {
            if (string.IsNullOrEmpty(req)) return true;
            return OwnsTool(req) || HasUpgrade(req) || HasFlag(req) || IsDiscovered(req);
        }

        public PlayerStats Stats => D.stats;
        public SettingsData Settings => D.settings;
        public void MarkDirty() => _save.MarkDirty();
    }
}
