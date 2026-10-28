using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.Interaction;

namespace MonkeyNoFear.Bunker
{
    /// <summary>
    /// Wall rack holding the player's permanent equipment. Every owned tool exists exactly once in the
    /// world; on load the rack spawns any owned tool that has no live instance. "Recall" (terminal)
    /// brings back tools left outside the bunker. Hanging a tool back on a socket is just releasing it there.
    /// </summary>
    public class ToolRack : MonoBehaviour
    {
        public static ToolRack Instance { get; private set; }
        public List<Holster> sockets = new List<Holster>();
        [Tooltip("Tools within this radius of the rack count as 'at home' for the recall.")]
        public float homeRadius = 14f;

        void Awake() { Instance = this; }

        void Start() { SpawnMissingTools(); }

        void OnEnable() => GameEvents.SaveLoaded += SpawnMissingTools;
        void OnDisable() => GameEvents.SaveLoaded -= SpawnMissingTools;

        public ItemInstance FindLive(string toolId)
        {
            foreach (var i in ItemInstance.All) if (i && i.toolId == toolId) return i;
            return null;
        }

        public void SpawnMissingTools()
        {
            var gr = GameRoot.I;
            if (!gr || !gr.itemDatabase) return;
            foreach (var id in gr.Progress.OwnedTools)
            {
                if (FindLive(id)) continue;
                var entry = gr.itemDatabase.GetTool(id);
                if (entry == null || !entry.item) { Debug.LogWarning($"[ToolRack] Unknown tool '{id}'"); continue; }
                Deliver(entry, silent: true);
            }
        }

        /// <summary>Puts a newly bought tool on its socket (or the dispenser if the socket is busy).</summary>
        public void Deliver(ToolEntry entry, bool silent = false)
        {
            var socket = GetSocket(entry.rackSlot);
            var pos = socket ? socket.transform.position : transform.position;
            var inst = ItemInstance.Spawn(entry.item, pos, socket ? socket.transform.rotation : transform.rotation);
            if (!inst) return;
            inst.toolId = entry.id;
            var g = inst.GetComponent<Grabbable>();
            if (socket && g) socket.InsertSilently(g);
            else if (ItemDispenser.Instance) { inst.transform.position = ItemDispenser.Instance.outlet.position; }
            if (!silent) AudioManager.Instance?.PlayAt("holster_snap", pos, 0.8f);
        }

        Holster GetSocket(int preferred)
        {
            if (preferred >= 0 && preferred < sockets.Count && sockets[preferred] && !sockets[preferred].Content) return sockets[preferred];
            foreach (var s in sockets) if (s && !s.Content) return s;
            return null;
        }

        /// <summary>Returns tools that are lying outside (or were lost on death) to the rack.</summary>
        public int RecallLostTools()
        {
            int n = 0;
            var gr = GameRoot.I;
            if (!gr) return 0;
            foreach (var id in gr.Progress.OwnedTools)
            {
                var live = FindLive(id);
                if (live)
                {
                    var g = live.GetComponent<Grabbable>();
                    bool carried = g && (g.IsHeld || (g.Holster && !sockets.Contains(g.Holster)));
                    bool home = Vector3.Distance(live.transform.position, transform.position) < homeRadius;
                    if (carried || home) continue;
                    var entry = gr.itemDatabase.GetTool(id);
                    var socket = GetSocket(entry != null ? entry.rackSlot : -1);
                    if (g && socket) { g.MakeLoose(); socket.InsertSilently(g); n++; }
                }
                else
                {
                    var entry = gr.itemDatabase.GetTool(id);
                    if (entry != null) { Deliver(entry, true); n++; }
                }
            }
            if (n > 0) AudioManager.Instance?.PlayAt("dispenser_thunk", transform.position, 0.8f);
            return n;
        }
    }
}
