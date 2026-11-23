# Arm Accuracy Super Resolution (generic library)

`include/` and `src/` from https://github.com/arm/accuracy-super-resolution-generic-library at commit `0501f49`
(2025-06-23), without its CMake files, its Windows tools (`tools/bin`) or the `.h.d` dependency files of the
prebuilt shaders; `LICENSES/MIT.txt` as `LICENSE` (MIT, Copyright © 2023 Advanced Micro Devices, Inc., © 2024-2025 Arm
Limited).

BO1 builds the FSR 2 component (`src/components/fsr2`, `src/shared`) and the standalone Vulkan backend
(`src/backends/vk`) with its prebuilt 16-bit SPIR-V shaders (`src/backends/shared/blob_accessors`) into the Vulkan
backend (`src/gfx_backend/vulkan`, docs/VULKAN.md step 6). The GLSL sources in `src/backends/vk/shaders` are kept for a
32-bit permutation (GPUs without `shaderFloat16`), not built yet.

One change, marked `BO1:` in `src/backends/vk/ffxm_vk.cpp` (`findMemoryTypeIndex`): for device-local memory ASR skips
every host-visible type, so a unified-memory device, where every device-local type is also host-visible (lavapipe,
some integrated GPUs), got no type at all and `ffxmFsr2ContextCreate` failed (`FFXM_ERROR_BACKEND_API_ERROR`). It now
falls back to the first host-visible device-local type when no other fits.
