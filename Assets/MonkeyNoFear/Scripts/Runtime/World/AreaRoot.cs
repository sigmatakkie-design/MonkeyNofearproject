using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.World
{
    /// <summary>Content root that is only enabled while the player is in one of the listed areas.
    /// Keeps distant creature AI, lights and renderers out of the frame budget.</summary>
    public class AreaRoot : MonoBehaviour
    {
        public AreaId area;
        public AreaId[] alsoActiveIn = new AreaId[0];

        public bool ShouldBeActive(AreaId current)
        {
            if (current == AreaId.None || current == area) return true;
            foreach (var a in alsoActiveIn) if (a == current) return true;
            return false;
        }
    }
}
