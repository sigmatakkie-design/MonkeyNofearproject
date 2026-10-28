using UnityEngine;
using MonkeyNoFear.Data;

namespace MonkeyNoFear.Core
{
    /// <summary>The single bootstrap object of the world scene. Owns the save and progression services;
    /// the other managers (audio, areas, expedition, horror director) live as components on the same
    /// GameObject. There is exactly one GameRoot; duplicates destroy themselves.</summary>
    [DefaultExecutionOrder(-100)]
    public class GameRoot : MonoBehaviour
    {
        public static GameRoot I { get; private set; }

        [Header("Data")]
        public ItemDatabase itemDatabase;
        public ShopCatalog shopCatalog;
        public LoreDatabase loreDatabase;

        [Header("Saving")]
        [Tooltip("Autosave interval while dirty (seconds).")]
        public float autosaveInterval = 45f;
        [Tooltip("Editor only: start every play session from a fresh save.")]
        public bool editorFreshSaveEachPlay;

        [Header("Shared prefabs")]
        public GameObject lostPackPrefab;

        public SaveSystem Save { get; private set; }
        public Progression Progress { get; private set; }

        float _autosaveTimer;

        void Awake()
        {
            if (I && I != this)
            {
                Debug.LogWarning("[GameRoot] Duplicate GameRoot destroyed.");
                Destroy(gameObject);
                return;
            }
            I = this;
            Application.targetFrameRate = -1; // XR runtime drives the frame rate
            int startMoney = itemDatabase ? itemDatabase.startingCurrency : 25;
            var startTools = itemDatabase ? itemDatabase.startingTools : null;
            Save = new SaveSystem(startMoney, startTools);
            Save.Load();
#if UNITY_EDITOR
            if (editorFreshSaveEachPlay) Save.ResetProgress();
#endif
            Progress = new Progression(Save, itemDatabase);
            if (!itemDatabase) Debug.LogError("[GameRoot] No ItemDatabase assigned — run 'Monkey No Fear > Build Game'.");
        }

        void Update()
        {
            Progress.Stats.playSeconds += Time.unscaledDeltaTime;
            _autosaveTimer += Time.unscaledDeltaTime;
            if (_autosaveTimer >= autosaveInterval && Save.IsDirty)
            {
                _autosaveTimer = 0f;
                Save.Save();
            }
        }

        public void SaveNow() { _autosaveTimer = 0f; Save.Save(); }

        void OnApplicationPause(bool paused) { if (paused && Save != null) Save.Save(); }
        void OnApplicationQuit() { Save?.Save(); }
        void OnDestroy() { if (I == this) { Save?.Save(); I = null; } }

        public static ItemDefinition Item(string id) => I && I.itemDatabase ? I.itemDatabase.GetItem(id) : null;
    }
}
