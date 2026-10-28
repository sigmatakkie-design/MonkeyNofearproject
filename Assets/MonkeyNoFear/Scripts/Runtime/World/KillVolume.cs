using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.World
{
    /// <summary>Bottomless drops / out-of-world areas: the player is returned to the last safe position
    /// (with damage, so falls still matter) instead of falling forever.</summary>
    [RequireComponent(typeof(BoxCollider))]
    public class KillVolume : MonoBehaviour
    {
        public float damage = 30f;
        BoxCollider _box;
        float _cool;

        void Awake() { _box = GetComponent<BoxCollider>(); _box.isTrigger = true; gameObject.layer = Layers.Trigger; }

        void Update()
        {
            var rig = PlayerRig.Instance;
            _cool -= Time.deltaTime;
            if (!rig || _cool > 0f) return;
            var local = transform.InverseTransformPoint(rig.HeadPosition) - _box.center;
            var h = _box.size * 0.5f;
            if (Mathf.Abs(local.x) > h.x || Mathf.Abs(local.y) > h.y || Mathf.Abs(local.z) > h.z) return;
            _cool = 2f;
            rig.locomotion.RecoverToSafePosition();
            PlayerHealth.Instance?.TakeDamage(new DamageInfo(damage, rig.HeadPosition, DamageType.Fall, this));
        }
    }
}
