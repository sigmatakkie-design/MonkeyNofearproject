using UnityEngine;

namespace MonkeyNoFear.Data
{
    /// <summary>Tunable numbers shared by all creature brains. Behaviour-specific values live on the
    /// creature components themselves (also Inspector-editable).</summary>
    [CreateAssetMenu(menuName = "Monkey No Fear/Creature Profile", fileName = "Creature_")]
    public class CreatureProfile : ScriptableObject
    {
        public string id;
        public string displayName;
        [TextArea] public string bestiaryEntry;

        [Header("Health")]
        public float maxHealth = 200f;
        [Tooltip("Multiplier on incoming spear/tool damage.")]
        public float weaponVulnerability = 1f;
        [Tooltip("Damage within 2 s that causes a stagger.")]
        public float staggerThreshold = 30f;
        public bool killable;

        [Header("Movement")]
        public float walkSpeed = 0.8f;
        public float alertSpeed = 1.6f;
        public float runSpeed = 5f;
        public float turnSpeed = 180f;
        public float acceleration = 8f;

        [Header("Senses")]
        [Tooltip("Noises are heard up to their radius × this.")]
        public float hearingSensitivity = 1f;
        public float sightRange = 25f;
        [Range(10, 360)] public float sightFov = 110f;
        [Tooltip("Within this range the player is sensed regardless of facing.")]
        public float proximitySense = 2.5f;
        public float awarenessDecay = 6f;

        [Header("Attack")]
        public float attackRange = 2.4f;
        public float attackDamage = 35f;
        public float attackWindup = 0.7f;
        public float attackCooldown = 3f;
        [Tooltip("Seconds the creature backs off after landing a hit (gives the player a window to react).")]
        public float postHitRecovery = 1.6f;

        [Header("Persistence")]
        public float loseInterestTime = 9f;
        public float searchTime = 14f;
        public float activationDistance = 110f;
    }
}
