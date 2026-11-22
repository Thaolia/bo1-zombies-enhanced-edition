# Vulkan Memory Allocator

`vk_mem_alloc.h` from https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator at tag `v3.1.0` (commit
`009ecd1`), unmodified. MIT, see `LICENSE.txt`.

The Vulkan backend (`src/gfx_backend/vulkan`) suballocates its buffers and images from large blocks with it, through
volk's function pointers (`VMA_STATIC_VULKAN_FUNCTIONS 0`, `VMA_DYNAMIC_VULKAN_FUNCTIONS 1`).
