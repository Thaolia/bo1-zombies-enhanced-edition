#pragma once

// r_mod_upscale, r_mod_upscaleSharpness and r_mod_upscaler (docs/VULKAN.md): the back buffer smaller (or larger) than
// the window, and the D3D9 frontend upscaling (or averaging) it into the window at Present. They exist where the
// emulated Direct3D 9 runs on a desktop: win64 with Vulkan (BO1_WIN_VULKAN) and posix. The Switch start menu sets
// its upscaler through BO1_UPSCALE* instead, and win32-msvc never sees any of it.
#if defined(BO1_WIN_VULKAN) || (!defined(_WIN32) && !defined(__SWITCH__))
#define BO1_MOD_UPSCALE 1

// The frontend upscales the `backWidth` x `backHeight` back buffer to the window's client size `outputWidth` x
// `outputHeight`, with FSR 1.0 or, `temporal` 1 to 3 (r_mod_upscaler), Arm ASR's quality, balanced or performance
// shaders where the backend has them. Set before the device is created or reset; 0 sizes turn it off.
void Bo1_SetUpscale(unsigned int backWidth, unsigned int backHeight, unsigned int outputWidth,
                    unsigned int outputHeight, float sharpness, unsigned int temporal);
// A position in the game window's client area, moved into back buffer pixels (they differ while upscaling).
void Bo1_ClientToBackBuffer(int *x, int *y);
#endif
