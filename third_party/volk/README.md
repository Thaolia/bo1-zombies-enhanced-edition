# volk

`volk.h` and `volk.c` from https://github.com/zeux/volk at tag `vulkan-sdk-1.3.296.0` (commit `59d2690`), unmodified.
MIT, see `LICENSE.md`.

The Vulkan backend (`src/gfx_backend/vulkan`) loads the Vulkan loader with it at run time (`libvulkan.so.1`,
`vulkan-1.dll`): the game starts, and falls back to another backend, on a machine without Vulkan.
