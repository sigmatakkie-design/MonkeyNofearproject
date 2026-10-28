using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.AI;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Mining
{
    public struct StrikeInfo
    {
        public int tier;
        public float damage;
        public float noiseMultiplier;
        public Vector3 point, normal;
        public Object instigator;
    }

    /// <summary>
    /// A mineable deposit. Built from the deposit model: `Base` (host rock, stays) and `Chunk_00..N`
    /// (pieces that break off one by one as durability drops). Each broken chunk drops collectible ore.
    /// Strikes are loud — creatures (especially the Borer) hear mining.
    /// </summary>
    public class OreDeposit : MonoBehaviour
    {
        public static readonly List<OreDeposit> Active = new List<OreDeposit>();

        public MineralDefinition mineral;
        public List<Transform> chunks = new List<Transform>();
        public Light glow;

        public float Health { get; private set; }
        public bool Depleted { get; private set; }
        public float Fraction => mineral ? Health / mineral.durability : 0f;

        int _removed, _dropsRemaining, _stages;
        Vector3[] _chunkScale;
        float _shake, _lastDeflectToast = -99f;
        Transform _shakeTarget;
        Vector3 _shakeBase;

        void Awake()
        {
            if (chunks.Count == 0)
                foreach (Transform t in GetComponentsInChildren<Transform>(true))
                    if (t.name.StartsWith("Chunk_")) chunks.Add(t);
            chunks.Sort((a, b) => string.CompareOrdinal(a.name, b.name));
            _chunkScale = new Vector3[chunks.Count];
            for (int i = 0; i < chunks.Count; i++) _chunkScale[i] = chunks[i].localScale;
        }

        void OnEnable() { if (!Active.Contains(this)) Active.Add(this); }
        void OnDisable() => Active.Remove(this);

        public void Init(MineralDefinition def, System.Random rng)
        {
            mineral = def;
            Health = def.durability;
            Depleted = false;
            _removed = 0;
            _stages = Mathf.Max(2, chunks.Count);
            _dropsRemaining = rng.Next(def.dropCount.x, def.dropCount.y + 1);
            for (int i = 0; i < chunks.Count; i++) { chunks[i].gameObject.SetActive(true); chunks[i].localScale = _chunkScale[i]; }
            if (glow)
            {
                glow.enabled = def.glowIntensity > 0f;
                glow.color = def.glowColor;
                glow.intensity = def.glowIntensity;
            }
        }

        public bool Strike(StrikeInfo s)
        {
            if (Depleted || !mineral) return false;
            float noise = mineral.strikeNoise * Mathf.Max(0.1f, s.noiseMultiplier);
            if (s.tier < mineral.requiredTier)
            {
                AudioManager.Instance?.PlayAt("pick_miss_metal", s.point, 0.9f);
                FXManager.Burst("sparks", s.point, s.normal, new Color(1f, 0.8f, 0.4f), 10);
                NoiseSystem.Emit(s.point, noise * 0.8f, NoiseKind.Mining, true, this);
                if (Time.time - _lastDeflectToast > 4f)
                {
                    _lastDeflectToast = Time.time;
                    GameEvents.Toast($"TOO HARD - NEEDS A TIER {mineral.requiredTier} PICK");
                }
                return false;
            }

            Health -= s.damage;
            AudioManager.Instance?.PlayAt(mineral.hitSound, s.point, 1f);
            FXManager.Burst("debris", s.point, s.normal, mineral.particleColor, 14);
            FXManager.Burst("dust", s.point, s.normal, new Color(0.5f, 0.47f, 0.43f, 0.5f), 4);
            NoiseSystem.Emit(s.point, noise, NoiseKind.Mining, true, this);
            GameRoot.I?.Progress.Discover("mineral_" + mineral.id);

            // the next chunk to fall shrinks and shakes on every hit: readable progress
            int next = _removed;
            if (next < chunks.Count)
            {
                float stageSize = mineral.durability / _stages;
                float into = Mathf.Clamp01((mineral.durability - Health - next * stageSize) / stageSize);
                chunks[next].localScale = _chunkScale[next] * Mathf.Lerp(1f, 0.82f, into);
                _shakeTarget = chunks[next];
                _shakeBase = chunks[next].localPosition;
                _shake = 0.12f;
            }

            int stageNow = Mathf.Clamp(Mathf.FloorToInt((1f - Mathf.Max(0f, Health) / mineral.durability) * _stages), 0, _stages);
            while (_removed < stageNow && !Depleted) BreakStage(s);
            if (Health <= 0f && !Depleted) Finish(s);
            return true;
        }

        void BreakStage(StrikeInfo s)
        {
            Vector3 at = s.point;
            if (_removed < chunks.Count)
            {
                var c = chunks[_removed];
                at = c.position;
                if (_shakeTarget == c) { c.localPosition = _shakeBase; _shakeTarget = null; }
                c.gameObject.SetActive(false);
            }
            _removed++;
            bool last = _removed >= _stages;
            int drop = last ? _dropsRemaining : Mathf.Min(_dropsRemaining, Mathf.Max(1, _dropsRemaining / Mathf.Max(1, _stages - _removed + 1)));
            for (int i = 0; i < drop; i++) DropChunk(at, s.normal);
            _dropsRemaining -= drop;
            AudioManager.Instance?.PlayAt(last ? mineral.finalBreakSound : mineral.breakSound, at, 1f);
            FXManager.Burst("debris", at, s.normal, mineral.particleColor, 26);
            FXManager.Burst("dust", at, Vector3.up, new Color(0.5f, 0.47f, 0.43f, 0.5f), 10);
            if (last) Finish(s);
        }

        void Finish(StrikeInfo s)
        {
            if (Depleted) return;
            Depleted = true;
            for (int i = 0; i < _dropsRemaining; i++) DropChunk(transform.position + Vector3.up * 0.4f, s.normal);
            _dropsRemaining = 0;
            foreach (var c in chunks) c.gameObject.SetActive(false);
            if (glow) glow.enabled = false;
            var gr = GameRoot.I;
            if (gr) { gr.Progress.Stats.oreMined++; gr.Progress.MarkDirty(); }
            NoiseSystem.Emit(transform.position, mineral.strikeNoise * 1.3f, NoiseKind.Break, true, this);
        }

        void DropChunk(Vector3 at, Vector3 normal)
        {
            if (!mineral.chunkItem) return;
            var out_ = (normal + Random.insideUnitSphere * 0.5f + Vector3.up * 0.3f).normalized;
            var item = ItemInstance.Spawn(mineral.chunkItem, at + out_ * 0.25f, Random.rotation);
            var rb = item ? item.GetComponent<Rigidbody>() : null;
            if (rb) rb.velocity = out_ * Random.Range(1f, 2.2f);
        }

        void Update()
        {
            if (_shake > 0f && _shakeTarget)
            {
                _shake -= Time.deltaTime;
                _shakeTarget.localPosition = _shakeBase + Random.insideUnitSphere * 0.012f * (_shake / 0.12f);
                if (_shake <= 0f) _shakeTarget.localPosition = _shakeBase;
            }
        }
    }
}
