#pragma once

// r_mod_gfxApi on win64 (docs/VULKAN.md, step 5): the D3D9 frontend on the Vulkan backend instead of the system's
// Direct3D 9. Only built with BO1_WIN_VULKAN (win64-msvc); win32-msvc never sees it.

#include <d3d9.h>

// The emulated Direct3D 9 (9Ex for the headless client, as R_PreCreateWindow asks of the system's), or null with
// the reason in the log when Vulkan cannot start.
IDirect3D9 *Bo1_EmulatedDirect3D(bool ex);
