using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR;

namespace MonkeyNoFear.Player
{
    public enum Hand { Left = 0, Right = 1 }

    public struct ControllerState
    {
        public bool tracked;
        public Vector3 position;     // tracking-space (floor origin)
        public Quaternion rotation;
        public float grip, trigger;
        public bool primary, secondary, stickClick, menu;
        public Vector2 stick;
    }

    public interface IPlayerInputSource
    {
        string Name { get; }
        bool Available { get; }
        void Poll();
        bool HeadTracked { get; }
        Vector3 HeadPosition { get; }
        Quaternion HeadRotation { get; }
        ControllerState Get(Hand hand);
        void Haptic(Hand hand, float amplitude, float duration);
    }

    /// <summary>OpenXR (or any XR plug-in) input through Unity's built-in XR InputDevices API.
    /// Works with the OpenXR plug-in plus an interaction profile (Oculus Touch / Index / etc.).</summary>
    public class XRPlayerInput : IPlayerInputSource
    {
        InputDevice _head, _left, _right;
        readonly ControllerState[] _state = new ControllerState[2];
        readonly List<XRInputSubsystem> _subsystems = new List<XRInputSubsystem>();
        bool _floorSet;
        float _floorRetry;

        public string Name => "OpenXR";
        public bool Available => XRSettings.isDeviceActive || _head.isValid;
        public bool HeadTracked { get; private set; }
        public Vector3 HeadPosition { get; private set; }
        public Quaternion HeadRotation { get; private set; } = Quaternion.identity;
        /// <summary>True when the runtime refused floor tracking (eye-level space); the rig adds a height offset.</summary>
        public bool EyeLevelSpace { get; private set; }

        public void Poll()
        {
            if (!_head.isValid) _head = InputDevices.GetDeviceAtXRNode(XRNode.CenterEye);
            if (!_head.isValid) _head = InputDevices.GetDeviceAtXRNode(XRNode.Head);
            if (!_left.isValid) _left = InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
            if (!_right.isValid) _right = InputDevices.GetDeviceAtXRNode(XRNode.RightHand);

            if (!_floorSet)
            {
                _floorRetry -= Time.unscaledDeltaTime;
                if (_floorRetry <= 0f) { _floorRetry = 1f; TrySetFloorOrigin(); }
            }

            HeadTracked = false;
            if (_head.isValid)
            {
                if (_head.TryGetFeatureValue(CommonUsages.centerEyePosition, out Vector3 p) ||
                    _head.TryGetFeatureValue(CommonUsages.devicePosition, out p))
                {
                    HeadPosition = p;
                    HeadTracked = true;
                }
                if (_head.TryGetFeatureValue(CommonUsages.centerEyeRotation, out Quaternion r) ||
                    _head.TryGetFeatureValue(CommonUsages.deviceRotation, out r))
                    HeadRotation = r;
            }
            Read(_left, ref _state[0]);
            Read(_right, ref _state[1]);
        }

        void TrySetFloorOrigin()
        {
            SubsystemManager.GetInstances(_subsystems);
            foreach (var s in _subsystems)
            {
                if ((s.GetSupportedTrackingOriginModes() & TrackingOriginModeFlags.Floor) != 0 &&
                    s.TrySetTrackingOriginMode(TrackingOriginModeFlags.Floor))
                {
                    _floorSet = true;
                    EyeLevelSpace = false;
                    return;
                }
            }
            if (_subsystems.Count > 0) EyeLevelSpace = true;
        }

        static void Read(InputDevice d, ref ControllerState s)
        {
            s.tracked = false;
            if (!d.isValid) return;
            bool isTracked = true;
            d.TryGetFeatureValue(CommonUsages.isTracked, out isTracked);
            if (d.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 p)) s.position = p; else isTracked = false;
            if (d.TryGetFeatureValue(CommonUsages.deviceRotation, out Quaternion r)) s.rotation = r;
            s.tracked = isTracked;
            d.TryGetFeatureValue(CommonUsages.grip, out s.grip);
            d.TryGetFeatureValue(CommonUsages.trigger, out s.trigger);
            d.TryGetFeatureValue(CommonUsages.primaryButton, out s.primary);
            d.TryGetFeatureValue(CommonUsages.secondaryButton, out s.secondary);
            d.TryGetFeatureValue(CommonUsages.primary2DAxisClick, out s.stickClick);
            d.TryGetFeatureValue(CommonUsages.menuButton, out s.menu);
            d.TryGetFeatureValue(CommonUsages.primary2DAxis, out s.stick);
        }

        public ControllerState Get(Hand hand) => _state[(int)hand];

        public void Haptic(Hand hand, float amplitude, float duration)
        {
            var d = hand == Hand.Left ? _left : _right;
            if (d.isValid && d.TryGetHapticCapabilities(out var caps) && caps.supportsImpulse)
                d.SendHapticImpulse(0, Mathf.Clamp01(amplitude), duration);
        }

        public void Recenter()
        {
            SubsystemManager.GetInstances(_subsystems);
            foreach (var s in _subsystems) s.TryRecenter();
        }
    }
}
