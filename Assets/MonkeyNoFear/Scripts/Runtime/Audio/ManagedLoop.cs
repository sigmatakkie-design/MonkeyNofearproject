using UnityEngine;

namespace MonkeyNoFear.Audio
{
    /// <summary>A looping 3D sound with fade in/out and smoothed occlusion.</summary>
    public class ManagedLoop : MonoBehaviour
    {
        AudioManager _mgr;
        SoundGroup _group;
        AudioSource _src;
        AudioLowPassFilter _lpf;
        float _volume, _current, _target;
        float _occl;
        internal float targetOcclusion;
        public float fadeSpeed = 1.5f;

        public bool IsPlaying => _src && _src.isPlaying;
        public bool Occlude => _group != null && _group.occlusion && _group.spatialBlend > 0.5f;
        public AudioSource Source => _src;

        internal void Init(AudioManager mgr, SoundGroup g, AudioSource src, AudioLowPassFilter lpf, float volume)
        {
            _mgr = mgr; _group = g; _src = src; _lpf = lpf; _volume = volume;
            if (g != null)
            {
                src.clip = g.Pick();
                src.spatialBlend = g.spatialBlend;
                src.spatialize = mgr.useSpatializerPlugin && g.spatialBlend > 0.5f;
                src.minDistance = g.minDistance;
                src.maxDistance = g.maxDistance;
                src.priority = g.priority;
                src.pitch = (g.pitchMin + g.pitchMax) * 0.5f;
            }
        }

        public void SetVolume(float v) => _volume = v;
        public void SetPitch(float p) { if (_src) _src.pitch = p; }

        public void FadeIn(float speed = 1.5f)
        {
            fadeSpeed = speed;
            _target = 1f;
            if (_src && _src.clip && !_src.isPlaying)
            {
                _src.time = Random.Range(0f, _src.clip.length * 0.9f); // desync identical loops
                _src.Play();
            }
        }

        public void FadeOut(float speed = 1.5f) { fadeSpeed = speed; _target = 0f; }

        public void StopImmediate() { _target = 0f; _current = 0f; if (_src) _src.Stop(); }

        void Update()
        {
            if (!_src) return;
            _current = Mathf.MoveTowards(_current, _target, fadeSpeed * Time.deltaTime);
            if (_current <= 0f && _target <= 0f && _src.isPlaying) _src.Stop();
            _occl = Mathf.Lerp(_occl, targetOcclusion, Time.deltaTime * 4f);
            float gv = _group != null ? _group.volume : 1f;
            float cat = _mgr ? (_group != null && _group.spatialBlend < 0.5f ? _mgr.ambienceVolume : _mgr.sfxVolume) : 1f;
            float ov = _mgr ? Mathf.Lerp(1f, _mgr.OccludedVolume, _occl) : 1f;
            _src.volume = _current * _volume * gv * cat * ov;
            if (_lpf) _lpf.cutoffFrequency = _mgr ? Mathf.Lerp(22000f, _mgr.OccludedCutoff, _occl) : 22000f;
        }

        void OnDestroy() { if (_mgr) _mgr.Unregister(this); }
    }
}
