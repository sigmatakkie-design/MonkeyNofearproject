using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.World
{
    /// <summary>
    /// Broken service lift between mine level 1 and level 3. Dead until the player reaches the bottom and
    /// throws the breaker lever (progression flag "elevator_powered", saved), after which it is a fast,
    /// safe shortcut back up with a heavy haul. Commands: "breaker", "call_top", "call_bottom", "go".
    /// </summary>
    public class ServiceElevator : MonoBehaviour, IButtonReceiver
    {
        public Transform platform;
        public Transform topStop, bottomStop;
        public float speed = 1.6f;
        public Light[] statusLights = new Light[0];
        public Light breakerLamp;

        public bool Powered => GameRoot.I && GameRoot.I.Progress.HasFlag("elevator_powered");
        bool _moving, _atTop = true;
        float _t = 1f; // 1 = top
        ManagedLoop _motor;

        void Start()
        {
            if (platform && !platform.GetComponent<MovingPlatform>()) platform.gameObject.AddComponent<MovingPlatform>();
            if (platform)
            {
                var rb = platform.GetComponent<Rigidbody>();
                if (!rb) rb = platform.gameObject.AddComponent<Rigidbody>();
                rb.isKinematic = true;
            }
            if (AudioManager.Instance && platform) _motor = AudioManager.Instance.CreateLoop("elevator_motor_loop", platform);
            Apply();
            UpdateLamps();
        }

        public void OnButton(string command)
        {
            switch (command)
            {
                case "breaker":
                    if (!Powered)
                    {
                        GameRoot.I?.Progress.SetFlag("elevator_powered");
                        GameRoot.I?.SaveNow();
                        AudioManager.Instance?.PlayAt("light_buzz_on", breakerLamp ? breakerLamp.transform.position : transform.position, 1f);
                        GameEvents.Toast("SERVICE LIFT POWERED");
                        UpdateLamps();
                    }
                    break;
                case "call_top": Go(true); break;
                case "call_bottom": Go(false); break;
                case "go": Go(!_atTop); break;
            }
        }

        void Go(bool toTop)
        {
            if (!Powered)
            {
                AudioManager.Instance?.PlayAt("terminal_error", platform ? platform.position : transform.position, 0.8f);
                GameEvents.Toast("LIFT: NO POWER");
                return;
            }
            if (_moving || _atTop == toTop) return;
            _moving = true;
            _atTop = toTop;
            AudioManager.Instance?.PlayAt("elevator_clank", platform.position, 1f);
            _motor?.FadeIn(2f);
            AI.NoiseSystem.Emit(platform.position, 0.6f, AI.NoiseKind.Machine, false, this);
        }

        void Update()
        {
            if (!_moving || !platform || !topStop || !bottomStop) return;
            float len = Mathf.Max(0.1f, Vector3.Distance(topStop.position, bottomStop.position));
            _t = Mathf.MoveTowards(_t, _atTop ? 1f : 0f, speed / len * Time.deltaTime);
            Apply();
            if (Mathf.Approximately(_t, _atTop ? 1f : 0f))
            {
                _moving = false;
                _motor?.FadeOut(3f);
                AudioManager.Instance?.PlayAt("elevator_arrive", platform.position, 1f);
            }
        }

        void Apply()
        {
            if (platform && topStop && bottomStop) platform.position = Vector3.Lerp(bottomStop.position, topStop.position, _t);
        }

        void UpdateLamps()
        {
            foreach (var l in statusLights) if (l) { l.enabled = true; l.color = Powered ? new Color(0.3f, 1f, 0.4f) : new Color(1f, 0.15f, 0.1f); }
            if (breakerLamp) breakerLamp.enabled = !Powered;
        }
    }
}
