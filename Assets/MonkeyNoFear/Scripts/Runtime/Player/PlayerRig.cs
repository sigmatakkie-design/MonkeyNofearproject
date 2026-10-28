using UnityEngine;
using UnityEngine.XR;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Player
{
    /// <summary>
    /// Root of the player. Hierarchy (built by the editor builder):
    ///   PlayerRig (this, MonkeyLocomotion, PlayerHealth, PlayerVitals, PlayerStealth, Backpack, kinematic Rigidbody)
    ///     TrackingSpace            — XR floor origin
    ///       HeadCamera             — Camera + AudioListener, posed from the HMD
    ///     Body                     — CapsuleCollider (Player layer), sized every frame
    ///     LeftHand / RightHand     — PhysicsHand + HandGrabber (world-positioned every frame)
    ///     BodyFrame                — follows head position + yaw: holsters, backpack zone
    ///     Avatar                   — the supplied monkey model + PlayerAvatar IK
    /// Update order: input → tracked poses → locomotion → grabbing (this script, early in the frame);
    /// avatar IK runs in LateUpdate.
    /// </summary>
    [DefaultExecutionOrder(-50)]
    public class PlayerRig : MonoBehaviour
    {
        public static PlayerRig Instance { get; private set; }

        [Header("Hierarchy")]
        public Transform trackingSpace;
        public Camera headCamera;
        public PhysicsHand leftHand;
        public PhysicsHand rightHand;
        public HandGrabber leftGrabber;
        public HandGrabber rightGrabber;
        public MonkeyLocomotion locomotion;
        public CapsuleCollider bodyCollider;
        public Transform bodyFrame;

        [Header("Input")]
        [Tooltip("Use the desktop debug driver when no headset is active (editor testing only).")]
        public bool allowDesktopFallback = true;
        [Tooltip("Offset from the controller grip pose to the palm centre (controller local, right hand; mirrored for left).")]
        public Vector3 palmOffset = new Vector3(0f, -0.01f, 0.03f);
        [Tooltip("Height added when the XR runtime only provides an eye-level tracking space.")]
        public float eyeLevelFallbackHeight = 1.45f;

        [Header("Comfort (optional)")]
        public float snapTurnThreshold = 0.75f;
        public float joystickSpeed = 2.2f;

        public IPlayerInputSource Input { get; private set; }
        public bool UsingXR => Input is XRPlayerInput;
        public Vector3 HeadPosition => headCamera ? headCamera.transform.position : transform.position + Vector3.up * 1.5f;
        public Quaternion HeadRotation => headCamera ? headCamera.transform.rotation : transform.rotation;
        public Vector3 HeadForward => headCamera ? headCamera.transform.forward : transform.forward;
        public PhysicsHand LeftHand => leftHand;
        public PhysicsHand RightHand => rightHand;
        public float BodyYaw { get; private set; }

        XRPlayerInput _xr;
        DesktopDebugInput _desktop;
        readonly ControllerState[] _ctrl = new ControllerState[2];
        bool _snapReady = true;
        float _recenterHold;

        void Awake()
        {
            if (Instance && Instance != this) { Debug.LogWarning("Duplicate PlayerRig destroyed"); Destroy(gameObject); return; }
            Instance = this;
            _xr = new XRPlayerInput();
            _desktop = new DesktopDebugInput();
            var rb = GetComponent<Rigidbody>();
            if (!rb) rb = gameObject.AddComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;
            leftHand.hand = Hand.Left; rightHand.hand = Hand.Right;
            leftHand.Init(this); rightHand.Init(this);
            locomotion.Init(this, bodyCollider);
            if (leftGrabber) leftGrabber.Init(this, leftHand);
            if (rightGrabber) rightGrabber.Init(this, rightHand);
            if (headCamera)
            {
                headCamera.nearClipPlane = 0.03f;
                if (XRSettings.enabled) XRDevice.DisableAutoXRCameraTracking(headCamera, true);
            }
        }

        void OnEnable() => Application.onBeforeRender += OnBeforeRender;
        void OnDisable() => Application.onBeforeRender -= OnBeforeRender;
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            Audio.AudioManager.Instance?.SetListener(headCamera ? headCamera.transform : transform);
            World.AreaManager.Instance?.BindCamera(headCamera);
            SelectInput();
            ApplyPoses();
            leftHand.Teleport(HandTarget(Hand.Left));
            rightHand.Teleport(HandTarget(Hand.Right));
        }

        void SelectInput()
        {
            _xr.Poll();
            if (_xr.Available) Input = _xr;
            else if (allowDesktopFallback && (Application.isEditor || Debug.isDebugBuild)) Input = _desktop;
            else Input = _xr;
        }

        void Update()
        {
            // hot-swap: headset put on / taken off in the editor
            if (Input != _xr && _xr.Available) Input = _xr;
            if (Input == _xr && !_xr.Available && allowDesktopFallback && Application.isEditor) Input = _desktop;

            Input.Poll();
            ApplyPoses();
            ComfortInput();
            locomotion.Step(Time.deltaTime);
            UpdateBodyFrame();
            leftGrabber?.Tick(Time.deltaTime);
            rightGrabber?.Tick(Time.deltaTime);
        }

        void OnBeforeRender()
        {
            // late latching: re-sample the head pose right before rendering to minimise latency
            if (Input == null || !Application.isPlaying) return;
            if (Input == _xr) { Input.Poll(); ApplyHead(); }
        }

        void ApplyHead()
        {
            if (!headCamera) return;
            if (Input.HeadTracked)
            {
                var p = Input.HeadPosition;
                if (Input == _xr && _xr.EyeLevelSpace) p.y += eyeLevelFallbackHeight;
                headCamera.transform.localPosition = p;
            }
            headCamera.transform.localRotation = Input.HeadRotation;
        }

        void ApplyPoses()
        {
            ApplyHead();
            for (int i = 0; i < 2; i++)
            {
                var s = Input.Get((Hand)i);
                if (s.tracked)
                {
                    if (Input == _xr && _xr.EyeLevelSpace) s.position.y += eyeLevelFallbackHeight;
                    _ctrl[i] = s;
                }
                else
                {
                    // lost tracking: keep the last pose, but drop buttons so nothing stays "held" by accident
                    var keep = _ctrl[i];
                    keep.grip = s.grip; keep.trigger = s.trigger; keep.primary = s.primary; keep.secondary = s.secondary;
                    keep.tracked = false;
                    _ctrl[i] = keep;
                }
            }
            leftHand.Rotation = trackingSpace.rotation * _ctrl[0].rotation;
            rightHand.Rotation = trackingSpace.rotation * _ctrl[1].rotation;
        }

        public ControllerState Controller(Hand h) => _ctrl[(int)h];
        public PhysicsHand GetHand(Hand h) => h == Hand.Left ? leftHand : rightHand;
        public HandGrabber GetGrabber(Hand h) => h == Hand.Left ? leftGrabber : rightGrabber;

        /// <summary>World-space palm target of the tracked controller (before collision).</summary>
        public Vector3 HandTarget(Hand h)
        {
            var s = _ctrl[(int)h];
            var off = palmOffset;
            if (h == Hand.Left) off.x = -off.x;
            return trackingSpace.TransformPoint(s.position + s.rotation * off);
        }

        public Quaternion HandRotation(Hand h) => trackingSpace.rotation * _ctrl[(int)h].rotation;

        void ComfortInput()
        {
            var settings = GameRoot.I ? GameRoot.I.Progress.Settings : null;
            var right = _ctrl[1];
            var left = _ctrl[0];

            if (settings == null || settings.snapTurn)
            {
                float x = right.stick.x;
                if (_snapReady && Mathf.Abs(x) > snapTurnThreshold)
                {
                    SnapTurn(Mathf.Sign(x) * (settings != null ? settings.snapTurnDegrees : 45f));
                    _snapReady = false;
                }
                else if (Mathf.Abs(x) < 0.3f) _snapReady = true;
            }

            // optional accessibility joystick movement (off by default; arm locomotion stays primary)
            if (settings != null && settings.joystickLocomotion && left.stick.sqrMagnitude > 0.04f)
            {
                var fwd = HeadForward; fwd.y = 0f; fwd.Normalize();
                var rightDir = Vector3.Cross(Vector3.up, fwd);
                locomotion.ExternalVelocity = (fwd * left.stick.y + rightDir * left.stick.x) * joystickSpeed;
            }
            else locomotion.ExternalVelocity = Vector3.zero;

            // hold both stick buttons for 2 s: un-stick / recentre (always available, never needed normally)
            if (left.stickClick && right.stickClick)
            {
                _recenterHold += Time.deltaTime;
                if (_recenterHold > 2f) { _recenterHold = 0f; _xr.Recenter(); locomotion.RecoverToSafePosition(); }
            }
            else _recenterHold = 0f;
        }

        public void SnapTurn(float degrees)
        {
            var pivot = HeadPosition;
            leftHand.Release(); rightHand.Release();
            transform.RotateAround(pivot, Vector3.up, degrees);
            leftHand.Teleport(HandTarget(Hand.Left));
            rightHand.Teleport(HandTarget(Hand.Right));
            ScreenFader.Instance?.Flash(Color.black, 0.08f);
        }

        void UpdateBodyFrame()
        {
            var f = HeadForward;
            f.y = 0f;
            if (f.sqrMagnitude < 0.001f) f = transform.forward;
            float targetYaw = Quaternion.LookRotation(f).eulerAngles.y;
            // the body lags behind fast head turns, like a real torso
            float diff = Mathf.DeltaAngle(BodyYaw, targetYaw);
            float rate = Mathf.Abs(diff) > 50f ? 12f : 3f;
            BodyYaw += diff * (1f - Mathf.Exp(-rate * Time.deltaTime));
            if (bodyFrame)
            {
                bodyFrame.position = HeadPosition;
                bodyFrame.rotation = Quaternion.Euler(0f, BodyYaw, 0f);
            }
        }

        /// <summary>Places the player so their head ends up above <paramref name="feet"/>, facing yaw.</summary>
        public void TeleportTo(Vector3 feet, float yaw)
        {
            float headYaw = headCamera ? headCamera.transform.localEulerAngles.y : 0f;
            transform.rotation = Quaternion.Euler(0f, yaw - headYaw, 0f);
            Vector3 headOffset = HeadPosition - transform.position;
            headOffset.y = 0f;
            locomotion.Teleport(feet - headOffset);
            BodyYaw = yaw;
        }

        public void Haptic(Hand h, float amplitude, float duration) => Input?.Haptic(h, amplitude, duration);
    }
}
