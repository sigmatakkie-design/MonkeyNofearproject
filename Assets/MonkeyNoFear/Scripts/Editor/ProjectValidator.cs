using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Data;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>Checks that the build produced a connected game: data ↔ prefabs ↔ models ↔ sounds ↔ scene.
    /// Writes Logs/MonkeyNoFear_Validation.txt and logs every problem.</summary>
    public static class ProjectValidator
    {
        public static bool Run(bool showDialog)
        {
            var errors = new List<string>();
            var warnings = new List<string>();

            var db = AssetDatabase.LoadAssetAtPath<ItemDatabase>(MNFPaths.Data + "/ItemDatabase.asset");
            if (!db) errors.Add("ItemDatabase missing");
            else
            {
                foreach (var i in db.items)
                {
                    if (!i) { errors.Add("Null entry in ItemDatabase"); continue; }
                    if (!i.prefab) errors.Add($"Item '{i.id}' has no prefab");
                    else if (!i.prefab.GetComponent<Interaction.ItemInstance>()) errors.Add($"Item prefab for '{i.id}' lacks ItemInstance");
                }
                foreach (var m in db.minerals)
                {
                    if (!m.depositPrefab) errors.Add($"Mineral '{m.id}' has no deposit prefab");
                    if (!m.chunkItem) errors.Add($"Mineral '{m.id}' has no chunk item");
                }
                foreach (var t in db.tools) if (!t.item) errors.Add($"Tool '{t.id}' has no item");
                foreach (var s in db.startingTools) if (db.GetTool(s) == null) errors.Add($"Starting tool '{s}' not in tool list");
            }

            var shop = AssetDatabase.LoadAssetAtPath<ShopCatalog>(MNFPaths.Data + "/ShopCatalog.asset");
            if (!shop) errors.Add("ShopCatalog missing");
            else if (db)
                foreach (var e in shop.entries)
                {
                    if (e.kind == ShopEntryKind.Consumable && !db.GetItem(e.grantId)) errors.Add($"Shop entry '{e.id}' grants unknown item '{e.grantId}'");
                    if (e.kind == ShopEntryKind.Tool && db.GetTool(e.grantId) == null) errors.Add($"Shop entry '{e.id}' grants unknown tool '{e.grantId}'");
                }

            var bank = AssetDatabase.LoadAssetAtPath<SoundBank>(AudioFactory.BankPath);
            if (!bank || bank.groups.Count == 0) warnings.Add("SoundBank empty: the game will be silent");
            else foreach (var g in bank.groups) if (g.clips.Length == 0) warnings.Add($"Sound group '{g.name}' has no clips");

            foreach (var kit in KitLibrary.Kits)
                if (!MNFPaths.Exists($"{MNFPaths.Props}/{kit}.fbx")) warnings.Add($"Prop kit {kit}.fbx missing (fallback shapes used)");
            foreach (var c in new[] { "Hollowback", "Rabbit", "Falsekin", "CeilingClerk", "Borer", "LanternMourner", "Gaunt", "Boar", "Gloomrat" })
                if (!MNFPaths.Exists($"{MNFPaths.Creatures}/{c}.fbx")) warnings.Add($"Creature model {c}.fbx missing (stand-in body used)");
            foreach (var l in new[] { "Bunker", "Forest", "Mine" })
                if (!MNFPaths.Exists($"{MNFPaths.Levels}/{l}.fbx")) errors.Add($"Level {l}.fbx missing");
            if (!MNFPaths.Exists(MNFPaths.Player + "/MonkeyPlayer.fbx")) errors.Add("Player model missing");
            if (!MNFPaths.Exists(MNFPaths.WorldScene)) errors.Add("World scene not built");
            if (!AssetDatabase.LoadAssetAtPath<Object>(NavMeshBaker.DataPath)) warnings.Add("NavMesh not baked");

            var fallback = MaterialFactory.Get("MNF_Fallback");
            if (fallback)
                foreach (var guid in AssetDatabase.FindAssets("t:Prefab", new[] { MNFPaths.Prefabs }))
                {
                    var go = AssetDatabase.LoadAssetAtPath<GameObject>(AssetDatabase.GUIDToAssetPath(guid));
                    foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                        foreach (var m in r.sharedMaterials)
                            if (m == fallback) { warnings.Add($"{go.name}/{r.name} uses the fallback material"); goto nextPrefab; }
                    nextPrefab:;
                }

            var sb = new StringBuilder();
            sb.AppendLine($"MONKEY NO FEAR validation — {errors.Count} errors, {warnings.Count} warnings");
            foreach (var e in errors) { sb.AppendLine("ERROR   " + e); Debug.LogError("[MNF] " + e); }
            foreach (var w in warnings) { sb.AppendLine("WARNING " + w); Debug.LogWarning("[MNF] " + w); }
            var logDir = Path.Combine(Path.GetDirectoryName(Application.dataPath), "Logs");
            Directory.CreateDirectory(logDir);
            File.WriteAllText(Path.Combine(logDir, "MonkeyNoFear_Validation.txt"), sb.ToString());
            Debug.Log(sb.ToString());
            if (showDialog) EditorUtility.DisplayDialog("Monkey No Fear", $"{errors.Count} errors, {warnings.Count} warnings.\nDetails in the Console and Logs/MonkeyNoFear_Validation.txt", "OK");
            return errors.Count == 0;
        }
    }
}
