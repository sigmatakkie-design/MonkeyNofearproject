using System;
using UnityEngine;

namespace MonkeyNoFear.Core
{
    public enum AreaId { None = 0, Bunker = 1, Corridor = 2, Forest = 3, MineShallow = 4, MineMid = 5, MineDeep = 6 }

    /// <summary>Global, allocation-free game events. Systems subscribe in OnEnable and unsubscribe in OnDisable.</summary>
    public static class GameEvents
    {
        public static event Action<int, int> CurrencyChanged;          // (newBalance, delta)
        public static event Action<AreaId, AreaId> AreaChanged;        // (from, to)
        public static event Action<float, Vector3> PlayerDamaged;      // (amount, sourcePosition)
        public static event Action PlayerDied;
        public static event Action PlayerRespawned;
        public static event Action<string> DiscoveryUnlocked;          // discovery id
        public static event Action<string> LoreUnlocked;               // lore id
        public static event Action ExpeditionStarted;
        public static event Action<ExpeditionSummary> ExpeditionEnded;
        public static event Action SaveLoaded;
        public static event Action InventoryChanged;
        public static event Action<string> ToastMessage;               // short status line for wrist/terminal

        public static void RaiseCurrencyChanged(int balance, int delta) => CurrencyChanged?.Invoke(balance, delta);
        public static void RaiseAreaChanged(AreaId from, AreaId to) => AreaChanged?.Invoke(from, to);
        public static void RaisePlayerDamaged(float amount, Vector3 src) => PlayerDamaged?.Invoke(amount, src);
        public static void RaisePlayerDied() => PlayerDied?.Invoke();
        public static void RaisePlayerRespawned() => PlayerRespawned?.Invoke();
        public static void RaiseDiscovery(string id) => DiscoveryUnlocked?.Invoke(id);
        public static void RaiseLore(string id) => LoreUnlocked?.Invoke(id);
        public static void RaiseExpeditionStarted() => ExpeditionStarted?.Invoke();
        public static void RaiseExpeditionEnded(ExpeditionSummary s) => ExpeditionEnded?.Invoke(s);
        public static void RaiseSaveLoaded() => SaveLoaded?.Invoke();
        public static void RaiseInventoryChanged() => InventoryChanged?.Invoke();
        public static void Toast(string msg) => ToastMessage?.Invoke(msg);
    }

    [Serializable]
    public struct ExpeditionSummary
    {
        public float durationSeconds;
        public int deepestLevel;
        public int itemsCarriedBack;
        public int valueCarriedBack;
        public bool died;
    }
}
