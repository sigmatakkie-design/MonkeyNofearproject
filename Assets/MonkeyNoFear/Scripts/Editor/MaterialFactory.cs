using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>
    /// Creates one Unity material per catalog name (Docs/ASSET_SPEC.md §2) from the generated texture
    /// sets, then remaps every model's embedded materials onto them by name. Missing textures degrade to
    /// tinted flat materials rather than failing.
    /// </summary>
    public static class MaterialFactory
    {
        enum Kind { Std, Cutout, Fade, Tri, Terrain, Foliage, Emissive, Flat, Water, Decal, Particle, ParticleAdd, Overlay }

        class Def
        {
            public string name, set; public Kind kind; public Color tint = Color.white;
            public float smooth = -1f, metal = -1f, wet, emission = 1f; public Color emissionColor = Color.black;
            public bool topMoss;
            public Def(string n, Kind k, string s = null) { name = n; kind = k; set = s; }
        }

        static readonly List<Def> Catalog = new List<Def>();
        static readonly Dictionary<string, Material> Cache = new Dictionary<string, Material>();

        static Def D(string n, Kind k, string s = null) { var d = new Def(n, k, s); Catalog.Add(d); return d; }

        static void BuildCatalog()
        {
            Catalog.Clear();
            D("MNF_ConcreteWall", Kind.Std, "concrete_wall");
            D("MNF_ConcreteFloor", Kind.Std, "concrete_floor");
            D("MNF_MetalGrate", Kind.Cutout, "metal_grate");
            D("MNF_MetalDiamond", Kind.Std, "metal_diamond");
            D("MNF_MetalRusted", Kind.Std, "metal_rusted");
            D("MNF_MetalPainted_Green", Kind.Std, "metal_painted").tint = new Color(0.36f, 0.46f, 0.34f);
            D("MNF_MetalPainted_Gray", Kind.Std, "metal_painted").tint = new Color(0.48f, 0.5f, 0.52f);
            D("MNF_MetalPainted_Yellow", Kind.Std, "metal_painted").tint = new Color(0.86f, 0.66f, 0.14f);
            D("MNF_MetalPainted_Red", Kind.Std, "metal_painted").tint = new Color(0.62f, 0.13f, 0.1f);
            D("MNF_MetalBare", Kind.Std, "metal_bare");
            D("MNF_Hazard", Kind.Std, "hazard_stripes");
            D("MNF_Rubber", Kind.Std, "rubber");
            D("MNF_Plastic_Yellow", Kind.Std, "plastic").tint = new Color(0.95f, 0.74f, 0.16f);
            D("MNF_Plastic_Orange", Kind.Std, "plastic").tint = new Color(0.95f, 0.42f, 0.1f);
            D("MNF_Plastic_Black", Kind.Std, "plastic").tint = new Color(0.13f, 0.13f, 0.14f);
            D("MNF_Plastic_Gray", Kind.Std, "plastic").tint = new Color(0.52f, 0.53f, 0.55f);
            foreach (var w in new[] { "Crate", "Planks", "Rotten", "Beam", "Handle" }) D("MNF_Wood" + w, Kind.Std, "wood_" + w.ToLowerInvariant());
            D("MNF_BarkPine", Kind.Std, "bark_pine");
            D("MNF_BarkDead", Kind.Std, "bark_dead");
            D("MNF_FoliagePine", Kind.Foliage, "foliage_pine");
            D("MNF_FoliageLeaf", Kind.Foliage, "foliage_leaf");
            D("MNF_Fern", Kind.Foliage, "fern");
            D("MNF_Grass", Kind.Foliage, "grass");
            D("MNF_ForestFloor", Kind.Std, "forest_floor");
            D("MNF_Mud", Kind.Std, "mud");
            D("MNF_Moss", Kind.Std, "moss");
            D("MNF_Terrain", Kind.Terrain);
            D("MNF_RockDry", Kind.Std, "rock_dry");
            D("MNF_RockWet", Kind.Std, "rock_wet");
            D("MNF_RockMine", Kind.Std, "rock_mine");
            D("MNF_RockDry_Tri", Kind.Tri, "rock_dry").topMoss = true;
            D("MNF_RockWet_Tri", Kind.Tri, "rock_wet").wet = 0.5f;
            D("MNF_RockMine_Tri", Kind.Tri, "rock_mine").wet = 0.15f;
            D("MNF_OreIron", Kind.Std, "ore_iron");
            D("MNF_OreCopper", Kind.Std, "ore_copper");
            var cr = D("MNF_Crystal", Kind.Std, "crystal"); cr.emissionColor = new Color(0.35f, 0.85f, 1f); cr.emission = 1.6f;
            D("MNF_Blackstone", Kind.Std, "blackstone");
            var an = D("MNF_Anomalous", Kind.Std, "anomalous"); an.emissionColor = new Color(1f, 0.22f, 0.12f); an.emission = 1.4f;
            foreach (var f in new[] { "FurRotten:fur_rotten", "SkinDecayed:skin_decayed", "FurRabbit:fur_rabbit", "FurRabbitMangy:fur_rabbit_mangy",
                                      "FurBoar:fur_boar", "FurDark:fur_dark", "MineralCrust:mineral_crust", "MournerSkin:mourner_skin",
                                      "FabricCanvas:fabric_canvas", "FabricBlanket:fabric_blanket", "Rope:rope", "Paper:paper", "Meat:meat", "Flesh:flesh" })
            {
                var p = f.Split(':');
                D("MNF_" + p[0], Kind.Std, p[1]);
            }
            Flat("MNF_Teeth", new Color(0.78f, 0.73f, 0.58f), 0.45f);
            Flat("MNF_Gums", new Color(0.24f, 0.05f, 0.06f), 0.65f);
            Flat("MNF_Nails", new Color(0.52f, 0.47f, 0.35f), 0.4f);
            Flat("MNF_EyeWet", new Color(0.01f, 0.01f, 0.012f), 0.97f);
            Flat("MNF_EyeClouded", new Color(0.62f, 0.67f, 0.71f), 0.75f);
            Emissive("MNF_EyeGlint", new Color(1f, 0.92f, 0.65f), 0.5f);
            Emissive("MNF_MournerGlow", new Color(0.72f, 0.85f, 0.32f), 1.6f);
            Emissive("MNF_BulbWarm", new Color(1f, 0.74f, 0.42f), 2.2f);
            Emissive("MNF_BulbCold", new Color(0.75f, 0.9f, 1f), 2.2f);
            Emissive("MNF_BulbRed", new Color(1f, 0.1f, 0.06f), 2.2f);
            Emissive("MNF_BulbGreen", new Color(0.3f, 1f, 0.42f), 2.2f);
            var g = D("MNF_Glass", Kind.Fade); g.tint = new Color(0.62f, 0.66f, 0.62f, 0.28f); g.smooth = 0.92f;
            var sc = D("MNF_Screen", Kind.Emissive, "screen_scanlines"); sc.tint = new Color(0.01f, 0.03f, 0.015f); sc.emissionColor = new Color(0.04f, 0.12f, 0.05f); sc.smooth = 0.9f;
            D("MNF_Signs", Kind.Std, "signs_atlas");
            D("MNF_Decals", Kind.Decal, "decals_atlas");
            D("MNF_Water", Kind.Water, "water");
            D("MNF_Player_Fur", Kind.Std, "player_fur").smooth = 0.1f;
            D("MNF_Player_Face", Kind.Std, "player_face").smooth = 0.15f;
            Flat("MNF_Player_Dark", new Color(0.03f, 0.03f, 0.03f), 0.3f);
            Flat("MNF_Silhouette", new Color(0.015f, 0.015f, 0.017f), 0.05f);
            Flat("MNF_Fallback", new Color(0.5f, 0.5f, 0.5f), 0.2f);
            // particles & overlays
            D("MNF_FX_Dust", Kind.Particle, "fx_dust");
            D("MNF_FX_Smoke", Kind.Particle, "fx_smoke");
            D("MNF_FX_Fog", Kind.Particle, "fx_fog");
            D("MNF_FX_Leaf", Kind.Particle, "fx_leaf");
            D("MNF_FX_Debris", Kind.Particle, "fx_debris");
            D("MNF_FX_Drip", Kind.Particle, "fx_drip");
            D("MNF_FX_Spark", Kind.ParticleAdd, "fx_spark");
            D("MNF_FX_Glow", Kind.ParticleAdd, "fx_glow");
            D("MNF_Overlay", Kind.Overlay);
            D("MNF_Vignette", Kind.Overlay, "vignette");
        }

        static void Flat(string n, Color c, float smooth) { var d = D(n, Kind.Flat); d.tint = c; d.smooth = smooth; }
        static void Emissive(string n, Color c, float intensity) { var d = D(n, Kind.Emissive); d.tint = c * 0.3f; d.emissionColor = c; d.emission = intensity; d.smooth = 0.6f; }

        // ------------------------------------------------------------------ API
        public static Material Get(string name)
        {
            if (Cache.TryGetValue(name, out var m) && m) return m;
            m = AssetDatabase.LoadAssetAtPath<Material>($"{MNFPaths.Materials}/{name}.mat");
            if (m) Cache[name] = m;
            return m;
        }

        public static Material GetOrFallback(string name) => Get(name) ?? Get("MNF_Fallback");

        public static void BuildAll()
        {
            BuildCatalog();
            Cache.Clear();
            MNFPaths.Ensure(MNFPaths.Materials);
            GenerateVignetteTexture();
            int n = 0;
            foreach (var d in Catalog) { Build(d); n++; }
            AssetDatabase.SaveAssets();
            Debug.Log($"[MNF] Materials: {n} built");
        }

        static Texture2D Tex(string set, string suffix)
        {
            if (string.IsNullOrEmpty(set)) return null;
            string[] dirs = { MNFPaths.Textures, MNFPaths.Player };
            foreach (var dir in dirs)
            {
                var t = AssetDatabase.LoadAssetAtPath<Texture2D>($"{dir}/{set}{suffix}.png");
                if (t) return t;
            }
            return null;
        }

        static Material Build(Def d)
        {
            string path = $"{MNFPaths.Materials}/{d.name}.mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            Shader sh = ShaderFor(d.kind);
            if (!m) { m = new Material(sh) { name = d.name }; AssetDatabase.CreateAsset(m, path); }
            else m.shader = sh;
            m.enableInstancing = true;

            var albedo = Tex(d.set, "_A") ?? Tex(d.set, "");
            var normal = Tex(d.set, "_N");
            var mask = Tex(d.set, "_M");
            var emis = Tex(d.set, "_E");

            switch (d.kind)
            {
                case Kind.Std:
                case Kind.Cutout:
                case Kind.Fade:
                case Kind.Flat:
                case Kind.Emissive:
                    SetupStandard(m, d, albedo, normal, mask, emis);
                    break;
                case Kind.Tri:
                    m.SetTexture("_MainTex", albedo); m.SetTexture("_BumpMap", normal); m.SetTexture("_MaskMap", mask);
                    m.SetFloat("_Scale", 3f);
                    m.SetFloat("_Wetness", d.wet);
                    if (d.topMoss)
                    {
                        m.SetFloat("_UseTop", 1f); m.EnableKeyword("_TOPLAYER");
                        m.SetTexture("_TopTex", Tex("moss", "_A")); m.SetTexture("_TopBump", Tex("moss", "_N"));
                        m.SetFloat("_TopAmount", 0.3f);
                    }
                    break;
                case Kind.Terrain:
                    m.SetTexture("_BaseTex", Tex("forest_floor", "_A")); m.SetTexture("_BaseBump", Tex("forest_floor", "_N")); m.SetTexture("_BaseMask", Tex("forest_floor", "_M"));
                    m.SetTexture("_MudTex", Tex("mud", "_A")); m.SetTexture("_MudBump", Tex("mud", "_N")); m.SetTexture("_MudMask", Tex("mud", "_M"));
                    m.SetTexture("_MossTex", Tex("moss", "_A")); m.SetTexture("_MossBump", Tex("moss", "_N"));
                    m.SetTexture("_RockTex", Tex("rock_dry", "_A")); m.SetTexture("_RockBump", Tex("rock_dry", "_N")); m.SetTexture("_RockMask", Tex("rock_dry", "_M"));
                    break;
                case Kind.Foliage:
                    m.SetTexture("_MainTex", albedo); m.SetTexture("_BumpMap", normal);
                    m.SetFloat("_Cutoff", 0.42f);
                    m.SetFloat("_WindStrength", d.name.Contains("Grass") || d.name.Contains("Fern") ? 0.05f : 0.09f);
                    m.SetFloat("_WindHeight", d.name.Contains("Grass") || d.name.Contains("Fern") ? 0.6f : 10f);
                    m.renderQueue = 2450;
                    break;
                case Kind.Water:
                    m.SetTexture("_BumpMap", normal);
                    break;
                case Kind.Decal:
                    m.SetTexture("_MainTex", albedo); m.SetTexture("_BumpMap", normal);
                    break;
                case Kind.Particle:
                case Kind.ParticleAdd:
                    m.SetTexture("_MainTex", albedo);
                    m.SetFloat("_SrcBlend", d.kind == Kind.ParticleAdd ? (float)UnityEngine.Rendering.BlendMode.SrcAlpha : (float)UnityEngine.Rendering.BlendMode.SrcAlpha);
                    m.SetFloat("_DstBlend", d.kind == Kind.ParticleAdd ? (float)UnityEngine.Rendering.BlendMode.One : (float)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                    m.SetFloat("_NearFade", d.name.Contains("Fog") ? 1.5f : 0.05f);
                    m.SetFloat("_FarFade", d.name.Contains("Fog") ? 4f : 0.15f);
                    break;
                case Kind.Overlay:
                    m.SetColor("_Color", new Color(0, 0, 0, 0));
                    if (d.set == "vignette") m.SetTexture("_MainTex", AssetDatabase.LoadAssetAtPath<Texture2D>(MNFPaths.Generated + "/vignette.png"));
                    break;
            }
            EditorUtility.SetDirty(m);
            Cache[d.name] = m;
            return m;
        }

        static Shader ShaderFor(Kind k)
        {
            switch (k)
            {
                case Kind.Tri: return Shader.Find("MNF/Triplanar");
                case Kind.Terrain: return Shader.Find("MNF/TerrainBlend");
                case Kind.Foliage: return Shader.Find("MNF/Foliage");
                case Kind.Water: return Shader.Find("MNF/Water");
                case Kind.Decal: return Shader.Find("MNF/Decal");
                case Kind.Particle: case Kind.ParticleAdd: return Shader.Find("MNF/Particle");
                case Kind.Overlay: return Shader.Find("MNF/ScreenOverlay");
                default: return Shader.Find("Standard");
            }
        }

        static void SetupStandard(Material m, Def d, Texture2D albedo, Texture2D normal, Texture2D mask, Texture2D emis)
        {
            m.SetColor("_Color", d.tint);
            m.SetTexture("_MainTex", albedo);
            if (normal) { m.SetTexture("_BumpMap", normal); m.SetFloat("_BumpScale", 1f); m.EnableKeyword("_NORMALMAP"); }
            else m.DisableKeyword("_NORMALMAP");
            if (mask)
            {
                m.SetTexture("_MetallicGlossMap", mask);
                m.EnableKeyword("_METALLICGLOSSMAP");
                m.SetFloat("_GlossMapScale", d.smooth >= 0f ? d.smooth : 1f);
                m.SetFloat("_SmoothnessTextureChannel", 0f);
                m.SetTexture("_OcclusionMap", mask);
                m.SetFloat("_OcclusionStrength", 1f);
            }
            else
            {
                m.DisableKeyword("_METALLICGLOSSMAP");
                m.SetFloat("_Glossiness", d.smooth >= 0f ? d.smooth : 0.25f);
                m.SetFloat("_Metallic", d.metal >= 0f ? d.metal : 0f);
            }
            if (d.kind == Kind.Emissive || emis || d.emissionColor.maxColorComponent > 0f)
            {
                if (emis) m.SetTexture("_EmissionMap", emis);
                var ec = (d.emissionColor.maxColorComponent > 0f ? d.emissionColor : Color.white) * d.emission;
                m.SetColor("_EmissionColor", ec);
                m.EnableKeyword("_EMISSION");
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
            }
            else { m.DisableKeyword("_EMISSION"); m.SetColor("_EmissionColor", Color.black); }

            // render mode
            int mode = d.kind == Kind.Cutout ? 1 : d.kind == Kind.Fade ? 2 : 0;
            m.SetFloat("_Mode", mode);
            m.DisableKeyword("_ALPHATEST_ON"); m.DisableKeyword("_ALPHABLEND_ON"); m.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            if (mode == 0)
            {
                m.SetOverrideTag("RenderType", "");
                m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.One);
                m.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.Zero);
                m.SetInt("_ZWrite", 1);
                m.renderQueue = -1;
            }
            else if (mode == 1)
            {
                m.SetOverrideTag("RenderType", "TransparentCutout");
                m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.One);
                m.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.Zero);
                m.SetInt("_ZWrite", 1);
                m.SetFloat("_Cutoff", 0.45f);
                m.EnableKeyword("_ALPHATEST_ON");
                m.renderQueue = (int)UnityEngine.Rendering.RenderQueue.AlphaTest;
            }
            else
            {
                m.SetOverrideTag("RenderType", "Transparent");
                m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
                m.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                m.SetInt("_ZWrite", 0);
                m.EnableKeyword("_ALPHABLEND_ON");
                m.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            }
        }

        static void GenerateVignetteTexture()
        {
            MNFPaths.Ensure(MNFPaths.Generated);
            string path = MNFPaths.Generated + "/vignette.png";
            if (MNFPaths.Exists(path)) return;
            const int s = 128;
            var t = new Texture2D(s, s, TextureFormat.RGBA32, false);
            for (int y = 0; y < s; y++)
            for (int x = 0; x < s; x++)
            {
                float dx = (x + 0.5f) / s * 2f - 1f, dy = (y + 0.5f) / s * 2f - 1f;
                float r = Mathf.Sqrt(dx * dx + dy * dy);
                float a = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.35f, 1.05f, r));
                t.SetPixel(x, y, new Color(1, 1, 1, a));
            }
            File.WriteAllBytes(Path.Combine(Path.GetDirectoryName(Application.dataPath), path), t.EncodeToPNG());
            Object.DestroyImmediate(t);
            AssetDatabase.ImportAsset(path);
        }

        /// <summary>Points every embedded FBX material at the catalog material of the same name.</summary>
        public static void RemapModelMaterials()
        {
            var missing = new HashSet<string>();
            foreach (var guid in AssetDatabase.FindAssets("t:Model", new[] { MNFPaths.Models }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                var mi = AssetImporter.GetAtPath(path) as ModelImporter;
                if (!mi) continue;
                bool changed = false;
                foreach (var o in AssetDatabase.LoadAllAssetsAtPath(path))
                {
                    if (!(o is Material src)) continue;
                    var target = Get(src.name);
                    if (!target) { missing.Add(src.name + " (" + Path.GetFileName(path) + ")"); target = Get("MNF_Fallback"); }
                    if (!target) continue;
                    mi.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), src.name), target);
                    changed = true;
                }
                if (changed) { mi.SaveAndReimport(); }
            }
            foreach (var m in missing) Debug.LogWarning("[MNF] Material not in catalog, using fallback: " + m);
        }
    }
}
