// World-space triplanar PBR for cliffs, caves and the mine shell (meshes without good UVs).
// Optional "top" layer (moss/mud) on upward-facing surfaces and a wetness control.
Shader "MNF/Triplanar"
{
    Properties
    {
        _Color ("Tint", Color) = (1,1,1,1)
        _MainTex ("Albedo", 2D) = "white" {}
        [Normal] _BumpMap ("Normal", 2D) = "bump" {}
        _BumpScale ("Normal Strength", Range(0,2)) = 1
        _MaskMap ("Mask (R metal, G AO, B height, A smooth)", 2D) = "white" {}
        _Scale ("Meters per tile", Float) = 2.5
        _Smoothness ("Smoothness Scale", Range(0,2)) = 1
        _Occlusion ("AO Strength", Range(0,1)) = 1
        _Sharpness ("Blend Sharpness", Range(1,16)) = 6
        [Toggle(_TOPLAYER)] _UseTop ("Top Layer", Float) = 0
        _TopTex ("Top Albedo", 2D) = "white" {}
        [Normal] _TopBump ("Top Normal", 2D) = "bump" {}
        _TopScale ("Top meters per tile", Float) = 2
        _TopAmount ("Top Amount", Range(0,1)) = 0.4
        _TopSharp ("Top Sharpness", Range(1,32)) = 8
        _Wetness ("Wetness", Range(0,1)) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        LOD 300

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows
        #pragma target 3.0
        #pragma shader_feature_local _TOPLAYER

        sampler2D _MainTex, _BumpMap, _MaskMap, _TopTex, _TopBump;
        fixed4 _Color;
        half _BumpScale, _Scale, _Smoothness, _Occlusion, _Sharpness, _TopScale, _TopAmount, _TopSharp, _Wetness;

        struct Input
        {
            float3 worldPos;
            float3 worldNormal;
            INTERNAL_DATA
        };

        float3 WorldToTangentNormalVector(Input IN, float3 normal)
        {
            float3 t2w0 = WorldNormalVector(IN, float3(1, 0, 0));
            float3 t2w1 = WorldNormalVector(IN, float3(0, 1, 0));
            float3 t2w2 = WorldNormalVector(IN, float3(0, 0, 1));
            float3x3 t2w = float3x3(t2w0, t2w1, t2w2);
            return normalize(mul(t2w, normal));
        }

        // whiteout-blended triplanar normal (returns world-space normal)
        float3 TriNormal(sampler2D tex, float2 uvX, float2 uvY, float2 uvZ, float3 n, float3 w, half strength)
        {
            float3 tx = UnpackNormal(tex2D(tex, uvX)); tx.xy *= strength;
            float3 ty = UnpackNormal(tex2D(tex, uvY)); ty.xy *= strength;
            float3 tz = UnpackNormal(tex2D(tex, uvZ)); tz.xy *= strength;
            tx = float3(tx.xy + n.zy, abs(tx.z) * n.x);
            ty = float3(ty.xy + n.xz, abs(ty.z) * n.y);
            tz = float3(tz.xy + n.xy, abs(tz.z) * n.z);
            return normalize(tx.zyx * w.x + ty.xzy * w.y + tz.xyz * w.z);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            IN.worldNormal = WorldNormalVector(IN, float3(0, 0, 1));
            float3 n = normalize(IN.worldNormal);
            float3 w = pow(abs(n), _Sharpness);
            w /= (w.x + w.y + w.z + 1e-5);
            float3 p = IN.worldPos / max(_Scale, 0.01);
            float2 uvX = p.zy, uvY = p.xz, uvZ = p.xy;

            fixed4 albedo = tex2D(_MainTex, uvX) * w.x + tex2D(_MainTex, uvY) * w.y + tex2D(_MainTex, uvZ) * w.z;
            fixed4 mask = tex2D(_MaskMap, uvX) * w.x + tex2D(_MaskMap, uvY) * w.y + tex2D(_MaskMap, uvZ) * w.z;
            float3 wn = TriNormal(_BumpMap, uvX, uvY, uvZ, n, w, _BumpScale);
            half smooth = mask.a * _Smoothness;

#if _TOPLAYER
            float2 tuv = IN.worldPos.xz / max(_TopScale, 0.01);
            half top = saturate((n.y - (1 - _TopAmount)) * _TopSharp) * saturate(mask.b * 1.5 + 0.2);
            fixed4 ta = tex2D(_TopTex, tuv);
            float3 tn = UnpackNormal(tex2D(_TopBump, tuv));
            float3 twn = normalize(float3(tn.x, 1, tn.y));
            albedo = lerp(albedo, ta, top);
            wn = normalize(lerp(wn, twn, top));
            smooth = lerp(smooth, 0.15, top);
#endif
            // wet surfaces: darker and glossier, mostly in cavities
            half wet = _Wetness * saturate(1.2 - mask.b);
            albedo.rgb *= lerp(1, 0.6, wet);
            smooth = lerp(smooth, 0.85, wet);

            o.Albedo = albedo.rgb * _Color.rgb;
            o.Metallic = mask.r;
            o.Smoothness = saturate(smooth);
            o.Occlusion = lerp(1, mask.g, _Occlusion);
            o.Normal = WorldToTangentNormalVector(IN, wn);
        }
        ENDCG
    }
    FallBack "Diffuse"
}
