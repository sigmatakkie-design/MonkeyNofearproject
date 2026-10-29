using System;
using System.Collections.Generic;
using UnityEngine;

namespace MonkeyNoFear.AI
{
    [Serializable]
    public class ClipEvent
    {
        public string name;
        public float time; // seconds into the clip
    }

    [Serializable]
    public class ClipInfo
    {
        public string name;
        public float length = 1f;
        public bool loop = true;
        [Tooltip("Ground speed the cycle was authored for (m/s), 0 for in-place clips.")]
        public float authoredSpeed;
        public List<ClipEvent> events = new List<ClipEvent>();
    }

    /// <summary>
    /// Plays the creature's legacy animation clips (imported from the FBX, data from the creature manifest)
    /// and layers procedural motion on top in LateUpdate: head look-at with limits, listening head tilt,
    /// jaw override, breathing. Raises clip events (hit frames, footfalls, slaps) as C# events. If clips are
    /// missing the creature still moves with a procedural bob so missing animation never breaks gameplay.
    /// </summary>
    public class CreatureAnimator : MonoBehaviour
    {
        public Animation anim;
        public List<ClipInfo> clips = new List<ClipInfo>();
        public string headBoneName = "head";
        public string jawBoneName = "jaw";
        public Transform visualRoot;
        public float maxLookYaw = 75f, maxLookPitch = 45f;

        public event Action<string> AnimEvent;

        public Transform Head { get; private set; }
        public Transform Jaw { get; private set; }
        public string Current { get; private set; }

        public Vector3? LookTarget { get; set; }
        public float LookWeight { get; set; }
        /// <summary>Degrees of head roll (listening tilt).</summary>
        public float HeadTilt { get; set; }
        /// <summary>Extra jaw opening in degrees (0 = animation only).</summary>
        public float JawOpen { get; set; }
        public Vector3 JawAxis = Vector3.right;

        readonly Dictionary<string, ClipInfo> _info = new Dictionary<string, ClipInfo>();
        Vector3 _headFwdLocal, _headUpLocal;
        float _lookW, _tilt, _prevTime;
        float _bob;
        Vector3 _visualRest;

        void Awake()
        {
            if (!anim) anim = GetComponentInChildren<Animation>();
            foreach (var c in clips) if (c != null && !string.IsNullOrEmpty(c.name)) _info[c.name] = c;
            if (anim)
            {
                foreach (AnimationState s in anim)
                {
                    var ci = Info(s.name);
                    s.wrapMode = ci == null || ci.loop ? WrapMode.Loop : WrapMode.ClampForever;
                }
                anim.cullingType = AnimationCullingType.BasedOnRenderers;
            }
            Head = FindBone(headBoneName);
            Jaw = FindBone(jawBoneName);
            if (Head)
            {
                _headFwdLocal = Head.InverseTransformDirection(transform.forward);
                _headUpLocal = Head.InverseTransformDirection(transform.up);
            }
            if (visualRoot) _visualRest = visualRoot.localPosition;
        }

        Transform FindBone(string n)
        {
            if (string.IsNullOrEmpty(n)) return null;
            foreach (var t in GetComponentsInChildren<Transform>(true)) if (t.name == n) return t;
            return null;
        }

        public ClipInfo Info(string clip) => clip != null && _info.TryGetValue(clip, out var c) ? c : null;
        public bool Has(string clip) => anim && anim[clip] != null;

        public float Length(string clip)
        {
            if (anim && anim[clip] != null) return anim[clip].length;
            var i = Info(clip);
            return i != null ? i.length : 1f;
        }

        /// <summary>Time (s) of a named event in a clip, or fallback fraction of its length.</summary>
        public float EventTime(string clip, string evt, float fallbackFraction)
        {
            var i = Info(clip);
            if (i != null) foreach (var e in i.events) if (e.name == evt) return e.time;
            return Length(clip) * fallbackFraction;
        }

        /// <summary>Crossfade to a clip. Speed 1 = authored rate. Re-playing the current clip only updates speed.</summary>
        public void Play(string clip, float fade = 0.25f, float speed = 1f, bool restart = false)
        {
            if (!anim || anim[clip] == null) { Current = clip; return; }
            var st = anim[clip];
            st.speed = speed;
            if (Current == clip && !restart && anim.IsPlaying(clip)) return;
            if (restart) st.time = 0f;
            anim.CrossFade(clip, fade);
            Current = clip;
            _prevTime = st.time;
        }

        /// <summary>Plays a one-shot clip from the start; returns its duration at the given speed.</summary>
        public float PlayOnce(string clip, float fade = 0.15f, float speed = 1f)
        {
            Play(clip, fade, speed, true);
            return Length(clip) / Mathf.Max(0.01f, speed);
        }

        /// <summary>Plays a clip on an upper layer restricted to one bone hierarchy (e.g. only the jaw), so
        /// clips that were baked with every bone do not override the body pose.</summary>
        public float PlayOverlay(string clip, string maskBone, float fade = 0.1f)
        {
            if (!anim || anim[clip] == null) return Length(clip);
            var st = anim[clip];
            if (st.layer != 2)
            {
                // unmasked, a clip baked with every bone would override the whole body pose
                var bone = FindBone(maskBone);
                if (!bone) return Length(clip);
                st.layer = 2;
                st.wrapMode = WrapMode.ClampForever;
                st.AddMixingTransform(bone, true);
            }
            st.time = 0f;
            anim.CrossFade(clip, fade, PlayMode.StopSameLayer);
            return st.length;
        }

        public void StopOverlay(string clip, float fade = 0.2f)
        {
            if (anim && anim[clip] != null) anim.Blend(clip, 0f, fade);
        }

        /// <summary>Scale playback so the feet match the ground speed.</summary>
        public void SyncSpeed(string clip, float groundSpeed, float min = 0.5f, float max = 1.8f)
        {
            if (!anim || anim[clip] == null) return;
            var i = Info(clip);
            if (i == null || i.authoredSpeed <= 0.01f) return;
            anim[clip].speed = Mathf.Clamp(groundSpeed / i.authoredSpeed, min, max);
        }

        public float NormalizedTime => anim && Current != null && anim[Current] != null ? anim[Current].normalizedTime : 0f;

        void LateUpdate()
        {
            RaiseEvents();
            ProceduralFallback();
            ApplyLook();
            if (Jaw && JawOpen > 0.01f) Jaw.localRotation *= Quaternion.AngleAxis(JawOpen, JawAxis);
        }

        void RaiseEvents()
        {
            if (AnimEvent == null || !anim || Current == null) return;
            var st = anim[Current];
            var info = Info(Current);
            if (st == null || info == null || info.events.Count == 0) return;
            float len = Mathf.Max(0.01f, st.length);
            float t = info.loop ? Mathf.Repeat(st.time, len) : Mathf.Min(st.time, len);
            float p = _prevTime;
            foreach (var e in info.events)
            {
                bool crossed = t >= p ? (e.time > p && e.time <= t) : (e.time > p || e.time <= t);
                if (crossed) AnimEvent(e.name);
            }
            _prevTime = t;
        }

        void ProceduralFallback()
        {
            if (anim && anim.isPlaying) return;
            if (!visualRoot) return;
            // no clips: subtle breathing bob so the creature never looks frozen by accident
            _bob += Time.deltaTime;
            visualRoot.localPosition = _visualRest + Vector3.up * Mathf.Sin(_bob * 2.2f) * 0.015f;
        }

        void ApplyLook()
        {
            if (!Head) return;
            float target = LookTarget.HasValue ? LookWeight : 0f;
            _lookW = Mathf.MoveTowards(_lookW, target, Time.deltaTime * 3f);
            _tilt = Mathf.MoveTowards(_tilt, HeadTilt, Time.deltaTime * 60f);
            if (_lookW > 0.001f && LookTarget.HasValue)
            {
                Vector3 curFwd = Head.TransformDirection(_headFwdLocal);
                Vector3 to = (LookTarget.Value - Head.position).normalized;
                // limit relative to the body
                Vector3 local = transform.InverseTransformDirection(to);
                float yaw = Mathf.Clamp(Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg, -maxLookYaw, maxLookYaw);
                float pitch = Mathf.Clamp(Mathf.Asin(Mathf.Clamp(local.y, -1f, 1f)) * Mathf.Rad2Deg, -maxLookPitch, maxLookPitch);
                Vector3 limited = transform.TransformDirection(Quaternion.Euler(-pitch, yaw, 0f) * Vector3.forward);
                Head.rotation = Quaternion.Slerp(Quaternion.identity, Quaternion.FromToRotation(curFwd, limited), _lookW) * Head.rotation;
            }
            if (Mathf.Abs(_tilt) > 0.1f)
                Head.rotation = Quaternion.AngleAxis(_tilt, Head.TransformDirection(_headFwdLocal)) * Head.rotation;
        }
    }
}
