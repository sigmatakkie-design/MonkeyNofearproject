using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.World
{
    /// <summary>Implemented by world systems that re-roll between expeditions (ore, wildlife, hazards,
    /// rare encounters) so every trip outside is different.</summary>
    public interface IExpeditionReset
    {
        void OnNewExpedition(int expeditionIndex, System.Random rng);
    }

    /// <summary>An expedition starts when the player leaves the bunker area and ends when they come
    /// back (or die). The world re-rolls while the player is safely inside.</summary>
    public class ExpeditionManager : MonoBehaviour
    {
        public static ExpeditionManager Instance { get; private set; }
        static readonly List<IExpeditionReset> Resettables = new List<IExpeditionReset>();

        public bool InExpedition { get; private set; }
        public float StartTime { get; private set; }
        public int DeepestThisRun { get; private set; }
        public ExpeditionSummary LastSummary { get; private set; }
        public bool HasLastSummary { get; private set; }

        bool _worldFresh;
        bool _died;

        public static void Register(IExpeditionReset r) { if (!Resettables.Contains(r)) Resettables.Add(r); }
        public static void Unregister(IExpeditionReset r) => Resettables.Remove(r);

        void Awake() { Instance = this; }

        void OnEnable()
        {
            GameEvents.AreaChanged += OnArea;
            GameEvents.PlayerDied += OnDied;
        }

        void OnDisable()
        {
            GameEvents.AreaChanged -= OnArea;
            GameEvents.PlayerDied -= OnDied;
        }

        void Start() { RerollWorld(); }

        void OnArea(AreaId from, AreaId to)
        {
            bool outside = to == AreaId.Forest || to >= AreaId.MineShallow;
            if (outside && !InExpedition) Begin();
            if (InExpedition && AreaManager.Instance)
                DeepestThisRun = Mathf.Max(DeepestThisRun, AreaManager.Instance.DepthLevel);
            if (to == AreaId.Bunker && InExpedition) End(false);
        }

        void OnDied() { _died = true; if (InExpedition) End(true); }

        void Begin()
        {
            if (!_worldFresh) RerollWorld();
            InExpedition = true;
            _died = false;
            _worldFresh = false;
            StartTime = Time.time;
            DeepestThisRun = 0;
            var gr = GameRoot.I;
            if (gr) { gr.Progress.Stats.expeditions++; gr.Progress.MarkDirty(); }
            GameEvents.RaiseExpeditionStarted();
        }

        void End(bool died)
        {
            InExpedition = false;
            var gr = GameRoot.I;
            var pack = Player.Backpack.Instance;
            var s = new ExpeditionSummary
            {
                durationSeconds = Time.time - StartTime,
                deepestLevel = DeepestThisRun,
                died = died,
                itemsCarriedBack = died || !pack ? 0 : pack.Count,
                valueCarriedBack = died || !pack ? 0 : pack.TotalValue
            };
            LastSummary = s;
            HasLastSummary = true;
            if (gr)
            {
                var st = gr.Progress.Stats;
                st.deepestLevel = Mathf.Max(st.deepestLevel, s.deepestLevel);
                st.longestExpeditionSeconds = Mathf.Max(st.longestExpeditionSeconds, s.durationSeconds);
                gr.SaveNow();
            }
            GameEvents.RaiseExpeditionEnded(s);
            if (!died && Audio.AudioManager.Instance) Audio.AudioManager.Instance.Play2D("sting_safe", 0.7f);
            RerollWorld();
        }

        /// <summary>Re-roll ore, wildlife, hazards and rare encounters for the next trip.</summary>
        public void RerollWorld()
        {
            int index = GameRoot.I ? GameRoot.I.Progress.Stats.expeditions : 0;
            var rng = new System.Random(System.Environment.TickCount ^ (index * 7919));
            foreach (var r in Resettables.ToArray())
            {
                try { r.OnNewExpedition(index, rng); }
                catch (System.Exception e) { Debug.LogException(e); }
            }
            _worldFresh = true;
        }

        public float ElapsedThisRun => InExpedition ? Time.time - StartTime : 0f;
    }
}
