// The contract's free functions, forwarded to the backend Init chose: BO1_GFX_BACKEND=null, gl, deko3d or vulkan names
// one; without it, the GL backend when it gets a context, else the null one.

#include "gb_backend.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace gb
{
namespace
{
const Backend *s_backend = &null::Table();
} // namespace

bool Init()
{
    const char *wanted = std::getenv("BO1_GFX_BACKEND");
    if (wanted && *wanted && std::strcmp(wanted, "null") && std::strcmp(wanted, "gl") &&
        std::strcmp(wanted, "deko3d") && std::strcmp(wanted, "vulkan"))
    {
        std::fprintf(stderr, "gb: BO1_GFX_BACKEND=%s names no backend (null, gl, deko3d, vulkan)\n", wanted);
        return false;
    }
    // Vulkan is opt-in only too (docs/VULKAN.md: GL stays the default): asking for it and failing does not fall back.
#if defined(BO1_GB_VULKAN)
    if (wanted && !std::strcmp(wanted, "vulkan"))
    {
        s_backend = &vulkan::Table();
        return s_backend->Init();
    }
#else
    if (wanted && !std::strcmp(wanted, "vulkan"))
    {
        std::fprintf(stderr, "gb: this build has no Vulkan backend\n");
        return false;
    }
#endif
    // deko3d is opt-in only (never the default while it is being brought up): asking for it and failing does not
    // fall back to GL, so the failure is seen.
#if defined(BO1_GB_DEKO3D)
    if (wanted && !std::strcmp(wanted, "deko3d"))
    {
        s_backend = &deko3d::Table();
        return s_backend->Init();
    }
#else
    if (wanted && !std::strcmp(wanted, "deko3d"))
    {
        std::fprintf(stderr, "gb: this build has no deko3d backend\n");
        return false;
    }
#endif
#if defined(BO1_GB_GL)
    if (!wanted || !*wanted || !std::strcmp(wanted, "gl"))
    {
        s_backend = &gl::Table();
        if (s_backend->Init())
            return true;
        if (wanted && *wanted)
            return false;
    }
#else
    if (wanted && !std::strcmp(wanted, "gl"))
    {
        std::fprintf(stderr, "gb: this build has no GL backend\n");
        return false;
    }
#endif
    s_backend = &null::Table();
    return s_backend->Init();
}

const char *Name()
{
    return s_backend->Name();
}

#define GB_FORWARD(ret, name, params, args)                                                                           \
    ret name params                                                                                                   \
    {                                                                                                                 \
        return s_backend->name args;                                                                                  \
    }
GB_BACKEND_CALLS(GB_FORWARD)
#undef GB_FORWARD
} // namespace gb
