// FSR 1.0 on the presented frame (d3d9emu_upscale.h). The shaders come from src/gfx_d3d9emu/shaders, embedded by
// tools/embed_shaders.py as GLSL, as DKSH in the Switch build and as SPIR-V in builds with the Vulkan backend: the
// backend gets the form shaders.pack has.

#include "d3d9emu_upscale.h"

#include "d3d9emu.h"
#include "upscale_shaders.h"

#include <cmath>
#include <cstddef>
#include <cstring>

namespace d3d9emu
{
namespace
{
// Fixed names for the backends' logs, not hashes of D3D9 bytecode: none of the 13 704 shaders of the zombies zones'
// pack has one (checked 2026-11-22).
constexpr uint64_t kHashVertex = 0xB01F5A1000000001ull;
constexpr uint64_t kHashEasu = 0xB01F5A1000000002ull;
constexpr uint64_t kHashRcas = 0xB01F5A1000000003ull;
constexpr uint64_t kHashDownsample = 0xB01F5A1000000007ull;

uint32_t FloatBits(float value)
{
    uint32_t bits;
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}

template <size_t N>
gb::Shader *Create(gb::Stage stage, uint64_t hash, const unsigned char (&code)[N])
{
    return gb::CreateShader(stage, hash, reinterpret_cast<const char *>(code), uint32_t(N));
}
} // namespace

void Fsr1EasuConstants(uint32_t con[16], float inputWidth, float inputHeight, float outputWidth, float outputHeight)
{
    // The whole back buffer is the input viewport, so the viewport and the resource have the same size.
    con[0] = FloatBits(inputWidth * (1.0f / outputWidth));
    con[1] = FloatBits(inputHeight * (1.0f / outputHeight));
    con[2] = FloatBits(0.5f * inputWidth * (1.0f / outputWidth) - 0.5f);
    con[3] = FloatBits(0.5f * inputHeight * (1.0f / outputHeight) - 0.5f);
    con[4] = FloatBits(1.0f / inputWidth);
    con[5] = FloatBits(1.0f / inputHeight);
    con[6] = FloatBits(1.0f * (1.0f / inputWidth));
    con[7] = FloatBits(-1.0f * (1.0f / inputHeight));
    con[8] = FloatBits(-1.0f * (1.0f / inputWidth));
    con[9] = FloatBits(2.0f * (1.0f / inputHeight));
    con[10] = FloatBits(1.0f * (1.0f / inputWidth));
    con[11] = FloatBits(2.0f * (1.0f / inputHeight));
    con[12] = FloatBits(0.0f * (1.0f / inputWidth));
    con[13] = FloatBits(4.0f * (1.0f / inputHeight));
    con[14] = con[15] = 0;
}

void Fsr1RcasConstants(uint32_t con[16], float sharpness)
{
    std::memset(con, 0, 16 * sizeof(uint32_t));
    // The 32-bit shader reads only con[0]; con[1] holds the packed half pair the 16-bit paths read, left out here.
    con[0] = FloatBits(std::exp2(-sharpness));
}

bool Upscaler::Supports(gb::Format format)
{
    const uint8_t needed = gb::FORMAT_SAMPLED | gb::FORMAT_COLOR_TARGET | gb::FORMAT_FILTERABLE;
    return (gb::GetCaps().formatFlags[int(format)] & needed) == needed;
}

Upscaler::~Upscaler()
{
    ReleaseTargets();
    gb::DestroyShader(m_vertex);
    gb::DestroyShader(m_easu);
    gb::DestroyShader(m_rcas);
    gb::DestroyShader(m_downsample);
}

void Upscaler::ReleaseTargets()
{
    gb::DestroyTexture(m_input);
    gb::DestroyTexture(m_middle);
    gb::DestroyTexture(m_output);
    m_input = m_middle = m_output = nullptr;
    m_format = gb::Format::Unknown;
    m_sourceWidth = m_sourceHeight = m_outputWidth = m_outputHeight = 0;
}

bool Upscaler::PrepareShaders(gb::Format format)
{
    if (!m_shadersTried)
    {
        m_shadersTried = true;
        switch (ShaderPackForm())
        {
        case ShaderForm::Glsl:
            m_vertex = Create(gb::Stage::Vertex, kHashVertex, upscale_shaders::kGlslVs);
            m_easu = Create(gb::Stage::Pixel, kHashEasu, upscale_shaders::kGlslEasu);
            m_rcas = Create(gb::Stage::Pixel, kHashRcas, upscale_shaders::kGlslRcas);
            m_downsample = Create(gb::Stage::Pixel, kHashDownsample, upscale_shaders::kGlslDownsample);
            break;
        case ShaderForm::Dksh:
#if defined(BO1_UPSCALE_HAS_DKSH)
            m_vertex = Create(gb::Stage::Vertex, kHashVertex, upscale_shaders::kDkshVs);
            m_easu = Create(gb::Stage::Pixel, kHashEasu, upscale_shaders::kDkshEasu);
            m_rcas = Create(gb::Stage::Pixel, kHashRcas, upscale_shaders::kDkshRcas);
            m_downsample = Create(gb::Stage::Pixel, kHashDownsample, upscale_shaders::kDkshDownsample);
#else
            Logf("d3d9emu: upscale: this build has no DKSH of the FSR 1.0 shaders: stretched instead");
#endif
            break;
        case ShaderForm::Spirv:
#if defined(BO1_UPSCALE_HAS_SPIRV)
            m_vertex = Create(gb::Stage::Vertex, kHashVertex, upscale_shaders::kSpirvVs);
            m_easu = Create(gb::Stage::Pixel, kHashEasu, upscale_shaders::kSpirvEasu);
            m_rcas = Create(gb::Stage::Pixel, kHashRcas, upscale_shaders::kSpirvRcas);
            m_downsample = Create(gb::Stage::Pixel, kHashDownsample, upscale_shaders::kSpirvDownsample);
#else
            Logf("d3d9emu: upscale: this build has no SPIR-V of the FSR 1.0 shaders: stretched instead");
#endif
            break;
        case ShaderForm::None:
            Logf("d3d9emu: upscale: no shaders.pack tells the shaders' form: stretched instead");
            break;
        }
        m_sampler = gb::GetSampler({gb::Filter::Linear, gb::Filter::Linear, gb::MipFilter::None, gb::Address::Clamp,
                                    gb::Address::Clamp, gb::Address::Clamp, 1, false});
    }
    if (!m_vertex || !m_sampler)
        return false;
    if (m_pipelineFormat != format)
    {
        gb::PipelineDesc desc;
        desc.vertex = m_vertex;
        desc.colorCount = 1;
        desc.colorFormats[0] = format;
        desc.pixel = m_easu;
        m_easuPipeline = m_easu ? gb::GetPipeline(desc) : nullptr;
        desc.pixel = m_rcas;
        m_rcasPipeline = m_rcas ? gb::GetPipeline(desc) : nullptr;
        desc.pixel = m_downsample;
        m_downsamplePipeline = m_downsample ? gb::GetPipeline(desc) : nullptr;
        m_pipelineFormat = format;
        if (!m_easuPipeline || !m_rcasPipeline || !m_downsamplePipeline)
            Logf("d3d9emu: upscale: the %s pipelines did not build: stretched instead",
                 m_downsamplePipeline ? "FSR 1.0" : "downsample");
    }
    return true;
}

bool Upscaler::PrepareTargets(gb::Format format, uint32_t sourceWidth, uint32_t sourceHeight, uint32_t outputWidth,
                              uint32_t outputHeight)
{
    if (m_output && m_format == format && m_sourceWidth == sourceWidth && m_sourceHeight == sourceHeight &&
        m_outputWidth == outputWidth && m_outputHeight == outputHeight)
        return true;
    ReleaseTargets();
    gb::TextureDesc desc = {};
    desc.type = gb::TextureType::Tex2D;
    desc.format = format;
    desc.usage = gb::Usage::RenderTarget;
    desc.sampled = true;
    desc.depth = 1;
    desc.levels = 1;
    desc.samples = 1;
    desc.width = uint16_t(sourceWidth);
    desc.height = uint16_t(sourceHeight);
    m_input = gb::CreateTexture(desc);
    desc.width = uint16_t(outputWidth);
    desc.height = uint16_t(outputHeight);
    m_middle = gb::CreateTexture(desc);
    m_output = gb::CreateTexture(desc);
    if (!m_input || !m_middle || !m_output)
    {
        ReleaseTargets();
        return false;
    }
    m_format = format;
    m_sourceWidth = sourceWidth;
    m_sourceHeight = sourceHeight;
    m_outputWidth = outputWidth;
    m_outputHeight = outputHeight;
    return true;
}

void Upscaler::DrawPass(gb::Texture *target, const gb::Pipeline *pipeline, gb::Texture *source, uint32_t width,
                        uint32_t height, const uint32_t constants[16])
{
    gb::PassDesc pass;
    pass.colorCount = 1;
    pass.color[0].texture = target;
    pass.color[0].load = gb::LoadOp::DontCare;
    gb::BeginPass(pass);
    gb::DrawState state;
    state.pipeline = pipeline;
    state.textures[0] = {source, m_sampler};
    // The vertex shader reads no constants, but a draw always carries both blocks (gfx_backend.h).
    state.pixelConstants = gb::AllocUniforms(constants, 16 * sizeof(uint32_t));
    state.vertexConstants = state.pixelConstants;
    state.viewport = {0.0f, 0.0f, float(width), float(height), 0.0f, 1.0f};
    state.scissor = {0, 0, width, height};
    gb::Draw(state, gb::Primitive::TriangleList, 3, 0);
    gb::EndPass();
}

gb::Texture *Upscaler::Run(gb::Texture *source, gb::Format format, uint32_t sourceWidth, uint32_t sourceHeight,
                           uint32_t outputWidth, uint32_t outputHeight, float sharpness, gb::Texture *target)
{
    const gb::Rect from = {0, 0, sourceWidth, sourceHeight};
    const gb::Rect to = {0, 0, outputWidth, outputHeight};
    if (!PrepareTargets(format, sourceWidth, sourceHeight, outputWidth, outputHeight))
    {
        WarnOnce("upscale targets", "d3d9emu: upscale: the %ux%u targets could not be made", outputWidth,
                 outputHeight);
        if (!target)
            return source;
        gb::Blit(source, 0, 0, from, target, 0, 0, to, gb::Filter::Linear);
        return target;
    }
    gb::Texture *output = target ? target : m_output;
    const bool down = outputWidth < sourceWidth && outputHeight < sourceHeight;
    if (!PrepareShaders(format) || !(down ? m_downsamplePipeline != nullptr : m_easuPipeline && m_rcasPipeline))
    {
        gb::Blit(source, 0, 0, from, output, 0, 0, to, gb::Filter::Linear);
        return output;
    }
    if (!(down ? m_loggedDown : m_logged))
    {
        (down ? m_loggedDown : m_logged) = true;
        if (down)
            Logf("d3d9emu: upscale: supersampling, %ux%u averaged down to %ux%u", sourceWidth, sourceHeight,
                 outputWidth, outputHeight);
        else
            Logf("d3d9emu: upscale: FSR 1.0 from %ux%u to %ux%u, sharpness %.2f", sourceWidth, sourceHeight,
                 outputWidth, outputHeight, double(sharpness));
    }
    gb::Blit(source, 0, 0, from, m_input, 0, 0, from, gb::Filter::Nearest);
    uint32_t constants[16] = {};
    if (down)
    {
        constants[0] = FloatBits(float(sourceWidth) / float(outputWidth));
        constants[1] = FloatBits(float(sourceHeight) / float(outputHeight));
        constants[2] = FloatBits(float(sourceWidth));
        constants[3] = FloatBits(float(sourceHeight));
        DrawPass(output, m_downsamplePipeline, m_input, outputWidth, outputHeight, constants);
        return output;
    }
    Fsr1EasuConstants(constants, float(sourceWidth), float(sourceHeight), float(outputWidth), float(outputHeight));
    DrawPass(m_middle, m_easuPipeline, m_input, outputWidth, outputHeight, constants);
    Fsr1RcasConstants(constants, sharpness);
    DrawPass(output, m_rcasPipeline, m_middle, outputWidth, outputHeight, constants);
    return output;
}
} // namespace d3d9emu
