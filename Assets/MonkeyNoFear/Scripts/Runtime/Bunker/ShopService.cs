using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;

namespace MonkeyNoFear.Bunker
{
    public enum PurchaseResult { Ok, NotEnoughMoney, AlreadyOwned, Locked, SoldOut, Invalid }

    /// <summary>Buying logic, independent of UI: checks price, ownership limits and requirements, deducts
    /// currency, then grants the tool / consumable / upgrade for real.</summary>
    public static class ShopService
    {
        public static PurchaseResult Check(ShopEntry e)
        {
            var gr = GameRoot.I;
            if (e == null || !gr) return PurchaseResult.Invalid;
            var p = gr.Progress;
            if (e.kind == ShopEntryKind.Tool && p.OwnsTool(e.grantId)) return PurchaseResult.AlreadyOwned;
            if (e.kind == ShopEntryKind.Upgrade && p.HasUpgrade(e.grantId)) return PurchaseResult.AlreadyOwned;
            if (e.maxPurchases > 0 && p.PurchaseCount(e.id) >= e.maxPurchases) return PurchaseResult.SoldOut;
            if (!p.MeetsRequirement(e.requires)) return PurchaseResult.Locked;
            if (p.Currency < e.price) return PurchaseResult.NotEnoughMoney;
            return PurchaseResult.Ok;
        }

        public static PurchaseResult Buy(ShopEntry e, Vector3 feedbackPos)
        {
            var r = Check(e);
            if (r != PurchaseResult.Ok)
            {
                AudioManager.Instance?.PlayAt("terminal_error", feedbackPos, 0.8f);
                return r;
            }
            var gr = GameRoot.I;
            var db = gr.itemDatabase;
            if (!gr.Progress.TrySpend(e.price)) return PurchaseResult.NotEnoughMoney;
            gr.Progress.RecordPurchase(e.id);
            switch (e.kind)
            {
                case ShopEntryKind.Tool:
                    gr.Progress.GrantTool(e.grantId);
                    var entry = db ? db.GetTool(e.grantId) : null;
                    if (entry != null && ToolRack.Instance) ToolRack.Instance.Deliver(entry);
                    else if (entry != null) ItemDispenser.Instance?.Enqueue(entry.item);
                    break;
                case ShopEntryKind.Consumable:
                    var def = db ? db.GetItem(e.grantId) : null;
                    if (def) ItemDispenser.Instance?.Enqueue(def, Mathf.Max(1, e.quantity));
                    break;
                case ShopEntryKind.Upgrade:
                    gr.Progress.GrantUpgrade(e.grantId);
                    break;
            }
            AudioManager.Instance?.PlayAt("purchase", feedbackPos, 1f);
            AudioManager.Instance?.Play2D("sting_purchase", 0.5f);
            gr.SaveNow();
            return PurchaseResult.Ok;
        }

        public static string Describe(PurchaseResult r, ShopEntry e)
        {
            switch (r)
            {
                case PurchaseResult.Ok: return e.kind == ShopEntryKind.Upgrade ? "UPGRADE INSTALLED" : e.kind == ShopEntryKind.Tool ? "DELIVERED TO TOOL RACK" : "DELIVERED TO TUBE";
                case PurchaseResult.NotEnoughMoney: return "INSUFFICIENT FUNDS";
                case PurchaseResult.AlreadyOwned: return "ALREADY OWNED";
                case PurchaseResult.Locked: return "LOCKED: " + (string.IsNullOrEmpty(e?.requiresLabel) ? e?.requires : e.requiresLabel);
                case PurchaseResult.SoldOut: return "SOLD OUT";
                default: return "ERROR";
            }
        }
    }
}
