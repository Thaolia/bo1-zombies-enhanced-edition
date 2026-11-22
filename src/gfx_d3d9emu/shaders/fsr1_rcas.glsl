#version 430 core
// FSR 1.0 RCAS (robust contrast adaptive sharpening): FsrRcasF, the non-packed 32-bit path of AMD's ffx_fsr1.h
// without its optional denoise and alpha pass-through, ported to plain GLSL with the ffx_a.h helpers it calls.
// Copyright (c) 2021 Advanced Micro Devices, Inc., MIT licence (third_party/fidelityfx_fsr1/LICENSE). bo1_con[0].x is
// FsrRcasCon's con[0] (d3d9emu_upscale.cpp).

layout(std140, binding = 1) uniform BO1Upscale
{
    uvec4 bo1_con[4];
};
layout(binding = 0) uniform sampler2D bo1_upscale_src;
layout(location = 0) out vec4 bo1_color0;

#define FSR_RCAS_LIMIT (0.25 - (1.0 / 16.0))

float APrxMedRcpF1(float a)
{
    float b = uintBitsToFloat(0x7ef19fffu - floatBitsToUint(a));
    return b * (-b * a + 2.0);
}

float AMin3F1(float x, float y, float z)
{
    return min(x, min(y, z));
}

float AMax3F1(float x, float y, float z)
{
    return max(x, max(y, z));
}

// HLSL's Load of a texel outside the texture returns 0, which would darken the frame's edges here: clamp instead.
vec3 FsrRcasLoadF(ivec2 p)
{
    return texelFetch(bo1_upscale_src, clamp(p, ivec2(0), textureSize(bo1_upscale_src, 0) - 1), 0).rgb;
}

void main()
{
    ivec2 sp = ivec2(gl_FragCoord.xy);
    vec3 b = FsrRcasLoadF(sp + ivec2(0, -1));
    vec3 d = FsrRcasLoadF(sp + ivec2(-1, 0));
    vec3 e = FsrRcasLoadF(sp);
    vec3 f = FsrRcasLoadF(sp + ivec2(1, 0));
    vec3 h = FsrRcasLoadF(sp + ivec2(0, 1));
    float bR = b.r, bG = b.g, bB = b.b;
    float dR = d.r, dG = d.g, dB = d.b;
    float eR = e.r, eG = e.g, eB = e.b;
    float fR = f.r, fG = f.g, fB = f.b;
    float hR = h.r, hG = h.g, hB = h.b;
    float mn4R = min(AMin3F1(bR, dR, fR), hR);
    float mn4G = min(AMin3F1(bG, dG, fG), hG);
    float mn4B = min(AMin3F1(bB, dB, fB), hB);
    float mx4R = max(AMax3F1(bR, dR, fR), hR);
    float mx4G = max(AMax3F1(bG, dG, fG), hG);
    float mx4B = max(AMax3F1(bB, dB, fB), hB);
    vec2 peakC = vec2(1.0, -1.0 * 4.0);
    // AMD's code divides by zero on a black ring (mx4 = 0) or a white one (mn4 = 1) and relies on the hardware's
    // min/max dropping the NaN; GLSL leaves that undefined, so the divisors stay off zero. Same result elsewhere.
    const float kTiny = 1.0 / 65536.0;
    float hitMinR = min(mn4R, eR) / max(4.0 * mx4R, kTiny);
    float hitMinG = min(mn4G, eG) / max(4.0 * mx4G, kTiny);
    float hitMinB = min(mn4B, eB) / max(4.0 * mx4B, kTiny);
    float hitMaxR = (peakC.x - max(mx4R, eR)) / min(4.0 * mn4R + peakC.y, -kTiny);
    float hitMaxG = (peakC.x - max(mx4G, eG)) / min(4.0 * mn4G + peakC.y, -kTiny);
    float hitMaxB = (peakC.x - max(mx4B, eB)) / min(4.0 * mn4B + peakC.y, -kTiny);
    float lobeR = max(-hitMinR, hitMaxR);
    float lobeG = max(-hitMinG, hitMaxG);
    float lobeB = max(-hitMinB, hitMaxB);
    float lobe = max(float(-FSR_RCAS_LIMIT), min(AMax3F1(lobeR, lobeG, lobeB), 0.0)) * uintBitsToFloat(bo1_con[0].x);
    float rcpL = APrxMedRcpF1(4.0 * lobe + 1.0);
    bo1_color0 = vec4((lobe * bR + lobe * dR + lobe * hR + lobe * fR + eR) * rcpL,
                      (lobe * bG + lobe * dG + lobe * hG + lobe * fG + eG) * rcpL,
                      (lobe * bB + lobe * dB + lobe * hB + lobe * fB + eB) * rcpL, 1.0);
}
