using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.AI.Wildlife
{
    /// <summary>
    /// Ordinary wildlife (rabbit, boar, gloomrat). Grazes, idles, wanders; notices the player by sight
    /// and sound; sits up alert, then bolts — to a burrow if one is near (and hides there until things are
    /// quiet) or just away. Approaching slowly and quietly gets you closer. Killing one drops food.
    /// Boars charge when hurt or cornered. Most animals are exactly what they look like.
    /// </summary>
    public class WildAnimal : CreatureBase
    {
        enum S { Idle, Graze, Wander, Alert, Flee, Hidden, Charge, Dead }

        [Header("Wildlife")]
        public ItemDefinition foodDrop;
        public int foodCount = 1;
        public float alertRadius = 10f;
        public float fleeRadius = 5f;
        [Tooltip("Player approach speed (m/s) that startles immediately.")]
        public float startleSpeed = 1.6f;
        public float wanderRadius = 10f;
        public bool usesBurrows = true;
        public bool chargesWhenHurt;
        public string idleSound = "rabbit_sniff";
        public string moveSound = "rabbit_hop";
        public string hurtSound = "rabbit_squeal";
        public string alertSound = "rabbit_thump";
        public string moveClip = "hop";
        [Tooltip("Chance per second to blink (eyelid layer).")]
        public float blinkRate = 0.25f;

        S _s;
        float _dur, _soundTimer, _blinkTimer, _alertTime;
        Burrow _burrow;
        Renderer[] _renderers;
        Vector3 _threat;

        public bool IsDead => _s == S.Dead;
        public System.Action<WildAnimal> Died;

        protected override void Awake()
        {
            base.Awake();
            _renderers = GetComponentsInChildren<Renderer>(true);
            SetupBlinkLayer();
            Enter(S.Graze);
        }

        void SetupBlinkLayer()
        {
            if (!animator || !animator.anim || animator.anim["blink"] == null) return;
            var st = animator.anim["blink"];
            st.layer = 1;
            st.wrapMode = WrapMode.Once;
            foreach (var t in GetComponentsInChildren<Transform>(true))
                if (t.name.StartsWith("eyelid")) st.AddMixingTransform(t, true);
        }

        protected override float ThreatLevel(float d) => _s == S.Charge && d < 15f ? 0.7f : 0f;

        void Enter(S s)
        {
            _s = s;
            SetState(s.ToString());
            switch (s)
            {
                case S.Idle: Stop(); _dur = Random.Range(2f, 6f); animator?.Play("idle", 0.3f); break;
                case S.Graze: Stop(); _dur = Random.Range(3f, 9f); animator?.Play("graze", 0.3f); break;
                case S.Wander:
                    if (RandomNavPoint(home, wanderRadius, out var p)) MoveTo(p, profile.walkSpeed);
                    animator?.Play(moveClip, 0.2f);
                    break;
                case S.Alert:
                    Stop(); _dur = Random.Range(0.6f, 1.8f); _alertTime = Time.time;
                    animator?.Play("alert", 0.15f);
                    if (!string.IsNullOrEmpty(alertSound)) Say(alertSound, 0.7f);
                    break;
                case S.Flee:
                    animator?.Play("run", 0.1f);
                    _burrow = usesBurrows ? Burrow.NearestAwayFrom(transform.position, _threat, 25f) : null;
                    Vector3 dest;
                    if (_burrow) dest = _burrow.transform.position;
                    else
                    {
                        var away = (transform.position - _threat); away.y = 0f;
                        if (!SampleNav(transform.position + away.normalized * 20f, 6f, out dest)) RandomNavPoint(transform.position, 15f, out dest);
                    }
                    MoveTo(dest, profile.runSpeed);
                    _dur = 8f;
                    break;
                case S.Hidden:
                    Stop(); SetVisible(false); _dur = Random.Range(15f, 40f);
                    break;
                case S.Charge:
                    animator?.Play(animator.Has("charge") ? "charge" : "run", 0.1f);
                    Say("boar_charge", 1f);
                    _dur = 3f;
                    break;
                case S.Dead:
                    Stop();
                    if (agent) agent.enabled = false;
                    if (animator) animator.PlayOnce("death", 0.1f);
                    break;
            }
        }

        void SetVisible(bool v) { foreach (var r in _renderers) if (r) r.enabled = v; }

        public override void OnNoiseHeard(in NoiseEvent e, float perceived)
        {
            if (_s == S.Dead || _s == S.Hidden || e.source == this) return;
            if (perceived > 0.5f) { _threat = e.position; Enter(S.Flee); }
            else if (perceived > 0.15f && (_s == S.Idle || _s == S.Graze || _s == S.Wander)) { _threat = e.position; Enter(S.Alert); }
        }

        protected override void Think(float dt)
        {
            if (_s == S.Dead) return;
            float d = DistToPlayer;
            var loco = Player ? Player.locomotion : null;
            float pSpeed = loco ? loco.Speed : 0f;
            bool sees = SawPlayerRecently(0.4f);

            if (_s == S.Idle || _s == S.Graze || _s == S.Wander)
            {
                if (sees && (d < fleeRadius || (d < alertRadius && pSpeed > startleSpeed))) { _threat = PlayerFeet; Enter(S.Flee); return; }
                if (sees && d < alertRadius) { _threat = PlayerFeet; Enter(S.Alert); return; }
            }

            Blink(dt);
            Ambient(dt);
            switch (_s)
            {
                case S.Idle:
                case S.Graze:
                    if (stateTime > _dur) Enter(Random.value < 0.5f ? S.Wander : (_s == S.Idle ? S.Graze : S.Idle));
                    break;
                case S.Wander:
                    animator?.SyncSpeed(moveClip, CurrentSpeed);
                    if (Arrived(0.5f) || stateTime > 12f) Enter(S.Graze);
                    break;
                case S.Alert:
                    FaceTowards(_threat, 240f);
                    if (sees && (d < fleeRadius || pSpeed > startleSpeed * 0.7f)) { _threat = PlayerFeet; Enter(S.Flee); break; }
                    if (stateTime > _dur) Enter(sees && d < alertRadius ? S.Flee : S.Idle);
                    break;
                case S.Flee:
                    animator?.SyncSpeed("run", CurrentSpeed);
                    if (_burrow && (transform.position - _burrow.transform.position).sqrMagnitude < 1f) { Enter(S.Hidden); break; }
                    if (Arrived(0.6f) || stateTime > _dur) Enter(_burrow ? S.Hidden : S.Alert);
                    break;
                case S.Hidden:
                    if (stateTime > _dur && d > 14f) { SetVisible(true); Enter(S.Idle); }
                    break;
                case S.Charge:
                    MoveTo(PlayerFeet, profile.runSpeed * 1.05f);
                    if (d < profile.attackRange && AttackReady)
                    {
                        TryHitPlayer(profile.attackRange * 1.2f, 90f, profile.attackDamage, DamageType.Melee);
                        _threat = PlayerFeet; Enter(S.Flee);
                    }
                    else if (stateTime > _dur) { _threat = PlayerFeet; Enter(S.Flee); }
                    break;
            }
        }

        void Blink(float dt)
        {
            if (blinkRate <= 0f || !animator || !animator.anim || animator.anim["blink"] == null) return;
            _blinkTimer -= dt;
            if (_blinkTimer <= 0f)
            {
                _blinkTimer = Random.Range(0.5f, 2f) / Mathf.Max(0.01f, blinkRate);
                animator.anim.Play("blink", PlayMode.StopSameLayer);
            }
        }

        void Ambient(float dt)
        {
            _soundTimer -= dt;
            if (_soundTimer > 0f) return;
            bool moving = CurrentSpeed > 0.3f;
            _soundTimer = moving ? 0.45f / Mathf.Max(0.5f, CurrentSpeed / 2f) : Random.Range(3f, 9f);
            var snd = moving ? moveSound : idleSound;
            if (!string.IsNullOrEmpty(snd)) SoundAt(snd, transform.position, moving ? 0.5f : 0.6f);
        }

        protected override void OnDamaged(DamageInfo info, float amount, bool stagger)
        {
            if (_s == S.Dead) return;
            if (!string.IsNullOrEmpty(hurtSound)) Say(hurtSound, 1f);
            if (Health <= 0f) return;
            _threat = info.sourcePosition;
            Enter(chargesWhenHurt && DistToPlayer < 8f ? S.Charge : S.Flee);
        }

        protected override void OnDeath(DamageInfo info)
        {
            Enter(S.Dead);
            var gr = GameRoot.I;
            if (gr) { gr.Progress.Stats.animalsHunted++; gr.Progress.MarkDirty(); }
            for (int i = 0; i < foodCount; i++)
                if (foodDrop) ItemInstance.Spawn(foodDrop, transform.position + Vector3.up * 0.3f + Random.insideUnitSphere * 0.15f, Random.rotation);
            GameEvents.Toast("HUNTED: " + (profile ? profile.displayName.ToUpperInvariant() : name));
            Died?.Invoke(this);
            Destroy(gameObject, 20f);
        }
    }
}
