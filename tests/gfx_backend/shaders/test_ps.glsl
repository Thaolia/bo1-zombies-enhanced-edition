#version 430 core
layout(std140, binding = 1) uniform BO1PixelConstants { vec4 ps_c_reg[256]; vec4 bo1_alpha_test; };
layout(binding = 0) uniform sampler2D s0;
layout(binding = 1) uniform sampler2DShadow s1;
layout(location = 0) in vec4 io_colour;
layout(location = 1) in vec2 io_uv;
layout(location = 0) out vec4 bo1_color0;
void main()
{
    if (ps_c_reg[0].x > 2.5)
        bo1_color0 = vec4(textureProj(s1, vec4(io_uv, ps_c_reg[0].y, 1.0)));
    else if (ps_c_reg[0].x > 1.5)
        bo1_color0 = vec4(floor(gl_FragCoord.xy) / 255.0, 0.0, 1.0);
    else if (ps_c_reg[0].x > 0.5)
        bo1_color0 = texture(s0, io_uv);
    else
        bo1_color0 = io_colour;
}
