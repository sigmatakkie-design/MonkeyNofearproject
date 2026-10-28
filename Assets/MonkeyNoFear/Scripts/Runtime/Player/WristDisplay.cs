using System.Text;
using UnityEngine;
using MonkeyNoFear.Core;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Player
{
    /// <summary>Survival readout strapped to the left wrist: health, vigor, backpack, carried value,
    /// flashlight battery, location and short toasts. Brightens when you look at it.</summary>
    public class WristDisplay : MonoBehaviour
    {
        public Hand hand = Hand.Left;
        public Vector3 localOffset = new Vector3(0.0f, 0.035f, -0.09f);
        public Vector3 localEuler = new Vector3(70f, 0f, 0f);
        public float lineHeight = 0.0075f;
        public Material backingMaterial;

        PlayerRig _rig;
        TextMesh _text;
        string _toast;
        float _toastUntil;
        float _refresh;
        readonly StringBuilder _sb = new StringBuilder(256);

        void Start()
        {
            _rig = PlayerRig.Instance;
            _text = TextUtil.Create(transform, "WristText", Vector3.zero, lineHeight, TextAnchor.MiddleCenter, new Color(0.6f, 1f, 0.7f));
            var back = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Destroy(back.GetComponent<Collider>());
            back.transform.SetParent(transform, false);
            back.transform.localPosition = new Vector3(0, 0, 0.001f);
            back.transform.localScale = new Vector3(0.085f, 0.06f, 1f);
            if (backingMaterial) back.GetComponent<Renderer>().sharedMaterial = backingMaterial;
        }

        void OnEnable() => GameEvents.ToastMessage += OnToast;
        void OnDisable() => GameEvents.ToastMessage -= OnToast;
        void OnToast(string m) { _toast = m; _toastUntil = Time.time + 4f; }

        void LateUpdate()
        {
            if (!_rig) { _rig = PlayerRig.Instance; if (!_rig) return; }
            var ph = _rig.GetHand(hand);
            transform.SetPositionAndRotation(ph.Position + ph.Rotation * localOffset, ph.Rotation * Quaternion.Euler(localEuler));
            // only readable when turned toward the face
            var toEye = (_rig.HeadPosition - transform.position).normalized;
            float facing = Vector3.Dot(-transform.forward, toEye);
            if (_text) _text.color = new Color(0.6f, 1f, 0.7f, Mathf.Clamp01((facing - 0.3f) * 3f));

            _refresh -= Time.deltaTime;
            if (_refresh > 0f || !_text) return;
            _refresh = 0.25f;
            _sb.Clear();
            var hp = PlayerHealth.Instance;
            var vit = PlayerVitals.Instance;
            var bp = Backpack.Instance;
            var area = AreaManager.Instance;
            _sb.Append("HP ").Append(hp ? Mathf.CeilToInt(hp.Current) : 0).Append("  VIG ").Append(vit ? Mathf.RoundToInt(vit.Vigor * 100) : 0).Append('%').Append('\n');
            if (bp) _sb.Append("PACK ").Append(bp.Count).Append('/').Append(bp.Capacity).Append("  $").Append(bp.TotalValue).Append('\n');
            float bat = Items.Flashlight.CarriedBattery();
            if (bat >= 0f) _sb.Append("LIGHT ").Append(TextUtil.Bar(bat, 8)).Append('\n');
            if (area && area.CurrentProfile) _sb.Append(area.CurrentProfile.displayName.ToUpperInvariant());
            if (GameRoot.I) _sb.Append("  $").Append(GameRoot.I.Progress.Currency);
            if (_toast != null && Time.time < _toastUntil) _sb.Append('\n').Append("<color=#ffcc55>").Append(_toast).Append("</color>");
            _text.text = _sb.ToString();
        }
    }
}
