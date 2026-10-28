using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Player
{
    /// <summary>Your dropped backpack after dying. Grab it to refill your backpack; whatever does not fit
    /// spills out. A faint blinking light and a periodic blip help you find it in the dark.</summary>
    public class LostPack : MonoBehaviour, IGrabInteractable
    {
        public List<Grabbable> contents = new List<Grabbable>();
        Light _light;
        float _blip;

        void Start()
        {
            gameObject.layer = Core.Layers.Interactable;
            if (!GetComponent<Collider>())
            {
                var s = gameObject.AddComponent<SphereCollider>();
                s.radius = 0.3f;
                s.isTrigger = true;
            }
            _light = gameObject.AddComponent<Light>();
            _light.type = LightType.Point;
            _light.color = new Color(1f, 0.25f, 0.15f);
            _light.range = 3f;
            _light.renderMode = LightRenderMode.ForceVertex;
        }

        void Update()
        {
            _light.intensity = 0.6f + Mathf.Sin(Time.time * 4f) * 0.4f;
            _blip -= Time.deltaTime;
            if (_blip <= 0f) { _blip = 3f; AudioManager.Instance?.PlayAt("marker_blip", transform.position, 0.5f); }
        }

        public bool CanGrab(HandGrabber hand) => true;

        public void BeginGrab(HandGrabber hand)
        {
            var bp = Backpack.Instance;
            foreach (var g in contents)
            {
                if (!g) continue;
                if (bp && bp.Count < bp.Capacity) { g.transform.SetParent(null); bp.Store(g); }
                else
                {
                    g.gameObject.SetActive(true);
                    g.MakeLoose();
                    g.transform.position = transform.position + Random.insideUnitSphere * 0.3f + Vector3.up * 0.2f;
                }
            }
            contents.Clear();
            Core.GameEvents.Toast("PACK RECOVERED");
            hand.ForceRelease();
            Destroy(gameObject);
        }

        public void UpdateGrab(HandGrabber hand, float dt) { }
        public void EndGrab(HandGrabber hand) { }
    }
}
