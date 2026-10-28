using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Player
{
    /// <summary>
    /// Over-the-shoulder backpack. Release a storable item behind your head to store it; grab behind your
    /// head with an empty hand to pull the last item back out. Stored objects are kept (deactivated) so
    /// their state survives. Capacity comes from upgrades. Contents are lost on death (dropped as a pack
    /// that can be recovered from where you died).
    /// </summary>
    public class Backpack : MonoBehaviour
    {
        public static Backpack Instance { get; private set; }

        [Tooltip("Zone centre in BodyFrame space (behind and slightly below the head).")]
        public Vector3 zoneLocal = new Vector3(0f, -0.12f, -0.22f);
        public float zoneRadius = 0.24f;
        public Transform bodyFrame;
        public Transform container;

        readonly List<Grabbable> _items = new List<Grabbable>();
        public int Count => _items.Count;
        public int Capacity => GameRoot.I ? GameRoot.I.Progress.BackpackCapacity : 6;
        public IReadOnlyList<Grabbable> Items => _items;

        public int TotalValue
        {
            get
            {
                int v = 0;
                foreach (var g in _items)
                    if (g && g.Item && g.Item.definition && g.Item.definition.sellable) v += g.Item.definition.sellValue;
                return v;
            }
        }

        void Awake()
        {
            Instance = this;
            if (!container)
            {
                container = new GameObject("BackpackContents").transform;
                container.SetParent(transform, false);
            }
        }

        public Vector3 ZoneCentre => bodyFrame ? bodyFrame.TransformPoint(zoneLocal) : transform.position;
        public bool IsInZone(Vector3 p) => (p - ZoneCentre).sqrMagnitude < zoneRadius * zoneRadius;

        public bool CanStore(Grabbable g)
        {
            if (!g || !g.Item || !g.Item.definition || !g.Item.definition.storable) return false;
            if (g.Item.IsTool) return false; // tools go on holsters / the rack
            if (Count >= Capacity)
            {
                GameEvents.Toast("BACKPACK FULL");
                AudioManager.Instance?.PlayAt("terminal_error", ZoneCentre, 0.4f);
                return false;
            }
            return true;
        }

        public void Store(Grabbable g)
        {
            _items.Add(g);
            g.MakeStowed(container);
            g.gameObject.SetActive(false);
            AudioManager.Instance?.PlayAt("backpack_store", ZoneCentre, 0.7f);
            GameEvents.RaiseInventoryChanged();
        }

        public Grabbable TakeLast(Vector3 at, Quaternion rot)
        {
            if (_items.Count == 0) return null;
            var g = _items[_items.Count - 1];
            _items.RemoveAt(_items.Count - 1);
            if (!g) return null;
            g.gameObject.SetActive(true);
            g.MakeLoose();
            g.transform.SetPositionAndRotation(at, rot);
            AudioManager.Instance?.PlayAt("backpack_take", at, 0.6f);
            GameEvents.RaiseInventoryChanged();
            return g;
        }

        /// <summary>Removes everything matching the predicate (used by "sell pack" at the trade machine).</summary>
        public List<Grabbable> RemoveWhere(System.Predicate<Grabbable> match)
        {
            var removed = new List<Grabbable>();
            for (int i = _items.Count - 1; i >= 0; i--)
                if (_items[i] && match(_items[i])) { removed.Add(_items[i]); _items.RemoveAt(i); }
            if (removed.Count > 0) GameEvents.RaiseInventoryChanged();
            return removed;
        }

        /// <summary>Empties the backpack into a recoverable lost pack at the given position.</summary>
        public void DropAllAsLostPack(Vector3 position)
        {
            if (_items.Count == 0) return;
            var prefab = GameRoot.I ? GameRoot.I.lostPackPrefab : null;
            GameObject go = prefab ? Instantiate(prefab, position + Vector3.up * 0.3f, Quaternion.identity) : new GameObject("LostPack");
            if (!prefab) go.transform.position = position + Vector3.up * 0.3f;
            var pack = go.GetComponent<LostPack>();
            if (!pack) pack = go.AddComponent<LostPack>();
            foreach (var g in _items) if (g) { g.transform.SetParent(go.transform, false); pack.contents.Add(g); }
            _items.Clear();
            GameEvents.RaiseInventoryChanged();
        }
    }
}
