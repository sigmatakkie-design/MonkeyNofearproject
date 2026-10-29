using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Items
{
    /// <summary>
    /// Handheld (or head-mounted) torch. Trigger toggles, primary button switches Wide / Focused beam.
    /// Battery drains while on and recharges inside the bunker; below 15 % it starts to flicker. Electrical
    /// interference (Lantern Mourner) makes it stutter — the only light manipulation that creature has.
    /// </summary>
    public class Flashlight : MonoBehaviour, IUsable, IPlayerLight
    {
        public static readonly List<Flashlight> All = new List<Flashlight>();

        public Light spot;
        public Renderer bulbRenderer;
        [Tooltip("Seconds of light on a full battery (before upgrades).")]
        public float batterySeconds = 210f;
        public float rechargePerSecond = 0.08f;
        [Header("Wide beam")]
        public float wideAngle = 62f, wideRange = 17f, wideIntensity = 2.2f;
        [Header("Focused beam")]
        public float focusAngle = 30f, focusRange = 30f, focusIntensity = 3.4f, focusDrain = 1.5f;
        public bool castShadows = true;
        [Tooltip("Head-mounted lamps toggle with the left primary button instead of the trigger.")]
        public bool headMounted;

        public float Battery01 { get; private set; } = 1f;
        public bool IsOn { get; private set; }
        public bool Focused { get; private set; }

        float _interference, _flickerTimer;
        bool _flickerOff;
        Material _bulbMat;
        Color _bulbEmission;
        bool _headToggleWas;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        public bool IsLit => IsOn && spot && spot.enabled;
        public Light Light => spot;
        public Vector3 Position => spot ? spot.transform.position : transform.position;
        public float Intensity01 => IsLit ? (Focused ? 1f : 0.75f) * Mathf.Clamp01(spot.intensity / focusIntensity) : 0f;

        void Awake()
        {
            if (!spot) spot = GetComponentInChildren<Light>(true);
            if (bulbRenderer) { _bulbMat = bulbRenderer.material; _bulbEmission = _bulbMat.GetColor(EmissionId); }
            if (spot)
            {
                spot.type = LightType.Spot;
                spot.shadows = castShadows ? LightShadows.Hard : LightShadows.None;
                spot.renderMode = LightRenderMode.ForcePixel;
            }
            ApplyMode();
            SetOn(false, true);
        }

        void OnEnable() { All.Add(this); PlayerStealth.RegisterLight(this); }
        void OnDisable() { All.Remove(this); PlayerStealth.UnregisterLight(this); }

        public void OnTrigger(HandGrabber hand, bool pressed)
        {
            if (pressed && !headMounted) Toggle();
        }

        public void OnTriggerHeld(HandGrabber hand, float value, float dt) { }

        public void OnPrimary(HandGrabber hand)
        {
            Focused = !Focused;
            ApplyMode();
            AudioManager.Instance?.PlayAt("flashlight_on", transform.position, 0.3f, 1.3f);
        }

        public void Toggle() => SetOn(!IsOn);

        public void SetOn(bool on, bool silent = false)
        {
            if (on && Battery01 <= 0f) { if (!silent) AudioManager.Instance?.PlayAt("battery_low", transform.position, 0.5f); return; }
            IsOn = on;
            if (!silent) AudioManager.Instance?.PlayAt(on ? "flashlight_on" : "flashlight_off", transform.position, 0.6f);
            Refresh();
        }

        public void Recharge(float amount = 1f) => Battery01 = Mathf.Clamp01(Battery01 + amount);

        /// <summary>Lantern Mourner: 0..1 interference strength for this frame.</summary>
        public void Interfere(float amount) => _interference = Mathf.Max(_interference, amount);

        void ApplyMode()
        {
            if (!spot) return;
            spot.spotAngle = Focused ? focusAngle : wideAngle;
            spot.innerSpotAngle = spot.spotAngle * 0.55f;
            spot.range = Focused ? focusRange : wideRange;
        }

        void Update()
        {
            var area = AreaManager.Instance;
            if (area && area.InSafeZone) Battery01 = Mathf.Min(1f, Battery01 + rechargePerSecond * Time.deltaTime);

            if (headMounted)
            {
                // toggled from the left controller's X button while worn on the head
                var rig = PlayerRig.Instance;
                bool x = rig && rig.Controller(Player.Hand.Left).primary;
                var grab = GetComponent<Grabbable>();
                bool worn = grab && grab.Holster != null && grab.Holster.headSlot; // not while hanging on the tool rack
                if (worn && x && !_headToggleWas) Toggle();
                _headToggleWas = x;
            }

            if (IsOn)
            {
                float mult = GameRoot.I ? GameRoot.I.Progress.BatteryMultiplier : 1f;
                float drain = (Focused ? focusDrain : 1f) / (batterySeconds * mult);
                Battery01 = Mathf.Max(0f, Battery01 - drain * Time.deltaTime);
                if (Battery01 <= 0f) { SetOn(false); AudioManager.Instance?.PlayAt("battery_low", transform.position, 0.6f); }
            }

            // flicker: low battery or interference
            float flickerChance = 0f;
            if (IsOn && Battery01 < 0.15f) flickerChance = (0.15f - Battery01) * 3f;
            flickerChance = Mathf.Max(flickerChance, _interference);
            _flickerTimer -= Time.deltaTime;
            if (_flickerTimer <= 0f)
            {
                _flickerTimer = Random.Range(0.04f, 0.18f);
                bool was = _flickerOff;
                _flickerOff = IsOn && Random.value < flickerChance * 0.6f;
                if (_flickerOff && !was && _interference > 0.2f) AudioManager.Instance?.PlayAt("flashlight_flicker_loop", transform.position, 0.4f);
            }
            _interference = Mathf.MoveTowards(_interference, 0f, Time.deltaTime * 2f);
            Refresh();
        }

        void Refresh()
        {
            if (!spot) return;
            bool lit = IsOn && !_flickerOff;
            spot.enabled = lit;
            float batteryDim = Battery01 < 0.3f ? Mathf.Lerp(0.45f, 1f, Battery01 / 0.3f) : 1f;
            spot.intensity = (Focused ? focusIntensity : wideIntensity) * batteryDim;
            if (_bulbMat) _bulbMat.SetColor(EmissionId, lit ? _bulbEmission * batteryDim : Color.black);
        }

        public bool Illuminates(Vector3 point)
        {
            if (!IsLit) return false;
            var p = spot.transform.position;
            var to = point - p;
            float d = to.magnitude;
            if (d > spot.range) return false;
            if (Vector3.Angle(spot.transform.forward, to) > spot.spotAngle * 0.5f) return false;
            return !Physics.Linecast(p, point, Layers.Occluders, QueryTriggerInteraction.Ignore);
        }

        /// <summary>Lowest battery among lights the player is carrying (held or holstered), or -1.</summary>
        public static float CarriedBattery()
        {
            float best = -1f;
            foreach (var f in All)
            {
                var g = f.GetComponent<Grabbable>();
                if (g && (g.IsHeld || g.Holster)) best = best < 0f ? f.Battery01 : Mathf.Min(best, f.Battery01);
            }
            return best;
        }

        public static void RechargeCarried()
        {
            foreach (var f in All)
            {
                var g = f.GetComponent<Grabbable>();
                if (g && (g.IsHeld || g.Holster)) f.Recharge();
            }
        }
    }
}
