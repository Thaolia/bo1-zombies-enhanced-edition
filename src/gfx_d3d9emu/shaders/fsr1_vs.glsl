#version 430 core
// The upscaler's vertex shader (d3d9emu_upscale.cpp): one triangle covering the whole target, no vertex input.
void main()
{
    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
