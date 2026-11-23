#version 450
// The Vulkan backend's Present (gb_vk.cpp): one triangle covering the swapchain image, with the image's texture
// coordinates. Vulkan's framebuffer rows count from the top, as the image's do: no flip.
layout(location = 0) out vec2 uv;
void main()
{
    vec2 corner = vec2((gl_VertexIndex << 1) & 2, gl_VertexIndex & 2);
    uv = corner;
    gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
