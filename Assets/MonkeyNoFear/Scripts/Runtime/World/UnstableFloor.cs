using System.Collections;
using UnityEngine;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Player;

namespace MonkeyNoFear.World
{
    /// <summary>Rotten planks / rusted grating over a drop. Stand on it and it creaks; stay and it gives way.
    /// The Lantern Mourner likes to lead followers here. Restored between expeditions.</summary>
    public class UnstableFloor : MonoBehaviour, IExpeditionReset
    {
        public float holdSeconds = 1.3f;
        public Vector3 sensorSize = new Vector3(2.5f, 1f, 2.5f);
        public GameObject floorObject;

        float _t;
        bool _broken;
        Vector3 _rest;

        void Awake() { if (!floorObject) floorObject = gameObject; _rest = floorObject.transform.localPosition; }
        void OnEnable() => ExpeditionManager.Register(this);
        void OnDisable() => ExpeditionManager.Unregister(this);

        public void OnNewExpedition(int index, System.Random rng)
        {
            StopAllCoroutines();
            _broken = false; _t = 0f;
            floorObject.SetActive(true);
            floorObject.transform.localPosition = _rest;
        }

        void Update()
        {
            if (_broken) return;
            var rig = PlayerRig.Instance;
            if (!rig) return;
            var local = transform.InverseTransformPoint(rig.transform.position + Vector3.ProjectOnPlane(rig.HeadPosition - rig.transform.position, Vector3.up));
            bool on = Mathf.Abs(local.x) < sensorSize.x * 0.5f && Mathf.Abs(local.z) < sensorSize.z * 0.5f && local.y > -0.2f && local.y < sensorSize.y;
            if (on)
            {
                if (_t == 0f) AudioManager.Instance?.PlayAt("structural_creak", transform.position, 1f);
                _t += Time.deltaTime;
                floorObject.transform.localPosition = _rest + Random.insideUnitSphere * 0.01f;
                if (_t > holdSeconds) StartCoroutine(Collapse());
            }
            else _t = Mathf.Max(0f, _t - Time.deltaTime * 0.5f);
        }

        IEnumerator Collapse()
        {
            _broken = true;
            AudioManager.Instance?.PlayAt("rock_fall_large", transform.position, 1f);
            FXManager.Burst("debris", transform.position, Vector3.down, new Color(0.35f, 0.28f, 0.2f), 40);
            float t = 0f;
            while (t < 0.6f) { t += Time.deltaTime; floorObject.transform.localPosition += Vector3.down * 9f * t * Time.deltaTime; yield return null; }
            floorObject.SetActive(false);
        }

        void OnDrawGizmos()
        {
            Gizmos.matrix = transform.localToWorldMatrix;
            Gizmos.color = new Color(1f, 0.4f, 0f, 0.5f);
            Gizmos.DrawWireCube(Vector3.up * sensorSize.y * 0.5f, sensorSize);
        }
    }
}
