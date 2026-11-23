#pragma once

// The engine tells the D3D9 frontend where the frame's 3D scene ends (docs/VULKAN.md, step 6). gfx_d3d's RB_Draw3D
// calls Bo1Emu_SceneComplete once the scene of every view, post effects included, is in the back buffer, before the
// 2D: the HUD, the menus. While the frontend upscales, it upscales the scene there and draws the rest of the frame at
// the output size, so the 2D stays sharp. Without upscaling, or on a frame without a scene (menus, loading screens,
// cinematics), the whole frame is upscaled at Present as before.
//
// With a temporal upscaler (Arm ASR), the engine also jitters its projection by Bo1Emu_TemporalJitter's offset, hands
// SceneComplete the frame's camera, and brackets the scene's emissive draws with Bo1Emu_SceneTransparents, from which
// the frontend makes the upscaler's reactive mask.

struct IDirect3DDevice9;

// The camera the scene was drawn with: D3D's row-vector matrices, the projection jittered.
struct Bo1EmuSceneView
{
    float viewProjection[4][4];
    float inverseViewProjection[4][4];
    float projection[4][4];
    float zNear;
    float tanHalfFovY;
};

// `device` must be the frontend's own device (never the system's Direct3D 9 on win64). `view` is null when the frame
// is not one plain camera (several views, a missile camera): the temporal upscaler then skips the frame.
void Bo1Emu_SceneComplete(IDirect3DDevice9 *device, const Bo1EmuSceneView *view);
// The sub-pixel offset of the next scene's projection, in render pixels (x right, y down), and true, while the
// temporal upscaler is in use; false otherwise (no jitter). Called once a frame, for the main view.
bool Bo1Emu_TemporalJitter(IDirect3DDevice9 *device, float *x, float *y);
// The scene's emissive draws (particles, effects) start (`done` false) or are over (true), in the scene's render
// target. Does nothing without the temporal upscaler.
void Bo1Emu_SceneTransparents(IDirect3DDevice9 *device, bool done);
