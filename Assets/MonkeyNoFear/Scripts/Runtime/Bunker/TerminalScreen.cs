using UnityEngine;
using MonkeyNoFear.Core;

namespace MonkeyNoFear.Bunker
{
    /// <summary>Fixed grid of TextMesh rows (left column + right-aligned column) on a CRT screen.</summary>
    public class TerminalScreen : MonoBehaviour
    {
        public float width = 0.4f;
        public float height = 0.3f;
        public int rows = 16;
        public Color textColor = new Color(0.55f, 1f, 0.6f);

        TextMesh[] _left, _right;
        bool _built;

        public int Rows => rows;

        public void Build()
        {
            if (_built) return;
            _built = true;
            _left = new TextMesh[rows];
            _right = new TextMesh[rows];
            float lh = height / rows;
            for (int i = 0; i < rows; i++)
            {
                float y = height * 0.5f - lh * (i + 0.5f);
                _left[i] = TextUtil.Create(transform, "L" + i, new Vector3(-width * 0.5f, y, 0f), lh * 0.78f, TextAnchor.MiddleLeft, textColor);
                _right[i] = TextUtil.Create(transform, "R" + i, new Vector3(width * 0.5f, y, 0f), lh * 0.78f, TextAnchor.MiddleRight, textColor);
            }
        }

        public void Set(int row, string left, string right = "")
        {
            if (!_built) Build();
            if (row < 0 || row >= rows) return;
            if (_left[row].text != left) _left[row].text = left ?? "";
            if (_right[row].text != right) _right[row].text = right ?? "";
        }

        public void Clear()
        {
            if (!_built) Build();
            for (int i = 0; i < rows; i++) Set(i, "", "");
        }

        public void SetBrightness(float b)
        {
            if (!_built) return;
            var c = textColor * b; c.a = 1f;
            for (int i = 0; i < rows; i++) { _left[i].color = c; _right[i].color = c; }
        }
    }
}
