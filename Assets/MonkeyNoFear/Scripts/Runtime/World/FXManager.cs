using System.Collections.Generic;
using UnityEngine;

namespace MonkeyNoFear.World
{
    /// <summary>Pooled particle bursts: one ParticleSystem per effect type, emitted with per-burst
    /// position/colour overrides (no instantiation at runtime).</summary>
    public class FXManager : MonoBehaviour
    {
        public static FXManager Instance { get; private set; }

        [System.Serializable]
        public class Effect
        {
            public string name;
            public ParticleSystem system;
            public float speed = 2f;
            public float spread = 0.7f;
        }

        public List<Effect> effects = new List<Effect>();
        readonly Dictionary<string, Effect> _map = new Dictionary<string, Effect>();

        void Awake()
        {
            Instance = this;
            foreach (var e in effects) if (e != null && e.system) _map[e.name] = e;
        }

        /// <summary>Emits <paramref name="count"/> particles at a point, sprayed around a normal.</summary>
        public static void Burst(string name, Vector3 pos, Vector3 normal, Color color, int count)
        {
            if (!Instance || !Instance._map.TryGetValue(name, out var e)) return;
            var p = new ParticleSystem.EmitParams { applyShapeToPosition = false };
            if (normal.sqrMagnitude < 0.001f) normal = Vector3.up;
            for (int i = 0; i < count; i++)
            {
                p.position = pos + Random.insideUnitSphere * 0.03f;
                var dir = (normal + Random.insideUnitSphere * e.spread).normalized;
                p.velocity = dir * e.speed * Random.Range(0.5f, 1.3f);
                p.startColor = color * Random.Range(0.75f, 1.1f);
                e.system.Emit(p, 1);
            }
        }
    }
}
