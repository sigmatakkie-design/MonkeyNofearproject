using UnityEngine;
using MonkeyNoFear.AI;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Mining;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Items
{
    /// <summary>
    /// Swing the pick into a deposit: only fast strikes that land with the pointed tip, travelling in the
    /// tip's direction, count. Higher tiers mine faster, can break harder minerals, and the Resonance pick
    /// is quieter. Also a weak weapon.
    /// </summary>
    [RequireComponent(typeof(Grabbable))]
    public class Pickaxe : MonoBehaviour
    {
        [Range(1, 3)] public int tier = 1;
        public float damage = 22f;
        [Tooltip("Strike speed (m/s) needed to count as a hit.")]
        public float minStrikeSpeed = 2.2f;
        [Tooltip("Speed at which a strike does full damage.")]
        public float fullDamageSpeed = 5f;
        public float noiseMultiplier = 1f;
        public float cooldown = 0.22f;
        [Tooltip("Max distance from TIP for a contact to count.")]
        public float tipRadius = 0.16f;
        [Range(-1, 1)] public float minAlignment = 0.25f;
        public Transform tip;
        public float creatureDamageFactor = 0.5f;

        Grabbable _grab;
        float _last = -1f;

        void Awake()
        {
            _grab = GetComponent<Grabbable>();
            if (!tip) tip = transform.Find("TIP");
        }

        void OnCollisionEnter(Collision c)
        {
            if (!_grab.IsHeld || Time.time - _last < cooldown) return;
            // pointed tip faces model -Z (Blender) = Unity -Y: a downward chop
            var r = ToolStrike.Evaluate(c, _grab, tip, Vector3.down, minStrikeSpeed, tipRadius, minAlignment);
            if (!r.valid) return;
            _last = Time.time;
            float power = Mathf.Clamp01((r.speed - minStrikeSpeed) / (fullDamageSpeed - minStrikeSpeed)) * 0.6f + 0.4f;

            var deposit = r.other.GetComponentInParent<OreDeposit>();
            if (deposit)
            {
                deposit.Strike(new StrikeInfo { tier = tier, damage = damage * power, noiseMultiplier = noiseMultiplier, point = r.point, normal = r.normal, instigator = this });
                ToolStrike.Haptic(_grab, 0.4f + power * 0.5f);
                return;
            }
            var dmg = r.other.GetComponentInParent<IDamageable>();
            if (dmg != null && dmg.IsAlive)
            {
                dmg.TakeDamage(new DamageInfo(damage * power * creatureDamageFactor, transform.position, DamageType.Melee, this) { hitPoint = r.point, tier = tier });
                ToolStrike.Haptic(_grab, 0.7f);
                return;
            }
            // plain rock / wood / metal: feedback and noise, no effect
            var kind = Surface.KindOf(r.other);
            string snd = kind == Data.SurfaceKind.Metal ? "pick_miss_metal" : kind == Data.SurfaceKind.Wood ? "spear_hit_wood" : "pick_hit_rock";
            AudioManager.Instance?.PlayAt(snd, r.point, 0.6f * power);
            if (kind == Data.SurfaceKind.Rock || kind == Data.SurfaceKind.Metal || kind == Data.SurfaceKind.Concrete)
                FXManager.Burst("sparks", r.point, r.normal, new Color(1f, 0.75f, 0.4f), 5);
            NoiseSystem.Emit(r.point, 0.35f * power * Surface.NoiseFactor(kind) * noiseMultiplier, NoiseKind.MetalImpact, true, this);
            ToolStrike.Haptic(_grab, 0.3f * power);
        }
    }
}
