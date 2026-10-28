using UnityEditor;
using UnityEngine;
#if MNF_XR_MANAGEMENT
using UnityEditor.XR.Management;
using UnityEngine.XR.Management;
#endif
#if MNF_OPENXR
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features.Interactions;
#endif

namespace MonkeyNoFear.EditorTools
{
    /// <summary>
    /// Enables OpenXR for Standalone (PC VR) and Android (Quest) with the Oculus Touch interaction profile
    /// (plus Valve Index / HTC Vive profiles on PC). Compiled only when the packages from
    /// Packages/manifest.json are installed; otherwise it logs the manual steps.
    /// </summary>
    public static class XRSetup
    {
        public static void Apply()
        {
#if MNF_XR_MANAGEMENT && MNF_OPENXR
            Enable(BuildTargetGroup.Standalone);
            Enable(BuildTargetGroup.Android);
            EnableProfiles(BuildTargetGroup.Standalone, true);
            EnableProfiles(BuildTargetGroup.Android, false);
            AssetDatabase.SaveAssets();
            Debug.Log("[MNF] OpenXR enabled for Standalone and Android.");
#else
            Debug.LogWarning("[MNF] XR packages not found. Install XR Plug-in Management + OpenXR (Packages/manifest.json), then: " +
                             "Project Settings > XR Plug-in Management > tick OpenXR (PC and Android tabs) > OpenXR > add 'Oculus Touch Controller Profile'.");
#endif
        }

#if MNF_XR_MANAGEMENT && MNF_OPENXR
        static void Enable(BuildTargetGroup group)
        {
            var perTarget = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(group);
            if (perTarget == null)
            {
                // creates the settings assets the first time
                XRGeneralSettingsPerBuildTarget buildTargetSettings = null;
                EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out buildTargetSettings);
                if (buildTargetSettings == null)
                {
                    buildTargetSettings = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
                    MNFPaths.Ensure("Assets/XR");
                    AssetDatabase.CreateAsset(buildTargetSettings, "Assets/XR/XRGeneralSettingsPerBuildTarget.asset");
                    EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey, buildTargetSettings, true);
                }
                if (!buildTargetSettings.HasSettingsForBuildTarget(group)) buildTargetSettings.CreateDefaultSettingsForBuildTarget(group);
                if (!buildTargetSettings.HasManagerSettingsForBuildTarget(group)) buildTargetSettings.CreateDefaultManagerSettingsForBuildTarget(group);
                perTarget = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(group);
            }
            if (perTarget == null || perTarget.AssignedSettings == null) { Debug.LogWarning("[MNF] Could not create XR settings for " + group); return; }
            perTarget.InitManagerOnStart = true;
            UnityEditor.XR.Management.Metadata.XRPackageMetadataStore.AssignLoader(perTarget.AssignedSettings, "UnityEngine.XR.OpenXR.OpenXRLoader", group);
            EditorUtility.SetDirty(perTarget);
        }

        static void EnableProfiles(BuildTargetGroup group, bool pc)
        {
            var settings = OpenXRSettings.GetSettingsForBuildTargetGroup(group);
            if (settings == null) return;
            foreach (var f in settings.GetFeatures<OculusTouchControllerProfile>()) f.enabled = true;
            if (pc)
            {
                foreach (var f in settings.GetFeatures<ValveIndexControllerProfile>()) f.enabled = true;
                foreach (var f in settings.GetFeatures<HTCViveControllerProfile>()) f.enabled = true;
            }
            EditorUtility.SetDirty(settings);
        }
#endif
    }
}
