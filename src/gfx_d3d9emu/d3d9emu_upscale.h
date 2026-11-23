#pragma once

// The presented frame upscaled from the back buffer's size to the swapchain's (docs/RENDERER.md, "Upscaling"): AMD
// FSR 1.0, EASU then RCAS, drawn through the backend contract like any other work, so every backend has it. A back
// buffer larger than the swapchain (supersampling) is averaged down with a box filter instead. Owned by the device and
// called from its Present, under the device lock.

#include <gfx_backend/gfx_backend.h>

#include <cstdint>

namespace d3d9emu
{
class Upscaler
{
public:
    Upscaler() = default;
    Upscaler(const Upscaler &) = delete;
    Upscaler &operator=(const Upscaler &) = delete;
    ~Upscaler();

    // Whether the backend can sample, filter and render the back buffer's format: the device enlarges the swapchain
    // only then.
    static bool Supports(gb::Format format);
    // The image the swapchain shows: `source` (a colour attachment of the back buffer's size and a format Supports
    // accepts) upscaled to the output size, with RCAS at `sharpness` stops below its strongest (0), or averaged down
    // to it when the output is smaller on both axes (`sharpness` unused). When FSR 1.0 or the downsample
    // cannot run (no shader for the backend's form, a pipeline that does not build), the source stretched by the
    // backend's linear blit, logged once. `source` itself only when the targets cannot be made (logged). With a
    // `target` (a colour attachment of the output size and `format`), the result goes there and `target` is returned.
    gb::Texture *Run(gb::Texture *source, gb::Format format, uint32_t sourceWidth, uint32_t sourceHeight,
                     uint32_t outputWidth, uint32_t outputHeight, float sharpness, gb::Texture *target = nullptr);
    // Frees the textures (a device reset changes the sizes); the shaders and pipelines stay.
    void ReleaseTargets();

private:
    bool PrepareShaders(gb::Format format);
    bool PrepareTargets(gb::Format format, uint32_t sourceWidth, uint32_t sourceHeight, uint32_t outputWidth,
                        uint32_t outputHeight);
    void DrawPass(gb::Texture *target, const gb::Pipeline *pipeline, gb::Texture *source, uint32_t width,
                  uint32_t height, const uint32_t constants[16]);

    bool m_shadersTried = false;
    bool m_logged = false;     // the first FSR 1.0 frame
    bool m_loggedDown = false; // the first downsampled frame
    gb::Shader *m_vertex = nullptr;
    gb::Shader *m_easu = nullptr;
    gb::Shader *m_rcas = nullptr;
    gb::Shader *m_downsample = nullptr;
    const gb::Pipeline *m_easuPipeline = nullptr;
    const gb::Pipeline *m_rcasPipeline = nullptr;
    const gb::Pipeline *m_downsamplePipeline = nullptr;
    const gb::Sampler *m_sampler = nullptr;
    gb::Format m_pipelineFormat = gb::Format::Unknown;

    gb::Format m_format = gb::Format::Unknown;
    uint32_t m_sourceWidth = 0, m_sourceHeight = 0, m_outputWidth = 0, m_outputHeight = 0;
    gb::Texture *m_input = nullptr;  // a sampled copy of the back buffer, which is not sampled
    gb::Texture *m_middle = nullptr; // EASU's output, RCAS's input
    gb::Texture *m_output = nullptr; // what the swapchain shows
};

// FsrEasuCon and FsrRcasCon (third_party/fidelityfx_fsr1/ffx_fsr1.h): the shaders' constants, 4 uvec4 each.
void Fsr1EasuConstants(uint32_t con[16], float inputWidth, float inputHeight, float outputWidth, float outputHeight);
void Fsr1RcasConstants(uint32_t con[16], float sharpness);
} // namespace d3d9emu
