using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.World
{
    /// <summary>
    /// Paces small unexplained events per area so the world feels watched: phantom footsteps behind you,
    /// a stone falling, a cart that moves a little, scratching behind a metal plate, a dead lamp that
    /// buzzes on, a PA recording that cuts off mid-sentence, a silhouette that vanishes when looked at.
    /// Many events have no follow-up and sometimes nothing happens at all — uncertainty is the point.
    /// Events become more frequent deeper down and never stack on top of a real creature encounter.
    /// </summary>
    public class HorrorEventDirector : MonoBehaviour, IExpeditionReset
    {
        [System.Serializable]
        public class EventDef
        {
            public HorrorEventType type;
            public float weight = 1f;
            public AreaId[] areas = new AreaId[0];
            public int minDepth;
            public float cooldown = 120f;
            [HideInInspector] public float lastTime = -9999f;
        }

        public List<EventDef> events = new List<EventDef>();
        public Vector2 interval = new Vector2(30f, 70f);
        [Range(0, 1)] public float nothingChance = 0.3f;
        [Tooltip("Interval multiplier per mine level (deeper = more often).")]
        public float depthIntervalFactor = 0.82f;
        public AmbienceController ambience;
        public bool debugLog;

        float _timer;
        readonly List<EventDef> _eligible = new List<EventDef>();

        void OnEnable() => ExpeditionManager.Register(this);
        void OnDisable() => ExpeditionManager.Unregister(this);

        void Start() => _timer = Random.Range(interval.x, interval.y);

        public void OnNewExpedition(int index, System.Random rng)
        {
            foreach (var a in HorrorAnchor.All)
            {
                a.usedThisExpedition = false;
                foreach (var r in a.reveal) if (r) r.SetActive(false);
                if (a.type == HorrorEventType.PeripheralSilhouette && a.target) a.target.SetActive(false);
            }
        }

        void Update()
        {
            var area = AreaManager.Instance;
            var rig = PlayerRig.Instance;
            if (!area || !rig) return;
            _timer -= Time.deltaTime;
            if (_timer > 0f) return;
            float mult = Mathf.Pow(depthIntervalFactor, area.DepthLevel);
            _timer = Random.Range(interval.x, interval.y) * mult;
            // a real threat is already happening: do not dilute it
            if (ThreatMonitor.Level > 0.5f) return;
            if (Random.value < nothingChance) { if (debugLog) Debug.Log("[Horror] nothing (on purpose)"); return; }

            _eligible.Clear();
            float total = 0f;
            foreach (var e in events)
            {
                if (Time.time - e.lastTime < e.cooldown || area.DepthLevel < e.minDepth) continue;
                bool areaOk = e.areas.Length == 0;
                foreach (var a in e.areas) if (a == area.Current) { areaOk = true; break; }
                if (!areaOk) continue;
                _eligible.Add(e); total += e.weight;
            }
            if (total <= 0f) return;
            float r = Random.value * total;
            foreach (var e in _eligible)
            {
                r -= e.weight;
                if (r > 0f) continue;
                if (Execute(e.type, rig)) { e.lastTime = Time.time; if (debugLog) Debug.Log("[Horror] " + e.type); }
                break;
            }
        }

        // ------------------------------------------------------------------ helpers
        static AudioManager A => AudioManager.Instance;

        HorrorAnchor FindAnchor(HorrorEventType t, PlayerRig rig)
        {
            HorrorAnchor best = null; float bestScore = float.MinValue;
            foreach (var a in HorrorAnchor.All)
            {
                if (a.type != t || (a.oncePerExpedition && a.usedThisExpedition)) continue;
                float d = Vector3.Distance(a.transform.position, rig.HeadPosition);
                if (d < a.minDistance || d > a.maxDistance) continue;
                if (a.requireUnseen && Vector3.Angle(rig.HeadForward, a.transform.position - rig.HeadPosition) < 60f) continue;
                float score = Random.value - d * 0.01f;
                if (score > bestScore) { bestScore = score; best = a; }
            }
            if (best) best.usedThisExpedition = true;
            return best;
        }

        /// <summary>A point behind the player along open space (not inside rock).</summary>
        static Vector3 BehindPlayer(PlayerRig rig, float min, float max)
        {
            var back = -rig.HeadForward; back.y = 0f;
            back = Quaternion.Euler(0f, Random.Range(-50f, 50f), 0f) * back.normalized;
            float d = Random.Range(min, max);
            if (Physics.Raycast(rig.HeadPosition, back, out var hit, d, Layers.Occluders)) d = Mathf.Max(1.5f, hit.distance - 0.8f);
            return rig.HeadPosition + back * d;
        }

        static Vector3 AroundPlayer(PlayerRig rig, float dist)
        {
            var dir = Quaternion.Euler(0f, Random.Range(0f, 360f), 0f) * Vector3.forward;
            return rig.HeadPosition + dir * dist;
        }

        bool Execute(HorrorEventType t, PlayerRig rig)
        {
            HorrorAnchor a;
            switch (t)
            {
                case HorrorEventType.PhantomFootsteps:
                    a = FindAnchor(t, rig);
                    A?.PlayAt("footsteps_echo", a ? a.transform.position : BehindPlayer(rig, 10f, 20f), 0.8f);
                    return true;
                case HorrorEventType.RockFall:
                {
                    var p = BehindPlayer(rig, 5f, 12f);
                    if (Physics.Raycast(p, Vector3.up, out var hit, 10f, Layers.Occluders)) p = hit.point - Vector3.up * 0.2f;
                    A?.PlayAt("rock_fall_small", p, 1f);
                    FXManager.Burst("dust_fall", p, Vector3.down, new Color(0.5f, 0.47f, 0.43f, 0.5f), 14);
                    FXManager.Burst("debris", p, Vector3.down, new Color(0.3f, 0.28f, 0.26f), 6);
                    return true;
                }
                case HorrorEventType.MinecartNudge:
                    a = FindAnchor(t, rig);
                    if (!a || !a.target) return false;
                    var cart = a.target.GetComponent<MinecartEvent>();
                    if (!cart) return false;
                    cart.Nudge();
                    return true;
                case HorrorEventType.WallScratch:
                    a = FindAnchor(t, rig);
                    if (!a) return false;
                    A?.PlayAt("scratch_metal", a.transform.position - a.transform.forward * 0.3f, 1f);
                    StartCoroutine(RevealLater(a, 2.2f));
                    return true;
                case HorrorEventType.LightTurnsOn:
                    a = FindAnchor(t, rig);
                    if (!a || !a.lightTarget) return false;
                    StartCoroutine(LightOn(a));
                    return true;
                case HorrorEventType.DeadRoomHum:
                    a = FindAnchor(t, rig);
                    if (!a) return false;
                    StartCoroutine(Hum(a.transform, Random.Range(8f, 14f)));
                    return true;
                case HorrorEventType.MetalRepeat:
                    A?.PlayAt("metal_impact_repeat", rig.HeadPosition + Vector3.down * 25f + Random.insideUnitSphere * 15f, 1f);
                    return true;
                case HorrorEventType.PARecording:
                    a = FindAnchor(t, rig);
                    if (!a) return false;
                    A?.PlayAt("warning_recording", a.transform.position, 1f);
                    return true;
                case HorrorEventType.PeripheralSilhouette:
                    a = FindSilhouetteAnchor(rig);
                    if (!a) return false;
                    StartCoroutine(Silhouette(a, rig));
                    return true;
                case HorrorEventType.DistantCallStops:
                    A?.PlayAt("distant_call", AroundPlayer(rig, 45f) + Vector3.up * 5f, 1f);
                    if (ambience) ambience.DuckLife(Random.Range(10f, 18f));
                    return true;
                case HorrorEventType.BranchSnap:
                    A?.PlayAt("branch_snap", BehindPlayer(rig, 12f, 25f), 1f);
                    return true;
                case HorrorEventType.TreeCreak:
                    A?.PlayAt("tree_creak", AroundPlayer(rig, 18f) + Vector3.up * 6f, 0.9f);
                    return true;
                case HorrorEventType.FoliageCircling:
                    StartCoroutine(Circle(rig));
                    return true;
                case HorrorEventType.Crow:
                    A?.PlayAt("crow_caw", AroundPlayer(rig, 30f) + Vector3.up * 12f, 0.8f);
                    return true;
                case HorrorEventType.BunkerImpact:
                    A?.PlayAt("distant_impact", rig.HeadPosition + Vector3.up * 12f + Random.insideUnitSphere * 10f, 1f);
                    Bunker.FlickerLight.BurstAll(0.6f);
                    return true;
                case HorrorEventType.BunkerCreak:
                    A?.PlayAt("structural_creak", AroundPlayer(rig, 8f) + Vector3.up * 2f, 0.9f);
                    return true;
                case HorrorEventType.RadioInterference:
                    a = FindAnchor(t, rig);
                    A?.PlayAt("radio_burst", a ? a.transform.position : AroundPlayer(rig, 5f), 1f);
                    return true;
                case HorrorEventType.PipeKnock:
                    a = FindAnchor(t, rig);
                    A?.PlayAt("pipe_knock", a ? a.transform.position : rig.HeadPosition + Vector3.up * 2.5f, 1f);
                    return true;
                case HorrorEventType.LightFlicker:
                    Bunker.FlickerLight.BurstAll(2f);
                    return true;
                case HorrorEventType.PowerDip:
                    Bunker.BunkerPower.Instance?.Dip(Random.Range(5f, 9f));
                    return Bunker.BunkerPower.Instance;
                case HorrorEventType.Whisper:
                    A?.PlayAt("whisper_air", BehindPlayer(rig, 2f, 4f), 0.6f);
                    return true;
            }
            return false;
        }

        HorrorAnchor FindSilhouetteAnchor(PlayerRig rig)
        {
            foreach (var a in HorrorAnchor.All)
            {
                if (a.type != HorrorEventType.PeripheralSilhouette || !a.target || a.usedThisExpedition) continue;
                var to = a.transform.position + Vector3.up * 1.5f - rig.HeadPosition;
                float d = to.magnitude, ang = Vector3.Angle(rig.HeadForward, to);
                if (d < 14f || d > 38f || ang < 35f || ang > 85f) continue; // in the corner of the eye
                if (Physics.Linecast(rig.HeadPosition, a.transform.position + Vector3.up * 1.5f, Layers.Occluders)) continue;
                a.usedThisExpedition = true;
                return a;
            }
            return null;
        }

        IEnumerator Silhouette(HorrorAnchor a, PlayerRig rig)
        {
            a.target.SetActive(true);
            float t = 0f;
            while (t < 4f)
            {
                t += Time.deltaTime;
                // it is gone the moment you look straight at it
                if (Vector3.Angle(rig.HeadForward, a.transform.position + Vector3.up * 1.5f - rig.HeadPosition) < 18f)
                {
                    A?.PlayAt("whisper_air", a.transform.position, 0.4f);
                    break;
                }
                yield return null;
            }
            a.target.SetActive(false);
        }

        IEnumerator RevealLater(HorrorAnchor a, float delay)
        {
            yield return new WaitForSeconds(delay);
            foreach (var r in a.reveal) if (r) r.SetActive(true);
        }

        IEnumerator LightOn(HorrorAnchor a)
        {
            var l = a.lightTarget;
            A?.PlayAt("light_buzz_on", l.transform.position, 1f);
            l.enabled = true;
            float t = 0f, dur = Random.Range(6f, 11f), baseI = Mathf.Max(0.5f, l.intensity);
            while (t < dur) { t += Time.deltaTime; l.intensity = baseI * (Random.value < 0.08f ? 0.2f : 1f); yield return null; }
            l.enabled = false;
        }

        IEnumerator Hum(Transform at, float seconds)
        {
            var loop = A ? A.CreateLoop("machinery_hum_loop", at) : null;
            if (!loop) yield break;
            loop.FadeIn(0.5f);
            yield return new WaitForSeconds(seconds);
            loop.FadeOut(0.3f);
            yield return new WaitForSeconds(4f);
            Destroy(loop.gameObject);
        }

        IEnumerator Circle(PlayerRig rig)
        {
            // something heavy steps through the undergrowth, moving around you — and nothing comes
            float ang = Random.Range(0f, 360f), dir = Random.value < 0.5f ? -1f : 1f;
            for (int i = 0; i < 4; i++)
            {
                var p = rig.HeadPosition + Quaternion.Euler(0f, ang, 0f) * Vector3.forward * 14f;
                A?.PlayAt("footsteps_foliage", p, 0.9f);
                ang += 35f * dir;
                yield return new WaitForSeconds(Random.Range(1.5f, 3f));
            }
        }
    }
}
