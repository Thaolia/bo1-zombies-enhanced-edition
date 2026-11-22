// The Vulkan backend's host on posix (gfx_backend/vulkan/gb_vk_host.h): SDL2's Vulkan support. Once the backend runs,
// the window layer makes every game window a Vulkan one (win32_gui.cpp), which SDL needs to make a surface on it.
// Only BO1_GFX_BACKEND=vulkan asks for this backend (docs/VULKAN.md): GL stays the default.

#include "posix_video.h"

#include <gfx_backend/vulkan/gb_vk_host.h>

#include <SDL.h>
#include <SDL_vulkan.h>

#include <vector>

bool __cdecl Sys_IsHeadless();
void Com_Printf(int channel, const char *fmt, ...);

namespace gb::vulkan::host
{
namespace
{
constexpr int kConsoleChannelGfx = 8;

bool s_loaded = false;

void Fail(const char *what)
{
    Com_Printf(kConsoleChannelGfx, "vk: %s: %s\n", what, SDL_GetError());
}
} // namespace

bool Open(std::vector<std::string> *instanceExtensions)
{
    instanceExtensions->clear();
    // A headless run's windows never show: it has no surface to make, and renders into its textures only.
    if (Sys_IsHeadless())
        return true;
    if (!Bo1_VideoReady())
    {
        Com_Printf(kConsoleChannelGfx, "vk: no display\n");
        return false;
    }
    if (SDL_Vulkan_LoadLibrary(nullptr) != 0)
    {
        Fail("SDL cannot load Vulkan");
        return false;
    }
    s_loaded = true;
    unsigned count = 0;
    if (!SDL_Vulkan_GetInstanceExtensions(nullptr, &count, nullptr))
    {
        Fail("SDL_Vulkan_GetInstanceExtensions");
        return false;
    }
    std::vector<const char *> names(count);
    if (!SDL_Vulkan_GetInstanceExtensions(nullptr, &count, names.data()))
    {
        Fail("SDL_Vulkan_GetInstanceExtensions");
        return false;
    }
    for (const char *name : names)
        instanceExtensions->emplace_back(name);
    Bo1_UseVulkanWindows();
    return true;
}

bool CreateSurface(VkInstance instance, void *window, VkSurfaceKHR *surface)
{
    if (!window || !SDL_Vulkan_CreateSurface(static_cast<SDL_Window *>(window), instance, surface))
    {
        Fail("no Vulkan surface on the game window");
        return false;
    }
    return true;
}

void DrawableSize(void *window, int *width, int *height)
{
    SDL_Vulkan_GetDrawableSize(static_cast<SDL_Window *>(window), width, height);
}

void Close()
{
    if (s_loaded)
        SDL_Vulkan_UnloadLibrary();
    s_loaded = false;
    Bo1_VideoRelease();
}

void Log(const char *line)
{
    Com_Printf(kConsoleChannelGfx, "%s\n", line);
}
} // namespace gb::vulkan::host
