using System.Text;
using UnityEngine;
using MonkeyNoFear.AI;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Core
{
    /// <summary>
    /// Development overlay for the desktop window / editor Game view (never drawn inside the headset):
    /// frame time, area, player state, nearby creature states and recent noise events.
    /// F1 toggles it. F2 draws noise spheres in the Scene view. Debug cheats (editor / development
    /// builds only): F5 +$500, F6 teleport to the next spawn of interest, F7 heal.
    /// </summary>
    public class DebugOverlay : MonoBehaviour
    {
        public bool visible = true;
        public Transform[] teleportTargets = new Transform[0];

        readonly StringBuilder _sb = new StringBuilder(1024);
        float _fps, _refresh;
        int _tp;
        GUIStyle _style;
        bool _inputBroken;
        string _text = "";

        void Update()
        {
            _fps = Mathf.Lerp(_fps, 1f / Mathf.Max(0.0001f, Time.unscaledDeltaTime), 0.05f);
            HandleKeys();
            _refresh -= Time.unscaledDeltaTime;
            if (_refresh > 0f || !visible) return;
            _refresh = 0.25f;
            Build();
        }

        void HandleKeys()
        {
            if (_inputBroken || !(Application.isEditor || Debug.isDebugBuild)) return;
            try
            {
                if (Input.GetKeyDown(KeyCode.F1)) visible = !visible;
                if (Input.GetKeyDown(KeyCode.F5)) GameRoot.I?.Progress.AddCurrency(500);
                if (Input.GetKeyDown(KeyCode.F7)) PlayerHealth.Instance?.Heal(100f);
                if (Input.GetKeyDown(KeyCode.F6) && teleportTargets.Length > 0 && PlayerRig.Instance)
                {
                    _tp = (_tp + 1) % teleportTargets.Length;
                    var t = teleportTargets[_tp];
                    if (t) PlayerRig.Instance.TeleportTo(t.position, t.eulerAngles.y);
                }
            }
            catch (System.InvalidOperationException) { _inputBroken = true; }
        }

        void Build()
        {
            _sb.Clear();
            _sb.Append("MONKEY NO FEAR  ").Append(_fps.ToString("0")).Append(" fps  (").Append((1000f / Mathf.Max(1f, _fps)).ToString("0.0")).Append(" ms)\n");
            var rig = PlayerRig.Instance;
            if (rig)
            {
                _sb.Append("input: ").Append(rig.Input != null ? rig.Input.Name : "-").Append("   speed ").Append(rig.locomotion.Speed.ToString("0.0"))
                   .Append(rig.locomotion.Grounded ? "  grounded" : "  air").Append(rig.locomotion.AnyHandAnchored ? "  anchored" : "").Append('\n');
            }
            var am = AreaManager.Instance;
            if (am) _sb.Append("area: ").Append(am.Current).Append("  depth ").Append(am.DepthLevel).Append("  fog vis ").Append(am.FogVisibility.ToString("0")).Append("m\n");
            var hp = PlayerHealth.Instance; var vit = PlayerVitals.Instance; var st = PlayerStealth.Instance;
            if (hp) _sb.Append("hp ").Append(hp.Current.ToString("0")).Append("  vigor ").Append(vit ? vit.Vigor.ToString("0.00") : "-")
                       .Append("  visibility ").Append(st ? st.Visibility.ToString("0.00") : "-").Append("  threat ").Append(ThreatMonitor.Level.ToString("0.00")).Append('\n');
            if (GameRoot.I) _sb.Append("$").Append(GameRoot.I.Progress.Currency).Append("  expeditions ").Append(GameRoot.I.Progress.Stats.expeditions).Append('\n');
            foreach (var c in FindObjectsOfType<CreatureBase>())
            {
                if (!c.Active || !rig) continue;
                float d = Vector3.Distance(c.transform.position, rig.HeadPosition);
                if (d > 80f) continue;
                _sb.Append("  ").Append(c.name).Append(": ").Append(c.StateName).Append("  aw ").Append(c.Awareness.ToString("0")).Append("  ").Append(d.ToString("0")).Append("m\n");
            }
            foreach (var n in NoiseSystem.RecentEvents(2f))
                _sb.Append("  noise ").Append(n.kind).Append(' ').Append(n.loudness.ToString("0.00")).Append(n.fromPlayer ? " (player)" : "").Append('\n');
            _text = _sb.ToString();
        }

        void OnGUI()
        {
            if (!visible) return;
            if (_style == null) _style = new GUIStyle(GUI.skin.label) { fontSize = 12, richText = false, normal = { textColor = new Color(0.7f, 1f, 0.75f) } };
            GUI.Box(new Rect(8, 8, 430, 22 + _text.Split('\n').Length * 15), GUIContent.none);
            GUI.Label(new Rect(14, 12, 420, 800), _text, _style);
        }

        void OnDrawGizmos()
        {
            foreach (var n in NoiseSystem.RecentEvents(2f))
            {
                Gizmos.color = n.fromPlayer ? new Color(1f, 0.4f, 0.2f, 0.3f) : new Color(0.3f, 0.6f, 1f, 0.3f);
                Gizmos.DrawWireSphere(n.position, n.Radius);
            }
        }
    }
}
