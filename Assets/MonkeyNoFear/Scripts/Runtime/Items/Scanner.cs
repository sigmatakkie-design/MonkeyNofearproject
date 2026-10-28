using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Mining;

namespace MonkeyNoFear.Items
{
    /// <summary>Handheld ore scanner: while held it beeps faster the closer the nearest intact deposit is,
    /// and its screen shows the mineral, distance and a direction arrow. Primary button filters to
    /// valuable minerals only.</summary>
    [RequireComponent(typeof(Grabbable))]
    public class Scanner : MonoBehaviour, IUsable
    {
        public float range = 35f;
        public TextMesh screen;
        public Renderer lamp;
        public bool valuableOnly;

        Grabbable _grab;
        float _beepTimer, _scanTimer;
        OreDeposit _target;
        Material _lampMat;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        void Awake()
        {
            _grab = GetComponent<Grabbable>();
            if (lamp) _lampMat = lamp.material;
        }

        public void OnTrigger(HandGrabber hand, bool pressed) { }
        public void OnTriggerHeld(HandGrabber hand, float v, float dt) { }
        public void OnPrimary(HandGrabber hand)
        {
            valuableOnly = !valuableOnly;
            AudioManager.Instance?.PlayAt("scanner_beep", transform.position, 0.4f, 1.5f);
        }

        void Update()
        {
            bool active = _grab.IsHeld;
            if (screen) screen.gameObject.SetActive(active);
            if (!active) { if (_lampMat) _lampMat.SetColor(EmissionId, Color.black); return; }

            _scanTimer -= Time.deltaTime;
            if (_scanTimer <= 0f) { _scanTimer = 0.3f; _target = FindNearest(); }

            if (!_target)
            {
                if (screen) screen.text = valuableOnly ? "SCAN: RARE\nNO SIGNAL" : "SCAN: ALL\nNO SIGNAL";
                return;
            }
            Vector3 to = _target.transform.position - transform.position;
            float d = to.magnitude;
            var local = transform.InverseTransformDirection(to);
            string arrow = Mathf.Abs(local.x) < Mathf.Abs(local.z) * 0.4f ? (local.z > 0 ? "^" : "v") : (local.x > 0 ? ">" : "<");
            if (Mathf.Abs(to.y) > 4f && Mathf.Abs(to.y) > Mathf.Sqrt(to.x * to.x + to.z * to.z)) arrow = to.y > 0 ? "UP" : "DOWN";
            if (screen)
                screen.text = $"{(_target.mineral ? _target.mineral.displayName.ToUpperInvariant() : "ORE")}\n{d:0}m {arrow}";

            float interval = Mathf.Lerp(0.12f, 1.6f, Mathf.Clamp01(d / range));
            _beepTimer -= Time.deltaTime;
            if (_beepTimer <= 0f)
            {
                _beepTimer = interval;
                AudioManager.Instance?.PlayAt(d < 4f ? "scanner_beep_strong" : "scanner_beep", transform.position, 0.45f);
                if (_lampMat) _lampMat.SetColor(EmissionId, new Color(0.3f, 1f, 0.4f) * 2f);
            }
            else if (_lampMat && _beepTimer < interval - 0.06f) _lampMat.SetColor(EmissionId, Color.black);
        }

        OreDeposit FindNearest()
        {
            OreDeposit best = null;
            float bd = range * range;
            foreach (var dep in OreDeposit.Active)
            {
                if (!dep || dep.Depleted || !dep.mineral) continue;
                if (valuableOnly && dep.mineral.chunkItem && dep.mineral.chunkItem.rarity < 2) continue;
                float d = (dep.transform.position - transform.position).sqrMagnitude;
                if (d < bd) { bd = d; best = dep; }
            }
            return best;
        }
    }
}
