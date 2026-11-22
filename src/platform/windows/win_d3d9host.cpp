// The D3D9 frontend's host on win64 (gfx_d3d9emu/d3d9emu_host.h), for r_mod_gfxApi vulkan (docs/VULKAN.md, step 5):
// the primary monitor, the game's own HWND, shaders.spv beside the exe, and the engine's console. Built into win64-msvc
// only (BO1_WIN_VULKAN); win32-msvc and the default win64 path keep the system's Direct3D 9.

#include "win_gfxapi.h"

#include <gfx_d3d9emu/d3d9emu_host.h>

#include <stdio.h>
#include <stdlib.h>

#include <cstring>
#include <string>

char *__cdecl Sys_DefaultInstallPath();
void Com_Printf(int channel, const char *fmt, ...);

// The emulator's entry points, renamed on Windows so that d3d9.lib's keep their names (d3d9emu_direct3d.cpp).
extern "C" IDirect3D9 *WINAPI Bo1Emu_Direct3DCreate9(UINT sdkVersion);
extern "C" HRESULT WINAPI Bo1Emu_Direct3DCreate9Ex(UINT sdkVersion, IDirect3D9Ex **d3d);

namespace
{
constexpr int kConsoleChannelGfx = 8;

HMONITOR PrimaryMonitor()
{
    return MonitorFromPoint(POINT{0, 0}, MONITOR_DEFAULTTOPRIMARY);
}

bool MonitorDevice(MONITORINFOEXA *info)
{
    info->cbSize = sizeof(*info);
    return GetMonitorInfoA(PrimaryMonitor(), info) != 0;
}
} // namespace

IDirect3D9 *Bo1_EmulatedDirect3D(bool ex)
{
    // Without its SPIR-V pack the frontend would draw nothing: the system's Direct3D 9 is better than a black screen.
    const char *pack = d3d9emu::host::ShaderPackPath();
    if (GetFileAttributesA(pack) == INVALID_FILE_ATTRIBUTES)
    {
        Com_Printf(kConsoleChannelGfx, "r_mod_gfxApi: no %s (tools/ffconv/gen/make_spirv_pack.py makes it)\n", pack);
        return nullptr;
    }
    // gb::Init picks the backend from the environment, as on posix; r_mod_gfxApi only names Vulkan for now.
    _putenv_s("BO1_GFX_BACKEND", "vulkan");
    if (!ex)
        return Bo1Emu_Direct3DCreate9(D3D_SDK_VERSION);
    IDirect3D9Ex *d3d = nullptr;
    const HRESULT hr = Bo1Emu_Direct3DCreate9Ex(D3D_SDK_VERSION, &d3d);
    if (FAILED(hr))
        Com_Printf(kConsoleChannelGfx, "r_mod_gfxApi: the emulated Direct3D 9Ex failed (0x%08x)\n", unsigned(hr));
    return d3d;
}

namespace d3d9emu::host
{
uint32_t DisplayModes(DisplayMode *modes, uint32_t capacity)
{
    MONITORINFOEXA info;
    if (!MonitorDevice(&info))
        return 0;
    uint32_t count = 0;
    DEVMODEA mode = {};
    mode.dmSize = sizeof(mode);
    for (DWORD i = 0; EnumDisplaySettingsA(info.szDevice, i, &mode); ++i)
    {
        // D3D9 lists the modes of its 32-bit display format, X8R8G8B8.
        if (mode.dmBitsPerPel != 32)
            continue;
        const DisplayMode m = {mode.dmPelsWidth, mode.dmPelsHeight, mode.dmDisplayFrequency > 1 ? mode.dmDisplayFrequency : 0};
        bool seen = false;
        for (uint32_t j = 0; j < count && j < capacity && !seen; ++j)
            seen = modes[j].width == m.width && modes[j].height == m.height && modes[j].refreshRate == m.refreshRate;
        if (seen)
            continue;
        if (count < capacity)
            modes[count] = m;
        ++count;
    }
    return count;
}

bool DesktopMode(DisplayMode *mode)
{
    MONITORINFOEXA info;
    DEVMODEA current = {};
    current.dmSize = sizeof(current);
    if (!MonitorDevice(&info) || !EnumDisplaySettingsA(info.szDevice, ENUM_CURRENT_SETTINGS, &current))
        return false;
    *mode = {current.dmPelsWidth, current.dmPelsHeight, current.dmDisplayFrequency > 1 ? current.dmDisplayFrequency : 0};
    return true;
}

HMONITOR AdapterMonitor()
{
    return PrimaryMonitor();
}

void *NativeWindow(HWND hwnd)
{
    return hwnd;
}

bool ClientSize(HWND hwnd, uint32_t *width, uint32_t *height)
{
    RECT rect;
    if (!hwnd || !GetClientRect(hwnd, &rect))
        return false;
    *width = uint32_t(rect.right - rect.left);
    *height = uint32_t(rect.bottom - rect.top);
    return true;
}

bool ClientOrigin(HWND hwnd, int32_t *x, int32_t *y)
{
    POINT origin = {0, 0};
    MONITORINFO info = {sizeof(info)};
    if (!hwnd || !ClientToScreen(hwnd, &origin) || !GetMonitorInfoA(PrimaryMonitor(), &info))
        return false;
    *x = origin.x - info.rcMonitor.left;
    *y = origin.y - info.rcMonitor.top;
    return true;
}

bool WindowVisible(HWND hwnd)
{
    return hwnd && IsWindowVisible(hwnd) && !IsIconic(hwnd);
}

const char *ShaderPackPath()
{
    static const std::string path = std::string(Sys_DefaultInstallPath()) + "\\shaders.spv";
    return path.c_str();
}

// As on posix (posix_d3d9host.cpp): BO1_UPSCALE=fsr1, BO1_UPSCALE_OUTPUT=<width>x<height>, BO1_UPSCALE_SHARPNESS.
bool Upscale(UpscaleSettings *settings)
{
    static const UpscaleSettings *chosen = []() -> const UpscaleSettings * {
        const char *mode = getenv("BO1_UPSCALE");
        if (!mode || !*mode || !std::strcmp(mode, "off"))
            return nullptr;
        static UpscaleSettings s = {0, 0, 0.2f};
        const char *output = getenv("BO1_UPSCALE_OUTPUT");
        unsigned width = 0, height = 0;
        char end = 0;
        if (std::strcmp(mode, "fsr1") || !output || sscanf(output, "%ux%u%c", &width, &height, &end) != 2 ||
            width < 16 || height < 16 || width > 8192 || height > 8192)
        {
            Com_Printf(kConsoleChannelGfx, "d3d9emu: BO1_UPSCALE=%s BO1_UPSCALE_OUTPUT=%s not understood: no upscale\n",
                       mode, output ? output : "(unset)");
            return nullptr;
        }
        s.outputWidth = width;
        s.outputHeight = height;
        if (const char *sharpness = getenv("BO1_UPSCALE_SHARPNESS"))
        {
            char *after = nullptr;
            const float value = strtof(sharpness, &after);
            if (after != sharpness && !*after && value >= 0.0f && value <= 2.0f)
                s.sharpness = value;
        }
        return &s;
    }();
    if (!chosen)
        return false;
    *settings = *chosen;
    return true;
}

bool SaveFile(const char *path, const void *data, size_t size)
{
    FILE *file = fopen(path, "wb");
    if (!file)
        return false;
    const bool written = fwrite(data, 1, size, file) == size;
    const bool closed = fclose(file) == 0;
    return closed && written;
}

void Log(const char *line)
{
    Com_Printf(kConsoleChannelGfx, "%s\n", line);
}
} // namespace d3d9emu::host
