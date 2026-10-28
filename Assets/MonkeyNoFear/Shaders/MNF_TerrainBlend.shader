// Forest ground: forest floor base, blended by vertex colour into mud (R), moss (G) and rock (B).
// Ground layers are projected from above; rock uses triplanar so cliffs and banks do not stretch.
Shader "MNF/TerrainBlend"
{
    Properties
    {
        _BaseTex ("Forest Floor", 2D) = "white" {}
        [Normal] _BaseBump ("Forest Floor Normal", 2D) = "bump" {}
        _BaseMask ("Forest Floor Mask", 2D) = "white" {}
        _MudTex ("Mud", 2D) = "white" {}
        [Normal] _MudBump ("Mud Normal", 2D) = "bump" {}
        _MudMask ("Mud Mask", 2D) = "white" {}
        _MossTex ("Moss", 2D) = "white" {}
        [Normal] _MossBump ("Moss Normal", 2D) = "bump" {}
        _RockTex ("Rock", 2D) = "white" {}
        [Normal] _RockBump ("Rock Normal", 2D) = "bump" {}
        _RockMask ("Rock Mask", 2D) = "white" {}
        _GroundScale ("Ground meters per tile", Float) = 3
        _RockScale ("Rock meters per tile", Float) = 4
        _SlopeRock ("Steep slopes become rock", Range(0,1)) = 0.55
        _Tint ("Tint", Color) = (1,1,1,1)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        LOD 300
        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows
        #pragma target 3.0

        sampler2D _BaseTex, _BaseBump, _BaseMask, _MudTex, _MudBump, _MudMask, _MossTex, _MossBump, _RockTex, _RockBump, _RockMask;
        half _GroundScale, _RockScale, _SlopeRock;
        fixed4 _Tint;

        struct Input
        {
            float3 worldPos;
            float3 worldNormal;
            float4 color : COLOR;
            INTERNAL_DATA
        };

        float3 WorldToTangentNormalVector(Input IN, float3 normal)
        {
            float3 t2w0 = WorldNormalVector(IN, float3(1, 0, 0));
            float3 t2w1 = WorldNormalVector(IN, float3(0, 1, 0));
            float3 t2w2 = WorldNormalVector(IN, float3(0, 0, 1));
            return normalize(mul(float3x3(t2w0, t2w1, t2w2), normal));
        }

        float3 GroundNormal(sampler2D tex, float2 uv)
        {
            float3 t = UnpackNormal(tex2D(tex, uv));
            return normalize(float3(t.x, 1, t.y));
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            IN.worldNormal = WorldNormalVector(IN, float3(0, 0, 1));
            float3 n = normalize(IN.worldNormal);
            float2 guv = IN.worldPos.xz / _GroundScale;

            fixed4 base = tex2D(_BaseTex, guv);
            fixed4 baseM = tex2D(_BaseMask, guv);
            float3 nrm = GroundNormal(_BaseBump, guv);
            half smooth = baseM.a;
            half ao = baseM.g;

            // height-aware blends: layers fill cavities first
            half h = baseM.b;
            half mud = saturate((IN.color.r * 1.6 - h) * 3);
            half moss = saturate((IN.color.g * 1.6 - (1 - h)) * 3);

            fixed4 mudC = tex2D(_MudTex, guv * 1.3);
            fixed4 mudM = tex2D(_MudMask, guv * 1.3);
            base = lerp(base, mudC, mud);
            nrm = normalize(lerp(nrm, GroundNormal(_MudBump, guv * 1.3), mud));
            smooth = lerp(smooth, mudM.a, mud);

            fixed4 mossC = tex2D(_MossTex, guv * 0.8);
            base = lerp(base, mossC, moss);
            nrm = normalize(lerp(nrm, GroundNormal(_MossBump, guv * 0.8), moss));
            smooth = lerp(smooth, 0.1, moss);

            // rock: painted (B) or steep slopes, triplanar
            half steep = saturate((1 - n.y - (1 - _SlopeRock)) * 6);
            half rock = saturate(max(IN.color.b, steep));
            float3 w = pow(abs(n), 6); w /= (w.x + w.y + w.z + 1e-5);
            float3 p = IN.worldPos / _RockScale;
            fixed4 rockC = tex2D(_RockTex, p.zy) * w.x + tex2D(_RockTex, p.xz) * w.y + tex2D(_RockTex, p.xy) * w.z;
            fixed4 rockM = tex2D(_RockMask, p.zy) * w.x + tex2D(_RockMask, p.xz) * w.y + tex2D(_RockMask, p.xy) * w.z;
            float3 rx = UnpackNormal(tex2D(_RockBump, p.zy));
            float3 ry = UnpackNormal(tex2D(_RockBump, p.xz));
            float3 rz = UnpackNormal(tex2D(_RockBump, p.xy));
            rx = float3(rx.xy + n.zy, abs(rx.z) * n.x);
            ry = float3(ry.xy + n.xz, abs(ry.z) * n.y);
            rz = float3(rz.xy + n.xy, abs(rz.z) * n.z);
            float3 rockN = normalize(rx.zyx * w.x + ry.xzy * w.y + rz.xyz * w.z);
            // ground normals are relative to "up": tilt them onto the actual surface
            float3 groundN = normalize(n + float3(nrm.x, 0, nrm.z));

            o.Albedo = lerp(base.rgb, rockC.rgb, rock) * _Tint.rgb;
            o.Smoothness = lerp(smooth, rockM.a, rock);
            o.Occlusion = lerp(ao, rockM.g, rock);
            o.Metallic = 0;
            o.Normal = WorldToTangentNormalVector(IN, normalize(lerp(groundN, rockN, rock)));
        }
        ENDCG
    }
    FallBack "Diffuse"
}
