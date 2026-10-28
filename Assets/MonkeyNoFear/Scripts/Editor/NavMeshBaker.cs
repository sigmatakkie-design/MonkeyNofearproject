using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.AI;
using MonkeyNoFear.Core;
using MonkeyNoFear.World;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>Bakes the walkable NavMesh for creatures from the level colliders with the built-in
    /// NavMeshBuilder API and stores it as an asset that NavMeshDataLoader adds at runtime.</summary>
    public static class NavMeshBaker
    {
        public const string DataPath = MNFPaths.Generated + "/WorldNavMesh.asset";

        public static NavMeshData Bake(Transform worldRoot)
        {
            var sources = new List<NavMeshBuildSource>();
            var markups = new List<NavMeshBuildMarkup>();
            var bounds = WorldBounds(worldRoot);
            int mask = (1 << Layers.Environment) | (1 << Layers.Default) | (1 << Layers.NoClimb);
            NavMeshBuilder.CollectSources(bounds, mask, NavMeshCollectGeometry.PhysicsColliders, 0, markups, sources);
            // moving things (gate bars, elevator, carts) must not be baked in
            sources.RemoveAll(s => s.component && (s.component.GetComponentInParent<Bunker.SecurityGate>() || s.component.GetComponentInParent<Player.MovingPlatform>()
                                                    || s.component.GetComponentInParent<MinecartEvent>() || s.component.GetComponentInParent<UnstableFloor>()));

            var settings = NavMesh.GetSettingsByID(0);
            settings.agentRadius = 0.4f;
            settings.agentHeight = 1.6f;
            settings.agentClimb = 0.45f;
            settings.agentSlope = 42f;
            settings.overrideVoxelSize = true;
            settings.voxelSize = 0.2f;
            settings.overrideTileSize = true;
            settings.tileSize = 128;
            settings.minRegionArea = 4f;

            EditorUtility.DisplayProgressBar("Monkey No Fear", $"Baking NavMesh ({sources.Count} sources)...", 0.5f);
            NavMeshData data;
            try { data = NavMeshBuilder.BuildNavMeshData(settings, sources, bounds, Vector3.zero, Quaternion.identity); }
            finally { EditorUtility.ClearProgressBar(); }
            if (data == null) { Debug.LogError("[MNF] NavMesh bake failed."); return null; }
            data.name = "WorldNavMesh";
            MNFPaths.Ensure(MNFPaths.Generated);
            if (AssetDatabase.LoadAssetAtPath<NavMeshData>(DataPath)) AssetDatabase.DeleteAsset(DataPath);
            AssetDatabase.CreateAsset(data, DataPath);
            AssetDatabase.SaveAssets();
            foreach (var loader in Object.FindObjectsOfType<NavMeshDataLoader>()) { loader.data = data; EditorUtility.SetDirty(loader); }
            Debug.Log($"[MNF] NavMesh baked from {sources.Count} sources, bounds {bounds.size}.");
            return data;
        }

        static Bounds WorldBounds(Transform root)
        {
            var cols = root ? root.GetComponentsInChildren<Collider>() : Object.FindObjectsOfType<Collider>();
            if (cols.Length == 0) return new Bounds(Vector3.zero, Vector3.one * 100f);
            var b = cols[0].bounds;
            foreach (var c in cols) if (!c.isTrigger) b.Encapsulate(c.bounds);
            b.Expand(4f);
            return b;
        }
    }
}
