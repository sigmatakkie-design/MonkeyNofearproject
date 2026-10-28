using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>Minimal JSON reader for the asset-pipeline manifests (objects → Dictionary, arrays → List,
    /// numbers → double). JsonUtility cannot read dictionaries, which every manifest uses.</summary>
    public static class MiniJson
    {
        public static object Parse(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            int i = 0;
            var v = Value(json, ref i);
            return v;
        }

        static void Ws(string s, ref int i) { while (i < s.Length && char.IsWhiteSpace(s[i])) i++; }

        static object Value(string s, ref int i)
        {
            Ws(s, ref i);
            if (i >= s.Length) return null;
            char c = s[i];
            if (c == '{') return Obj(s, ref i);
            if (c == '[') return Arr(s, ref i);
            if (c == '"') return Str(s, ref i);
            if (s.Length - i >= 4 && string.CompareOrdinal(s, i, "true", 0, 4) == 0) { i += 4; return true; }
            if (s.Length - i >= 5 && string.CompareOrdinal(s, i, "false", 0, 5) == 0) { i += 5; return false; }
            if (s.Length - i >= 4 && string.CompareOrdinal(s, i, "null", 0, 4) == 0) { i += 4; return null; }
            if (s.Length - i >= 3 && string.CompareOrdinal(s, i, "NaN", 0, 3) == 0) { i += 3; return double.NaN; }
            return Num(s, ref i);
        }

        static Dictionary<string, object> Obj(string s, ref int i)
        {
            var d = new Dictionary<string, object>();
            i++;
            while (true)
            {
                Ws(s, ref i);
                if (i >= s.Length) throw new FormatException("unterminated object");
                if (s[i] == '}') { i++; return d; }
                if (s[i] == ',') { i++; continue; }
                var k = Str(s, ref i);
                Ws(s, ref i);
                if (s[i] != ':') throw new FormatException("expected ':' at " + i);
                i++;
                d[k] = Value(s, ref i);
            }
        }

        static List<object> Arr(string s, ref int i)
        {
            var l = new List<object>();
            i++;
            while (true)
            {
                Ws(s, ref i);
                if (i >= s.Length) throw new FormatException("unterminated array");
                if (s[i] == ']') { i++; return l; }
                if (s[i] == ',') { i++; continue; }
                l.Add(Value(s, ref i));
            }
        }

        static string Str(string s, ref int i)
        {
            var sb = new StringBuilder();
            i++; // opening quote
            while (i < s.Length)
            {
                char c = s[i++];
                if (c == '"') return sb.ToString();
                if (c != '\\') { sb.Append(c); continue; }
                char e = s[i++];
                switch (e)
                {
                    case 'n': sb.Append('\n'); break;
                    case 't': sb.Append('\t'); break;
                    case 'r': sb.Append('\r'); break;
                    case 'b': sb.Append('\b'); break;
                    case 'f': sb.Append('\f'); break;
                    case 'u': sb.Append((char)Convert.ToInt32(s.Substring(i, 4), 16)); i += 4; break;
                    default: sb.Append(e); break;
                }
            }
            throw new FormatException("unterminated string");
        }

        static object Num(string s, ref int i)
        {
            int start = i;
            while (i < s.Length && "+-0123456789.eE".IndexOf(s[i]) >= 0) i++;
            return double.Parse(s.Substring(start, i - start), CultureInfo.InvariantCulture);
        }

        // ---------------- typed helpers ----------------
        public static Dictionary<string, object> AsObj(this object o) => o as Dictionary<string, object>;
        public static List<object> AsList(this object o) => o as List<object> ?? new List<object>();

        public static object Get(this Dictionary<string, object> d, string k) => d != null && d.TryGetValue(k, out var v) ? v : null;
        public static float GetFloat(this Dictionary<string, object> d, string k, float def = 0f) => d.Get(k) is double v ? (float)v : def;
        public static bool GetBool(this Dictionary<string, object> d, string k, bool def = false) => d.Get(k) is bool b ? b : def;
        public static string GetString(this Dictionary<string, object> d, string k, string def = null) => d.Get(k) as string ?? def;

        public static UnityEngine.Vector3 GetVec3(this Dictionary<string, object> d, string k)
        {
            var l = d.Get(k) as List<object>;
            if (l == null || l.Count < 3) return UnityEngine.Vector3.zero;
            return new UnityEngine.Vector3(Convert.ToSingle(l[0]), Convert.ToSingle(l[1]), Convert.ToSingle(l[2]));
        }
    }
}
