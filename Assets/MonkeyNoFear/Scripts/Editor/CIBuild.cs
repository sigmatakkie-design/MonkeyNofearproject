using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>
    /// Unattended build for CI (GitHub Actions / GameCI) or any batch-mode Unity:
    ///   Unity -batchmode -quit -projectPath . -buildTarget StandaloneWindows64 -executeMethod MonkeyNoFear.EditorTools.CIBuild.Build -customBuildPath Builds/MonkeyNoFear.exe
    /// Runs the full game builder (settings, materials, data, prefabs, world scene, NavMesh), then builds the player
    /// for the active build target. Exits with code 1 if anything fails so the CI job goes red.
    /// </summary>
    public static class CIBuild
    {
        public static void Build()
        {
            try
            {
                MNFMenu.BuildAllBatch();
                var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
                if (scenes.Length == 0) throw new Exception("No scenes in the build settings: the world scene was not created.");

                var target = EditorUserBuildSettings.activeBuildTarget;
                string path = Arg("-customBuildPath") ?? DefaultPath(target);
                Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path)));
                var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = scenes,
                    locationPathName = path,
                    target = target,
                    options = BuildOptions.None,
                });
                Debug.Log($"[MNF] Player build {report.summary.result}: {path} ({report.summary.totalSize / (1024 * 1024)} MB, {report.summary.totalErrors} errors)");
                if (report.summary.result != BuildResult.Succeeded) EditorApplication.Exit(1);
            }
            catch (Exception e)
            {
                Debug.LogError("[MNF] CI build failed: " + e);
                EditorApplication.Exit(1);
            }
        }

        static string DefaultPath(BuildTarget t) =>
            t == BuildTarget.Android ? "Builds/Android/MonkeyNoFear.apk" : "Builds/Windows/MonkeyNoFear.exe";

        static string Arg(string name)
        {
            var args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }
    }
}
