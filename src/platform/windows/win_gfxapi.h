#pragma once

// r_mod_gfxApi on win64 (docs/VULKAN.md, step 5): the D3D9 frontend on the Vulkan backend instead of the system's
// Direct3D 9. Only built with BO1_WIN_VULKAN (win64-msvc); win32-msvc never sees it.

#include <d3d9.h>

// The emulated Direct3D 9 (9Ex for the headless client, as R_PreCreateWindow asks of the system's), or null with
// the reason in the log when Vulkan cannot start.
IDirect3D9 *Bo1_EmulatedDirect3D(bool ex);
// Whether the emulated Direct3D 9 is the one in use (the last Bo1_EmulatedDirect3D succeeded).
bool Bo1_EmulatedDirect3DActive();

// FSR 1.0 (r_mod_upscale): the frontend upscales the `backWidth` x `backHeight` back buffer to the window's client
// size `outputWidth` x `outputHeight` at Present. Set before the device is created or reset; 0 sizes turn it off.
void Bo1_SetUpscale(unsigned int backWidth, unsigned int backHeight, unsigned int outputWidth,
                    unsigned int outputHeight, float sharpness);
// A position in the game window's client area, moved into back buffer pixels (they differ while upscaling).
void Bo1_ClientToBackBuffer(int *x, int *y);
