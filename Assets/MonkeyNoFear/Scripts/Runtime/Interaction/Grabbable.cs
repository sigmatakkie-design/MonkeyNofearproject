using System;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.Interaction
{
    /// <summary>Something a hand can grab: loose items, tools, levers, cranks.</summary>
    public interface IGrabInteractable
    {
        bool CanGrab(HandGrabber hand);
        void BeginGrab(HandGrabber hand);
        void UpdateGrab(HandGrabber hand, float dt);
        void EndGrab(HandGrabber hand);
        Transform transform { get; }
    }

    /// <summary>Held-item actions mapped from the controller (trigger, face buttons).</summary>
    public interface IUsable
    {
        void OnTrigger(HandGrabber hand, bool pressed);
        void OnTriggerHeld(HandGrabber hand, float value, float dt);
        void OnPrimary(HandGrabber hand);
    }

    /// <summary>
    /// Physics item that follows the hand by velocity tracking (so it still collides with the world: a held
    /// pickaxe really hits the rock, a held spear really stops at a wall). Tools snap to their GRIP point;
    /// other items keep the offset they were grabbed with.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class Grabbable : MonoBehaviour, IGrabInteractable
    {
        public enum GrabMode { SnapToGrip, KeepOffset }

        public GrabMode mode = GrabMode.KeepOffset;
        [Tooltip("Grip point (child named GRIP). Defaults to the object origin.")]
        public Transform gripPoint;
        public Vector3 gripRotationOffset;
        [Tooltip("Can be stored in a hip/chest holster.")]
        public bool holsterable;
        public float throwMultiplier = 1.25f;
        public float maxFollowSpeed = 25f;
        [Tooltip("If the item is held back by geometry further than this from the hand, it snaps back.")]
        public float breakDistance = 0.55f;
        [Tooltip("Impact sound/noise when the item hits something while loose.")]
        public bool impactNoise = true;

        public HandGrabber Holder { get; private set; }
        public bool IsHeld => Holder != null;
        public Holster Holster { get; internal set; }
        public Rigidbody Body { get; private set; }
        public ItemInstance Item { get; private set; }

        public event Action<HandGrabber> Grabbed;
        public event Action<HandGrabber> Released;

        /// <summary>Velocity of the hand-driven target pose while held: what the controller does, not what
        /// the body was allowed to do. Pressing a held tool into a surface gives zero here.</summary>
        public Vector3 TargetVelocity { get; private set; }
        public Vector3 TargetAngularVelocity { get; private set; }

        int[] _layers;
        Transform[] _layerTargets;
        Vector3 _attachPos;
        Quaternion _attachRot = Quaternion.identity;
        float _lastImpact;
        Vector3 _lastTargetPos;
        Quaternion _lastTargetRot = Quaternion.identity;
        bool _hasTarget;

        void Awake()
        {
            Body = GetComponent<Rigidbody>();
            Item = GetComponent<ItemInstance>();
            if (!gripPoint) gripPoint = transform.Find("GRIP");
            Body.interpolation = RigidbodyInterpolation.Interpolate;
        }

        public virtual bool CanGrab(HandGrabber hand) => enabled && gameObject.activeInHierarchy;

        public virtual void BeginGrab(HandGrabber hand)
        {
            if (Holder != null && Holder != hand) Holder.ForceRelease(); // hand-to-hand swap
            if (Holster) Holster.Remove(this);
            Holder = hand;
            transform.SetParent(null, true);
            CacheAndSetLayer(Layers.HeldItem);
            Body.isKinematic = false;
            Body.useGravity = false;
            Body.collisionDetectionMode = CollisionDetectionMode.ContinuousDynamic;

            var handRot = hand.HandRotation;
            if (mode == GrabMode.SnapToGrip)
            {
                var gp = gripPoint ? transform.InverseTransformPoint(gripPoint.position) : Vector3.zero;
                var gr = gripPoint ? Quaternion.Inverse(transform.rotation) * gripPoint.rotation : Quaternion.identity;
                _attachRot = Quaternion.Euler(gripRotationOffset) * Quaternion.Inverse(gr);
                _attachPos = -(_attachRot * gp);
            }
            else
            {
                _attachRot = Quaternion.Inverse(handRot) * transform.rotation;
                _attachPos = Quaternion.Inverse(handRot) * (transform.position - hand.HandPosition);
            }
            Grabbed?.Invoke(hand);
        }

        public virtual void UpdateGrab(HandGrabber hand, float dt) { }

        /// <summary>Hand-driven velocity of a point on the item (world space), for strike validation.</summary>
        public Vector3 TargetPointVelocity(Vector3 worldPoint)
        {
            if (Holder == null || !_hasTarget) return Vector3.zero;
            // the point's offset from the body, carried over to the target pose
            var offset = _lastTargetRot * (Quaternion.Inverse(transform.rotation) * (worldPoint - transform.position));
            return TargetVelocity + Vector3.Cross(TargetAngularVelocity, offset);
        }

        void Update()
        {
            // render rate, after PlayerRig (-50) has resolved the hands for this frame
            if (Holder == null) { _hasTarget = false; TargetVelocity = TargetAngularVelocity = Vector3.zero; return; }
            var rot = Holder.HandRotation * _attachRot;
            var pos = Holder.HandPosition + Holder.HandRotation * _attachPos;
            float dt = Time.deltaTime;
            if (_hasTarget && dt > 0f && (pos - _lastTargetPos).sqrMagnitude < 1f) // ignore snap turns / teleports
            {
                TargetVelocity = Vector3.Lerp(TargetVelocity, (pos - _lastTargetPos) / dt, 0.5f);
                (rot * Quaternion.Inverse(_lastTargetRot)).ToAngleAxis(out float angle, out Vector3 axis);
                if (angle > 180f) angle -= 360f;
                var w = Mathf.Abs(angle) > 0.01f && !float.IsInfinity(axis.x) && !float.IsNaN(axis.x) ? axis * (angle * Mathf.Deg2Rad / dt) : Vector3.zero;
                TargetAngularVelocity = Vector3.Lerp(TargetAngularVelocity, w, 0.5f);
            }
            else { TargetVelocity = Vector3.zero; TargetAngularVelocity = Vector3.zero; }
            _lastTargetPos = pos; _lastTargetRot = rot; _hasTarget = true;
        }

        void FixedUpdate()
        {
            if (Holder == null) return;
            var targetRot = Holder.HandRotation * _attachRot;
            var targetPos = Holder.HandPosition + Holder.HandRotation * _attachPos;
            float dt = Time.fixedDeltaTime;

            if ((Body.position - targetPos).sqrMagnitude > breakDistance * breakDistance)
            {
                Body.position = targetPos;
                Body.rotation = targetRot;
                Body.velocity = Vector3.zero;
                Body.angularVelocity = Vector3.zero;
                return;
            }
            var v = (targetPos - Body.position) / dt;
            Body.velocity = Vector3.ClampMagnitude(v, maxFollowSpeed);
            var dq = targetRot * Quaternion.Inverse(Body.rotation);
            dq.ToAngleAxis(out float angle, out Vector3 axis);
            if (angle > 180f) angle -= 360f;
            if (Mathf.Abs(angle) > 0.01f && !float.IsInfinity(axis.x))
                Body.angularVelocity = Vector3.ClampMagnitude(axis * (angle * Mathf.Deg2Rad / dt), 40f);
            else Body.angularVelocity = Vector3.zero;
        }

        public virtual void EndGrab(HandGrabber hand)
        {
            if (Holder != hand) return;
            Holder = null;
            RestoreLayer();
            Body.useGravity = true;
            Body.collisionDetectionMode = CollisionDetectionMode.ContinuousSpeculative;
            Body.velocity = hand.ThrowVelocity * throwMultiplier;
            Body.angularVelocity = Vector3.ClampMagnitude(Body.angularVelocity, 20f);
            Released?.Invoke(hand);
        }

        /// <summary>Put into a holster / backpack: kinematic, parented, no collisions with the player.</summary>
        public void MakeStowed(Transform parent)
        {
            if (Holder != null) Holder.ForceRelease();
            Body.isKinematic = true;
            Body.useGravity = false;
            transform.SetParent(parent, false);
            CacheAndSetLayer(Layers.HeldItem);
        }

        public void MakeLoose()
        {
            transform.SetParent(null, true);
            RestoreLayer();
            Body.isKinematic = false;
            Body.useGravity = true;
        }

        void CacheAndSetLayer(int layer)
        {
            if (_layers == null)
            {
                var all = GetComponentsInChildren<Transform>(true);
                _layers = new int[all.Length];
                _layerTargets = all;
                for (int i = 0; i < all.Length; i++) _layers[i] = all[i].gameObject.layer;
            }
            foreach (var t in _layerTargets) if (t) t.gameObject.layer = layer;
        }

        void RestoreLayer()
        {
            if (_layers == null) return;
            for (int i = 0; i < _layerTargets.Length; i++) if (_layerTargets[i]) _layerTargets[i].gameObject.layer = _layers[i];
        }

        void OnCollisionEnter(Collision c)
        {
            if (!impactNoise || IsHeld) return;
            float s = c.relativeVelocity.magnitude;
            if (s < 1.2f || Time.time - _lastImpact < 0.15f) return;
            _lastImpact = Time.time;
            var kind = Item && Item.definition ? Item.definition.dropSurface : Data.SurfaceKind.Rock;
            AudioManager.Instance?.PlayAt(World.Surface.DropSound(kind), transform.position, Mathf.Clamp01(s / 6f));
            float loud = Mathf.Clamp(s * 0.08f, 0.05f, 0.6f) * (kind == Data.SurfaceKind.Metal ? 1.6f : 1f);
            AI.NoiseSystem.Emit(transform.position, loud, kind == Data.SurfaceKind.Metal ? AI.NoiseKind.MetalImpact : AI.NoiseKind.ItemDrop, true, this);
        }
    }
}
