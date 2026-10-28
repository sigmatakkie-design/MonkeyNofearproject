using System;
using System.Collections.Generic;
using UnityEngine;

namespace MonkeyNoFear.Audio
{
    [Serializable]
    public class SoundGroup
    {
        public string name;
        public AudioClip[] clips = new AudioClip[0];
        [Range(0, 2)] public float volume = 1f;
        public float pitchMin = 0.95f;
        public float pitchMax = 1.05f;
        [Tooltip("3D: distance at which attenuation starts.")]
        public float minDistance = 1f;
        public float maxDistance = 25f;
        [Range(0, 1)] public float spatialBlend = 1f;
        public bool loop;
        [Tooltip("Muffle through walls (low-pass + volume) for 3D sounds.")]
        public bool occlusion = true;
        [Range(0, 256)] public int priority = 128;
        [Tooltip("Minimum seconds between two plays of this group (prevents stacking).")]
        public float cooldown = 0.03f;

        [NonSerialized] public float lastPlayTime = -999f;
        [NonSerialized] int _lastIndex = -1;

        public AudioClip Pick()
        {
            if (clips == null || clips.Length == 0) return null;
            if (clips.Length == 1) return clips[0];
            // avoid immediate repeats: repetition kills immersion fast
            int i = UnityEngine.Random.Range(0, clips.Length - 1);
            if (i >= _lastIndex) i++;
            if (i >= clips.Length) i = 0;
            _lastIndex = i;
            return clips[i];
        }
    }

    [CreateAssetMenu(menuName = "Monkey No Fear/Sound Bank", fileName = "SoundBank")]
    public class SoundBank : ScriptableObject
    {
        public List<SoundGroup> groups = new List<SoundGroup>();
        Dictionary<string, SoundGroup> _map;

        public SoundGroup Get(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            if (_map == null)
            {
                _map = new Dictionary<string, SoundGroup>(StringComparer.Ordinal);
                foreach (var g in groups) if (g != null && !string.IsNullOrEmpty(g.name)) _map[g.name] = g;
            }
            return _map.TryGetValue(name, out var grp) ? grp : null;
        }

        void OnValidate() { _map = null; }
    }
}
