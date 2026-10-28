using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.Interaction
{
    /// <summary>
    /// Grip to grab whatever is under the palm (item, lever, holstered tool, or — reaching over the
    /// shoulder — the last thing in the backpack). Releasing over the shoulder stores the item, releasing
    /// near a hip/chest holster holsters a tool, anywhere else drops or throws it. Trigger and the face
    /// buttons are forwarded to the held item.
    /// </summary>
    public class HandGrabber : MonoBehaviour
    {
        public float grabRadius = 0.11f;
        public float gripPress = 0.6f;
        public float gripRelease = 0.35f;
        public float triggerPress = 0.6f;
        public float triggerRelease = 0.35f;

        public PlayerRig Rig { get; private set; }
        public PhysicsHand Hand { get; private set; }
        public Hand Side => Hand ? Hand.hand : Player.Hand.Right;
        public IGrabInteractable Held { get; private set; }
        public Grabbable HeldGrabbable => Held as Grabbable;
        public Vector3 HandPosition => Hand ? Hand.Position : transform.position;
        public Quaternion HandRotation => Hand ? Hand.Rotation : transform.rotation;
        public Vector3 ThrowVelocity => (Hand ? Hand.ControllerVelocity : Vector3.zero) + (Rig ? Rig.locomotion.Velocity : Vector3.zero);
        public bool GripDown { get; private set; }
        public bool TriggerDown { get; private set; }

        readonly Collider[] _hits = new Collider[16];
        bool _primaryWas;

        public void Init(PlayerRig rig, PhysicsHand hand) { Rig = rig; Hand = hand; }

        public void Tick(float dt)
        {
            if (!Rig) return;
            var c = Rig.Controller(Side);

            bool grip = GripDown ? c.grip > gripRelease : c.grip > gripPress;
            if (grip && !GripDown) TryGrab();
            else if (!grip && GripDown) Release();
            GripDown = grip;

            if (Held != null)
            {
                if (Held.transform == null || !Held.transform.gameObject.activeInHierarchy) { Held = null; }
                else
                {
                    Held.UpdateGrab(this, dt);
                    var usable = Held.transform.GetComponent<IUsable>();
                    bool trig = TriggerDown ? c.trigger > triggerRelease : c.trigger > triggerPress;
                    if (usable != null)
                    {
                        if (trig != TriggerDown) usable.OnTrigger(this, trig);
                        usable.OnTriggerHeld(this, c.trigger, dt);
                        if (c.primary && !_primaryWas) usable.OnPrimary(this);
                    }
                    TriggerDown = trig;
                }
            }
            else TriggerDown = false;
            _primaryWas = c.primary;
        }

        void TryGrab()
        {
            var palm = HandPosition;
            // 1. something physically under the palm
            IGrabInteractable best = null;
            float bestD = float.MaxValue;
            int n = Physics.OverlapSphereNonAlloc(palm, grabRadius, _hits, Layers.Grabbables, QueryTriggerInteraction.Collide);
            for (int i = 0; i < n; i++)
            {
                var gi = _hits[i].GetComponentInParent<IGrabInteractable>();
                if (gi == null || !gi.CanGrab(this)) continue;
                if (gi is Grabbable g && g.IsHeld && g.Holder != this) { /* allowed: hand swap */ }
                float d = (_hits[i].ClosestPoint(palm) - palm).sqrMagnitude;
                if (d < bestD) { bestD = d; best = gi; }
            }
            // 2. holstered tool
            if (best == null)
            {
                var h = Holster.FindNear(palm, true);
                if (h && h.Content) best = h.Content;
            }
            // 3. reach over the shoulder into the backpack
            if (best == null && Backpack.Instance && Backpack.Instance.IsInZone(palm))
            {
                var item = Backpack.Instance.TakeLast(palm, HandRotation);
                if (item) best = item;
                else AudioManager.Instance?.PlayAt("backpack_take", palm, 0.3f);
            }
            if (best == null) return;
            Held = best;
            best.BeginGrab(this);
            Rig.Haptic(Side, 0.3f, 0.04f);
            AudioManager.Instance?.PlayAt("grab", palm, 0.5f);
        }

        void Release()
        {
            if (Held == null) return;
            var held = Held;
            Held = null;
            var g = held as Grabbable;
            var palm = HandPosition;
            if (g)
            {
                if (Backpack.Instance && Backpack.Instance.IsInZone(palm) && Backpack.Instance.CanStore(g))
                {
                    held.EndGrab(this);
                    Backpack.Instance.Store(g);
                    Rig.Haptic(Side, 0.4f, 0.06f);
                    return;
                }
                var h = Holster.FindNear(palm, false);
                if (h && h.Accepts(g))
                {
                    held.EndGrab(this);
                    h.Insert(g);
                    Rig.Haptic(Side, 0.35f, 0.05f);
                    return;
                }
            }
            held.EndGrab(this);
        }

        /// <summary>Release without throw velocity (item taken by the other hand, stowed, destroyed).</summary>
        public void ForceRelease()
        {
            if (Held == null) return;
            var h = Held;
            Held = null;
            h.EndGrab(this);
        }

        void OnDrawGizmosSelected()
        {
            Gizmos.color = Held != null ? Color.green : Color.white;
            Gizmos.DrawWireSphere(HandPosition, grabRadius);
        }
    }
}
