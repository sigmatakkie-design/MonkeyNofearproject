using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Items
{
    /// <summary>Trigger arms the beacon; drop or throw it and it spikes into the first surface it hits, then
    /// blinks red and blips every few seconds — a spatial sound you can follow back out of the dark.</summary>
    [RequireComponent(typeof(Grabbable))]
    public class MarkerBeacon : MonoBehaviour, IUsable, IExpeditionReset
    {
        public Light blink;
        public Renderer lamp;
        public float blipInterval = 2.5f;

        bool _armed, _deployed;
        float _t;
        Grabbable _grab;
        Material _mat;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        void Awake()
        {
            _grab = GetComponent<Grabbable>();
            if (!blink) blink = GetComponentInChildren<Light>(true);
            if (lamp) _mat = lamp.material;
            if (blink) { blink.enabled = false; blink.color = new Color(1f, 0.15f, 0.1f); blink.range = 5f; blink.renderMode = LightRenderMode.ForceVertex; }
            _grab.Grabbed += h => { if (_deployed) { _deployed = false; _armed = false; } };
        }

        void OnEnable() => ExpeditionManager.Register(this);
        void OnDisable() => ExpeditionManager.Unregister(this);

        public void OnNewExpedition(int index, System.Random rng)
        {
            // deployed beacons left outside are lost; carried / stored ones stay
            if (_deployed) Destroy(gameObject);
        }

        public void OnTrigger(HandGrabber hand, bool pressed)
        {
            if (!pressed) return;
            _armed = !_armed;
            AudioManager.Instance?.PlayAt("marker_blip", transform.position, 0.5f, _armed ? 1.2f : 0.8f);
        }

        public void OnTriggerHeld(HandGrabber hand, float v, float dt) { }
        public void OnPrimary(HandGrabber hand) { }

        void OnCollisionEnter(Collision c)
        {
            if (!_armed || _grab.IsHeld || _deployed) return;
            _deployed = true;
            _grab.Body.isKinematic = true;
            AudioManager.Instance?.PlayAt("marker_deploy", transform.position, 0.9f);
        }

        void Update()
        {
            if (!_deployed && !_armed) { if (blink) blink.enabled = false; return; }
            _t += Time.deltaTime;
            bool on = (_t % 1f) < 0.15f;
            if (blink) { blink.enabled = on; blink.intensity = 1.4f; }
            if (_mat) _mat.SetColor(EmissionId, on ? new Color(3f, 0.3f, 0.2f) : Color.black);
            if (_deployed && _t >= blipInterval)
            {
                _t = 0f;
                AudioManager.Instance?.PlayAt("marker_blip", transform.position, 0.7f);
            }
        }
    }
}
