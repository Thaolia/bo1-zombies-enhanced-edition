#version 450
// The Vulkan backend's Present (gb_vk.cpp): the frame, filtered to the swapchain's size, through D3D9's gamma ramp
// (a 256x1 texture, one channel per colour), as the GL backend presents it.
layout(binding = 0) uniform sampler2D image;
layout(binding = 1) uniform sampler2D ramp;
layout(location = 0) in vec2 uv;
layout(location = 0) out vec4 color;
void main()
{
    ivec3 i = ivec3(clamp(texture(image, uv).rgb, 0.0, 1.0) * 255.0 + 0.5);
    color = vec4(texelFetch(ramp, ivec2(i.r, 0), 0).r, texelFetch(ramp, ivec2(i.g, 0), 0).g,
                 texelFetch(ramp, ivec2(i.b, 0), 0).b, 1.0);
}
