using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.Data
{
    /// <summary>Fog, light and audio mood of one area. AreaManager blends between profiles.</summary>
    [CreateAssetMenu(menuName = "Monkey No Fear/Atmosphere Profile", fileName = "Atmosphere_")]
    public class AtmosphereProfile : ScriptableObject
    {
        public AreaId area;
        public string displayName = "Area";
        [Tooltip("0 = surface, 1-3 = mine levels. Drives escalation.")]
        public int depthLevel;

        [Header("Fog")]
        public Color fogColor = new Color(0.08f, 0.09f, 0.1f);
        [Tooltip("Exponential-squared fog density.")]
        public float fogDensity = 0.03f;

        [Header("Ambient light")]
        public Color ambientSky = new Color(0.08f, 0.09f, 0.11f);
        public Color ambientEquator = new Color(0.05f, 0.05f, 0.06f);
        public Color ambientGround = new Color(0.03f, 0.03f, 0.03f);
        [Tooltip("Moonlight intensity multiplier (0 underground).")]
        public float moonIntensity;

        [Header("Camera")]
        public float farClip = 120f;

        [Header("Audio")]
        public string[] ambienceBeds = new string[0];
        [Tooltip("Ambience layers that fade out when a threat is near (insects, frogs...).")]
        public string[] lifeLayers = new string[0];
        public AudioReverbPreset reverb = AudioReverbPreset.Off;

        [Header("Survival")]
        public float vigorDrainMultiplier = 1f;
        public bool isSafeZone;

        /// <summary>Approximate distance at which fog hides a silhouette (used by AI vision for fairness).</summary>
        public float FogVisibility => fogDensity <= 0.0001f ? 500f : Mathf.Sqrt(-Mathf.Log(0.08f)) / fogDensity;
    }
}
