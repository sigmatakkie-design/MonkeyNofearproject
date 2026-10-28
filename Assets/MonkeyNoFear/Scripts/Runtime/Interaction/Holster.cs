using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;

namespace MonkeyNoFear.Interaction
{
    /// <summary>Body-mounted slot (hips, chest strap). Lives under PlayerRig/BodyFrame so it follows the
    /// player's head height and body yaw. Holds one holsterable item.</summary>
    public class Holster : MonoBehaviour
    {
        static readonly List<Holster> All = new List<Holster>();

        public float radius = 0.2f;
        public Vector3 itemLocalEuler = new Vector3(90f, 0f, 0f);
        [Tooltip("Tool rack socket: accepts any item, not only holsterable ones.")]
        public bool acceptAnyItem;
        [Tooltip("Head slot: only accepts head-mounted lights.")]
        public bool headSlot;
        public Grabbable Content { get; private set; }

        void OnEnable() { if (!All.Contains(this)) All.Add(this); }
        void OnDisable() => All.Remove(this);

        public static Holster FindNear(Vector3 p, bool requireContent)
        {
            Holster best = null;
            float bestD = float.MaxValue;
            foreach (var h in All)
            {
                if (requireContent != (h.Content != null)) continue;
                float d = (h.transform.position - p).sqrMagnitude;
                if (d < h.radius * h.radius && d < bestD) { bestD = d; best = h; }
            }
            return best;
        }

        public bool Accepts(Grabbable g)
        {
            if (Content != null || !g) return false;
            var lamp = g.GetComponent<Items.Flashlight>();
            bool headLamp = lamp && lamp.headMounted;
            if (headSlot) return headLamp;
            if (headLamp && !acceptAnyItem) return false;
            return acceptAnyItem ? g.Item != null : g.holsterable;
        }

        public void Insert(Grabbable g)
        {
            Content = g;
            g.Holster = this;
            g.MakeStowed(transform);
            var grip = g.gripPoint ? g.transform.InverseTransformPoint(g.gripPoint.position) : Vector3.zero;
            g.transform.localRotation = Quaternion.Euler(itemLocalEuler);
            g.transform.localPosition = -(g.transform.localRotation * grip);
            AudioManager.Instance?.PlayAt("holster_snap", transform.position, 0.6f);
        }

        /// <summary>Place an item without sound (initial rack fill / tool recall).</summary>
        public void InsertSilently(Grabbable g)
        {
            Content = g;
            g.Holster = this;
            g.MakeStowed(transform);
            var grip = g.gripPoint ? g.transform.InverseTransformPoint(g.gripPoint.position) : Vector3.zero;
            g.transform.localRotation = Quaternion.Euler(itemLocalEuler);
            g.transform.localPosition = -(g.transform.localRotation * grip);
        }

        public void Remove(Grabbable g)
        {
            if (Content != g) return;
            Content = null;
            g.Holster = null;
            g.MakeLoose();
        }

        void OnDrawGizmos()
        {
            Gizmos.color = Content ? new Color(0, 1, 0, 0.4f) : new Color(1, 1, 0, 0.25f);
            Gizmos.DrawWireSphere(transform.position, radius);
        }
    }
}
