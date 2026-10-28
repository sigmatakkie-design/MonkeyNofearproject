using UnityEngine;
using MonkeyNoFear.AI;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Player
{
    /// <summary>
    /// Arm-driven monkey locomotion with a custom kinematic solver (no PhysX character controller):
    ///  * the rig root is the tracking-space floor origin; the body is a capsule from the floor to the head
    ///  * anchored hands move the body by (anchor − controller): push, pull, climb, pull-up
    ///  * releasing all hands converts the recent hand-driven motion into ballistic velocity (jumps, leaps)
    ///  * every body move is a swept capsule with sliding, followed by depenetration
    ///  * room-scale head movement cannot push the head through walls
    ///  * safety: velocity clamps, tracking-glitch rejection, stuck detection, safe-position recovery,
    ///    out-of-bounds recovery, fall damage
    /// Runs in Update (render rate) because hand tracking is sampled at render rate; all queries are
    /// against static/kinematic geometry so the physics step rate does not matter.
    /// </summary>
    public class MonkeyLocomotion : MonoBehaviour
    {
        [Header("Body")]
        public float bodyRadius = 0.17f;
        public float minBodyHeight = 0.45f;
        public float headRadius = 0.13f;
        public float skin = 0.01f;

        [Header("Arm locomotion")]
        [Tooltip("Max body speed that hands can produce per frame (prevents spikes from fast flailing).")]
        public float maxHandSpeed = 9f;
        [Tooltip("Release velocity = average recent hand motion × this.")]
        public float jumpMultiplier = 1.15f;
        public float maxJumpSpeed = 6.5f;
        [Tooltip("Released velocity below this is discarded (avoids drifting after gentle releases).")]
        public float minReleaseSpeed = 0.35f;
        [Range(2, 12)] public int velocityHistoryFrames = 6;

        [Header("Ballistics")]
        public float gravity = -9.81f;
        public float airDrag = 0.05f;
        [Tooltip("Horizontal deceleration while the body rests on the ground and no hand holds on.")]
        public float groundFriction = 9f;
        [Range(0, 1)] public float groundNormalMinY = 0.6f;

        [Header("Damage & safety")]
        public float fallDamageSpeed = 9.5f;
        public float fallDamagePerSpeed = 12f;
        public float killY = -250f;
        public float stuckSecondsBeforeRecovery = 1.2f;

        [Header("Noise")]
        [Tooltip("Body speed above which movement itself makes noise creatures can hear.")]
        public float noisySpeed = 3.8f;

        // ------------------------------------------------------------------ state
        public Vector3 Velocity => _velocity;
        public bool Grounded { get; private set; }
        public bool AnyHandAnchored { get; private set; }
        public float Speed { get; private set; }
        public bool HeadInsideGeometry { get; private set; }
        /// <summary>Set by creatures that pin the player (Ceiling Clerk grab). Hands still move, body does not.</summary>
        public bool Pinned { get; set; }
        /// <summary>Vigor/armour effects on leap strength.</summary>
        public float StrengthMultiplier { get; set; } = 1f;
        /// <summary>Optional joystick movement (accessibility), meters per second in world space.</summary>
        public Vector3 ExternalVelocity { get; set; }

        PlayerRig _rig;
        CapsuleCollider _capsule;
        Vector3 _velocity;
        Vector3[] _history;
        int _historyCount, _historyIndex;
        bool _wasAnchored;
        Vector3 _lastHead;
        bool _hasLastHead;
        float _stuckTimer, _safeTimer, _noiseTimer;
        readonly Vector3[] _safe = new Vector3[12];
        int _safeCount, _safeIndex;
        readonly Collider[] _overlap = new Collider[16];
        Transform _platform;
        Vector3 _platformLastPos;
        Quaternion _platformLastRot;

        public void Init(PlayerRig rig, CapsuleCollider capsule)
        {
            _rig = rig;
            _capsule = capsule;
            _capsule.direction = 1;
            _capsule.radius = bodyRadius;
            _capsule.gameObject.layer = Layers.Player;
            _history = new Vector3[Mathf.Max(2, velocityHistoryFrames)];
            RecordSafe(transform.position);
        }

        // ------------------------------------------------------------------ main step
        public void Step(float dt)
        {
            if (dt <= 0f) return;
            dt = Mathf.Min(dt, 1f / 30f); // hitch guard: never integrate huge steps

            bool wasGrounded = Grounded;
            ApplyPlatformMotion();
            ResolveHead();

            var left = _rig.LeftHand;
            var right = _rig.RightHand;
            Vector3 offset = Vector3.zero;
            int anchoredCount = 0;
            if (left.ResolvePreMove(_rig.HandTarget(Hand.Left), dt, out var lo)) { offset += lo; anchoredCount++; }
            if (right.ResolvePreMove(_rig.HandTarget(Hand.Right), dt, out var ro)) { offset += ro; anchoredCount++; }
            AnyHandAnchored = anchoredCount > 0;

            Vector3 move;
            if (Pinned)
            {
                move = Vector3.zero;
                _velocity = Vector3.zero;
                ClearHistory();
            }
            else if (AnyHandAnchored)
            {
                move = offset / anchoredCount;
                float max = maxHandSpeed * dt;
                if (move.sqrMagnitude > max * max) move = move.normalized * max;
                _velocity = move / dt;
                PushHistory(_velocity);
            }
            else
            {
                if (_wasAnchored) ReleaseToBallistic();
                _velocity.y += gravity * dt;
                _velocity *= 1f / (1f + airDrag * dt);
                if (Grounded)
                {
                    var h = new Vector3(_velocity.x, 0f, _velocity.z);
                    h = Vector3.MoveTowards(h, Vector3.zero, groundFriction * dt);
                    _velocity.x = h.x; _velocity.z = h.z;
                    if (_velocity.y < 0f) _velocity.y = 0f;
                }
                move = _velocity * dt;
            }
            _wasAnchored = AnyHandAnchored;
            if (!Pinned) move += ExternalVelocity * dt;

            float fallSpeed = Mathf.Max(0f, -_velocity.y);
            float impactSpeed = MoveBody(move);
            Depenetrate(dt);
            GroundCheck();
            if (Grounded && !wasGrounded && !AnyHandAnchored) OnLanded(Mathf.Max(impactSpeed, fallSpeed));

            left.ResolvePostMove(_rig.HandTarget(Hand.Left));
            right.ResolvePostMove(_rig.HandTarget(Hand.Right));

            Speed = Mathf.Lerp(Speed, _velocity.magnitude, 0.25f);
            MovementNoise(dt);
            SafetyChecks(dt);
            _lastHead = _rig.HeadPosition;
        }

        void ReleaseToBallistic()
        {
            Vector3 avg = Vector3.zero;
            for (int i = 0; i < _historyCount; i++) avg += _history[i];
            if (_historyCount > 0) avg /= _historyCount;
            avg *= jumpMultiplier;
            float max = maxJumpSpeed * StrengthMultiplier;
            if (avg.magnitude > max) avg = avg.normalized * max;
            _velocity = avg.magnitude < minReleaseSpeed ? Vector3.zero : avg;
            ClearHistory();
        }

        void PushHistory(Vector3 v)
        {
            _history[_historyIndex] = v;
            _historyIndex = (_historyIndex + 1) % _history.Length;
            _historyCount = Mathf.Min(_historyCount + 1, _history.Length);
        }

        void ClearHistory() { _historyCount = 0; _historyIndex = 0; }

        // ------------------------------------------------------------------ head (room-scale) collision
        void ResolveHead()
        {
            var head = _rig.HeadPosition;
            if (!_hasLastHead) { _lastHead = head; _hasLastHead = true; }
            Vector3 d = head - _lastHead;
            float dist = d.magnitude;
            if (dist > 1.5f) { _lastHead = head; dist = 0f; } // recentre / teleport
            if (dist > 1e-5f && Physics.SphereCast(_lastHead, headRadius, d / dist, out var hit, dist, Layers.SolidWorld, QueryTriggerInteraction.Ignore))
            {
                Vector3 allowed = _lastHead + d / dist * Mathf.Max(0f, hit.distance - skin);
                Vector3 push = allowed - head;
                push.y = 0f; // never push the rig vertically for room-scale moves: fade instead
                transform.position += push;
            }
            HeadInsideGeometry = Physics.CheckSphere(_rig.HeadPosition, headRadius * 0.6f, Layers.SolidWorld, QueryTriggerInteraction.Ignore);
        }

        // ------------------------------------------------------------------ capsule helpers
        void CapsulePoints(Vector3 rootPos, out Vector3 bottom, out Vector3 top)
        {
            Vector3 headLocal = _rig.HeadPosition - transform.position;
            float height = Mathf.Max(minBodyHeight, headLocal.y + headRadius);
            bottom = new Vector3(rootPos.x + headLocal.x, rootPos.y + bodyRadius, rootPos.z + headLocal.z);
            top = bottom + Vector3.up * Mathf.Max(0f, height - bodyRadius * 2f);
        }

        void SyncCapsule()
        {
            CapsulePoints(transform.position, out var b, out var t);
            var c = (b + t) * 0.5f;
            _capsule.center = _capsule.transform.InverseTransformPoint(c);
            _capsule.height = (t - b).magnitude + bodyRadius * 2f;
            _capsule.radius = bodyRadius;
        }

        /// <summary>Swept capsule move with up to 3 slide iterations. Returns the speed of the hardest impact.</summary>
        float MoveBody(Vector3 move)
        {
            float impact = 0f;
            for (int i = 0; i < 3; i++)
            {
                float dist = move.magnitude;
                if (dist < 1e-6f) break;
                Vector3 dir = move / dist;
                CapsulePoints(transform.position, out var b, out var t);
                if (Physics.CapsuleCast(b, t, bodyRadius - skin, dir, out var hit, dist + skin, Layers.SolidWorld, QueryTriggerInteraction.Ignore))
                {
                    float travel = Mathf.Max(0f, hit.distance - skin);
                    transform.position += dir * travel;
                    float into = -Vector3.Dot(_velocity, hit.normal);
                    if (into > 0f)
                    {
                        impact = Mathf.Max(impact, into);
                        _velocity += hit.normal * into; // remove the velocity component into the surface
                    }
                    move = Vector3.ProjectOnPlane(move - dir * travel, hit.normal);
                    if (hit.normal.y >= groundNormalMinY) Grounded = true;
                }
                else
                {
                    transform.position += move;
                    break;
                }
            }
            SyncCapsule();
            return impact;
        }

        void Depenetrate(float dt)
        {
            SyncCapsule();
            CapsulePoints(transform.position, out var b, out var t);
            bool stillStuck = false;
            for (int iter = 0; iter < 4; iter++)
            {
                int n = Physics.OverlapCapsuleNonAlloc(b, t, bodyRadius, _overlap, Layers.SolidWorld, QueryTriggerInteraction.Ignore);
                if (n == 0) { stillStuck = false; break; }
                Vector3 total = Vector3.zero;
                stillStuck = false;
                for (int i = 0; i < n; i++)
                {
                    var c = _overlap[i];
                    if (c == _capsule) continue;
                    if (Physics.ComputePenetration(_capsule, _capsule.transform.position, _capsule.transform.rotation,
                            c, c.transform.position, c.transform.rotation, out var dir, out var depth))
                    {
                        total += dir * (depth + 0.001f);
                        if (depth > 0.06f) stillStuck = true;
                        if (dir.y > groundNormalMinY) Grounded = true;
                    }
                }
                if (total.sqrMagnitude < 1e-8f) break;
                // cap per-frame correction so a bad overlap cannot launch the player
                if (total.magnitude > 0.3f) total = total.normalized * 0.3f;
                transform.position += total;
                float into = -Vector3.Dot(_velocity, total.normalized);
                if (into > 0f) _velocity += total.normalized * into;
                SyncCapsule();
                CapsulePoints(transform.position, out b, out t);
            }
            _stuckTimer = stillStuck ? _stuckTimer + dt : 0f;
        }

        void GroundCheck()
        {
            CapsulePoints(transform.position, out var b, out _);
            Grounded = false;
            _platform = null;
            if (Physics.SphereCast(b + Vector3.up * 0.05f, bodyRadius * 0.9f, Vector3.down, out var hit, 0.1f, Layers.SolidWorld, QueryTriggerInteraction.Ignore)
                && hit.normal.y >= groundNormalMinY)
            {
                Grounded = true;
                var plat = hit.collider.GetComponentInParent<MovingPlatform>();
                if (plat)
                {
                    _platform = plat.transform;
                    _platformLastPos = _platform.position;
                    _platformLastRot = _platform.rotation;
                }
            }
        }

        void ApplyPlatformMotion()
        {
            if (!_platform) return;
            Quaternion rot = _platform.rotation * Quaternion.Inverse(_platformLastRot);
            Vector3 rel = transform.position - _platformLastPos;
            transform.position = _platform.position + rot * rel;
            _platformLastPos = _platform.position;
            _platformLastRot = _platform.rotation;
        }

        void OnLanded(float impactSpeed)
        {
            if (impactSpeed > 2.5f)
            {
                AudioManager.Instance?.PlayAt("land_thud", transform.position, Mathf.Clamp01(impactSpeed / 9f));
                NoiseSystem.Emit(transform.position, Mathf.Clamp(impactSpeed * 0.06f, 0.1f, 0.6f), NoiseKind.Movement, true, this);
                _rig.Haptic(Hand.Left, 0.5f, 0.08f);
                _rig.Haptic(Hand.Right, 0.5f, 0.08f);
            }
            if (impactSpeed > fallDamageSpeed && PlayerHealth.Instance)
                PlayerHealth.Instance.TakeDamage(new DamageInfo((impactSpeed - fallDamageSpeed) * fallDamagePerSpeed, transform.position, DamageType.Fall));
        }

        void MovementNoise(float dt)
        {
            _noiseTimer -= dt;
            if (Speed > noisySpeed && _noiseTimer <= 0f)
            {
                _noiseTimer = 0.45f;
                NoiseSystem.Emit(transform.position, Mathf.Clamp01((Speed - noisySpeed) * 0.12f + 0.15f), NoiseKind.Movement, true, this);
            }
        }

        // ------------------------------------------------------------------ safety
        void SafetyChecks(float dt)
        {
            if (transform.position.y < killY || float.IsNaN(transform.position.x))
            {
                Debug.LogWarning("[Locomotion] Out of bounds — recovering to last safe position.");
                RecoverToSafePosition();
                return;
            }
            if (_stuckTimer > stuckSecondsBeforeRecovery)
            {
                Debug.LogWarning("[Locomotion] Stuck in geometry — recovering.");
                RecoverToSafePosition();
                return;
            }
            _safeTimer -= dt;
            if (_safeTimer <= 0f && Grounded && !AnyHandAnchored && _stuckTimer <= 0f && !HeadInsideGeometry && !Pinned)
            {
                _safeTimer = 0.5f;
                RecordSafe(transform.position);
            }
        }

        void RecordSafe(Vector3 p)
        {
            _safe[_safeIndex] = p;
            _safeIndex = (_safeIndex + 1) % _safe.Length;
            _safeCount = Mathf.Min(_safeCount + 1, _safe.Length);
        }

        public void RecoverToSafePosition()
        {
            // prefer a slightly older sample: the newest one may be the edge we just got stuck on
            Vector3 p = transform.position;
            if (_safeCount > 0)
            {
                int back = Mathf.Min(_safeCount - 1, 2);
                p = _safe[(_safeIndex - 1 - back + _safe.Length * 2) % _safe.Length];
            }
            Teleport(p);
            ScreenFader.Instance?.Flash(Color.black, 0.4f);
        }

        /// <summary>Hard reposition of the rig root (floor origin). Clears velocity and hand anchors.</summary>
        public void Teleport(Vector3 rootPosition)
        {
            transform.position = rootPosition;
            _velocity = Vector3.zero;
            ClearHistory();
            _wasAnchored = false;
            _stuckTimer = 0f;
            _hasLastHead = false;
            _platform = null;
            _rig.LeftHand.Teleport(_rig.HandTarget(Hand.Left));
            _rig.RightHand.Teleport(_rig.HandTarget(Hand.Right));
            SyncCapsule();
        }

        public void AddImpulse(Vector3 v) { _velocity += v; }

        void OnDrawGizmosSelected()
        {
            if (!_rig) return;
            CapsulePoints(transform.position, out var b, out var t);
            Gizmos.color = Grounded ? Color.green : Color.cyan;
            Gizmos.DrawWireSphere(b, bodyRadius);
            Gizmos.DrawWireSphere(t, bodyRadius);
            Gizmos.DrawLine(b, t);
            Gizmos.color = Color.red;
            Gizmos.DrawLine(t, t + _velocity * 0.25f);
        }
    }

}
