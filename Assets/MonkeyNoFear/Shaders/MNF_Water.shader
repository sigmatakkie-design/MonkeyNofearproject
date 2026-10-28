// Dark still water for streams and flooded mine galleries: two scrolling ripple normals, high gloss,
// depth-free (cheap on mobile VR), alpha-blended so the bed shows through near edges.
Shader "MNF/Water"
{
    Properties
    {
        _Color ("Colour (A = opacity)", Color) = (0.04,0.06,0.06,0.82)
        [Normal] _BumpMap ("Ripples", 2D) = "bump" {}
        _Scale ("Meters per tile", Float) = 3
        _Speed ("Flow speed", Vector) = (0.03, 0.02, -0.02, 0.035)
        _Glossiness ("Smoothness", Range(0,1)) = 0.95
    }
    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent-10" "IgnoreProjector"="True" }
        LOD 200
        ZWrite Off

        CGPROGRAM
        #pragma surface surf Standard alpha:fade
        #pragma target 3.0

        sampler2D _BumpMap;
        fixed4 _Color;
        half _Scale, _Glossiness;
        float4 _Speed;

        struct Input { float3 worldPos; };

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float2 uv = IN.worldPos.xz / _Scale;
            float3 n1 = UnpackNormal(tex2D(_BumpMap, uv + _Time.y * _Speed.xy));
            float3 n2 = UnpackNormal(tex2D(_BumpMap, uv * 1.7 + _Time.y * _Speed.zw));
            o.Normal = normalize(float3(n1.xy + n2.xy, n1.z * n2.z));
            o.Albedo = _Color.rgb;
            o.Alpha = _Color.a;
            o.Smoothness = _Glossiness;
            o.Metallic = 0;
        }
        ENDCG
    }
    FallBack "Legacy Shaders/Transparent/Diffuse"
}
