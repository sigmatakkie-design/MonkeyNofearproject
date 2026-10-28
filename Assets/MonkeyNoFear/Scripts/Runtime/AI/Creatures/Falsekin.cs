using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.World;

namespace MonkeyNoFear.AI.Creatures
{
    /// <summary>
    /// THE FALSEKIN — an ambush predator wearing a rabbit. While disguised it uses the real rabbit model,
    /// but with learnable wrongness (never shown as UI):
    ///   * its head stays locked on the player; it never blinks or flicks an ear
    ///   * it breathes far too slowly (idle at a fraction of the normal rate) and makes no animal sounds
    ///   * it does not flee when the other rabbits bolt; it backs away while still facing you
    ///   * when you look away it sometimes "skips" a little closer between frames
    ///   * mangy patches, slightly long hind legs, ears bent in opposite directions
    /// Reveal: when you get within grabbing distance, reach for it, hit it, or linger at its nest. It
    /// unfolds (a short window to react), lunges once at short range, then retreats into the undergrowth,
    /// hides, and later puts the rabbit back on somewhere else. It can be killed (valuable gland).
    /// </summary>
    public class Falsekin : CreatureBase, IExpeditionReset
    {
        enum S { Disguised, Revealing, Ambush, Retreat, Hidden, Dead }

        [Header("Models")]
        public GameObject disguiseModel;
        public CreatureAnimator disguiseAnimator;
        public GameObject revealedModel;
        public CreatureAnimator revealedAnimator;

        [Header("Disguise")]
        public float revealDistance = 2.2f;
        public float grabRevealDistance = 0.55f;
        public float backAwayDistance = 8f;
        public float skipChancePerSecond = 0.12f;
        [Range(0.05f, 1f)] public float wrongBreathingSpeed = 0.22f;
        public Transform nest;
        public float nestRadius = 6f;

        [Header("Ambush")]
        public float lungeSpeed = 8.5f;
        public float lungeMaxTime = 1.3f;
        public float hitRange = 1.5f;
        public int maxRevealsPerExpedition = 3;
        public ItemDefinition glandDrop;
        public List<Transform> coverPoints = new List<Transform>();
        public List<Transform> redisguisePoints = new List<Transform>();

        S _s;
        float _dur, _closeTime, _nestTime, _hitAt;
        bool _hitDone;
        int _reveals;
        Vector3 _lungeDir;

        protected override void Awake()
        {
            base.Awake();
            animator = disguiseAnimator ? disguiseAnimator : animator;
            Enter(S.Disguised);
        }

        protected override void OnEnable() { base.OnEnable(); ExpeditionManager.Register(this); }
        protected override void OnDisable() { base.OnDisable(); ExpeditionManager.Unregister(this); }

        public void OnNewExpedition(int index, System.Random rng)
        {
            if (_s == S.Dead) return;
            _reveals = 0;
            Health = profile ? profile.maxHealth : 60f;
            Redisguise();
        }

        protected override bool IsChasing => _s == S.Ambush;
        protected override float ThreatLevel(float d)
        {
            if (_s == S.Ambush || _s == S.Revealing) return 1f;
            if (_s == S.Retreat) return 0.6f;
            // the forest goes quiet around it even while it pretends — a clue
            return _s == S.Disguised && d < 18f ? 0.4f : 0f;
        }

        void ShowRevealed(bool revealed)
        {
            if (disguiseModel) disguiseModel.SetActive(!revealed);
            if (revealedModel) revealedModel.SetActive(revealed);
            animator = revealed && revealedAnimator ? revealedAnimator : disguiseAnimator ? disguiseAnimator : animator;
            if (revealed && revealedAnimator && revealedAnimator.Head) eyes = revealedAnimator.Head;
            else if (!revealed && disguiseAnimator && disguiseAnimator.Head) eyes = disguiseAnimator.Head;
        }

        void Enter(S s)
        {
            _s = s;
            SetState(s.ToString());
            switch (s)
            {
                case S.Disguised:
                    ShowRevealed(false);
                    if (HasAgent) agent.updateRotation = false;
                    animator?.Play("idle", 0.3f, wrongBreathingSpeed);
                    _closeTime = 0f; _nestTime = 0f;
                    break;
                case S.Revealing:
                    Stop();
                    ShowRevealed(true);
                    _dur = animator ? animator.PlayOnce("unfold", 0.02f) : 0.9f;
                    Say("fk_reveal", 1f);
                    AudioManager.Instance?.Play2D("sting_reveal", 0.75f);
                    FXManager.Burst("fur", transform.position + Vector3.up * 0.25f, Vector3.up, new Color(0.35f, 0.28f, 0.22f), 30);
                    _reveals++;
                    GameRoot.I?.Progress.Discover("creature_falsekin");
                    break;
                case S.Ambush:
                    if (HasAgent) { agent.updateRotation = true; }
                    animator?.Play("run", 0.08f);
                    var to = PlayerFeet - transform.position; to.y = 0f;
                    _lungeDir = to.normalized;
                    _hitDone = false;
                    _dur = lungeMaxTime;
                    Say("fk_shriek", 1f);
                    break;
                case S.Retreat:
                    animator?.Play(animator && animator.Has("retreat") ? "retreat" : "run", 0.15f);
                    MoveTo(PickCover(), profile.runSpeed);
                    _dur = 7f;
                    break;
                case S.Hidden:
                    Stop();
                    if (disguiseModel) disguiseModel.SetActive(false);
                    if (revealedModel) revealedModel.SetActive(false);
                    _dur = Random.Range(25f, 45f);
                    break;
                case S.Dead:
                    Stop();
                    if (agent) agent.enabled = false;
                    ShowRevealed(true);
                    animator?.PlayOnce("death", 0.1f);
                    Say("fk_death", 1f);
                    break;
            }
        }

        protected override void Think(float dt)
        {
            switch (_s)
            {
                case S.Disguised: Disguised(dt); break;
                case S.Revealing:
                    FaceTowards(PlayerFeet, 720f);
                    if (stateTime > _dur) Enter(S.Ambush);
                    break;
                case S.Ambush: Ambush(dt); break;
                case S.Retreat:
                    if (Arrived(1f) || stateTime > _dur) Enter(S.Hidden);
                    break;
                case S.Hidden:
                    if (stateTime > _dur && DistToPlayer > 20f) Redisguise();
                    break;
            }
        }

        void Disguised(float dt)
        {
            float d = DistToPlayer;
            // the stare: head locked on the player, body still
            if (animator)
            {
                animator.LookTarget = d < 25f ? PlayerHead : (Vector3?)null;
                animator.LookWeight = 1f;
            }
            if (d < 25f) FaceTowards(PlayerFeet, 25f);

            // reveal triggers
            bool grabbing = Player && (Vector3.Distance(Player.LeftHand.Position, EyePosition) < grabRevealDistance ||
                                       Vector3.Distance(Player.RightHand.Position, EyePosition) < grabRevealDistance);
            if (d < revealDistance) _closeTime += dt; else _closeTime = 0f;
            if (nest && Vector3.Distance(PlayerFeet, nest.position) < nestRadius) _nestTime += dt; else _nestTime = 0f;
            if (_reveals < maxRevealsPerExpedition && (grabbing || _closeTime > 0.35f || _nestTime > 2f)) { Enter(S.Revealing); return; }

            // back away while facing forward (the wrong way for prey to move)
            if (d < backAwayDistance && d > revealDistance + 0.5f && HasAgent)
            {
                var away = transform.position - PlayerFeet; away.y = 0f;
                MoveTo(transform.position + away.normalized * 1.5f, 0.6f);
                animator?.Play("hop", 0.3f, 0.55f); // hop cycle too slow for the distance covered: it slides
            }
            else if (HasAgent && agent.hasPath && Arrived(0.3f)) { Stop(); animator?.Play("idle", 0.3f, wrongBreathingSpeed); }

            // the skip: shifts closer between glances
            if (Player && d > 5f && d < 20f)
            {
                bool watched = Vector3.Angle(Player.HeadForward, EyePosition - Player.HeadPosition) < 55f;
                if (!watched && Random.value < skipChancePerSecond * dt)
                {
                    var toward = (PlayerFeet - transform.position); toward.y = 0f;
                    if (SampleNav(transform.position + toward.normalized * Random.Range(0.6f, 1.3f), 0.8f, out var p) && HasAgent)
                        agent.Warp(p);
                }
            }
        }

        void Ambush(float dt)
        {
            float d = DistToPlayer;
            if (!_hitDone)
            {
                // short, extremely fast lunge along the initial direction (dodgeable), slight homing
                var to = PlayerFeet - transform.position; to.y = 0f;
                _lungeDir = Vector3.Slerp(_lungeDir, to.normalized, dt * 2f);
                if (HasAgent) agent.Move(_lungeDir * lungeSpeed * dt);
                transform.rotation = Quaternion.LookRotation(_lungeDir);
                if (d < hitRange)
                {
                    _hitDone = true;
                    animator?.PlayOnce("lunge", 0.05f);
                    TryHitPlayer(hitRange * 1.3f, 120f, profile.attackDamage, DamageType.Bite);
                    _hitAt = stateTime;
                }
            }
            if ((_hitDone && stateTime - _hitAt > 0.5f) || stateTime > _dur) Enter(S.Retreat);
        }

        Vector3 PickCover()
        {
            Vector3 best = transform.position;
            float bestScore = float.MinValue;
            foreach (var c in coverPoints)
            {
                if (!c) continue;
                float dp = Vector3.Distance(c.position, PlayerFeet);
                float dm = Vector3.Distance(c.position, transform.position);
                if (dm > 45f) continue;
                float score = dp - dm * 0.3f;
                if (score > bestScore) { bestScore = score; best = c.position; }
            }
            if (bestScore == float.MinValue)
            {
                var away = transform.position - PlayerFeet; away.y = 0f;
                SampleNav(transform.position + away.normalized * 20f, 8f, out best);
            }
            return best;
        }

        void Redisguise()
        {
            Vector3 p = transform.position;
            if (redisguisePoints.Count > 0)
            {
                var t = redisguisePoints[Random.Range(0, redisguisePoints.Count)];
                if (t) RandomNavPoint(t.position, 6f, out p);
            }
            if (HasAgent) agent.Warp(p); else transform.position = p;
            Enter(S.Disguised);
        }

        public override void OnNoiseHeard(in NoiseEvent e, float perceived) { /* it does not startle: a clue */ }

        public override bool TakeDamage(DamageInfo info)
        {
            if (_s == S.Hidden || _s == S.Dead) return false;
            return base.TakeDamage(info);
        }

        protected override void OnDamaged(DamageInfo info, float amount, bool stagger)
        {
            if (Health <= 0f) return;
            if (_s == S.Disguised) { Enter(S.Revealing); return; }
            Say("fk_hiss", 1f);
            if (_s == S.Ambush || _s == S.Revealing) Enter(S.Retreat);
        }

        protected override void OnDeath(DamageInfo info)
        {
            Enter(S.Dead);
            if (glandDrop) ItemInstance.Spawn(glandDrop, transform.position + Vector3.up * 0.3f, Random.rotation);
            GameEvents.Toast("THE FALSEKIN IS DEAD");
            var gr = GameRoot.I;
            if (gr) { gr.Progress.Stats.animalsHunted++; gr.Progress.Discover("falsekin_killed"); }
            Destroy(gameObject, 25f);
        }
    }
}
