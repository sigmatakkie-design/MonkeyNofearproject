using UnityEngine;
using MonkeyNoFear.Audio;

namespace MonkeyNoFear.Interaction
{
    /// <summary>Grab the handle and pull it through its arc (rotation about the hinge's local X). Passing
    /// the end of travel fires the command. Spring-return levers snap back; toggle levers stay.</summary>
    public class PhysicalLever : MonoBehaviour, IGrabInteractable
    {
        public MonoBehaviour receiver;
        public string commandDown = "lever_down";
        public string commandUp = "lever_up";
        [Tooltip("The hinge transform that rotates (usually the handle's pivot).")]
        public Transform hinge;
        public float minAngle = -45f;
        public float maxAngle = 45f;
        [Range(0.5f, 1f)] public float triggerFraction = 0.85f;
        public bool springReturn = true;
        public float restAngle = -45f;

        float _angle;
        bool _down;
        HandGrabber _holder;
        Quaternion _hingeRest;
        IButtonReceiver _recv;

        void Awake()
        {
            if (!hinge) hinge = transform;
            _hingeRest = hinge.localRotation;
            _angle = restAngle;
            _recv = receiver as IButtonReceiver;
            Apply();
        }

        public bool CanGrab(HandGrabber hand) => _holder == null;
        public void BeginGrab(HandGrabber hand) { _holder = hand; }
        public void EndGrab(HandGrabber hand) { if (_holder == hand) _holder = null; }

        public void UpdateGrab(HandGrabber hand, float dt)
        {
            // project the hand onto the hinge plane and measure its angle around local X
            var parent = hinge.parent ? hinge.parent : hinge;
            var local = parent.InverseTransformPoint(hand.HandPosition) - hinge.localPosition;
            float a = Mathf.Atan2(local.z, local.y) * Mathf.Rad2Deg;
            _angle = Mathf.Clamp(a, minAngle, maxAngle);
            Apply();
            float t = Mathf.InverseLerp(minAngle, maxAngle, _angle);
            if (!_down && t >= triggerFraction) { _down = true; Fire(commandDown); hand.Rig?.Haptic(hand.Side, 0.7f, 0.08f); }
            else if (_down && t <= 1f - triggerFraction) { _down = false; Fire(commandUp); hand.Rig?.Haptic(hand.Side, 0.5f, 0.06f); }
        }

        void Fire(string cmd)
        {
            AudioManager.Instance?.PlayAt("lever_pull", hinge.position, 0.9f);
            if (_recv == null) _recv = receiver as IButtonReceiver;
            if (!string.IsNullOrEmpty(cmd)) _recv?.OnButton(cmd);
        }

        void Update()
        {
            if (_holder == null && springReturn)
            {
                _angle = Mathf.MoveTowards(_angle, restAngle, 240f * Time.deltaTime);
                if (Mathf.Abs(_angle - restAngle) < 0.5f) _down = false;
                Apply();
            }
        }

        void Apply() => hinge.localRotation = _hingeRest * Quaternion.Euler(_angle - restAngle, 0f, 0f);
    }
}
