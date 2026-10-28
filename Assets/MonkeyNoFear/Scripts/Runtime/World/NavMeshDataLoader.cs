using UnityEngine;
using UnityEngine.AI;

namespace MonkeyNoFear.World
{
    /// <summary>Adds the NavMesh baked by the editor builder (a NavMeshData asset) at runtime. Uses only
    /// the built-in AI module, so no navigation package is required.</summary>
    [DefaultExecutionOrder(-90)]
    public class NavMeshDataLoader : MonoBehaviour
    {
        public NavMeshData data;
        NavMeshDataInstance _instance;

        void OnEnable()
        {
            if (!data) { Debug.LogWarning("[NavMesh] No baked data — creatures cannot path. Run 'Monkey No Fear > Bake NavMesh'."); return; }
            _instance = NavMesh.AddNavMeshData(data);
        }

        void OnDisable()
        {
            if (_instance.valid) _instance.Remove();
        }
    }
}
