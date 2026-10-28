using UnityEngine;

namespace MonkeyNoFear.Player
{
    /// <summary>
    /// Drives the supplied monkey rig (torso → neck → head, backarm → forearm → hand) from VR tracking:
    ///  * the model is translated so its eyes sit exactly at the HMD camera (camera never detaches)
    ///  * head follows HMD rotation, neck takes part of it, torso follows body yaw and leans with pitch
    ///  * each arm is a two-bone IK chain to the collision-limited physics hand, elbow hinted down/out/back
    ///  * small controlled stretch (≤ maxStretch) when the target is beyond reach, never bone explosions
    ///  * hand bones take the controller rotation through a rest-pose frame mapping
    ///  * the head is collapsed for the first-person camera (configurable)
    /// Bone names default to the supplied model; change them in the Inspector for another rig.
    /// </summary>
    [DefaultExecutionOrder(100)]
    public class PlayerAvatar : MonoBehaviour
    {
        public PlayerRig rig;
        public Transform modelRoot;

        [Header("Bones (supplied model names)")]
        public string torsoBone = "torso";
        public string neckBone = "neck";
        public string headBone = "head";
        public string leftUpperBone = "left backarm";
        public string leftForeBone = "left forearm";
        public string leftHandBone = "left hand";
        public string rightUpperBone = "right backarm";
        public string rightForeBone = "right forearm";
        public string rightHandBone = "right hand";

        [Header("Fit")]
        [Tooltip("Eye point in model space (rest pose, before scaling). The camera sits here.")]
        public Vector3 eyeInModel = new Vector3(0f, 0.25f, 0.05f);
        public float scale = 1f;
        [Range(0, 1)] public float neckShare = 0.35f;
        [Range(0, 1)] public float torsoLeanFromPitch = 0.25f;
        [Tooltip("Distance from palm centre back to the wrist joint.")]
        public float wristBack = 0.07f;
        [Range(1f, 1.3f)] public float maxStretch = 1.12f;
        public Vector3 leftHandRotationOffset;
        public Vector3 rightHandRotationOffset;
        [Tooltip("Collapse the head for the local first-person camera.")]
        public bool hideHeadInFirstPerson = true;

        class Arm
        {
            public Transform upper, fore, hand;
            public float a, b;
            public Vector3 foreRestLocalPos, handRestLocalPos;
            public Quaternion restFrameModel;   // LookRotation(pointDir, backOfHandDir) in model space
            public Quaternion handRestModel;    // hand bone rotation in model space
            public float side;                  // -1 left, +1 right (model X)
        }

        Transform _torso, _neck, _head;
        Arm _left, _right;
        Transform[] _bones;
        Quaternion[] _restRot;
        Vector3[] _restPos;
        Quaternion _headRestModel, _neckRestModel;
        Vector3 _eyeInHeadLocal;
        bool _ok;

        void Start() { Setup(); }

        public void Setup()
        {
            if (!modelRoot) { Debug.LogError("[PlayerAvatar] No model assigned"); return; }
            _torso = Find(torsoBone); _neck = Find(neckBone); _head = Find(headBone);
            _left = MakeArm(leftUpperBone, leftForeBone, leftHandBone, -1f);
            _right = MakeArm(rightUpperBone, rightForeBone, rightHandBone, 1f);
            if (!_head || _left == null || _right == null)
            {
                Debug.LogError("[PlayerAvatar] Required bones not found on the player model — check the bone names.");
                return;
            }
            _bones = modelRoot.GetComponentsInChildren<Transform>(true);
            _restRot = new Quaternion[_bones.Length];
            _restPos = new Vector3[_bones.Length];
            for (int i = 0; i < _bones.Length; i++) { _restRot[i] = _bones[i].localRotation; _restPos[i] = _bones[i].localPosition; }
            var inv = Quaternion.Inverse(modelRoot.rotation);
            _headRestModel = inv * _head.rotation;
            _neckRestModel = _neck ? inv * _neck.rotation : Quaternion.identity;
            _eyeInHeadLocal = _head.InverseTransformPoint(modelRoot.TransformPoint(eyeInModel));
            foreach (var r in modelRoot.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                r.updateWhenOffscreen = true; // the model is always next to the camera
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            }
            _ok = true;
        }

        Arm MakeArm(string u, string f, string h, float side)
        {
            var arm = new Arm { upper = Find(u), fore = Find(f), hand = Find(h), side = side };
            if (!arm.upper || !arm.fore || !arm.hand) return null;
            arm.a = Vector3.Distance(arm.upper.position, arm.fore.position) / Mathf.Max(0.0001f, modelRoot.lossyScale.x);
            arm.b = Vector3.Distance(arm.fore.position, arm.hand.position) / Mathf.Max(0.0001f, modelRoot.lossyScale.x);
            arm.foreRestLocalPos = arm.fore.localPosition;
            arm.handRestLocalPos = arm.hand.localPosition;
            var inv = Quaternion.Inverse(modelRoot.rotation);
            Vector3 point = inv * (arm.hand.position - arm.fore.position).normalized;
            // T-pose: back of the hand faces up
            Vector3 back = Vector3.ProjectOnPlane(Vector3.up, point).normalized;
            arm.restFrameModel = Quaternion.LookRotation(point, back);
            arm.handRestModel = inv * arm.hand.rotation;
            return arm;
        }

        Transform Find(string n)
        {
            if (string.IsNullOrEmpty(n)) return null;
            foreach (var t in modelRoot.GetComponentsInChildren<Transform>(true)) if (t.name == n) return t;
            return null;
        }

        void LateUpdate()
        {
            if (!_ok || !rig || !rig.headCamera) return;
            for (int i = 0; i < _bones.Length; i++) { _bones[i].localRotation = _restRot[i]; _bones[i].localPosition = _restPos[i]; }

            var rootRot = Quaternion.Euler(0f, rig.BodyYaw, 0f);
            modelRoot.rotation = rootRot;
            modelRoot.localScale = Vector3.one * scale;

            var headRot = rig.HeadRotation;
            var fwd = headRot * Vector3.forward;
            float pitch = Mathf.Asin(Mathf.Clamp(-fwd.y, -1f, 1f)) * Mathf.Rad2Deg; // + looking down
            if (_torso) _torso.rotation = Quaternion.AngleAxis(pitch * torsoLeanFromPitch, rootRot * Vector3.right) * _torso.rotation;
            if (_neck) _neck.rotation = Quaternion.Slerp(_neck.rotation, headRot * _neckRestModel, neckShare);
            _head.rotation = headRot * _headRestModel;

            // eyes onto the camera
            modelRoot.position += rig.headCamera.transform.position - _head.TransformPoint(_eyeInHeadLocal);

            SolveArm(_left, Hand.Left, rootRot, leftHandRotationOffset);
            SolveArm(_right, Hand.Right, rootRot, rightHandRotationOffset);

            _head.localScale = hideHeadInFirstPerson ? Vector3.one * 0.001f : Vector3.one;
        }

        void SolveArm(Arm arm, Hand h, Quaternion rootRot, Vector3 rotOffset)
        {
            var ph = rig.GetHand(h);
            Quaternion ctrl = ph.Rotation * Quaternion.Euler(rotOffset);
            Quaternion ctrlFrame = ctrl * Quaternion.LookRotation(Vector3.forward, h == Hand.Left ? Vector3.left : Vector3.right);
            Quaternion handRot = ctrlFrame * Quaternion.Inverse(arm.restFrameModel) * arm.handRestModel;

            Vector3 point = ctrl * Vector3.forward;
            Vector3 wrist = ph.Position - point * wristBack * scale;

            float s = scale;
            float A = arm.a * s, B = arm.b * s;
            Vector3 S = arm.upper.position;
            Vector3 toT = wrist - S;
            float d = toT.magnitude;
            float stretch = Mathf.Clamp(d / (A + B), 1f, maxStretch);
            if (stretch > 1f)
            {
                A *= stretch; B *= stretch;
                arm.fore.localPosition = arm.foreRestLocalPos * stretch;
                arm.hand.localPosition = arm.handRestLocalPos * stretch;
            }
            d = Mathf.Clamp(d, Mathf.Abs(A - B) + 0.001f, A + B - 0.001f);
            Vector3 dir = toT.sqrMagnitude > 1e-8f ? toT.normalized : rootRot * Vector3.down;

            Vector3 hint = rootRot * new Vector3(arm.side * 0.6f, -1f, -0.35f);
            Vector3 pole = Vector3.ProjectOnPlane(hint, dir);
            if (pole.sqrMagnitude < 1e-6f) pole = Vector3.ProjectOnPlane(rootRot * Vector3.back, dir);
            pole.Normalize();

            float cosA = Mathf.Clamp((A * A + d * d - B * B) / (2f * A * d), -1f, 1f);
            float sinA = Mathf.Sqrt(1f - cosA * cosA);
            Vector3 elbow = S + dir * (A * cosA) + pole * (A * sinA);
            Vector3 target = S + dir * d;

            arm.upper.rotation = Quaternion.FromToRotation(arm.fore.position - S, elbow - S) * arm.upper.rotation;
            arm.fore.rotation = Quaternion.FromToRotation(arm.hand.position - arm.fore.position, target - arm.fore.position) * arm.fore.rotation;
            arm.hand.rotation = handRot;
        }
    }
}
