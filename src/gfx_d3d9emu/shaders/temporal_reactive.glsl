#version 430 core
// The temporal upscaler's reactive mask (d3d9emu_temporal.cpp): how much each pixel changed while the scene's emissive
// draws (particles, smoke, sparks, glows, muzzle flashes) went on, from copies of the scene taken just before and just
// after them, in the same frame and with the same jitter. Where they drew, the upscaler trusts its history less, so
// moving effects do not leave trails. FSR 2's ffxFsr2ContextGenerateReactiveMask computes the same from its
// "opaque only" input (the largest component's difference, scaled), with a ramp instead of its binary threshold: a
// smoke puff fades out smoothly instead of going 0 or 0.9 from one pixel to the next. Changes below 0.08 count for
// nothing: Kino's scene has a full-screen emissive layer that changes every pixel by about 0.06, and a mask that high
// everywhere costs the whole image some of its anti-aliasing. 0.9, never 1, is FSR 2's advice for blended effects.

layout(binding = 0) uniform sampler2D bo1_opaque;
layout(binding = 1) uniform sampler2D bo1_blended;
layout(location = 0) out float bo1_reactive;

void main()
{
    ivec2 pixel = ivec2(gl_FragCoord.xy);
    vec3 change = abs(texelFetch(bo1_blended, pixel, 0).rgb - texelFetch(bo1_opaque, pixel, 0).rgb);
    bo1_reactive = clamp((max(change.r, max(change.g, change.b)) - 0.08) * 2.5, 0.0, 0.9);
}
