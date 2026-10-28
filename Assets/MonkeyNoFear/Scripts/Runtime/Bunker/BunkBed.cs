using System.Collections;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.Bunker
{
    /// <summary>Press the button by the bunk to sleep: fades out, saves, restores vigor and lets the world
    /// outside change (ore, wildlife and encounters re-roll).</summary>
    public class BunkBed : MonoBehaviour, IButtonReceiver
    {
        bool _sleeping;

        public void OnButton(string command)
        {
            if (command == "sleep" && !_sleeping) StartCoroutine(Sleep());
        }

        IEnumerator Sleep()
        {
            _sleeping = true;
            ScreenFader.Instance?.FadeTo(Color.black, 1.2f);
            AudioManager.Instance?.Play2D("sting_safe", 0.5f);
            yield return new WaitForSeconds(2f);
            PlayerVitals.Instance?.Restore(1f);
            PlayerHealth.Instance?.Heal(1000f);
            if (ExpeditionManager.Instance && !ExpeditionManager.Instance.InExpedition) ExpeditionManager.Instance.RerollWorld();
            GameRoot.I?.SaveNow();
            yield return new WaitForSeconds(1.5f);
            ScreenFader.Instance?.FadeTo(Color.clear, 2f);
            GameEvents.Toast("RESTED. THE WORLD OUTSIDE HAS CHANGED.");
            _sleeping = false;
        }
    }
}
