// The Vulkan backend (gb_vk.h). Recording follows the deko3d backend's model, which Vulkan shares: the frame is recorded
// into command buffers and submitted at Present, two frames in flight, a dynamic buffer renamed when a DISCARD finds
// its store still in use, objects destroyed once the GPU has finished every submission that could use them.
//
// - Every image stays in VK_IMAGE_LAYOUT_GENERAL from its creation on (swapchain images aside). A full memory barrier
//   at each pass boundary, copy and readback resolves the contract's hazards (docs/RENDERER.md, "Contract").
// - Uploads go to a "setup" command buffer submitted before the frame's, unless work already recorded in the frame
//   uses the resource: then they go into the frame in order, the pass suspended around them.
// - Submissions signal one timeline semaphore; its value orders frames, fences, queries and deferred destruction.
// - Draws push their descriptors (VK_KHR_push_descriptor) into one pipeline layout: samplers 0-15, the constant
//   blocks at 16 and 17 (make_spirv_pack.py moves them there).
// - D3D9's conventions: a negative viewport height puts row 0 on top, clockwise front faces, depth 0 to 1.

#include "gb_vk.h"

#include "../gb_common.h"
#include "gb_vk_host.h"
#include "vk_shaders.h"

#define VMA_STATIC_VULKAN_FUNCTIONS 0
#define VMA_DYNAMIC_VULKAN_FUNCTIONS 1
#include <vk_mem_alloc.h>

#include <algorithm>
#include <bit>
#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace gb::vulkan
{
namespace
{
constexpr uint32_t kFramesInFlight = 2;
constexpr uint32_t kSamplerBindings = 16;
constexpr uint32_t kDummyStream = MAX_STREAMS; // feeds vertex inputs no stream gives (0, 0, 0, 1)
constexpr uint32_t kUniformBlockBytes = 4u << 20;
constexpr uint32_t kStagingChunkBytes = 16u << 20;
constexpr uint32_t kQueriesPerFrame = 4096;
constexpr int kMaxDebugMessages = 64;

void Log(const char *fmt, ...) BO1_PRINTF_FORMAT(1, 2);
void Log(const char *fmt, ...)
{
    char line[1024];
    va_list args;
    va_start(args, fmt);
    std::vsnprintf(line, sizeof(line), fmt, args);
    va_end(args);
    host::Log(line);
}

const char *ResultName(VkResult r)
{
    switch (r)
    {
    case VK_SUCCESS: return "VK_SUCCESS";
    case VK_NOT_READY: return "VK_NOT_READY";
    case VK_TIMEOUT: return "VK_TIMEOUT";
    case VK_SUBOPTIMAL_KHR: return "VK_SUBOPTIMAL_KHR";
    case VK_ERROR_OUT_OF_HOST_MEMORY: return "VK_ERROR_OUT_OF_HOST_MEMORY";
    case VK_ERROR_OUT_OF_DEVICE_MEMORY: return "VK_ERROR_OUT_OF_DEVICE_MEMORY";
    case VK_ERROR_INITIALIZATION_FAILED: return "VK_ERROR_INITIALIZATION_FAILED";
    case VK_ERROR_DEVICE_LOST: return "VK_ERROR_DEVICE_LOST";
    case VK_ERROR_LAYER_NOT_PRESENT: return "VK_ERROR_LAYER_NOT_PRESENT";
    case VK_ERROR_EXTENSION_NOT_PRESENT: return "VK_ERROR_EXTENSION_NOT_PRESENT";
    case VK_ERROR_FEATURE_NOT_PRESENT: return "VK_ERROR_FEATURE_NOT_PRESENT";
    case VK_ERROR_INCOMPATIBLE_DRIVER: return "VK_ERROR_INCOMPATIBLE_DRIVER";
    case VK_ERROR_SURFACE_LOST_KHR: return "VK_ERROR_SURFACE_LOST_KHR";
    case VK_ERROR_OUT_OF_DATE_KHR: return "VK_ERROR_OUT_OF_DATE_KHR";
    default: return "VkResult";
    }
}

// A failed call that leaves the backend unusable is logged; the caller degrades (skips the work) rather than aborts.
bool Ok(VkResult r, const char *what)
{
    if (r == VK_SUCCESS)
        return true;
    Log("vk: %s: %s (%d)", what, ResultName(r), int(r));
    return false;
}

// ---- formats

struct FormatMap
{
    VkFormat format;
    VkImageAspectFlags aspect; // of a sampled view
};

VkFormat s_depthStencilFormat = VK_FORMAT_D24_UNORM_S8_UINT; // D32_SFLOAT_S8_UINT where D24S8 cannot be rendered

FormatMap MapFormat(Format f)
{
    switch (f)
    {
    case Format::BGRA8:
    case Format::BGRX8: return {VK_FORMAT_B8G8R8A8_UNORM, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::RGBA8: return {VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::B5G6R5: return {VK_FORMAT_R5G6B5_UNORM_PACK16, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::B5G5R5A1: return {VK_FORMAT_A1R5G5B5_UNORM_PACK16, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::R8: return {VK_FORMAT_R8_UNORM, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::RG8: return {VK_FORMAT_R8G8_UNORM, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::RG16: return {VK_FORMAT_R16G16_UNORM, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::RGBA16: return {VK_FORMAT_R16G16B16A16_UNORM, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::R16F: return {VK_FORMAT_R16_SFLOAT, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::RG16F: return {VK_FORMAT_R16G16_SFLOAT, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::RGBA16F: return {VK_FORMAT_R16G16B16A16_SFLOAT, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::R32F: return {VK_FORMAT_R32_SFLOAT, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::BC1: return {VK_FORMAT_BC1_RGBA_UNORM_BLOCK, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::BC2: return {VK_FORMAT_BC2_UNORM_BLOCK, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::BC3: return {VK_FORMAT_BC3_UNORM_BLOCK, VK_IMAGE_ASPECT_COLOR_BIT};
    case Format::D16: return {VK_FORMAT_D16_UNORM, VK_IMAGE_ASPECT_DEPTH_BIT};
    case Format::D24S8: return {s_depthStencilFormat, VK_IMAGE_ASPECT_DEPTH_BIT};
    case Format::Unknown:
    case Format::Count: break;
    }
    return {VK_FORMAT_UNDEFINED, 0};
}

bool HasStencil(Format f)
{
    return f == Format::D24S8;
}

VkImageAspectFlags AttachmentAspect(Format f)
{
    return f == Format::D24S8 ? VK_IMAGE_ASPECT_DEPTH_BIT | VK_IMAGE_ASPECT_STENCIL_BIT
           : f == Format::D16 ? VK_IMAGE_ASPECT_DEPTH_BIT
                              : VK_IMAGE_ASPECT_COLOR_BIT;
}

VkComponentSwizzle MapSource(Source s, bool alphaIsOne)
{
    switch (s)
    {
    case Source::R: return VK_COMPONENT_SWIZZLE_R;
    case Source::G: return VK_COMPONENT_SWIZZLE_G;
    case Source::B: return VK_COMPONENT_SWIZZLE_B;
    case Source::A: return alphaIsOne ? VK_COMPONENT_SWIZZLE_ONE : VK_COMPONENT_SWIZZLE_A;
    case Source::Zero: return VK_COMPONENT_SWIZZLE_ZERO;
    case Source::One: return VK_COMPONENT_SWIZZLE_ONE;
    }
    return VK_COMPONENT_SWIZZLE_IDENTITY;
}

VkFormat MapAttrib(AttribType t)
{
    switch (t)
    {
    case AttribType::Float1: return VK_FORMAT_R32_SFLOAT;
    case AttribType::Float2: return VK_FORMAT_R32G32_SFLOAT;
    case AttribType::Float3: return VK_FORMAT_R32G32B32_SFLOAT;
    case AttribType::Float4: return VK_FORMAT_R32G32B32A32_SFLOAT;
    case AttribType::UByte4: return VK_FORMAT_R8G8B8A8_USCALED;
    case AttribType::UByte4N: return VK_FORMAT_R8G8B8A8_UNORM;
    case AttribType::UByte4NBGRA: return VK_FORMAT_B8G8R8A8_UNORM;
    case AttribType::Short2: return VK_FORMAT_R16G16_SSCALED;
    case AttribType::Short4: return VK_FORMAT_R16G16B16A16_SSCALED;
    case AttribType::Short2N: return VK_FORMAT_R16G16_SNORM;
    case AttribType::Short4N: return VK_FORMAT_R16G16B16A16_SNORM;
    case AttribType::UShort2N: return VK_FORMAT_R16G16_UNORM;
    case AttribType::UShort4N: return VK_FORMAT_R16G16B16A16_UNORM;
    case AttribType::Half2: return VK_FORMAT_R16G16_SFLOAT;
    case AttribType::Half4: return VK_FORMAT_R16G16B16A16_SFLOAT;
    }
    return VK_FORMAT_UNDEFINED;
}

VkBlendFactor MapBlend(Blend b)
{
    switch (b)
    {
    case Blend::Zero: return VK_BLEND_FACTOR_ZERO;
    case Blend::One: return VK_BLEND_FACTOR_ONE;
    case Blend::SrcColor: return VK_BLEND_FACTOR_SRC_COLOR;
    case Blend::InvSrcColor: return VK_BLEND_FACTOR_ONE_MINUS_SRC_COLOR;
    case Blend::SrcAlpha: return VK_BLEND_FACTOR_SRC_ALPHA;
    case Blend::InvSrcAlpha: return VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA;
    case Blend::DstAlpha: return VK_BLEND_FACTOR_DST_ALPHA;
    case Blend::InvDstAlpha: return VK_BLEND_FACTOR_ONE_MINUS_DST_ALPHA;
    case Blend::DstColor: return VK_BLEND_FACTOR_DST_COLOR;
    case Blend::InvDstColor: return VK_BLEND_FACTOR_ONE_MINUS_DST_COLOR;
    case Blend::SrcAlphaSat: return VK_BLEND_FACTOR_SRC_ALPHA_SATURATE;
    case Blend::Constant: return VK_BLEND_FACTOR_CONSTANT_COLOR;
    case Blend::InvConstant: return VK_BLEND_FACTOR_ONE_MINUS_CONSTANT_COLOR;
    }
    return VK_BLEND_FACTOR_ONE;
}

VkBlendOp MapBlendOp(BlendOp o)
{
    switch (o)
    {
    case BlendOp::Add: return VK_BLEND_OP_ADD;
    case BlendOp::Subtract: return VK_BLEND_OP_SUBTRACT;
    case BlendOp::RevSubtract: return VK_BLEND_OP_REVERSE_SUBTRACT;
    case BlendOp::Min: return VK_BLEND_OP_MIN;
    case BlendOp::Max: return VK_BLEND_OP_MAX;
    }
    return VK_BLEND_OP_ADD;
}

VkStencilOp MapStencilOp(StencilOp o)
{
    switch (o)
    {
    case StencilOp::Keep: return VK_STENCIL_OP_KEEP;
    case StencilOp::Zero: return VK_STENCIL_OP_ZERO;
    case StencilOp::Replace: return VK_STENCIL_OP_REPLACE;
    case StencilOp::IncrSat: return VK_STENCIL_OP_INCREMENT_AND_CLAMP;
    case StencilOp::DecrSat: return VK_STENCIL_OP_DECREMENT_AND_CLAMP;
    case StencilOp::Invert: return VK_STENCIL_OP_INVERT;
    case StencilOp::Incr: return VK_STENCIL_OP_INCREMENT_AND_WRAP;
    case StencilOp::Decr: return VK_STENCIL_OP_DECREMENT_AND_WRAP;
    }
    return VK_STENCIL_OP_KEEP;
}

// gb::Compare lists the comparisons in VkCompareOp's order.
VkCompareOp MapCompare(Compare c)
{
    return VkCompareOp(int(c));
}

VkSamplerAddressMode MapAddress(Address a, bool mirrorClamp)
{
    switch (a)
    {
    case Address::Wrap: return VK_SAMPLER_ADDRESS_MODE_REPEAT;
    case Address::Mirror: return VK_SAMPLER_ADDRESS_MODE_MIRRORED_REPEAT;
    case Address::Clamp: return VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    case Address::Border: return VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_BORDER;
    case Address::MirrorOnce:
        return mirrorClamp ? VK_SAMPLER_ADDRESS_MODE_MIRROR_CLAMP_TO_EDGE : VK_SAMPLER_ADDRESS_MODE_MIRRORED_REPEAT;
    }
    return VK_SAMPLER_ADDRESS_MODE_REPEAT;
}

VkPrimitiveTopology MapPrimitive(Primitive p)
{
    switch (p)
    {
    case Primitive::PointList: return VK_PRIMITIVE_TOPOLOGY_POINT_LIST;
    case Primitive::LineList: return VK_PRIMITIVE_TOPOLOGY_LINE_LIST;
    case Primitive::LineStrip: return VK_PRIMITIVE_TOPOLOGY_LINE_STRIP;
    case Primitive::TriangleList: return VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    case Primitive::TriangleStrip: return VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP;
    case Primitive::TriangleFan: return VK_PRIMITIVE_TOPOLOGY_TRIANGLE_FAN;
    }
    return VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
}

VkPrimitiveTopology MapTopology(Topology t)
{
    return t == Topology::Points  ? VK_PRIMITIVE_TOPOLOGY_POINT_LIST
           : t == Topology::Lines ? VK_PRIMITIVE_TOPOLOGY_LINE_LIST
                                  : VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
}

// ---- shader reflection: the descriptor bindings and vertex inputs a SPIR-V module uses

enum class ImageKind : uint8_t
{
    Tex2D,
    Tex3D,
    Cube,
    Shadow2D,
};

struct Reflection
{
    uint32_t samplers = 0;  // bit b: a sampler at binding b (0-15)
    ImageKind kinds[kSamplerBindings] = {};
    uint32_t inputs = 0;    // vertex shaders: bit l: an input at location l
};

// False when the module is not SPIR-V. Reads OpDecorate (Binding, Location), OpVariable and the types they point to.
bool Reflect(const uint32_t *words, size_t count, Reflection *out)
{
    if (count < 5 || words[0] != 0x07230203)
        return false;
    std::unordered_map<uint32_t, uint32_t> binding, location, varType, varClass, pointee, sampledImage;
    std::unordered_map<uint32_t, ImageKind> image;
    for (size_t at = 5; at < count;)
    {
        const uint32_t length = words[at] >> 16, op = words[at] & 0xFFFF;
        if (!length || at + length > count)
            return false;
        const uint32_t *w = words + at;
        if (op == 71 && length >= 4 && w[2] == 33) // OpDecorate Binding
            binding[w[1]] = w[3];
        else if (op == 71 && length >= 4 && w[2] == 30) // OpDecorate Location
            location[w[1]] = w[3];
        else if (op == 59 && length >= 4) // OpVariable: result type, result, storage class
        {
            varType[w[2]] = w[1];
            varClass[w[2]] = w[3];
        }
        else if (op == 32 && length >= 4) // OpTypePointer: result, storage class, type
            pointee[w[1]] = w[3];
        else if (op == 27 && length >= 3) // OpTypeSampledImage: result, image type
            sampledImage[w[1]] = w[2];
        else if (op == 25 && length >= 9) // OpTypeImage: result, sampled type, dim, depth, ...
            image[w[1]] = w[3] == 2 ? ImageKind::Tex3D : w[3] == 3 ? ImageKind::Cube
                          : w[4] == 1 ? ImageKind::Shadow2D : ImageKind::Tex2D;
        at += length;
    }
    *out = {};
    for (const auto &[var, slot] : binding)
    {
        if (slot >= kSamplerBindings || varClass[var] != 0) // UniformConstant
            continue;
        const auto sampled = sampledImage.find(pointee[varType[var]]);
        if (sampled == sampledImage.end())
            continue;
        out->samplers |= 1u << slot;
        const auto kind = image.find(sampled->second);
        out->kinds[slot] = kind == image.end() ? ImageKind::Tex2D : kind->second;
    }
    for (const auto &[var, loc] : location)
        if (varClass[var] == 1 && loc < 32) // Input
            out->inputs |= 1u << loc;
    return true;
}

// ---- objects

struct Store
{
    VkBuffer buffer = VK_NULL_HANDLE;
    VmaAllocation allocation = VK_NULL_HANDLE;
    uint8_t *mapped = nullptr;
    uint64_t lastUse = 0; // the submission serial of the last recorded work that reads or writes it
};

struct Buffer : gb::Buffer
{
    BufferDesc desc;
    bool hostVisible = false; // Dynamic and Shared buffers: written in place, renamed on DISCARD
    Store store;
    std::vector<Store> spare; // earlier stores of a renamed buffer, reused once the GPU is done with them
};

struct Texture : gb::Texture
{
    TextureDesc desc;
    VkImage image = VK_NULL_HANDLE;
    VmaAllocation allocation = VK_NULL_HANDLE;
    VkFormat format = VK_FORMAT_UNDEFINED;
    uint32_t layers = 1;
    VkImageView sampledView = VK_NULL_HANDLE;
    std::map<uint32_t, VkImageView> attachmentViews; // level << 8 | layer
    uint64_t lastUse = 0;
};

struct Sampler : gb::Sampler
{
    VkSampler sampler = VK_NULL_HANDLE;
};

struct Pipeline;

struct Shader : gb::Shader
{
    Stage stage;
    uint64_t hash;
    VkShaderModule module = VK_NULL_HANDLE;
    Reflection reflection;
    std::vector<Pipeline *> pipelines; // ended with the shader
};

struct Pipeline : gb::Pipeline
{
    PipelineDesc desc;
    std::string key;
    VkPipeline pipeline = VK_NULL_HANDLE;
    uint32_t streams = 0;     // bit s: a vertex buffer binding s
    bool dummyStream = false; // inputs the layout does not feed read kDummyStream
    uint32_t samplers = 0;
    ImageKind kinds[kSamplerBindings] = {};
};

struct Query : gb::Query
{
    QueryType type;
    int slot = -1;           // the frame slot whose pool holds the pending result
    uint32_t index = 0;
    uint64_t serial = 0;     // the submission that writes it; 0 when nothing is pending
    bool open = false;       // occlusion: between Begin and End
    bool hasValue = false;
    uint64_t value = 0;
};

struct Fence : gb::Fence
{
    uint64_t serial = 0;
};

struct Swapchain : gb::Swapchain
{
    SwapchainDesc desc;
    VkSurfaceKHR surface = VK_NULL_HANDLE;
    VkSwapchainKHR swapchain = VK_NULL_HANDLE;
    VkFormat format = VK_FORMAT_UNDEFINED;
    VkExtent2D extent = {};
    std::vector<VkImage> images;
    std::vector<VkImageView> views;
    std::vector<VkSemaphore> renderDone; // one per image, signalled by the frame that draws it
    VkPipeline present = VK_NULL_HANDLE;
    VkFormat presentFormat = VK_FORMAT_UNDEFINED;
    Texture *ramp = nullptr; // D3D9's gamma ramp, 256x1 RGBA16
    bool stale = true;       // made again before the next frame is shown
    bool reportedNoSurface = false;
};

struct UniformBlock
{
    Buffer *buffer = nullptr;
};

struct StagingChunk
{
    Store store;
    uint32_t size = 0;
    uint32_t used = 0;
};

struct FrameSlot
{
    VkCommandPool pool = VK_NULL_HANDLE;
    std::vector<VkCommandBuffer> commands;
    uint32_t commandsUsed = 0;
    uint64_t serial = 0; // its last submission
    std::vector<UniformBlock> uniforms;
    uint32_t uniformBlock = 0, uniformOffset = 0;
    std::vector<StagingChunk> staging;
    uint32_t stagingChunk = 0;
    VkQueryPool occlusion = VK_NULL_HANDLE, timestamps = VK_NULL_HANDLE;
    uint32_t occlusionUsed = 0, timestampsUsed = 0;
    std::vector<Query *> queries; // queries whose pending result is in this slot's pools
    VkSemaphore acquire = VK_NULL_HANDLE;
};

struct Deferred
{
    uint64_t serial;
    std::function<void()> destroy;
};

// ---- the device

struct State
{
    std::recursive_mutex lock;
    bool initialized = false;
    Caps caps = {};
    std::string deviceName;

    VkInstance instance = VK_NULL_HANDLE;
    VkDebugUtilsMessengerEXT messenger = VK_NULL_HANDLE;
    bool surfaces = false; // the instance has VK_KHR_surface
    VkPhysicalDevice physical = VK_NULL_HANDLE;
    VkPhysicalDeviceProperties properties = {};
    VkDevice device = VK_NULL_HANDLE;
    uint32_t family = 0;
    VkQueue queue = VK_NULL_HANDLE;
    VmaAllocator allocator = VK_NULL_HANDLE;
    bool anisotropy = false, wireframe = false, mirrorClamp = false;
    bool timestamps = false;
    float timestampPeriod = 1.0f;

    VkSemaphore timeline = VK_NULL_HANDLE;
    uint64_t submitted = 0; // the last submission's serial
    uint64_t completed = 0; // the last one the GPU finished, as last read

    VkDescriptorSetLayout setLayout = VK_NULL_HANDLE;
    VkPipelineLayout layout = VK_NULL_HANDLE;
    VkPipelineCache cache = VK_NULL_HANDLE;
    VkShaderModule presentVertex = VK_NULL_HANDLE, presentPixel = VK_NULL_HANDLE;

    FrameSlot frames[kFramesInFlight];
    uint32_t frame = 0;
    bool frameOpen = false;
    VkCommandBuffer setup = VK_NULL_HANDLE; // uploads and first layouts, submitted before `cmd`
    VkCommandBuffer cmd = VK_NULL_HANDLE;
    std::vector<Deferred> deferred;

    // the open pass, which a flush or an in-order upload suspends and resumes
    bool rendering = false;
    PassDesc pass = {};
    VkRect2D passArea = {};
    const Pipeline *bound = nullptr;
    int openOcclusion = 0;

    std::unordered_map<std::string, Sampler *> samplers;
    std::unordered_map<std::string, Pipeline *> pipelines;

    // what a draw binds where the frontend bound nothing
    Texture *dummy[4] = {}; // per ImageKind
    const Sampler *dummySampler = nullptr, *dummyShadowSampler = nullptr, *presentSampler = nullptr,
                  *rampSampler = nullptr;
    Buffer *dummyVertices = nullptr;

    Buffer readback;
    uint32_t readbackSize = 0;
    int debugMessages = 0;

    // perf
    uint64_t draws = 0, presented = 0, flushes = 0, renames = 0, suspends = 0, newPipelines = 0;
    std::chrono::steady_clock::time_point perfStart = std::chrono::steady_clock::now();
};

State &S()
{
    static State *state = new State();
    return *state;
}

uint64_t Pending()
{
    return S().submitted + 1;
}

uint64_t Completed()
{
    State &s = S();
    uint64_t value = 0;
    if (vkGetSemaphoreCounterValue(s.device, s.timeline, &value) == VK_SUCCESS)
        s.completed = value;
    return s.completed;
}

void WaitSerial(uint64_t serial)
{
    State &s = S();
    if (serial <= s.completed)
        return;
    VkSemaphoreWaitInfo wait = {VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO};
    wait.semaphoreCount = 1;
    wait.pSemaphores = &s.timeline;
    wait.pValues = &serial;
    Ok(vkWaitSemaphores(s.device, &wait, UINT64_MAX), "vkWaitSemaphores");
    Completed();
}

void Defer(std::function<void()> destroy)
{
    S().deferred.push_back({Pending(), std::move(destroy)});
}

void RunDeferred()
{
    State &s = S();
    const uint64_t done = Completed();
    size_t kept = 0;
    for (size_t i = 0; i < s.deferred.size(); ++i)
    {
        if (s.deferred[i].serial <= done)
            s.deferred[i].destroy();
        else
            s.deferred[kept++] = std::move(s.deferred[i]);
    }
    s.deferred.resize(kept);
}

// A full memory barrier: everything recorded or submitted before it finishes its writes before anything after it
// reads or writes. Outside a pass only.
void FullBarrier(VkCommandBuffer cmd)
{
    VkMemoryBarrier barrier = {VK_STRUCTURE_TYPE_MEMORY_BARRIER};
    barrier.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 1, &barrier,
                         0, nullptr, 0, nullptr);
}

bool MakeStore(Store *store, uint32_t size, VkBufferUsageFlags usage, bool hostVisible, bool readback = false)
{
    State &s = S();
    VkBufferCreateInfo info = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
    info.size = size ? size : 4;
    info.usage = usage | VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
    VmaAllocationCreateInfo alloc = {};
    alloc.usage = VMA_MEMORY_USAGE_AUTO;
    if (hostVisible)
        alloc.flags = VMA_ALLOCATION_CREATE_MAPPED_BIT |
                      (readback ? VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT
                                : VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT);
    VmaAllocationInfo result = {};
    if (!Ok(vmaCreateBuffer(s.allocator, &info, &alloc, &store->buffer, &store->allocation, &result),
            "vmaCreateBuffer"))
        return false;
    store->mapped = static_cast<uint8_t *>(result.pMappedData);
    store->lastUse = 0;
    return true;
}

void FreeStore(Store &store)
{
    if (store.buffer)
        vmaDestroyBuffer(S().allocator, store.buffer, store.allocation);
    store = {};
}

void DeferFreeStore(const Store &store)
{
    if (!store.buffer)
        return;
    Store copy = store;
    Defer([copy]() mutable { FreeStore(copy); });
}

// ---- frames and submissions

VkCommandBuffer NextCommandBuffer()
{
    State &s = S();
    FrameSlot &f = s.frames[s.frame];
    if (f.commandsUsed == f.commands.size())
    {
        VkCommandBufferAllocateInfo info = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
        info.commandPool = f.pool;
        info.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        info.commandBufferCount = 1;
        VkCommandBuffer cmd = VK_NULL_HANDLE;
        if (!Ok(vkAllocateCommandBuffers(s.device, &info, &cmd), "vkAllocateCommandBuffers"))
            return VK_NULL_HANDLE;
        f.commands.push_back(cmd);
    }
    VkCommandBuffer cmd = f.commands[f.commandsUsed++];
    VkCommandBufferBeginInfo begin = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    begin.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    vkBeginCommandBuffer(cmd, &begin);
    return cmd;
}

void HarvestQueries(FrameSlot &f);

void BeginFrame()
{
    State &s = S();
    if (s.frameOpen)
        return;
    s.frame = (s.frame + 1) % kFramesInFlight;
    FrameSlot &f = s.frames[s.frame];
    WaitSerial(f.serial);
    HarvestQueries(f);
    vkResetCommandPool(s.device, f.pool, 0);
    f.commandsUsed = 0;
    f.uniformBlock = f.uniformOffset = 0;
    f.stagingChunk = 0;
    for (StagingChunk &chunk : f.staging)
        chunk.used = 0;
    vkResetQueryPool(s.device, f.occlusion, 0, kQueriesPerFrame);
    if (f.timestamps)
        vkResetQueryPool(s.device, f.timestamps, 0, kQueriesPerFrame);
    f.occlusionUsed = f.timestampsUsed = 0;
    RunDeferred();
    s.frameOpen = true;
}

VkCommandBuffer Cmd()
{
    State &s = S();
    BeginFrame();
    if (!s.cmd)
    {
        s.cmd = NextCommandBuffer();
        s.bound = nullptr;
    }
    return s.cmd;
}

VkCommandBuffer Setup()
{
    State &s = S();
    BeginFrame();
    if (!s.setup)
    {
        s.setup = NextCommandBuffer();
        FullBarrier(s.setup);
    }
    return s.setup;
}

// Submits what is recorded (setup first), signalling the timeline. `wait` / `signal`: binary semaphores of a Present.
void Submit(VkSemaphore wait = VK_NULL_HANDLE, VkSemaphore signal = VK_NULL_HANDLE)
{
    State &s = S();
    VkCommandBuffer cmds[2];
    uint32_t count = 0;
    if (s.setup)
    {
        FullBarrier(s.setup);
        vkEndCommandBuffer(s.setup);
        cmds[count++] = s.setup;
    }
    if (s.cmd)
    {
        vkEndCommandBuffer(s.cmd);
        cmds[count++] = s.cmd;
    }
    s.setup = s.cmd = VK_NULL_HANDLE;
    s.bound = nullptr;
    if (!count && !wait && !signal)
        return;
    const uint64_t serial = ++s.submitted;
    const uint64_t values[2] = {serial, 0};
    const VkSemaphore signals[2] = {s.timeline, signal};
    VkTimelineSemaphoreSubmitInfo timeline = {VK_STRUCTURE_TYPE_TIMELINE_SEMAPHORE_SUBMIT_INFO};
    timeline.signalSemaphoreValueCount = signal ? 2 : 1;
    timeline.pSignalSemaphoreValues = values;
    const uint64_t waitValue = 0;
    timeline.waitSemaphoreValueCount = wait ? 1 : 0;
    timeline.pWaitSemaphoreValues = &waitValue;
    const VkPipelineStageFlags waitStage = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    VkSubmitInfo submit = {VK_STRUCTURE_TYPE_SUBMIT_INFO};
    submit.pNext = &timeline;
    submit.waitSemaphoreCount = wait ? 1 : 0;
    submit.pWaitSemaphores = &wait;
    submit.pWaitDstStageMask = &waitStage;
    submit.commandBufferCount = count;
    submit.pCommandBuffers = cmds;
    submit.signalSemaphoreCount = signal ? 2 : 1;
    submit.pSignalSemaphores = signals;
    Ok(vkQueueSubmit(s.queue, 1, &submit, VK_NULL_HANDLE), "vkQueueSubmit");
    s.frames[s.frame].serial = serial;
}

void MarkTexture(Texture *t)
{
    if (t)
        t->lastUse = Pending();
}

VkImageView AttachmentView(Texture *t, uint8_t level, uint8_t layer);

void BeginRendering(const PassDesc &d, bool resume)
{
    State &s = S();
    VkCommandBuffer cmd = Cmd();
    FullBarrier(cmd);
    VkRenderingAttachmentInfo colors[MAX_COLOR_TARGETS] = {};
    for (int i = 0; i < d.colorCount; ++i)
    {
        Texture *t = static_cast<Texture *>(d.color[i].texture);
        MarkTexture(t);
        VkRenderingAttachmentInfo &a = colors[i];
        a.sType = VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO;
        a.imageView = AttachmentView(t, d.color[i].level, d.color[i].layer);
        a.imageLayout = VK_IMAGE_LAYOUT_GENERAL;
        a.loadOp = resume || d.color[i].load == LoadOp::Load ? VK_ATTACHMENT_LOAD_OP_LOAD
                   : d.color[i].load == LoadOp::Clear        ? VK_ATTACHMENT_LOAD_OP_CLEAR
                                                             : VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        a.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
        std::memcpy(a.clearValue.color.float32, d.color[i].clear, sizeof(float) * 4);
        // X8 formats read alpha 1 in D3D9 (as a blend's destination alpha too): it is kept at 1 in the image.
        if (t->desc.format == Format::BGRX8)
            a.clearValue.color.float32[3] = 1.0f;
    }
    VkRenderingAttachmentInfo depth = {VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO};
    VkRenderingAttachmentInfo stencil = {VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO};
    Texture *z = static_cast<Texture *>(d.depth);
    if (z)
    {
        MarkTexture(z);
        depth.imageView = AttachmentView(z, 0, 0);
        depth.imageLayout = VK_IMAGE_LAYOUT_GENERAL;
        depth.loadOp = resume || d.depthLoad == LoadOp::Load ? VK_ATTACHMENT_LOAD_OP_LOAD
                       : d.depthLoad == LoadOp::Clear        ? VK_ATTACHMENT_LOAD_OP_CLEAR
                                                             : VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        depth.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
        depth.clearValue.depthStencil = {d.clearDepth, d.clearStencil};
        stencil = depth;
        stencil.loadOp = resume || d.stencilLoad == LoadOp::Load ? VK_ATTACHMENT_LOAD_OP_LOAD
                         : d.stencilLoad == LoadOp::Clear        ? VK_ATTACHMENT_LOAD_OP_CLEAR
                                                                 : VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    }
    VkRenderingInfo info = {VK_STRUCTURE_TYPE_RENDERING_INFO};
    info.renderArea = s.passArea;
    info.layerCount = 1;
    info.colorAttachmentCount = d.colorCount;
    info.pColorAttachments = colors;
    info.pDepthAttachment = z ? &depth : nullptr;
    info.pStencilAttachment = z && HasStencil(z->desc.format) ? &stencil : nullptr;
    vkCmdBeginRendering(cmd, &info);
    s.rendering = true;
    s.bound = nullptr;
}

void SuspendRendering()
{
    State &s = S();
    vkCmdEndRendering(s.cmd);
    s.rendering = false;
    ++s.suspends;
}

// Submits the recorded work now (a readback, a polled query or fence), carrying an open pass over to new commands.
void Flush()
{
    State &s = S();
    const bool wasRendering = s.rendering;
    if (wasRendering)
        SuspendRendering();
    Submit();
    ++s.flushes;
    if (wasRendering)
        BeginRendering(s.pass, true);
}

// ---- staging and uniform memory

struct Staged
{
    VkBuffer buffer;
    uint32_t offset;
    uint8_t *data;
};

bool StageBytes(uint32_t size, Staged *out)
{
    State &s = S();
    BeginFrame();
    FrameSlot &f = s.frames[s.frame];
    for (; f.stagingChunk < f.staging.size(); ++f.stagingChunk)
    {
        StagingChunk &chunk = f.staging[f.stagingChunk];
        const uint32_t at = (chunk.used + 15u) & ~15u;
        if (at + size <= chunk.size)
        {
            chunk.used = at + size;
            *out = {chunk.store.buffer, at, chunk.store.mapped + at};
            return true;
        }
    }
    StagingChunk chunk;
    chunk.size = std::max(size, kStagingChunkBytes);
    if (!MakeStore(&chunk.store, chunk.size, 0, true))
        return false;
    chunk.used = size;
    f.staging.push_back(chunk);
    f.stagingChunk = uint32_t(f.staging.size() - 1);
    *out = {chunk.store.buffer, 0, chunk.store.mapped};
    return true;
}

// Where an upload of a resource whose last use is `lastUse` is recorded: the setup buffer when no work recorded in
// this frame's open commands uses the resource, else the frame itself, the pass suspended around the copy.
struct UploadTarget
{
    VkCommandBuffer cmd;
    bool inFrame;
    bool resume; // the pass to begin again after the copy
};

UploadTarget BeginUpload(uint64_t lastUse)
{
    State &s = S();
    BeginFrame();
    if (lastUse != Pending() || !s.cmd)
        return {Setup(), false, false};
    const bool resume = s.rendering;
    if (resume)
        SuspendRendering();
    FullBarrier(s.cmd);
    return {s.cmd, true, resume};
}

void EndUpload(const UploadTarget &t)
{
    if (!t.inFrame)
        return;
    FullBarrier(t.cmd);
    if (t.resume)
        BeginRendering(S().pass, true);
}

// ---- formats the device supports

uint8_t FormatFlags(Format f)
{
    State &s = S();
    const FormatMap m = MapFormat(f);
    if (m.format == VK_FORMAT_UNDEFINED)
        return 0;
    VkFormatProperties p = {};
    vkGetPhysicalDeviceFormatProperties(s.physical, m.format, &p);
    const VkFormatFeatureFlags t = p.optimalTilingFeatures;
    const VkFormatFeatureFlags copy = VK_FORMAT_FEATURE_TRANSFER_SRC_BIT | VK_FORMAT_FEATURE_TRANSFER_DST_BIT;
    if ((t & copy) != copy)
        return 0;
    uint8_t flags = 0;
    if (t & VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT)
        flags |= FORMAT_SAMPLED;
    if (t & VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT)
        flags |= FORMAT_FILTERABLE;
    if (IsDepthFormat(f) && (t & VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT))
        flags |= FORMAT_DEPTH_TARGET;
    // A colour target is also blitted from and into (StretchRect, resolves).
    const VkFormatFeatureFlags target =
        VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT | VK_FORMAT_FEATURE_BLIT_SRC_BIT | VK_FORMAT_FEATURE_BLIT_DST_BIT;
    if (!IsDepthFormat(f) && (t & target) == target)
        flags |= FORMAT_COLOR_TARGET;
    return flags;
}

// ---- textures

VkImageViewType ViewType(const TextureDesc &d)
{
    return d.type == TextureType::Cube ? VK_IMAGE_VIEW_TYPE_CUBE
           : d.type == TextureType::Tex3D ? VK_IMAGE_VIEW_TYPE_3D
                                          : VK_IMAGE_VIEW_TYPE_2D;
}

VkImageView AttachmentView(Texture *t, uint8_t level, uint8_t layer)
{
    const uint32_t key = uint32_t(level) << 8 | layer;
    const auto found = t->attachmentViews.find(key);
    if (found != t->attachmentViews.end())
        return found->second;
    VkImageViewCreateInfo info = {VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
    info.image = t->image;
    info.viewType = VK_IMAGE_VIEW_TYPE_2D;
    info.format = t->format;
    info.subresourceRange = {AttachmentAspect(t->desc.format), level, 1, layer, 1};
    VkImageView view = VK_NULL_HANDLE;
    Ok(vkCreateImageView(S().device, &info, nullptr, &view), "vkCreateImageView (attachment)");
    t->attachmentViews[key] = view;
    return view;
}

void FreeTexture(Texture *t)
{
    State &s = S();
    for (auto &[key, view] : t->attachmentViews)
        vkDestroyImageView(s.device, view, nullptr);
    if (t->sampledView)
        vkDestroyImageView(s.device, t->sampledView, nullptr);
    if (t->image)
        vmaDestroyImage(s.allocator, t->image, t->allocation);
    delete t;
}

Texture *MakeTexture(const TextureDesc &desc)
{
    State &s = S();
    const FormatMap m = MapFormat(desc.format);
    if (m.format == VK_FORMAT_UNDEFINED || !desc.width || !desc.height)
        return nullptr;
    Texture *t = new Texture();
    t->desc = desc;
    t->format = m.format;
    t->layers = desc.type == TextureType::Cube ? 6 : 1;
    VkImageCreateInfo info = {VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
    info.flags = desc.type == TextureType::Cube ? VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT : 0;
    info.imageType = desc.type == TextureType::Tex3D ? VK_IMAGE_TYPE_3D : VK_IMAGE_TYPE_2D;
    info.format = m.format;
    info.extent = {desc.width, desc.height, desc.type == TextureType::Tex3D ? std::max<uint32_t>(desc.depth, 1) : 1};
    info.mipLevels = std::max<uint32_t>(desc.levels, 1);
    info.arrayLayers = t->layers;
    info.samples = VkSampleCountFlagBits(std::max<uint32_t>(desc.samples, 1));
    info.tiling = VK_IMAGE_TILING_OPTIMAL;
    info.usage = VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    // Colour targets are always sampled here: Present reads the image it shows through a shader.
    const bool sampled = desc.samples <= 1 && (desc.sampled || desc.usage != Usage::DepthStencil);
    if (sampled)
        info.usage |= VK_IMAGE_USAGE_SAMPLED_BIT;
    if (desc.usage == Usage::RenderTarget)
        info.usage |= VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    if (desc.usage == Usage::DepthStencil)
        info.usage |= VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT;
    info.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    VmaAllocationCreateInfo alloc = {};
    alloc.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;
    if (!Ok(vmaCreateImage(s.allocator, &info, &alloc, &t->image, &t->allocation, nullptr), "vmaCreateImage"))
    {
        delete t;
        return nullptr;
    }
    if (sampled)
    {
        VkImageViewCreateInfo view = {VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
        view.image = t->image;
        view.viewType = ViewType(desc);
        view.format = m.format;
        const bool alphaIsOne = desc.format == Format::BGRX8;
        view.components = {MapSource(desc.swizzle.r, alphaIsOne), MapSource(desc.swizzle.g, alphaIsOne),
                           MapSource(desc.swizzle.b, alphaIsOne), MapSource(desc.swizzle.a, alphaIsOne)};
        view.subresourceRange = {m.aspect, 0, info.mipLevels, 0, t->layers};
        if (!Ok(vkCreateImageView(s.device, &view, nullptr, &t->sampledView), "vkCreateImageView"))
        {
            FreeTexture(t);
            return nullptr;
        }
    }
    // Every image lives in GENERAL from here on; the transition goes before any use, in the setup commands.
    VkImageMemoryBarrier barrier = {VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
    barrier.srcAccessMask = 0;
    barrier.dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;
    barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
    barrier.srcQueueFamilyIndex = barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.image = t->image;
    barrier.subresourceRange = {AttachmentAspect(desc.format), 0, info.mipLevels, 0, t->layers};
    vkCmdPipelineBarrier(Setup(), VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 0, nullptr,
                         0, nullptr, 1, &barrier);
    return t;
}

void Upload2D(Texture *t, uint8_t level, uint8_t layer, const Box &box, const void *data, uint32_t rowPitch,
              uint32_t slicePitch)
{
    const TextureDesc &d = t->desc;
    const bool block = IsBlockFormat(d.format);
    const uint32_t bytes = FormatBytes(d.format);
    const uint32_t columns = block ? (box.width + 3) / 4 : box.width;
    const uint32_t rows = block ? (box.height + 3) / 4 : box.height;
    const uint32_t depth = std::max<uint32_t>(box.depth, 1);
    const uint32_t rowBytes = columns * bytes;
    Staged staged;
    if (!StageBytes(rowBytes * rows * depth, &staged))
        return;
    for (uint32_t z = 0; z < depth; ++z)
        for (uint32_t y = 0; y < rows; ++y)
            std::memcpy(staged.data + (size_t(z) * rows + y) * rowBytes,
                        static_cast<const uint8_t *>(data) + size_t(z) * slicePitch + size_t(y) * rowPitch, rowBytes);
    const UploadTarget target = BeginUpload(t->lastUse);
    VkBufferImageCopy region = {};
    region.bufferOffset = staged.offset;
    region.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, level, d.type == TextureType::Cube ? layer : 0u, 1};
    region.imageOffset = {int32_t(box.x), int32_t(box.y), d.type == TextureType::Tex3D ? int32_t(box.z) : 0};
    // A block format's copy covers whole blocks, clipped to the level as Vulkan wants it.
    const uint32_t levelWidth = LevelExtent(d.width, level), levelHeight = LevelExtent(d.height, level);
    region.imageExtent = {std::min<uint32_t>(box.width, levelWidth - box.x),
                          std::min<uint32_t>(box.height, levelHeight - box.y), depth};
    vkCmdCopyBufferToImage(target.cmd, staged.buffer, t->image, VK_IMAGE_LAYOUT_GENERAL, 1, &region);
    EndUpload(target);
}

// ---- samplers, shaders, pipelines

const Sampler *MakeSampler(const SamplerDesc &d)
{
    State &s = S();
    const std::string key = SamplerKey(d);
    const auto found = s.samplers.find(key);
    if (found != s.samplers.end())
        return found->second;
    VkSamplerCreateInfo info = {VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};
    info.magFilter = d.magFilter == Filter::Linear ? VK_FILTER_LINEAR : VK_FILTER_NEAREST;
    info.minFilter = d.minFilter == Filter::Linear ? VK_FILTER_LINEAR : VK_FILTER_NEAREST;
    info.mipmapMode = d.mipFilter == MipFilter::Linear ? VK_SAMPLER_MIPMAP_MODE_LINEAR : VK_SAMPLER_MIPMAP_MODE_NEAREST;
    info.addressModeU = MapAddress(d.addressU, s.mirrorClamp);
    info.addressModeV = MapAddress(d.addressV, s.mirrorClamp);
    info.addressModeW = MapAddress(d.addressW, s.mirrorClamp);
    info.anisotropyEnable = s.anisotropy && d.maxAnisotropy > 1;
    info.maxAnisotropy = std::min(float(d.maxAnisotropy), s.properties.limits.maxSamplerAnisotropy);
    info.compareEnable = d.depthCompare;
    info.compareOp = VK_COMPARE_OP_LESS_OR_EQUAL;
    info.minLod = 0.0f;
    // MipFilter::None reads the top level only, as GL's base-level filter does.
    info.maxLod = d.mipFilter == MipFilter::None ? 0.25f : VK_LOD_CLAMP_NONE;
    info.borderColor = VK_BORDER_COLOR_FLOAT_TRANSPARENT_BLACK;
    Sampler *sampler = new Sampler();
    if (!Ok(vkCreateSampler(s.device, &info, nullptr, &sampler->sampler), "vkCreateSampler"))
    {
        delete sampler;
        return nullptr;
    }
    s.samplers[key] = sampler;
    return sampler;
}

VkShaderModule MakeModule(const void *code, size_t size)
{
    VkShaderModuleCreateInfo info = {VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
    info.codeSize = size;
    // SPIR-V words must be 4-aligned; the caller's bytes need not be.
    std::vector<uint32_t> words((size + 3) / 4);
    std::memcpy(words.data(), code, size);
    info.pCode = words.data();
    VkShaderModule module = VK_NULL_HANDLE;
    Ok(vkCreateShaderModule(S().device, &info, nullptr, &module), "vkCreateShaderModule");
    return module;
}

void FreePipeline(Pipeline *p)
{
    if (p->pipeline)
        vkDestroyPipeline(S().device, p->pipeline, nullptr);
    delete p;
}

VkPipeline BuildPipeline(Pipeline *p, const Shader *vertex, const Shader *pixel)
{
    State &s = S();
    const PipelineDesc &d = p->desc;
    VkVertexInputBindingDescription bindings[MAX_STREAMS + 1];
    VkVertexInputAttributeDescription attributes[MAX_ATTRIBS + 32];
    uint32_t bindingCount = 0, attributeCount = 0;
    uint32_t fed = 0;
    for (int i = 0; i < d.attribCount && i < MAX_ATTRIBS; ++i)
    {
        const VertexAttrib &a = d.attribs[i];
        p->streams |= 1u << a.stream;
        fed |= 1u << a.location;
        attributes[attributeCount++] = {a.location, a.stream, MapAttrib(a.type), a.offset};
    }
    // D3D9 reads (0, 0, 0, 1) from an input the declaration does not give; Vulkan leaves it undefined.
    const uint32_t missing = vertex->reflection.inputs & ~fed;
    for (uint32_t l = 0; l < 32; ++l)
        if (missing & (1u << l))
            attributes[attributeCount++] = {l, kDummyStream, VK_FORMAT_R32G32B32A32_SFLOAT, 0};
    p->dummyStream = missing != 0;
    for (uint32_t b = 0; b < MAX_STREAMS; ++b)
        if (p->streams & (1u << b))
            bindings[bindingCount++] = {b, 0, VK_VERTEX_INPUT_RATE_VERTEX};
    if (p->dummyStream)
        bindings[bindingCount++] = {kDummyStream, 0, VK_VERTEX_INPUT_RATE_VERTEX};
    VkPipelineVertexInputStateCreateInfo input = {VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
    input.vertexBindingDescriptionCount = bindingCount;
    input.pVertexBindingDescriptions = bindings;
    input.vertexAttributeDescriptionCount = attributeCount;
    input.pVertexAttributeDescriptions = attributes;

    VkPipelineInputAssemblyStateCreateInfo assembly = {VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};
    assembly.topology = MapTopology(d.topology);
    VkPipelineViewportStateCreateInfo viewport = {VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO};
    viewport.viewportCount = 1;
    viewport.scissorCount = 1;

    VkPipelineRasterizationStateCreateInfo raster = {VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};
    raster.polygonMode = d.raster.fill == Fill::Wireframe && s.wireframe ? VK_POLYGON_MODE_LINE : VK_POLYGON_MODE_FILL;
    raster.cullMode = d.raster.cull == Cull::Front  ? VK_CULL_MODE_FRONT_BIT
                      : d.raster.cull == Cull::Back ? VK_CULL_MODE_BACK_BIT
                                                    : VK_CULL_MODE_NONE;
    // D3D9's clockwise front faces; the negative viewport height keeps the winding as D3D9 sees it on screen.
    raster.frontFace = VK_FRONT_FACE_CLOCKWISE;
    raster.depthBiasEnable = d.raster.depthBias != 0.0f || d.raster.slopeScaledDepthBias != 0.0f;
    // D3DRS_DEPTHBIAS is a depth offset; Vulkan's constant factor counts the depth format's smallest steps.
    raster.depthBiasConstantFactor = d.raster.depthBias * (d.depthFormat == Format::D16 ? 65536.0f : 16777216.0f);
    raster.depthBiasSlopeFactor = d.raster.slopeScaledDepthBias;
    raster.lineWidth = 1.0f;

    VkPipelineMultisampleStateCreateInfo multisample = {VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO};
    multisample.rasterizationSamples = VkSampleCountFlagBits(std::max<uint32_t>(d.samples, 1));

    const DepthStencilState &ds = d.depthStencil;
    VkPipelineDepthStencilStateCreateInfo depth = {VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO};
    depth.depthTestEnable = ds.depthTest;
    depth.depthWriteEnable = ds.depthWrite;
    depth.depthCompareOp = MapCompare(ds.depthFunc);
    depth.stencilTestEnable = ds.stencil;
    auto face = [&](const StencilFace &f) {
        VkStencilOpState o = {};
        o.failOp = MapStencilOp(f.fail);
        o.passOp = MapStencilOp(f.pass);
        o.depthFailOp = MapStencilOp(f.depthFail);
        o.compareOp = MapCompare(f.func);
        o.compareMask = ds.readMask;
        o.writeMask = ds.writeMask;
        return o;
    };
    depth.front = face(ds.front);
    depth.back = face(ds.back);
    depth.maxDepthBounds = 1.0f;

    VkPipelineColorBlendAttachmentState blends[MAX_COLOR_TARGETS] = {};
    for (int i = 0; i < d.colorCount; ++i)
    {
        VkPipelineColorBlendAttachmentState &b = blends[i];
        b.blendEnable = d.blend.enable;
        b.srcColorBlendFactor = MapBlend(d.blend.srcColor);
        b.dstColorBlendFactor = MapBlend(d.blend.dstColor);
        b.colorBlendOp = MapBlendOp(d.blend.opColor);
        b.srcAlphaBlendFactor = MapBlend(d.blend.srcAlpha);
        b.dstAlphaBlendFactor = MapBlend(d.blend.dstAlpha);
        b.alphaBlendOp = MapBlendOp(d.blend.opAlpha);
        // Bit 0 red .. bit 3 alpha, as Vulkan's; an X8 target's alpha stays 1 (BeginRendering).
        b.colorWriteMask = d.blend.writeMask & (d.colorFormats[i] == Format::BGRX8 ? 0x7 : 0xF);
    }
    VkPipelineColorBlendStateCreateInfo blend = {VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO};
    blend.attachmentCount = d.colorCount;
    blend.pAttachments = blends;

    const VkDynamicState dynamics[] = {VK_DYNAMIC_STATE_VIEWPORT,           VK_DYNAMIC_STATE_SCISSOR,
                                       VK_DYNAMIC_STATE_STENCIL_REFERENCE,  VK_DYNAMIC_STATE_BLEND_CONSTANTS,
                                       VK_DYNAMIC_STATE_PRIMITIVE_TOPOLOGY, VK_DYNAMIC_STATE_VERTEX_INPUT_BINDING_STRIDE};
    VkPipelineDynamicStateCreateInfo dynamic = {VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO};
    dynamic.dynamicStateCount = sizeof(dynamics) / sizeof(dynamics[0]);
    dynamic.pDynamicStates = dynamics;

    VkFormat colorFormats[MAX_COLOR_TARGETS];
    for (int i = 0; i < d.colorCount; ++i)
        colorFormats[i] = MapFormat(d.colorFormats[i]).format;
    VkPipelineRenderingCreateInfo rendering = {VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO};
    rendering.colorAttachmentCount = d.colorCount;
    rendering.pColorAttachmentFormats = colorFormats;
    rendering.depthAttachmentFormat = d.depthFormat != Format::Unknown ? MapFormat(d.depthFormat).format
                                                                       : VK_FORMAT_UNDEFINED;
    rendering.stencilAttachmentFormat = HasStencil(d.depthFormat) ? rendering.depthAttachmentFormat
                                                                  : VK_FORMAT_UNDEFINED;

    VkPipelineShaderStageCreateInfo stages[2] = {};
    stages[0].sType = stages[1].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[0].stage = VK_SHADER_STAGE_VERTEX_BIT;
    stages[0].module = vertex->module;
    stages[0].pName = "main";
    stages[1].stage = VK_SHADER_STAGE_FRAGMENT_BIT;
    stages[1].module = pixel->module;
    stages[1].pName = "main";

    VkGraphicsPipelineCreateInfo info = {VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};
    info.pNext = &rendering;
    info.stageCount = 2;
    info.pStages = stages;
    info.pVertexInputState = &input;
    info.pInputAssemblyState = &assembly;
    info.pViewportState = &viewport;
    info.pRasterizationState = &raster;
    info.pMultisampleState = &multisample;
    info.pDepthStencilState = &depth;
    info.pColorBlendState = &blend;
    info.pDynamicState = &dynamic;
    info.layout = s.layout;
    VkPipeline pipeline = VK_NULL_HANDLE;
    if (!Ok(vkCreateGraphicsPipelines(s.device, s.cache, 1, &info, nullptr, &pipeline), "vkCreateGraphicsPipelines"))
        return VK_NULL_HANDLE;
    ++s.newPipelines;
    return pipeline;
}

// ---- queries

void HarvestQueries(FrameSlot &f)
{
    State &s = S();
    for (Query *q : f.queries)
    {
        if (q->slot != int(&f - s.frames) || !q->serial)
            continue;
        uint64_t value = 0;
        const VkQueryPool pool = q->type == QueryType::Occlusion ? f.occlusion : f.timestamps;
        if (vkGetQueryPoolResults(s.device, pool, q->index, 1, sizeof(value), &value, sizeof(value),
                                  VK_QUERY_RESULT_64_BIT) == VK_SUCCESS)
        {
            q->value = q->type == QueryType::Timestamp ? uint64_t(double(value) * s.timestampPeriod) : value;
            q->hasValue = true;
        }
        q->slot = -1;
        q->serial = 0;
    }
    f.queries.clear();
}

uint64_t CpuNanoseconds()
{
    return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
                        std::chrono::steady_clock::now().time_since_epoch())
                        .count());
}

// ---- swapchains

void FreeSwapchainImages(Swapchain *sc)
{
    State &s = S();
    for (VkImageView view : sc->views)
        vkDestroyImageView(s.device, view, nullptr);
    for (VkSemaphore semaphore : sc->renderDone)
        vkDestroySemaphore(s.device, semaphore, nullptr);
    sc->views.clear();
    sc->renderDone.clear();
    sc->images.clear();
}

VkPipeline PresentPipeline(VkFormat format)
{
    State &s = S();
    VkPipelineVertexInputStateCreateInfo input = {VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
    VkPipelineInputAssemblyStateCreateInfo assembly = {VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};
    assembly.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    VkPipelineViewportStateCreateInfo viewport = {VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO};
    viewport.viewportCount = viewport.scissorCount = 1;
    VkPipelineRasterizationStateCreateInfo raster = {VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};
    raster.cullMode = VK_CULL_MODE_NONE;
    raster.lineWidth = 1.0f;
    VkPipelineMultisampleStateCreateInfo multisample = {VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO};
    multisample.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;
    VkPipelineColorBlendAttachmentState attachment = {};
    attachment.colorWriteMask = 0xF;
    VkPipelineColorBlendStateCreateInfo blend = {VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO};
    blend.attachmentCount = 1;
    blend.pAttachments = &attachment;
    const VkDynamicState dynamics[] = {VK_DYNAMIC_STATE_VIEWPORT, VK_DYNAMIC_STATE_SCISSOR};
    VkPipelineDynamicStateCreateInfo dynamic = {VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO};
    dynamic.dynamicStateCount = 2;
    dynamic.pDynamicStates = dynamics;
    VkPipelineRenderingCreateInfo rendering = {VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO};
    rendering.colorAttachmentCount = 1;
    rendering.pColorAttachmentFormats = &format;
    VkPipelineShaderStageCreateInfo stages[2] = {};
    stages[0].sType = stages[1].sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stages[0].stage = VK_SHADER_STAGE_VERTEX_BIT;
    stages[0].module = s.presentVertex;
    stages[0].pName = "main";
    stages[1].stage = VK_SHADER_STAGE_FRAGMENT_BIT;
    stages[1].module = s.presentPixel;
    stages[1].pName = "main";
    VkGraphicsPipelineCreateInfo info = {VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};
    info.pNext = &rendering;
    info.stageCount = 2;
    info.pStages = stages;
    info.pVertexInputState = &input;
    info.pInputAssemblyState = &assembly;
    info.pViewportState = &viewport;
    info.pRasterizationState = &raster;
    info.pMultisampleState = &multisample;
    info.pColorBlendState = &blend;
    info.pDynamicState = &dynamic;
    info.layout = s.layout;
    VkPipeline pipeline = VK_NULL_HANDLE;
    Ok(vkCreateGraphicsPipelines(s.device, s.cache, 1, &info, nullptr, &pipeline), "vkCreateGraphicsPipelines (present)");
    return pipeline;
}

// (Re)makes the swapchain at the window's size. False when there is nothing to show into (no surface, a minimised
// window).
bool MakeSwapchainImages(Swapchain *sc)
{
    State &s = S();
    if (!sc->surface)
        return false;
    VkSurfaceCapabilitiesKHR caps = {};
    if (!Ok(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(s.physical, sc->surface, &caps), "surface capabilities"))
        return false;
    VkExtent2D extent = caps.currentExtent;
    if (extent.width == 0xFFFFFFFFu)
    {
        int w = 0, h = 0;
        host::DrawableSize(sc->desc.window, &w, &h);
        extent = {uint32_t(std::max(w, 0)), uint32_t(std::max(h, 0))};
        extent.width = std::clamp(extent.width, caps.minImageExtent.width, caps.maxImageExtent.width);
        extent.height = std::clamp(extent.height, caps.minImageExtent.height, caps.maxImageExtent.height);
    }
    if (!extent.width || !extent.height)
        return false;
    uint32_t count = 0;
    vkGetPhysicalDeviceSurfaceFormatsKHR(s.physical, sc->surface, &count, nullptr);
    std::vector<VkSurfaceFormatKHR> formats(count);
    vkGetPhysicalDeviceSurfaceFormatsKHR(s.physical, sc->surface, &count, formats.data());
    if (formats.empty())
        return false;
    // UNORM, as the GL backend's window: the frame's values go to the screen as they are.
    VkSurfaceFormatKHR chosen = formats[0];
    for (const VkSurfaceFormatKHR &f : formats)
        if (f.format == VK_FORMAT_B8G8R8A8_UNORM || f.format == VK_FORMAT_R8G8B8A8_UNORM)
        {
            chosen = f;
            break;
        }
    vkGetPhysicalDeviceSurfacePresentModesKHR(s.physical, sc->surface, &count, nullptr);
    std::vector<VkPresentModeKHR> modes(count);
    vkGetPhysicalDeviceSurfacePresentModesKHR(s.physical, sc->surface, &count, modes.data());
    VkPresentModeKHR mode = VK_PRESENT_MODE_FIFO_KHR;
    if (!sc->desc.vsync)
        for (VkPresentModeKHR m : {VK_PRESENT_MODE_MAILBOX_KHR, VK_PRESENT_MODE_IMMEDIATE_KHR})
            if (std::find(modes.begin(), modes.end(), m) != modes.end())
            {
                mode = m;
                break;
            }
    VkSwapchainCreateInfoKHR info = {VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR};
    info.surface = sc->surface;
    info.minImageCount = caps.maxImageCount ? std::min(caps.minImageCount + 1, caps.maxImageCount)
                                            : caps.minImageCount + 1;
    info.imageFormat = chosen.format;
    info.imageColorSpace = chosen.colorSpace;
    info.imageExtent = extent;
    info.imageArrayLayers = 1;
    info.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    info.imageSharingMode = VK_SHARING_MODE_EXCLUSIVE;
    info.preTransform = caps.currentTransform;
    info.compositeAlpha = (caps.supportedCompositeAlpha & VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR)
                              ? VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR
                              : VkCompositeAlphaFlagBitsKHR(caps.supportedCompositeAlpha &
                                                            -caps.supportedCompositeAlpha);
    info.presentMode = mode;
    info.clipped = VK_TRUE;
    info.oldSwapchain = sc->swapchain;
    VkSwapchainKHR swapchain = VK_NULL_HANDLE;
    const bool made = Ok(vkCreateSwapchainKHR(s.device, &info, nullptr, &swapchain), "vkCreateSwapchainKHR");
    if (sc->swapchain)
    {
        // The old images may still be in a submitted frame.
        WaitSerial(s.submitted);
        FreeSwapchainImages(sc);
        vkDestroySwapchainKHR(s.device, sc->swapchain, nullptr);
        sc->swapchain = VK_NULL_HANDLE;
    }
    if (!made)
        return false;
    sc->swapchain = swapchain;
    sc->format = chosen.format;
    sc->extent = extent;
    vkGetSwapchainImagesKHR(s.device, swapchain, &count, nullptr);
    sc->images.resize(count);
    vkGetSwapchainImagesKHR(s.device, swapchain, &count, sc->images.data());
    for (VkImage image : sc->images)
    {
        VkImageViewCreateInfo view = {VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
        view.image = image;
        view.viewType = VK_IMAGE_VIEW_TYPE_2D;
        view.format = chosen.format;
        view.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
        VkImageView v = VK_NULL_HANDLE;
        vkCreateImageView(s.device, &view, nullptr, &v);
        sc->views.push_back(v);
        VkSemaphoreCreateInfo semaphore = {VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};
        VkSemaphore done = VK_NULL_HANDLE;
        vkCreateSemaphore(s.device, &semaphore, nullptr, &done);
        sc->renderDone.push_back(done);
    }
    if (sc->presentFormat != chosen.format)
    {
        if (sc->present)
            vkDestroyPipeline(s.device, sc->present, nullptr);
        sc->present = PresentPipeline(chosen.format);
        sc->presentFormat = chosen.format;
    }
    sc->stale = false;
    Log("vk: swapchain %ux%u, %zu images, %s", extent.width, extent.height, sc->images.size(),
        mode == VK_PRESENT_MODE_FIFO_KHR ? "vsync" : mode == VK_PRESENT_MODE_MAILBOX_KHR ? "mailbox" : "immediate");
    return true;
}

void ImageBarrier(VkCommandBuffer cmd, VkImage image, VkImageLayout from, VkImageLayout to, VkAccessFlags srcAccess,
                  VkAccessFlags dstAccess, VkPipelineStageFlags srcStage, VkPipelineStageFlags dstStage)
{
    VkImageMemoryBarrier barrier = {VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
    barrier.srcAccessMask = srcAccess;
    barrier.dstAccessMask = dstAccess;
    barrier.oldLayout = from;
    barrier.newLayout = to;
    barrier.srcQueueFamilyIndex = barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.image = image;
    barrier.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    vkCmdPipelineBarrier(cmd, srcStage, dstStage, 0, 0, nullptr, 0, nullptr, 1, &barrier);
}

void LogPerf()
{
    State &s = S();
    const auto now = std::chrono::steady_clock::now();
    const double seconds = std::chrono::duration<double>(now - s.perfStart).count();
    if (seconds < 10.0)
        return;
    VmaTotalStatistics stats = {};
    vmaCalculateStatistics(s.allocator, &stats);
    Log("vk perf: %.1f fps, %.0f draws a frame, %.1f flushes and %.1f suspended passes a frame, %llu renames, "
        "%llu new pipelines, %.1f MB in %u blocks",
        s.presented / seconds, s.presented ? double(s.draws) / double(s.presented) : 0.0,
        s.presented ? double(s.flushes) / double(s.presented) : 0.0,
        s.presented ? double(s.suspends) / double(s.presented) : 0.0,
        static_cast<unsigned long long>(s.renames), static_cast<unsigned long long>(s.newPipelines),
        double(stats.total.statistics.blockBytes) / double(1 << 20), stats.total.statistics.blockCount);
    s.perfStart = now;
    s.presented = s.draws = s.flushes = s.suspends = s.renames = s.newPipelines = 0;
}

VKAPI_ATTR VkBool32 VKAPI_CALL DebugMessage(VkDebugUtilsMessageSeverityFlagBitsEXT severity, VkDebugUtilsMessageTypeFlagsEXT,
                                const VkDebugUtilsMessengerCallbackDataEXT *data, void *)
{
    State &s = S();
    if (s.debugMessages++ < kMaxDebugMessages)
        Log("vk %s: %s", severity >= VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT ? "error" : "warning",
            data && data->pMessage ? data->pMessage : "?");
    else if (s.debugMessages == kMaxDebugMessages + 1)
        Log("vk: more validation messages, not logged");
    return VK_FALSE;
}

bool HasExtension(const std::vector<VkExtensionProperties> &list, const char *name)
{
    for (const VkExtensionProperties &e : list)
        if (!std::strcmp(e.extensionName, name))
            return true;
    return false;
}

Buffer *MakeBuffer(const BufferDesc &desc)
{
    Buffer *b = new Buffer();
    b->desc = desc;
    b->hostVisible = desc.usage == Usage::Dynamic || desc.memory == Memory::Shared;
    const VkBufferUsageFlags usage = desc.type == BufferType::Vertex ? VK_BUFFER_USAGE_VERTEX_BUFFER_BIT
                                                                     : VK_BUFFER_USAGE_INDEX_BUFFER_BIT;
    if (!MakeStore(&b->store, desc.size, usage | VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT, b->hostVisible))
    {
        delete b;
        return nullptr;
    }
    return b;
}
} // namespace

// ---- the contract

void Shutdown();

bool Init()
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    std::vector<std::string> hostExtensions;
    if (!host::Open(&hostExtensions))
        return false;
    if (volkInitialize() != VK_SUCCESS)
    {
        Log("vk: no Vulkan loader on this system");
        host::Close();
        return false;
    }
    if (volkGetInstanceVersion() < VK_API_VERSION_1_3)
    {
        Log("vk: the Vulkan loader is older than 1.3");
        host::Close();
        return false;
    }
    const bool debug = std::getenv("BO1_VK_DEBUG") && *std::getenv("BO1_VK_DEBUG") == '1';
    uint32_t count = 0;
    vkEnumerateInstanceExtensionProperties(nullptr, &count, nullptr);
    std::vector<VkExtensionProperties> instanceExtensions(count);
    vkEnumerateInstanceExtensionProperties(nullptr, &count, instanceExtensions.data());
    std::vector<const char *> extensions;
    for (const std::string &e : hostExtensions)
        extensions.push_back(e.c_str());
    s.surfaces = !hostExtensions.empty();
    const bool debugUtils = debug && HasExtension(instanceExtensions, VK_EXT_DEBUG_UTILS_EXTENSION_NAME);
    if (debugUtils)
        extensions.push_back(VK_EXT_DEBUG_UTILS_EXTENSION_NAME);
    std::vector<const char *> layers;
    if (debug)
    {
        vkEnumerateInstanceLayerProperties(&count, nullptr);
        std::vector<VkLayerProperties> available(count);
        vkEnumerateInstanceLayerProperties(&count, available.data());
        for (const VkLayerProperties &l : available)
            if (!std::strcmp(l.layerName, "VK_LAYER_KHRONOS_validation"))
                layers.push_back("VK_LAYER_KHRONOS_validation");
        Log("vk: BO1_VK_DEBUG=1: validation %s", layers.empty() ? "layer not installed" : "on");
    }
    VkApplicationInfo app = {VK_STRUCTURE_TYPE_APPLICATION_INFO};
    app.pApplicationName = "BO1Zombies";
    app.pEngineName = "BO1Zombies";
    app.apiVersion = VK_API_VERSION_1_3;
    VkInstanceCreateInfo instanceInfo = {VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    instanceInfo.pApplicationInfo = &app;
    instanceInfo.enabledExtensionCount = uint32_t(extensions.size());
    instanceInfo.ppEnabledExtensionNames = extensions.data();
    instanceInfo.enabledLayerCount = uint32_t(layers.size());
    instanceInfo.ppEnabledLayerNames = layers.data();
    if (!Ok(vkCreateInstance(&instanceInfo, nullptr, &s.instance), "vkCreateInstance"))
    {
        host::Close();
        return false;
    }
    volkLoadInstance(s.instance);
    if (debugUtils)
    {
        VkDebugUtilsMessengerCreateInfoEXT messenger = {VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT};
        messenger.messageSeverity =
            VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT;
        messenger.messageType = VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT |
                                VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT |
                                VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT;
        messenger.pfnUserCallback = DebugMessage;
        if (Ok(vkCreateDebugUtilsMessengerEXT(s.instance, &messenger, nullptr, &s.messenger),
               "vkCreateDebugUtilsMessengerEXT"))
            Log("vk: validation messages go to the log (the first %d)", kMaxDebugMessages);
    }

    // The device: Vulkan 1.3, a graphics queue, push descriptors. A discrete GPU first, then an integrated one.
    vkEnumeratePhysicalDevices(s.instance, &count, nullptr);
    std::vector<VkPhysicalDevice> devices(count);
    vkEnumeratePhysicalDevices(s.instance, &count, devices.data());
    int bestScore = -1;
    for (VkPhysicalDevice device : devices)
    {
        VkPhysicalDeviceProperties p;
        vkGetPhysicalDeviceProperties(device, &p);
        uint32_t extensionCount = 0;
        vkEnumerateDeviceExtensionProperties(device, nullptr, &extensionCount, nullptr);
        std::vector<VkExtensionProperties> deviceExtensions(extensionCount);
        vkEnumerateDeviceExtensionProperties(device, nullptr, &extensionCount, deviceExtensions.data());
        uint32_t families = 0;
        vkGetPhysicalDeviceQueueFamilyProperties(device, &families, nullptr);
        std::vector<VkQueueFamilyProperties> family(families);
        vkGetPhysicalDeviceQueueFamilyProperties(device, &families, family.data());
        int graphics = -1;
        for (uint32_t i = 0; i < families && graphics < 0; ++i)
            if (family[i].queueFlags & VK_QUEUE_GRAPHICS_BIT)
                graphics = int(i);
        const bool usable = p.apiVersion >= VK_API_VERSION_1_3 && graphics >= 0 &&
                            HasExtension(deviceExtensions, VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME) &&
                            (!s.surfaces || HasExtension(deviceExtensions, VK_KHR_SWAPCHAIN_EXTENSION_NAME));
        Log("vk: device %s (Vulkan %u.%u)%s", p.deviceName, VK_API_VERSION_MAJOR(p.apiVersion),
            VK_API_VERSION_MINOR(p.apiVersion), usable ? "" : ": not usable (needs 1.3 and push descriptors)");
        if (!usable)
            continue;
        const int score = p.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU     ? 3
                          : p.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU ? 2
                                                                                   : 1;
        if (score > bestScore)
        {
            bestScore = score;
            s.physical = device;
            s.properties = p;
            s.family = uint32_t(graphics);
            s.timestamps = family[graphics].timestampValidBits != 0;
        }
    }
    if (!s.physical)
    {
        Log("vk: no usable Vulkan device");
        Shutdown();
        return false;
    }
    s.timestampPeriod = s.properties.limits.timestampPeriod;

    VkPhysicalDeviceVulkan12Features have12 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES};
    VkPhysicalDeviceVulkan13Features have13 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES};
    have12.pNext = &have13;
    VkPhysicalDeviceFeatures2 have = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};
    have.pNext = &have12;
    vkGetPhysicalDeviceFeatures2(s.physical, &have);
    if (!have12.timelineSemaphore || !have12.hostQueryReset || !have13.dynamicRendering)
    {
        Log("vk: the device lacks timeline semaphores, host query reset or dynamic rendering");
        Shutdown();
        return false;
    }
    VkPhysicalDeviceVulkan12Features want12 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES};
    want12.timelineSemaphore = VK_TRUE;
    want12.hostQueryReset = VK_TRUE;
    want12.samplerMirrorClampToEdge = have12.samplerMirrorClampToEdge;
    VkPhysicalDeviceVulkan13Features want13 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES};
    want13.dynamicRendering = VK_TRUE;
    want12.pNext = &want13;
    VkPhysicalDeviceFeatures2 want = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};
    want.pNext = &want12;
    want.features.samplerAnisotropy = have.features.samplerAnisotropy;
    want.features.fillModeNonSolid = have.features.fillModeNonSolid;
    want.features.textureCompressionBC = have.features.textureCompressionBC;
    want.features.occlusionQueryPrecise = VK_FALSE;
    s.anisotropy = have.features.samplerAnisotropy;
    s.wireframe = have.features.fillModeNonSolid;
    s.mirrorClamp = have12.samplerMirrorClampToEdge;

    const float priority = 1.0f;
    VkDeviceQueueCreateInfo queueInfo = {VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    queueInfo.queueFamilyIndex = s.family;
    queueInfo.queueCount = 1;
    queueInfo.pQueuePriorities = &priority;
    std::vector<const char *> deviceExtensions = {VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME};
    if (s.surfaces)
        deviceExtensions.push_back(VK_KHR_SWAPCHAIN_EXTENSION_NAME);
    VkDeviceCreateInfo deviceInfo = {VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
    deviceInfo.pNext = &want;
    deviceInfo.queueCreateInfoCount = 1;
    deviceInfo.pQueueCreateInfos = &queueInfo;
    deviceInfo.enabledExtensionCount = uint32_t(deviceExtensions.size());
    deviceInfo.ppEnabledExtensionNames = deviceExtensions.data();
    if (!Ok(vkCreateDevice(s.physical, &deviceInfo, nullptr, &s.device), "vkCreateDevice"))
    {
        Shutdown();
        return false;
    }
    volkLoadDevice(s.device);
    vkGetDeviceQueue(s.device, s.family, 0, &s.queue);

    VmaVulkanFunctions functions = {};
    functions.vkGetInstanceProcAddr = vkGetInstanceProcAddr;
    functions.vkGetDeviceProcAddr = vkGetDeviceProcAddr;
    VmaAllocatorCreateInfo allocator = {};
    allocator.vulkanApiVersion = VK_API_VERSION_1_3;
    allocator.physicalDevice = s.physical;
    allocator.device = s.device;
    allocator.instance = s.instance;
    allocator.pVulkanFunctions = &functions;
    if (!Ok(vmaCreateAllocator(&allocator, &s.allocator), "vmaCreateAllocator"))
    {
        Shutdown();
        return false;
    }

    VkSemaphoreTypeCreateInfo timelineType = {VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO};
    timelineType.semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE;
    VkSemaphoreCreateInfo semaphore = {VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};
    semaphore.pNext = &timelineType;
    vkCreateSemaphore(s.device, &semaphore, nullptr, &s.timeline);

    // One pipeline layout for every draw: samplers 0-15, the constant blocks at 16 and 17, pushed per draw.
    VkDescriptorSetLayoutBinding bindings[kSamplerBindings + 2];
    for (uint32_t b = 0; b < kSamplerBindings; ++b)
        bindings[b] = {b, VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1,
                       VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT, nullptr};
    bindings[kSamplerBindings] = {BINDING_VERTEX_CONSTANTS, VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1,
                                  VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT, nullptr};
    bindings[kSamplerBindings + 1] = {BINDING_PIXEL_CONSTANTS, VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1,
                                      VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT, nullptr};
    VkDescriptorSetLayoutCreateInfo setInfo = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    setInfo.flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR;
    setInfo.bindingCount = kSamplerBindings + 2;
    setInfo.pBindings = bindings;
    vkCreateDescriptorSetLayout(s.device, &setInfo, nullptr, &s.setLayout);
    VkPipelineLayoutCreateInfo layoutInfo = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
    layoutInfo.setLayoutCount = 1;
    layoutInfo.pSetLayouts = &s.setLayout;
    vkCreatePipelineLayout(s.device, &layoutInfo, nullptr, &s.layout);
    VkPipelineCacheCreateInfo cacheInfo = {VK_STRUCTURE_TYPE_PIPELINE_CACHE_CREATE_INFO};
    vkCreatePipelineCache(s.device, &cacheInfo, nullptr, &s.cache);

    for (FrameSlot &f : s.frames)
    {
        VkCommandPoolCreateInfo pool = {VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
        pool.flags = VK_COMMAND_POOL_CREATE_TRANSIENT_BIT;
        pool.queueFamilyIndex = s.family;
        vkCreateCommandPool(s.device, &pool, nullptr, &f.pool);
        VkQueryPoolCreateInfo queries = {VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO};
        queries.queryType = VK_QUERY_TYPE_OCCLUSION;
        queries.queryCount = kQueriesPerFrame;
        vkCreateQueryPool(s.device, &queries, nullptr, &f.occlusion);
        vkResetQueryPool(s.device, f.occlusion, 0, kQueriesPerFrame);
        if (s.timestamps)
        {
            queries.queryType = VK_QUERY_TYPE_TIMESTAMP;
            vkCreateQueryPool(s.device, &queries, nullptr, &f.timestamps);
            vkResetQueryPool(s.device, f.timestamps, 0, kQueriesPerFrame);
        }
        VkSemaphoreCreateInfo binary = {VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};
        vkCreateSemaphore(s.device, &binary, nullptr, &f.acquire);
    }

    // Caps.
    s.deviceName = std::string(s.properties.deviceName) + " (Vulkan " +
                   std::to_string(VK_API_VERSION_MAJOR(s.properties.apiVersion)) + "." +
                   std::to_string(VK_API_VERSION_MINOR(s.properties.apiVersion)) + "." +
                   std::to_string(VK_API_VERSION_PATCH(s.properties.apiVersion)) + ")";
    VkFormatProperties d24 = {};
    vkGetPhysicalDeviceFormatProperties(s.physical, VK_FORMAT_D24_UNORM_S8_UINT, &d24);
    s_depthStencilFormat = (d24.optimalTilingFeatures & VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT)
                               ? VK_FORMAT_D24_UNORM_S8_UINT
                               : VK_FORMAT_D32_SFLOAT_S8_UINT;
    s.caps.device = s.deviceName.c_str();
    s.caps.maxTextureSize = uint16_t(std::min<uint32_t>(s.properties.limits.maxImageDimension2D, 16384));
    const VkSampleCountFlags samples =
        s.properties.limits.framebufferColorSampleCounts & s.properties.limits.framebufferDepthSampleCounts;
    s.caps.maxSamples = samples & VK_SAMPLE_COUNT_8_BIT ? 8 : samples & VK_SAMPLE_COUNT_4_BIT ? 4
                        : samples & VK_SAMPLE_COUNT_2_BIT ? 2 : 1;
    VkPhysicalDeviceMemoryProperties memory;
    vkGetPhysicalDeviceMemoryProperties(s.physical, &memory);
    for (uint32_t i = 0; i < memory.memoryHeapCount; ++i)
        if (memory.memoryHeaps[i].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT)
            s.caps.memoryBytes = std::max<uint64_t>(s.caps.memoryBytes, memory.memoryHeaps[i].size);
    for (int f = 1; f < int(Format::Count); ++f)
        s.caps.formatFlags[f] = FormatFlags(Format(f));
    if (!have.features.textureCompressionBC)
        for (Format f : {Format::BC1, Format::BC2, Format::BC3})
            s.caps.formatFlags[int(f)] = 0;

    // What draws bind where the frontend binds nothing, and Present's own shaders.
    s.presentVertex = MakeModule(shaders::kSpirvPresentVs, sizeof(shaders::kSpirvPresentVs));
    s.presentPixel = MakeModule(shaders::kSpirvPresentFs, sizeof(shaders::kSpirvPresentFs));
    s.dummySampler = MakeSampler(SamplerDesc{});
    SamplerDesc shadow;
    shadow.depthCompare = true;
    s.dummyShadowSampler = MakeSampler(shadow);
    SamplerDesc linearClamp;
    linearClamp.mipFilter = MipFilter::None;
    linearClamp.addressU = linearClamp.addressV = linearClamp.addressW = Address::Clamp;
    s.presentSampler = MakeSampler(linearClamp);
    SamplerDesc nearestClamp = linearClamp;
    nearestClamp.magFilter = nearestClamp.minFilter = Filter::Nearest;
    s.rampSampler = MakeSampler(nearestClamp);
    const uint8_t black[4 * 6] = {0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255};
    for (int kind = 0; kind < 4; ++kind)
    {
        TextureDesc d = {};
        d.type = kind == int(ImageKind::Tex3D) ? TextureType::Tex3D
                 : kind == int(ImageKind::Cube) ? TextureType::Cube
                                                : TextureType::Tex2D;
        d.format = kind == int(ImageKind::Shadow2D) ? Format::D16 : Format::RGBA8;
        d.usage = kind == int(ImageKind::Shadow2D) ? Usage::DepthStencil : Usage::Static;
        d.sampled = true;
        d.width = d.height = d.depth = 1;
        d.levels = d.samples = 1;
        s.dummy[kind] = MakeTexture(d);
        if (!s.dummy[kind])
            continue;
        if (kind == int(ImageKind::Shadow2D))
        {
            // Depth 1: a shadow test against it passes, as an unbound shadow map reads in D3D9 drivers.
            VkClearDepthStencilValue one = {1.0f, 0};
            VkImageSubresourceRange range = {VK_IMAGE_ASPECT_DEPTH_BIT, 0, 1, 0, 1};
            vkCmdClearDepthStencilImage(Setup(), s.dummy[kind]->image, VK_IMAGE_LAYOUT_GENERAL, &one, 1, &range);
        }
        else
            for (uint8_t layer = 0; layer < s.dummy[kind]->layers; ++layer)
                Upload2D(s.dummy[kind], 0, layer, {0, 0, 0, 1, 1, 1}, black, 4, 4);
    }
    s.dummyVertices = MakeBuffer({BufferType::Vertex, Usage::Static, Memory::Device, 16});
    if (s.dummyVertices)
    {
        const float zeroOne[4] = {0.0f, 0.0f, 0.0f, 1.0f};
        Staged staged;
        if (StageBytes(sizeof(zeroOne), &staged))
        {
            std::memcpy(staged.data, zeroOne, sizeof(zeroOne));
            const VkBufferCopy region = {staged.offset, 0, sizeof(zeroOne)};
            vkCmdCopyBuffer(Setup(), staged.buffer, s.dummyVertices->store.buffer, 1, &region);
        }
    }
    s.initialized = true;
    Log("vk: %s, %s depth-stencil, %s", s.deviceName.c_str(),
        s_depthStencilFormat == VK_FORMAT_D24_UNORM_S8_UINT ? "D24S8" : "D32FS8",
        s.timestamps ? "GPU timestamps" : "CPU timestamps");
    return true;
}

void Shutdown()
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    if (s.device)
    {
        if (s.frameOpen)
        {
            Submit();
            s.frameOpen = false;
        }
        vkDeviceWaitIdle(s.device);
        s.completed = s.submitted;
        for (Deferred &d : s.deferred)
            d.destroy();
        s.deferred.clear();
        for (Texture *&t : s.dummy)
            if (t)
                FreeTexture(t);
        for (Texture *&t : s.dummy)
            t = nullptr;
        if (s.dummyVertices)
        {
            FreeStore(s.dummyVertices->store);
            delete s.dummyVertices;
            s.dummyVertices = nullptr;
        }
        FreeStore(s.readback.store);
        s.readbackSize = 0;
        for (auto &[key, p] : s.pipelines)
            FreePipeline(p);
        s.pipelines.clear();
        for (auto &[key, sampler] : s.samplers)
        {
            vkDestroySampler(s.device, sampler->sampler, nullptr);
            delete sampler;
        }
        s.samplers.clear();
        for (FrameSlot &f : s.frames)
        {
            for (UniformBlock &u : f.uniforms)
            {
                FreeStore(u.buffer->store);
                delete u.buffer;
            }
            for (StagingChunk &c : f.staging)
                FreeStore(c.store);
            f.uniforms.clear();
            f.staging.clear();
            if (f.occlusion)
                vkDestroyQueryPool(s.device, f.occlusion, nullptr);
            if (f.timestamps)
                vkDestroyQueryPool(s.device, f.timestamps, nullptr);
            if (f.pool)
                vkDestroyCommandPool(s.device, f.pool, nullptr);
            if (f.acquire)
                vkDestroySemaphore(s.device, f.acquire, nullptr);
            f = FrameSlot();
        }
        if (s.presentVertex)
            vkDestroyShaderModule(s.device, s.presentVertex, nullptr);
        if (s.presentPixel)
            vkDestroyShaderModule(s.device, s.presentPixel, nullptr);
        if (s.cache)
            vkDestroyPipelineCache(s.device, s.cache, nullptr);
        if (s.layout)
            vkDestroyPipelineLayout(s.device, s.layout, nullptr);
        if (s.setLayout)
            vkDestroyDescriptorSetLayout(s.device, s.setLayout, nullptr);
        if (s.timeline)
            vkDestroySemaphore(s.device, s.timeline, nullptr);
        if (s.allocator)
            vmaDestroyAllocator(s.allocator);
        vkDestroyDevice(s.device, nullptr);
    }
    if (s.messenger)
        vkDestroyDebugUtilsMessengerEXT(s.instance, s.messenger, nullptr);
    if (s.instance)
        vkDestroyInstance(s.instance, nullptr);
    if (s.instance)
        host::Close();
    // A fresh state for a later Init.
    s.instance = VK_NULL_HANDLE;
    s.messenger = VK_NULL_HANDLE;
    s.device = VK_NULL_HANDLE;
    s.physical = VK_NULL_HANDLE;
    s.allocator = VK_NULL_HANDLE;
    s.timeline = VK_NULL_HANDLE;
    s.setLayout = VK_NULL_HANDLE;
    s.layout = VK_NULL_HANDLE;
    s.cache = VK_NULL_HANDLE;
    s.presentVertex = s.presentPixel = VK_NULL_HANDLE;
    s.submitted = s.completed = 0;
    s.frameOpen = false;
    s.setup = s.cmd = VK_NULL_HANDLE;
    s.rendering = false;
    s.initialized = false;
}

const Caps &GetCaps()
{
    return S().caps;
}

const char *Name()
{
    return "vulkan";
}

gb::Buffer *CreateBuffer(const BufferDesc &desc)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    return MakeBuffer(desc);
}

gb::Texture *CreateTexture(const TextureDesc &desc)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    return MakeTexture(desc);
}

void DestroyBuffer(gb::Buffer *handle)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    Buffer *b = static_cast<Buffer *>(handle);
    if (!b)
        return;
    DeferFreeStore(b->store);
    for (const Store &store : b->spare)
        DeferFreeStore(store);
    delete b;
}

void DestroyTexture(gb::Texture *handle)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    Texture *t = static_cast<Texture *>(handle);
    if (t)
        Defer([t]() { FreeTexture(t); });
}

void UploadBuffer(gb::Buffer *handle, uint32_t offset, const void *data, uint32_t size, Upload mode)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Buffer *b = static_cast<Buffer *>(handle);
    if (!b || !data || !size || uint64_t(offset) + size > b->desc.size)
        return;
    BeginFrame();
    if (b->hostVisible)
    {
        const bool inUse = b->store.lastUse > Completed();
        if (mode == Upload::NoOverwrite || !inUse)
        {
            std::memcpy(b->store.mapped + offset, data, size);
            return;
        }
        if (mode == Upload::Discard)
        {
            // Rename: a store the GPU is done with, else a new one; the old one waits in `spare`.
            Store next;
            for (size_t i = 0; i < b->spare.size(); ++i)
                if (b->spare[i].lastUse <= s.completed)
                {
                    next = b->spare[i];
                    b->spare.erase(b->spare.begin() + long(i));
                    break;
                }
            if (!next.buffer && !MakeStore(&next, b->desc.size,
                                           (b->desc.type == BufferType::Vertex ? VK_BUFFER_USAGE_VERTEX_BUFFER_BIT
                                                                                : VK_BUFFER_USAGE_INDEX_BUFFER_BIT) |
                                               VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,
                                           true))
                return;
            b->spare.push_back(b->store);
            if (b->spare.size() > 8)
            {
                DeferFreeStore(b->spare.front());
                b->spare.erase(b->spare.begin());
            }
            b->store = next;
            ++s.renames;
            std::memcpy(b->store.mapped + offset, data, size);
            return;
        }
    }
    // In order with the recorded work: a copy from staging memory.
    Staged staged;
    if (!StageBytes(size, &staged))
        return;
    std::memcpy(staged.data, data, size);
    const UploadTarget target = BeginUpload(b->store.lastUse);
    const VkBufferCopy region = {staged.offset, offset, size};
    vkCmdCopyBuffer(target.cmd, staged.buffer, b->store.buffer, 1, &region);
    EndUpload(target);
    b->store.lastUse = std::max(b->store.lastUse, Pending());
}

void UploadTexture(gb::Texture *handle, uint8_t level, uint8_t layer, const Box &box, const void *data,
                   uint32_t rowPitch, uint32_t slicePitch)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    Texture *t = static_cast<Texture *>(handle);
    if (!t || !data || t->desc.samples > 1 || IsDepthFormat(t->desc.format))
        return;
    Upload2D(t, level, layer, box, data, rowPitch, slicePitch);
    t->lastUse = std::max(t->lastUse, Pending());
}

const gb::Sampler *GetSampler(const SamplerDesc &desc)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    return MakeSampler(desc);
}

gb::Shader *CreateShader(Stage stage, uint64_t hash, const char *code, uint32_t size)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    Shader *shader = new Shader();
    shader->stage = stage;
    shader->hash = hash;
    std::vector<uint32_t> words((size + 3) / 4);
    std::memcpy(words.data(), code, size);
    if (!Reflect(words.data(), words.size(), &shader->reflection))
    {
        static int logged = 0;
        if (logged++ < 4)
            Log("vk: shader %016llx is not SPIR-V (is shaders.spv there?): its pipelines will not build",
                static_cast<unsigned long long>(hash));
    }
    else
        shader->module = MakeModule(code, size);
    return shader;
}

void DestroyShader(gb::Shader *handle)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Shader *shader = static_cast<Shader *>(handle);
    if (!shader)
        return;
    for (Pipeline *p : shader->pipelines)
    {
        s.pipelines.erase(p->key);
        // The pipeline's other shader forgets it too.
        for (const gb::Shader *other : {p->desc.vertex, p->desc.pixel})
            if (other != shader)
            {
                auto &list = static_cast<Shader *>(const_cast<gb::Shader *>(other))->pipelines;
                list.erase(std::remove(list.begin(), list.end(), p), list.end());
            }
        Defer([p]() { FreePipeline(p); });
    }
    const VkShaderModule module = shader->module;
    if (module)
        Defer([module]() { vkDestroyShaderModule(S().device, module, nullptr); });
    delete shader;
}

const gb::Pipeline *GetPipeline(const PipelineDesc &desc)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    std::string key = PipelineKey(desc);
    const auto found = s.pipelines.find(key);
    if (found != s.pipelines.end())
        return found->second->pipeline ? found->second : nullptr;
    Shader *vertex = static_cast<Shader *>(const_cast<gb::Shader *>(desc.vertex));
    Shader *pixel = static_cast<Shader *>(const_cast<gb::Shader *>(desc.pixel));
    if (!vertex || !pixel)
        return nullptr;
    Pipeline *p = new Pipeline();
    p->desc = desc;
    p->key = key;
    p->samplers = vertex->reflection.samplers | pixel->reflection.samplers;
    for (uint32_t b = 0; b < kSamplerBindings; ++b)
        p->kinds[b] = (pixel->reflection.samplers & (1u << b)) ? pixel->reflection.kinds[b] : vertex->reflection.kinds[b];
    if (vertex->module && pixel->module)
        p->pipeline = BuildPipeline(p, vertex, pixel);
    s.pipelines[key] = p;
    vertex->pipelines.push_back(p);
    if (pixel != vertex)
        pixel->pipelines.push_back(p);
    return p->pipeline ? p : nullptr;
}

void BeginPass(const PassDesc &desc)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    if (s.rendering)
        SuspendRendering();
    uint32_t width = ~0u, height = ~0u;
    for (int i = 0; i < desc.colorCount; ++i)
    {
        const Texture *t = static_cast<const Texture *>(desc.color[i].texture);
        width = std::min(width, LevelExtent(t->desc.width, desc.color[i].level));
        height = std::min(height, LevelExtent(t->desc.height, desc.color[i].level));
    }
    if (const Texture *z = static_cast<const Texture *>(desc.depth))
    {
        width = std::min<uint32_t>(width, z->desc.width);
        height = std::min<uint32_t>(height, z->desc.height);
    }
    if (width == ~0u)
        width = height = 0;
    s.pass = desc;
    s.passArea = {{0, 0}, {width, height}};
    BeginRendering(desc, false);
}

void EndPass()
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    if (s.rendering)
        vkCmdEndRendering(s.cmd);
    s.rendering = false;
    s.pass = {};
}

void Clear(const Rect *rects, uint32_t count, bool color, bool depth, bool stencil, const float rgba[4],
           float depthValue, uint8_t stencilValue)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    if (!s.rendering || !count)
        return;
    VkClearAttachment attachments[MAX_COLOR_TARGETS + 1];
    uint32_t n = 0;
    if (color)
        for (uint32_t i = 0; i < s.pass.colorCount; ++i)
        {
            attachments[n] = {VK_IMAGE_ASPECT_COLOR_BIT, i, {}};
            std::memcpy(attachments[n].clearValue.color.float32, rgba, sizeof(float) * 4);
            if (static_cast<const Texture *>(s.pass.color[i].texture)->desc.format == Format::BGRX8)
                attachments[n].clearValue.color.float32[3] = 1.0f;
            ++n;
        }
    const Texture *z = static_cast<const Texture *>(s.pass.depth);
    VkImageAspectFlags aspects = 0;
    if (z && depth)
        aspects |= VK_IMAGE_ASPECT_DEPTH_BIT;
    if (z && stencil && HasStencil(z->desc.format))
        aspects |= VK_IMAGE_ASPECT_STENCIL_BIT;
    if (aspects)
    {
        attachments[n] = {aspects, 0, {}};
        attachments[n].clearValue.depthStencil = {depthValue, stencilValue};
        ++n;
    }
    if (!n)
        return;
    std::vector<VkClearRect> clears;
    const int32_t areaW = int32_t(s.passArea.extent.width), areaH = int32_t(s.passArea.extent.height);
    for (uint32_t i = 0; i < count; ++i)
    {
        const int32_t x0 = std::max(rects[i].x, 0), y0 = std::max(rects[i].y, 0);
        const int32_t x1 = std::min(rects[i].x + int32_t(rects[i].width), areaW);
        const int32_t y1 = std::min(rects[i].y + int32_t(rects[i].height), areaH);
        if (x1 > x0 && y1 > y0)
            clears.push_back({{{x0, y0}, {uint32_t(x1 - x0), uint32_t(y1 - y0)}}, 0, 1});
    }
    if (!clears.empty())
        vkCmdClearAttachments(s.cmd, n, attachments, uint32_t(clears.size()), clears.data());
}

UniformSlice AllocUniforms(const void *data, uint32_t size)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    BeginFrame();
    FrameSlot &f = s.frames[s.frame];
    const uint32_t align = uint32_t(std::max<VkDeviceSize>(s.properties.limits.minUniformBufferOffsetAlignment, 16));
    if (size > kUniformBlockBytes)
        return {};
    uint32_t at = (f.uniformOffset + align - 1) / align * align;
    if (f.uniformBlock < f.uniforms.size() && at + size > kUniformBlockBytes)
    {
        ++f.uniformBlock;
        at = 0;
    }
    if (f.uniformBlock == f.uniforms.size())
    {
        Buffer *b = new Buffer();
        b->desc = {BufferType::Vertex, Usage::Dynamic, Memory::Shared, kUniformBlockBytes};
        b->hostVisible = true;
        if (!MakeStore(&b->store, kUniformBlockBytes, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT, true))
        {
            delete b;
            return {};
        }
        f.uniforms.push_back({b});
        at = 0;
    }
    Buffer *block = f.uniforms[f.uniformBlock].buffer;
    std::memcpy(block->store.mapped + at, data, size);
    f.uniformOffset = at + size;
    return {block, at, size};
}

void DoDraw(const DrawState &state, Primitive primitive, uint32_t count, uint32_t first, bool indexed,
            int32_t baseVertex)
{
    State &s = S();
    const Pipeline *p = static_cast<const Pipeline *>(state.pipeline);
    if (!s.rendering || !p || !p->pipeline || !count)
        return;
    VkCommandBuffer cmd = s.cmd;
    if (s.bound != p)
    {
        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, p->pipeline);
        s.bound = p;
    }
    const Viewport &v = state.viewport;
    const VkViewport viewport = {v.x, v.y + v.height, v.width, -v.height, v.minDepth, v.maxDepth};
    vkCmdSetViewport(cmd, 0, 1, &viewport);
    VkRect2D scissor = s.passArea;
    if (p->desc.raster.scissor)
    {
        const int32_t x0 = std::max(state.scissor.x, 0), y0 = std::max(state.scissor.y, 0);
        const int32_t x1 = std::min(state.scissor.x + int32_t(state.scissor.width), int32_t(s.passArea.extent.width));
        const int32_t y1 = std::min(state.scissor.y + int32_t(state.scissor.height), int32_t(s.passArea.extent.height));
        scissor = {{x0, y0}, {uint32_t(std::max(x1 - x0, 0)), uint32_t(std::max(y1 - y0, 0))}};
    }
    vkCmdSetScissor(cmd, 0, 1, &scissor);
    vkCmdSetStencilReference(cmd, VK_STENCIL_FACE_FRONT_AND_BACK, state.stencilRef);
    vkCmdSetBlendConstants(cmd, state.blendConstant);
    vkCmdSetPrimitiveTopology(cmd, MapPrimitive(primitive));

    VkBuffer buffers[MAX_STREAMS + 1];
    VkDeviceSize offsets[MAX_STREAMS + 1], strides[MAX_STREAMS + 1];
    const uint32_t bindings = p->dummyStream ? kDummyStream + 1 : 32 - uint32_t(std::countl_zero(uint32_t(p->streams | 1)));
    for (uint32_t b = 0; b < bindings; ++b)
    {
        const Buffer *vb = b < MAX_STREAMS ? static_cast<const Buffer *>(state.vertices[b].buffer) : nullptr;
        if ((p->streams & (1u << b)) && vb)
        {
            buffers[b] = vb->store.buffer;
            offsets[b] = state.vertices[b].offset;
            strides[b] = state.vertices[b].stride;
            const_cast<Buffer *>(vb)->store.lastUse = Pending();
        }
        else
        {
            buffers[b] = s.dummyVertices->store.buffer;
            offsets[b] = 0;
            strides[b] = 0;
        }
    }
    if (p->streams || p->dummyStream)
        vkCmdBindVertexBuffers2(cmd, 0, bindings, buffers, offsets, nullptr, strides);
    if (indexed)
    {
        const Buffer *ib = static_cast<const Buffer *>(state.indices);
        if (!ib)
            return;
        vkCmdBindIndexBuffer(cmd, ib->store.buffer, 0,
                             ib->desc.type == BufferType::Index32 ? VK_INDEX_TYPE_UINT32 : VK_INDEX_TYPE_UINT16);
        const_cast<Buffer *>(ib)->store.lastUse = Pending();
    }

    VkWriteDescriptorSet writes[kSamplerBindings + 2];
    VkDescriptorImageInfo images[kSamplerBindings];
    VkDescriptorBufferInfo constants[2];
    uint32_t n = 0;
    const UniformSlice slices[2] = {state.vertexConstants, state.pixelConstants};
    for (int i = 0; i < 2; ++i)
    {
        const Buffer *ub = static_cast<const Buffer *>(slices[i].buffer);
        if (!ub)
            continue;
        constants[i] = {ub->store.buffer, slices[i].offset, slices[i].size};
        writes[n] = {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
        writes[n].dstBinding = i == 0 ? BINDING_VERTEX_CONSTANTS : BINDING_PIXEL_CONSTANTS;
        writes[n].descriptorCount = 1;
        writes[n].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
        writes[n].pBufferInfo = &constants[i];
        ++n;
    }
    for (uint32_t b = 0; b < kSamplerBindings; ++b)
    {
        if (!(p->samplers & (1u << b)))
            continue;
        Texture *t = static_cast<Texture *>(const_cast<gb::Texture *>(state.textures[b].texture));
        const Sampler *sampler = static_cast<const Sampler *>(state.textures[b].sampler);
        if (!t || !t->sampledView)
        {
            t = s.dummy[int(p->kinds[b])];
            sampler = static_cast<const Sampler *>(p->kinds[b] == ImageKind::Shadow2D ? s.dummyShadowSampler
                                                                                       : s.dummySampler);
        }
        if (!t)
            continue;
        if (!sampler)
            sampler = static_cast<const Sampler *>(s.dummySampler);
        t->lastUse = Pending();
        images[b] = {sampler->sampler, t->sampledView, VK_IMAGE_LAYOUT_GENERAL};
        writes[n] = {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
        writes[n].dstBinding = b;
        writes[n].descriptorCount = 1;
        writes[n].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
        writes[n].pImageInfo = &images[b];
        ++n;
    }
    if (n)
        vkCmdPushDescriptorSetKHR(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, s.layout, 0, n, writes);
    if (indexed)
        vkCmdDrawIndexed(cmd, count, 1, first, baseVertex, 0);
    else
        vkCmdDraw(cmd, count, 1, first, 0);
    ++s.draws;
}

void Draw(const DrawState &state, Primitive primitive, uint32_t vertexCount, uint32_t firstVertex)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    DoDraw(state, primitive, vertexCount, firstVertex, false, 0);
}

void DrawIndexed(const DrawState &state, Primitive primitive, uint32_t indexCount, uint32_t firstIndex,
                 int32_t baseVertex)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    DoDraw(state, primitive, indexCount, firstIndex, true, baseVertex);
}

void Blit(gb::Texture *srcHandle, uint8_t srcLevel, uint8_t srcLayer, const Rect &srcRect, gb::Texture *dstHandle,
          uint8_t dstLevel, uint8_t dstLayer, const Rect &dstRect, Filter filter)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Texture *src = static_cast<Texture *>(srcHandle), *dst = static_cast<Texture *>(dstHandle);
    if (!src || !dst || !srcRect.width || !srcRect.height || !dstRect.width || !dstRect.height)
        return;
    VkCommandBuffer cmd = Cmd();
    if (s.rendering)
        SuspendRendering();
    FullBarrier(cmd);
    MarkTexture(src);
    MarkTexture(dst);
    const bool depth = IsDepthFormat(src->desc.format);
    const VkImageAspectFlags aspect = AttachmentAspect(src->desc.format);
    const bool sameSize = srcRect.width == dstRect.width && srcRect.height == dstRect.height;
    const VkImageSubresourceLayers from = {aspect, srcLevel, src->desc.type == TextureType::Cube ? srcLayer : 0u, 1};
    const VkImageSubresourceLayers to = {aspect, dstLevel, dst->desc.type == TextureType::Cube ? dstLayer : 0u, 1};
    const VkOffset3D srcOffset = {srcRect.x, srcRect.y, src->desc.type == TextureType::Tex3D ? int32_t(srcLayer) : 0};
    const VkOffset3D dstOffset = {dstRect.x, dstRect.y, dst->desc.type == TextureType::Tex3D ? int32_t(dstLayer) : 0};
    if (src->desc.samples > 1 && sameSize && src->format == dst->format)
    {
        const VkImageResolve region = {from, srcOffset, to, dstOffset, {srcRect.width, srcRect.height, 1}};
        vkCmdResolveImage(cmd, src->image, VK_IMAGE_LAYOUT_GENERAL, dst->image, VK_IMAGE_LAYOUT_GENERAL, 1, &region);
    }
    else if (src->desc.samples > 1)
        Log("vk: Blit: a multisampled source is only resolved to a target of its size and format");
    else if (depth || (sameSize && src->format == dst->format))
    {
        const VkImageCopy region = {from, srcOffset, to, dstOffset, {srcRect.width, srcRect.height, 1}};
        vkCmdCopyImage(cmd, src->image, VK_IMAGE_LAYOUT_GENERAL, dst->image, VK_IMAGE_LAYOUT_GENERAL, 1, &region);
    }
    else
    {
        VkImageBlit region = {};
        region.srcSubresource = from;
        region.srcOffsets[0] = srcOffset;
        region.srcOffsets[1] = {srcRect.x + int32_t(srcRect.width), srcRect.y + int32_t(srcRect.height),
                                srcOffset.z + 1};
        region.dstSubresource = to;
        region.dstOffsets[0] = dstOffset;
        region.dstOffsets[1] = {dstRect.x + int32_t(dstRect.width), dstRect.y + int32_t(dstRect.height),
                                dstOffset.z + 1};
        const bool linear = filter == Filter::Linear && (s.caps.formatFlags[int(src->desc.format)] & FORMAT_FILTERABLE);
        vkCmdBlitImage(cmd, src->image, VK_IMAGE_LAYOUT_GENERAL, dst->image, VK_IMAGE_LAYOUT_GENERAL, 1, &region,
                       linear ? VK_FILTER_LINEAR : VK_FILTER_NEAREST);
    }
    FullBarrier(cmd);
}

void ReadTexture(gb::Texture *handle, uint8_t level, uint8_t layer, const Box &box, void *data, uint32_t rowPitch)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Texture *t = static_cast<Texture *>(handle);
    if (!t || !data || !box.width || !box.height || t->desc.samples > 1)
        return;
    const Format format = t->desc.format;
    // D24S8 reads back as GL's packing: depth in the top 24 bits, stencil in the low byte. Vulkan copies the depth
    // (X8_D24 or, on a D32FS8 device, a float) and the stencil (a byte per texel) separately.
    const bool depthStencil = format == Format::D24S8;
    const uint32_t texels = box.width * box.height;
    const uint32_t copyBytes = depthStencil ? 4 : FormatBytes(format);
    const uint32_t stencilOffset = (texels * copyBytes + 3u) & ~3u;
    const uint32_t size = stencilOffset + (depthStencil ? texels : 0);
    if (size > s.readbackSize)
    {
        FreeStore(s.readback.store);
        s.readbackSize = 0;
        if (!MakeStore(&s.readback.store, size, 0, true, true))
            return;
        s.readbackSize = size;
    }
    VkCommandBuffer cmd = Cmd();
    if (s.rendering)
        SuspendRendering();
    FullBarrier(cmd);
    MarkTexture(t);
    VkBufferImageCopy regions[2] = {};
    const uint32_t imageLayer = t->desc.type == TextureType::Cube ? layer : 0u;
    for (VkBufferImageCopy &r : regions)
    {
        r.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, level, imageLayer, 1};
        r.imageOffset = {int32_t(box.x), int32_t(box.y), t->desc.type == TextureType::Tex3D ? int32_t(box.z) : 0};
        r.imageExtent = {box.width, box.height, 1};
    }
    uint32_t regionCount = 1;
    if (IsDepthFormat(format))
        regions[0].imageSubresource.aspectMask = VK_IMAGE_ASPECT_DEPTH_BIT;
    if (depthStencil)
    {
        regions[1].bufferOffset = stencilOffset;
        regions[1].imageSubresource.aspectMask = VK_IMAGE_ASPECT_STENCIL_BIT;
        regionCount = 2;
    }
    vkCmdCopyImageToBuffer(cmd, t->image, VK_IMAGE_LAYOUT_GENERAL, s.readback.store.buffer, regionCount, regions);
    VkMemoryBarrier host = {VK_STRUCTURE_TYPE_MEMORY_BARRIER};
    host.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    host.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &host, 0, nullptr, 0,
                         nullptr);
    Flush();
    WaitSerial(s.submitted);
    vmaInvalidateAllocation(s.allocator, s.readback.store.allocation, 0, size);
    const uint8_t *in = s.readback.store.mapped;
    const uint32_t rowBytes = box.width * copyBytes;
    for (uint32_t y = 0; y < box.height; ++y)
    {
        uint8_t *out = static_cast<uint8_t *>(data) + size_t(y) * rowPitch;
        const uint8_t *row = in + size_t(y) * rowBytes;
        if (!depthStencil)
        {
            std::memcpy(out, row, rowBytes);
            if (format == Format::BGRX8)
                for (uint32_t x = 0; x < box.width; ++x)
                    out[x * 4 + 3] = 0xFF;
            continue;
        }
        for (uint32_t x = 0; x < box.width; ++x)
        {
            uint32_t raw;
            std::memcpy(&raw, row + x * 4, 4);
            uint32_t depth24;
            if (s_depthStencilFormat == VK_FORMAT_D24_UNORM_S8_UINT)
                depth24 = raw & 0xFFFFFFu;
            else
            {
                float value;
                std::memcpy(&value, &raw, 4);
                depth24 = uint32_t(std::clamp(value, 0.0f, 1.0f) * 16777215.0f + 0.5f);
            }
            const uint32_t packed = depth24 << 8 | in[stencilOffset + size_t(y) * box.width + x];
            std::memcpy(out + x * 4, &packed, 4);
        }
    }
}

gb::Query *CreateQuery(QueryType type)
{
    Query *q = new Query();
    q->type = type;
    return q;
}

void DestroyQuery(gb::Query *handle)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Query *q = static_cast<Query *>(handle);
    if (!q)
        return;
    if (q->open)
        --s.openOcclusion;
    for (FrameSlot &f : s.frames)
        f.queries.erase(std::remove(f.queries.begin(), f.queries.end(), q), f.queries.end());
    delete q;
}

void BeginQuery(gb::Query *handle)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Query *q = static_cast<Query *>(handle);
    FrameSlot &f = s.frames[s.frame];
    if (!q || q->type != QueryType::Occlusion || !s.rendering || q->open || f.occlusionUsed >= kQueriesPerFrame)
        return;
    q->slot = int(s.frame);
    q->index = f.occlusionUsed++;
    q->serial = 0;
    q->open = true;
    ++s.openOcclusion;
    f.queries.push_back(q);
    vkCmdBeginQuery(s.cmd, f.occlusion, q->index, 0);
}

void EndQuery(gb::Query *handle)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Query *q = static_cast<Query *>(handle);
    if (!q)
        return;
    FrameSlot &f = s.frames[s.frame];
    if (q->type == QueryType::Occlusion)
    {
        if (!q->open)
            return;
        vkCmdEndQuery(s.cmd, f.occlusion, q->index);
        q->open = false;
        --s.openOcclusion;
        q->serial = Pending();
        return;
    }
    if (!s.timestamps || f.timestampsUsed >= kQueriesPerFrame)
    {
        q->value = CpuNanoseconds();
        q->hasValue = true;
        q->serial = 0;
        return;
    }
    q->slot = int(s.frame);
    q->index = f.timestampsUsed++;
    q->serial = Pending();
    f.queries.push_back(q);
    vkCmdWriteTimestamp(Cmd(), VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, f.timestamps, q->index);
}

bool QueryResult(gb::Query *handle, uint64_t *value)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Query *q = static_cast<Query *>(handle);
    if (!q || !value)
        return false;
    if (q->serial)
    {
        // Still in the open commands: submit them, unless an occlusion query spans them (it cannot be split).
        if (q->serial > s.submitted)
        {
            if (s.openOcclusion)
                return false;
            Flush();
        }
        FrameSlot &f = s.frames[q->slot];
        uint64_t raw = 0;
        const VkQueryPool pool = q->type == QueryType::Occlusion ? f.occlusion : f.timestamps;
        if (vkGetQueryPoolResults(s.device, pool, q->index, 1, sizeof(raw), &raw, sizeof(raw),
                                  VK_QUERY_RESULT_64_BIT) != VK_SUCCESS)
            return false;
        q->value = q->type == QueryType::Timestamp ? uint64_t(double(raw) * s.timestampPeriod) : raw;
        q->hasValue = true;
        q->serial = 0;
        f.queries.erase(std::remove(f.queries.begin(), f.queries.end(), q), f.queries.end());
        q->slot = -1;
    }
    if (!q->hasValue)
        return false;
    *value = q->value;
    return true;
}

gb::Fence *InsertFence()
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    Fence *fence = new Fence();
    fence->serial = Pending();
    return fence;
}

bool FenceReached(gb::Fence *handle)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Fence *fence = static_cast<Fence *>(handle);
    if (!fence)
        return true;
    if (fence->serial > s.submitted)
    {
        if (s.openOcclusion)
            return false;
        Flush();
    }
    return Completed() >= fence->serial;
}

void DestroyFence(gb::Fence *handle)
{
    delete static_cast<Fence *>(handle);
}

gb::Swapchain *CreateSwapchain(const SwapchainDesc &desc)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Swapchain *sc = new Swapchain();
    sc->desc = desc;
    if (desc.window && s.surfaces)
    {
        if (host::CreateSurface(s.instance, desc.window, &sc->surface))
        {
            VkBool32 present = VK_FALSE;
            vkGetPhysicalDeviceSurfaceSupportKHR(s.physical, s.family, sc->surface, &present);
            if (!present)
            {
                Log("vk: the device's graphics queue cannot present to the game window");
                vkDestroySurfaceKHR(s.instance, sc->surface, nullptr);
                sc->surface = VK_NULL_HANDLE;
            }
        }
    }
    TextureDesc ramp = {};
    ramp.type = TextureType::Tex2D;
    ramp.format = Format::RGBA16;
    ramp.usage = Usage::Static;
    ramp.sampled = true;
    ramp.width = 256;
    ramp.height = ramp.depth = 1;
    ramp.levels = ramp.samples = 1;
    sc->ramp = MakeTexture(ramp);
    uint16_t identity[256 * 4];
    for (int i = 0; i < 256; ++i)
        for (int c = 0; c < 4; ++c)
            identity[i * 4 + c] = uint16_t(i * 257);
    if (sc->ramp)
        Upload2D(sc->ramp, 0, 0, {0, 0, 0, 256, 1, 1}, identity, sizeof(identity), sizeof(identity));
    return sc;
}

void ResizeSwapchain(gb::Swapchain *handle, uint16_t width, uint16_t height)
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    Swapchain *sc = static_cast<Swapchain *>(handle);
    if (!sc)
        return;
    sc->desc.width = width;
    sc->desc.height = height;
    sc->stale = true;
}

void DestroySwapchain(gb::Swapchain *handle)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Swapchain *sc = static_cast<Swapchain *>(handle);
    if (!sc)
        return;
    // Synchronous: once it returns, the platform may destroy the window.
    if (s.frameOpen)
        Flush();
    WaitSerial(s.submitted);
    FreeSwapchainImages(sc);
    if (sc->swapchain)
        vkDestroySwapchainKHR(s.device, sc->swapchain, nullptr);
    if (sc->surface)
        vkDestroySurfaceKHR(s.instance, sc->surface, nullptr);
    if (sc->present)
        vkDestroyPipeline(s.device, sc->present, nullptr);
    if (sc->ramp)
        FreeTexture(sc->ramp);
    delete sc;
}

void SetGamma(gb::Swapchain *handle, const uint16_t red[256], const uint16_t green[256], const uint16_t blue[256])
{
    std::lock_guard<std::recursive_mutex> guard(S().lock);
    Swapchain *sc = static_cast<Swapchain *>(handle);
    if (!sc || !sc->ramp)
        return;
    uint16_t texels[256 * 4];
    for (int i = 0; i < 256; ++i)
    {
        texels[i * 4] = red[i];
        texels[i * 4 + 1] = green[i];
        texels[i * 4 + 2] = blue[i];
        texels[i * 4 + 3] = 65535;
    }
    Upload2D(sc->ramp, 0, 0, {0, 0, 0, 256, 1, 1}, texels, sizeof(texels), sizeof(texels));
    sc->ramp->lastUse = std::max(sc->ramp->lastUse, Pending());
}

void Present(gb::Swapchain *handle, gb::Texture *imageHandle)
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    Swapchain *sc = static_cast<Swapchain *>(handle);
    Texture *image = static_cast<Texture *>(imageHandle);
    BeginFrame();
    if (s.rendering)
        SuspendRendering();
    FrameSlot &f = s.frames[s.frame];
    bool shown = false;
    if (sc && image && image->sampledView && sc->surface)
    {
        if (sc->stale || !sc->swapchain)
            MakeSwapchainImages(sc);
        uint32_t index = 0;
        VkResult acquired = sc->swapchain ? vkAcquireNextImageKHR(s.device, sc->swapchain, UINT64_MAX, f.acquire,
                                                                  VK_NULL_HANDLE, &index)
                                          : VK_ERROR_OUT_OF_DATE_KHR;
        if (acquired == VK_ERROR_OUT_OF_DATE_KHR)
            sc->stale = true;
        else if (acquired == VK_SUCCESS || acquired == VK_SUBOPTIMAL_KHR)
        {
            // The frame's own work first, then the copy into the window's image, which waits for the image.
            Submit();
            VkCommandBuffer cmd = Cmd();
            FullBarrier(cmd);
            MarkTexture(image);
            MarkTexture(sc->ramp);
            ImageBarrier(cmd, sc->images[index], VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
                         0, VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT, VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                         VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT);
            VkRenderingAttachmentInfo target = {VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO};
            target.imageView = sc->views[index];
            target.imageLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
            target.loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
            target.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
            VkRenderingInfo info = {VK_STRUCTURE_TYPE_RENDERING_INFO};
            info.renderArea = {{0, 0}, sc->extent};
            info.layerCount = 1;
            info.colorAttachmentCount = 1;
            info.pColorAttachments = &target;
            vkCmdBeginRendering(cmd, &info);
            vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, sc->present);
            const VkViewport viewport = {0.0f, 0.0f, float(sc->extent.width), float(sc->extent.height), 0.0f, 1.0f};
            vkCmdSetViewport(cmd, 0, 1, &viewport);
            const VkRect2D scissor = {{0, 0}, sc->extent};
            vkCmdSetScissor(cmd, 0, 1, &scissor);
            VkDescriptorImageInfo images[2] = {
                {static_cast<const Sampler *>(s.presentSampler)->sampler, image->sampledView, VK_IMAGE_LAYOUT_GENERAL},
                {static_cast<const Sampler *>(s.rampSampler)->sampler, sc->ramp->sampledView,
                 VK_IMAGE_LAYOUT_GENERAL}};
            VkWriteDescriptorSet writes[2] = {{VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET},
                                              {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET}};
            for (uint32_t i = 0; i < 2; ++i)
            {
                writes[i].dstBinding = i;
                writes[i].descriptorCount = 1;
                writes[i].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
                writes[i].pImageInfo = &images[i];
            }
            vkCmdPushDescriptorSetKHR(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, s.layout, 0, 2, writes);
            vkCmdDraw(cmd, 3, 1, 0, 0);
            vkCmdEndRendering(cmd);
            ImageBarrier(cmd, sc->images[index], VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
                         VK_IMAGE_LAYOUT_PRESENT_SRC_KHR, VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT, 0,
                         VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT);
            Submit(f.acquire, sc->renderDone[index]);
            VkPresentInfoKHR present = {VK_STRUCTURE_TYPE_PRESENT_INFO_KHR};
            present.waitSemaphoreCount = 1;
            present.pWaitSemaphores = &sc->renderDone[index];
            present.swapchainCount = 1;
            present.pSwapchains = &sc->swapchain;
            present.pImageIndices = &index;
            const VkResult presented = vkQueuePresentKHR(s.queue, &present);
            if (presented == VK_ERROR_OUT_OF_DATE_KHR || presented == VK_SUBOPTIMAL_KHR)
                sc->stale = true;
            else
                Ok(presented, "vkQueuePresentKHR");
            shown = true;
        }
        else
            Ok(acquired, "vkAcquireNextImageKHR");
    }
    else if (sc && !sc->surface && sc->desc.window && !sc->reportedNoSurface)
    {
        Log("vk: no surface on the game window: its frames are not shown");
        sc->reportedNoSurface = true;
    }
    if (!shown)
        Submit();
    s.frameOpen = false;
    ++s.presented;
    LogPerf();
}

void WaitIdle()
{
    State &s = S();
    std::lock_guard<std::recursive_mutex> guard(s.lock);
    if (s.frameOpen && (s.cmd || s.setup))
        Flush();
    WaitSerial(s.submitted);
}

const Backend &Table()
{
#define GB_VULKAN_ENTRY(ret, name, params, args) &vulkan::name,
    static const Backend table = {&vulkan::Init, &vulkan::Name, GB_BACKEND_CALLS(GB_VULKAN_ENTRY)};
#undef GB_VULKAN_ENTRY
    return table;
}
} // namespace gb::vulkan

