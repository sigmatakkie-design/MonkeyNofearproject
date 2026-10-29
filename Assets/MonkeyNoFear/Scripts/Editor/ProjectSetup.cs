using UnityEditor;
using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>Project-wide settings the game depends on: physics layers and collision matrix, physics
    /// timing, quality levels tuned for standalone VR, player settings (Linear, Android/Quest), and the
    /// input backend. Safe to run repeatedly.</summary>
    public static class ProjectSetup
    {
        public static void Apply()
        {
            SetupLayers();
            SetupCollisionMatrix();
            SetupPhysics();
            SetupQuality();
            SetupPlayer();
            XRSetup.Apply();
            AssetDatabase.SaveAssets();
            Debug.Log("[MNF] Project settings applied.");
        }

        static void SetupLayers()
        {
            var tagManager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layers = tagManager.FindProperty("layers");
            for (int i = 8; i < Layers.Names.Length; i++)
            {
                var name = Layers.Names[i];
                if (string.IsNullOrEmpty(name)) continue;
                var el = layers.GetArrayElementAtIndex(i);
                if (el.stringValue != name)
                {
                    if (!string.IsNullOrEmpty(el.stringValue)) Debug.LogWarning($"[MNF] Layer {i} '{el.stringValue}' renamed to '{name}'");
                    el.stringValue = name;
                }
            }
            tagManager.ApplyModifiedProperties();
        }

        static void SetupCollisionMatrix()
        {
            // start from "everything collides", then cut the pairs that must not interact
            for (int a = 0; a < 32; a++) for (int b = 0; b < 32; b++) Physics.IgnoreLayerCollision(a, b, false);
            void Ignore(int a, int b) => Physics.IgnoreLayerCollision(a, b, true);
            Ignore(Layers.Player, Layers.PlayerHand);
            Ignore(Layers.Player, Layers.HeldItem);
            Ignore(Layers.PlayerHand, Layers.HeldItem);
            Ignore(Layers.PlayerHand, Layers.Item);        // the palm must not shove items it reaches for (grabs use overlap queries)
            Ignore(Layers.PlayerHand, Layers.PlayerHand);
            Ignore(Layers.PlayerHand, Layers.Environment); // hands are solved kinematically by PhysicsHand
            Ignore(Layers.PlayerHand, Layers.Default);
            Ignore(Layers.PlayerHand, Layers.NoClimb);
            Ignore(Layers.PlayerHand, Layers.Creature);
            Ignore(Layers.Player, Layers.Item);            // the body walks through loose items instead of kicking them
            Ignore(Layers.Player, Layers.Creature);        // creatures resolve contact with attacks, not shoves
            for (int i = 0; i < 32; i++)
            {
                Ignore(Layers.Trigger, i);                 // zones never collide physically
                Ignore(Layers.Foliage, i);
                Ignore(Layers.Interactable, i);
            }
            Physics.IgnoreLayerCollision(Layers.Interactable, Layers.Item, false); // items rest on levers/buttons housings
        }

        static void SetupPhysics()
        {
            Time.fixedDeltaTime = 1f / 72f;
            Physics.defaultSolverIterations = 8;
            Physics.defaultSolverVelocityIterations = 2;
            Physics.autoSyncTransforms = false;
            Physics.queriesHitBackfaces = false;
            Physics.defaultContactOffset = 0.01f;
        }

        static void SetupQuality()
        {
            var names = QualitySettings.names;
            int current = QualitySettings.GetQualityLevel();
            for (int i = 0; i < names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                bool high = i >= names.Length - 2;
                QualitySettings.pixelLightCount = high ? 4 : 2;
                QualitySettings.shadows = ShadowQuality.HardOnly;
                QualitySettings.shadowDistance = high ? 35f : 20f;
                QualitySettings.shadowCascades = high ? 2 : 1;
                QualitySettings.shadowResolution = high ? ShadowResolution.Medium : ShadowResolution.Low;
                QualitySettings.antiAliasing = 4;
                QualitySettings.anisotropicFiltering = AnisotropicFiltering.Enable;
                QualitySettings.softParticles = false;
                QualitySettings.realtimeReflectionProbes = false;
                QualitySettings.billboardsFaceCameraPosition = true;
                QualitySettings.vSyncCount = 0;
                QualitySettings.lodBias = high ? 1.5f : 1f;
                QualitySettings.skinWeights = SkinWeights.TwoBones;
            }
            QualitySettings.SetQualityLevel(current, true);
        }

        static void SetupPlayer()
        {
            PlayerSettings.companyName = "Monkey No Fear";
            PlayerSettings.productName = "MONKEY NO FEAR";
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.stereoRenderingPath = StereoRenderingPath.Instancing;
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel29;
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { UnityEngine.Rendering.GraphicsDeviceType.OpenGLES3 });
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "com.monkeynofear.game");
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Standalone, "com.monkeynofear.game");
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
            PlayerSettings.runInBackground = true;
            // "Both" input backends: the XR plug-ins bring the Input System package, the desktop debug
            // driver uses the legacy Input Manager.
            var ps = new SerializedObject(Unsupported.GetSerializedAssetInterfaceSingleton("PlayerSettings"));
            var input = ps.FindProperty("activeInputHandler");
            if (input != null && input.intValue != 2) { input.intValue = 2; ps.ApplyModifiedProperties(); Debug.Log("[MNF] Active Input Handling set to Both (editor restart may be requested)."); }
        }
    }
}
