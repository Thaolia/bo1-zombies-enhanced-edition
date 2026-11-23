// The Vulkan Memory Allocator's implementation (third_party/vma), in a file of its own: its warnings and its size stay
// out of gb_vk.cpp. It calls Vulkan through the functions volk loaded (gb_vk.cpp hands them over).

#include <volk.h>

#define VMA_STATIC_VULKAN_FUNCTIONS 0
#define VMA_DYNAMIC_VULKAN_FUNCTIONS 1
#define VMA_IMPLEMENTATION
#include <vk_mem_alloc.h>
