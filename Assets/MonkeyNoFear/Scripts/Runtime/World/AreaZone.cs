using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.World
{
    /// <summary>Box volume that defines an area. Uses its BoxCollider bounds (trigger, never collides).</summary>
    [RequireComponent(typeof(BoxCollider))]
    public class AreaZone : MonoBehaviour
    {
        public AreaId area;
        [Tooltip("Higher wins where zones overlap (e.g. a corridor inside the forest bounds).")]
        public int priority;
        BoxCollider _box;

        void Awake()
        {
            _box = GetComponent<BoxCollider>();
            _box.isTrigger = true;
            gameObject.layer = Layers.Trigger;
        }

        void OnEnable() => AreaManager.RegisterZone(this);
        void OnDisable() => AreaManager.UnregisterZone(this);

        public bool Contains(Vector3 p)
        {
            if (!_box) _box = GetComponent<BoxCollider>();
            var local = transform.InverseTransformPoint(p) - _box.center;
            var h = _box.size * 0.5f;
            return Mathf.Abs(local.x) <= h.x && Mathf.Abs(local.y) <= h.y && Mathf.Abs(local.z) <= h.z;
        }

        void OnDrawGizmos()
        {
            var b = GetComponent<BoxCollider>();
            if (!b) return;
            Gizmos.matrix = transform.localToWorldMatrix;
            Gizmos.color = new Color(0.2f, 0.8f, 1f, 0.15f);
            Gizmos.DrawCube(b.center, b.size);
        }
    }
}
