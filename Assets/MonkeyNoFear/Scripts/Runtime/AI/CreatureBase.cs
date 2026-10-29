using UnityEngine;
using UnityEngine.AI;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.AI
{
    /// <summary>
    /// Shared foundation for every monster: senses (hearing via the NoiseSystem, line-of-sight vision limited
    /// by FOV, fog and the player's visibility), last-known-position memory (never omniscient), NavMesh
    /// movement helpers, telegraphed attacks with cooldowns and post-hit recovery, damage handling,
    /// activation culling, threat reporting for the ambience, bestiary discovery and debug gizmos.
    /// Each creature implements its own behaviour in Think().
    /// </summary>
    public abstract class CreatureBase : MonoBehaviour, IDamageable, INoiseListener
    {
        [Header("Common")]
        public CreatureProfile profile;
        public CreatureAnimator animator;
        public NavMeshAgent agent;
        [Tooltip("Eye/ear point. Defaults to the head bone or a point 1.5 m up.")]
        public Transform eyes;
        public string voiceLoop;
        [Tooltip("Show state, senses and path in the Scene view.")]
        public bool debugGizmos = true;

        public float Health { get; protected set; }
        public virtual bool IsAlive => Health > 0f;
        public string StateName { get; protected set; } = "Init";
        public float Awareness { get; protected set; }
        public Vector3 LastKnownPlayerPos { get; protected set; }
        public float LastSeenTime { get; protected set; } = -999f;
        public float LastHeardTime { get; protected set; } = -999f;
        public bool Active { get; private set; } = true;

        protected float stateTime;
        protected ManagedLoop voice;
        protected Vector3 home;
        protected float recentDamage, recentDamageTime;
        float _visionTimer, _discoverTimer, _attackReadyAt, _navBindTimer;
        float _lastStimulus;

        protected PlayerRig Player => PlayerRig.Instance;
        protected Vector3 PlayerHead => Player ? Player.HeadPosition : transform.position;
        protected Vector3 PlayerFeet => Player ? Player.transform.position + Vector3.ProjectOnPlane(Player.HeadPosition - Player.transform.position, Vector3.up) : transform.position;
        protected float DistToPlayer => Player ? Vector3.Distance(transform.position, PlayerFeet) : 999f;
        public Vector3 EyePosition => eyes ? eyes.position : transform.position + Vector3.up * 1.5f;
        public string Id => profile ? profile.id : name;

        // -------------------------------------------------------------------- INoiseListener
        public Vector3 HearingPosition => EyePosition;
        public float HearingSensitivity => profile ? profile.hearingSensitivity : 1f;
        public bool ListeningEnabled => Active && IsAlive && isActiveAndEnabled;
        public virtual void OnNoiseHeard(in NoiseEvent e, float perceived) { }

        protected virtual void Awake()
        {
            Health = profile ? profile.maxHealth : 100f;
            if (!agent) agent = GetComponent<NavMeshAgent>();
            if (!animator) animator = GetComponentInChildren<CreatureAnimator>();
            if (!eyes && animator && animator.Head) eyes = animator.Head;
            if (agent && profile)
            {
                agent.speed = profile.walkSpeed;
                agent.angularSpeed = profile.turnSpeed;
                agent.acceleration = profile.acceleration;
                agent.autoBraking = true;
            }
            home = transform.position;
        }

        protected virtual void OnEnable()
        {
            NoiseSystem.Register(this);
            if (!voice && !string.IsNullOrEmpty(voiceLoop) && AudioManager.Instance)
                voice = AudioManager.Instance.CreateLoop(voiceLoop, eyes ? eyes : transform);
        }

        protected virtual void OnDisable() { NoiseSystem.Unregister(this); }

        protected virtual void Update()
        {
            float dist = DistToPlayer;
            bool shouldBeActive = Player && dist < (profile ? profile.activationDistance : 100f);
            if (shouldBeActive != Active)
            {
                Active = shouldBeActive;
                if (agent && agent.isOnNavMesh) agent.isStopped = !Active;
                if (animator && animator.anim) animator.anim.enabled = Active;
                if (voice) { if (Active) voice.FadeIn(); else voice.FadeOut(); }
            }
            if (!Active) return;
            BindToNavMesh();
            stateTime += Time.deltaTime;
            if (Time.time - recentDamageTime > 2f) recentDamage = 0f;

            _visionTimer -= Time.deltaTime;
            if (_visionTimer <= 0f)
            {
                _visionTimer = 0.15f;
                if (CanSeePlayer(out float q)) OnSeePlayer(q);
            }
            if (Time.time - _lastStimulus > 2f && profile)
                Awareness = Mathf.Max(0f, Awareness - profile.awarenessDecay * Time.deltaTime);

            Think(Time.deltaTime);
            ThreatMonitor.Report(ThreatLevel(dist), IsChasing);
            CheckDiscovery(dist);
        }

        protected abstract void Think(float dt);
        protected virtual float ThreatLevel(float distance) => 0f;
        protected virtual bool IsChasing => false;
        protected virtual void OnSeePlayer(float quality) { }

        protected void Stimulus(float amount)
        {
            Awareness = Mathf.Clamp(Awareness + amount, 0f, 120f);
            _lastStimulus = Time.time;
        }

        protected void SetState(string s)
        {
            if (StateName == s) return;
            StateName = s;
            stateTime = 0f;
        }

        // -------------------------------------------------------------------- vision
        /// <summary>
        /// Line-of-sight check against the player's head and chest. Range shrinks with fog (the creature
        /// sees silhouettes no further than the player does) and with the player's visibility (still,
        /// crouched, lights off). Bushes (Foliage triggers) on the line reduce quality.
        /// </summary>
        public bool CanSeePlayer(out float quality)
        {
            quality = 0f;
            if (!Player || !profile) return false;
            Vector3 eye = EyePosition;
            Vector3 head = PlayerHead;
            Vector3 to = head - eye;
            float d = to.magnitude;
            var stealth = PlayerStealth.Instance;
            float vis = stealth ? stealth.Visibility : 1f;
            float fogVis = AreaManager.Instance ? AreaManager.Instance.FogVisibility * 1.15f : 500f;
            float range = Mathf.Min(profile.sightRange, fogVis) * Mathf.Lerp(0.35f, 1f, vis);
            // a lit flashlight pointing anywhere near the creature is visible from much further away
            if (stealth && stealth.OwnLightOn) range = Mathf.Max(range, Mathf.Min(profile.sightRange * 1.4f, fogVis * 1.6f));
            if (d > range) return false;
            Vector3 fwd = eyes ? transform.forward : transform.forward;
            bool inFov = Vector3.Angle(fwd, to) <= profile.sightFov * 0.5f;
            if (!inFov && d > profile.proximitySense) return false;
            bool losHead = !Physics.Linecast(eye, head, Layers.Occluders, QueryTriggerInteraction.Ignore);
            bool losChest = !Physics.Linecast(eye, head + Vector3.down * 0.5f, Layers.Occluders, QueryTriggerInteraction.Ignore);
            if (!losHead && !losChest) return false;
            quality = (losHead && losChest ? 1f : 0.55f) * (1f - d / range * 0.6f) * vis;
            // soft cover
            int bushes = Physics.RaycastNonAlloc(eye, to / d, _foliageHits, d, 1 << Layers.Foliage, QueryTriggerInteraction.Collide);
            for (int i = 0; i < bushes; i++) quality *= 0.4f;
            if (quality < 0.05f) return false;
            LastKnownPlayerPos = PlayerFeet;
            LastSeenTime = Time.time;
            return true;
        }
        static readonly RaycastHit[] _foliageHits = new RaycastHit[6];

        protected bool HeardPlayerRecently(float seconds) => Time.time - LastHeardTime < seconds;
        protected bool SawPlayerRecently(float seconds) => Time.time - LastSeenTime < seconds;

        // -------------------------------------------------------------------- movement
        protected bool HasAgent => agent && agent.enabled && agent.isOnNavMesh;

        /// <summary>An enabled agent that is not on the NavMesh never moves (spawned before the runtime NavMesh
        /// data was added, or placed slightly off it). Re-seat it on the nearest NavMesh point; Warp only ever
        /// targets a validated NavMesh position.</summary>
        void BindToNavMesh()
        {
            if (!agent || !agent.enabled || agent.isOnNavMesh) return;
            _navBindTimer -= Time.deltaTime;
            if (_navBindTimer > 0f) return;
            _navBindTimer = 1f;
            if (SampleNav(transform.position, 2f, out var p)) agent.Warp(p);
        }

        protected void MoveTo(Vector3 p, float speed)
        {
            if (!HasAgent) return;
            agent.isStopped = false;
            agent.speed = speed;
            // do not restart a path request that is still being computed (re-issuing it every frame for a moving
            // or off-mesh target could keep a long path from ever finishing)
            if (agent.pathPending) return;
            // targets are often off the mesh (a noise on a wall, a deposit, a player on a ledge): aim for the
            // walkable point below/beside it, which also keeps the comparison below stable
            SampleNav(p, 2.5f, out p);
            if (!agent.hasPath || (agent.destination - p).sqrMagnitude > 0.25f) agent.SetDestination(p);
        }

        protected void Stop()
        {
            if (!HasAgent) return;
            agent.isStopped = true;
            agent.velocity = Vector3.zero;
            agent.ResetPath();
        }

        protected bool Arrived(float tolerance = 0.8f)
        {
            if (!HasAgent) return true;
            if (agent.pathPending) return false;
            if (!agent.hasPath) return true; // no path (failed or cleared): nothing left to walk, let the state move on
            return agent.remainingDistance <= Mathf.Max(tolerance, agent.stoppingDistance);
        }

        protected float CurrentSpeed => HasAgent ? agent.velocity.magnitude : 0f;

        protected void FaceTowards(Vector3 p, float degPerSec)
        {
            var d = p - transform.position; d.y = 0f;
            if (d.sqrMagnitude < 0.0001f) return;
            transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(d), degPerSec * Time.deltaTime);
        }

        protected bool SampleNav(Vector3 p, float radius, out Vector3 result)
        {
            if (NavMesh.SamplePosition(p, out var hit, radius, NavMesh.AllAreas)) { result = hit.position; return true; }
            result = p; return false;
        }

        protected bool RandomNavPoint(Vector3 centre, float radius, out Vector3 result)
        {
            for (int i = 0; i < 8; i++)
            {
                var r = Random.insideUnitSphere * radius; r.y = 0f;
                if (SampleNav(centre + r, 3f, out result)) return true;
            }
            result = centre;
            return false;
        }

        static NavMeshPath _path;
        /// <summary>True if the agent can walk all the way to p (the player may have climbed out of reach).</summary>
        protected bool Reachable(Vector3 p)
        {
            if (!HasAgent) return false;
            _path ??= new NavMeshPath();
            if (!SampleNav(p, 1.5f, out var q)) return false;
            return agent.CalculatePath(q, _path) && _path.status == NavMeshPathStatus.PathComplete;
        }

        // -------------------------------------------------------------------- attacks
        protected bool AttackReady => Time.time >= _attackReadyAt;

        /// <summary>Hit check at the moment the swing lands: range and frontal arc. Returns true on hit.</summary>
        protected bool TryHitPlayer(float range, float arcDegrees, float damage, DamageType type)
        {
            _attackReadyAt = Time.time + (profile ? profile.attackCooldown : 3f);
            if (!Player || PlayerHealth.Instance == null || PlayerHealth.Instance.IsDead) return false;
            var to = PlayerFeet - transform.position; to.y = 0f;
            if (to.magnitude > range) return false;
            if (Vector3.Angle(transform.forward, to) > arcDegrees * 0.5f) return false;
            if (Physics.Linecast(EyePosition, PlayerHead, Layers.Occluders, QueryTriggerInteraction.Ignore)) return false;
            return PlayerHealth.Instance.TakeDamage(new DamageInfo(damage, transform.position, type, this));
        }

        // -------------------------------------------------------------------- damage
        public virtual bool TakeDamage(DamageInfo info)
        {
            if (!IsAlive) return false;
            float dmg = info.amount * (profile ? profile.weaponVulnerability : 1f);
            if (profile && profile.killable) Health -= dmg;
            else Health = Mathf.Max(1f, Health - dmg); // unkillable creatures retreat instead of dying
            recentDamage += dmg;
            recentDamageTime = Time.time;
            LastKnownPlayerPos = PlayerFeet;
            Stimulus(100f);
            OnDamaged(info, dmg, profile && recentDamage >= profile.staggerThreshold);
            if (profile && profile.killable && Health <= 0f) OnDeath(info);
            return true;
        }

        protected virtual void OnDamaged(DamageInfo info, float amount, bool stagger) { }
        protected virtual void OnDeath(DamageInfo info) { }

        // -------------------------------------------------------------------- sound helpers
        protected void Say(string sound, float volume = 1f) => AudioManager.Instance?.PlayAt(sound, EyePosition, volume, 1f, eyes);
        protected void SoundAt(string sound, Vector3 p, float volume = 1f) => AudioManager.Instance?.PlayAt(sound, p, volume);

        // -------------------------------------------------------------------- bestiary
        void CheckDiscovery(float dist)
        {
            _discoverTimer -= Time.deltaTime;
            if (_discoverTimer > 0f || !Player || dist > 30f) return;
            _discoverTimer = 0.5f;
            var gr = GameRoot.I;
            if (!gr || gr.Progress.IsDiscovered("creature_" + Id)) return;
            var cam = Player.HeadPosition;
            var to = EyePosition - cam;
            bool inView = Vector3.Angle(Player.HeadForward, to) < 30f;
            bool clear = !Physics.Linecast(cam, EyePosition, Layers.Occluders, QueryTriggerInteraction.Ignore);
            bool lit = to.magnitude < 12f || PlayerStealth.LightOn(EyePosition) != null;
            if (inView && clear && lit && gr.Progress.Discover("creature_" + Id))
                GameEvents.Toast("BESTIARY: " + (profile ? profile.displayName.ToUpperInvariant() : Id));
        }

        // -------------------------------------------------------------------- debug
        protected virtual void OnDrawGizmosSelected()
        {
            if (!debugGizmos || !profile) return;
            var eye = EyePosition;
            Gizmos.color = new Color(1f, 1f, 0f, 0.3f);
            float half = profile.sightFov * 0.5f;
            var l = Quaternion.Euler(0, -half, 0) * transform.forward * profile.sightRange;
            var r = Quaternion.Euler(0, half, 0) * transform.forward * profile.sightRange;
            Gizmos.DrawLine(eye, eye + l); Gizmos.DrawLine(eye, eye + r);
            Gizmos.color = new Color(0.3f, 0.6f, 1f, 0.25f);
            Gizmos.DrawWireSphere(eye, NoiseSystem.MetersPerLoudness * 0.5f * profile.hearingSensitivity);
            Gizmos.color = Color.red;
            Gizmos.DrawWireSphere(transform.position, profile.attackRange);
            Gizmos.color = Color.magenta;
            Gizmos.DrawWireCube(LastKnownPlayerPos + Vector3.up * 0.5f, Vector3.one * 0.5f);
            if (HasAgent && agent.hasPath)
            {
                Gizmos.color = Color.cyan;
                var c = agent.path.corners;
                for (int i = 1; i < c.Length; i++) Gizmos.DrawLine(c[i - 1], c[i]);
            }
        }

        protected virtual void OnDrawGizmos()
        {
#if UNITY_EDITOR
            if (debugGizmos && Application.isPlaying)
                UnityEditor.Handles.Label(transform.position + Vector3.up * 3f, $"{name}\n{StateName}  aw:{Awareness:0}");
#endif
        }
    }
}
