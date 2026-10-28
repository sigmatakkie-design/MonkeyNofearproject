using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using MonkeyNoFear.Audio;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>Builds the SoundBank from Audio/audio_manifest.json: one group per sound name with its
    /// variants, plus spatial defaults per category (how far a creature or a tool can be heard).</summary>
    public static class AudioFactory
    {
        public const string BankPath = MNFPaths.Data + "/SoundBank.asset";

        public static SoundBank Build()
        {
            var bank = MNFPaths.CreateOrReplace<SoundBank>(BankPath);
            bank.groups.Clear();
            var manifest = MiniJson.Parse(MNFPaths.ReadText(MNFPaths.Audio + "/audio_manifest.json")).AsObj();
            if (manifest == null)
            {
                Debug.LogWarning("[MNF] audio_manifest.json missing — SoundBank is empty (the game runs silently).");
                EditorUtility.SetDirty(bank);
                return bank;
            }
            foreach (var kv in manifest)
            {
                var e = kv.Value.AsObj();
                var g = new SoundGroup { name = kv.Key };
                var clips = new List<AudioClip>();
                foreach (var f in e.Get("files").AsList())
                {
                    var clip = AssetDatabase.LoadAssetAtPath<AudioClip>($"{MNFPaths.Audio}/{f}");
                    if (clip) clips.Add(clip); else Debug.LogWarning($"[MNF] Missing audio file {f}");
                }
                g.clips = clips.ToArray();
                g.loop = e.GetBool("loop");
                bool spatial = e.GetBool("spatial", true);
                g.spatialBlend = spatial ? 1f : 0f;
                ApplyDefaults(g, e.GetString("category", ""));
                bank.groups.Add(g);
            }
            EditorUtility.SetDirty(bank);
            AssetDatabase.SaveAssets();
            Debug.Log($"[MNF] SoundBank: {bank.groups.Count} groups");
            return bank;
        }

        static void ApplyDefaults(SoundGroup g, string category)
        {
            string n = g.name;
            g.pitchMin = 0.94f; g.pitchMax = 1.06f;
            g.minDistance = 1f; g.maxDistance = 20f; g.priority = 128; g.volume = 1f; g.occlusion = true;
            switch (category)
            {
                case "Player":
                    g.maxDistance = 10f; g.priority = 100; g.occlusion = false;
                    if (n.StartsWith("hand_tap")) g.volume = 0.7f;
                    if (n.StartsWith("heartbeat") || n.StartsWith("breath") || n.StartsWith("death")) { g.spatialBlend = 0f; g.pitchMin = g.pitchMax = 1f; }
                    break;
                case "Tools":
                    g.maxDistance = 18f; g.priority = 90; g.occlusion = false;
                    if (n.StartsWith("pick_hit") || n.StartsWith("ore_break") || n.StartsWith("noisemaker")) g.maxDistance = 35f;
                    break;
                case "Bunker":
                    g.maxDistance = 22f;
                    if (n.StartsWith("distant_impact") || n.StartsWith("structural")) { g.minDistance = 6f; g.maxDistance = 60f; }
                    if (n.StartsWith("gate")) { g.minDistance = 2f; g.maxDistance = 40f; g.priority = 70; }
                    if (n.StartsWith("terminal") || n.StartsWith("button") || n.StartsWith("coin")) { g.maxDistance = 8f; g.occlusion = false; }
                    break;
                case "Forest":
                    g.minDistance = 3f; g.maxDistance = 70f; g.priority = 160;
                    if (n.StartsWith("stream") || n.StartsWith("frogs")) { g.minDistance = 2f; g.maxDistance = 25f; }
                    break;
                case "Creatures":
                    g.minDistance = 1.5f; g.maxDistance = 45f; g.priority = 40;
                    if (n.StartsWith("clerk_tap") || n.StartsWith("clerk_click")) { g.minDistance = 0.7f; g.maxDistance = 14f; g.priority = 30; }
                    if (n.StartsWith("borer_impact") || n.StartsWith("borer_roar") || n.StartsWith("borer_emerge")) { g.minDistance = 5f; g.maxDistance = 80f; g.priority = 20; }
                    if (n.StartsWith("gaunt")) { g.minDistance = 30f; g.maxDistance = 250f; g.pitchMin = 0.97f; g.pitchMax = 1.0f; }
                    if (n.StartsWith("hb_slap") || n.StartsWith("hb_scrape")) g.maxDistance = 55f;
                    if (n.StartsWith("rabbit") || n.StartsWith("rat_") || n.StartsWith("fk_mimic")) { g.minDistance = 0.8f; g.maxDistance = 15f; g.priority = 150; }
                    if (n.StartsWith("fk_reveal") || n.StartsWith("fk_shriek")) g.priority = 10;
                    break;
                case "Mine":
                    g.minDistance = 2f; g.maxDistance = 45f; g.priority = 140;
                    if (n.StartsWith("drip")) { g.minDistance = 0.8f; g.maxDistance = 18f; g.priority = 200; }
                    if (n.StartsWith("metal_impact") || n.StartsWith("rock_fall_large")) { g.minDistance = 6f; g.maxDistance = 90f; }
                    break;
                case "Music":
                    g.spatialBlend = 0f; g.priority = 5; g.pitchMin = g.pitchMax = 1f; g.occlusion = false;
                    break;
            }
            if (n.Contains("_bed")) { g.spatialBlend = 0f; g.priority = 8; g.pitchMin = g.pitchMax = 1f; g.occlusion = false; g.volume = 0.8f; }
            if (n.EndsWith("_loop")) { g.pitchMin = g.pitchMax = 1f; g.cooldown = 0f; }
            if (n == "amb_forest_insects_loop" || n == "tension_drone_loop") { g.spatialBlend = 0f; g.occlusion = false; }
        }
    }
}
