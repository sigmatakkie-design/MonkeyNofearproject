using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Audio
{
    /// <summary>Creatures report how threatening they currently are; ambience and music react.</summary>
    public static class ThreatMonitor
    {
        static float _frameMax, _value, _chase;
        static int _frame = -1;

        /// <param name="threat">0..1: 0.3 = something is listening nearby, 0.6 = stalking, 1 = attacking</param>
        public static void Report(float threat, bool chasing = false)
        {
            if (Time.frameCount != _frame) { _frame = Time.frameCount; _frameMax = 0f; }
            _frameMax = Mathf.Max(_frameMax, threat);
            if (chasing) _chase = Time.time;
        }

        internal static void Tick(float dt)
        {
            float target = Time.frameCount - _frame <= 1 ? _frameMax : 0f;
            // rise fast, fall slow: silence lingers after the threat leaves
            _value = target > _value ? Mathf.MoveTowards(_value, target, dt * 2f) : Mathf.MoveTowards(_value, target, dt * 0.12f);
        }

        public static float Level => _value;
        public static bool RecentlyChased => Time.time - _chase < 4f;
    }

    /// <summary>Layered area ambience: beds crossfade on area change, "life" layers (insects, frogs, birds)
    /// fade to silence as the threat level rises, a tension drone plays during chases.</summary>
    public class AmbienceController : MonoBehaviour
    {
        public string tensionLoop = "tension_drone_loop";
        public string heartbeatLoop = "heartbeat_loop";
        public float crossfadeSpeed = 0.5f;

        readonly Dictionary<string, ManagedLoop> _loops = new Dictionary<string, ManagedLoop>();
        readonly HashSet<string> _activeBeds = new HashSet<string>();
        readonly HashSet<string> _activeLife = new HashSet<string>();
        ManagedLoop _tension, _heart;
        float _lifeDuckTimer;

        void OnEnable() => GameEvents.AreaChanged += OnArea;
        void OnDisable() => GameEvents.AreaChanged -= OnArea;

        /// <summary>Forest events call this when an animal call "stops without explanation".</summary>
        public void DuckLife(float seconds) => _lifeDuckTimer = Mathf.Max(_lifeDuckTimer, seconds);

        ManagedLoop Loop(string name)
        {
            if (!_loops.TryGetValue(name, out var l) || !l)
            {
                if (!AudioManager.Instance) return null;
                l = AudioManager.Instance.CreateLoop(name, transform);
                _loops[name] = l;
            }
            return l;
        }

        void OnArea(AreaId from, AreaId to)
        {
            var p = AreaManager.Instance ? AreaManager.Instance.GetProfile(to) : null;
            _activeBeds.Clear(); _activeLife.Clear();
            if (p)
            {
                foreach (var b in p.ambienceBeds) if (!string.IsNullOrEmpty(b)) _activeBeds.Add(b);
                foreach (var b in p.lifeLayers) if (!string.IsNullOrEmpty(b)) _activeLife.Add(b);
            }
            foreach (var kv in _loops)
            {
                if (!kv.Value || kv.Value == _tension || kv.Value == _heart) continue;
                if (!_activeBeds.Contains(kv.Key) && !_activeLife.Contains(kv.Key)) kv.Value.FadeOut(crossfadeSpeed);
            }
            foreach (var b in _activeBeds) Loop(b)?.FadeIn(crossfadeSpeed);
            foreach (var b in _activeLife) Loop(b)?.FadeIn(crossfadeSpeed);
        }

        void Update()
        {
            ThreatMonitor.Tick(Time.deltaTime);
            float threat = ThreatMonitor.Level;
            _lifeDuckTimer -= Time.deltaTime;

            // life layers: silent near threats or after a ducking event
            float life = Mathf.Clamp01(1f - threat * 1.6f);
            if (_lifeDuckTimer > 0f) life = 0f;
            foreach (var n in _activeLife)
            {
                var l = Loop(n);
                if (l) l.SetVolume(life);
            }
            // beds dip slightly so small sounds become noticeable
            foreach (var n in _activeBeds)
            {
                var l = Loop(n);
                if (l) l.SetVolume(Mathf.Lerp(1f, 0.55f, threat));
            }

            if (_tension == null) _tension = Loop(tensionLoop);
            if (_tension)
            {
                bool chase = ThreatMonitor.RecentlyChased;
                if (chase) _tension.FadeIn(0.6f); else _tension.FadeOut(0.25f);
            }

            if (_heart == null) _heart = Loop(heartbeatLoop);
            if (_heart)
            {
                var hp = Player.PlayerHealth.Instance;
                float danger = Mathf.Max(threat > 0.75f ? (threat - 0.75f) * 4f : 0f, hp ? Mathf.Clamp01((40f - hp.Current) / 30f) : 0f);
                if (danger > 0.05f) { _heart.FadeIn(1f); _heart.SetVolume(danger); _heart.SetPitch(1f + danger * 0.25f); }
                else _heart.FadeOut(0.5f);
            }
        }
    }
}
