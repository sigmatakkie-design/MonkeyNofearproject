using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.Interaction
{
    /// <summary>
    /// A physical push button pressed by the player's hand. The cap travels along its local −Y as the palm
    /// pushes into it; the command fires once when the cap passes the press depth and re-arms after the hand
    /// leaves. Hands do not anchor on buttons (Interactable layer), so pressing never moves the player.
    /// </summary>
    public class PokeButton : MonoBehaviour
    {
        static readonly List<PokeButton> All = new List<PokeButton>();

        public MonoBehaviour receiver;
        public string command = "press";
        [Tooltip("Moving cap (child). If empty the button still works, just without visible travel.")]
        public Transform cap;
        public float radius = 0.06f;
        public float travel = 0.02f;
        [Range(0.2f, 1f)] public float pressFraction = 0.6f;
        public string label;
        public TextMesh labelMesh;
        public Renderer indicator;
        public bool interactable = true;

        Vector3 _capRest;
        bool _pressed, _armed = true;
        float _depth;
        IButtonReceiver _recv;
        Material _indMat;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        public bool IsPressed => _pressed;

        void Awake()
        {
            if (cap) _capRest = cap.localPosition;
            _recv = receiver as IButtonReceiver;
            if (indicator) _indMat = indicator.material;
            if (labelMesh && !string.IsNullOrEmpty(label)) labelMesh.text = label;
        }

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        public void SetIndicator(Color c)
        {
            if (_indMat) _indMat.SetColor(EmissionId, c);
        }

        void Update()
        {
            var rig = PlayerRig.Instance;
            if (!rig || !interactable) return;
            float depth = 0f;
            depth = Mathf.Max(depth, DepthFor(rig.LeftHand));
            depth = Mathf.Max(depth, DepthFor(rig.RightHand));
            _depth = Mathf.MoveTowards(_depth, depth, Time.deltaTime * 0.4f);
            if (depth > _depth) _depth = depth;
            if (cap) cap.localPosition = _capRest + Vector3.down * _depth;

            if (!_pressed && _armed && _depth >= travel * pressFraction)
            {
                _pressed = true;
                _armed = false;
                AudioManager.Instance?.PlayAt("button_press", transform.position, 0.8f);
                var h = NearestHand(rig);
                if (h) rig.Haptic(h.hand, 0.5f, 0.05f);
                Fire();
            }
            else if (_pressed && _depth < travel * 0.25f)
            {
                _pressed = false;
                AudioManager.Instance?.PlayAt("button_release", transform.position, 0.5f);
            }
            if (!_armed && depth <= 0f) _armed = true;
        }

        public void Fire()
        {
            if (_recv == null) _recv = receiver as IButtonReceiver;
            _recv?.OnButton(command);
        }

        float DepthFor(PhysicsHand h)
        {
            if (!h) return 0f;
            // use the raw controller target: buttons are not solid for hands
            var local = transform.InverseTransformPoint(h.Target);
            float lateral = new Vector2(local.x, local.z).magnitude;
            if (lateral > radius) return 0f;
            float top = (cap ? _capRest.y : 0f) + h.radius;
            float d = top - local.y;
            if (d < 0f || d > travel + h.radius * 2f + 0.05f) return 0f;
            return Mathf.Clamp(d, 0f, travel);
        }

        PhysicsHand NearestHand(PlayerRig rig)
        {
            float l = (rig.LeftHand.Target - transform.position).sqrMagnitude;
            float r = (rig.RightHand.Target - transform.position).sqrMagnitude;
            return l < r ? rig.LeftHand : rig.RightHand;
        }

        /// <summary>Desktop debug: press the button closest to a ray.</summary>
        public static PokeButton Raycast(Ray ray, float maxDist)
        {
            PokeButton best = null; float bd = float.MaxValue;
            foreach (var b in All)
            {
                var to = b.transform.position - ray.origin;
                float t = Vector3.Dot(to, ray.direction);
                if (t < 0f || t > maxDist) continue;
                float off = (ray.origin + ray.direction * t - b.transform.position).magnitude;
                if (off < b.radius * 1.5f && t < bd) { bd = t; best = b; }
            }
            return best;
        }

        void OnDrawGizmos()
        {
            Gizmos.matrix = transform.localToWorldMatrix;
            Gizmos.color = new Color(1f, 0.8f, 0.2f, 0.6f);
            Gizmos.DrawWireCube(Vector3.up * 0.01f, new Vector3(radius * 2f, 0.02f, radius * 2f));
        }
    }
}
