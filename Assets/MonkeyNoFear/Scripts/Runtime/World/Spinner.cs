using UnityEngine;

namespace MonkeyNoFear.World
{
    /// <summary>Constant rotation (vent fans, beacons). Slows with bunker power if requested.</summary>
    public class Spinner : MonoBehaviour
    {
        public Vector3 axis = Vector3.forward;
        public float degreesPerSecond = 240f;
        public bool followsBunkerPower = true;

        void Update()
        {
            float k = followsBunkerPower && Bunker.BunkerPower.Instance ? Bunker.BunkerPower.Instance.Level : 1f;
            transform.Rotate(axis, degreesPerSecond * k * Time.deltaTime, Space.Self);
        }
    }
}
