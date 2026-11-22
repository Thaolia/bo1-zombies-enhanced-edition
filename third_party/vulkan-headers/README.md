# Vulkan-Headers

The C headers of https://github.com/KhronosGroup/Vulkan-Headers at tag `vulkan-sdk-1.3.296.0` (commit `29f979e`,
`VK_HEADER_VERSION` 296), unmodified: `include/vulkan/` (`vk_platform.h`, `vulkan.h`, `vulkan_core.h`,
`vulkan_win32.h`) and `include/vk_video/`. The C++ headers and the other platforms' surface headers are left out.
Apache-2.0 or MIT, see `LICENSE.md` and `LICENSES/`.

The Vulkan backend (`src/gfx_backend/vulkan`) compiles against them, so no Vulkan SDK or `-dev` package is needed to
build; the loader is opened at run time by volk (`third_party/volk`).
