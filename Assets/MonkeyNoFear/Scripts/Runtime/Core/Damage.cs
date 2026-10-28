using UnityEngine;

namespace MonkeyNoFear.Core
{
    public enum DamageType { Generic, Melee, Stab, Fall, Crush, Bite, Drain, Mining }

    public struct DamageInfo
    {
        public float amount;
        public Vector3 sourcePosition;
        public DamageType type;
        public Object instigator;
        public Vector3 hitPoint;
        public Vector3 direction;
        /// <summary>Tool tier (spear/pick) for creature-specific responses.</summary>
        public int tier;

        public DamageInfo(float amount, Vector3 source, DamageType type, Object instigator = null)
        {
            this.amount = amount; sourcePosition = source; this.type = type; this.instigator = instigator;
            hitPoint = source; direction = Vector3.zero; tier = 0;
        }
    }

    /// <summary>Creatures, animals, breakables. Return true if the hit had an effect.</summary>
    public interface IDamageable
    {
        bool TakeDamage(DamageInfo info);
        bool IsAlive { get; }
    }
}
