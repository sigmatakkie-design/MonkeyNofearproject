using System.Collections.Generic;
using UnityEngine;

namespace MonkeyNoFear.AI.Wildlife
{
    /// <summary>A hole small animals bolt into when startled. They vanish inside and re-emerge when it is quiet.</summary>
    public class Burrow : MonoBehaviour
    {
        public static readonly List<Burrow> All = new List<Burrow>();
        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        public static Burrow NearestAwayFrom(Vector3 from, Vector3 threat, float maxDist)
        {
            Burrow best = null; float bd = maxDist * maxDist;
            foreach (var b in All)
            {
                var p = b.transform.position;
                float d = (p - from).sqrMagnitude;
                if (d > bd) continue;
                // do not run toward the threat
                if (Vector3.Dot((p - from).normalized, (threat - from).normalized) > 0.3f) continue;
                bd = d; best = b;
            }
            return best;
        }

        void OnDrawGizmos() { Gizmos.color = new Color(0.6f, 0.4f, 0.2f); Gizmos.DrawWireSphere(transform.position, 0.4f); }
    }
}
