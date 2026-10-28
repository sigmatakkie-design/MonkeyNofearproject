using UnityEngine;
using MonkeyNoFear.Audio;

namespace MonkeyNoFear.World
{
    /// <summary>Warm, irregular flame light for camps and lanterns: the only warm light in the forest.</summary>
    public class FireFlicker : MonoBehaviour
    {
        public Light target;
        public float baseIntensity = 1.6f;
        public float variation = 0.35f;
        public float speed = 6f;
        public string crackleLoop;
        float _seed;

        void Awake()
        {
            if (!target) target = GetComponent<Light>();
            _seed = Random.value * 100f;
        }

        void Start()
        {
            if (!string.IsNullOrEmpty(crackleLoop) && AudioManager.Instance)
                AudioManager.Instance.CreateLoop(crackleLoop, transform, 0.6f).FadeIn(2f);
        }

        void Update()
        {
            if (!target) return;
            float n = Mathf.PerlinNoise(_seed, Time.time * speed) * 2f - 1f;
            float m = Mathf.PerlinNoise(_seed + 7f, Time.time * speed * 2.7f) * 2f - 1f;
            target.intensity = baseIntensity * (1f + n * variation + m * variation * 0.4f);
        }
    }
}
