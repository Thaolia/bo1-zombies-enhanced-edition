#version 430 core
layout(std140, binding = 0) uniform BO1VertexConstants { vec4 vs_c_reg[256]; vec4 bo1_pos_fixup; };
layout(location = 0) in vec4 position;
layout(location = 1) in vec4 colour;
layout(location = 2) in vec2 uv;
layout(location = 0) out vec4 io_colour;
layout(location = 1) out vec2 io_uv;
void main()
{
    gl_Position = position;
    io_colour = colour;
    io_uv = uv;
    gl_Position.xy += bo1_pos_fixup.xy * gl_Position.w;
}
