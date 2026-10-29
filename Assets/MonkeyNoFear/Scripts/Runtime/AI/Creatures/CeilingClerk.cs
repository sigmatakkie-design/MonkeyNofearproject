using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.Items;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.AI.Creatures
{
    /// <summary>
    /// THE CEILING CLERK — vertical ambush predator.
    ///  Stalk: crawls node-to-node across the ceiling toward the player, but only while it is not being
    ///   looked at. Every move is accompanied by tiny finger taps you can hear above you.
    ///  Freeze: caught in a beam (flashlight / flare / glowstick) it locks up. Each exposure in a row
    ///   shortens the freeze, and too much light sends it retreating to a dark node — light is a tool,
    ///   not a permanent solution.
    ///  Windup: directly above you, the jaw drops and it starts clicking (your warning: look up!).
    ///  Drop: it lets go and falls toward where you were; step away and it misses.
    ///  Grab: if it lands on you it clings to your face and drains you; break free by hitting it twice,
    ///   shining a light in its face, or waiting it out (a few seconds). Then it flees and climbs away.
    /// </summary>
    public class CeilingClerk : CreatureBase, IExpeditionReset
    {
        enum S { Dormant, Stalk, Freeze, Retreat, Windup, Drop, Grab, Flee, Climb }

        [Header("Ceiling movement")]
        public float crawlSpeed = 1.3f;
        public float fleeSpeed = 3.2f;
        public float hangOffset = 0.12f;
        public float wakeDistance = 28f;
        [Header("Light response")]
        public float baseFreeze = 3.5f;
        public float freezeDecay = 0.6f;
        public float minFreeze = 1.0f;
        public float exposureToRetreat = 6f;
        [Header("Ambush")]
        public float ambushHorizontal = 2.1f;
        public float windupTime = 2.4f;
        public float grabRange = 1.3f;
        public float drainPerSecond = 9f;
        public float maxGrabTime = 4.5f;
        public float ambushCooldown = 40f;

        S _s = S.Dormant;
        ClerkNode _at, _to;
        float _t, _freezeDur, _exposure, _tapTimer, _ambushReadyAt, _grabLight;
        int _freezeCount, _grabHits;
        Vector3 _dropVel, _climbFrom, _climbTo;
        readonly List<ClerkNode> _tmp = new List<ClerkNode>();
        static bool _linked;

        protected override void Awake()
        {
            base.Awake();
            if (agent) agent.enabled = false; // graph movement only
        }

        void Start()
        {
            if (!_linked) { ClerkNode.LinkAll(); _linked = true; }
            _at = NearestNode(transform.position, null);
            if (_at) PlaceOn(_at.HangPoint(hangOffset), _at.Normal, transform.forward);
            Enter(S.Dormant);
        }

        protected override void OnEnable() { base.OnEnable(); ExpeditionManager.Register(this); }
        protected override void OnDisable() { base.OnDisable(); ExpeditionManager.Unregister(this); _linked = false; }

        public void OnNewExpedition(int index, System.Random rng)
        {
            _freezeCount = 0; _exposure = 0f; _ambushReadyAt = 0f;
            ReleasePlayer();
            if (ClerkNode.All.Count > 0)
            {
                _at = ClerkNode.All[rng.Next(ClerkNode.All.Count)];
                PlaceOn(_at.HangPoint(hangOffset), _at.Normal, transform.forward);
            }
            Enter(S.Dormant);
        }

        protected override bool IsChasing => _s == S.Drop || _s == S.Grab;
        protected override float ThreatLevel(float d)
        {
            switch (_s)
            {
                case S.Windup: case S.Drop: case S.Grab: return 1f;
                case S.Stalk: return d < 15f ? 0.6f : 0.3f;
                case S.Freeze: return 0.5f;
                default: return 0f;
            }
        }

        void Enter(S s)
        {
            _s = s;
            SetState(s.ToString());
            _t = 0f;
            switch (s)
            {
                case S.Dormant: animator?.Play("cling", 0.3f); break;
                case S.Stalk: animator?.Play("cling", 0.2f); break;
                case S.Freeze:
                    _freezeDur = Mathf.Max(minFreeze, baseFreeze - _freezeCount * freezeDecay);
                    _freezeCount++;
                    animator?.Play("freeze", 0.05f);
                    Say("clerk_hiss", 0.5f);
                    break;
                case S.Retreat:
                    _to = FarthestDarkNode(3);
                    animator?.Play("flee", 0.1f);
                    Say("clerk_skitter", 0.9f);
                    break;
                case S.Windup:
                    animator?.PlayOverlay("jaw_open", "jaw", 0.1f);
                    if (animator) animator.JawOpen = 0f;
                    Say("clerk_jaw_drop", 0.8f);
                    break;
                case S.Drop:
                    animator?.PlayOnce("drop", 0.05f);
                    var target = PlayerFeet;
                    var horizontal = target - transform.position; horizontal.y = 0f;
                    _dropVel = horizontal.normalized * Mathf.Min(horizontal.magnitude, 2f) * 1.2f;
                    break;
                case S.Grab:
                    animator?.Play("grab", 0.05f);
                    Say("clerk_screech", 1f);
                    _grabHits = 0; _grabLight = 0f;
                    if (Player) Player.locomotion.Pinned = true;
                    break;
                case S.Flee:
                    animator?.Play("flee", 0.1f);
                    _at = FarthestDarkNode(4);
                    if (_at)
                    {
                        _climbTo = _at.HangPoint(hangOffset);
                        var below = _climbTo;
                        if (Physics.Raycast(_climbTo, Vector3.down, out var hit, 8f, Layers.Occluders)) below = hit.point;
                        _climbFrom = below;
                    }
                    break;
                case S.Climb:
                    _climbFrom = transform.position;
                    break;
            }
        }

        protected override void Think(float dt)
        {
            _t += dt;
            if (!_at && _s != S.Drop && _s != S.Grab) { _at = NearestNode(transform.position, null); if (!_at) return; }
            float d = DistToPlayer;
            bool lit = IsLit();
            if (lit && (_s == S.Stalk || _s == S.Windup || _s == S.Dormant)) _exposure += dt; else _exposure = Mathf.Max(0f, _exposure - dt * 0.25f);

            switch (_s)
            {
                case S.Dormant:
                    if (Player && d < wakeDistance) Enter(S.Stalk);
                    break;

                case S.Stalk:
                    if (lit) { Enter(_exposure > exposureToRetreat ? S.Retreat : S.Freeze); break; }
                    if (Player && d > wakeDistance * 1.6f) { Enter(S.Dormant); break; }
                    if (_to == null)
                    {
                        if (AboveTarget(_at) && Time.time >= _ambushReadyAt) { Enter(S.Windup); break; }
                        if (!Observed()) _to = StepToward(PlayerFeet);
                    }
                    else Crawl(dt, crawlSpeed);
                    break;

                case S.Freeze:
                    if (_t > _freezeDur) Enter(lit ? (_exposure > exposureToRetreat ? S.Retreat : S.Freeze) : S.Stalk);
                    break;

                case S.Retreat:
                    if (_to == null) { _exposure = 0f; Enter(S.Stalk); break; }
                    Crawl(dt, fleeSpeed);
                    break;

                case S.Windup:
                    if (animator) animator.JawOpen = Mathf.Lerp(animator.JawOpen, 35f, dt * 3f);
                    if (lit) { CloseJaw(); Enter(S.Freeze); break; }
                    if (!AboveTarget(_at, 1.6f)) { CloseJaw(); Enter(S.Stalk); break; }
                    if (_t > windupTime) { CloseJaw(); Enter(S.Drop); }
                    break;

                case S.Drop:
                    _dropVel += Physics.gravity * dt;
                    var next = transform.position + _dropVel * dt;
                    if (Physics.Raycast(transform.position, _dropVel.normalized, out var hit, _dropVel.magnitude * dt + 0.3f, Layers.Occluders))
                    {
                        transform.position = hit.point;
                        transform.rotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(PlayerFeet - transform.position, Vector3.up).normalized + Vector3.forward * 0.001f, Vector3.up);
                        SoundAt("clerk_drop", hit.point, 1f);
                        NoiseSystem.Emit(hit.point, 0.4f, NoiseKind.Combat, false, this);
                        if (Player && d < grabRange && PlayerHealth.Instance && !PlayerHealth.Instance.IsDead) Enter(S.Grab);
                        else Enter(S.Flee);
                    }
                    else
                    {
                        transform.position = next;
                        transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(transform.forward, Vector3.up), dt * 6f);
                    }
                    break;

                case S.Grab:
                    HoldPlayer(dt, lit);
                    break;

                case S.Flee:
                    // scuttle along the floor to below a dark node, then climb up to it
                    if (!_at) { Enter(S.Dormant); break; }
                    var to = _climbFrom - transform.position; to.y = 0f;
                    if (to.magnitude > 0.4f)
                    {
                        var step = to.normalized * fleeSpeed * dt;
                        var pos = transform.position + step;
                        if (Physics.Raycast(pos + Vector3.up * 0.8f, Vector3.down, out var g, 2f, Layers.Occluders)) pos.y = g.point.y;
                        transform.position = pos;
                        transform.rotation = Quaternion.LookRotation(to.normalized, Vector3.up);
                        Taps(dt, 0.08f);
                    }
                    else Enter(S.Climb);
                    break;

                case S.Climb:
                    float k = Mathf.Clamp01(_t / 1.4f);
                    transform.position = Vector3.Lerp(_climbFrom, _climbTo, k);
                    transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(transform.forward, _at.Normal), k);
                    Taps(dt, 0.06f);
                    if (k >= 1f) { _to = null; _ambushReadyAt = Time.time + ambushCooldown; Enter(S.Stalk); }
                    break;
            }
        }

        void CloseJaw()
        {
            if (!animator) return;
            animator.JawOpen = 0f;
            animator.StopOverlay("jaw_open");
        }

        void HoldPlayer(float dt, bool lit)
        {
            if (!Player) { Enter(S.Flee); return; }
            // cling in front of the face
            var head = Player.HeadPosition;
            var fwd = Player.HeadForward;
            transform.position = Vector3.Lerp(transform.position, head + fwd * 0.45f + Vector3.down * 0.55f, dt * 10f);
            transform.rotation = Quaternion.LookRotation(-new Vector3(fwd.x, 0f, fwd.z).normalized + Vector3.forward * 0.0001f, Vector3.up);
            PlayerHealth.Instance?.TakeDamage(new DamageInfo(drainPerSecond * dt, transform.position, DamageType.Drain, this));
            Player.Haptic(Hand.Left, 0.35f, dt); Player.Haptic(Hand.Right, 0.35f, dt);
            if (lit) _grabLight += dt;
            // bare-handed punches count too
            _punchCooldown -= dt;
            foreach (var h in new[] { Player.LeftHand, Player.RightHand })
            {
                if (_punchCooldown <= 0f && h.ControllerVelocity.magnitude > 2.5f && Vector3.Distance(h.Position, transform.position + Vector3.up * 0.3f) < 0.55f)
                {
                    _grabHits++; _punchCooldown = 0.3f;
                    SoundAt("spear_stab_flesh", h.Position, 0.6f);
                    Player.Haptic(h.hand, 0.9f, 0.08f);
                }
            }
            if (_grabHits >= 2 || _grabLight > 1.2f || _t > maxGrabTime || (PlayerHealth.Instance && PlayerHealth.Instance.IsDead))
            {
                ReleasePlayer();
                Say("clerk_hurt", 1f);
                Enter(S.Flee);
            }
        }

        void ReleasePlayer()
        {
            if (Player && Player.locomotion.Pinned && _s == S.Grab) Player.locomotion.Pinned = false;
            if (Player && _s == S.Grab) Player.locomotion.AddImpulse(-Player.HeadForward * 1.5f);
        }

        void Crawl(float dt, float speed)
        {
            if (_to == null || _at == null) return;
            var a = _at.HangPoint(hangOffset);
            var b = _to.HangPoint(hangOffset);
            float len = Mathf.Max(0.01f, Vector3.Distance(a, b));
            _progress += speed * dt / len;
            var p = Vector3.Lerp(a, b, Mathf.Clamp01(_progress));
            var n = Vector3.Slerp(_at.Normal, _to.Normal, Mathf.Clamp01(_progress));
            PlaceOn(p, n, (b - a).normalized);
            animator?.Play(speed > crawlSpeed * 1.5f ? "flee" : "crawl", 0.15f);
            Taps(dt, speed > crawlSpeed * 1.5f ? 0.07f : 0.14f);
            if (_progress >= 1f)
            {
                _at = _to; _to = null; _progress = 0f;
                animator?.Play("cling", 0.25f);
            }
        }
        float _progress, _punchCooldown;

        void Taps(float dt, float interval)
        {
            _tapTimer -= dt;
            if (_tapTimer > 0f) return;
            _tapTimer = interval * Random.Range(0.6f, 1.4f);
            SoundAt("clerk_tap", transform.position, 0.55f);
        }

        void PlaceOn(Vector3 p, Vector3 normal, Vector3 travel)
        {
            transform.position = p;
            var fwd = Vector3.ProjectOnPlane(travel.sqrMagnitude > 0.001f ? travel : transform.forward, normal);
            if (fwd.sqrMagnitude < 0.001f) fwd = Vector3.ProjectOnPlane(Vector3.forward, normal);
            // the creature's back points along the surface normal: on a ceiling it hangs upside down
            transform.rotation = Quaternion.LookRotation(fwd.normalized, normal);
        }

        bool AboveTarget(ClerkNode n, float slack = 1f)
        {
            if (!n || !Player) return false;
            var p = n.SurfacePoint;
            var head = Player.HeadPosition;
            var h = p - head; float up = h.y; h.y = 0f;
            return h.magnitude < ambushHorizontal * slack && up > 0.3f && up < 5f;
        }

        bool Observed()
        {
            if (!Player) return false;
            var to = EyePosition - Player.HeadPosition;
            if (Vector3.Angle(Player.HeadForward, to) > 50f) return false;
            if (Physics.Linecast(Player.HeadPosition, EyePosition, Layers.Occluders, QueryTriggerInteraction.Ignore)) return false;
            // in total darkness and far away, it does not feel watched
            return to.magnitude < 15f || IsLit();
        }

        bool IsLit()
        {
            var p = EyePosition;
            if (PlayerStealth.LightOn(p) != null) return true;
            var wl = WorldLights.StrongestAt(p);
            return wl != null && wl.Strength > 0.5f;
        }

        ClerkNode StepToward(Vector3 target)
        {
            if (!_at) return null;
            ClerkNode best = null;
            float bd = Horizontal(_at.SurfacePoint, target) - 0.3f;
            foreach (var n in _at.neighbours)
            {
                if (!n) continue;
                // never crawl into a lit area (flares, glowsticks)
                var wl = WorldLights.StrongestAt(n.SurfacePoint);
                if (wl != null && wl.Strength > 0.3f) continue;
                float d = Horizontal(n.SurfacePoint, target);
                if (d < bd) { bd = d; best = n; }
            }
            _progress = 0f;
            return best;
        }

        ClerkNode FarthestDarkNode(int hops)
        {
            var cur = _at ? _at : NearestNode(transform.position, null);
            if (!cur) return null;
            var player = PlayerFeet;
            for (int i = 0; i < hops; i++)
            {
                ClerkNode best = null; float bd = Horizontal(cur.SurfacePoint, player);
                foreach (var n in cur.neighbours)
                {
                    if (!n) continue;
                    float d = Horizontal(n.SurfacePoint, player);
                    if (d > bd && PlayerStealth.LightOn(n.SurfacePoint) == null) { bd = d; best = n; }
                }
                if (!best) break;
                cur = best;
            }
            _progress = 0f;
            return cur == _at ? null : cur;
        }

        static float Horizontal(Vector3 a, Vector3 b) { a.y = 0f; b.y = 0f; return Vector3.Distance(a, b); }

        ClerkNode NearestNode(Vector3 p, ClerkNode exclude)
        {
            ClerkNode best = null; float bd = float.MaxValue;
            foreach (var n in ClerkNode.All)
            {
                if (!n || n == exclude || !n.Valid) continue;
                float d = (n.SurfacePoint - p).sqrMagnitude;
                if (d < bd) { bd = d; best = n; }
            }
            return best;
        }

        public override void OnNoiseHeard(in NoiseEvent e, float perceived)
        {
            if (_s == S.Dormant && perceived > 0.25f && e.fromPlayer) Enter(S.Stalk);
        }

        protected override void OnDamaged(DamageInfo info, float amount, bool stagger)
        {
            if (_s == S.Grab) { _grabHits++; return; }
            if (_s == S.Windup || _s == S.Stalk || _s == S.Freeze) { Say("clerk_hurt", 1f); Enter(S.Retreat); }
        }
    }
}
