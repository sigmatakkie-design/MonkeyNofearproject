using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.AI.Creatures
{
    /// <summary>
    /// Authored attachment point for the Ceiling Clerk on a beam / rock ceiling. At start it snaps to the
    /// real surface above it (raycast) and links to visible neighbours, forming the graph the Clerk crawls
    /// along — it never flies freely through the tunnel.
    /// </summary>
    public class ClerkNode : MonoBehaviour
    {
        public static readonly List<ClerkNode> All = new List<ClerkNode>();
        public float linkDistance = 8.5f;
        public float searchUp = 6f;

        public Vector3 SurfacePoint { get; private set; }
        public Vector3 Normal { get; private set; } = Vector3.down;
        public readonly List<ClerkNode> neighbours = new List<ClerkNode>();
        public bool Valid { get; private set; }

        void OnEnable() { All.Add(this); Snap(); }
        void OnDisable() => All.Remove(this);

        void Snap()
        {
            if (Physics.Raycast(transform.position, Vector3.up, out var hit, searchUp, Layers.Occluders, QueryTriggerInteraction.Ignore))
            {
                SurfacePoint = hit.point; Normal = hit.normal; Valid = true;
            }
            else { SurfacePoint = transform.position; Normal = Vector3.down; Valid = false; }
        }

        /// <summary>Called once all nodes exist (by the first Clerk).</summary>
        public static void LinkAll()
        {
            foreach (var n in All) n.neighbours.Clear();
            for (int i = 0; i < All.Count; i++)
            for (int j = i + 1; j < All.Count; j++)
            {
                var a = All[i]; var b = All[j];
                if (!a.Valid || !b.Valid) continue;
                float d = Vector3.Distance(a.SurfacePoint, b.SurfacePoint);
                if (d > Mathf.Min(a.linkDistance, b.linkDistance)) continue;
                var pa = a.SurfacePoint + a.Normal * 0.3f;
                var pb = b.SurfacePoint + b.Normal * 0.3f;
                if (Physics.Linecast(pa, pb, Layers.Occluders, QueryTriggerInteraction.Ignore)) continue;
                a.neighbours.Add(b); b.neighbours.Add(a);
            }
        }

        public Vector3 HangPoint(float offset) => SurfacePoint + Normal * offset;

        void OnDrawGizmos()
        {
            Gizmos.color = Valid || !Application.isPlaying ? new Color(0.8f, 0.3f, 1f) : Color.red;
            var p = Application.isPlaying ? SurfacePoint : transform.position;
            Gizmos.DrawWireSphere(p, 0.25f);
            foreach (var n in neighbours) if (n) Gizmos.DrawLine(p, n.SurfacePoint);
        }
    }
}
