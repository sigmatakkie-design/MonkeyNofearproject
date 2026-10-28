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
            if (c.contactCount == 0) return r;
            var contact = c.GetContact(0);
            r.point = contact.point;
            r.normal = contact.normal;
            r.other = c.collider;
            Vector3 handVel = grab && grab.Holder && grab.Holder.Hand ? grab.Holder.Hand.ControllerVelocity : Vector3.zero;
            // the tip moves faster than the hand: approximate with rigidbody point velocity before the solver resolved it
            Vector3 tipVel = grab ? grab.Body.GetPointVelocity(tip ? tip.position : grab.transform.position) : Vector3.zero;
            Vector3 v = tipVel.sqrMagnitude > handVel.sqrMagnitude ? tipVel : handVel;
            r.speed = Mathf.Max(c.relativeVelocity.magnitude, v.magnitude);
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
