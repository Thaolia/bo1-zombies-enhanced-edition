#pragma once

// The temporal upscaler (docs/VULKAN.md, step 6): Arm ASR through gb::TemporalUpscale, on backends that report
// Caps::temporalUpscale. The engine jitters its projection by Jitter's offsets; at the end of the scene the device
// hands Run the scene, its depth buffer and the camera, and Run makes the upscaler's inputs (an RGBA8 copy of the
// scene, the camera's motion and a float depth from one full-screen pass) and upscales into the device's output-size
// target. Owned by the device, called under its lock.

#include <gfx_backend/gfx_backend.h>

#include <cstdint>

namespace d3d9emu
{
// The engine's camera for the frame (d3d9emu_scene.h's Bo1EmuSceneView), D3D's row-vector matrices.
struct TemporalView
{
    float viewProjection[4][4];        // jittered, as the scene was drawn
    float inverseViewProjection[4][4];
    float projection[4][4];            // jittered: [2][0] and [2][1] hold the offset
    float zNear;
    float tanHalfFovY;
};

class Temporal
{
public:
    Temporal() = default;
    Temporal(const Temporal &) = delete;
    Temporal &operator=(const Temporal &) = delete;
    ~Temporal();

    // The next frame's offset in render pixels (FSR 2's Halton 2, 3 sequence, its phase count for these sizes).
    void Jitter(uint32_t renderWidth, uint32_t renderHeight, uint32_t outputWidth, uint32_t *phase, float *x,
                float *y);
    // One frame. `color` is the resolved scene (back buffer size, any 8-bit colour format), `depth` the depth buffer
    // it was drawn with (that size, possibly multisampled). False when it cannot run (logged once): the device then
    // upscales with FSR 1.0.
    bool Run(gb::Texture *color, gb::Texture *depth, gb::Format depthFormat, uint32_t renderWidth,
             uint32_t renderHeight, uint32_t outputWidth, uint32_t outputHeight, const TemporalView &view,
             float sharpness, gb::UpscalePreset preset, float frameMs, gb::Texture *target);
    // Frees the textures and forgets the history (a device reset).
    void ReleaseTargets();
    bool Failed() const
    {
        return m_failed;
    }

private:
    bool Fail(const char *why);
    bool PrepareShaders();
    bool PrepareTargets(gb::Format depthFormat, uint32_t renderWidth, uint32_t renderHeight, uint32_t outputWidth,
                        uint32_t outputHeight);

    bool m_failed = false;
    bool m_shadersTried = false;
    gb::Shader *m_vertex = nullptr;
    gb::Shader *m_motion = nullptr;
    const gb::Pipeline *m_pipeline = nullptr;
    const gb::Sampler *m_sampler = nullptr;

    gb::Format m_depthFormat = gb::Format::Unknown;
    uint32_t m_renderWidth = 0, m_renderHeight = 0, m_outputWidth = 0, m_outputHeight = 0;
    gb::Texture *m_colorIn = nullptr; // RGBA8: the upscaler has no BGRA
    gb::Texture *m_depthIn = nullptr; // a sampled copy of the scene's depth buffer
    gb::Texture *m_motionOut = nullptr;
    gb::Texture *m_depthOut = nullptr;
    gb::Texture *m_output = nullptr; // RGBA8, copied into the device's target

    bool m_history = false; // m_previous holds the last frame's camera
    double m_previous[4][4] = {};
    uint32_t m_phase = 0;
};
} // namespace d3d9emu
