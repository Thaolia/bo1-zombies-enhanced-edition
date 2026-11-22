#pragma once

// What the Vulkan backend needs from the platform it runs on: the instance extensions its windows need, a surface for
// a window, a window's size and the log. The platform layer implements it (src/platform/posix/posix_vkhost.cpp with
// SDL2), and so does tests/gfx_backend. The backend loads Vulkan itself (volk): the host never calls it.

#include <volk.h>

#include <string>
#include <vector>

namespace gb::vulkan::host
{
// On the thread that calls gb::Init, before the instance exists: whether the backend may run (false, with the reason
// in the log, keeps the dispatcher's fallback), and the instance extensions the platform's windows need (none when
// it has none, as in a test that only renders into textures). From then on the platform makes its windows so that a
// surface can be made on them.
bool Open(std::vector<std::string> *instanceExtensions);
// A surface for a SwapchainDesc::window on `instance`. False, with the reason in the log, when there is none.
bool CreateSurface(VkInstance instance, void *window, VkSurfaceKHR *surface);
// A window's size in pixels, for a surface that does not report its own.
void DrawableSize(void *window, int *width, int *height);
// Where the pipeline cache is kept between runs (a file the backend reads at Init and writes as pipelines are made);
// false keeps it in memory only.
bool PipelineCachePath(std::string *path);
// On the thread that calls gb::Shutdown, once the instance is destroyed.
void Close();
// One line, without the newline, for the engine's log.
void Log(const char *line);
} // namespace gb::vulkan::host
