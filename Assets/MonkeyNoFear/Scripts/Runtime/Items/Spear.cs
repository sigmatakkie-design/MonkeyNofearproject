using UnityEngine;
using MonkeyNoFear.AI;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Items
{
    /// <summary>
    /// Stab forward along the spear, or throw it. Hunts wildlife in one good hit; against monsters it is a
    /// tool for creating an escape window (each creature decides how it responds — none dies to one stab).
    /// Thrown spears stick into wood and earth and can be picked up again.
    /// </summary>
    [RequireComponent(typeof(Grabbable))]
    public class Spear : MonoBehaviour
    {
        public float damage = 35f;
        public float thrownDamage = 45f;
        public float minStabSpeed = 2.0f;
        public float minThrowSpeed = 6f;
        public float tipRadius = 0.22f;
        [Range(-1, 1)] public float minAlignment = 0.5f;
        public float cooldown = 0.35f;
        public Transform tip;

        Grabbable _grab;
        float _last = -1f;
        bool _inFlight;

        void Awake()
        {
            _grab = GetComponent<Grabbable>();
            if (!tip) tip = transform.Find("TIP");
            _grab.Released += h => _inFlight = _grab.Body.velocity.magnitude > minThrowSpeed;
            _grab.Grabbed += h => { _inFlight = false; _grab.Body.isKinematic = false; };
        }

        void FixedUpdate()
        {
            // a thrown spear flies point-first
            if (_inFlight && !_grab.IsHeld)
            {
                var v = _grab.Body.velocity;
                if (v.sqrMagnitude > 4f)
                    _grab.Body.MoveRotation(Quaternion.Slerp(_grab.Body.rotation, Quaternion.LookRotation(v.normalized, transform.up), 0.25f));
                else _inFlight = false;
            }
        }

        void OnCollisionEnter(Collision c)
        {
            if (Time.time - _last < cooldown) return;
            bool thrown = _inFlight && !_grab.IsHeld;
            if (!_grab.IsHeld && !thrown) return;
            var r = ToolStrike.Evaluate(c, _grab, tip, Vector3.forward, thrown ? minThrowSpeed * 0.6f : minStabSpeed, tipRadius, thrown ? 0.2f : minAlignment);
            if (!r.valid) return;
            _last = Time.time;

            var target = r.other.GetComponentInParent<IDamageable>();
            if (target != null && target.IsAlive)
            {
                float d = (thrown ? thrownDamage : damage) * Mathf.Clamp(r.speed / 4f, 0.6f, 1.3f);
                target.TakeDamage(new DamageInfo(d, transform.position, DamageType.Stab, this) { hitPoint = r.point, direction = transform.forward, tier = 1 });
                AudioManager.Instance?.PlayAt("spear_stab_flesh", r.point, 1f);
                FXManager.Burst("blood", r.point, r.normal, new Color(0.25f, 0.02f, 0.02f), 10);
                ToolStrike.Haptic(_grab, 0.8f);
                NoiseSystem.Emit(r.point, 0.3f, NoiseKind.Combat, true, this);
                _inFlight = false;
                return;
            }

            var kind = Surface.KindOf(r.other);
            AudioManager.Instance?.PlayAt(kind == Data.SurfaceKind.Wood ? "spear_hit_wood" : "spear_hit_hard", r.point, 0.8f);
            ToolStrike.Haptic(_grab, 0.4f);
            if (thrown && (kind == Data.SurfaceKind.Wood || kind == Data.SurfaceKind.Dirt || kind == Data.SurfaceKind.Mud))
            {
                // stick
                _grab.Body.isKinematic = true; // stays embedded where it hit; grabbing frees it
                _inFlight = false;
            }
        }
    }
}
