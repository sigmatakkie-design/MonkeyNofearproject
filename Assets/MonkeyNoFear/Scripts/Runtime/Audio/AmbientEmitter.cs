using UnityEngine;

namespace MonkeyNoFear.Audio
{
    /// <summary>Positional ambience placed in the level: a loop (stream, generator, water trickle) and/or
    /// randomly timed one-shots (drips, distant knocks) around this point.</summary>
    public class AmbientEmitter : MonoBehaviour
    {
        public string loop;
        [Range(0, 1)] public float loopVolume = 0.8f;
        public string oneShot;
        public Vector2 interval = new Vector2(4f, 12f);
        public float scatterRadius = 2f;
        [Tooltip("Only emit while the listener is within this distance.")]
        public float activeDistance = 40f;

        ManagedLoop _loop;
        float _timer;

        void Start()
        {
            _timer = Random.Range(interval.x, interval.y);
            if (!string.IsNullOrEmpty(loop) && AudioManager.Instance)
                _loop = AudioManager.Instance.CreateLoop(loop, transform, loopVolume);
        }

        void Update()
        {
            var am = AudioManager.Instance;
            if (!am) return;
            bool near = (am.ListenerPosition - transform.position).sqrMagnitude < activeDistance * activeDistance;
            if (_loop) { if (near) _loop.FadeIn(0.5f); else _loop.FadeOut(0.5f); }
            if (string.IsNullOrEmpty(oneShot) || !near) return;
            _timer -= Time.deltaTime;
            if (_timer > 0f) return;
            _timer = Random.Range(interval.x, interval.y);
            var p = transform.position + Random.insideUnitSphere * scatterRadius;
            am.PlayAt(oneShot, p, Random.Range(0.6f, 1f));
        }

        void OnDrawGizmos() { Gizmos.color = new Color(0.3f, 0.7f, 1f, 0.6f); Gizmos.DrawWireSphere(transform.position, 0.3f); }
    }
}
