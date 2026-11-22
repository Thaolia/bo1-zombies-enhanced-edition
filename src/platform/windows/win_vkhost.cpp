// The Vulkan backend's host on win64 (gfx_backend/vulkan/gb_vk_host.h): VK_KHR_win32_surface on the game's HWND.
// volk loads vulkan-1.dll (gb_vk.cpp); without a Vulkan driver the backend fails to start and r_init.cpp falls back to
// the system's Direct3D 9.

#include <windows.h>

#include <gfx_backend/vulkan/gb_vk_host.h>

#include <vulkan/vulkan_win32.h>

void Com_Printf(int channel, const char *fmt, ...);
char *__cdecl Sys_DefaultInstallPath();

namespace gb::vulkan::host
{
namespace
{
constexpr int kConsoleChannelGfx = 8;
} // namespace

bool Open(std::vector<std::string> *instanceExtensions)
{
    instanceExtensions->assign({VK_KHR_SURFACE_EXTENSION_NAME, VK_KHR_WIN32_SURFACE_EXTENSION_NAME});
    return true;
}

bool CreateSurface(VkInstance instance, void *window, VkSurfaceKHR *surface)
{
    // volk is built without VK_USE_PLATFORM_WIN32_KHR, so the WSI entry point is looked up here.
    const auto create = reinterpret_cast<PFN_vkCreateWin32SurfaceKHR>(
        vkGetInstanceProcAddr(instance, "vkCreateWin32SurfaceKHR"));
    VkWin32SurfaceCreateInfoKHR info = {VK_STRUCTURE_TYPE_WIN32_SURFACE_CREATE_INFO_KHR};
    info.hinstance = GetModuleHandleA(nullptr);
    info.hwnd = static_cast<HWND>(window);
    const VkResult result = window && create ? create(instance, &info, nullptr, surface) : VK_ERROR_INITIALIZATION_FAILED;
    if (result != VK_SUCCESS)
    {
        Com_Printf(kConsoleChannelGfx, "vk: no Vulkan surface on the game window (%d)\n", int(result));
        return false;
    }
    return true;
}

void DrawableSize(void *window, int *width, int *height)
{
    RECT rect = {};
    GetClientRect(static_cast<HWND>(window), &rect);
    *width = rect.right - rect.left;
    *height = rect.bottom - rect.top;
}

// Beside the exe, as shaders.spv: the package folder is the player's own.
bool PipelineCachePath(std::string *path)
{
    *path = std::string(Sys_DefaultInstallPath()) + "\\vk_pipelines.bin";
    return true;
}

void Close()
{
}

void Log(const char *line)
{
    Com_Printf(kConsoleChannelGfx, "%s\n", line);
}
} // namespace gb::vulkan::host
