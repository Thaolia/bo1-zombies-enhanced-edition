#pragma once

// The engine tells the D3D9 frontend where the frame's 3D scene ends (docs/VULKAN.md, step 6.1). gfx_d3d's RB_Draw3D
// calls it once the scene of every view, post effects included, is in the back buffer, before the 2D: the HUD, the
// menus. While the frontend upscales (FSR 1.0), it upscales the scene there and draws the rest of the frame at the
// output size, so the 2D stays sharp. Without upscaling, or on a frame without a scene (menus, loading screens,
// cinematics), the whole frame is upscaled at Present as before.

struct IDirect3DDevice9;

// `device` must be the frontend's own device (never the system's Direct3D 9 on win64).
void Bo1Emu_SceneComplete(IDirect3DDevice9 *device);
