using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Items;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.AI.Creatures
{
    /// <summary>
    /// THE LANTERN MOURNER — rare, intelligent stalker that is drawn to artificial light. Its rules are
    /// strict so they can be learned:
    ///   1. It appears far away (end of a tunnel, across a chamber) and keeps its distance: approach and it
    ///      backs away at exactly your pace, facing you, so its carrier stays in the dark.
    ///   2. Follow it far enough and it walks toward a lure point — next to a hazard — then vanishes.
    ///   3. Light draws it in. A flashlight on (or a flare) makes it approach slowly. Within ~12 m it
    ///      disturbs your torch (flicker + rising electrical buzz: its only power over light).
    ///   4. Within ~5 m with your light on, it reaches for you. Turn the light off and it stops, confused,
    ///      and fades away. A thrown flare is a decoy: it prefers the strongest light.
    ///   5. It never attacks a player whose lights are off. Weapons only make it recoil and vanish.
    /// </summary>
    public class LanternMourner : CreatureBase, IExpeditionReset
    {
        enum S { Absent, Observe, Retreat, Lure, Drawn, Confused, Reach, Vanish }

        [Header("Appearance")]
        public float appearCheckInterval = 90f;
        [Range(0, 1)] public float appearChance = 0.35f;
        public int maxAppearancesPerExpedition = 2;
        public int minDepthLevel = 2;
        public float appearMin = 22f, appearMax = 42f;
        [Header("Behaviour")]
        public float keepDistance = 19f;
        public float followDistanceToLure = 25f;
        public float drawnSpeed = 1.0f;
        public float interferenceRange = 12f;
        public float reachRange = 5f;
        public float reachDelay = 1.5f;
        [Header("Glow")]
        public Light chestLight;
        public Light lampLight;

        S _s = S.Absent;
        float _checkTimer, _dur, _fade, _reachCharge, _clinkTimer, _hitAt;
        int _appearances;
        bool _hit;
        Vector3 _lastPlayerPos;
        float _followed;
        MournerPoint _lure;
        Renderer[] _renderers;
        ManagedLoop _buzz;

        protected override void Awake()
        {
            base.Awake();
            _renderers = GetComponentsInChildren<Renderer>(true);
            SetVisible(false);
            _checkTimer = appearCheckInterval * 0.5f;
        }

        void Start()
        {
            if (AudioManager.Instance) _buzz = AudioManager.Instance.CreateLoop("mourner_buzz_loop", eyes ? eyes : transform);
        }

        protected override void OnEnable() { base.OnEnable(); ExpeditionManager.Register(this); }
        protected override void OnDisable() { base.OnDisable(); ExpeditionManager.Unregister(this); }

        public void OnNewExpedition(int index, System.Random rng)
        {
            _appearances = 0;
            _checkTimer = appearCheckInterval * (0.4f + (float)rng.NextDouble() * 0.6f);
            Enter(S.Absent);
        }

        protected override bool IsChasing => _s == S.Reach;
        protected override float ThreatLevel(float d)
        {
            switch (_s)
            {
                case S.Reach: return 1f;
                case S.Drawn: return d < interferenceRange ? 0.85f : 0.55f;
                case S.Absent: return 0f;
                default: return 0.45f;
            }
        }

        void SetVisible(bool v)
        {
            foreach (var r in _renderers) if (r) r.enabled = v;
            if (agent) agent.enabled = v;
            if (voice) { if (v) voice.FadeIn(0.5f); else voice.FadeOut(0.5f); }
        }

        void Enter(S s)
        {
            _s = s;
            SetState(s.ToString());
            switch (s)
            {
                case S.Absent: SetVisible(false); _buzz?.FadeOut(1f); break;
                case S.Observe: Stop(); animator?.Play("idle", 0.4f); _dur = Random.Range(6f, 12f); break;
                case S.Retreat: animator?.Play("retreat", 0.3f); if (HasAgent) agent.updateRotation = false; break;
                case S.Lure:
                    animator?.Play("walk", 0.3f);
                    if (HasAgent) agent.updateRotation = true;
                    _lure = NearestLure();
                    if (_lure) MoveTo(_lure.transform.position, profile.walkSpeed); else Enter(S.Vanish);
                    break;
                case S.Drawn: animator?.Play("walk", 0.3f); if (HasAgent) agent.updateRotation = true; break;
                case S.Confused:
                    Stop(); _dur = animator ? animator.PlayOnce("turn_head", 0.2f) : 1.5f;
                    _reachCharge = 0f;
                    break;
                case S.Reach:
                    Stop(); _hit = false;
                    _dur = animator ? animator.PlayOnce("reach", 0.15f) : 1.6f;
                    _hitAt = animator ? animator.EventTime("reach", "hit", 0.75f) : 1.2f;
                    Say("mourner_reach", 1f);
                    break;
                case S.Vanish: Stop(); _fade = 1f; _dur = 2f; break;
            }
        }

        protected override void Update()
        {
            if (_s == S.Absent)
            {
                TryAppear();
                return;
            }
            base.Update();
        }

        void TryAppear()
        {
            var area = AreaManager.Instance;
            if (!area || area.DepthLevel < minDepthLevel || !Player || _appearances >= maxAppearancesPerExpedition) return;
            _checkTimer -= Time.deltaTime;
            if (_checkTimer > 0f) return;
            _checkTimer = appearCheckInterval;
            if (Random.value > appearChance) return;
            var p = PickAppearPoint();
            if (!p) return;
            transform.position = p.transform.position;
            SetVisible(true);
            if (HasAgent) agent.Warp(p.transform.position);
            transform.rotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(PlayerFeet - transform.position, Vector3.up).normalized + Vector3.forward * 0.001f);
            _appearances++;
            _fade = 0f;
            _followed = 0f;
            _lastPlayerPos = PlayerFeet;
            Say("mourner_wail", 0.7f);
            Enter(S.Observe);
        }

        MournerPoint PickAppearPoint()
        {
            MournerPoint best = null; float bestScore = float.MinValue;
            foreach (var m in MournerPoint.All)
            {
                if (m.isLure) continue;
                float d = Vector3.Distance(m.transform.position, PlayerFeet);
                if (d < appearMin || d > appearMax) continue;
                // prefer points the player can glimpse down a passage
                bool los = !Physics.Linecast(m.transform.position + Vector3.up * 1.8f, PlayerHead, Layers.Occluders);
                float angle = Vector3.Angle(Player.HeadForward, m.transform.position - PlayerHead);
                float score = (los ? 10f : 0f) - angle * 0.05f + Random.value * 3f;
                if (score > bestScore) { bestScore = score; best = m; }
            }
            return best;
        }

        MournerPoint NearestLure()
        {
            MournerPoint best = null; float bd = 80f;
            foreach (var m in MournerPoint.All)
            {
                if (!m.isLure) continue;
                float d = Vector3.Distance(m.transform.position, transform.position);
                if (d < bd) { bd = d; best = m; }
            }
            return best;
        }

        protected override void Think(float dt)
        {
            Glow(dt);
            Clinks(dt);
            float d = DistToPlayer;
            var playerLight = PlayerStealth.Instance && PlayerStealth.Instance.OwnLightOn;
            var attractor = WorldLights.MostAttractive(transform.position, 30f);
            bool flashlightOnMe = PlayerStealth.LightOn(EyePosition) != null;
            bool drawnByPlayer = (playerLight && d < 26f) || flashlightOnMe;
            if (animator) { animator.LookTarget = PlayerHead; animator.LookWeight = 0.7f; }

            // track how far the player follows it
            if (Player)
            {
                var pf = PlayerFeet;
                float moved = Vector3.Distance(pf, _lastPlayerPos);
                if (moved < 3f && Vector3.Dot(pf - _lastPlayerPos, transform.position - _lastPlayerPos) > 0f) _followed += moved;
                _lastPlayerPos = pf;
            }

            switch (_s)
            {
                case S.Observe:
                    FaceTowards(PlayerFeet, 30f);
                    if (drawnByPlayer || attractor != null) { Enter(S.Drawn); break; }
                    if (d < keepDistance) { Enter(S.Retreat); break; }
                    if (stateTime > _dur) Enter(S.Vanish);
                    break;

                case S.Retreat:
                    if (drawnByPlayer) { Enter(S.Drawn); break; }
                    if (_followed > followDistanceToLure) { Enter(S.Lure); break; }
                    FaceTowards(PlayerFeet, 90f);
                    if (d < keepDistance + 3f)
                    {
                        // back away at the player's pace
                        float pace = Player ? Mathf.Clamp(Player.locomotion.Speed, 0.6f, 3.6f) : 1f;
                        var away = transform.position - PlayerFeet; away.y = 0f;
                        if (SampleNav(transform.position + away.normalized * 3f, 2f, out var p)) MoveTo(p, pace);
                        if (HasAgent && agent.pathStatus != UnityEngine.AI.NavMeshPathStatus.PathComplete && stateTime > 2f) { Enter(S.Vanish); break; }
                    }
                    else Stop();
                    if (stateTime > 45f) Enter(S.Vanish);
                    break;

                case S.Lure:
                    if (drawnByPlayer) { Enter(S.Drawn); break; }
                    if (_lure && Arrived(1.5f)) { Stop(); animator?.Play("idle", 0.4f); if (d < 12f) Enter(S.Vanish); }
                    break;

                case S.Drawn:
                    // the strongest light wins: a flare thrown away from you is a decoy
                    Vector3 lightPos = PlayerFeet;
                    float lightStrength = drawnByPlayer ? 0.75f : 0f;
                    if (attractor != null && attractor.Strength > lightStrength) { lightPos = attractor.Position; lightStrength = attractor.Strength; }
                    if (lightStrength <= 0f) { Enter(playerLight ? S.Drawn : S.Confused); if (!playerLight) break; }
                    MoveTo(lightPos, drawnSpeed);
                    bool targetingPlayer = lightPos == PlayerFeet;
                    float interference = targetingPlayer ? Mathf.Clamp01(1f - (d - reachRange) / (interferenceRange - reachRange)) : 0f;
                    if (interference > 0f)
                    {
                        foreach (var f in Flashlight.All) f.Interfere(interference * 0.8f);
                        _buzz?.FadeIn(2f); _buzz?.SetVolume(interference);
                    }
                    else _buzz?.FadeOut(1f);
                    if (targetingPlayer && d < reachRange)
                    {
                        _reachCharge += dt;
                        if (_reachCharge > reachDelay && playerLight) { Enter(S.Reach); break; }
                    }
                    else _reachCharge = Mathf.Max(0f, _reachCharge - dt);
                    if (!targetingPlayer && Arrived(1.5f)) { Stop(); animator?.Play("idle", 0.4f); }
                    break;

                case S.Confused:
                    _buzz?.FadeOut(1f);
                    if (playerLight && d < 26f) { Enter(S.Drawn); break; }
                    if (stateTime > _dur) Enter(S.Vanish);
                    break;

                case S.Reach:
                    FaceTowards(PlayerFeet, 120f);
                    bool lightStillOn = PlayerStealth.Instance && PlayerStealth.Instance.OwnLightOn;
                    if (!_hit && !lightStillOn && stateTime < _hitAt) { Enter(S.Confused); break; } // rule 5
                    if (!_hit && stateTime >= _hitAt)
                    {
                        _hit = true;
                        TryHitPlayer(reachRange * 0.75f, 100f, profile.attackDamage, DamageType.Drain);
                    }
                    if (stateTime > _dur) Enter(S.Vanish);
                    break;

                case S.Vanish:
                    _fade = Mathf.MoveTowards(_fade, 0f, dt / _dur);
                    _buzz?.FadeOut(1f);
                    if (_fade <= 0f) Enter(S.Absent);
                    break;
            }
        }

        void Glow(float dt)
        {
            if (_s != S.Vanish) _fade = Mathf.MoveTowards(_fade, 1f, dt * 0.5f);
            float flicker = 0.65f + Mathf.PerlinNoise(Time.time * 3f, 1.7f) * 0.5f;
            float k = _s == S.Reach ? 1.8f : _s == S.Drawn ? 1.2f : 1f;
            if (chestLight) { chestLight.intensity = 0.9f * flicker * _fade * k; chestLight.enabled = _fade > 0.01f; }
            if (lampLight) { lampLight.intensity = 0.4f * Mathf.PerlinNoise(Time.time * 5f, 3.3f) * _fade; lampLight.enabled = _fade > 0.01f; }
        }

        void Clinks(float dt)
        {
            _clinkTimer -= dt;
            if (_clinkTimer > 0f) return;
            _clinkTimer = CurrentSpeed > 0.2f ? Random.Range(0.6f, 1.4f) : Random.Range(3f, 7f);
            SoundAt("mourner_clink", lampLight ? lampLight.transform.position : transform.position, 0.6f);
        }

        public override bool TakeDamage(DamageInfo info)
        {
            if (_s == S.Absent) return false;
            animator?.PlayOnce("recoil", 0.1f);
            Say("mourner_recoil", 1f);
            Enter(S.Vanish);
            return true;
        }
    }
}
