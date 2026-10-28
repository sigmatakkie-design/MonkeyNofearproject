using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.Audio
{
    /// <summary>Pooled spatial one-shots plus managed loops, with obstruction-aware muffling.
    /// All gameplay sounds go through here so occlusion and volume categories stay consistent.</summary>
    [DefaultExecutionOrder(-80)]
    public class AudioManager : MonoBehaviour
    {
        public static AudioManager Instance { get; private set; }

        public SoundBank bank;
        [Min(8)] public int poolSize = 40;
        [Range(0, 1)] public float sfxVolume = 1f;
        [Range(0, 1)] public float ambienceVolume = 0.85f;
        [Tooltip("Low-pass cutoff applied when a wall is between the sound and the listener.")]
        public float occludedCutoff = 1100f;
        [Range(0, 1)] public float occludedVolume = 0.55f;
        [Tooltip("Use the platform spatializer plugin (e.g. Oculus/Meta XR Audio) if one is selected in Project Settings.")]
        public bool useSpatializerPlugin = true;

        class Voice
        {
            public AudioSource src;
            public AudioLowPassFilter lpf;
            public Transform follow;
            public bool occlude;
            public float baseVolume;
            public float occl; // 0 clear .. 1 fully occluded (smoothed)
        }

        readonly List<Voice> _voices = new List<Voice>();
        readonly List<ManagedLoop> _loops = new List<ManagedLoop>();
        readonly HashSet<string> _warned = new HashSet<string>();
        int _occlusionCursor;
        Transform _listener;

        public Vector3 ListenerPosition => _listener ? _listener.position : Vector3.zero;

        void Awake()
        {
            if (Instance && Instance != this) { Debug.LogWarning("Duplicate AudioManager destroyed"); Destroy(this); return; }
            Instance = this;
            for (int i = 0; i < poolSize; i++)
            {
                var go = new GameObject("Voice_" + i);
                go.transform.SetParent(transform, false);
                var src = go.AddComponent<AudioSource>();
                src.playOnAwake = false;
                src.rolloffMode = AudioRolloffMode.Logarithmic;
                src.dopplerLevel = 0f;
                var lpf = go.AddComponent<AudioLowPassFilter>();
                lpf.cutoffFrequency = 22000f;
                _voices.Add(new Voice { src = src, lpf = lpf });
            }
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        public void SetListener(Transform t) => _listener = t;

        public SoundGroup GetGroup(string name)
        {
            var g = bank ? bank.Get(name) : null;
            if (g == null && _warned.Add(name ?? "<null>")) Debug.LogWarning($"[Audio] Missing sound group '{name}'");
            return g;
        }

        /// <summary>Plays a 3D one-shot at a world position. Returns the AudioSource (do not keep it).</summary>
        public AudioSource PlayAt(string name, Vector3 position, float volume = 1f, float pitch = 1f, Transform follow = null)
        {
            var g = GetGroup(name);
            if (g == null) return null;
            if (Time.time - g.lastPlayTime < g.cooldown) return null;
            var clip = g.Pick();
            if (!clip) return null;
            g.lastPlayTime = Time.time;

            var v = GetFreeVoice(g.priority);
            if (v == null) return null;
            var s = v.src;
            s.transform.position = position;
            s.clip = clip;
            s.loop = false;
            s.spatialBlend = g.spatialBlend;
            s.spatialize = useSpatializerPlugin && g.spatialBlend > 0.5f;
            s.minDistance = g.minDistance;
            s.maxDistance = g.maxDistance;
            s.priority = g.priority;
            s.pitch = Random.Range(g.pitchMin, g.pitchMax) * pitch;
            v.baseVolume = g.volume * volume * sfxVolume;
            v.follow = follow;
            v.occlude = g.occlusion && g.spatialBlend > 0.5f;
            v.occl = v.occlude ? ComputeOcclusion(position) : 0f;
            ApplyOcclusion(v);
            s.Play();
            return s;
        }

        public AudioSource Play2D(string name, float volume = 1f, float pitch = 1f)
        {
            var src = PlayAt(name, ListenerPosition, volume, pitch, _listener);
            if (src) src.spatialBlend = 0f;
            return src;
        }

        Voice GetFreeVoice(int priority)
        {
            Voice worst = null;
            foreach (var v in _voices)
            {
                if (!v.src.isPlaying) return v;
                if (worst == null || v.src.priority > worst.src.priority) worst = v;
            }
            // steal the least important voice only if the new one is at least as important
            return worst != null && worst.src.priority >= priority ? worst : null;
        }

        /// <summary>Creates a looping source owned by the caller (creature breathing, motors, ambience emitters).</summary>
        public ManagedLoop CreateLoop(string name, Transform parent, float volume = 1f)
        {
            var g = GetGroup(name);
            var go = new GameObject("Loop_" + name);
            go.transform.SetParent(parent ? parent : transform, false);
            var src = go.AddComponent<AudioSource>();
            src.playOnAwake = false;
            src.loop = true;
            src.dopplerLevel = 0f;
            src.rolloffMode = AudioRolloffMode.Logarithmic;
            var lpf = go.AddComponent<AudioLowPassFilter>();
            lpf.cutoffFrequency = 22000f;
            var loop = go.AddComponent<ManagedLoop>();
            loop.Init(this, g, src, lpf, volume);
            _loops.Add(loop);
            return loop;
        }

        internal void Unregister(ManagedLoop l) => _loops.Remove(l);

        void LateUpdate()
        {
            // follow targets
            foreach (var v in _voices)
                if (v.follow && v.src.isPlaying) v.src.transform.position = v.follow.position;

            // amortised occlusion: a few raycasts per frame
            int budget = 4;
            int total = _voices.Count + _loops.Count;
            for (int n = 0; n < budget && total > 0; n++)
            {
                _occlusionCursor = (_occlusionCursor + 1) % total;
                if (_occlusionCursor < _voices.Count)
                {
                    var v = _voices[_occlusionCursor];
                    if (v.src.isPlaying && v.occlude)
                        v.occl = Mathf.Lerp(v.occl, ComputeOcclusion(v.src.transform.position), 0.6f);
                }
                else
                {
                    var l = _loops[_occlusionCursor - _voices.Count];
                    if (l && l.IsPlaying && l.Occlude) l.targetOcclusion = ComputeOcclusion(l.transform.position);
                }
            }
            foreach (var v in _voices) if (v.src.isPlaying) ApplyOcclusion(v);
        }

        void ApplyOcclusion(Voice v)
        {
            v.src.volume = v.baseVolume * Mathf.Lerp(1f, occludedVolume, v.occl);
            v.lpf.cutoffFrequency = Mathf.Lerp(22000f, occludedCutoff, v.occl);
        }

        /// <summary>0 = clear line to listener, 1 = blocked. Uses two rays (direct + slightly raised) so
        /// thin props do not fully muffle sounds.</summary>
        public float ComputeOcclusion(Vector3 pos)
        {
            if (!_listener) return 0f;
            var l = _listener.position;
            float o = 0f;
            if (Physics.Linecast(pos, l, Layers.Occluders, QueryTriggerInteraction.Ignore)) o += 0.6f;
            if (Physics.Linecast(pos + Vector3.up * 0.6f, l + Vector3.up * 0.3f, Layers.Occluders, QueryTriggerInteraction.Ignore)) o += 0.4f;
            return o;
        }

        internal float OccludedCutoff => occludedCutoff;
        internal float OccludedVolume => occludedVolume;
    }

}
