using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.Player
{
    /// <summary>Anything the player carries that emits light (flashlight, flare, glowstick, headlamp).
    /// Creatures react to these: the Lantern Mourner is drawn to them, the Ceiling Clerk freezes in them.</summary>
    public interface IPlayerLight
    {
        bool IsLit { get; }
        Light Light { get; }
        /// <summary>True if the light's beam/radius currently illuminates the point (with line of sight).</summary>
        bool Illuminates(Vector3 point);
        Vector3 Position { get; }
        float Intensity01 { get; }
    }

    /// <summary>How noticeable the player is right now (0..1): movement, own lights, crouching.</summary>
    public class PlayerStealth : MonoBehaviour
    {
        public static PlayerStealth Instance { get; private set; }
        public static readonly List<IPlayerLight> Lights = new List<IPlayerLight>();

        public float crouchHeadHeight = 1.05f;
        public float stillSpeed = 0.15f;

        PlayerRig _rig;
        float _stillTime;

        public float Visibility { get; private set; }
        public bool IsStill => _stillTime > 0.75f;
        public float StillTime => _stillTime;
        public bool Crouched { get; private set; }
        public bool OwnLightOn { get; private set; }

        void Awake() { Instance = this; _rig = GetComponent<PlayerRig>(); }

        public static void RegisterLight(IPlayerLight l) { if (!Lights.Contains(l)) Lights.Add(l); }
        public static void UnregisterLight(IPlayerLight l) => Lights.Remove(l);

        void Update()
        {
            if (!_rig) return;
            float speed = _rig.locomotion.Speed;
            float handSpeed = Mathf.Max(_rig.LeftHand.ControllerVelocity.magnitude, _rig.RightHand.ControllerVelocity.magnitude);
            bool still = speed < stillSpeed && handSpeed < 0.6f;
            _stillTime = still ? _stillTime + Time.deltaTime : 0f;
            Crouched = _rig.HeadPosition.y - _rig.transform.position.y < crouchHeadHeight;

            OwnLightOn = false;
            foreach (var l in Lights)
                if (l != null && l.IsLit && (l.Position - _rig.HeadPosition).sqrMagnitude < 4f) { OwnLightOn = true; break; }

            float moving = IsStill ? 0.25f : Mathf.Lerp(0.55f, 1f, Mathf.Clamp01(speed / 4f));
            float v = moving * (OwnLightOn ? 1.6f : 1f) * (Crouched ? 0.7f : 1f);
            Visibility = Mathf.Clamp01(v);
        }

        /// <summary>Strongest player-carried light illuminating a point (null if none).</summary>
        public static IPlayerLight LightOn(Vector3 point)
        {
            IPlayerLight best = null; float bi = 0f;
            foreach (var l in Lights)
                if (l != null && l.IsLit && l.Intensity01 > bi && l.Illuminates(point)) { best = l; bi = l.Intensity01; }
            return best;
        }
    }
}
