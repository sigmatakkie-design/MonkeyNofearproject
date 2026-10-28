using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Data;

namespace MonkeyNoFear.World
{
    /// <summary>Tags a collider with a surface type: drives hand-tap sounds, noise loudness, slipperiness
    /// and impact effects. Colliders without one are classified from their material names (cached).</summary>
    public class Surface : MonoBehaviour
    {
        public SurfaceKind kind = SurfaceKind.Rock;
        [Tooltip("0 = grippy, 1 = ice. Hands slide along slippery surfaces instead of anchoring.")]
        [Range(0, 1)] public float slipperiness;

        static readonly Dictionary<int, SurfaceKind> Cache = new Dictionary<int, SurfaceKind>();

        public static SurfaceKind KindOf(Collider c)
        {
            if (!c) return SurfaceKind.Rock;
            var s = c.GetComponentInParent<Surface>();
            if (s) return s.kind;
            int id = c.GetInstanceID();
            if (Cache.TryGetValue(id, out var k)) return k;
            k = Guess(c);
            Cache[id] = k;
            return k;
        }

        public static float SlipperinessOf(Collider c)
        {
            if (!c) return 0f;
            var s = c.GetComponentInParent<Surface>();
            if (s) return s.slipperiness;
            return c.gameObject.layer == Core.Layers.NoClimb ? 1f : 0f;
        }

        static SurfaceKind Guess(Collider c)
        {
            var r = c.GetComponent<Renderer>();
            string n = r && r.sharedMaterial ? r.sharedMaterial.name : c.name;
            return FromName(n);
        }

        public static SurfaceKind FromName(string n)
        {
            if (string.IsNullOrEmpty(n)) return SurfaceKind.Rock;
            if (n.Contains("Metal") || n.Contains("Hazard") || n.Contains("Rail") || n.Contains("Grate")) return SurfaceKind.Metal;
            if (n.Contains("Wood") || n.Contains("Bark") || n.Contains("Plank") || n.Contains("Beam")) return SurfaceKind.Wood;
            if (n.Contains("Concrete")) return SurfaceKind.Concrete;
            if (n.Contains("Mud")) return SurfaceKind.Mud;
            if (n.Contains("Foliage") || n.Contains("Fern") || n.Contains("Grass") || n.Contains("Leaf") || n.Contains("Moss")) return SurfaceKind.Foliage;
            if (n.Contains("Terrain") || n.Contains("Floor") || n.Contains("Dirt")) return SurfaceKind.Dirt;
            if (n.Contains("Crystal")) return SurfaceKind.Crystal;
            if (n.Contains("Water")) return SurfaceKind.Water;
            if (n.Contains("Fur") || n.Contains("Skin") || n.Contains("Flesh")) return SurfaceKind.Flesh;
            return SurfaceKind.Rock;
        }

        public static string TapSound(SurfaceKind k)
        {
            switch (k)
            {
                case SurfaceKind.Metal: return "hand_tap_metal";
                case SurfaceKind.Wood: return "hand_tap_wood";
                case SurfaceKind.Foliage: return "hand_tap_foliage";
                case SurfaceKind.Mud:
                case SurfaceKind.Water: return "hand_tap_mud";
                case SurfaceKind.Dirt: return "hand_tap_ground";
                case SurfaceKind.Flesh: return "hand_tap_mud";
                default: return "hand_tap_rock";
            }
        }

        /// <summary>How much louder (for creatures) an impact on this surface is.</summary>
        public static float NoiseFactor(SurfaceKind k)
        {
            switch (k)
            {
                case SurfaceKind.Metal: return 1.6f;
                case SurfaceKind.Wood: return 1.15f;
                case SurfaceKind.Foliage: return 1.1f;
                case SurfaceKind.Mud: return 0.6f;
                case SurfaceKind.Dirt: return 0.75f;
                case SurfaceKind.Crystal: return 1.3f;
                default: return 1f;
            }
        }

        public static string DropSound(SurfaceKind itemKind)
        {
            switch (itemKind)
            {
                case SurfaceKind.Metal: return "item_drop_metal";
                case SurfaceKind.Wood: return "item_drop_wood";
                case SurfaceKind.Flesh:
                case SurfaceKind.Foliage: return "item_drop_soft";
                default: return "item_drop_stone";
            }
        }
    }
}
