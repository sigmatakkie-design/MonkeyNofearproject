using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Data;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Bunker
{
    /// <summary>Pneumatic delivery tube on the workbench: purchases and storage withdrawals arrive here one
    /// at a time with a thunk, so they never spawn inside each other.</summary>
    public class ItemDispenser : MonoBehaviour
    {
        public static ItemDispenser Instance { get; private set; }

        public Transform outlet;
        public float interval = 0.7f;
        readonly Queue<ItemDefinition> _queue = new Queue<ItemDefinition>();
        float _timer;

        void Awake() { Instance = this; if (!outlet) outlet = transform; }

        public void Enqueue(ItemDefinition def, int count = 1)
        {
            if (!def) return;
            for (int i = 0; i < count; i++) _queue.Enqueue(def);
        }

        public int Pending => _queue.Count;

        void Update()
        {
            if (_queue.Count == 0) return;
            _timer -= Time.deltaTime;
            if (_timer > 0f) return;
            _timer = interval;
            var def = _queue.Dequeue();
            var pos = outlet.position + Random.insideUnitSphere * 0.05f;
            var item = ItemInstance.Spawn(def, pos, outlet.rotation * Quaternion.Euler(0f, Random.Range(0f, 360f), 0f));
            var rb = item ? item.GetComponent<Rigidbody>() : null;
            if (rb) rb.velocity = outlet.forward * 0.6f;
            AudioManager.Instance?.PlayAt("dispenser_thunk", outlet.position, 0.9f);
            World.FXManager.Burst("dust", outlet.position, outlet.forward, new Color(0.7f, 0.7f, 0.7f, 0.4f), 6);
        }
    }
}
