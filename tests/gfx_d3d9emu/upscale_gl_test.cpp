// The frontend's FSR 1.0 upscaler (src/gfx_d3d9emu/d3d9emu_upscale.cpp) on the GL backend: it upscales test images
// with the embedded GLSL and reads the pixels back. It checks that the shaders compile and link, that rows stay the
// right way up, that a flat image stays flat, that the sharpening's halo stays small, and that an edge comes out
// narrower than the backend's bilinear stretch gives it. Run it as SDL_VIDEODRIVER=offscreen
// ./upscale_gl_test [--image in.ppm] [--out dir]: --image also upscales a picture (binary PPM) 2x, --out writes the
// results as PPM to look at.

#include <gfx_backend/gfx_backend.h>
#include <gfx_backend/gl/gb_gl_host.h>
#include <gfx_d3d9emu/d3d9emu.h>
#include <gfx_d3d9emu/d3d9emu_upscale.h>

#include <SDL.h>

#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace
{
int g_failures = 0;
int g_checks = 0;
std::string g_outDir;

void Check(bool condition, const char *what)
{
    ++g_checks;
    if (!condition)
    {
        ++g_failures;
        std::printf("FAIL: %s\n", what);
    }
}

SDL_Window *g_hidden = nullptr;
SDL_GLContext g_context = nullptr;
} // namespace

// What d3d9emu_upscale.cpp needs from the rest of the frontend.
namespace d3d9emu
{
ShaderForm ShaderPackForm()
{
    return ShaderForm::Glsl;
}

void Logf(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    std::vprintf(fmt, args);
    va_end(args);
    std::printf("\n");
}

void WarnOnce(const char *, const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    std::vprintf(fmt, args);
    va_end(args);
    std::printf("\n");
}
} // namespace d3d9emu

// The test's host: SDL's context on a hidden window, as tests/gfx_backend/gb_gl_test.cpp makes it.
namespace gb::gl::host
{
bool Open()
{
    SDL_GL_ResetAttributes();
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 4);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 0);
    SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_FLAGS, SDL_GL_CONTEXT_DEBUG_FLAG);
    g_hidden = SDL_CreateWindow("", 0, 0, 1, 1, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    if (!g_hidden)
    {
        std::printf("no OpenGL window: %s\n", SDL_GetError());
        return false;
    }
    g_context = SDL_GL_CreateContext(g_hidden);
    if (!g_context)
    {
        std::printf("no OpenGL 4.3 core context: %s\n", SDL_GetError());
        return false;
    }
    SDL_GL_MakeCurrent(g_hidden, nullptr);
    return true;
}

bool MakeCurrent(void *window)
{
    return SDL_GL_MakeCurrent(window ? static_cast<SDL_Window *>(window) : g_hidden, g_context) == 0;
}

void ReleaseCurrent()
{
    SDL_GL_MakeCurrent(g_hidden, nullptr);
}

void *ProcAddress(const char *name)
{
    return SDL_GL_GetProcAddress(name);
}

void DrawableSize(void *window, int *width, int *height)
{
    SDL_GL_GetDrawableSize(static_cast<SDL_Window *>(window), width, height);
}

void SetSwapInterval(int interval)
{
    SDL_GL_SetSwapInterval(interval);
}

void Swap(void *window)
{
    SDL_GL_SwapWindow(static_cast<SDL_Window *>(window));
}

void Close()
{
    SDL_GL_DeleteContext(g_context);
    SDL_DestroyWindow(g_hidden);
}

void Log(const char *line)
{
    std::printf("%s\n", line);
}
} // namespace gb::gl::host

namespace
{
// RGBA8 pixels, row 0 on top.
struct Image
{
    uint32_t width = 0, height = 0;
    std::vector<uint8_t> rgba;

    uint8_t *At(uint32_t x, uint32_t y)
    {
        return &rgba[(size_t(y) * width + x) * 4];
    }
};

Image Make(uint32_t width, uint32_t height)
{
    Image image;
    image.width = width;
    image.height = height;
    image.rgba.assign(size_t(width) * height * 4, 255);
    return image;
}

void Fill(Image &image, uint32_t x0, uint32_t y0, uint32_t x1, uint32_t y1, uint8_t r, uint8_t g, uint8_t b)
{
    for (uint32_t y = y0; y < y1; ++y)
        for (uint32_t x = x0; x < x1; ++x)
        {
            uint8_t *p = image.At(x, y);
            p[0] = r;
            p[1] = g;
            p[2] = b;
        }
}

gb::Texture *Upload(const Image &image)
{
    gb::TextureDesc desc = {};
    desc.type = gb::TextureType::Tex2D;
    desc.format = gb::Format::RGBA8;
    desc.usage = gb::Usage::Static;
    desc.sampled = true;
    desc.width = uint16_t(image.width);
    desc.height = uint16_t(image.height);
    desc.depth = 1;
    desc.levels = 1;
    desc.samples = 1;
    gb::Texture *texture = gb::CreateTexture(desc);
    gb::UploadTexture(texture, 0, 0, {0, 0, 0, uint16_t(image.width), uint16_t(image.height), 1}, image.rgba.data(),
                      image.width * 4, image.width * image.height * 4);
    return texture;
}

Image Read(gb::Texture *texture, uint32_t width, uint32_t height)
{
    Image image = Make(width, height);
    gb::ReadTexture(texture, 0, 0, {0, 0, 0, uint16_t(width), uint16_t(height), 1}, image.rgba.data(), width * 4);
    return image;
}

// The backend's linear stretch, which the console's compositor stands for without FSR.
Image Stretch(gb::Texture *source, uint32_t sw, uint32_t sh, uint32_t ow, uint32_t oh)
{
    gb::TextureDesc desc = {};
    desc.type = gb::TextureType::Tex2D;
    desc.format = gb::Format::RGBA8;
    desc.usage = gb::Usage::RenderTarget;
    desc.sampled = true;
    desc.width = uint16_t(ow);
    desc.height = uint16_t(oh);
    desc.depth = 1;
    desc.levels = 1;
    desc.samples = 1;
    gb::Texture *target = gb::CreateTexture(desc);
    gb::Blit(source, 0, 0, {0, 0, sw, sh}, target, 0, 0, {0, 0, ow, oh}, gb::Filter::Linear);
    Image image = Read(target, ow, oh);
    gb::DestroyTexture(target);
    return image;
}

void Save(const Image &image, const char *name)
{
    if (g_outDir.empty())
        return;
    const std::string path = g_outDir + "/" + name + ".ppm";
    FILE *file = std::fopen(path.c_str(), "wb");
    if (!file)
        return;
    std::fprintf(file, "P6\n%u %u\n255\n", image.width, image.height);
    for (size_t i = 0; i < size_t(image.width) * image.height; ++i)
        std::fwrite(&image.rgba[i * 4], 1, 3, file);
    std::fclose(file);
    std::printf("wrote %s\n", path.c_str());
}

bool LoadPpm(const char *path, Image &image)
{
    FILE *file = std::fopen(path, "rb");
    if (!file)
        return false;
    unsigned width = 0, height = 0, max = 0;
    const bool header = std::fscanf(file, "P6 %u %u %u", &width, &height, &max) == 3 && max == 255 &&
                        std::fgetc(file) != EOF && width && height && width <= 4096 && height <= 4096;
    if (header)
    {
        image = Make(width, height);
        std::vector<uint8_t> rgb(size_t(width) * height * 3);
        if (std::fread(rgb.data(), 1, rgb.size(), file) == rgb.size())
            for (size_t i = 0; i < size_t(width) * height; ++i)
                std::memcpy(&image.rgba[i * 4], &rgb[i * 3], 3);
        else
            image.width = 0;
    }
    std::fclose(file);
    return header && image.width;
}

// The columns of a row whose red is strictly between 10 % and 90 % of the way from `low` to `high`: the edge's width.
int EdgeWidth(Image &image, uint32_t y, uint8_t low, uint8_t high)
{
    int n = 0;
    for (uint32_t x = 0; x < image.width; ++x)
    {
        const double t = (double(image.At(x, y)[0]) - low) / (double(high) - low);
        n += t > 0.1 && t < 0.9;
    }
    return n;
}
} // namespace

int main(int argc, char **argv)
{
    const char *picture = nullptr;
    for (int i = 1; i + 1 < argc; i += 2)
    {
        if (!std::strcmp(argv[i], "--image"))
            picture = argv[i + 1];
        else if (!std::strcmp(argv[i], "--out"))
            g_outDir = argv[i + 1];
    }
    if (SDL_Init(SDL_INIT_VIDEO) != 0)
    {
        std::printf("SDL_Init: %s\n", SDL_GetError());
        return 2;
    }
    setenv("BO1_GFX_BACKEND", "gl", 1);
    if (!gb::Init() || std::strcmp(gb::Name(), "gl"))
    {
        std::printf("no GL backend\n");
        return 2;
    }
    Check(d3d9emu::Upscaler::Supports(gb::Format::RGBA8), "RGBA8 can be upscaled");
    d3d9emu::Upscaler upscaler;

    // A flat grey stays flat: EASU's weights sum to one and RCAS finds no contrast.
    {
        Image flat = Make(160, 90);
        Fill(flat, 0, 0, 160, 90, 128, 128, 128);
        gb::Texture *source = Upload(flat);
        Image out = Read(upscaler.Run(source, gb::Format::RGBA8, 160, 90, 320, 180, 0.2f), 320, 180);
        int off = 0;
        for (size_t i = 0; i < out.rgba.size(); i += 4)
            off += std::abs(int(out.rgba[i]) - 128) > 1 || std::abs(int(out.rgba[i + 1]) - 128) > 1 ||
                   std::abs(int(out.rgba[i + 2]) - 128) > 1;
        std::printf("flat: %d pixels off by more than 1\n", off);
        Check(off == 0, "a flat image stays flat");
        gb::DestroyTexture(source);
    }

    // Rows the right way up: a red block in the top-left corner and a blue one at the bottom-right stay there.
    {
        Image corners = Make(160, 90);
        Fill(corners, 0, 0, 160, 90, 0, 0, 0);
        Fill(corners, 0, 0, 40, 20, 255, 0, 0);
        Fill(corners, 120, 70, 160, 90, 0, 0, 255);
        gb::Texture *source = Upload(corners);
        Image out = Read(upscaler.Run(source, gb::Format::RGBA8, 160, 90, 320, 180, 0.2f), 320, 180);
        const uint8_t *topLeft = out.At(20, 10), *bottomRight = out.At(300, 170);
        std::printf("corners: top-left %u,%u,%u bottom-right %u,%u,%u\n", topLeft[0], topLeft[1], topLeft[2],
                    bottomRight[0], bottomRight[1], bottomRight[2]);
        Check(topLeft[0] > 240 && topLeft[2] < 15 && bottomRight[2] > 240 && bottomRight[0] < 15,
              "the top row stays on top");
        Save(out, "corners_fsr1");
        gb::DestroyTexture(source);
    }

    // A slanted edge between dark and light: EASU stays inside the source's range (its deringing), RCAS sharpens past
    // it by design but its limiter keeps the halo small (14-15 of 180 levels at sharpness 0.2 on llvmpipe), and fewer
    // intermediate pixels cross the edge than with the bilinear stretch.
    {
        const uint8_t dark = 40, light = 220;
        Image edge = Make(160, 90);
        for (uint32_t y = 0; y < 90; ++y)
            for (uint32_t x = 0; x < 160; ++x)
            {
                const uint8_t v = double(x) > 60.0 + 0.35 * y ? light : dark;
                Fill(edge, x, y, x + 1, y + 1, v, v, v);
            }
        gb::Texture *source = Upload(edge);
        for (const uint32_t scale : {2u, 3u})
        {
            const uint32_t ow = 160 * scale / (scale == 3 ? 2 : 1), oh = 90 * scale / (scale == 3 ? 2 : 1);
            Image fsr = Read(upscaler.Run(source, gb::Format::RGBA8, 160, 90, ow, oh, 0.2f), ow, oh);
            Image bilinear = Stretch(source, 160, 90, ow, oh);
            int halo = 0;
            for (size_t i = 0; i < fsr.rgba.size(); i += 4)
                halo = std::max(halo, std::max(int(dark) - fsr.rgba[i], int(fsr.rgba[i]) - light));
            int fsrWidth = 0, bilinearWidth = 0;
            for (uint32_t y = 4; y + 4 < oh; ++y)
            {
                fsrWidth += EdgeWidth(fsr, y, dark, light);
                bilinearWidth += EdgeWidth(bilinear, y, dark, light);
            }
            std::printf("edge %ux%u: halo %d levels past [%u, %u]; edge pixels FSR %d, bilinear %d\n", ow, oh, halo,
                        dark, light, fsrWidth, bilinearWidth);
            Check(halo <= (light - dark) / 10, "the sharpening's halo stays under a tenth of the edge");
            Check(fsrWidth < bilinearWidth, "FSR's edge is narrower than the bilinear stretch's");
            Save(fsr, scale == 2 ? "edge_fsr1_2x" : "edge_fsr1_1.5x");
            Save(bilinear, scale == 2 ? "edge_bilinear_2x" : "edge_bilinear_1.5x");
        }
        gb::DestroyTexture(source);
    }

    // The Switch's case, 960x540 to 1280x720, and a picture when one is given.
    if (picture)
    {
        Image image;
        if (!LoadPpm(picture, image))
        {
            std::printf("cannot read %s (binary PPM, 255 levels)\n", picture);
            ++g_failures;
        }
        else
        {
            gb::Texture *source = Upload(image);
            const uint32_t ow = image.width * 4 / 3, oh = image.height * 4 / 3;
            Save(Read(upscaler.Run(source, gb::Format::RGBA8, image.width, image.height, ow, oh, 0.2f), ow, oh),
                 "picture_fsr1");
            Save(Stretch(source, image.width, image.height, ow, oh), "picture_bilinear");
            gb::DestroyTexture(source);
        }
    }

    upscaler.ReleaseTargets();
    gb::WaitIdle();
    std::printf("upscale_gl_test: %d of %d checks passed\n", g_checks - g_failures, g_checks);
    return g_failures ? 1 : 0;
}
