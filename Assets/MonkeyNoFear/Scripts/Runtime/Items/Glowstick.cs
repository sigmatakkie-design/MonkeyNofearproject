using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Items
{
    /// <summary>Crack it (trigger) and drop it to mark a route. Dim, long-lasting, quiet. A weak lure.</summary>
    [RequireComponent(typeof(Grabbable))]
    public class Glowstick : MonoBehaviour, IUsable, IWorldLight
    {
        public Light glow;
        public Renderer tube;
        public float lifetime = 600f;
        public Color color = new Color(0.35f, 1f, 0.45f);

        bool _cracked;
        float _age;
        Material _mat;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        public bool IsLit => _cracked && _age < lifetime;
        public Vector3 Position => transform.position;
        public float Radius => glow ? glow.range : 4f;
        public float Strength => IsLit ? 0.3f * Fade : 0f;
        float Fade => Mathf.Clamp01((lifetime - _age) / (lifetime * 0.25f));

        void Awake()
        {
            if (!glow) glow = GetComponentInChildren<Light>(true);
            if (tube) _mat = tube.material;
            if (glow) { glow.enabled = false; glow.color = color; glow.range = 4.5f; glow.intensity = 0.9f; glow.renderMode = LightRenderMode.ForceVertex; }
            if (_mat) _mat.SetColor(EmissionId, Color.black);
        }

        void OnEnable() => WorldLights.Register(this);
        void OnDisable() => WorldLights.Unregister(this);

        public void OnTrigger(HandGrabber hand, bool pressed)
        {
            if (!pressed || _cracked) return;
            _cracked = true;
            AudioManager.Instance?.PlayAt("glowstick_crack", transform.position, 0.8f);
            if (glow) glow.enabled = true;
        }

        public void OnTriggerHeld(HandGrabber hand, float v, float dt) { }
        public void OnPrimary(HandGrabber hand) { }

        void Update()
        {
            if (!_cracked) return;
            _age += Time.deltaTime;
            float f = Fade;
            if (glow) { glow.intensity = 0.9f * f; glow.enabled = f > 0.01f; }
            if (_mat) _mat.SetColor(EmissionId, color * (1.5f * f));
        }
    }
}
