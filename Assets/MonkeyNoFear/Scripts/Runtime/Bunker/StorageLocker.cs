using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Bunker
{
    /// <summary>Persistent storage. Items left in the locker hopper for a moment are filed into the stash
    /// (saved). Withdraw them from the terminal's STORAGE page; they arrive through the dispenser tube.</summary>
    public class StorageLocker : MonoBehaviour
    {
        public ItemZone hopper = new ItemZone();
        public TextMesh label;
        public float settleSeconds = 0.8f;

        readonly List<ItemInstance> _items = new List<ItemInstance>();
        readonly Dictionary<ItemInstance, float> _time = new Dictionary<ItemInstance, float>();
        readonly List<ItemInstance> _remove = new List<ItemInstance>();
        float _labelTimer;

        void Update()
        {
            hopper.Collect(_items);
            float now = Time.time;
            foreach (var i in _items)
            {
                if (!i.definition.storable || i.IsTool) continue;
                if (!_time.TryGetValue(i, out float t)) { _time[i] = now; continue; }
                if (now - t < settleSeconds) continue;
                GameRoot.I?.Progress.AddToStash(i.definition.id);
                AudioManager.Instance?.PlayAt("sell_vacuum", hopper.frame ? hopper.frame.position : transform.position, 0.5f, 1.3f);
                _remove.Add(i);
            }
            foreach (var i in _remove) { _time.Remove(i); if (i) Destroy(i.gameObject); }
            if (_remove.Count > 0) GameRoot.I?.SaveNow();
            _remove.Clear();
            // forget items that left the hopper
            if (_time.Count > _items.Count)
            {
                var keys = new List<ItemInstance>(_time.Keys);
                foreach (var k in keys) if (!k || !_items.Contains(k)) _time.Remove(k);
            }

            _labelTimer -= Time.deltaTime;
            if (label && _labelTimer <= 0f && GameRoot.I)
            {
                _labelTimer = 0.5f;
                int n = 0;
                foreach (var s in GameRoot.I.Progress.Stash) n += s.count;
                label.text = $"STORAGE\n{n} ITEMS  ${GameRoot.I.Progress.StashValue()}";
            }
        }

        void OnDrawGizmos() => hopper.DrawGizmo(new Color(0.3f, 0.8f, 1f));
    }
}
