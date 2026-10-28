using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;

namespace MonkeyNoFear.Bunker
{
    /// <summary>Fluorescent tube / old bulb behaviour: occasional stutters, rare bursts (events), dims with
    /// bunker power, keeps its emissive fixture in sync. Optional hum loop and flicker ticks.</summary>
    public class FlickerLight : MonoBehaviour
    {
        static readonly List<FlickerLight> All = new List<FlickerLight>();

        public Light target;
        public Renderer emissive;
        [Tooltip("Average stutters per minute (0 = steady).")]
        public float stuttersPerMinute = 2f;
        public bool followsBunkerPower = true;
        public string humLoop;
        public bool flickerSound = true;

        float _base, _burst, _stutter;
        Material _mat;
        Color _emission;
        ManagedLoop _hum;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        void Awake()
        {
            if (!target) target = GetComponent<Light>();
            if (target) _base = target.intensity;
            if (emissive) { _mat = emissive.material; _emission = _mat.GetColor(EmissionId); }
        }

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        void Start()
        {
            if (!string.IsNullOrEmpty(humLoop) && AudioManager.Instance)
            {
                _hum = AudioManager.Instance.CreateLoop(humLoop, transform, 0.5f);
                _hum.FadeIn(5f);
            }
        }

        public static void BurstAll(float seconds) { foreach (var f in All) f.Burst(seconds * Random.Range(0.6f, 1.2f)); }
        public void Burst(float seconds) => _burst = Mathf.Max(_burst, seconds);

        void Update()
        {
            float power = followsBunkerPower && BunkerPower.Instance ? BunkerPower.Instance.Level : 1f;
            float k = power;
            if (_burst > 0f)
            {
                _burst -= Time.deltaTime;
                k *= Random.value < 0.45f ? Random.Range(0f, 0.3f) : 1f;
            }
            else if (stuttersPerMinute > 0f)
            {
                if (_stutter > 0f) { _stutter -= Time.deltaTime; k *= Random.value < 0.5f ? 0.1f : 1f; }
                else if (Random.value < stuttersPerMinute / 60f * Time.deltaTime)
                {
                    _stutter = Random.Range(0.08f, 0.5f);
                    if (flickerSound) AudioManager.Instance?.PlayAt("fluorescent_flicker", transform.position, 0.5f);
                }
            }
            if (target) { target.intensity = _base * k; target.enabled = k > 0.02f; }
            if (_mat) _mat.SetColor(EmissionId, _emission * k);
            if (_hum) _hum.SetVolume(0.5f * power);
        }
    }
}
