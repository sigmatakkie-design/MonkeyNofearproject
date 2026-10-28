using UnityEngine;
using MonkeyNoFear.AI;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.Items
{
    /// <summary>Strike it (trigger): a big hissing red light for 90 s. Lights up a chamber, keeps the
    /// Ceiling Clerk off nearby beams, and — thrown away from you — decoys the Lantern Mourner.</summary>
    [RequireComponent(typeof(Grabbable))]
    public class Flare : MonoBehaviour, IUsable, IWorldLight, IPlayerLight
    {
        public Light flame;
        public ParticleSystem smoke;
        public Transform tip;
        public float burnSeconds = 90f;
        public Color color = new Color(1f, 0.22f, 0.12f);

        bool _lit, _spent;
        float _age, _flicker;
        ManagedLoop _loop;

        public bool IsLit => _lit && !_spent;
        public Vector3 Position => tip ? tip.position : transform.position;
        public float Radius => 14f;
        public float Strength => IsLit ? 1f : 0f;
        public Light Light => flame;
        public float Intensity01 => IsLit ? 1f : 0f;

        public bool Illuminates(Vector3 p)
        {
            if (!IsLit || (p - Position).sqrMagnitude > Radius * Radius) return false;
            return !Physics.Linecast(Position, p, Core.Layers.Occluders, QueryTriggerInteraction.Ignore);
        }

        void Awake()
        {
            if (!tip) tip = transform.Find("TIP");
            if (!flame) flame = GetComponentInChildren<Light>(true);
            if (flame) { flame.enabled = false; flame.type = LightType.Point; flame.color = color; flame.range = Radius; flame.shadows = LightShadows.None; }
            if (smoke) smoke.Stop();
        }

        void OnEnable() { WorldLights.Register(this); PlayerStealth.RegisterLight(this); }
        void OnDisable() { WorldLights.Unregister(this); PlayerStealth.UnregisterLight(this); }

        public void OnTrigger(HandGrabber hand, bool pressed)
        {
            if (!pressed || _lit) return;
            _lit = true;
            AudioManager.Instance?.PlayAt("flare_ignite", Position, 1f);
            NoiseSystem.Emit(Position, 0.25f, NoiseKind.Flare, true, this);
            if (flame) flame.enabled = true;
            if (smoke) smoke.Play();
            _loop = AudioManager.Instance ? AudioManager.Instance.CreateLoop("flare_burn_loop", tip ? tip : transform) : null;
            _loop?.FadeIn(4f);
        }

        public void OnTriggerHeld(HandGrabber hand, float v, float dt) { }
        public void OnPrimary(HandGrabber hand) { }

        void Update()
        {
            if (!_lit || _spent) return;
            _age += Time.deltaTime;
            _flicker = Mathf.Lerp(_flicker, Random.Range(0.75f, 1.15f), 0.35f);
            float end = Mathf.Clamp01((burnSeconds - _age) / 6f);
            if (flame) flame.intensity = 2.6f * _flicker * end;
            if (_age >= burnSeconds)
            {
                _spent = true;
                if (flame) flame.enabled = false;
                if (smoke) smoke.Stop();
                _loop?.FadeOut(1f);
            }
        }
    }
}
