#version 430 core
// FSR 1.0 EASU (edge adaptive spatial upsampling): FsrEasuF, the non-packed 32-bit path of AMD's ffx_fsr1.h, ported
// to plain GLSL with the ffx_a.h helpers it calls. Copyright (c) 2021 Advanced Micro Devices, Inc., MIT licence
// (third_party/fidelityfx_fsr1/LICENSE). The constants are FsrEasuCon's (d3d9emu_upscale.cpp).

layout(std140, binding = 1) uniform BO1Upscale
{
    uvec4 bo1_con[4];
};
layout(binding = 0) uniform sampler2D bo1_upscale_src;
layout(location = 0) out vec4 bo1_color0;

float APrxLoRcpF1(float a)
{
    return uintBitsToFloat(0x7ef07ebbu - floatBitsToUint(a));
}

float APrxLoRsqF1(float a)
{
    return uintBitsToFloat(0x5f347d74u - (floatBitsToUint(a) >> 1u));
}

vec3 AMin3F3(vec3 x, vec3 y, vec3 z)
{
    return min(x, min(y, z));
}

vec3 AMax3F3(vec3 x, vec3 y, vec3 z)
{
    return max(x, max(y, z));
}

void FsrEasuTapF(inout vec3 aC, inout float aW, vec2 off, vec2 dir, vec2 len, float lob, float clp, vec3 c)
{
    vec2 v;
    v.x = (off.x * (dir.x)) + (off.y * dir.y);
    v.y = (off.x * (-dir.y)) + (off.y * dir.x);
    v *= len;
    float d2 = v.x * v.x + v.y * v.y;
    d2 = min(d2, clp);
    float wB = float(2.0 / 5.0) * d2 + float(-1.0);
    float wA = lob * d2 + float(-1.0);
    wB *= wB;
    wA *= wA;
    wB = float(25.0 / 16.0) * wB + float(-(25.0 / 16.0 - 1.0));
    float w = wB * wA;
    aC += c * w;
    aW += w;
}

void FsrEasuSetF(inout vec2 dir, inout float len, vec2 pp, bool biS, bool biT, bool biU, bool biV, float lA,
                 float lB, float lC, float lD, float lE)
{
    float w = 0.0;
    if (biS)
        w = (1.0 - pp.x) * (1.0 - pp.y);
    if (biT)
        w = pp.x * (1.0 - pp.y);
    if (biU)
        w = (1.0 - pp.x) * pp.y;
    if (biV)
        w = pp.x * pp.y;
    float dc = lD - lC;
    float cb = lC - lB;
    float lenX = max(abs(dc), abs(cb));
    lenX = APrxLoRcpF1(lenX);
    float dirX = lD - lB;
    dir.x += dirX * w;
    lenX = clamp(abs(dirX) * lenX, 0.0, 1.0);
    lenX *= lenX;
    len += lenX * w;
    float ec = lE - lC;
    float ca = lC - lA;
    float lenY = max(abs(ec), abs(ca));
    lenY = APrxLoRcpF1(lenY);
    float dirY = lE - lA;
    dir.y += dirY * w;
    lenY = clamp(abs(dirY) * lenY, 0.0, 1.0);
    lenY *= lenY;
    len += lenY * w;
}

void main()
{
    uvec4 con0 = bo1_con[0], con1 = bo1_con[1], con2 = bo1_con[2], con3 = bo1_con[3];
    // Fragment coordinates count from the top row, as the source texture's rows do (docs/RENDERER.md).
    uvec2 ip = uvec2(gl_FragCoord.xy);

    vec2 pp = vec2(ip) * uintBitsToFloat(con0.xy) + uintBitsToFloat(con0.zw);
    vec2 fp = floor(pp);
    pp -= fp;
    vec2 p0 = fp * uintBitsToFloat(con1.xy) + uintBitsToFloat(con1.zw);
    vec2 p1 = p0 + uintBitsToFloat(con2.xy);
    vec2 p2 = p0 + uintBitsToFloat(con2.zw);
    vec2 p3 = p0 + uintBitsToFloat(con3.xy);
    vec4 bczzR = textureGather(bo1_upscale_src, p0, 0);
    vec4 bczzG = textureGather(bo1_upscale_src, p0, 1);
    vec4 bczzB = textureGather(bo1_upscale_src, p0, 2);
    vec4 ijfeR = textureGather(bo1_upscale_src, p1, 0);
    vec4 ijfeG = textureGather(bo1_upscale_src, p1, 1);
    vec4 ijfeB = textureGather(bo1_upscale_src, p1, 2);
    vec4 klhgR = textureGather(bo1_upscale_src, p2, 0);
    vec4 klhgG = textureGather(bo1_upscale_src, p2, 1);
    vec4 klhgB = textureGather(bo1_upscale_src, p2, 2);
    vec4 zzonR = textureGather(bo1_upscale_src, p3, 0);
    vec4 zzonG = textureGather(bo1_upscale_src, p3, 1);
    vec4 zzonB = textureGather(bo1_upscale_src, p3, 2);

    vec4 bczzL = bczzB * vec4(0.5) + (bczzR * vec4(0.5) + bczzG);
    vec4 ijfeL = ijfeB * vec4(0.5) + (ijfeR * vec4(0.5) + ijfeG);
    vec4 klhgL = klhgB * vec4(0.5) + (klhgR * vec4(0.5) + klhgG);
    vec4 zzonL = zzonB * vec4(0.5) + (zzonR * vec4(0.5) + zzonG);
    float bL = bczzL.x;
    float cL = bczzL.y;
    float iL = ijfeL.x;
    float jL = ijfeL.y;
    float fL = ijfeL.z;
    float eL = ijfeL.w;
    float kL = klhgL.x;
    float lL = klhgL.y;
    float hL = klhgL.z;
    float gL = klhgL.w;
    float oL = zzonL.z;
    float nL = zzonL.w;
    vec2 dir = vec2(0.0);
    float len = 0.0;
    FsrEasuSetF(dir, len, pp, true, false, false, false, bL, eL, fL, gL, jL);
    FsrEasuSetF(dir, len, pp, false, true, false, false, cL, fL, gL, hL, kL);
    FsrEasuSetF(dir, len, pp, false, false, true, false, fL, iL, jL, kL, nL);
    FsrEasuSetF(dir, len, pp, false, false, false, true, gL, jL, kL, lL, oL);

    vec2 dir2 = dir * dir;
    float dirR = dir2.x + dir2.y;
    bool zro = dirR < float(1.0 / 32768.0);
    dirR = APrxLoRsqF1(dirR);
    dirR = zro ? 1.0 : dirR;
    dir.x = zro ? 1.0 : dir.x;
    dir *= vec2(dirR);
    len = len * 0.5;
    len *= len;
    float stretch = (dir.x * dir.x + dir.y * dir.y) * APrxLoRcpF1(max(abs(dir.x), abs(dir.y)));
    vec2 len2 = vec2(1.0 + (stretch - 1.0) * len, 1.0 + -0.5 * len);
    float lob = 0.5 + float((1.0 / 4.0 - 0.04) - 0.5) * len;
    float clp = APrxLoRcpF1(lob);

    vec3 min4 = min(AMin3F3(vec3(ijfeR.z, ijfeG.z, ijfeB.z), vec3(klhgR.w, klhgG.w, klhgB.w),
                            vec3(ijfeR.y, ijfeG.y, ijfeB.y)),
                    vec3(klhgR.x, klhgG.x, klhgB.x));
    vec3 max4 = max(AMax3F3(vec3(ijfeR.z, ijfeG.z, ijfeB.z), vec3(klhgR.w, klhgG.w, klhgB.w),
                            vec3(ijfeR.y, ijfeG.y, ijfeB.y)),
                    vec3(klhgR.x, klhgG.x, klhgB.x));
    vec3 aC = vec3(0.0);
    float aW = 0.0;
    FsrEasuTapF(aC, aW, vec2(0.0, -1.0) - pp, dir, len2, lob, clp, vec3(bczzR.x, bczzG.x, bczzB.x)); // b
    FsrEasuTapF(aC, aW, vec2(1.0, -1.0) - pp, dir, len2, lob, clp, vec3(bczzR.y, bczzG.y, bczzB.y)); // c
    FsrEasuTapF(aC, aW, vec2(-1.0, 1.0) - pp, dir, len2, lob, clp, vec3(ijfeR.x, ijfeG.x, ijfeB.x)); // i
    FsrEasuTapF(aC, aW, vec2(0.0, 1.0) - pp, dir, len2, lob, clp, vec3(ijfeR.y, ijfeG.y, ijfeB.y));  // j
    FsrEasuTapF(aC, aW, vec2(0.0, 0.0) - pp, dir, len2, lob, clp, vec3(ijfeR.z, ijfeG.z, ijfeB.z));  // f
    FsrEasuTapF(aC, aW, vec2(-1.0, 0.0) - pp, dir, len2, lob, clp, vec3(ijfeR.w, ijfeG.w, ijfeB.w)); // e
    FsrEasuTapF(aC, aW, vec2(1.0, 1.0) - pp, dir, len2, lob, clp, vec3(klhgR.x, klhgG.x, klhgB.x));  // k
    FsrEasuTapF(aC, aW, vec2(2.0, 1.0) - pp, dir, len2, lob, clp, vec3(klhgR.y, klhgG.y, klhgB.y));  // l
    FsrEasuTapF(aC, aW, vec2(2.0, 0.0) - pp, dir, len2, lob, clp, vec3(klhgR.z, klhgG.z, klhgB.z));  // h
    FsrEasuTapF(aC, aW, vec2(1.0, 0.0) - pp, dir, len2, lob, clp, vec3(klhgR.w, klhgG.w, klhgB.w));  // g
    FsrEasuTapF(aC, aW, vec2(1.0, 2.0) - pp, dir, len2, lob, clp, vec3(zzonR.z, zzonG.z, zzonB.z));  // o
    FsrEasuTapF(aC, aW, vec2(0.0, 2.0) - pp, dir, len2, lob, clp, vec3(zzonR.w, zzonG.w, zzonB.w));  // n
    vec3 pix = min(max4, max(min4, aC * vec3(1.0 / aW)));
    bo1_color0 = vec4(pix, 1.0);
}
