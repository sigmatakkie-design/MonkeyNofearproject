using System.Collections;
using UnityEngine;
using MonkeyNoFear.Audio;

namespace MonkeyNoFear.Bunker
{
    /// <summary>The bunker generator. Occasionally hiccups (horror director): lights dim to emergency red,
    /// the security gate motor loses power (manual override still works), then everything stutters back.</summary>
    public class BunkerPower : MonoBehaviour
    {
        public static BunkerPower Instance { get; private set; }

        public SecurityGate gate;
        public Light[] emergencyLights = new Light[0];
        public Transform generator;

        public float Level { get; private set; } = 1f;
        public bool Powered => Level > 0.5f;
        ManagedLoop _gen;
        bool _dipping;

        void Awake() { Instance = this; }

        void Start()
        {
            if (AudioManager.Instance && generator)
            {
                _gen = AudioManager.Instance.CreateLoop("generator_loop", generator, 0.8f);
                _gen.FadeIn(2f);
            }
            foreach (var l in emergencyLights) if (l) l.enabled = false;
        }

        public void Dip(float seconds) { if (!_dipping) StartCoroutine(DipRoutine(seconds)); }

        IEnumerator DipRoutine(float seconds)
        {
            _dipping = true;
            AudioManager.Instance?.PlayAt("spark", generator ? generator.position : transform.position, 1f);
            for (float t = 0f; t < 1f; t += Time.deltaTime) { Level = Mathf.Lerp(1f, 0.05f, t); yield return null; }
            Level = 0.05f;
            _gen?.SetPitch(0.6f); _gen?.SetVolume(0.3f);
            if (gate) gate.Powered = false;
            foreach (var l in emergencyLights) if (l) l.enabled = true;
            yield return new WaitForSeconds(seconds);
            // stutter back
            for (int i = 0; i < 5; i++) { Level = Random.value < 0.5f ? 0.1f : 0.9f; yield return new WaitForSeconds(Random.Range(0.08f, 0.25f)); }
            Level = 1f;
            _gen?.SetPitch(1f); _gen?.SetVolume(0.8f);
            if (gate) gate.Powered = true;
            foreach (var l in emergencyLights) if (l) l.enabled = false;
            _dipping = false;
        }
    }
}
