using System;
using System.Collections.Generic;
using UnityEngine;

namespace MonkeyNoFear.Data
{
    [Serializable]
    public class LoreEntry
    {
        public string id;
        public string title;
        [TextArea(3, 10)] public string text;
        [Tooltip("Note = paper read in hand, Tape = audio log, Bestiary = unlocked by sighting a creature")]
        public string kind = "Note";
    }

    /// <summary>All text of the Monkopocalypse mystery: notes, tapes and bestiary entries.</summary>
    [CreateAssetMenu(menuName = "Monkey No Fear/Lore Database", fileName = "LoreDatabase")]
    public class LoreDatabase : ScriptableObject
    {
        public List<LoreEntry> entries = new List<LoreEntry>();

        public LoreEntry Get(string id)
        {
            foreach (var e in entries) if (e.id == id) return e;
            return null;
        }
    }
}
