using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>
    /// Import rules for everything the Python/Blender pipelines produce, so re-running a generator and
    /// re-importing never needs manual Inspector work.
    /// </summary>
    public class ImportPostprocessor : AssetPostprocessor
    {
        static Dictionary<string, object> _creatureManifest;

        static Dictionary<string, object> CreatureManifest
        {
            get
            {
                if (_creatureManifest == null)
                    _creatureManifest = MiniJson.Parse(MNFPaths.ReadText(MNFPaths.Creatures + "/creatures_manifest.json")).AsObj()
                                        ?? new Dictionary<string, object>();
                return _creatureManifest;
            }
        }

        bool IsOurs => assetPath.StartsWith(MNFPaths.Root + "/");

        // ------------------------------------------------------------------ models
        void OnPreprocessModel()
        {
            if (!IsOurs) return;
            var mi = (ModelImporter)assetImporter;
            mi.globalScale = 1f;
            mi.useFileScale = true;
            mi.bakeAxisConversion = true;
            mi.importCameras = false;
            mi.importLights = false;
            mi.importBlendShapes = true;
            mi.importVisibility = false;
            mi.addCollider = false;
            mi.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            mi.materialLocation = ModelImporterMaterialLocation.InPrefab;
            mi.importTangents = ModelImporterTangents.CalculateMikk;
            mi.meshCompression = ModelImporterMeshCompression.Off;

            bool creature = assetPath.StartsWith(MNFPaths.Creatures);
            bool player = assetPath.StartsWith(MNFPaths.Player);
            bool level = assetPath.StartsWith(MNFPaths.Levels);
            mi.isReadable = level; // level meshes feed MeshColliders and the NavMesh bake
            mi.optimizeMeshPolygons = true;
            mi.optimizeMeshVertices = true;
            if (creature)
            {
                mi.animationType = ModelImporterAnimationType.Legacy;
                mi.importAnimation = true;
                mi.generateAnimations = ModelImporterGenerateAnimations.GenerateAnimations;
                mi.optimizeGameObjects = false;
            }
            else if (player)
            {
                mi.animationType = ModelImporterAnimationType.None;
                mi.importAnimation = false;
                mi.optimizeGameObjects = false;
            }
            else
            {
                mi.animationType = ModelImporterAnimationType.None;
                mi.importAnimation = false;
            }
            // lightmap UVs for level geometry in case someone bakes lighting later
            mi.generateSecondaryUV = level;
        }

        void OnPreprocessAnimation()
        {
            if (!assetPath.StartsWith(MNFPaths.Creatures)) return;
            var mi = (ModelImporter)assetImporter;
            var name = Path.GetFileNameWithoutExtension(assetPath);
            var info = CreatureManifest.Get(name).AsObj();
            var clipsInfo = info?.Get("clips").AsObj();
            var defaults = mi.defaultClipAnimations;
            var clips = new List<ModelImporterClipAnimation>();
            foreach (var c in defaults)
            {
                var clean = c.takeName.Contains("|") ? c.takeName.Substring(c.takeName.LastIndexOf('|') + 1) : c.takeName;
                c.name = clean;
                var ci = clipsInfo?.Get(clean).AsObj();
                bool loop = ci != null ? ci.GetBool("loop", true) : true;
                c.loopTime = loop;
                c.wrapMode = loop ? WrapMode.Loop : WrapMode.ClampForever;
                clips.Add(c);
            }
            mi.clipAnimations = clips.ToArray();
        }

        // ------------------------------------------------------------------ textures
        void OnPreprocessTexture()
        {
            if (!IsOurs) return;
            var ti = (TextureImporter)assetImporter;
            var n = Path.GetFileNameWithoutExtension(assetPath);
            // Art direction (Gorilla Tag fan-game look): chunky point-filtered low-res surfaces. Sign/decal atlases keep
            // enough resolution for their lettering; particles and screens stay smooth.
            bool smooth = n.StartsWith("fx_") || n.StartsWith("screen_") || n == "vignette";
            int size = n.Contains("atlas") ? 512 : smooth ? 256 : assetPath.StartsWith(MNFPaths.Player) ? 256 : 128;
            ti.mipmapEnabled = true;
            ti.maxTextureSize = size;
            ti.filterMode = smooth ? FilterMode.Bilinear : FilterMode.Point;
            ti.anisoLevel = smooth ? 1 : 0;
            ti.textureCompression = TextureImporterCompression.Compressed;
            if (n.EndsWith("_N"))
            {
                ti.textureType = TextureImporterType.NormalMap;
                ti.sRGBTexture = false;
            }
            else if (n.EndsWith("_M"))
            {
                ti.textureType = TextureImporterType.Default;
                ti.sRGBTexture = false;
                ti.alphaSource = TextureImporterAlphaSource.FromInput;
            }
            else
            {
                ti.textureType = TextureImporterType.Default;
                ti.sRGBTexture = true;
                ti.alphaSource = TextureImporterAlphaSource.FromInput;
                bool cutout = n.StartsWith("foliage") || n.StartsWith("fern") || n.StartsWith("grass") || n.StartsWith("metal_grate") || n.StartsWith("decals");
                ti.alphaIsTransparency = cutout || n.StartsWith("fx_") || n.StartsWith("screen_");
            }
            if (n.StartsWith("fx_") || n.Contains("atlas")) ti.wrapMode = TextureWrapMode.Clamp;
            else ti.wrapMode = TextureWrapMode.Repeat;
            if (assetPath.StartsWith(MNFPaths.Player)) ti.mipmapEnabled = false;

            var android = ti.GetPlatformTextureSettings("Android");
            android.overridden = true;
            android.maxTextureSize = size;
            android.format = TextureImporterFormat.ASTC_6x6;
            ti.SetPlatformTextureSettings(android);
        }

        // ------------------------------------------------------------------ audio
        void OnPreprocessAudio()
        {
            if (!IsOurs) return;
            var ai = (AudioImporter)assetImporter;
            var n = Path.GetFileNameWithoutExtension(assetPath);
            bool stereo = n.Contains("_bed") || n.StartsWith("sting_") || n.StartsWith("tension_drone") || n.StartsWith("amb_forest_insects");
            bool longClip = n.Contains("_loop") || n.Contains("_bed") || n.StartsWith("sting_");
            ai.forceToMono = !stereo;
            ai.loadInBackground = longClip;
            var s = ai.defaultSampleSettings;
            s.loadType = longClip ? AudioClipLoadType.CompressedInMemory : AudioClipLoadType.DecompressOnLoad;
            s.compressionFormat = longClip ? AudioCompressionFormat.Vorbis : AudioCompressionFormat.ADPCM;
            s.quality = 0.5f;
            s.sampleRateSetting = AudioSampleRateSetting.PreserveSampleRate;
            ai.defaultSampleSettings = s;
        }

        public static void ClearCache() { _creatureManifest = null; }
    }
}
