using System.Collections;
using UnityEngine;
using MonkeyNoFear.AI;
using MonkeyNoFear.Audio;

namespace MonkeyNoFear.World
{
    /// <summary>An abandoned cart on rails that rolls a short distance on its own (horror event), or when
    /// pushed hard by the player. Rolling is loud: the Borer hears carts.</summary>
    public class MinecartEvent : MonoBehaviour, Player.IHandTouchable
    {
        public Vector3 railDirection = Vector3.forward;
        public float maxTravel = 3f;
        float _travel;
        bool _rolling;

        public void Nudge(float distance = 1.6f)
        {
            if (_rolling) return;
            float dir = Mathf.Abs(_travel) > maxTravel * 0.6f ? -Mathf.Sign(_travel) : (Random.value < 0.5f ? -1f : 1f);
            StartCoroutine(Roll(distance * dir));
        }

        public void OnHandTouch(Player.PhysicsHand hand, Vector3 point, float speed)
        {
            if (speed < 2.5f || _rolling) return;
            var push = Vector3.Dot(hand.ControllerVelocity, transform.TransformDirection(railDirection));
            if (Mathf.Abs(push) > 1.5f) StartCoroutine(Roll(Mathf.Sign(push) * Mathf.Min(2f, Mathf.Abs(push) * 0.5f)));
        }

        IEnumerator Roll(float distance)
        {
            _rolling = true;
            distance = Mathf.Clamp(_travel + distance, -maxTravel, maxTravel) - _travel;
            AudioManager.Instance?.PlayAt("minecart_roll", transform.position, 1f);
            NoiseSystem.Emit(transform.position, 0.7f, NoiseKind.Cart, false, this);
            var axis = transform.TransformDirection(railDirection).normalized;
            float dur = Mathf.Abs(distance) / 0.9f, t = 0f;
            var start = transform.position;
            while (t < dur)
            {
                t += Time.deltaTime;
                float k = Mathf.SmoothStep(0f, 1f, t / dur);
                transform.position = start + axis * distance * k;
                yield return null;
            }
            _travel += distance;
            _rolling = false;
        }
    }
}
