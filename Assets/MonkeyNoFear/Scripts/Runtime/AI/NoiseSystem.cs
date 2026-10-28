using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.AI
{
    public enum NoiseKind { HandImpact, Movement, ItemDrop, MetalImpact, Mining, Break, Lure, Flare, Cart, Voice, Machine, Combat }

    public struct NoiseEvent
    {
        public Vector3 position;
        /// <summary>0..1+ . Radius in meters = loudness * NoiseSystem.MetersPerLoudness.</summary>
        public float loudness;
        public NoiseKind kind;
        public bool fromPlayer;
        public float time;
        public Object source;
        public float Radius => loudness * NoiseSystem.MetersPerLoudness;
    }

    /// <summary>Anything that can hear: creatures, wildlife, the Borer's territory.</summary>
    public interface INoiseListener
    {
        Vector3 HearingPosition { get; }
        float HearingSensitivity { get; }
        bool ListeningEnabled { get; }
        /// <param name="perceived">0..1 strength after distance falloff and occlusion</param>
        void OnNoiseHeard(in NoiseEvent e, float perceived);
    }

    /// <summary>Static noise bus. Sounds the player makes are physically meaningful: they propagate with
    /// distance falloff and are muffled (not blocked) by walls, so creatures cannot hear through solid rock
    /// as well as through open air.</summary>
    public static class NoiseSystem
    {
        public const float MetersPerLoudness = 30f;
        public const float WallTransmission = 0.4f;

        static readonly List<INoiseListener> Listeners = new List<INoiseListener>();
        static readonly NoiseEvent[] Recent = new NoiseEvent[32];
        static int _recentIndex;

        public static void Register(INoiseListener l) { if (!Listeners.Contains(l)) Listeners.Add(l); }
        public static void Unregister(INoiseListener l) => Listeners.Remove(l);

        public static void Emit(Vector3 position, float loudness, NoiseKind kind, bool fromPlayer, Object source = null)
        {
            if (loudness <= 0.01f) return;
            var e = new NoiseEvent { position = position, loudness = loudness, kind = kind, fromPlayer = fromPlayer, time = Time.time, source = source };
            Recent[_recentIndex] = e;
            _recentIndex = (_recentIndex + 1) % Recent.Length;

            float radius = e.Radius;
            for (int i = Listeners.Count - 1; i >= 0; i--)
            {
                var l = Listeners[i];
                if (l == null || !l.ListeningEnabled) continue;
                float r = radius * l.HearingSensitivity;
                var lp = l.HearingPosition;
                float d = Vector3.Distance(lp, position);
                if (d >= r) continue;
                float perceived = 1f - d / r;
                if (Physics.Linecast(position + Vector3.up * 0.1f, lp, Layers.Occluders, QueryTriggerInteraction.Ignore))
                    perceived *= WallTransmission;
                if (perceived > 0.02f) l.OnNoiseHeard(e, perceived);
            }
        }

        public static IEnumerable<NoiseEvent> RecentEvents(float maxAge)
        {
            float now = Time.time;
            foreach (var e in Recent)
                if (e.loudness > 0f && now - e.time <= maxAge) yield return e;
        }
    }
}
