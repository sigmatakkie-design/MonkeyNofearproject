using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Items
{
    /// <summary>A hanging rope: thin visual cylinder plus a slightly fatter climbable capsule.</summary>
    public class DeployedRope : MonoBehaviour, IExpeditionReset
    {
        static readonly List<DeployedRope> All = new List<DeployedRope>();

        public static DeployedRope Create(Vector3 top, Vector3 bottom, Material mat)
        {
            var go = new GameObject("DeployedRope");
            var rope = go.AddComponent<DeployedRope>();
            float len = Vector3.Distance(top, bottom);
            go.transform.position = (top + bottom) * 0.5f;
            go.layer = Layers.Environment;

            var vis = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            Object.Destroy(vis.GetComponent<Collider>());
            vis.transform.SetParent(go.transform, false);
            vis.transform.localScale = new Vector3(0.035f, len * 0.5f, 0.035f);
            if (mat) vis.GetComponent<Renderer>().sharedMaterial = mat;

            var col = go.AddComponent<CapsuleCollider>();
            col.direction = 1;
            col.radius = 0.06f;
            col.height = len;
            var s = go.AddComponent<Surface>();
            s.kind = Data.SurfaceKind.Wood;
            return rope;
        }

        void OnEnable() { All.Add(this); ExpeditionManager.Register(this); }
        void OnDisable() { All.Remove(this); ExpeditionManager.Unregister(this); }

        public void OnNewExpedition(int index, System.Random rng) => Destroy(gameObject);
    }
}
