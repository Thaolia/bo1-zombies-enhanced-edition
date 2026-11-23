#version 430 core
// Supersampling's downsample (d3d9emu_upscale.cpp): each output pixel is the mean of the source pixels under it, each
// weighted by the part of it the output pixel covers, a box filter exact at any ratio (1.5 and 2 here). Bilinear
// filtering reads only 4 of the 9 pixels a 1.5x pixel covers.

layout(std140, binding = 1) uniform BO1Downsample
{
    vec4 bo1_ratio; // source pixels per output pixel (x, y), source width, height
};
layout(binding = 0) uniform sampler2D bo1_downsample_src;
layout(location = 0) out vec4 bo1_color0;

void main()
{
    vec2 low = floor(gl_FragCoord.xy) * bo1_ratio.xy;
    vec2 high = min(low + bo1_ratio.xy, bo1_ratio.zw);
    ivec2 first = ivec2(low);
    ivec2 last = ivec2(ceil(high)) - 1;
    vec4 sum = vec4(0.0);
    float total = 0.0;
    for (int y = first.y; y <= last.y; ++y)
    {
        float height = min(high.y, float(y + 1)) - max(low.y, float(y));
        for (int x = first.x; x <= last.x; ++x)
        {
            float weight = height * (min(high.x, float(x + 1)) - max(low.x, float(x)));
            sum += weight * texelFetch(bo1_downsample_src, ivec2(x, y), 0);
            total += weight;
        }
    }
    bo1_color0 = sum / total;
}
