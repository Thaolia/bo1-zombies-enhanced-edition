#version 430 core
layout(std140, binding = 0) uniform BO1VertexConstants { vec4 vs_c_reg[256]; vec4 bo1_pos_fixup; };
layout(location = 0) in vec4 position;
layout(location = 1) in vec4 colour;
layout(location = 16) out vec4 io_10_0;
void main()
{
    gl_Position = position;
    io_10_0 = colour;
    io_10_0 = clamp(io_10_0, 0.0, 1.0);
    gl_Position.xy += bo1_pos_fixup.xy * gl_Position.w;
}
