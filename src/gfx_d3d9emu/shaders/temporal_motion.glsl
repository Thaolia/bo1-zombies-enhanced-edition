#version 430 core
// The temporal upscaler's inputs from the scene's depth (d3d9emu_temporal.cpp): each pixel's camera motion, in render
// pixels from where it is to where it was the frame before, and the depth as a float. bo1_reproject's rows map this
// frame's clip space to the previous frame's (D3D's row vectors: x * row0 + y * row1 + z * row2 + row3), homogeneous
// all the way, so that the sky at an infinite distance moves with the camera's rotation only. Objects that move on
// their own get the camera's motion: the upscaler's own checks catch most of it.

layout(std140, binding = 1) uniform BO1Motion
{
    vec4 bo1_reproject[4];
    vec4 bo1_size; // render width, height, 1 / width, 1 / height
};
layout(binding = 0) uniform sampler2D bo1_scene_depth;
layout(location = 0) out vec2 bo1_motion;
layout(location = 1) out float bo1_depth;

void main()
{
    vec2 pixel = gl_FragCoord.xy;
    float depth = texelFetch(bo1_scene_depth, ivec2(pixel), 0).r;
    // D3D's clip space: the top row is y = +1.
    vec2 ndc = vec2(pixel.x * bo1_size.z * 2.0 - 1.0, 1.0 - pixel.y * bo1_size.w * 2.0);
    vec4 previous = ndc.x * bo1_reproject[0] + ndc.y * bo1_reproject[1] + depth * bo1_reproject[2] + bo1_reproject[3];
    vec2 motion = vec2(0.0);
    if (previous.w > 1e-6)
    {
        vec2 previousNdc = previous.xy / previous.w;
        vec2 previousPixel = vec2(previousNdc.x * 0.5 + 0.5, 0.5 - previousNdc.y * 0.5) * bo1_size.xy;
        motion = previousPixel - pixel;
    }
    bo1_motion = motion;
    bo1_depth = depth;
}
