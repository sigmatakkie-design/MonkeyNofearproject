using UnityEngine;

namespace MonkeyNoFear.Core
{
    /// <summary>
    /// Physics layer layout. The editor ProjectSetup step writes these names into the TagManager and
    /// configures the collision matrix, so the numbers here must stay in sync with ProjectSetup.LayerNames.
    /// </summary>
    public static class Layers
    {
        public const int Default = 0;
        public const int Player = 8;        // body capsule
        public const int PlayerHand = 9;    // kinematic hand spheres (push loose props)
        public const int Item = 10;         // loose grabbable items
        public const int HeldItem = 11;     // items currently in a hand (ignore the player)
        public const int Creature = 12;
        public const int Trigger = 13;      // zones, sensors
        public const int Interactable = 14; // buttons, levers (hands press instead of anchoring)
        public const int Environment = 15;  // static level geometry (climbable)
        public const int NoClimb = 16;      // slippery geometry: blocks but hands slide
        public const int Foliage = 17;      // bush trigger volumes: soft vision cover

        public static readonly string[] Names =
        {
            null, null, null, null, null, null, null, null,
            "Player", "PlayerHand", "Item", "HeldItem", "Creature", "Trigger", "Interactable",
            "Environment", "NoClimb", "Foliage"
        };

        /// <summary>Solid world for the player's body and hands.</summary>
        public static readonly int SolidWorld = (1 << Default) | (1 << Environment) | (1 << NoClimb);

        /// <summary>Surfaces hands can anchor to.</summary>
        public static readonly int Climbable = (1 << Default) | (1 << Environment);

        /// <summary>What blocks sight and muffles sound.</summary>
        public static readonly int Occluders = (1 << Default) | (1 << Environment) | (1 << NoClimb);

        public static readonly int Grabbables = (1 << Item) | (1 << Interactable);

        public static bool InMask(int layer, int mask) => (mask & (1 << layer)) != 0;

        public static void SetLayerRecursive(GameObject go, int layer)
        {
            go.layer = layer;
            foreach (Transform t in go.transform) SetLayerRecursive(t.gameObject, layer);
        }
    }
}
