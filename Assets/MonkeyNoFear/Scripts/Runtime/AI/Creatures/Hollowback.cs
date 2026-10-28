using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.AI.Creatures
{
    /// <summary>
    /// THE HOLLOWBACK — slow territorial forest hunter that hunts by sound.
    ///  Idle: stands motionless for long periods, scrapes nails on trunks, leans around trees.
    ///  Wander: slow walk between authored interest points (camps, trees) — never a visible loop.
    ///  Listen: a faint noise freezes it; the small head tilts toward the sound.
    ///  Alert → Investigate: a clear noise snaps its head round, then it walks to where the sound was.
    ///  Search: inspects likely hiding spots (near cover) around the last known position.
    ///  Follow: rises out of the hunch and stalks toward the player once it has a lead.
    ///  Chase: repeated loud noises / a running player trigger a gallop with slapping arms.
    ///  Attack: unmistakable gurgling warning, wind-up, long-armed swipe; then it backs off.
    ///  Counterplay: stay still behind cover (it cannot see through it and hears nothing), break line of
    ///  sight, climb where it cannot path, throw a rattle can to lure it away, stab it to buy a stagger.
    /// </summary>
    public class Hollowback : CreatureBase
    {
        enum S { Idle, Wander, Listen, Alert, Investigate, Search, Follow, Chase, Attack, Recover, Stagger, Retreat, Unreachable }

        [Header("Territory")]
        public List<Transform> interestPoints = new List<Transform>();
        public float territoryRadius = 70f;

        [Header("Behaviour")]
        public float listenThreshold = 10f;
        public float investigateThreshold = 32f;
        public float followThreshold = 62f;
        [Tooltip("Loud player noises within the window that make it charge.")]
        public int chaseNoiseCount = 3;
        public float chaseNoiseWindow = 6f;
        public float idleMin = 6f, idleMax = 22f;
        public float searchPointDuration = 3f;

        S _s = S.Idle;
        float _stateDur;
        Vector3 _noisePos;
        readonly Queue<float> _loudNoises = new Queue<float>();
        readonly List<Vector3> _searchPoints = new List<Vector3>();
        int _searchIndex;
        float _stepTimer, _scrapeTimer, _attackHitAt;
        bool _hitDone;
        float _anger;

        protected override void Awake()
        {
            base.Awake();
            if (animator) animator.AnimEvent += OnAnimEvent;
            Enter(S.Idle);
        }

        protected override bool IsChasing => _s == S.Chase || _s == S.Attack;

        protected override float ThreatLevel(float d)
        {
            if (d > 45f) return 0f;
            switch (_s)
            {
                case S.Chase: case S.Attack: return 1f;
                case S.Follow: return 0.75f;
                case S.Investigate: case S.Search: return 0.55f;
                case S.Listen: case S.Alert: return 0.5f;
                default: return d < 30f ? 0.35f : 0.15f;
            }
        }

        void Enter(S s)
        {
            _s = s;
            SetState(s.ToString());
            _hitDone = false;
            var a = animator;
            switch (s)
            {
                case S.Idle:
                    Stop(); _stateDur = Random.Range(idleMin, idleMax);
                    a?.Play("idle", 0.4f);
                    break;
                case S.Wander:
                    a?.Play("walk", 0.4f);
                    if (!PickWanderTarget(out var p)) { Enter(S.Idle); return; }
                    MoveTo(p, profile.walkSpeed);
                    break;
                case S.Listen:
                    Stop(); _stateDur = Random.Range(2.5f, 5f);
                    a?.Play("listen", 0.3f);
                    Say("hb_listen_click", 0.6f);
                    break;
                case S.Alert:
                    Stop(); _stateDur = a ? a.PlayOnce("alert", 0.1f) : 0.8f;
                    Say("hb_alert", 1f);
                    break;
                case S.Investigate:
                    a?.Play("walk", 0.3f);
                    MoveTo(_noisePos, profile.walkSpeed * 1.25f);
                    break;
                case S.Search:
                    BuildSearchPoints(LastKnownPlayerPos.sqrMagnitude > 0 && SawPlayerRecently(30f) ? LastKnownPlayerPos : _noisePos);
                    _searchIndex = 0;
                    _stateDur = profile.searchTime;
                    a?.Play("walk", 0.3f);
                    break;
                case S.Follow:
                    a?.Play("follow", 0.3f);
                    break;
                case S.Chase:
                    a?.Play("run", 0.2f);
                    Say("hb_alert", 0.8f);
                    break;
                case S.Attack:
                    Stop();
                    Say("hb_warning", 1f);
                    float len = a ? a.PlayOnce("attack", 0.1f) : 1.2f;
                    _attackHitAt = a ? a.EventTime("attack", "hit", 0.6f) : 0.7f;
                    _stateDur = len;
                    break;
                case S.Recover:
                    _stateDur = profile.postHitRecovery;
                    a?.Play("walk", 0.3f);
                    var away = transform.position - PlayerFeet; away.y = 0f;
                    if (SampleNav(transform.position + away.normalized * 3f, 2f, out var back)) MoveTo(back, profile.walkSpeed);
                    break;
                case S.Stagger:
                    Stop();
                    _stateDur = a ? a.PlayOnce("stagger", 0.08f) : 1f;
                    Say("hb_hurt", 1f);
                    break;
                case S.Retreat:
                    a?.Play("run", 0.3f);
                    _stateDur = 6f;
                    var dir = transform.position - PlayerFeet; dir.y = 0f;
                    if (SampleNav(transform.position + dir.normalized * 18f, 6f, out var r)) MoveTo(r, profile.runSpeed * 0.8f);
                    break;
                case S.Unreachable:
                    Stop(); _stateDur = Random.Range(5f, 9f);
                    a?.Play("listen", 0.4f);
                    break;
            }
        }

        public override void OnNoiseHeard(in NoiseEvent e, float perceived)
        {
            if (e.source == this) return;
            float boost = e.kind == NoiseKind.Lure ? 1.25f : e.kind == NoiseKind.Mining || e.kind == NoiseKind.MetalImpact ? 1.15f : 1f;
            float amount = perceived * 75f * boost;
            Stimulus(amount);
            LastHeardTime = Time.time;
            // it goes where the sound came from — it does not magically know where the player is
            _noisePos = e.position;
            if (e.fromPlayer) LastKnownPlayerPos = e.position;
            if (e.fromPlayer && perceived > 0.3f) _loudNoises.Enqueue(Time.time);

            switch (_s)
            {
                case S.Idle: case S.Wander:
                    if (amount > investigateThreshold) Enter(S.Alert);
                    else if (Awareness > listenThreshold) Enter(S.Listen);
                    break;
                case S.Listen:
                    if (Awareness > investigateThreshold) Enter(S.Alert);
                    break;
                case S.Search: case S.Investigate:
                    if (_s == S.Search || (_noisePos - (HasAgent ? agent.destination : transform.position)).sqrMagnitude > 9f) Enter(S.Investigate);
                    break;
            }
        }

        protected override void OnSeePlayer(float q)
        {
            // movement is far more noticeable than a still silhouette
            var st = Player ? Player.locomotion : null;
            float motion = st ? Mathf.Clamp01(st.Speed / 2f) : 0.5f;
            Stimulus(q * (8f + motion * 30f) * 0.15f * 6f);
            if (_s == S.Idle || _s == S.Wander || _s == S.Listen)
            {
                if (Awareness > followThreshold) Enter(S.Follow);
                else if (Awareness > investigateThreshold) { _noisePos = LastKnownPlayerPos; Enter(S.Alert); }
            }
            if ((_s == S.Follow || _s == S.Search || _s == S.Investigate) && st && st.Speed > 3f && DistToPlayer < 22f) Enter(S.Chase);
        }

        bool WantsChase()
        {
            while (_loudNoises.Count > 0 && Time.time - _loudNoises.Peek() > chaseNoiseWindow) _loudNoises.Dequeue();
            if (_loudNoises.Count >= chaseNoiseCount) return true;
            if (_anger > 0f && SawPlayerRecently(1f)) return true;
            return Awareness > 95f && SawPlayerRecently(0.5f) && DistToPlayer < 14f;
        }

        protected override void Think(float dt)
        {
            _anger = Mathf.Max(0f, _anger - dt);
            if (animator) animator.HeadTilt = _s == S.Listen || _s == S.Unreachable ? Mathf.Sin(stateTime * 0.7f) * 25f : 0f;
            if (animator)
            {
                bool look = _s != S.Idle && _s != S.Wander;
                animator.LookTarget = look ? (SawPlayerRecently(2f) ? PlayerHead : _noisePos + Vector3.up) : (Vector3?)null;
                animator.LookWeight = _s == S.Alert ? 1f : 0.8f;
            }
            if (voice) voice.SetVolume(_s == S.Chase ? 1f : 0.6f);
            Footsteps(dt);

            switch (_s)
            {
                case S.Idle:
                    MaybeScrape(dt);
                    if (stateTime > _stateDur) Enter(S.Wander);
                    break;
                case S.Wander:
                    MaybeScrape(dt);
                    animator?.SyncSpeed("walk", CurrentSpeed);
                    if (Arrived(1f)) Enter(S.Idle);
                    break;
                case S.Listen:
                    FaceTowards(_noisePos, 60f);
                    if (stateTime > _stateDur) Enter(Awareness > listenThreshold ? S.Investigate : S.Idle);
                    break;
                case S.Alert:
                    FaceTowards(_noisePos, 420f); // the head-snap
                    if (stateTime > _stateDur) Enter(WantsChase() ? S.Chase : S.Investigate);
                    break;
                case S.Investigate:
                    animator?.SyncSpeed("walk", CurrentSpeed);
                    if (WantsChase()) { Enter(S.Chase); break; }
                    if (Awareness > followThreshold && SawPlayerRecently(1.5f)) { Enter(S.Follow); break; }
                    if (Arrived(1.2f)) Enter(S.Search);
                    break;
                case S.Search:
                    DoSearch();
                    break;
                case S.Follow:
                    animator?.SyncSpeed("follow", CurrentSpeed);
                    if (WantsChase()) { Enter(S.Chase); break; }
                    MoveTo(LastKnownPlayerPos, profile.alertSpeed);
                    if (DistToPlayer < profile.attackRange && SawPlayerRecently(0.5f)) { Enter(S.Attack); break; }
                    if (Arrived(1.5f) && !SawPlayerRecently(2f)) Enter(S.Search);
                    if (!SawPlayerRecently(profile.loseInterestTime) && !HeardPlayerRecently(profile.loseInterestTime)) Enter(S.Search);
                    break;
                case S.Chase:
                    animator?.SyncSpeed("run", CurrentSpeed);
                    bool tracking = SawPlayerRecently(1f) || HeardPlayerRecently(1.5f);
                    var target = tracking ? (SawPlayerRecently(1f) ? PlayerFeet : LastKnownPlayerPos) : LastKnownPlayerPos;
                    if (!Reachable(target) && DistToPlayer < 25f) { Enter(S.Unreachable); break; }
                    MoveTo(target, profile.runSpeed);
                    if (DistToPlayer < profile.attackRange * 0.9f && AttackReady) { Enter(S.Attack); break; }
                    if (!tracking && Arrived(1.5f)) Enter(S.Search);
                    if (!SawPlayerRecently(profile.loseInterestTime) && !HeardPlayerRecently(profile.loseInterestTime)) Enter(S.Search);
                    break;
                case S.Attack:
                    if (stateTime < _attackHitAt) FaceTowards(PlayerFeet, 200f);
                    if (!_hitDone && stateTime >= _attackHitAt)
                    {
                        _hitDone = true;
                        Say("hb_attack", 1f);
                        TryHitPlayer(profile.attackRange * 1.15f, 110f, profile.attackDamage, DamageType.Melee);
                    }
                    if (stateTime > _stateDur) Enter(S.Recover);
                    break;
                case S.Recover:
                    if (stateTime > _stateDur) Enter(SawPlayerRecently(3f) ? S.Chase : S.Search);
                    break;
                case S.Stagger:
                    if (stateTime > _stateDur) Enter(Health < profile.maxHealth * 0.3f ? S.Retreat : S.Chase);
                    break;
                case S.Retreat:
                    animator?.SyncSpeed("run", CurrentSpeed);
                    if (stateTime > _stateDur || Arrived(1f))
                    {
                        Health = Mathf.Min(profile.maxHealth, Health + profile.maxHealth * 0.5f);
                        Awareness = 30f;
                        Enter(S.Idle);
                    }
                    break;
                case S.Unreachable:
                    // stands below the player, looking up, listening. Terrifying, but it cannot climb.
                    FaceTowards(PlayerFeet, 90f);
                    if (Reachable(PlayerFeet) && SawPlayerRecently(1f)) { Enter(S.Chase); break; }
                    if (stateTime > _stateDur) Enter(S.Search);
                    break;
            }
        }

        void DoSearch()
        {
            animator?.SyncSpeed("walk", CurrentSpeed);
            if (WantsChase()) { Enter(S.Chase); return; }
            if (SawPlayerRecently(0.3f) && DistToPlayer < 3f) { Enter(AttackReady ? S.Attack : S.Chase); return; }
            if (stateTime > _stateDur || _searchIndex >= _searchPoints.Count)
            {
                Awareness *= 0.5f;
                Enter(S.Wander);
                return;
            }
            var p = _searchPoints[_searchIndex];
            if ((transform.position - p).sqrMagnitude > 1.6f * 1.6f) { MoveTo(p, profile.walkSpeed * 1.2f); animator?.Play("walk", 0.3f); }
            else
            {
                // peer around the cover
                Stop();
                animator?.Play("inspect", 0.3f);
                _searchDwell += Time.deltaTime;
                if (Player && Vector3.Distance(p, PlayerFeet) < 2.4f && !Physics.Linecast(EyePosition, PlayerHead, Layers.Occluders))
                {
                    LastKnownPlayerPos = PlayerFeet; LastSeenTime = Time.time;
                    Stimulus(60f);
                    Enter(S.Chase);
                    return;
                }
                if (_searchDwell > searchPointDuration) { _searchDwell = 0f; _searchIndex++; }
            }
        }
        float _searchDwell;

        void BuildSearchPoints(Vector3 centre)
        {
            _searchPoints.Clear();
            _searchDwell = 0f;
            // the exact spot first, then nearby places someone could hide (next to obstacles)
            if (SampleNav(centre, 3f, out var c)) _searchPoints.Add(c);
            for (int i = 0; i < 14 && _searchPoints.Count < 4; i++)
            {
                if (!RandomNavPoint(centre, 7f, out var p)) continue;
                if (Physics.CheckSphere(p + Vector3.up, 1.4f, Layers.Occluders | (1 << Layers.Foliage), QueryTriggerInteraction.Collide))
                    _searchPoints.Add(p);
            }
        }

        bool PickWanderTarget(out Vector3 p)
        {
            p = transform.position;
            if (interestPoints.Count > 0)
            {
                for (int i = 0; i < 5; i++)
                {
                    var t = interestPoints[Random.Range(0, interestPoints.Count)];
                    if (t && Vector3.Distance(t.position, home) < territoryRadius && SampleNav(t.position, 4f, out p)) return true;
                }
            }
            return RandomNavPoint(home, territoryRadius * 0.6f, out p);
        }

        void MaybeScrape(float dt)
        {
            _scrapeTimer -= dt;
            if (_scrapeTimer > 0f) return;
            _scrapeTimer = Random.Range(8f, 20f);
            // nails dragged down a nearby trunk
            if (Physics.SphereCast(transform.position + Vector3.up * 1.2f, 0.3f, transform.forward, out var hit, 2.5f, Layers.Occluders))
                SoundAt("hb_scrape", hit.point, 1f);
            else if (Random.value < 0.3f) Say("hb_listen_click", 0.4f);
        }

        void Footsteps(float dt)
        {
            float sp = CurrentSpeed;
            if (sp < 0.2f || _s == S.Chase) return; // chase uses slap events
            _stepTimer -= dt;
            if (_stepTimer <= 0f)
            {
                _stepTimer = Mathf.Clamp(1.1f / sp, 0.35f, 1.6f);
                SoundAt("hb_step", transform.position, 0.7f);
            }
        }

        void OnAnimEvent(string e)
        {
            if (e == "slap" && _s == S.Chase)
            {
                SoundAt("hb_slap", transform.position + transform.forward * 0.8f, 1f);
                NoiseSystem.Emit(transform.position, 0.3f, NoiseKind.Movement, false, this);
            }
        }

        float _slapTimer;
        protected override void Update()
        {
            base.Update();
            // fallback slap rhythm when the run clip has no events
            if (_s == S.Chase && animator && animator.Info("run") != null && animator.Info("run").events.Count == 0)
            {
                _slapTimer -= Time.deltaTime;
                if (_slapTimer <= 0f) { _slapTimer = 0.26f; OnAnimEvent("slap"); }
            }
        }

        protected override void OnDamaged(DamageInfo info, float amount, bool stagger)
        {
            _anger = 8f;
            if (stagger && _s != S.Stagger) { Enter(S.Stagger); return; }
            if (_s == S.Idle || _s == S.Wander || _s == S.Listen || _s == S.Search || _s == S.Investigate || _s == S.Follow) Enter(S.Chase);
        }
    }
}
