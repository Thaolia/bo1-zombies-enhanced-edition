// The D3D9 frontend's host on posix (gfx_d3d9emu/d3d9emu_host.h): the first SDL display and the game windows through
// the window layer (win32_gui.cpp), shaders.pack in the install folder next to zone/, and the engine's console.

#include "posix_video.h"
#include "win32_handles.h"

#include <gfx_d3d9emu/d3d9emu_host.h>

#include <SDL.h>

#include <stdio.h>

#include <cstdlib>
#include <cstring>
#include <string>

char *__cdecl Sys_DefaultInstallPath();
namespace gb { const char *Name(); } // backend name, for ShaderPackPath
void Com_Printf(int channel, const char *fmt, ...);

namespace d3d9emu::host
{
namespace
{
constexpr int kAdapterDisplay = 0;
constexpr int kConsoleChannelGfx = 8;

// D3D9 lists the modes of its 32-bit display format.
bool Listed(const SDL_DisplayMode &mode)
{
    return SDL_BITSPERPIXEL(mode.format) >= 24;
}
} // namespace

namespace
{
// The console's fixed output modes, reported when SDL has none to give: the deko3d backend drives nwindow directly
// and runs with SDL's dummy video driver (switch_main.cpp), and a headless desktop run has no display either. Both
// are >= 800x600, so the engine's renderer init finds a valid resolution instead of aborting. The GL path gets real
// modes from SDL and never reaches this fallback.
constexpr DisplayMode kFixedModes[] = {{1280, 720, 60}, {1920, 1080, 60}};
} // namespace

uint32_t DisplayModes(DisplayMode *modes, uint32_t capacity)
{
    uint32_t count = 0;
    const int total = Bo1_VideoReady() ? SDL_GetNumDisplayModes(kAdapterDisplay) : 0;
    for (int i = 0; i < total; ++i)
    {
        SDL_DisplayMode mode;
        if (SDL_GetDisplayMode(kAdapterDisplay, i, &mode) || !Listed(mode))
            continue;
        if (count < capacity)
            modes[count] = {uint32_t(mode.w), uint32_t(mode.h), uint32_t(mode.refresh_rate)};
        ++count;
    }
    if (count == 0)
        for (const DisplayMode &m : kFixedModes)
        {
            if (count < capacity)
                modes[count] = m;
            ++count;
        }
    return count;
}

bool DesktopMode(DisplayMode *mode)
{
    SDL_DisplayMode desktop;
    if (!Bo1_VideoReady() || SDL_GetDesktopDisplayMode(kAdapterDisplay, &desktop))
    {
        *mode = kFixedModes[0]; // 720p, as the backbuffer is created at (switch display fix)
        return true;
    }
    *mode = {uint32_t(desktop.w), uint32_t(desktop.h), uint32_t(desktop.refresh_rate)};
    return true;
}

HMONITOR AdapterMonitor()
{
    return Bo1_VideoReady() ? Bo1_DisplayMonitor(kAdapterDisplay) : nullptr;
}

void *NativeWindow(HWND hwnd)
{
    return Bo1_NativeWindow(hwnd);
}

bool ClientSize(HWND hwnd, uint32_t *width, uint32_t *height)
{
    RECT rect;
    if (!Bo1_ClientRect(hwnd, &rect))
        return false;
    *width = uint32_t(rect.right - rect.left);
    *height = uint32_t(rect.bottom - rect.top);
    return true;
}

bool ClientOrigin(HWND hwnd, int32_t *x, int32_t *y)
{
    RECT rect;
    SDL_Rect display;
    if (!Bo1_ClientRect(hwnd, &rect) || !Bo1_VideoReady() || SDL_GetDisplayBounds(kAdapterDisplay, &display))
        return false;
    *x = rect.left - display.x;
    *y = rect.top - display.y;
    return true;
}

bool WindowVisible(HWND hwnd)
{
    return Bo1_WindowShown(hwnd);
}

const char *ShaderPackPath()
{
    // deko3d loads DKSH that uam compiled offline (shaders.dksh); GL/null load the GLSL pack.
    static const bool dksh = !std::strcmp(gb::Name(), "deko3d");
    static const std::string path =
        Bo1_PosixPath(Sys_DefaultInstallPath()) + (dksh ? "/shaders.dksh" : "/shaders.pack");
    return path.c_str();
}

// BO1_UPSCALE=fsr1 turns it on, BO1_UPSCALE_OUTPUT=<width>x<height> gives the output (required),
// BO1_UPSCALE_SHARPNESS the RCAS stops (default 0.2, AMD's). The Switch start menu sets them (switch_main.cpp).
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
    FILE *file = fopen(Bo1_PosixPath(path).c_str(), "wb");
    if (!file)
        return false;
    const bool written = fwrite(data, 1, size, file) == size;
    const bool closed = fclose(file) == 0;
    Bo1_PathsChanged();
    return closed && written;
}

void Log(const char *line)
{
    Com_Printf(kConsoleChannelGfx, "%s\n", line);
}
} // namespace d3d9emu::host
