using System.Collections.Generic;
using UnityEngine;

namespace MonkeyNoFear.AI.Creatures
{
    /// <summary>Where the Lantern Mourner may appear (far ends of passages), or — when <see cref="isLure"/> —
    /// where it tries to lead a follower (beside a hazard).</summary>
    public class MournerPoint : MonoBehaviour
    {
        public static readonly List<MournerPoint> All = new List<MournerPoint>();
        public bool isLure;
        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);
        void OnDrawGizmos() { Gizmos.color = isLure ? Color.red : new Color(0.8f, 1f, 0.4f); Gizmos.DrawWireSphere(transform.position + Vector3.up, 0.6f); }
    }
}
