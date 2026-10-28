using System.Collections.Generic;
using System.Text;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.Bunker
{
    /// <summary>
    /// "Assay &amp; Trade" machine. Drop minerals (or any sellable item) into the hopper: the screen lists
    /// item, quantity, unit value and total payout. Press SELL to vacuum them away and get paid; press
    /// SELL PACK to sell every sellable item in your backpack directly.
    /// </summary>
    public class SellStation : MonoBehaviour, IButtonReceiver
    {
        public ItemZone bin = new ItemZone();
        public TextMesh screen;
        public Transform tubeOrigin;

        readonly List<ItemInstance> _inBin = new List<ItemInstance>();
        readonly Dictionary<Data.ItemDefinition, int> _counts = new Dictionary<Data.ItemDefinition, int>();
        readonly StringBuilder _sb = new StringBuilder(512);
        float _refresh;
        string _flash;
        float _flashUntil;
        int _countdown, _shownBalance;
        float _tickTimer;

        void Start() { _shownBalance = GameRoot.I ? GameRoot.I.Progress.Currency : 0; }

        public void OnButton(string command)
        {
            if (command == "sell") SellBin();
            else if (command == "sellpack") SellPack();
        }

        int Value(ItemInstance i) => i.definition && i.definition.sellable ? i.definition.sellValue : 0;

        void SellBin()
        {
            bin.Collect(_inBin);
            int total = 0, count = 0;
            foreach (var i in _inBin)
            {
                int v = Value(i);
                if (v <= 0) continue;
                total += v; count++;
                Destroy(i.gameObject);
            }
            Payout(total, count);
        }

        void SellPack()
        {
            var bp = Backpack.Instance;
            if (!bp) return;
            int total = 0, count = 0;
            foreach (var g in bp.RemoveWhere(g => g.Item && Value(g.Item) > 0))
            {
                total += Value(g.Item); count++;
                Destroy(g.gameObject);
            }
            Payout(total, count);
        }

        void Payout(int total, int count)
        {
            var pos = tubeOrigin ? tubeOrigin.position : transform.position;
            if (count == 0)
            {
                AudioManager.Instance?.PlayAt("terminal_error", pos, 0.7f);
                Flash("NOTHING TO SELL");
                return;
            }
            var gr = GameRoot.I;
            gr.Progress.AddCurrency(total);
            gr.Progress.Stats.itemsSold += count;
            gr.SaveNow();
            AudioManager.Instance?.PlayAt("sell_vacuum", pos, 1f);
            AudioManager.Instance?.PlayAt("purchase", transform.position, 0.8f);
            _countdown = total;
            Flash($"SOLD {count} ITEMS  +${total}");
            GameEvents.Toast($"+${total}");
        }

        void Flash(string s) { _flash = s; _flashUntil = Time.time + 4f; }

        void Update()
        {
            // counter animation: ticks while the balance counts up
            if (_countdown > 0)
            {
                _tickTimer -= Time.deltaTime;
                if (_tickTimer <= 0f)
                {
                    _tickTimer = 0.04f;
                    int step = Mathf.Max(1, _countdown / 12);
                    _countdown -= step;
                    _shownBalance += step;
                    AudioManager.Instance?.PlayAt("coin_tick", transform.position, 0.35f);
                }
            }
            else if (GameRoot.I) _shownBalance = GameRoot.I.Progress.Currency;

            _refresh -= Time.deltaTime;
            if (_refresh > 0f || !screen) return;
            _refresh = 0.2f;
            bin.Collect(_inBin);
            _counts.Clear();
            foreach (var i in _inBin) { _counts.TryGetValue(i.definition, out int c); _counts[i.definition] = c + 1; }

            _sb.Clear();
            _sb.Append("<color=#ffcc44>ASSAY & TRADE</color>   BAL $").Append(_shownBalance).Append('\n');
            _sb.Append("--------------------------------\n");
            int total = 0, lines = 0;
            foreach (var kv in _counts)
            {
                var d = kv.Key;
                int unit = d.sellable ? d.sellValue : 0;
                total += unit * kv.Value;
                if (lines++ < 6)
                    _sb.Append("<color=").Append(d.ColorTag).Append('>').Append(d.displayName).Append("</color> x").Append(kv.Value)
                       .Append(" @").Append(unit).Append(" = ").Append(unit * kv.Value).Append('\n');
            }
            if (_counts.Count == 0) _sb.Append("DROP MINERALS IN HOPPER\n");
            _sb.Append("--------------------------------\n");
            _sb.Append("TOTAL PAYOUT: <color=#88ff88>$").Append(total).Append("</color>\n");
            var bp = Backpack.Instance;
            if (bp && bp.TotalValue > 0) _sb.Append("PACK VALUE: $").Append(bp.TotalValue).Append("  [SELL PACK]\n");
            if (_flash != null && Time.time < _flashUntil) _sb.Append("<color=#ffcc44>").Append(_flash).Append("</color>");
            screen.text = _sb.ToString();
        }

        void OnDrawGizmos() => bin.DrawGizmo(new Color(1f, 0.8f, 0.2f));
    }
}
