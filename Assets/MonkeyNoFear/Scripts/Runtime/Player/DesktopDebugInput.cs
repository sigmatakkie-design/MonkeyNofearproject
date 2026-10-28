using UnityEngine;

namespace MonkeyNoFear.Player
{
    /// <summary>
    /// DEBUG ONLY desktop driver. It never moves the body directly: it synthesises head and hand poses and
    /// feeds them to the real arm locomotion, so movement tested on desktop is the same system as in VR.
    ///   Mouse = look (Tab toggles cursor lock)       W/A/S/D = knuckle-walk (hands paw the ground)
    ///   Shift = faster paws    Space = two-hand jump push    C = crouch
    ///   LMB / RMB = right / left grip    E / Q = right / left trigger    R / F = right primary / secondary
    ///   Mouse wheel = right hand reach    Hold Z = left hand reaches forward too
    /// Disabled automatically when an XR headset is active or when the legacy input backend is disabled.
    /// </summary>
    public class DesktopDebugInput : IPlayerInputSource
    {
        public float eyeHeight = 1.55f;
        public float crouchHeight = 0.95f;
        public float pawCycle = 0.55f;

        float _yaw, _pitch, _reach = 0.45f, _phase, _jumpT = -1f;
        bool _crouch, _locked, _broken;
        float _height;
        readonly ControllerState[] _s = new ControllerState[2];

        public string Name => "Desktop (debug)";
        public bool Available => !_broken;
        public bool HeadTracked => true;
        public Vector3 HeadPosition { get; private set; }
        public Quaternion HeadRotation { get; private set; } = Quaternion.identity;

        public void Poll()
        {
            if (_broken) return;
            try { PollInternal(); }
            catch (System.InvalidOperationException)
            {
                // Project uses the new Input System only: the debug driver cannot read keys.
                _broken = true;
                Debug.LogWarning("[DesktopDebugInput] Legacy input disabled (Player Settings > Active Input Handling). Desktop debug controls unavailable.");
            }
        }

        void PollInternal()
        {
            float dt = Time.deltaTime;
            if (Input.GetKeyDown(KeyCode.Tab)) { _locked = !_locked; Cursor.lockState = _locked ? CursorLockMode.Locked : CursorLockMode.None; Cursor.visible = !_locked; }
            if (_locked || Input.GetMouseButton(2))
            {
                _yaw += Input.GetAxis("Mouse X") * 2.5f;
                _pitch = Mathf.Clamp(_pitch - Input.GetAxis("Mouse Y") * 2.5f, -85f, 85f);
            }
            if (Input.GetKeyDown(KeyCode.C)) _crouch = !_crouch;
            _height = Mathf.MoveTowards(_height <= 0f ? eyeHeight : _height, _crouch ? crouchHeight : eyeHeight, dt * 2f);
            _reach = Mathf.Clamp(_reach + Input.mouseScrollDelta.y * 0.05f, 0.2f, 0.75f);

            var yawRot = Quaternion.Euler(0f, _yaw, 0f);
            HeadRotation = Quaternion.Euler(_pitch, _yaw, 0f);
            HeadPosition = new Vector3(0f, _height, 0f);

            // rest poses in front of the body
            Vector3 head = HeadPosition;
            Vector3 restL = head + yawRot * new Vector3(-0.22f, -0.45f, 0.3f);
            Vector3 aimR = head + HeadRotation * new Vector3(0.12f, -0.12f, _reach);
            Vector3 aimL = head + HeadRotation * new Vector3(-0.12f, -0.12f, _reach);
            Vector3 l = Input.GetKey(KeyCode.Z) ? aimL : restL;
            Vector3 r = aimR;

            // knuckle-walk macro: alternate hands press into the floor and drag backwards
            Vector2 move = new Vector2((Input.GetKey(KeyCode.D) ? 1 : 0) - (Input.GetKey(KeyCode.A) ? 1 : 0),
                                       (Input.GetKey(KeyCode.W) ? 1 : 0) - (Input.GetKey(KeyCode.S) ? 1 : 0));
            if (move.sqrMagnitude > 0.01f)
            {
                move.Normalize();
                float cycle = Input.GetKey(KeyCode.LeftShift) ? pawCycle * 0.6f : pawCycle;
                _phase = (_phase + dt / cycle) % 1f;
                Vector3 dir = yawRot * new Vector3(move.x, 0f, move.y);
                l = PawPose(head, yawRot, dir, _phase, -0.2f);
                r = PawPose(head, yawRot, dir, (_phase + 0.5f) % 1f, 0.2f);
            }

            // jump macro: both hands slam down then lift
            if (Input.GetKeyDown(KeyCode.Space)) _jumpT = 0f;
            if (_jumpT >= 0f)
            {
                _jumpT += dt;
                float t = _jumpT / 0.32f;
                float y = t < 0.35f ? Mathf.Lerp(0.35f, -0.06f, t / 0.35f) : Mathf.Lerp(-0.06f, -0.75f, (t - 0.35f) / 0.65f);
                // hands are anchored on the floor while pushing "down" relative to the body: the body rises
                l = new Vector3(l.x, y, l.z); r = new Vector3(r.x, y, r.z);
                if (t >= 1f) _jumpT = -1f;
            }

            Set(Hand.Left, l, HeadRotation, Input.GetMouseButton(1), Input.GetKey(KeyCode.Q), false, false);
            Set(Hand.Right, r, HeadRotation, Input.GetMouseButton(0), Input.GetKey(KeyCode.E), Input.GetKey(KeyCode.R), Input.GetKey(KeyCode.F));
        }

        static Vector3 PawPose(Vector3 head, Quaternion yaw, Vector3 dir, float phase, float side)
        {
            Vector3 lateral = yaw * new Vector3(side, 0f, 0f);
            Vector3 basePos = new Vector3(head.x, 0f, head.z) + lateral;
            if (phase < 0.5f)
            {
                // planted: press 6 cm into the ground, drag from front to back
                float t = phase / 0.5f;
                return basePos + dir * Mathf.Lerp(0.35f, -0.25f, t) + Vector3.up * -0.06f;
            }
            else
            {
                // recover: lift and swing forward
                float t = (phase - 0.5f) / 0.5f;
                return basePos + dir * Mathf.Lerp(-0.25f, 0.35f, t) + Vector3.up * (0.05f + Mathf.Sin(t * Mathf.PI) * 0.25f);
            }
        }

        void Set(Hand h, Vector3 p, Quaternion rot, bool grip, bool trigger, bool primary, bool secondary)
        {
            ref var s = ref _s[(int)h];
            s.tracked = true;
            s.position = p;
            s.rotation = rot;
            s.grip = grip ? 1f : 0f;
            s.trigger = trigger ? 1f : 0f;
            s.primary = primary;
            s.secondary = secondary;
            s.stick = Vector2.zero;
        }

        public ControllerState Get(Hand hand) => _s[(int)hand];
        public void Haptic(Hand hand, float amplitude, float duration) { }
    }
}
