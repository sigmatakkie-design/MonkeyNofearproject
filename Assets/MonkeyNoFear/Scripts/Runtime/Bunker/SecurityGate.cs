using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Bunker
{
    /// <summary>
    /// Heavy barred security gate. Commands: "open", "close", "toggle", "override" (manual crank lever).
    ///  * the bars are a solid kinematic collider at every height — nothing passes through while closed
    ///  * it rises slowly (motor + chain loop, start/stop clunks, alarm beeps, rotating amber beacons)
    ///  * closing stops and re-opens if anything is underneath (player, item, creature) — safety stop
    ///  * when bunker power drops (generator hiccup events) the motor dies; the override lever still
    ///    cranks it at a third of the speed
    ///  * status lamps: red = closed, amber = moving, green = open
    /// </summary>
    public class SecurityGate : MonoBehaviour, IButtonReceiver
    {
        public enum State { Closed, Opening, Open, Closing, Stopped }

        public Transform bars;
        public BoxCollider barsCollider;
        public float openHeight = 2.7f;
        public float speed = 0.42f;
        public float overrideSpeedFactor = 0.33f;
        public float startDelay = 0.8f;
        [Tooltip("Width/depth of the safety sensor under the bars.")]
        public Vector3 sensorSize = new Vector3(2.9f, 0.4f, 0.6f);
        public Light[] beacons = new Light[0];
        public Transform[] beaconRotors = new Transform[0];
        public Renderer[] statusLamps = new Renderer[0];
        public PokeButton[] openButtons = new PokeButton[0];
        public PokeButton[] closeButtons = new PokeButton[0];

        public State Current { get; private set; } = State.Closed;
        public bool Powered { get; set; } = true;
        public float OpenFraction => _h / openHeight;

        float _h, _delay;
        int _dir; // +1 opening, -1 closing
        bool _manual;
        ManagedLoop _motor, _alarm;
        Vector3 _barsRest;
        Material[] _lampMats;
        readonly Collider[] _hits = new Collider[8];
        UnityEngine.AI.NavMeshObstacle _obstacle;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        void Awake()
        {
            if (bars) _barsRest = bars.localPosition;
            _lampMats = new Material[statusLamps.Length];
            for (int i = 0; i < statusLamps.Length; i++) if (statusLamps[i]) _lampMats[i] = statusLamps[i].material;
            var rb = bars ? bars.GetComponent<Rigidbody>() : null;
            if (bars && !rb) rb = bars.gameObject.AddComponent<Rigidbody>();
            // moved through the transform every frame: interpolation would overwrite those writes with stale poses
            if (rb) { rb.isKinematic = true; rb.interpolation = RigidbodyInterpolation.None; }
            // the NavMesh is baked without the gate (it moves), so creatures would path straight through the
            // closed bars: carve the opening shut while the bars are down
            if (barsCollider)
            {
                _obstacle = barsCollider.gameObject.AddComponent<UnityEngine.AI.NavMeshObstacle>();
                _obstacle.shape = UnityEngine.AI.NavMeshObstacleShape.Box;
                _obstacle.center = barsCollider.center;
                _obstacle.size = barsCollider.size + new Vector3(0f, 0f, 0.3f);
                _obstacle.carving = true;
                _obstacle.carveOnlyStationary = false;
            }
        }

        void Start()
        {
            if (AudioManager.Instance)
            {
                _motor = AudioManager.Instance.CreateLoop("gate_motor_loop", bars ? bars : transform);
                _alarm = AudioManager.Instance.CreateLoop("gate_alarm", transform);
            }
            ApplyVisuals();
        }

        public void OnButton(string command)
        {
            switch (command)
            {
                case "open": Begin(+1, false); break;
                case "close": Begin(-1, false); break;
                case "toggle": Begin(Current == State.Open || Current == State.Opening ? -1 : +1, false); break;
                case "override": Begin(Current == State.Open || Current == State.Opening ? -1 : +1, true); break;
            }
        }

        void Begin(int dir, bool manual)
        {
            if (!manual && !Powered)
            {
                AudioManager.Instance?.PlayAt("terminal_error", transform.position + Vector3.up * 1.4f, 0.8f);
                GameEvents.Toast("GATE: NO POWER - USE MANUAL OVERRIDE");
                return;
            }
            if ((dir > 0 && Current == State.Open) || (dir < 0 && Current == State.Closed)) return;
            if (_dir == dir && (Current == State.Opening || Current == State.Closing)) return;
            _dir = dir;
            _manual = manual;
            _delay = manual ? 0.2f : startDelay;
            Current = dir > 0 ? State.Opening : State.Closing;
            AudioManager.Instance?.PlayAt("gate_start", bars ? bars.position : transform.position, 1f);
            _alarm?.FadeIn(8f);
        }

        void Update()
        {
            float dt = Time.deltaTime;
            if (Current == State.Opening || Current == State.Closing)
            {
                if (!_manual && !Powered) { Halt(); return; }
                if (_delay > 0f) { _delay -= dt; }
                else
                {
                    _motor?.FadeIn(3f);
                    float v = speed * (_manual ? overrideSpeedFactor : 1f);
                    if (_dir < 0 && Obstructed())
                    {
                        // safety: something is under the gate — reverse
                        AudioManager.Instance?.PlayAt("terminal_error", transform.position + Vector3.up * 1.5f, 0.6f);
                        _dir = 1; Current = State.Opening;
                    }
                    _h = Mathf.Clamp(_h + _dir * v * dt, 0f, openHeight);
                    if (_dir > 0 && _h >= openHeight) Arrive(State.Open);
                    else if (_dir < 0 && _h <= 0f) Arrive(State.Closed);
                }
                // shake slightly while moving: it is heavy and old
                if (bars) bars.localPosition = _barsRest + Vector3.up * _h + (_delay <= 0f ? Random.insideUnitSphere * 0.003f : Vector3.zero);
            }
            else if (bars) bars.localPosition = _barsRest + Vector3.up * _h;

            if (_obstacle) _obstacle.enabled = _h < 1.6f; // passable once a creature fits under the bars
            bool moving = Current == State.Opening || Current == State.Closing;
            for (int i = 0; i < beacons.Length; i++)
            {
                if (beacons[i]) beacons[i].enabled = moving;
                if (i < beaconRotors.Length && beaconRotors[i] && moving) beaconRotors[i].Rotate(0f, 360f * dt, 0f, Space.Self);
            }
            ApplyVisuals();
        }

        void Arrive(State s)
        {
            Current = s;
            _motor?.FadeOut(6f);
            _alarm?.FadeOut(8f);
            AudioManager.Instance?.PlayAt("gate_stop", bars ? bars.position : transform.position, 1f);
            NoiseSystem_EmitClank();
        }

        void Halt()
        {
            Current = State.Stopped;
            _motor?.FadeOut(4f);
            _alarm?.FadeOut(8f);
            AudioManager.Instance?.PlayAt("gate_stop", bars ? bars.position : transform.position, 0.6f);
        }

        void NoiseSystem_EmitClank() => AI.NoiseSystem.Emit(transform.position, 0.5f, AI.NoiseKind.Machine, false, this);

        bool Obstructed()
        {
            if (!bars) return false;
            var centre = bars.position + Vector3.down * 0.0f + bars.up * (sensorSize.y * 0.5f - 0.05f);
            int n = Physics.OverlapBoxNonAlloc(centre, sensorSize * 0.5f, _hits, bars.rotation,
                (1 << Layers.Player) | (1 << Layers.Item) | (1 << Layers.Creature) | (1 << Layers.HeldItem), QueryTriggerInteraction.Ignore);
            return n > 0;
        }

        void ApplyVisuals()
        {
            Color c = Current == State.Open ? new Color(0.1f, 1.6f, 0.2f)
                : Current == State.Closed ? new Color(1.6f, 0.05f, 0.03f)
                : (Mathf.Repeat(Time.time, 0.5f) < 0.25f ? new Color(2f, 1.2f, 0.1f) : Color.black);
            foreach (var m in _lampMats) if (m) m.SetColor(EmissionId, c);
            foreach (var b in openButtons) if (b) b.SetIndicator(Current == State.Open ? Color.black : new Color(0.1f, 1.2f, 0.2f));
            foreach (var b in closeButtons) if (b) b.SetIndicator(Current == State.Closed ? Color.black : new Color(1.2f, 0.1f, 0.05f));
        }

        void OnDrawGizmosSelected()
        {
            if (!bars) return;
            Gizmos.matrix = Matrix4x4.TRS(bars.position + bars.up * (sensorSize.y * 0.5f - 0.05f), bars.rotation, Vector3.one);
            Gizmos.color = Color.red;
            Gizmos.DrawWireCube(Vector3.zero, sensorSize);
        }
    }
}
