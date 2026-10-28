using System;
using System.Collections.Generic;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Bunker
{
    /// <summary>
    /// SURVIVOR NET — the workbench computer. Physical keys: PAGE◄ PAGE► ▲ ▼ SELECT BACK.
    /// Pages: HOME (status, last expedition), SHOP (equipment, consumables, upgrades), STORAGE (stash,
    /// withdraw, sell stored, recall tools), EXPEDITION (map knowledge, progress), ARCHIVE (bestiary,
    /// minerals, recovered notes about the Monkopocalypse), STATS, SETTINGS (comfort options, reset).
    /// Every action goes through the real systems (Progression, ShopService, ToolRack, ItemDispenser).
    /// </summary>
    public class BunkerTerminal : MonoBehaviour, IButtonReceiver
    {
        public TerminalScreen screen;
        public SellStation sellStation;

        static readonly string[] Pages = { "HOME", "SHOP", "STORAGE", "EXPED", "ARCHIVE", "STATS", "SETUP" };

        struct Row
        {
            public string left, right;
            public bool selectable;
            public Action action;
            public string detail;
        }

        readonly List<Row> _rows = new List<Row>();
        int _page, _sel, _scroll;
        string _status = "";
        float _statusUntil;
        string _detailTitle, _detailText;
        int _detailPage;
        bool _booted;
        float _bootT, _idle, _refresh;
        bool _confirmReset;

        Vector3 FeedbackPos => screen ? screen.transform.position : transform.position;

        void Start()
        {
            if (screen) { screen.Build(); screen.Clear(); }
        }

        public void OnButton(string command)
        {
            _idle = 0f;
            if (!_booted)
            {
                _booted = true; _bootT = 0f;
                AudioManager.Instance?.PlayAt("terminal_boot", FeedbackPos, 0.8f);
                return;
            }
            AudioManager.Instance?.PlayAt("terminal_select", FeedbackPos, 0.6f);
            switch (command)
            {
                case "next": SetPage((_page + 1) % Pages.Length); break;
                case "prev": SetPage((_page + Pages.Length - 1) % Pages.Length); break;
                case "up": Move(-1); break;
                case "down": Move(+1); break;
                case "select": Select(); break;
                case "back":
                    if (_detailText != null) { _detailText = null; }
                    else SetPage(0);
                    break;
            }
            Redraw();
        }

        void SetPage(int p) { _page = p; _sel = 0; _scroll = 0; _detailText = null; _confirmReset = false; }

        void Move(int d)
        {
            if (_detailText != null) { _detailPage = Mathf.Max(0, _detailPage + d); return; }
            Build();
            if (_rows.Count == 0) return;
            int start = _sel;
            for (int i = 0; i < _rows.Count; i++)
            {
                _sel = (_sel + d + _rows.Count) % _rows.Count;
                if (_rows[_sel].selectable) return;
            }
            _sel = start;
        }

        void Select()
        {
            if (_detailText != null) { _detailText = null; return; }
            Build();
            if (_sel >= 0 && _sel < _rows.Count && _rows[_sel].selectable)
            {
                var r = _rows[_sel];
                if (r.action != null) r.action();
                else if (r.detail != null) { _detailTitle = r.left; _detailText = r.detail; _detailPage = 0; }
            }
        }

        void Status(string s, bool good)
        {
            _status = (good ? "<color=#88ff88>" : "<color=#ff7755>") + s + "</color>";
            _statusUntil = Time.time + 5f;
            if (good) AudioManager.Instance?.PlayAt("terminal_confirm", FeedbackPos, 0.7f);
        }

        void Update()
        {
            _idle += Time.deltaTime;
            if (_booted && _idle > 120f) { _booted = false; if (screen) screen.Clear(); }
            if (_booted) _bootT += Time.deltaTime;
            _refresh -= Time.deltaTime;
            if (_refresh <= 0f) { _refresh = 0.5f; Redraw(); }
            if (screen) screen.SetBrightness(0.85f + Mathf.PerlinNoise(Time.time * 7f, 0f) * 0.15f);
        }

        // ----------------------------------------------------------------------------- page content
        void Build()
        {
            _rows.Clear();
            var gr = GameRoot.I;
            if (!gr) return;
            switch (_page)
            {
                case 0: BuildHome(gr); break;
                case 1: BuildShop(gr); break;
                case 2: BuildStorage(gr); break;
                case 3: BuildExpedition(gr); break;
                case 4: BuildArchive(gr); break;
                case 5: BuildStats(gr); break;
                case 6: BuildSettings(gr); break;
            }
            if (_sel >= _rows.Count) _sel = Mathf.Max(0, _rows.Count - 1);
            if (_rows.Count > 0 && !_rows[_sel].selectable) { for (int i = 0; i < _rows.Count; i++) if (_rows[i].selectable) { _sel = i; break; } }
        }

        void Info(string l, string r = "") => _rows.Add(new Row { left = l, right = r });
        void Option(string l, string r, Action a) => _rows.Add(new Row { left = l, right = r, selectable = true, action = a });
        void Entry(string l, string r, string detail) => _rows.Add(new Row { left = l, right = r, selectable = true, detail = detail });

        void BuildHome(GameRoot gr)
        {
            var p = gr.Progress;
            var hp = Player.PlayerHealth.Instance;
            var vit = Player.PlayerVitals.Instance;
            Info("SURVIVOR NET // BUNKER 7", "ONLINE");
            Info("FUNDS", "$" + p.Currency);
            Info("HEALTH", hp ? Mathf.CeilToInt(hp.Current) + "/" + hp.maxHealth : "-");
            Info("VIGOR", vit ? TextUtil.Bar(vit.Vigor) : "-");
            Info("STORED VALUE", "$" + p.StashValue());
            var em = ExpeditionManager.Instance;
            if (em && em.HasLastSummary)
            {
                var s = em.LastSummary;
                Info("LAST EXPEDITION", s.died ? "<color=#ff7755>LOST</color>" : "RETURNED");
                Info("  DURATION", Mathf.FloorToInt(s.durationSeconds / 60f) + "m " + Mathf.FloorToInt(s.durationSeconds % 60f) + "s");
                Info("  DEEPEST", s.deepestLevel == 0 ? "SURFACE" : "MINE LEVEL " + s.deepestLevel);
                if (!s.died) Info("  HAUL CARRIED", s.itemsCarriedBack + " ITEMS / $" + s.valueCarriedBack);
            }
            else Info("NO EXPEDITION ON RECORD", "");
            Info("");
            Info("<color=#ffcc44>TIP</color> " + Tip(p));
        }

        string Tip(Progression p)
        {
            if (p.Stats.expeditions == 0) return "Open the gate. Follow the trail signs north to the mine.";
            if (p.Stats.oreMined == 0) return "Swing the pick hard, point first, into the ore veins.";
            if (!p.OwnsTool("spear")) return "Buy a spear before the forest gets you.";
            if (!p.IsDiscovered("creature_hollowback")) return "If you hear scraping, stop moving.";
            if (!p.OwnsTool("pickaxe_t2")) return "Blackstone needs a tempered pick.";
            return "Keep your light off if something is drawn to it.";
        }

        void BuildShop(GameRoot gr)
        {
            var cat = gr.shopCatalog;
            Info("EQUIPMENT SUPPLY", "$" + gr.Progress.Currency);
            if (!cat) { Info("CATALOG OFFLINE"); return; }
            foreach (var e in cat.entries)
            {
                var r = ShopService.Check(e);
                string right = r == PurchaseResult.AlreadyOwned ? "OWNED" : r == PurchaseResult.SoldOut ? "SOLD OUT"
                    : r == PurchaseResult.Locked ? "LOCKED" : "$" + e.price;
                string col = r == PurchaseResult.Ok ? "" : r == PurchaseResult.NotEnoughMoney ? "<color=#ff9966>" : "<color=#668866>";
                string name = (e.quantity > 1 ? e.quantity + "x " : "") + e.displayName;
                var entry = e;
                _rows.Add(new Row
                {
                    left = col + name + (col.Length > 0 ? "</color>" : ""),
                    right = right,
                    selectable = true,
                    action = () =>
                    {
                        var res = ShopService.Buy(entry, FeedbackPos);
                        Status(ShopService.Describe(res, entry), res == PurchaseResult.Ok);
                    },
                    detail = entry.description
                });
            }
        }

        void BuildStorage(GameRoot gr)
        {
            var p = gr.Progress;
            var db = gr.itemDatabase;
            Info("STORAGE LOCKER", "$" + p.StashValue());
            var stash = new List<ItemStack>(p.Stash);
            if (stash.Count == 0) Info("  (EMPTY - USE THE LOCKER HOPPER)");
            foreach (var s in stash)
            {
                var def = db ? db.GetItem(s.id) : null;
                if (!def) continue;
                var d = def;
                Option("<color=" + d.ColorTag + ">" + d.displayName + "</color> x" + s.count, d.sellable ? "$" + d.sellValue * s.count : "",
                    () =>
                    {
                        if (p.TakeFromStash(d.id)) { ItemDispenser.Instance?.Enqueue(d); Status("WITHDRAWN: " + d.displayName.ToUpperInvariant(), true); }
                    });
            }
            Info("");
            Option("SELL ALL STORED MINERALS", "", () =>
            {
                int total = 0, n = 0;
                foreach (var s in new List<ItemStack>(p.Stash))
                {
                    var def = db ? db.GetItem(s.id) : null;
                    if (!def || !def.sellable || def.category != ItemCategory.Mineral && def.category != ItemCategory.Valuable) continue;
                    total += def.sellValue * s.count; n += s.count;
                    p.TakeFromStash(def.id, s.count);
                }
                if (n == 0) { Status("NO MINERALS STORED", false); return; }
                p.AddCurrency(total);
                p.Stats.itemsSold += n;
                gr.SaveNow();
                AudioManager.Instance?.PlayAt("purchase", FeedbackPos, 1f);
                Status($"SOLD {n} STORED ITEMS +${total}", true);
            });
            Option("RECALL LOST TOOLS TO RACK", "", () =>
            {
                int n = ToolRack.Instance ? ToolRack.Instance.RecallLostTools() : 0;
                Status(n > 0 ? $"RECALLED {n} TOOLS" : "ALL TOOLS ACCOUNTED FOR", n > 0);
            });
        }

        void BuildExpedition(GameRoot gr)
        {
            var p = gr.Progress;
            Info("EXPEDITION PLANNING");
            Info("ROUTE", "GATE > FOREST TRAIL > MINE");
            Info("SURFACE", p.IsDiscovered("area_forest") ? "SURVEYED" : "UNKNOWN");
            Info("MINE LEVEL 1", p.IsDiscovered("area_mine1") ? "IRON / COPPER" : "UNKNOWN");
            Info("MINE LEVEL 2", p.IsDiscovered("area_mine2") ? "COPPER / CRYSTAL" : "UNKNOWN");
            Info("MINE LEVEL 3", p.IsDiscovered("area_mine3") ? "CRYSTAL / BLACKSTONE" : "<color=#ff7755>NO ENTRY</color>");
            Info("SERVICE LIFT", p.HasFlag("elevator_powered") ? "<color=#88ff88>POWERED</color>" : "NO POWER (BREAKER L3)");
            Info("BEST PICK TIER", p.BestPickaxeTier.ToString());
            Info("PACK CAPACITY", p.BackpackCapacity.ToString());
            Info("DEEPEST REACHED", p.Stats.deepestLevel == 0 ? "SURFACE" : "LEVEL " + p.Stats.deepestLevel);
            Info("");
            Info("<color=#ffcc44>Deeper = richer. Deeper = worse.</color>");
        }

        void BuildArchive(GameRoot gr)
        {
            var p = gr.Progress;
            var lore = gr.loreDatabase;
            Info("ARCHIVE / MONKOPOCALYPSE", (p.Lore.Count + p.Discoveries.Count) + " RECORDS");
            if (!lore) return;
            int shown = 0;
            foreach (var e in lore.entries)
            {
                bool have = p.HasLore(e.id) || p.IsDiscovered(e.id);
                if (!have) continue;
                Entry((e.kind == "Bestiary" ? "<color=#ff9966>" : e.kind == "Mineral" ? "<color=#88ccff>" : "<color=#ffeeaa>") + e.title + "</color>", e.kind.ToUpperInvariant(), e.text);
                shown++;
            }
            if (shown == 0) Info("  NOTHING RECOVERED YET");
        }

        void BuildStats(GameRoot gr)
        {
            var s = gr.Progress.Stats;
            Info("SURVIVOR RECORD");
            Info("EXPEDITIONS", s.expeditions.ToString());
            Info("DEATHS", s.deaths.ToString());
            Info("ORE DEPOSITS MINED", s.oreMined.ToString());
            Info("ANIMALS HUNTED", s.animalsHunted.ToString());
            Info("ITEMS SOLD", s.itemsSold.ToString());
            Info("TOTAL EARNED", "$" + s.totalEarned);
            Info("LONGEST TRIP", Mathf.FloorToInt(s.longestExpeditionSeconds / 60f) + " MIN");
            Info("TIME SURVIVED", Mathf.FloorToInt(s.playSeconds / 3600f) + "h " + Mathf.FloorToInt(s.playSeconds % 3600f / 60f) + "m");
        }

        void BuildSettings(GameRoot gr)
        {
            var st = gr.Progress.Settings;
            Info("SETUP");
            Option("SNAP TURN", st.snapTurn ? "ON" : "OFF", () => { st.snapTurn = !st.snapTurn; gr.Progress.MarkDirty(); });
            Option("SNAP ANGLE", st.snapTurnDegrees.ToString("0"), () => { st.snapTurnDegrees = st.snapTurnDegrees >= 90f ? 30f : st.snapTurnDegrees + 15f; gr.Progress.MarkDirty(); });
            Option("JOYSTICK MOVE (ACCESSIBILITY)", st.joystickLocomotion ? "ON" : "OFF", () => { st.joystickLocomotion = !st.joystickLocomotion; gr.Progress.MarkDirty(); });
            Info("");
            Option(_confirmReset ? "<color=#ff5544>PRESS AGAIN TO ERASE ALL PROGRESS</color>" : "RESET SAVE", "", () =>
            {
                if (!_confirmReset) { _confirmReset = true; return; }
                _confirmReset = false;
                gr.Save.ResetProgress();
                Status("SAVE ERASED", true);
            });
        }

        // ----------------------------------------------------------------------------- drawing
        void Redraw()
        {
            if (!screen) return;
            if (!_booted) { screen.Clear(); screen.Set(screen.Rows / 2, "      PRESS ANY KEY", ""); return; }
            if (_bootT < 1.6f)
            {
                screen.Clear();
                screen.Set(1, "SURVIVOR NET BIOS v0.7");
                if (_bootT > 0.4f) screen.Set(2, "MEMORY ........ OK");
                if (_bootT > 0.8f) screen.Set(3, "UPLINK ........ <color=#ff7755>NO CARRIER</color>");
                if (_bootT > 1.2f) screen.Set(4, "LOCAL NODE .... OK");
                return;
            }
            int rows = screen.Rows;
            screen.Set(0, TabLine(), "$" + (GameRoot.I ? GameRoot.I.Progress.Currency : 0));

            if (_detailText != null)
            {
                for (int i = 1; i < rows; i++) screen.Set(i, "");
                screen.Set(1, "<color=#ffcc44>" + _detailTitle + "</color>");
                var lines = Items.LoreItem.Wrap(_detailText, 52).Split('\n');
                int per = rows - 4;
                int maxPage = Mathf.Max(0, (lines.Length - 1) / per);
                _detailPage = Mathf.Min(_detailPage, maxPage);
                for (int i = 0; i < per; i++)
                {
                    int li = _detailPage * per + i;
                    if (li < lines.Length) screen.Set(2 + i, lines[li]);
                }
                screen.Set(rows - 1, "[BACK] RETURN" + (maxPage > 0 ? $"   [UP/DOWN] PAGE {_detailPage + 1}/{maxPage + 1}" : ""));
                return;
            }

            Build();
            int body = rows - 3; // tab line, status line, description line
            if (_sel < _scroll) _scroll = _sel;
            if (_sel >= _scroll + body) _scroll = _sel - body + 1;
            for (int i = 0; i < body; i++)
            {
                int ri = _scroll + i;
                if (ri < _rows.Count)
                {
                    var r = _rows[ri];
                    bool sel = ri == _sel && r.selectable;
                    screen.Set(1 + i, (sel ? "<color=#ffffff>> " : r.selectable ? "  " : "") + r.left + (sel ? "</color>" : ""), r.right);
                }
                else screen.Set(1 + i, "");
            }
            string desc = _sel < _rows.Count && _rows[_sel].selectable && _page == 1 ? _rows[_sel].detail : null;
            screen.Set(rows - 2, desc != null ? "<color=#99bb99>" + Trim(desc, 60) + "</color>" : "");
            screen.Set(rows - 1, Time.time < _statusUntil ? _status : "<color=#557755>[<] [>] PAGE  [^] [v] MOVE  [SELECT]</color>");
        }

        static string Trim(string s, int n) => string.IsNullOrEmpty(s) ? "" : s.Length <= n ? s.Replace('\n', ' ') : s.Substring(0, n - 3).Replace('\n', ' ') + "...";

        string TabLine()
        {
            // TextMesh has no background highlight: the active tab is bracketed and bright
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < Pages.Length; i++)
            {
                if (i == _page) sb.Append("<color=#ffffff>[").Append(Pages[i]).Append("]</color> ");
                else sb.Append("<color=#4f8a55>").Append(Pages[i]).Append("</color> ");
            }
            return sb.ToString();
        }
    }
}
