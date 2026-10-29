using System.Collections;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Player
{
    /// <summary>
    /// Health with fairness rules: a short invulnerability window after every hit (no attack chains the
    /// player cannot react to), delayed regeneration, armour upgrades. Death drops the backpack as a lost
    /// pack and wakes the player in the bunker; permanent progression is never lost.
    /// </summary>
    public class PlayerHealth : MonoBehaviour
    {
        public static PlayerHealth Instance { get; private set; }

        public float maxHealth = 100f;
        [Tooltip("Seconds of invulnerability after taking a hit.")]
        public float hitGrace = 0.9f;
        public float regenDelay = 8f;
        public float regenPerSecond = 2.5f;
        [Tooltip("Without vigor, health only regenerates up to this fraction.")]
        [Range(0, 1)] public float lowVigorRegenCap = 0.5f;
        public float respawnHealth = 70f;
        public Transform respawnPoint;

        public float Current { get; private set; }
        public bool IsDead { get; private set; }
        public float Fraction => Current / maxHealth;

        float _lastHit = -999f;
        PlayerRig _rig;

        void Awake()
        {
            Instance = this;
            Current = maxHealth;
            _rig = GetComponent<PlayerRig>();
        }

        public bool TakeDamage(DamageInfo info)
        {
            if (IsDead || info.amount <= 0f) return false;
            if (Time.time - _lastHit < hitGrace && info.type != DamageType.Drain) return false;
            float mult = GameRoot.I ? GameRoot.I.Progress.DamageTakenMultiplier : 1f;
            if (info.type == DamageType.Fall) mult = 1f; // armour does not help against falls
            float dmg = info.amount * mult;
            if (info.type != DamageType.Drain) _lastHit = Time.time;
            else _lastHit = Mathf.Max(_lastHit, Time.time - hitGrace); // drains still pause regeneration
            Current = Mathf.Max(0f, Current - dmg);

            if (info.type != DamageType.Drain)
            {
                AudioManager.Instance?.PlayAt("hurt_grunt", _rig ? _rig.HeadPosition : transform.position, 0.9f);
                ScreenFader.Instance?.Flash(new Color(0.55f, 0f, 0f), 0.35f, Mathf.Clamp01(dmg / 50f) * 0.7f + 0.2f);
                _rig?.Haptic(Hand.Left, 0.9f, 0.2f);
                _rig?.Haptic(Hand.Right, 0.9f, 0.2f);
                // knock back away from the source
                if (_rig && info.type != DamageType.Fall)
                {
                    var away = _rig.HeadPosition - info.sourcePosition; away.y = 0f;
                    if (away.sqrMagnitude > 0.001f) _rig.locomotion.AddImpulse(away.normalized * Mathf.Min(4f, dmg * 0.08f) + Vector3.up * 1.2f);
                }
            }
            GameEvents.RaisePlayerDamaged(dmg, info.sourcePosition);
            if (Current <= 0f) StartCoroutine(Die());
            return true;
        }

        public void Heal(float amount)
        {
            if (IsDead) return;
            Current = Mathf.Min(maxHealth, Current + amount);
        }

        void Update()
        {
            if (IsDead) return;
            if (Time.time - _lastHit > regenDelay && Current < maxHealth)
            {
                var v = PlayerVitals.Instance;
                float cap = v && v.Vigor < 0.25f ? maxHealth * lowVigorRegenCap : maxHealth;
                if (Current < cap) Current = Mathf.Min(cap, Current + regenPerSecond * Time.deltaTime);
            }
            // low health desaturating vignette
            if (ScreenFader.Instance) ScreenFader.Instance.SetDangerVignette(Mathf.Clamp01((45f - Current) / 45f));
        }

        IEnumerator Die()
        {
            IsDead = true;
            var gr = GameRoot.I;
            if (gr) { gr.Progress.Stats.deaths++; gr.Progress.MarkDirty(); }
            AudioManager.Instance?.Play2D("death_sting", 1f);
            if (_rig) _rig.locomotion.Pinned = true;
            // under the body, not at the tracking-space origin (room-scale offset can put that inside a wall)
            var feet = transform.position;
            if (_rig) feet += Vector3.ProjectOnPlane(_rig.HeadPosition - transform.position, Vector3.up);
            Backpack.Instance?.DropAllAsLostPack(feet);
            GameEvents.RaisePlayerDied();
            ScreenFader.Instance?.FadeTo(Color.black, 1.5f);
            yield return new WaitForSeconds(3f);

            // drop anything held so it stays where you died
            if (_rig)
            {
                _rig.leftGrabber?.ForceRelease();
                _rig.rightGrabber?.ForceRelease();
                var p = respawnPoint ? respawnPoint.position : transform.position;
                var yaw = respawnPoint ? respawnPoint.eulerAngles.y : 0f;
                _rig.TeleportTo(p, yaw);
                _rig.locomotion.Pinned = false;
            }
            AreaManager.Instance?.ForceArea(AreaId.Bunker);
            Current = respawnHealth;
            IsDead = false;
            PlayerVitals.Instance?.Restore(0.6f);
            ScreenFader.Instance?.FadeTo(Color.clear, 2f);
            GameEvents.Toast("YOU WOKE UP IN THE BUNKER");
            GameEvents.RaisePlayerRespawned();
            gr?.SaveNow();
        }
    }
}
