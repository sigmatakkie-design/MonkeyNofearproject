using UnityEngine;
using MonkeyNoFear.AI;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Items
{
    /// <summary>A tin can full of bolts. Throw it: every hard landing makes a loud rattle that
    /// sound-hunting creatures (Hollowback, Borer) go to investigate. Shaking it in your hand works too —
    /// but then they come to you. Falls apart after a few rattles.</summary>
    [RequireComponent(typeof(Grabbable))]
    public class Noisemaker : MonoBehaviour, IUsable
    {
        public int rattles = 6;
        public float loudness = 1.1f;
        public float minImpactSpeed = 2.5f;

        Grabbable _grab;
        float _last;

        void Awake() { _grab = GetComponent<Grabbable>(); _grab.impactNoise = false; }

        void OnCollisionEnter(Collision c)
        {
            if (_grab.IsHeld || c.relativeVelocity.magnitude < minImpactSpeed) return;
            Rattle(loudness);
        }

        public void OnTrigger(HandGrabber hand, bool pressed) { if (pressed) Rattle(loudness * 0.7f); }
        public void OnTriggerHeld(HandGrabber hand, float v, float dt) { }
        public void OnPrimary(HandGrabber hand) { }

        void Rattle(float loud)
        {
            if (Time.time - _last < 0.35f) return;
            _last = Time.time;
            AudioManager.Instance?.PlayAt("noisemaker_rattle", transform.position, 1f);
            NoiseSystem.Emit(transform.position, loud, NoiseKind.Lure, false, this);
            if (--rattles <= 0)
            {
                Core.GameEvents.Toast("THE RATTLE CAN FELL APART");
                if (_grab.IsHeld) _grab.Holder.ForceRelease();
                Destroy(gameObject, 0.05f);
            }
        }
    }
}
