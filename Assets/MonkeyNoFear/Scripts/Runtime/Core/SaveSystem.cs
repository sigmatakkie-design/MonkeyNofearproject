using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace MonkeyNoFear.Core
{
    /// <summary>JSON save file in persistentDataPath with an atomic write and a rolling backup.
    /// A corrupt main file falls back to the backup, then to a fresh save.</summary>
    public class SaveSystem
    {
        public const string FileName = "monkeynofear_save.json";
        public SaveData Data { get; private set; }
        public string FilePath { get; }
        public bool IsDirty { get; private set; }

        readonly int _startingCurrency;
        readonly List<string> _startingTools;

        public SaveSystem(int startingCurrency, IEnumerable<string> startingTools, string directory = null)
        {
            _startingCurrency = startingCurrency;
            _startingTools = new List<string>(startingTools ?? Array.Empty<string>());
            FilePath = Path.Combine(directory ?? Application.persistentDataPath, FileName);
        }

        public void Load()
        {
            Data = TryRead(FilePath) ?? TryRead(FilePath + ".bak");
            if (Data == null)
            {
                Data = SaveData.CreateNew(_startingCurrency, _startingTools);
                Debug.Log($"[Save] New save created ({FilePath})");
                IsDirty = true;
            }
            Data.Sanitize(_startingCurrency, _startingTools);
            GameEvents.RaiseSaveLoaded();
        }

        static SaveData TryRead(string path)
        {
            try
            {
                if (!File.Exists(path)) return null;
                var json = File.ReadAllText(path);
                if (string.IsNullOrWhiteSpace(json)) return null;
                var d = JsonUtility.FromJson<SaveData>(json);
                if (d == null) return null;
                Debug.Log($"[Save] Loaded {path} (v{d.version}, ${d.currency})");
                return d;
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[Save] Could not read {path}: {e.Message}");
                return null;
            }
        }

        public void MarkDirty() => IsDirty = true;

        public void Save()
        {
            if (Data == null) return;
            try
            {
                var dir = Path.GetDirectoryName(FilePath);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                var tmp = FilePath + ".tmp";
                File.WriteAllText(tmp, JsonUtility.ToJson(Data, true));
                if (File.Exists(FilePath)) File.Copy(FilePath, FilePath + ".bak", true);
                if (File.Exists(FilePath)) File.Delete(FilePath);
                File.Move(tmp, FilePath);
                IsDirty = false;
            }
            catch (Exception e)
            {
                Debug.LogError($"[Save] Failed to write save: {e.Message}");
            }
        }

        /// <summary>Deletes progress (used by the terminal's factory reset and by the editor menu).</summary>
        public void ResetProgress()
        {
            Data = SaveData.CreateNew(_startingCurrency, _startingTools);
            Data.Sanitize(_startingCurrency, _startingTools);
            Save();
            GameEvents.RaiseSaveLoaded();
        }
    }
}
