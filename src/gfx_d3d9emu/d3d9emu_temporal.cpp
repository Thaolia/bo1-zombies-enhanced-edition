// The temporal upscaler's frontend side (d3d9emu_temporal.h, docs/VULKAN.md step 6).

#include "d3d9emu_temporal.h"

#include "d3d9emu.h"
#include "upscale_shaders.h"

#include <cmath>
#include <cstring>

namespace d3d9emu
{
namespace
{
constexpr uint64_t kHashVertex = 0xB01F5A1000000004ull;
constexpr uint64_t kHashMotion = 0xB01F5A1000000005ull;

template <size_t N>
gb::Shader *Create(gb::Stage stage, uint64_t hash, const unsigned char (&code)[N])
{
    return gb::CreateShader(stage, hash, reinterpret_cast<const char *>(code), uint32_t(N));
}

double Halton(uint32_t index, uint32_t base)
{
    double f = 1.0, result = 0.0;
    for (uint32_t i = index; i > 0; i /= base)
    {
        f /= double(base);
        result += f * double(i % base);
    }
    return result;
}

// a * b, row vectors (D3D)
void Multiply(const double a[4][4], const double b[4][4], double out[4][4])
{
    for (int r = 0; r < 4; ++r)
        for (int c = 0; c < 4; ++c)
            out[r][c] = a[r][0] * b[0][c] + a[r][1] * b[1][c] + a[r][2] * b[2][c] + a[r][3] * b[3][c];
}

void ToDouble(const float in[4][4], double out[4][4])
{
    for (int r = 0; r < 4; ++r)
        for (int c = 0; c < 4; ++c)
            out[r][c] = in[r][c];
}

void ReleaseTexture(gb::Texture *&texture)
{
    gb::DestroyTexture(texture);
    texture = nullptr;
}
} // namespace

Temporal::~Temporal()
{
    ReleaseTargets();
    gb::DestroyShader(m_vertex);
    gb::DestroyShader(m_motion);
}

void Temporal::ReleaseTargets()
{
    ReleaseTexture(m_colorIn);
    ReleaseTexture(m_depthIn);
    ReleaseTexture(m_motionOut);
    ReleaseTexture(m_depthOut);
    ReleaseTexture(m_output);
    m_depthFormat = gb::Format::Unknown;
    m_renderWidth = m_renderHeight = m_outputWidth = m_outputHeight = 0;
    m_history = false;
}

bool Temporal::Fail(const char *why)
{
    m_failed = true;
    Logf("d3d9emu: upscale: no temporal upscaling (%s): FSR 1.0 instead", why);
    return false;
}

void Temporal::Jitter(uint32_t renderWidth, uint32_t renderHeight, uint32_t outputWidth, uint32_t *phase, float *x,
                      float *y)
{
    (void)renderHeight;
    const double ratio = double(outputWidth) / double(renderWidth ? renderWidth : 1);
    const uint32_t count = uint32_t(8.0 * ratio * ratio + 0.5);
    m_phase = (m_phase + 1) % (count ? count : 1);
    *phase = m_phase;
    *x = float(Halton(m_phase + 1, 2) - 0.5);
    *y = float(Halton(m_phase + 1, 3) - 0.5);
}

bool Temporal::PrepareShaders()
{
    if (!m_shadersTried)
    {
        m_shadersTried = true;
        switch (ShaderPackForm())
        {
        case ShaderForm::Glsl:
            m_vertex = Create(gb::Stage::Vertex, kHashVertex, upscale_shaders::kGlslVs);
            m_motion = Create(gb::Stage::Pixel, kHashMotion, upscale_shaders::kGlslMotion);
            break;
        case ShaderForm::Spirv:
#if defined(BO1_UPSCALE_HAS_SPIRV)
            m_vertex = Create(gb::Stage::Vertex, kHashVertex, upscale_shaders::kSpirvVs);
            m_motion = Create(gb::Stage::Pixel, kHashMotion, upscale_shaders::kSpirvMotion);
#endif
            break;
        default:
            break;
        }
        m_sampler = gb::GetSampler({gb::Filter::Nearest, gb::Filter::Nearest, gb::MipFilter::None, gb::Address::Clamp,
                                    gb::Address::Clamp, gb::Address::Clamp, 1, false});
        if (m_vertex && m_motion)
        {
            gb::PipelineDesc desc;
            desc.vertex = m_vertex;
            desc.pixel = m_motion;
            desc.colorCount = 2;
            desc.colorFormats[0] = gb::Format::RG16F;
            desc.colorFormats[1] = gb::Format::R32F;
            m_pipeline = gb::GetPipeline(desc);
        }
    }
    return m_pipeline && m_sampler;
}

bool Temporal::PrepareTargets(gb::Format depthFormat, uint32_t renderWidth, uint32_t renderHeight,
                              uint32_t outputWidth, uint32_t outputHeight)
{
    if (m_output && m_depthFormat == depthFormat && m_renderWidth == renderWidth && m_renderHeight == renderHeight &&
        m_outputWidth == outputWidth && m_outputHeight == outputHeight)
        return true;
    ReleaseTargets();
    gb::TextureDesc desc = {};
    desc.type = gb::TextureType::Tex2D;
    desc.usage = gb::Usage::RenderTarget;
    desc.sampled = true;
    desc.depth = 1;
    desc.levels = 1;
    desc.samples = 1;
    desc.width = uint16_t(renderWidth);
    desc.height = uint16_t(renderHeight);
    desc.format = gb::Format::RGBA8;
    m_colorIn = gb::CreateTexture(desc);
    desc.format = gb::Format::RG16F;
    m_motionOut = gb::CreateTexture(desc);
    desc.format = gb::Format::R32F;
    m_depthOut = gb::CreateTexture(desc);
    desc.format = depthFormat;
    desc.usage = gb::Usage::DepthStencil;
    m_depthIn = gb::CreateTexture(desc);
    desc.format = gb::Format::RGBA8;
    desc.usage = gb::Usage::RenderTarget;
    desc.width = uint16_t(outputWidth);
    desc.height = uint16_t(outputHeight);
    m_output = gb::CreateTexture(desc);
    if (!m_colorIn || !m_motionOut || !m_depthOut || !m_depthIn || !m_output)
    {
        ReleaseTargets();
        return false;
    }
    m_depthFormat = depthFormat;
    m_renderWidth = renderWidth;
    m_renderHeight = renderHeight;
    m_outputWidth = outputWidth;
    m_outputHeight = outputHeight;
    return true;
}

bool Temporal::Run(gb::Texture *color, gb::Texture *depth, gb::Format depthFormat, uint32_t renderWidth,
                   uint32_t renderHeight, uint32_t outputWidth, uint32_t outputHeight, const TemporalView &view,
                   float sharpness, gb::UpscalePreset preset, float frameMs, gb::Texture *target)
{
    if (m_failed)
        return false;
    const gb::Caps &caps = gb::GetCaps();
    const uint8_t target_flags = gb::FORMAT_SAMPLED | gb::FORMAT_COLOR_TARGET;
    if (!caps.temporalUpscale)
        return Fail("the backend has no temporal upscaler");
    if ((caps.formatFlags[int(gb::Format::RG16F)] & target_flags) != target_flags ||
        (caps.formatFlags[int(gb::Format::R32F)] & target_flags) != target_flags ||
        (caps.formatFlags[int(gb::Format::RGBA8)] & target_flags) != target_flags ||
        !(caps.formatFlags[int(depthFormat)] & gb::FORMAT_SAMPLED))
        return Fail("a format it needs is missing");
    if (!PrepareShaders())
        return Fail("its motion shader did not build");
    if (!PrepareTargets(depthFormat, renderWidth, renderHeight, outputWidth, outputHeight))
        return Fail("its textures could not be made");

    // This frame's clip space to the previous frame's: inverse(viewProjection) * previous viewProjection.
    double inverse[4][4], current[4][4], reproject[4][4];
    ToDouble(view.inverseViewProjection, inverse);
    ToDouble(view.viewProjection, current);
    const bool reset = !m_history;
    Multiply(inverse, reset ? current : m_previous, reproject);
    std::memcpy(m_previous, current, sizeof(current));
    m_history = true;

    const gb::Rect render = {0, 0, renderWidth, renderHeight};
    gb::Blit(color, 0, 0, render, m_colorIn, 0, 0, render, gb::Filter::Nearest);
    gb::Blit(depth, 0, 0, render, m_depthIn, 0, 0, render, gb::Filter::Nearest);

    float constants[20];
    for (int r = 0; r < 4; ++r)
        for (int c = 0; c < 4; ++c)
            constants[r * 4 + c] = float(reproject[r][c]);
    constants[16] = float(renderWidth);
    constants[17] = float(renderHeight);
    constants[18] = 1.0f / float(renderWidth);
    constants[19] = 1.0f / float(renderHeight);
    gb::PassDesc pass;
    pass.colorCount = 2;
    pass.color[0].texture = m_motionOut;
    pass.color[0].load = gb::LoadOp::DontCare;
    pass.color[1].texture = m_depthOut;
    pass.color[1].load = gb::LoadOp::DontCare;
    gb::BeginPass(pass);
    gb::DrawState state;
    state.pipeline = m_pipeline;
    state.textures[0] = {m_depthIn, m_sampler};
    state.pixelConstants = gb::AllocUniforms(constants, sizeof(constants));
    state.vertexConstants = state.pixelConstants;
    state.viewport = {0.0f, 0.0f, float(renderWidth), float(renderHeight), 0.0f, 1.0f};
    state.scissor = render;
    gb::Draw(state, gb::Primitive::TriangleList, 3, 0);
    gb::EndPass();

    gb::TemporalUpscaleDesc desc = {};
    desc.color = m_colorIn;
    desc.depth = m_depthOut;
    desc.motion = m_motionOut;
    desc.output = m_output;
    desc.renderWidth = uint16_t(renderWidth);
    desc.renderHeight = uint16_t(renderHeight);
    desc.outputWidth = uint16_t(outputWidth);
    desc.outputHeight = uint16_t(outputHeight);
    // The offset the engine added to the projection (R_RenderScene): 2 * x / width at [2][0], -2 * y / height at [2][1].
    desc.jitterX = view.projection[2][0] * float(renderWidth) * 0.5f;
    desc.jitterY = -view.projection[2][1] * float(renderHeight) * 0.5f;
    desc.frameMs = frameMs;
    desc.sharpness = sharpness;
    desc.cameraNear = view.zNear;
    desc.cameraFar = 3.0e38f; // the engine's projection has no far plane
    desc.verticalFov = 2.0f * std::atan(view.tanHalfFovY);
    desc.reset = reset;
    desc.preset = preset;
    if (!gb::TemporalUpscale(desc))
        return Fail("the backend's upscaler failed");
    const gb::Rect output = {0, 0, outputWidth, outputHeight};
    gb::Blit(m_output, 0, 0, output, target, 0, 0, output, gb::Filter::Nearest);
    return true;
}
} // namespace d3d9emu
