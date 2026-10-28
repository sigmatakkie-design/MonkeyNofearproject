using System.IO;
using UnityEditor;
using UnityEngine;

namespace MonkeyNoFear.EditorTools
{
    public static class MNFPaths
    {
        public const string Root = "Assets/MonkeyNoFear";
        public const string Textures = Root + "/Art/Textures";
        public const string Models = Root + "/Art/Models";
        public const string Player = Models + "/Player";
        public const string Creatures = Models + "/Creatures";
        public const string Props = Models + "/Props";
        public const string Levels = Models + "/Levels";
        public const string Audio = Root + "/Audio";
        public const string Materials = Root + "/Materials";
        public const string Data = Root + "/Data";
        public const string Prefabs = Root + "/Prefabs";
        public const string Scenes = Root + "/Scenes";
        public const string Shaders = Root + "/Shaders";
        public const string Generated = Root + "/Generated";
        public const string WorldScene = Scenes + "/MonkeyNoFear_World.unity";

        public static void Ensure(string assetFolder)
        {
            if (AssetDatabase.IsValidFolder(assetFolder)) return;
            var parent = Path.GetDirectoryName(assetFolder).Replace('\\', '/');
            Ensure(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(assetFolder));
        }

        public static string ReadText(string assetPath)
        {
            var full = Path.Combine(Path.GetDirectoryName(Application.dataPath), assetPath);
            return File.Exists(full) ? File.ReadAllText(full) : null;
        }

        public static bool Exists(string assetPath)
        {
            var full = Path.Combine(Path.GetDirectoryName(Application.dataPath), assetPath);
            return File.Exists(full);
        }

        /// <summary>Create or overwrite a ScriptableObject asset, keeping its GUID if it exists.</summary>
        public static T CreateOrReplace<T>(string path) where T : ScriptableObject
        {
            var existing = AssetDatabase.LoadAssetAtPath<T>(path);
            if (existing) return existing;
            Ensure(Path.GetDirectoryName(path).Replace('\\', '/'));
            var so = ScriptableObject.CreateInstance<T>();
            AssetDatabase.CreateAsset(so, path);
            return so;
        }
    }
}
