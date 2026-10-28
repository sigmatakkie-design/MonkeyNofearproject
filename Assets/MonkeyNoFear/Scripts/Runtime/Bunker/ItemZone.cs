using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Bunker
{
    /// <summary>Box volume that collects the loose (not held, not stowed) items currently inside it.
    /// Polls the ItemInstance registry instead of relying on trigger callbacks.</summary>
    [System.Serializable]
    public class ItemZone
    {
        public Transform frame;
        public Vector3 center;
        public Vector3 size = new Vector3(0.6f, 0.5f, 0.5f);

        public bool Contains(Vector3 world)
        {
            if (!frame) return false;
            var l = frame.InverseTransformPoint(world) - center;
            var h = size * 0.5f;
            return Mathf.Abs(l.x) <= h.x && Mathf.Abs(l.y) <= h.y && Mathf.Abs(l.z) <= h.z;
        }

        public void Collect(List<ItemInstance> into)
        {
            into.Clear();
            foreach (var i in ItemInstance.All)
            {
                if (!i || !i.isActiveAndEnabled || !i.definition) continue;
                var g = i.Grab;
                if (g && (g.IsHeld || g.Holster)) continue;
                if (Contains(i.transform.position)) into.Add(i);
            }
        }

        public void DrawGizmo(Color c)
        {
            if (!frame) return;
            Gizmos.matrix = frame.localToWorldMatrix;
            Gizmos.color = c;
            Gizmos.DrawWireCube(center, size);
        }
    }
}
