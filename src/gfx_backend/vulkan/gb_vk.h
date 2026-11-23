#pragma once

// The Vulkan backend (docs/RENDERER.md, "The Vulkan backend"): gfx_backend.h on Vulkan 1.3 with dynamic rendering and
// push descriptors, the loader opened at run time by volk, memory from the Vulkan Memory Allocator. Opt-in:
// BO1_GFX_BACKEND=vulkan. Its shaders are SPIR-V from tools/ffconv/gen/make_spirv_pack.py (shaders.spv).

#include "../gb_backend.h"

namespace gb::vulkan
{
// The contract's descriptor bindings, all in set 0, as make_spirv_pack.py moves the GLSL's: the samplers at their
// D3D9 index, then the vertex and pixel constant blocks.
inline constexpr uint32_t BINDING_VERTEX_CONSTANTS = 16;
inline constexpr uint32_t BINDING_PIXEL_CONSTANTS = 17;
} // namespace gb::vulkan
