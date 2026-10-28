using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Player
{
    /// <summary>
    /// Vigor: a gentle survival meter that only drains outside the bunker (≈ 25 minutes from full to
    /// empty at the default rate). Low vigor weakens leaps and caps health regeneration — it never kills.
    /// Eating restores it: hold food to your mouth for a moment.
    /// </summary>
    public class PlayerVitals : MonoBehaviour
    {
        public static PlayerVitals Instance { get; private set; }

        [Range(0, 1)] public float startVigor = 1f;
        [Tooltip("Fraction of vigor lost per minute outside (scaled by the area's drain multiplier).")]
        public float drainPerMinute = 0.04f;
        [Tooltip("Leap strength multiplier at zero vigor.")]
        public float weakLeapMultiplier = 0.8f;
        public float eatDistance = 0.2f;
        public float eatHoldSeconds = 0.6f;

        public float Vigor { get; private set; }
        PlayerRig _rig;
        readonly float[] _eatTimer = new float[2];

        void Awake() { Instance = this; Vigor = startVigor; _rig = GetComponent<PlayerRig>(); }

        public void Restore(float amount) => Vigor = Mathf.Clamp01(Vigor + amount);

        void Update()
        {
            var area = AreaManager.Instance;
            var p = area ? area.CurrentProfile : null;
            if (p && !p.isSafeZone)
                Vigor = Mathf.Max(0f, Vigor - drainPerMinute / 60f * p.vigorDrainMultiplier * Time.deltaTime);
            if (_rig) _rig.locomotion.StrengthMultiplier = Mathf.Lerp(weakLeapMultiplier, 1f, Mathf.Clamp01(Vigor / 0.25f));
            CheckEating(Player.Hand.Left);
            CheckEating(Player.Hand.Right);
        }

        void CheckEating(Hand h)
        {
            var g = _rig ? _rig.GetGrabber(h) : null;
            var item = g && g.HeldGrabbable ? g.HeldGrabbable.Item : null;
            int i = (int)h;
            if (!item || !item.definition || !item.definition.IsEdible) { _eatTimer[i] = 0f; return; }
            var mouth = _rig.HeadPosition + _rig.HeadRotation * new Vector3(0f, -0.08f, 0.06f);
            if ((item.transform.position - mouth).sqrMagnitude < eatDistance * eatDistance)
            {
                _eatTimer[i] += Time.deltaTime;
                if (_eatTimer[i] >= eatHoldSeconds) Eat(g, item.definition);
            }
            else _eatTimer[i] = 0f;
        }

        void Eat(Interaction.HandGrabber g, ItemDefinition def)
        {
            var held = g.HeldGrabbable;
            g.ForceRelease();
            Restore(def.foodVigor);
            PlayerHealth.Instance?.Heal(def.foodHeal);
            AudioManager.Instance?.PlayAt("eat_munch", _rig.HeadPosition, 0.8f);
            GameEvents.Toast($"ATE {def.displayName.ToUpperInvariant()}");
            if (held) Destroy(held.gameObject);
        }
    }
}
