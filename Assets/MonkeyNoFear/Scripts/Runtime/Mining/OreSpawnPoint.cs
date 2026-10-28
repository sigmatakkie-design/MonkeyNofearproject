using UnityEngine;
using MonkeyNoFear.Data;

namespace MonkeyNoFear.Mining
{
    /// <summary>Authored candidate location for a deposit (placed by the level builder).</summary>
    public class OreSpawnPoint : MonoBehaviour
    {
        public DepthZone zone;
        public bool wallMounted;
        [Range(0, 1)] public float activeChance = 0.65f;
        [HideInInspector] public OreDeposit current;

        void OnDrawGizmos()
        {
            Gizmos.color = zone == DepthZone.Shallow ? Color.gray : zone == DepthZone.Mid ? new Color(1f, 0.5f, 0.2f) : zone == DepthZone.Deep ? Color.cyan : Color.magenta;
            Gizmos.DrawWireCube(transform.position + Vector3.up * 0.4f, Vector3.one * 0.8f);
        }
    }
}
