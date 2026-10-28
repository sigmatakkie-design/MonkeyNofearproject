using UnityEngine;

namespace MonkeyNoFear.Player
{
    /// <summary>Head-locked overlay quad for fades, damage flashes, the low-health vignette and blacking out
    /// when the head is pushed inside geometry (prevents peeking through walls). Uses MNF/ScreenOverlay.</summary>
    public class ScreenFader : MonoBehaviour
    {
        public static ScreenFader Instance { get; private set; }

        public Renderer overlay;
        public Renderer vignette;
        PlayerRig _rig;
        Material _mat, _vigMat;
        Color _fadeColor = Color.clear, _fadeFrom, _fadeTo;
        float _fadeT = 1f, _fadeDur;
        Color _flashColor; float _flashAlpha, _flashDur, _flashT = 1f;
        float _danger;
        float _wall;

        static readonly int ColorId = Shader.PropertyToID("_Color");

        void Awake()
        {
            Instance = this;
            _rig = GetComponentInParent<PlayerRig>();
            if (overlay) _mat = overlay.material;
            if (vignette) _vigMat = vignette.material;
        }

        public void FadeTo(Color c, float seconds)
        {
            _fadeFrom = _fadeColor; _fadeTo = c; _fadeDur = Mathf.Max(0.01f, seconds); _fadeT = 0f;
        }

        public void Flash(Color c, float seconds, float alpha = 1f)
        {
            _flashColor = c; _flashAlpha = alpha; _flashDur = Mathf.Max(0.01f, seconds); _flashT = 0f;
        }

        public void SetDangerVignette(float amount) => _danger = amount;

        void LateUpdate()
        {
            if (_fadeT < 1f)
            {
                _fadeT = Mathf.Min(1f, _fadeT + Time.deltaTime / _fadeDur);
                _fadeColor = Color.Lerp(_fadeFrom, _fadeTo, _fadeT);
            }
            float flash = 0f;
            if (_flashT < 1f)
            {
                _flashT = Mathf.Min(1f, _flashT + Time.deltaTime / _flashDur);
                flash = (1f - _flashT) * _flashAlpha;
            }
            bool inWall = _rig && _rig.locomotion && _rig.locomotion.HeadInsideGeometry;
            _wall = Mathf.MoveTowards(_wall, inWall ? 1f : 0f, Time.deltaTime * 6f);

            Color c = _fadeColor;
            if (flash > 0f)
            {
                var fc = _flashColor; fc.a = 1f;
                float a = Mathf.Max(c.a, flash);
                c = Color.Lerp(c, fc, flash);
                c.a = a;
            }
            if (_wall > 0f) c = new Color(c.r * (1 - _wall), c.g * (1 - _wall), c.b * (1 - _wall), Mathf.Max(c.a, _wall));
            if (_mat)
            {
                _mat.SetColor(ColorId, c);
                overlay.enabled = c.a > 0.003f;
            }
            if (_vigMat)
            {
                _vigMat.SetColor(ColorId, new Color(0.25f, 0f, 0f, _danger * 0.65f));
                vignette.enabled = _danger > 0.01f;
            }
        }
    }
}
