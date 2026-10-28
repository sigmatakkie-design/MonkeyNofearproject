using UnityEngine;

namespace MonkeyNoFear.Core
{
    /// <summary>World-space text without the UI packages: TextMesh with the built-in font.</summary>
    public static class TextUtil
    {
        static Font _font;

        public static Font BuiltinFont
        {
            get
            {
                if (_font) return _font;
                // 2022.2+ ships LegacyRuntime.ttf; older versions Arial.ttf
                try { _font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); } catch { _font = null; }
                if (!_font) { try { _font = Resources.GetBuiltinResource<Font>("Arial.ttf"); } catch { _font = null; } }
                return _font;
            }
        }

        /// <param name="height">world height of one line of text in meters</param>
        public static TextMesh Create(Transform parent, string name, Vector3 localPos, float height, TextAnchor anchor, Color color, Font font = null)
        {
            var go = new GameObject(name);
            go.layer = parent ? parent.gameObject.layer : 0;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var tm = go.AddComponent<TextMesh>();
            tm.font = font ? font : BuiltinFont;
            tm.fontSize = 64;
            // TextMesh character size: world height ≈ characterSize * fontSize / 10 (at scale 1)
            tm.characterSize = height * 10f / tm.fontSize;
            tm.anchor = anchor;
            tm.alignment = anchor == TextAnchor.UpperRight || anchor == TextAnchor.MiddleRight || anchor == TextAnchor.LowerRight
                ? TextAlignment.Right : anchor == TextAnchor.UpperCenter || anchor == TextAnchor.MiddleCenter || anchor == TextAnchor.LowerCenter
                ? TextAlignment.Center : TextAlignment.Left;
            tm.color = color;
            tm.richText = true;
            var mr = go.GetComponent<MeshRenderer>();
            if (tm.font) mr.sharedMaterial = tm.font.material;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            mr.receiveShadows = false;
            return tm;
        }

        public static string Bar(float fraction, int width = 10)
        {
            int n = Mathf.Clamp(Mathf.RoundToInt(fraction * width), 0, width);
            return new string('|', n) + new string('.', width - n);
        }
    }
}
