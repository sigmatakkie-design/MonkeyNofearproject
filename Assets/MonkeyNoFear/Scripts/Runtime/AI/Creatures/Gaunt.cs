using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.AI.Creatures
{
    /// <summary>
    /// THE GAUNT — an enormous figure that walks the floor of the deep chasm. It is never fought: it is
    /// evidence that something far bigger lives below. Appears at most once per expedition (by chance) when
    /// the player is at the chasm, walks a slow authored path, and — if watched long enough — slowly
    /// raises its head toward the player. The world goes silent while it is in view.
    /// </summary>
    public class Gaunt : MonoBehaviour, IExpeditionReset
    {
        public List<Transform> path = new List<Transform>();
        public CreatureAnimator animator;
        [Tooltip("Player must be inside this zone (the chasm viewpoint) for it to appear.")]
        public AreaZone viewZone;
        [Range(0, 1)] public float appearChance = 0.45f;
        public float speed = 1.0f;
        public float watchToLookUp = 8f;

        bool _active, _done, _looked;
        int _index;
        float _watch, _stepTimer, _checkTimer;
        Renderer[] _renderers;

        void Awake()
        {
            _renderers = GetComponentsInChildren<Renderer>(true);
            if (!animator) animator = GetComponentInChildren<CreatureAnimator>();
            Show(false);
        }

        void OnEnable() => ExpeditionManager.Register(this);
        void OnDisable() => ExpeditionManager.Unregister(this);

        public void OnNewExpedition(int index, System.Random rng)
        {
            _done = rng.NextDouble() > appearChance; // decided once per expedition
            _active = false; _looked = false; _index = 0; _watch = 0f;
            Show(false);
        }

        void Show(bool v) { foreach (var r in _renderers) if (r) r.enabled = v; if (animator && animator.anim) animator.anim.enabled = v; }

        void Update()
        {
            var rig = PlayerRig.Instance;
            if (!rig || path.Count < 2) return;
            if (!_active)
            {
                if (_done) return;
                _checkTimer -= Time.deltaTime;
                if (_checkTimer > 0f) return;
                _checkTimer = 1f;
                if (viewZone && !viewZone.Contains(rig.HeadPosition)) return;
                _active = true; _done = true;
                transform.position = path[0].position;
                Show(true);
                animator?.Play("walk", 0.5f);
                AudioManager.Instance?.PlayAt("gaunt_groan", transform.position + Vector3.up * 10f, 1f);
                return;
            }

            ThreatMonitor.Report(0.6f); // silence: life layers fade while it walks
            var target = path[_index + 1].position;
            var to = target - transform.position; to.y = 0f;
            if (!_looked && to.magnitude > 0.5f)
            {
                transform.position += to.normalized * speed * Time.deltaTime;
                transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(to), Time.deltaTime * 0.3f);
                _stepTimer -= Time.deltaTime;
                if (_stepTimer <= 0f) { _stepTimer = 2.6f; AudioManager.Instance?.PlayAt("gaunt_step", transform.position, 1f); }
            }
            else if (!_looked && to.magnitude <= 0.5f)
            {
                _index++;
                if (_index >= path.Count - 1) { _active = false; Show(false); return; }
            }

            // being watched
            var head = transform.position + Vector3.up * 12f;
            bool watched = Vector3.Angle(rig.HeadForward, head - rig.HeadPosition) < 25f;
            _watch = watched ? _watch + Time.deltaTime : Mathf.Max(0f, _watch - Time.deltaTime * 0.5f);
            if (!_looked && _watch > watchToLookUp)
            {
                _looked = true;
                animator?.PlayOnce("look_up", 0.6f);
                if (animator) { animator.LookTarget = rig.HeadPosition; animator.LookWeight = 0.6f; }
                AudioManager.Instance?.Play2D("sting_dread", 0.8f);
                GameRoot.I?.Progress.Discover("creature_gaunt");
                Invoke(nameof(Leave), 7f);
            }
        }

        void Leave() { _looked = false; animator?.Play("walk", 1f); if (animator) animator.LookWeight = 0f; }
    }
}
