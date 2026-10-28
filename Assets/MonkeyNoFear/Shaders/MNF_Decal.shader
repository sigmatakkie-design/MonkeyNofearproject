// Alpha-blended lit decal quad (cracks, stains, claw scratches, hand prints, signs with wear).
// Pulled toward the camera in depth so it never z-fights with the wall it sits on.
Shader "MNF/Decal"
{
    Properties
    {
        _Color ("Tint", Color) = (1,1,1,1)
        _MainTex ("Albedo (A = opacity)", 2D) = "white" {}
        [Normal] _BumpMap ("Normal", 2D) = "bump" {}
        _Glossiness ("Smoothness", Range(0,1)) = 0.2
        _AtlasRect ("Atlas rect (x, y, w, h)", Vector) = (0,0,1,1)
    }
    SubShader
    {
        Tags { "Queue"="Geometry+50" "RenderType"="Transparent" "IgnoreProjector"="True" "ForceNoShadowCasting"="True" }
        ZWrite Off
        Offset -1, -1

        CGPROGRAM
        #pragma surface surf Standard alpha:fade
        #pragma target 3.0

        sampler2D _MainTex, _BumpMap;
        fixed4 _Color;
        half _Glossiness;
        float4 _AtlasRect;

        struct Input { float2 uv_MainTex; };

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float2 uv = _AtlasRect.xy + IN.uv_MainTex * _AtlasRect.zw;
            fixed4 c = tex2D(_MainTex, uv) * _Color;
            o.Albedo = c.rgb;
            o.Alpha = c.a;
            o.Normal = UnpackNormal(tex2D(_BumpMap, uv));
            o.Smoothness = _Glossiness;
        }
        ENDCG
    }
}
