using UnityEngine;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.Items
{
    /// <summary>Shared impact evaluation for swung/stabbed tools: a contact only counts as a strike when it
    /// is fast enough, lands near the business end and travels in the tool's striking direction. Accidental
    /// touches therefore never mine or damage anything.</summary>
    public static class ToolStrike
    {
        public struct Result
        {
            public bool valid;
            public float speed;
            public Vector3 point, normal;
            public Collider other;
        }

        /// <param name="strikeDir">tool-local direction the business end moves when striking</param>
        public static Result Evaluate(Collision c, Grabbable grab, Transform tip, Vector3 strikeDirLocal,
            float minSpeed, float tipRadius, float minAlignment)
        {
            var r = new Result();
            int n = c.contactCount;
            if (n == 0) return r;
            // contact order is arbitrary (the handle may touch first): judge the one nearest the business end
            var contact = c.GetContact(0);
            if (tip)
            {
                float best = (contact.point - tip.position).sqrMagnitude;
                for (int i = 1; i < n; i++)
                {
                    var ci = c.GetContact(i);
                    float d = (ci.point - tip.position).sqrMagnitude;
                    if (d < best) { best = d; contact = ci; }
                }
            }
            r.point = contact.point;
            r.normal = contact.normal;
            r.other = c.collider;
            Vector3 at = tip ? tip.position : (grab ? grab.transform.position : contact.point);
            Vector3 v;
            if (grab && grab.IsHeld)
            {
                // held: only the controller-driven motion counts. The velocity-tracked body (and therefore
                // relativeVelocity) is large whenever the hand presses the tool into a surface, so a touch
                // or a lean would otherwise read as a strike.
                v = grab.TargetPointVelocity(at);
                r.speed = v.magnitude;
            }
            else
            {
                // thrown: real flight speed (point velocity is post-solve, relativeVelocity is pre-solve)
                v = grab ? grab.Body.GetPointVelocity(at) : Vector3.zero;
                r.speed = Mathf.Max(c.relativeVelocity.magnitude, v.magnitude);
            }
            if (r.speed < minSpeed) return r;
            if (tip && (contact.point - tip.position).sqrMagnitude > tipRadius * tipRadius) return r;
            Vector3 strikeWorld = grab ? grab.transform.TransformDirection(strikeDirLocal) : Vector3.down;
            if (v.sqrMagnitude > 0.01f && Vector3.Dot(v.normalized, strikeWorld) < minAlignment) return r;
            r.valid = true;
            return r;
        }

        public static void Haptic(Grabbable g, float strength)
        {
            if (g && g.Holder && g.Holder.Rig) g.Holder.Rig.Haptic(g.Holder.Side, Mathf.Clamp01(strength), 0.06f + strength * 0.06f);
        }
    }
}
