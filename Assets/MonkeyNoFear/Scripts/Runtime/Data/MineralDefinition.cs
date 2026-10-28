using UnityEngine;

namespace MonkeyNoFear.Data
{
    public enum DepthZone { Shallow = 0, Mid = 1, Deep = 2, Anomalous = 3 }

    /// <summary>A mineable resource type: deposit behaviour, drops, sounds and where it spawns.</summary>
    [CreateAssetMenu(menuName = "Monkey No Fear/Mineral Definition", fileName = "Mineral_")]
    public class MineralDefinition : ScriptableObject
    {
        public string id;
        public string displayName;
        [Tooltip("Item dropped when a chunk breaks off.")]
        public ItemDefinition chunkItem;
        public GameObject depositPrefab;
        public GameObject wallDepositPrefab;

        [Header("Mining")]
        [Tooltip("Total damage needed to fully mine the deposit.")]
        [Min(1)] public float durability = 100f;
        [Tooltip("Minimum pickaxe tier able to damage this deposit (1-3).")]
        [Range(1, 3)] public int requiredTier = 1;
        [Tooltip("Chunk items dropped over the deposit's life.")]
        public Vector2Int dropCount = new Vector2Int(3, 5);
        [Tooltip("How loud each strike is for creatures (0-1+).")]
        public float strikeNoise = 0.55f;

        [Header("Feedback")]
        public string hitSound = "pick_hit_rock";
        public string breakSound = "ore_break";
        public string finalBreakSound = "ore_break_final";
        public Color particleColor = Color.gray;
        public Color glowColor = Color.black;
        [Tooltip("Light intensity of the deposit's own glow (0 = none).")]
        public float glowIntensity;

        [Header("Spawning weights per depth zone")]
        public float weightShallow = 1f;
        public float weightMid = 1f;
        public float weightDeep = 0f;
        public float weightAnomalous = 0f;

        public float WeightFor(DepthZone z)
        {
            switch (z)
            {
                case DepthZone.Shallow: return weightShallow;
                case DepthZone.Mid: return weightMid;
                case DepthZone.Deep: return weightDeep;
                default: return weightAnomalous;
            }
        }
    }
}
