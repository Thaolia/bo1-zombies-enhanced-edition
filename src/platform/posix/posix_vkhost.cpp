// The Vulkan backend's host on posix (gfx_backend/vulkan/gb_vk_host.h): SDL2's Vulkan support. Once the backend runs,
// the window layer makes every game window a Vulkan one (win32_gui.cpp), which SDL needs to make a surface on it.
// Only BO1_GFX_BACKEND=vulkan asks for this backend (docs/VULKAN.md): GL stays the default.

#include "posix_video.h"
#include "win32_handles.h"

#include <gfx_backend/vulkan/gb_vk_host.h>

#include <SDL.h>
#include <SDL_vulkan.h>

#include <vector>

#if defined(__OpenBSD__)
#include <stdlib.h>
#include <sys/stat.h>
#endif

bool __cdecl Sys_IsHeadless();
char *__cdecl Sys_DefaultInstallPath();
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

#if defined(__OpenBSD__)
// OpenBSD's Mesa is part of xenocara: its driver manifests are in /usr/X11R6/share/vulkan/icd.d, which the
// vulkan-loader package never searches (a player's loader listed only /usr/local and /usr: "Found no files", then SDL's
// "doesn't implement VK_KHR_surface"). Add that folder unless the player chose drivers themselves.
void AddXenocaraDrivers()
{
    constexpr const char *kIcdDir = "/usr/X11R6/share/vulkan/icd.d";
    if (getenv("VK_DRIVER_FILES") || getenv("VK_ICD_FILENAMES") || getenv("VK_ADD_DRIVER_FILES"))
        return;
    struct stat st;
    if (stat(kIcdDir, &st) != 0 || !S_ISDIR(st.st_mode))
        return;
    setenv("VK_ADD_DRIVER_FILES", kIcdDir, 1);
    Com_Printf(kConsoleChannelGfx, "vk: Vulkan drivers also searched in %s\n", kIcdDir);
}
#endif
} // namespace

bool Open(std::vector<std::string> *instanceExtensions)
{
    instanceExtensions->clear();
#if defined(__OpenBSD__)
    AddXenocaraDrivers();
#endif
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

// Beside shaders.spv in the install folder (posix_d3d9host.cpp's ShaderPackPath).
bool AsyncPipelines()
{
    return true;
}

bool PipelineCachePath(std::string *path)
{
    *path = Bo1_PosixPath(Sys_DefaultInstallPath()) + "/vk_pipelines.bin";
    return true;
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
