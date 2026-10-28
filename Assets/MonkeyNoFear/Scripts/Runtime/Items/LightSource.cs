using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.Items
{
    /// <summary>Registry of artificial lights in the world (flares, glowsticks, marker beacons, deposit
    /// glow does not count). The Lantern Mourner is drawn to these; the Ceiling Clerk avoids them.</summary>
    public static class WorldLights
    {
        public struct Entry { public Vector3 position; public float radius; public float strength; public Object owner; }
        static readonly List<IWorldLight> Lights = new List<IWorldLight>();

        public static void Register(IWorldLight l) { if (!Lights.Contains(l)) Lights.Add(l); }
        public static void Unregister(IWorldLight l) => Lights.Remove(l);

        /// <summary>Strongest lit world light near a point (within its radius, with line of sight).</summary>
        public static IWorldLight StrongestAt(Vector3 p, bool requireLos = true)
        {
            IWorldLight best = null; float bs = 0f;
            foreach (var l in Lights)
            {
                if (l == null || !l.IsLit) continue;
                float d = Vector3.Distance(l.Position, p);
                if (d > l.Radius) continue;
                float s = l.Strength * (1f - d / l.Radius);
                if (s <= bs) continue;
                if (requireLos && Physics.Linecast(l.Position, p, Layers.Occluders, QueryTriggerInteraction.Ignore)) continue;
                best = l; bs = s;
            }
            return best;
        }

        /// <summary>The most attractive light within range of a point (for the Mourner's attraction).</summary>
        public static IWorldLight MostAttractive(Vector3 from, float range)
        {
            IWorldLight best = null; float bs = 0f;
            foreach (var l in Lights)
            {
                if (l == null || !l.IsLit) continue;
                float d = Vector3.Distance(l.Position, from);
                if (d > range) continue;
                float s = l.Strength / (1f + d * 0.1f);
                if (s > bs) { best = l; bs = s; }
            }
            return best;
        }
    }

    public interface IWorldLight
    {
        bool IsLit { get; }
        Vector3 Position { get; }
        float Radius { get; }
        float Strength { get; }
    }
}
