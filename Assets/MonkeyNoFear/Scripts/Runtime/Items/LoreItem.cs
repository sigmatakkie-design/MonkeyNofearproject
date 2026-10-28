using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Items
{
    /// <summary>A note, tape or tag left behind by the miners. Picking it up unlocks its entry in the
    /// terminal archive; notes show their text above the paper while held, tapes play a garbled recording.</summary>
    [RequireComponent(typeof(Grabbable))]
    public class LoreItem : MonoBehaviour
    {
        public string loreId;
        public bool isTape;
        public TextMesh readout;

        Grabbable _grab;

        void Awake()
        {
            _grab = GetComponent<Grabbable>();
            _grab.Grabbed += OnGrabbed;
            if (readout) readout.gameObject.SetActive(false);
        }

        void OnGrabbed(HandGrabber hand)
        {
            var gr = GameRoot.I;
            var entry = gr && gr.loreDatabase ? gr.loreDatabase.Get(loreId) : null;
            bool first = gr && gr.Progress.UnlockLore(loreId);
            if (first)
            {
                AudioManager.Instance?.Play2D("sting_lore", 0.6f);
                GameEvents.Toast("ARCHIVE: " + (entry != null ? entry.title.ToUpperInvariant() : loreId));
            }
            if (isTape) AudioManager.Instance?.PlayAt("radio_burst", transform.position, 0.8f);
            if (readout && entry != null)
            {
                readout.text = Wrap(entry.text, 34);
                readout.gameObject.SetActive(true);
            }
        }

        void Update()
        {
            if (readout && readout.gameObject.activeSelf && !_grab.IsHeld) readout.gameObject.SetActive(false);
            if (readout && readout.gameObject.activeSelf && Player.PlayerRig.Instance)
            {
                var cam = Player.PlayerRig.Instance.HeadPosition;
                readout.transform.rotation = Quaternion.LookRotation(readout.transform.position - cam, Vector3.up);
            }
        }

        public static string Wrap(string s, int width)
        {
            if (string.IsNullOrEmpty(s)) return "";
            var sb = new System.Text.StringBuilder();
            int col = 0;
            foreach (var word in s.Split(' '))
            {
                if (word.Contains("\n")) { sb.Append(word).Append(' '); col = word.Length - word.LastIndexOf('\n'); continue; }
                if (col + word.Length > width) { sb.Append('\n'); col = 0; }
                sb.Append(word).Append(' ');
                col += word.Length + 1;
            }
            return sb.ToString();
        }
    }
}
