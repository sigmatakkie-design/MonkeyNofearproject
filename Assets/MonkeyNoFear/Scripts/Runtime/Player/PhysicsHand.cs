using UnityEngine;
using MonkeyNoFear.AI;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Player
{
    /// <summary>
    /// One collision-aware hand. The hand chases the tracked controller but can never pass through solid
    /// geometry. When it hits a climbable surface it anchors there; while anchored, controller motion moves
    /// the BODY instead of the hand (push the floor down → rise, drag the floor back → move forward,
    /// pull down on a wall → climb). Moving the controller away from the surface releases the anchor.
    /// </summary>
    public class PhysicsHand : MonoBehaviour
    {
        public Hand hand;
        [Tooltip("Collision radius of the palm sphere.")]
        public float radius = 0.055f;
        [Tooltip("Controller must move this far out of the surface (along its normal) to release.")]
        public float releaseDistance = 0.025f;
        [Tooltip("Release if the controller gets further than this from the anchored hand (prevents arm stretching).")]
        public float maxStretch = 0.5f;
        [Tooltip("Minimum approach speed for a tap sound / haptic / noise.")]
        public float tapSpeed = 0.55f;
        [Tooltip("Seconds between tap sounds on one hand.")]
        public float tapCooldown = 0.09f;

        public bool Anchored { get; private set; }
        public Vector3 Position { get; private set; }
        public Vector3 Target { get; private set; }
        public Vector3 SurfaceNormal { get; private set; } = Vector3.up;
        public Collider SurfaceCollider { get; private set; }
        public Quaternion Rotation { get; set; } = Quaternion.identity;
        /// <summary>Smoothed world-space velocity of the tracked controller (used for throws and strikes).</summary>
        public Vector3 ControllerVelocity { get; private set; }

        Vector3 _anchorLocal, _anchorWorld;
        Transform _anchorTransform;
        float _slip;
        float _lastTap = -1f;
        Vector3 _lastTarget;
        bool _hasLastTarget;
        Rigidbody _body;
        PlayerRig _rig;
        readonly Collider[] _overlap = new Collider[8];

        public void Init(PlayerRig rig)
        {
            _rig = rig;
            _body = GetComponent<Rigidbody>();
            if (!_body) _body = gameObject.AddComponent<Rigidbody>();
            _body.isKinematic = true;
            _body.interpolation = RigidbodyInterpolation.Interpolate;
            var col = GetComponent<SphereCollider>();
            if (!col) col = gameObject.AddComponent<SphereCollider>();
            col.radius = radius * 0.9f;
            gameObject.layer = Layers.PlayerHand;
        }

        public void Teleport(Vector3 p)
        {
            Release();
            Position = p; Target = p; _lastTarget = p; _hasLastTarget = true;
            transform.position = p;
        }

        public void Release()
        {
            Anchored = false;
            _anchorTransform = null;
            SurfaceCollider = null;
        }

        Vector3 AnchorWorld => _anchorTransform ? _anchorTransform.TransformPoint(_anchorLocal) : _anchorWorld;

        /// <summary>Phase 1 (before the body moves): update anchor state against the new target and return
        /// the body offset this hand requests (anchor − target) when anchored.</summary>
        public bool ResolvePreMove(Vector3 target, float dt, out Vector3 bodyOffset)
        {
            bodyOffset = Vector3.zero;
            // tracking glitch guard: a >1.2 m jump in one frame is not a real hand movement
            if (_hasLastTarget && (target - _lastTarget).sqrMagnitude > 1.44f)
            {
                Teleport(target);
                return false;
            }
            if (_hasLastTarget && dt > 0f)
                ControllerVelocity = Vector3.Lerp(ControllerVelocity, (target - _lastTarget) / dt, 0.5f);
            _lastTarget = target; _hasLastTarget = true;
            Target = target;

            if (Anchored)
            {
                if (_anchorTransform == null && SurfaceCollider == null) { Release(); }
                else
                {
                    var a = AnchorWorld;
                    float outward = Vector3.Dot(target - a, SurfaceNormal);
                    if (outward > releaseDistance || (target - a).sqrMagnitude > maxStretch * maxStretch ||
                        (SurfaceCollider && !SurfaceCollider.enabled))
                    {
                        Release();
                        Position = a;
                    }
                    else
                    {
                        if (_slip > 0f)
                        {
                            // slippery: the anchor slides with the tangential part of the motion
                            var tangential = Vector3.ProjectOnPlane(target - a, SurfaceNormal) * _slip;
                            SetAnchor(a + tangential, SurfaceNormal, SurfaceCollider);
                            a = AnchorWorld;
                        }
                        Position = a;
                        bodyOffset = a - target;
                        return true;
                    }
                }
            }

            // free: sweep from the last physical position toward the target
            return SweepTo(target, out bodyOffset);
        }

        /// <summary>Phase 2 (after the body moved): free hands follow their (shifted) targets with collision.</summary>
        public void ResolvePostMove(Vector3 target)
        {
            Target = target;
            if (Anchored) { Position = AnchorWorld; return; }
            SweepTo(target, out _);
        }

        bool SweepTo(Vector3 target, out Vector3 bodyOffset)
        {
            bodyOffset = Vector3.zero;
            Vector3 from = Position;
            // if we start inside geometry (moving object, spawn), push out first
            from = Depenetrate(from);
            Vector3 delta = target - from;
            float dist = delta.magnitude;
            if (dist > 1e-5f &&
                Physics.SphereCast(from, radius, delta / dist, out var hit, dist, Layers.SolidWorld, QueryTriggerInteraction.Ignore))
            {
                Vector3 contact = from + delta / dist * Mathf.Max(0f, hit.distance - 0.002f);
                Position = contact;
                float approach = Vector3.Dot(ControllerVelocity, -hit.normal);
                OnContact(hit.collider, hit.point, approach);
                if (Layers.InMask(hit.collider.gameObject.layer, Layers.Climbable | (1 << Layers.NoClimb)))
                {
                    SetAnchor(contact, hit.normal, hit.collider);
                    _slip = Surface.SlipperinessOf(hit.collider);
                    bodyOffset = contact - target;
                    return true;
                }
                return false;
            }
            Position = target;
            return false;
        }

        Vector3 Depenetrate(Vector3 p)
        {
            int n = Physics.OverlapSphereNonAlloc(p, radius, _overlap, Layers.SolidWorld, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var c = _overlap[i];
                if (Physics.ComputePenetration(_sphereProbe, p, Quaternion.identity, c, c.transform.position, c.transform.rotation, out var dir, out var d))
                    p += dir * (d + 0.001f);
            }
            return p;
        }

        static SphereCollider _probe;
        SphereCollider _sphereProbe
        {
            get
            {
                if (!_probe)
                {
                    // a trigger on the Trigger layer, parked far away: invisible to every gameplay query
                    var go = new GameObject("HandProbe") { hideFlags = HideFlags.HideAndDontSave, layer = Layers.Trigger };
                    go.transform.position = new Vector3(0f, -10000f, 0f);
                    _probe = go.AddComponent<SphereCollider>();
                    _probe.isTrigger = true;
                }
                _probe.radius = radius;
                return _probe;
            }
        }

        void SetAnchor(Vector3 world, Vector3 normal, Collider c)
        {
            Anchored = true;
            SurfaceNormal = normal;
            SurfaceCollider = c;
            _anchorWorld = world;
            // stick to moving platforms / doors / elevators
            _anchorTransform = c && !c.gameObject.isStatic ? c.transform : null;
            if (_anchorTransform) _anchorLocal = _anchorTransform.InverseTransformPoint(world);
        }

        void OnContact(Collider c, Vector3 point, float approachSpeed)
        {
            if (approachSpeed < tapSpeed || Time.time - _lastTap < tapCooldown) return;
            _lastTap = Time.time;
            var kind = Surface.KindOf(c);
            float strength = Mathf.Clamp01((approachSpeed - tapSpeed) / 3.5f);
            AudioManager.Instance?.PlayAt(Surface.TapSound(kind), point, 0.35f + strength * 0.65f, 1f + Random.Range(-0.05f, 0.05f));
            _rig?.Haptic(hand, 0.15f + strength * 0.6f, 0.04f + strength * 0.05f);
            // creatures hear slaps: louder the harder you hit, metal is loudest
            float loud = (0.08f + strength * 0.5f) * Surface.NoiseFactor(kind);
            NoiseSystem.Emit(point, loud, NoiseKind.HandImpact, true, this);
            c.GetComponentInParent<IHandTouchable>()?.OnHandTouch(this, point, approachSpeed);
        }

        void FixedUpdate()
        {
            if (_body) _body.MovePosition(Position);
        }

        void OnDrawGizmos()
        {
            Gizmos.color = Anchored ? Color.green : Color.yellow;
            Gizmos.DrawWireSphere(Position, radius);
            Gizmos.color = Color.gray;
            Gizmos.DrawLine(Position, Target);
        }
    }

    /// <summary>Optional reaction to being slapped (breakables, buttons, creatures).</summary>
    public interface IHandTouchable
    {
        void OnHandTouch(PhysicsHand hand, Vector3 point, float speed);
    }
}
