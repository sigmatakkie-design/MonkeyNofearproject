using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.Items
{
    /// <summary>Hold the trigger for a moment to use: first-aid tin (heal) or battery pack (recharge every
    /// light you are carrying). Consumed on use.</summary>
    [RequireComponent(typeof(Grabbable))]
    public class Consumable : MonoBehaviour, IUsable
    {
        public enum Effect { Heal, RechargeLights }
        public Effect effect = Effect.Heal;
        public float amount = 50f;
        public float holdSeconds = 1.2f;
        public string useSound = "medkit_use";

        float _hold;
        bool _soundPlayed;

        public void OnTrigger(HandGrabber hand, bool pressed)
        {
            _hold = 0f;
            _soundPlayed = false;
        }

        public void OnTriggerHeld(HandGrabber hand, float value, float dt)
        {
            if (value < 0.5f) { _hold = 0f; return; }
            if (!_soundPlayed) { _soundPlayed = true; AudioManager.Instance?.PlayAt(useSound, transform.position, 0.8f); }
            _hold += dt;
            hand.Rig?.Haptic(hand.Side, 0.1f, 0.02f);
            if (_hold < holdSeconds) return;
            if (effect == Effect.Heal)
            {
                if (PlayerHealth.Instance) PlayerHealth.Instance.Heal(amount);
                GameEvents.Toast("PATCHED UP");
            }
            else
            {
                Flashlight.RechargeCarried();
                GameEvents.Toast("LIGHTS RECHARGED");
            }
            hand.ForceRelease();
            Destroy(gameObject);
        }

        public void OnPrimary(HandGrabber hand) { }
    }
}
