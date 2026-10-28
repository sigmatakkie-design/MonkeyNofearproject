using System;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.World
{
    /// <summary>Player-following ambient particle layers (forest ground fog and drifting leaves, mine and
    /// bunker dust motes). Each layer emits in world space around the player and is enabled per area.</summary>
    public class AmbientParticles : MonoBehaviour
    {
        [Serializable]
        public class Layer
        {
            public ParticleSystem system;
            public AreaId[] areas = new AreaId[0];
            [Tooltip("Follow the head height (motes) instead of the floor (ground fog).")]
            public bool followHead;
            public Vector3 offset;
        }

        public Layer[] layers = new Layer[0];

        void OnEnable() => GameEvents.AreaChanged += OnArea;
        void OnDisable() => GameEvents.AreaChanged -= OnArea;

        void OnArea(AreaId from, AreaId to)
        {
            foreach (var l in layers)
            {
                if (!l.system) continue;
                bool on = Array.IndexOf(l.areas, to) >= 0;
                var em = l.system.emission;
                em.enabled = on;
                if (on && !l.system.isPlaying) l.system.Play();
            }
        }

        void LateUpdate()
        {
            var rig = PlayerRig.Instance;
            if (!rig) return;
            foreach (var l in layers)
            {
                if (!l.system) continue;
                var p = l.followHead ? rig.HeadPosition : rig.transform.position;
                l.system.transform.position = p + l.offset;
            }
        }
    }
}
