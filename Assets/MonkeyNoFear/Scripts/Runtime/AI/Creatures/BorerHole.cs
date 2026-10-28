using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.World;

namespace MonkeyNoFear.AI.Creatures
{
    /// <summary>Authored emergence point for the Borer: an existing burrow opening or a loose rubble plug
    /// that bursts the first time the Borer comes through it (and is restored between expeditions).</summary>
    public class BorerHole : MonoBehaviour, IExpeditionReset
    {
        public static readonly List<BorerHole> All = new List<BorerHole>();
        [Tooltip("Optional rubble plug that blocks the passage until the Borer breaks it.")]
        public GameObject plug;

        public bool Opened { get; private set; }

        void OnEnable() { All.Add(this); ExpeditionManager.Register(this); }
        void OnDisable() { All.Remove(this); ExpeditionManager.Unregister(this); }

        public void OnNewExpedition(int index, System.Random rng)
        {
            Opened = false;
            if (plug) plug.SetActive(true);
        }

        public void Burst()
        {
            if (Opened) return;
            Opened = true;
            if (plug)
            {
                plug.SetActive(false);
                AudioManager.Instance?.PlayAt("rock_fall_large", transform.position, 1f);
                FXManager.Burst("debris", transform.position + Vector3.up, transform.forward, new Color(0.35f, 0.32f, 0.3f), 60);
                FXManager.Burst("dust", transform.position + Vector3.up, Vector3.up, new Color(0.5f, 0.47f, 0.43f, 0.5f), 25);
            }
        }

        public static BorerHole Nearest(Vector3 p)
        {
            BorerHole best = null; float bd = float.MaxValue;
            foreach (var h in All) { float d = (h.transform.position - p).sqrMagnitude; if (d < bd) { bd = d; best = h; } }
            return best;
        }

        void OnDrawGizmos() { Gizmos.color = new Color(0.9f, 0.5f, 0.1f); Gizmos.DrawWireSphere(transform.position + Vector3.up, 1.2f); }
    }
}
