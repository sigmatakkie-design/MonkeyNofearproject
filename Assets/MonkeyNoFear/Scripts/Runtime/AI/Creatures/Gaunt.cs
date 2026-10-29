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
        [Tooltip("Degrees per second it can turn: it turns into each new path leg before striding on.")]
        public float turnSpeed = 14f;

        bool _active, _done, _looked, _lookedOnce;
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
            _active = false; _looked = false; _lookedOnce = false; _index = 0; _watch = 0f;
            CancelInvoke(nameof(Leave));
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
                // it walks in from the start of its path: never materialise in plain view
                if (Vector3.Angle(rig.HeadForward, path[0].position + Vector3.up * 7f - rig.HeadPosition) < 45f) return;
                _active = true; _done = true;
                transform.position = path[0].position;
                var first = path[1].position - path[0].position; first.y = 0f;
                if (first.sqrMagnitude > 0.01f) transform.rotation = Quaternion.LookRotation(first);
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
                // scripted walk along the authored chasm-floor path (no NavMesh down there): it faces where it
                // goes and strides at the authored cycle speed, slowing while it turns into a new leg
                var dir = to.normalized;
                transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(dir), turnSpeed * Time.deltaTime);
                float stride = speed * Mathf.Clamp01(Vector3.Dot(transform.forward, dir));
                var next = Vector3.MoveTowards(new Vector3(transform.position.x, 0f, transform.position.z), new Vector3(target.x, 0f, target.z), stride * Time.deltaTime);
                // follow the floor height between path points instead of keeping the start height
                float k = 1f - Mathf.Clamp01(to.magnitude / Mathf.Max(0.01f, Horizontal(path[_index].position, target)));
                next.y = Mathf.Lerp(path[_index].position.y, target.y, k);
                transform.position = next;
                animator?.SyncSpeed("walk", stride, 0.25f, 1.5f);
                _stepTimer -= Time.deltaTime * Mathf.Max(0.25f, stride / Mathf.Max(0.01f, speed));
                if (_stepTimer <= 0f) { _stepTimer = 2.6f; AudioManager.Instance?.PlayAt("gaunt_step", transform.position, 1f); }
            }
            else if (!_looked && to.magnitude <= 0.5f)
            {
                if (_index + 1 >= path.Count - 1)
                {
                    // end of the walk: it only leaves the world once nobody is looking at it
                    if (Vector3.Angle(rig.HeadForward, transform.position + Vector3.up * 7f - rig.HeadPosition) > 50f) { _active = false; Show(false); return; }
                    animator?.Play("stand", 0.8f);
                }
                else _index++;
            }

            // being watched
            var head = transform.position + Vector3.up * 12f;
            bool watched = Vector3.Angle(rig.HeadForward, head - rig.HeadPosition) < 25f;
            _watch = watched ? _watch + Time.deltaTime : Mathf.Max(0f, _watch - Time.deltaTime * 0.5f);
            if (!_looked && !_lookedOnce && _watch > watchToLookUp)
            {
                _looked = true; _lookedOnce = true; // once per appearance, then it walks on
                animator?.PlayOnce("look_up", 0.6f);
                if (animator) { animator.LookTarget = rig.HeadPosition; animator.LookWeight = 0.6f; }
                AudioManager.Instance?.Play2D("sting_dread", 0.8f);
                GameRoot.I?.Progress.Discover("creature_gaunt");
                Invoke(nameof(Leave), 7f);
            }
        }

        void Leave() { _looked = false; animator?.Play("walk", 1f); if (animator) animator.LookWeight = 0f; }

        static float Horizontal(Vector3 a, Vector3 b) { a.y = 0f; b.y = 0f; return Vector3.Distance(a, b); }
    }
}
