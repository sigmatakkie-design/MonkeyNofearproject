using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;
using MonkeyNoFear.AI.Creatures;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.AI.Wildlife
{
    /// <summary>
    /// Keeps a population of wildlife alive in authored spawn areas. Every expedition re-rolls the animals;
    /// animals that die or wander off are replaced only while the player is far away (no pop-in).
    /// Falsekin are a deliberate, limited subset: a configured number of the rabbit areas get one mimic,
    /// which is placed among (and dressed as) the real rabbits.
    /// </summary>
    public class WildlifeSpawner : MonoBehaviour, IExpeditionReset
    {
        [System.Serializable]
        public class Area
        {
            public Transform centre;
            public float radius = 12f;
            public GameObject prefab;
            public int count = 3;
            [Tooltip("Areas where a Falsekin may hide among this species.")]
            public bool falsekinAllowed;
            [HideInInspector] public List<GameObject> live = new List<GameObject>();
        }

        public List<Area> areas = new List<Area>();
        public List<Falsekin> falsekin = new List<Falsekin>();
        [Tooltip("How many Falsekin are active per expedition (taken from the list above).")]
        public int falsekinPerExpedition = 1;
        public float respawnCheck = 45f;
        public float minPlayerDistance = 55f;

        float _timer;
        System.Random _rng = new System.Random(1);

        void OnEnable() => ExpeditionManager.Register(this);
        void OnDisable() => ExpeditionManager.Unregister(this);

        public void OnNewExpedition(int index, System.Random rng)
        {
            _rng = rng;
            foreach (var a in areas)
            {
                foreach (var g in a.live) if (g) Destroy(g);
                a.live.Clear();
                for (int i = 0; i < a.count; i++) SpawnIn(a);
            }
            PlaceFalsekin(rng);
        }

        void PlaceFalsekin(System.Random rng)
        {
            var candidates = areas.FindAll(a => a.falsekinAllowed && a.centre);
            for (int i = 0; i < falsekin.Count; i++)
            {
                var f = falsekin[i];
                if (!f || !f.IsAlive) continue; // a killed one stays where it fell until it is cleaned up
                bool active = i < falsekinPerExpedition && candidates.Count > 0;
                f.gameObject.SetActive(active);
                if (!active) continue;
                var area = candidates[rng.Next(candidates.Count)];
                if (RandomPoint(area.centre.position, area.radius, out var p))
                {
                    var ag = f.GetComponent<NavMeshAgent>();
                    if (ag && ag.isOnNavMesh) ag.Warp(p); else f.transform.position = p;
                }
            }
        }

        void SpawnIn(Area a)
        {
            if (!a.prefab || !a.centre) return;
            if (!RandomPoint(a.centre.position, a.radius, out var p)) return;
            var go = Instantiate(a.prefab, p, Quaternion.Euler(0f, (float)_rng.NextDouble() * 360f, 0f), transform);
            a.live.Add(go);
        }

        static bool RandomPoint(Vector3 c, float r, out Vector3 p)
        {
            for (int i = 0; i < 10; i++)
            {
                var o = Random.insideUnitSphere * r; o.y = 0f;
                if (NavMesh.SamplePosition(c + o, out var hit, 4f, NavMesh.AllAreas)) { p = hit.position; return true; }
            }
            p = c; return false;
        }

        void Update()
        {
            _timer -= Time.deltaTime;
            if (_timer > 0f) return;
            _timer = respawnCheck;
            var rig = PlayerRig.Instance;
            foreach (var a in areas)
            {
                a.live.RemoveAll(g => !g);
                if (!a.centre || a.live.Count >= a.count) continue;
                if (rig && Vector3.Distance(rig.HeadPosition, a.centre.position) < minPlayerDistance) continue;
                SpawnIn(a);
            }
        }

        void OnDrawGizmos()
        {
            foreach (var a in areas)
            {
                if (!a.centre) continue;
                Gizmos.color = a.falsekinAllowed ? new Color(1f, 0.3f, 0.3f, 0.4f) : new Color(0.4f, 1f, 0.4f, 0.4f);
                Gizmos.DrawWireSphere(a.centre.position, a.radius);
            }
        }
    }
}
