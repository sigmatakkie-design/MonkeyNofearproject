using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>
    /// "Monkey No Fear" menu. "Build Game (Full)" runs every step in order; each step can also be run alone.
    /// Batch mode: Unity -batchmode -projectPath . -executeMethod MonkeyNoFear.EditorTools.MNFMenu.BuildAllBatch -quit
    /// </summary>
    public static class MNFMenu
    {
        [MenuItem("Monkey No Fear/Build Game (Full)", priority = 0)]
        public static void BuildAll()
        {
            try
            {
                Step("Project settings", 0.05f); ProjectSetup.Apply();
                Step("Reimporting assets", 0.1f); Reimport();
                Step("Materials", 0.2f); MaterialFactory.BuildAll(); MaterialFactory.RemapModelMaterials();
                Step("Sound bank", 0.3f); AudioFactory.Build();
                Step("Data", 0.35f); DataFactory.BuildAll(false);
                Step("Item prefabs", 0.45f); KitLibrary.Refresh(); PrefabFactory.BuildItems();
                Step("Deposit prefabs", 0.5f); PrefabFactory.BuildDeposits();
                Step("Prop prefabs", 0.55f); PrefabFactory.BuildProps();
                Step("Stations", 0.6f); PrefabFactory.BuildStations();
                Step("Creatures", 0.65f); PrefabFactory.BuildCreatures();
                Step("Player rig + FX", 0.7f); PrefabFactory.BuildPlayerRig(); PrefabFactory.BuildFX();
                Step("Assembling world + NavMesh", 0.8f); LevelAssembler.Build(true);
                Step("Validating", 0.95f); ProjectValidator.Run(false);
            }
            finally { EditorUtility.ClearProgressBar(); }
            Debug.Log("[MNF] BUILD COMPLETE. Press Play (desktop debug controls) or put on a headset.");
        }

        public static void BuildAllBatch()
        {
            BuildAll();
            AssetDatabase.SaveAssets();
        }

        static void Step(string what, float p) => EditorUtility.DisplayProgressBar("Monkey No Fear", what, p);

        static void Reimport()
        {
            ImportPostprocessor.ClearCache();
            foreach (var dir in new[] { MNFPaths.Models })
                foreach (var guid in AssetDatabase.FindAssets("t:Model", new[] { dir }))
                    AssetDatabase.ImportAsset(AssetDatabase.GUIDToAssetPath(guid), ImportAssetOptions.ForceUpdate);
            AssetDatabase.Refresh();
        }

        [MenuItem("Monkey No Fear/Steps/1 Project Settings")] static void M1() => ProjectSetup.Apply();
        [MenuItem("Monkey No Fear/Steps/2 Materials")] static void M2() { MaterialFactory.BuildAll(); MaterialFactory.RemapModelMaterials(); }
        [MenuItem("Monkey No Fear/Steps/3 Sound Bank")] static void M3() => AudioFactory.Build();
        [MenuItem("Monkey No Fear/Steps/4 Data (keep edits)")] static void M4() => DataFactory.BuildAll(false);
        [MenuItem("Monkey No Fear/Steps/4b Data (reset to defaults)")] static void M4b() { if (EditorUtility.DisplayDialog("Reset data", "Overwrite all items, minerals, shop, creature and atmosphere values with the defaults?", "Reset", "Cancel")) DataFactory.BuildAll(true); }
        [MenuItem("Monkey No Fear/Steps/5 Prefabs")] static void M5() { KitLibrary.Refresh(); PrefabFactory.BuildItems(); PrefabFactory.BuildDeposits(); PrefabFactory.BuildProps(); PrefabFactory.BuildStations(); PrefabFactory.BuildCreatures(); PrefabFactory.BuildPlayerRig(); PrefabFactory.BuildFX(); }
        [MenuItem("Monkey No Fear/Steps/6 Assemble World")] static void M6() => LevelAssembler.Build(true);
        [MenuItem("Monkey No Fear/Steps/7 Bake NavMesh Only")] static void M7() => NavMeshBaker.Bake(GameObject.Find("World") ? GameObject.Find("World").transform : null);

        [MenuItem("Monkey No Fear/Validate Project")] static void Validate() => ProjectValidator.Run(true);

        [MenuItem("Monkey No Fear/Open World Scene")]
        static void OpenWorld()
        {
            if (File.Exists(MNFPaths.WorldScene)) EditorSceneManager.OpenScene(MNFPaths.WorldScene);
            else if (EditorUtility.DisplayDialog("Monkey No Fear", "The world has not been built yet. Build it now?", "Build", "Cancel")) BuildAll();
        }

        [MenuItem("Monkey No Fear/Delete Save File")]
        static void DeleteSave()
        {
            var path = Path.Combine(Application.persistentDataPath, Core.SaveSystem.FileName);
            if (File.Exists(path)) File.Delete(path);
            if (File.Exists(path + ".bak")) File.Delete(path + ".bak");
            Debug.Log("[MNF] Save deleted: " + path);
        }
    }

    /// <summary>Offers to build the game the first time the project is opened.</summary>
    [InitializeOnLoad]
    static class FirstRunPrompt
    {
        static FirstRunPrompt()
        {
            EditorApplication.delayCall += () =>
            {
                if (Application.isBatchMode || File.Exists(MNFPaths.WorldScene) || SessionState.GetBool("MNF_Prompted", false)) return;
                SessionState.SetBool("MNF_Prompted", true);
                if (EditorUtility.DisplayDialog("MONKEY NO FEAR", "The game world has not been built in this project yet.\n\nRun 'Monkey No Fear > Build Game (Full)' now? (a few minutes)", "Build now", "Later"))
                    MNFMenu.BuildAll();
            };
        }
    }
}
