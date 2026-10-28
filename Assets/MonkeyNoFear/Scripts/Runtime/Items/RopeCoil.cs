using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Items
{
    /// <summary>Hold the coil over a drop and pull the trigger: the hook bites into the edge and the rope
    /// unrolls to the ground below (max 18 m). The rope is a climbable surface in mid-air, so you can climb
    /// down — and back up — shafts that would otherwise be a one-way fall. Ropes are cleared between
    /// expeditions.</summary>
    [RequireComponent(typeof(Grabbable))]
    public class RopeCoil : MonoBehaviour, IUsable
    {
        public float maxLength = 18f;
        public float minDrop = 1.5f;
        public Material ropeMaterial;

        public void OnTrigger(HandGrabber hand, bool pressed)
        {
            if (!pressed) return;
            Vector3 top = hand.HandPosition + Vector3.up * 0.05f;
            if (!Physics.Raycast(top, Vector3.down, out var hit, maxLength, Layers.SolidWorld, QueryTriggerInteraction.Ignore) || hit.distance < minDrop)
            {
                GameEvents.Toast(hit.collider ? "NOT A BIG ENOUGH DROP" : "TOO DEEP FOR THE ROPE");
                AudioManager.Instance?.PlayAt("terminal_error", top, 0.4f);
                return;
            }
            DeployedRope.Create(top, hit.point, ropeMaterial);
            AudioManager.Instance?.PlayAt("rope_unroll", top, 1f);
            hand.ForceRelease();
            Destroy(gameObject);
        }

        public void OnTriggerHeld(HandGrabber hand, float v, float dt) { }
        public void OnPrimary(HandGrabber hand) { }
    }
}
