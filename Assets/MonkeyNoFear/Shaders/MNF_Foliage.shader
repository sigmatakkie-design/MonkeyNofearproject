// Alpha-cutout, two-sided foliage cards with wind sway. Sway strength grows with height above the
// object's pivot so trunks stay put while branch tips move. Back faces get a translucency boost.
Shader "MNF/Foliage"
{
    Properties
    {
        _Color ("Tint", Color) = (1,1,1,1)
        _MainTex ("Albedo (A = cutout)", 2D) = "white" {}
        [Normal] _BumpMap ("Normal", 2D) = "bump" {}
        _Cutoff ("Alpha Cutoff", Range(0,1)) = 0.45
        _WindStrength ("Wind Strength", Range(0,0.5)) = 0.08
        _WindSpeed ("Wind Speed", Range(0,5)) = 1.1
        _WindHeight ("Full sway at height (m)", Float) = 8
        _Translucency ("Translucency", Range(0,1)) = 0.35
    }
    SubShader
    {
        Tags { "RenderType"="TransparentCutout" "Queue"="AlphaTest" "IgnoreProjector"="True" }
        LOD 200
        Cull Off

        CGPROGRAM
        #pragma surface surf Lambert alphatest:_Cutoff vertex:vert addshadow
        #pragma target 3.0
        #pragma multi_compile_instancing

        sampler2D _MainTex, _BumpMap;
        fixed4 _Color;
        half _WindStrength, _WindSpeed, _WindHeight, _Translucency;

        struct Input
        {
            float2 uv_MainTex;
            float facing : VFACE;
        };

        void vert(inout appdata_full v)
        {
            float3 wpos = mul(unity_ObjectToWorld, v.vertex).xyz;
            float3 pivot = mul(unity_ObjectToWorld, float4(0, 0, 0, 1)).xyz;
            float h = saturate((wpos.y - pivot.y) / max(_WindHeight, 0.1));
            float phase = dot(pivot.xz, float2(0.13, 0.17));
            float t = _Time.y * _WindSpeed;
            float gust = sin(t * 0.37 + phase) * 0.5 + 0.5;
            float3 sway = float3(sin(t + phase + wpos.x * 0.3), 0, cos(t * 0.83 + phase + wpos.z * 0.3));
            float flutter = sin(t * 4.7 + wpos.x * 2.1 + wpos.z * 1.7) * 0.25;
            wpos += (sway * (0.6 + gust) + flutter) * _WindStrength * h * h;
            v.vertex.xyz = mul(unity_WorldToObject, float4(wpos, 1)).xyz;
        }

        void surf(Input IN, inout SurfaceOutput o)
        {
            fixed4 c = tex2D(_MainTex, IN.uv_MainTex) * _Color;
            o.Albedo = c.rgb * (IN.facing > 0 ? 1 : 1 + _Translucency);
            o.Alpha = c.a;
            float3 n = UnpackNormal(tex2D(_BumpMap, IN.uv_MainTex));
            o.Normal = IN.facing > 0 ? n : float3(n.xy, -n.z);
        }
        ENDCG
    }
    FallBack "Legacy Shaders/Transparent/Cutout/VertexLit"
}
