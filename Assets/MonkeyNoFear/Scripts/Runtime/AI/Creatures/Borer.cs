using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.AI.Creatures
{
    /// <summary>
    /// THE BORER — tunnelling brute that controls a section of the mine and hunts by vibration.
    ///  Dormant: underground. Noise in its territory (mining above all, metal impacts, carts, running)
    ///   raises agitation. First a deep impact sounds from beneath the floor and dust falls (warning 1),
    ///   then a closer one (warning 2). Keep mining and it emerges from the authored hole nearest the
    ///   noise — never through solid rock.
    ///  Hunt: walks to the source of vibrations. It feels a moving player within ~14 m; it only sees you
    ///   within a few meters. Stand still and it loses you.
    ///  Charge: straight-line rush with poor turning — side-step it. Attack: rears up (roar), slams.
    ///  Armoured back: hits only stagger it when they land on its face/front during a wind-up or charge.
    ///  Quiet for a while → it presses its palm to the ground, listens, then returns to a hole and burrows.
    /// </summary>
    public class Borer : CreatureBase, IExpeditionReset
    {
        enum S { Dormant, Emerging, Hunt, Sense, Return, Charge, Attack, Recover, Stagger, Burrowing }

        [Header("Territory")]
        public float territoryRadius = 40f;
        public Transform territoryCentre;
        public float warn1 = 35f, warn2 = 60f, emergeAt = 85f;
        public float agitationDecay = 1.5f;
        [Header("Senses")]
        public float vibrationRange = 14f;
        public float vibrationSpeed = 1.8f;
        public float sightRange = 5f;
        public float quietToBurrow = 10f;
        [Header("Combat")]
        public float chargeSpeed = 4.5f;
        public float chargeTurnRate = 70f;
        public float chargeMaxTime = 3f;
        public float burrowCooldown = 45f;

        S _s = S.Dormant;
        float _agitation, _lastVibration, _cooldownUntil, _dur, _hitAt;
        bool _warned1, _warned2, _hit;
        Vector3 _target, _lastNoise;
        BorerHole _hole;
        Renderer[] _renderers;
        Collider[] _colliders;
        ManagedLoop _grind;

        protected override void Awake()
        {
            base.Awake();
            _renderers = GetComponentsInChildren<Renderer>(true);
            _colliders = GetComponentsInChildren<Collider>(true);
            SetPresent(false);
        }

        void Start()
        {
            if (AudioManager.Instance) _grind = AudioManager.Instance.CreateLoop("borer_grind_loop", eyes ? eyes : transform);
        }

        protected override void OnEnable() { base.OnEnable(); ExpeditionManager.Register(this); }
        protected override void OnDisable() { base.OnDisable(); ExpeditionManager.Unregister(this); }

        public void OnNewExpedition(int index, System.Random rng)
        {
            _agitation = 0f; _warned1 = _warned2 = false;
            Health = profile ? profile.maxHealth : 400f;
            SetPresent(false);
            Enter(S.Dormant);
        }

        Vector3 Centre => territoryCentre ? territoryCentre.position : home;

        protected override bool IsChasing => _s == S.Charge || _s == S.Attack || _s == S.Hunt && SawPlayerRecently(2f);
        protected override float ThreatLevel(float d)
        {
            if (_s == S.Dormant) return _agitation > warn1 && d < territoryRadius ? 0.5f : 0f;
            return d < 30f ? (_s == S.Charge || _s == S.Attack ? 1f : 0.8f) : 0.3f;
        }

        void SetPresent(bool v)
        {
            foreach (var r in _renderers) if (r) r.enabled = v;
            foreach (var c in _colliders) if (c) c.enabled = v;
            if (agent) agent.enabled = v;
        }

        void Enter(S s)
        {
            _s = s;
            SetState(s.ToString());
            switch (s)
            {
                case S.Dormant:
                    _grind?.FadeOut(1f);
                    break;
                case S.Emerging:
                    _hole = BorerHole.Nearest(_lastNoise);
                    var p = _hole ? _hole.transform.position : Centre;
                    transform.position = p;
                    transform.rotation = _hole ? Quaternion.LookRotation(Vector3.ProjectOnPlane(_hole.transform.forward, Vector3.up)) : transform.rotation;
                    SetPresent(true);
                    if (HasAgent) agent.Warp(p);
                    _hole?.Burst();
                    _dur = animator ? animator.PlayOnce("emerge", 0.05f) : 2f;
                    SoundAt("borer_emerge", p, 1f);
                    Say("borer_roar", 1f);
                    _grind?.FadeIn(1f);
                    GameRoot.I?.Progress.Discover("creature_borer");
                    break;
                case S.Hunt:
                    animator?.Play("walk", 0.3f);
                    if (HasAgent) agent.angularSpeed = profile.turnSpeed;
                    break;
                case S.Return:
                    _hole = BorerHole.Nearest(transform.position);
                    animator?.Play("walk", 0.3f);
                    break;
                case S.Sense:
                    Stop(); _dur = 4f;
                    animator?.Play("sense", 0.4f);
                    break;
                case S.Charge:
                    animator?.Play("charge", 0.15f);
                    Say("borer_roar", 1f);
                    if (HasAgent) agent.angularSpeed = chargeTurnRate;
                    _dur = chargeMaxTime;
                    break;
                case S.Attack:
                    Stop(); _hit = false;
                    _dur = animator ? animator.PlayOnce("attack", 0.1f) : 1.4f;
                    _hitAt = animator ? animator.EventTime("attack", "hit", 0.6f) : 0.9f;
                    Say("borer_roar", 1f);
                    break;
                case S.Recover:
                    _dur = profile.postHitRecovery + 0.5f;
                    animator?.Play("idle", 0.3f);
                    Stop();
                    break;
                case S.Stagger:
                    Stop();
                    _dur = animator ? animator.PlayOnce("stagger", 0.08f) : 1.5f;
                    Say("borer_hurt", 1f);
                    break;
                case S.Burrowing:
                    Stop();
                    _dur = animator ? animator.PlayOnce("burrow", 0.2f) : 2f;
                    SoundAt("borer_dig_loop", transform.position, 1f);
                    break;
            }
        }

        public override void OnNoiseHeard(in NoiseEvent e, float perceived)
        {
            if (e.source == this) return;
            if (Vector3.Distance(e.position, Centre) > territoryRadius) return;
            float k;
            switch (e.kind)
            {
                case NoiseKind.Mining: k = 32f; break;
                case NoiseKind.MetalImpact: case NoiseKind.Cart: case NoiseKind.Break: k = 22f; break;
                case NoiseKind.Lure: k = 26f; break;
                case NoiseKind.HandImpact: k = 9f; break;
                default: k = 6f; break;
            }
            if (Time.time < _cooldownUntil) k *= 0.5f;
            _lastNoise = e.position;
            if (_s == S.Dormant) _agitation += perceived * k;
            else
            {
                _target = e.position; _lastVibration = Time.time;
                if (e.fromPlayer) LastKnownPlayerPos = e.position;
            }
        }

        protected override void Think(float dt)
        {
            switch (_s)
            {
                case S.Dormant: Dormant(dt); break;
                case S.Emerging:
                    if (stateTime > _dur) { _target = _lastNoise; _lastVibration = Time.time; Enter(S.Hunt); }
                    break;
                case S.Hunt:
                    Feel();
                    animator?.SyncSpeed("walk", CurrentSpeed);
                    MoveTo(_target, profile.walkSpeed);
                    if (CanCharge()) { Enter(S.Charge); break; }
                    if (DistToPlayer < profile.attackRange && SeesPlayerClose()) { Enter(S.Attack); break; }
                    if (Time.time - _lastVibration > quietToBurrow && Arrived(1.5f)) Enter(S.Sense);
                    break;
                case S.Sense:
                    Feel();
                    if (Time.time - _lastVibration < 0.5f) { Enter(S.Hunt); break; }
                    if (stateTime > _dur) Enter(S.Return);
                    break;
                case S.Return:
                    Feel();
                    if (Time.time - _lastVibration < 0.5f) { Enter(S.Hunt); break; }
                    if (!_hole) { Enter(S.Burrowing); break; }
                    MoveTo(_hole.transform.position, profile.walkSpeed);
                    animator?.SyncSpeed("walk", CurrentSpeed);
                    if (Vector3.Distance(transform.position, _hole.transform.position) < 2f || stateTime > 30f) Enter(S.Burrowing);
                    break;
                case S.Charge:
                    Feel();
                    MoveTo(PlayerFeet, chargeSpeed);
                    animator?.SyncSpeed("charge", CurrentSpeed);
                    if (DistToPlayer < profile.attackRange) { Enter(S.Attack); break; }
                    if (stateTime > _dur) Enter(S.Hunt);
                    break;
                case S.Attack:
                    if (stateTime < _hitAt) FaceTowards(PlayerFeet, 90f);
                    if (!_hit && stateTime >= _hitAt)
                    {
                        _hit = true;
                        TryHitPlayer(profile.attackRange * 1.1f, 100f, profile.attackDamage, DamageType.Crush);
                        SoundAt("borer_impact_close", transform.position + transform.forward * 1.5f, 1f);
                        FXManager.Burst("dust", transform.position + transform.forward * 1.5f, Vector3.up, new Color(0.5f, 0.47f, 0.43f, 0.5f), 20);
                        NoiseSystem.Emit(transform.position, 0.6f, NoiseKind.Combat, false, this);
                    }
                    if (stateTime > _dur) Enter(S.Recover);
                    break;
                case S.Recover:
                    if (stateTime > _dur) Enter(S.Hunt);
                    break;
                case S.Stagger:
                    if (stateTime > _dur) Enter(S.Hunt);
                    break;
                case S.Burrowing:
                    if (stateTime > _dur)
                    {
                        SetPresent(false);
                        _agitation = 0f; _warned1 = _warned2 = false;
                        _cooldownUntil = Time.time + burrowCooldown;
                        Enter(S.Dormant);
                    }
                    break;
            }
        }

        void Dormant(float dt)
        {
            _agitation = Mathf.Max(0f, _agitation - agitationDecay * dt);
            if (!Player || Vector3.Distance(PlayerFeet, Centre) > territoryRadius * 1.3f) return;
            if (!_warned1 && _agitation > warn1) { _warned1 = true; DeepImpact(false); }
            if (!_warned2 && _agitation > warn2) { _warned2 = true; DeepImpact(true); }
            if (_agitation < warn1 * 0.5f) { _warned1 = false; _warned2 = false; }
            if (_agitation > emergeAt) Enter(S.Emerging);
        }

        void DeepImpact(bool close)
        {
            var below = _lastNoise + Vector3.down * (close ? 2.5f : 5f);
            SoundAt(close ? "borer_impact_close" : "borer_impact_deep", below, 1f);
            // dust trickles from the ceiling above the player; controllers rumble — no camera shake in VR
            if (Player)
            {
                var above = Player.HeadPosition + Vector3.up * 1.5f;
                if (Physics.Raycast(Player.HeadPosition, Vector3.up, out var hit, 8f, Layers.Occluders)) above = hit.point - Vector3.up * 0.1f;
                FXManager.Burst("dust_fall", above, Vector3.down, new Color(0.55f, 0.5f, 0.45f, 0.6f), close ? 40 : 20);
                SoundAt("dust_fall", above, 0.8f);
                Player.Haptic(Hand.Left, close ? 0.6f : 0.3f, 0.5f);
                Player.Haptic(Hand.Right, close ? 0.6f : 0.3f, 0.5f);
            }
        }

        /// <summary>Vibration sense: a moving player is felt through the ground; a still one is not.</summary>
        void Feel()
        {
            if (!Player) return;
            float d = DistToPlayer;
            if (d < vibrationRange && Player.locomotion.Speed > vibrationSpeed)
            {
                _target = PlayerFeet; LastKnownPlayerPos = _target; _lastVibration = Time.time;
                Stimulus(2f);
            }
            if (SeesPlayerClose()) { _target = PlayerFeet; _lastVibration = Time.time; }
        }

        bool SeesPlayerClose() => DistToPlayer < sightRange && !Physics.Linecast(EyePosition, PlayerHead, Layers.Occluders);

        bool CanCharge() => AttackReady && DistToPlayer < 10f && DistToPlayer > profile.attackRange && Time.time - _lastVibration < 0.5f
                            && (_target - PlayerFeet).sqrMagnitude < 4f && Reachable(PlayerFeet);

        public override bool TakeDamage(DamageInfo info)
        {
            if (_s == S.Dormant || _s == S.Burrowing || _s == S.Emerging) return false;
            // armoured back: only frontal hits during a wind-up / charge get through
            var from = info.sourcePosition - transform.position; from.y = 0f;
            bool frontal = Vector3.Dot(from.normalized, transform.forward) > 0.4f;
            bool exposed = (_s == S.Attack && stateTime < _hitAt) || _s == S.Charge;
            if (!frontal || !exposed)
            {
                SoundAt("spear_hit_hard", info.hitPoint, 1f);
                FXManager.Burst("sparks", info.hitPoint, -from.normalized, new Color(1f, 0.8f, 0.5f), 8);
                Stimulus(30f);
                _target = info.sourcePosition; _lastVibration = Time.time;
                return false;
            }
            return base.TakeDamage(info);
        }

        protected override void OnDamaged(DamageInfo info, float amount, bool stagger) => Enter(S.Stagger);
    }
}
