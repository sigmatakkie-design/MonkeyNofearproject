using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Data;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Mining
{
    /// <summary>Re-rolls which candidate points hold deposits and which mineral each gets, every expedition,
    /// using per-zone rarity weights from the MineralDefinitions. Deeper zones hold rarer minerals.</summary>
    public class ResourceDistributor : MonoBehaviour, IExpeditionReset
    {
        public List<MineralDefinition> minerals = new List<MineralDefinition>();
        public List<OreSpawnPoint> points = new List<OreSpawnPoint>();

        void OnEnable() => ExpeditionManager.Register(this);
        void OnDisable() => ExpeditionManager.Unregister(this);

        public void OnNewExpedition(int index, System.Random rng)
        {
            int spawned = 0;
            foreach (var p in points)
            {
                if (!p) continue;
                if (p.current) { Destroy(p.current.gameObject); p.current = null; }
                if (rng.NextDouble() > p.activeChance) continue;
                var m = Pick(p.zone, rng);
                if (!m) continue;
                var prefab = p.wallMounted && m.wallDepositPrefab ? m.wallDepositPrefab : m.depositPrefab;
                if (!prefab) continue;
                var rot = p.transform.rotation;
                if (!p.wallMounted) rot *= Quaternion.Euler(0f, (float)rng.NextDouble() * 360f, 0f);
                var go = Instantiate(prefab, p.transform.position, rot, p.transform);
                float s = 0.85f + (float)rng.NextDouble() * 0.35f;
                go.transform.localScale = Vector3.one * s;
                var dep = go.GetComponent<OreDeposit>();
                if (!dep) dep = go.AddComponent<OreDeposit>();
                dep.Init(m, rng);
                p.current = dep;
                spawned++;
            }
            Debug.Log($"[Resources] Expedition {index}: {spawned}/{points.Count} deposits");
        }

        MineralDefinition Pick(DepthZone z, System.Random rng)
        {
            float total = 0f;
            foreach (var m in minerals) if (m) total += m.WeightFor(z);
            if (total <= 0f) return null;
            float r = (float)rng.NextDouble() * total;
            foreach (var m in minerals)
            {
                if (!m) continue;
                r -= m.WeightFor(z);
                if (r <= 0f) return m;
            }
            return minerals[minerals.Count - 1];
        }
    }
}
