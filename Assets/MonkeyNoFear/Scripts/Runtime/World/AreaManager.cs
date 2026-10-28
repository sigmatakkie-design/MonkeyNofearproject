using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;

namespace MonkeyNoFear.World
{
    [DefaultExecutionOrder(-60)]
    public class AreaManager : MonoBehaviour
    {
        public static AreaManager Instance { get; private set; }
        static readonly List<AreaZone> Zones = new List<AreaZone>();

        public List<AtmosphereProfile> profiles = new List<AtmosphereProfile>();
        public AreaId startArea = AreaId.Bunker;
        public Light moonLight;
        public float moonBaseIntensity = 0.35f;
        [Tooltip("Seconds to blend fog/ambient between areas.")]
        public float blendTime = 2.5f;
        public List<AreaRoot> roots = new List<AreaRoot>();

        public AreaId Current { get; private set; } = AreaId.None;
        public AtmosphereProfile CurrentProfile { get; private set; }
        public int DepthLevel => CurrentProfile ? CurrentProfile.depthLevel : 0;
        public bool InSafeZone => CurrentProfile && CurrentProfile.isSafeZone;

        Camera _camera;
        AudioReverbFilter _reverb;
        float _checkTimer;
        // blended atmosphere state
        Color _fogColor, _sky, _eq, _ground;
        float _fogDensity, _moon, _far;

        public static void RegisterZone(AreaZone z) { if (!Zones.Contains(z)) Zones.Add(z); }
        public static void UnregisterZone(AreaZone z) => Zones.Remove(z);

        void Awake()
        {
            if (Instance && Instance != this) { Destroy(this); return; }
            Instance = this;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        public AtmosphereProfile GetProfile(AreaId id)
        {
            foreach (var p in profiles) if (p && p.area == id) return p;
            return null;
        }

        public void BindCamera(Camera cam)
        {
            _camera = cam;
            if (cam)
            {
                _reverb = cam.GetComponent<AudioReverbFilter>();
                if (!_reverb) _reverb = cam.gameObject.AddComponent<AudioReverbFilter>();
            }
        }

        void Start()
        {
            ForceArea(startArea);
        }

        /// <summary>Snap atmosphere and roots immediately (spawn / respawn).</summary>
        public void ForceArea(AreaId id)
        {
            SetArea(id);
            var p = CurrentProfile;
            if (!p) return;
            _fogColor = p.fogColor; _fogDensity = p.fogDensity; _sky = p.ambientSky; _eq = p.ambientEquator;
            _ground = p.ambientGround; _moon = p.moonIntensity; _far = p.farClip;
            ApplyAtmosphere();
        }

        void SetArea(AreaId id)
        {
            if (id == Current) return;
            var old = Current;
            Current = id;
            CurrentProfile = GetProfile(id);
            foreach (var r in roots)
                if (r) r.gameObject.SetActive(r.ShouldBeActive(id));
            if (_reverb) _reverb.reverbPreset = CurrentProfile ? CurrentProfile.reverb : AudioReverbPreset.Off;
            GameEvents.RaiseAreaChanged(old, id);
        }

        void Update()
        {
            var player = Player.PlayerRig.Instance;
            _checkTimer -= Time.deltaTime;
            if (player && _checkTimer <= 0f)
            {
                _checkTimer = 0.2f;
                var head = player.HeadPosition;
                AreaZone best = null;
                foreach (var z in Zones)
                    if (z && z.Contains(head) && (best == null || z.priority > best.priority)) best = z;
                if (best) SetArea(best.area);
            }

            var p = CurrentProfile;
            if (!p) return;
            float k = blendTime <= 0f ? 1f : 1f - Mathf.Exp(-Time.deltaTime * 3f / blendTime);
            _fogColor = Color.Lerp(_fogColor, p.fogColor, k);
            _fogDensity = Mathf.Lerp(_fogDensity, p.fogDensity, k);
            _sky = Color.Lerp(_sky, p.ambientSky, k);
            _eq = Color.Lerp(_eq, p.ambientEquator, k);
            _ground = Color.Lerp(_ground, p.ambientGround, k);
            _moon = Mathf.Lerp(_moon, p.moonIntensity, k);
            _far = Mathf.Lerp(_far, p.farClip, k);
            ApplyAtmosphere();
        }

        void ApplyAtmosphere()
        {
            RenderSettings.fogColor = _fogColor;
            RenderSettings.fogDensity = _fogDensity;
            RenderSettings.ambientSkyColor = _sky;
            RenderSettings.ambientEquatorColor = _eq;
            RenderSettings.ambientGroundColor = _ground;
            if (moonLight)
            {
                moonLight.intensity = moonBaseIntensity * _moon;
                moonLight.enabled = _moon > 0.01f;
            }
            if (_camera)
            {
                _camera.farClipPlane = Mathf.Max(20f, _far);
                _camera.backgroundColor = _fogColor;
            }
        }

        /// <summary>Distance at which fog hides silhouettes right now (AI vision is limited by it too).</summary>
        public float FogVisibility => _fogDensity <= 0.0001f ? 500f : 1.589f / _fogDensity;
    }
}
