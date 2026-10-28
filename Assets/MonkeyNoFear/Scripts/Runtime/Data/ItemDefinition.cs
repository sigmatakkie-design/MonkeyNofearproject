using UnityEngine;

namespace MonkeyNoFear.Data
{
    public enum ItemCategory { Mineral, Food, Tool, Consumable, Valuable, Lore }

    /// <summary>Static data for anything the player can carry. Physical instances carry an ItemInstance that
    /// points back to one of these.</summary>
    [CreateAssetMenu(menuName = "Monkey No Fear/Item Definition", fileName = "Item_")]
    public class ItemDefinition : ScriptableObject
    {
        [Tooltip("Stable id used in save files. Never change after shipping.")]
        public string id;
        public string displayName;
        [TextArea] public string description;
        public ItemCategory category;
        [Tooltip("Physical prefab spawned in the world (must contain an ItemInstance).")]
        public GameObject prefab;

        [Header("Economy")]
        public bool sellable = true;
        [Min(0)] public int sellValue = 5;
        [Tooltip("Can be put in the backpack / storage locker.")]
        public bool storable = true;

        [Header("Physics")]
        [Min(0.01f)] public float mass = 0.5f;
        public SurfaceKind dropSurface = SurfaceKind.Rock;

        [Header("Food")]
        [Tooltip("Vigor restored when eaten (0 = not edible).")]
        public float foodVigor;
        public float foodHeal;

        [Header("Display")]
        public Color terminalColor = new Color(0.8f, 0.9f, 0.8f);
        [Tooltip("Rarity tier 0-4, shown on the terminal and used by the scanner.")]
        [Range(0, 4)] public int rarity;

        public bool IsEdible => foodVigor > 0f || foodHeal > 0f;
        public string ColorTag => "#" + ColorUtility.ToHtmlStringRGB(terminalColor);
    }

    public enum SurfaceKind { Rock, Dirt, Wood, Metal, Foliage, Mud, Water, Flesh, Concrete, Crystal }
}
