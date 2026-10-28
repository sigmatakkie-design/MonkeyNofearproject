using System.Collections.Generic;
using UnityEngine;

namespace MonkeyNoFear.World
{
    public enum HorrorEventType
    {
        PhantomFootsteps, RockFall, MinecartNudge, WallScratch, LightTurnsOn, DeadRoomHum, MetalRepeat,
        PARecording, PeripheralSilhouette, DistantCallStops, BranchSnap, TreeCreak, FoliageCircling, Crow,
        BunkerImpact, BunkerCreak, RadioInterference, PipeKnock, LightFlicker, PowerDip, Whisper
    }

    /// <summary>Authored place where a specific scare can happen (a PA speaker, a metal plate, a dark side
    /// passage lamp, a cart on rails, the end of a long tunnel for a silhouette...).</summary>
    public class HorrorAnchor : MonoBehaviour
    {
        public static readonly List<HorrorAnchor> All = new List<HorrorAnchor>();

        public HorrorEventType type;
        [Tooltip("Object the event animates or shows (silhouette, cart, hum source).")]
        public GameObject target;
        public Light lightTarget;
        [Tooltip("Objects revealed after the event (e.g. fresh scratch decals).")]
        public GameObject[] reveal = new GameObject[0];
        public float minDistance = 6f;
        public float maxDistance = 30f;
        [Tooltip("Only fire while the player is not looking at the anchor.")]
        public bool requireUnseen = true;
        [Tooltip("Fires at most once per expedition.")]
        public bool oncePerExpedition;
        [HideInInspector] public bool usedThisExpedition;

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        void OnDrawGizmos()
        {
            Gizmos.color = new Color(1f, 0.2f, 0.6f, 0.8f);
            Gizmos.DrawWireSphere(transform.position, 0.35f);
        }
    }
}
