# Renderer: D3D9 frontend and backend contract

The engine's 64 `gfx_d3d` files keep calling Direct3D 9. On posix (and later the Switch), Direct3D 9 is
`src/gfx_d3d9emu/`, a frontend that records into `src/gfx_backend/gfx_backend.h`, a contract modelled on an
explicit, low-level API, so that a deko3d backend can implement it later without changing the frontend or the game.
`src/gfx_d3d9emu/` must contain no GL or deko3d calls: it only talks to `gfx_backend.h` and to its host
(`d3d9emu_host.h`: displays, windows, the `shaders.pack` path, screenshot files, the log), which the platform layer
implements (`src/platform/posix/posix_d3d9host.cpp`).

The backends sit behind a dispatcher (`gb_backend.cpp`): each fills a table of the contract's functions in its own
namespace (`gb::null`, `gb::gl`), and `gb::Init` picks one. `BO1_GFX_BACKEND=null` or `gl` names it; without the
variable it is GL when the platform gives a context, else null. A headless run gets a context only when
`BO1_GFX_BACKEND=gl` asks for one (its back buffer screenshots then show what GL drew).

## Contract (`gfx_backend.h`)
- **Conventions are D3D9's**: row 0 of a texture is its top row (uploads, attachments, viewports, scissors and
  fragment coordinates count from it), clip-space depth runs from 0 to 1, clockwise triangles face the front. The
  backend reproduces them (GL: `glClipControl(GL_UPPER_LEFT, GL_ZERO_TO_ONE)`, `glFrontFace(GL_CW)`, a flipped copy
  at present). **Rasterisation is the backend API's own** (pixels sampled at their middle, viewports covering whole
  pixels): D3D9's half-pixel offset is in the shaders, `bo1_pos_fixup` below. A viewport moved by half a pixel
  instead would clip geometry half a pixel inside the first column and row, which multisampling shows as a line of
  clear colour (seen on Kino with 4 samples, 2026-10-24).
- **Resources** declare format, usage (static, dynamic, colour or depth attachment), memory class, whether they are
  sampled, sample count and a component swizzle at creation, and never change. Destruction never waits: the backend
  frees what the GPU still uses later.
- **Uploads**: `UploadBuffer` (ordered, discard, or no-overwrite, D3D9's lock flags) and `UploadTexture` (a box of
  one level and layer), in order with the recorded work around them, from any thread.
- **State objects**: `GetSampler` and `GetPipeline` take a description and return an immutable object, cached by
  value (`gb_common.h` gives the canonical keys). A pipeline holds the shader pair, topology, vertex layout, blend,
  depth-stencil, rasterizer state and the formats of the attachments it renders into. `DestroyShader` ends the
  pipelines made with the shader, so that a new shader at the same address never meets a stale pipeline.
- **Passes**: `BeginPass` (attachments, load operations: load, clear, don't care) … `EndPass`. All rendering happens
  inside a pass; copies and readbacks outside. Hazards between passes are resolved at pass boundaries; inside a pass
  nothing samples an attachment. Attachments share their sample count; the pass covers the area they all have.
- **Draws**: `Draw`, `DrawIndexed` take a `DrawState` holding everything the draw reads besides its pipeline (vertex
  and index buffers, textures with their samplers, the two constant blocks, viewport, scissor, stencil reference,
  blend constant): nothing carries over from one draw to the next. Constants are copied into per-frame uniform memory
  with `AllocUniforms`.
- **Sync points**: `ReadTexture` (waits for the work that writes it), `WaitIdle`, `Present`. Query results and fences
  are polled and never wait.
- **Threads**: the frontend makes one call at a time. Creation, destruction and uploads may come from any thread;
  recording from one thread at a time (the render thread), which a thread-bound device (a GL context) follows.

## Review checklist (every change to `gfx_backend.h`)
1. No implicit global state: everything a draw needs is in its pipeline, its `DrawState` or the current pass.
2. No query that reads back GPU or driver state (`glGet*`, sync readbacks) outside `ReadTexture`, `WaitIdle` and
   `Present`; queries and fences only report what is ready.
3. No implicit synchronisation. Hazards between passes are expressed by pass boundaries.
4. Every resource declares format, usage and memory class at creation.
5. Nothing names a GL object, enum or extension.
6. The null backend (`src/gfx_backend/null/`) still implements the whole header, and `tests/gfx_d3d9emu` passes; so
   does `tests/gfx_backend` on the GL backend.

## The frontend (`src/gfx_d3d9emu`)
It implements the part of Direct3D 9 the engine calls, inventoried with libclang over the posix build (87 methods,
`AddRef` and `Release` included); every other method ends the process naming itself (`Unemulated`), so a new caller
is noticed at once. One recursive lock serialises every call, as the runtime does for a `D3DCREATE_MULTITHREADED` device.

- **Objects** have two reference counts, as in the runtime (and Wine): the application's, and the device's while
  the object is bound, so a texture released while bound lives until it is unbound. A resource holds a reference on
  its device while the application holds one on it. Texture levels share their texture's counts, the back buffer and
  the swap chain the device's.
- **Locks**: a lockable resource (managed, dynamic, system memory, scratch, offscreen plain) keeps a CPU copy of each
  locked level, so a lock sees what was written (the model lighting volume is locked every frame for a few texels).
  The unlock uploads the locked region. A copy the GPU wrote since (`StretchRect` into a lockable surface) is read
  back at the next lock.
- **Passes follow the render targets**: changing a target or the depth buffer ends the pass, and the next draw or
  clear begins one. A clear of the whole targets before the pass's first draw becomes its load operation; other
  clears are `gb::Clear` on the viewport, scissor and rects, as D3D9 clears.
- **Pipelines** are rebuilt only when a state that feeds them changed; constants are uploaded (4112 bytes per
  block: the 256 registers and one state vector) only when they changed, and again after each `Present`.
- **Draws** bind only the samplers the pixel shader declares (its `dcl` tokens). A sampler that reads an attachment of
  the pass (undefined in D3D9 too) is left unbound and logged once. `DrawPrimitiveUP` streams through one dynamic
  buffer, padded with zeros past the vertices, and leaves stream 0 unset as the runtime does.
- **Queries**: event queries are fences; occlusion queries count over one backend query per pass they span, and one
  counts at a time (a query opened inside another pauses it); timestamps are in nanoseconds (frequency 1 GHz, never
  disjoint).
- **Vendor tricks the engine uses**: `INTZ` depth textures (sampled as depth in every component), AMD's RESZ resolve
  (`D3DRS_POINTSIZE` = `0x7FA05000` copies the depth buffer into the INTZ texture at sampler 0), `NULL` render
  targets (no colour attachment), and hardware shadow maps (a D24S8/D16 texture created as a depth-stencil and
  sampled with `depthCompare`).
- **The adapter** reports one display (the host's first), no PCI vendor (the engine's NVIDIA/ATI paths stay off), a
  shader model 3 device with the caps `gfx_d3d/r_caps.cpp` requires, the formats the backend supports (D24FS8,
  `ATOC`/`SSAA` transparency AA, vertex texture fetch and sRGB are not reported), and up to 4 GB of texture memory, as
  a 32-bit runtime would. A 9Ex device has no managed pool, and its `Present` returns `S_PRESENT_OCCLUDED` when the
  window cannot be seen (the headless client's hidden window, as on Windows' private desktop).

- **D3DX**: `D3DXSaveSurfaceToFileA` writes the engine's screenshots (`screenshot`, `screenshotJpeg`) from a 32-bit
  surface as JPG, TGA, BMP or PNG with stb_image_write (`third_party/stb`), the file through the host; TGA is
  uncompressed and JPG and BMP drop the alpha, as D3DX writes them.

Not emulated (the engine never calls them on these paths): the fixed-function pipeline (Bink only), vertex textures,
state blocks, sRGB reads and writes, lockable render targets, clip planes, cursors, point sprites, autogenerated
mipmaps.

## Upscaling (`src/gfx_d3d9emu/d3d9emu_upscale.cpp`)
The frontend can present the frame larger than the engine rendered it, with AMD FSR 1.0: EASU (edge-adaptive
upscale), then RCAS (sharpening). It runs as ordinary contract work at `Present`, so every backend has it without code
of its own, and `gfx_backend.h` did not change. The Switch's 540p and 480p modes are what it is for: without it, the
console's compositor stretches the frame bilinearly.

- **Settings** come from the host (`host::Upscale`). On posix and the Switch they are environment variables:
  - `BO1_UPSCALE=fsr1`;
  - `BO1_UPSCALE_OUTPUT=<width>x<height>` (required);
  - `BO1_UPSCALE_SHARPNESS`, RCAS's stops below its strongest, 0 to 2, default 0.2 as AMD's.

  The Switch start menu sets them (`Launcher_UpscaleEnvironment`, `switch_main.cpp`): FSR 1.0 to 1280x720, only
  below 720p.
- **The swapchain takes the output size** (`Device::ChooseOutput`, at creation and `Reset`) when it is larger than the
  back buffer and the backend can sample, filter and render the back buffer's format. Otherwise nothing changes.
- **Present**:
  1. a copy of the back buffer into a sampled texture (the back buffer is not sampled; a multisampled one is resolved
     first, as before);
  2. EASU into an output-sized target;
  3. RCAS into the image presented.

  Each pass is one full-screen triangle (`gl_VertexID`, no vertex input) with the constants of `FsrEasuCon` /
  `FsrRcasCon` in a 64-byte block at binding 1. The back buffer `GetFrontBufferData` and screenshots read is still
  the engine's own size.
- **The 2D at the output size** (`d3d9emu_scene.h`, docs/VULKAN.md step 6.1). The engine calls
  `Bo1Emu_SceneComplete` at the end of `RB_Draw3D`, once every view's scene, post effects included, is in the back
  buffer and before the 2D (each view's HUD in `RB_Draw3DCommon`, then the frame's commands). The frontend then:
  - runs the three steps above into `m_hudTarget`, an output-size colour target made with the back buffer;
  - until `Present`, sends every pass into the back buffer to `m_hudTarget` instead (`PassTarget`), with the viewport,
    the scissor rect and the clear rects scaled from the back buffer's size to the output's (`PassViewport`,
    `PassScissor`), `bo1_pos_fixup` from the scaled viewport, and without the back buffer's depth buffer, whose size
    no longer matches (`PassDepth`; the 2D does not depth-test);
  - redirects `StretchRect` from or to the back buffer the same way, rects scaled (the saved-screen blur and flash
    read the frame so far), and `GetRenderTargetData` of the back buffer gets the frame so far brought back to its
    size;
  - presents `m_hudTarget` as it is.

  The HUD and menus over a scene are then drawn at the output size instead of being upscaled with the scene. A frame
  without a scene (main menu without a world, loading screen, cinematic) is upscaled whole at `Present` as before. A
  read of the back buffer after such a `Present` (the headless client's screenshot, `GetFrontBufferData`) first gets
  the presented frame brought back to the back buffer's size, once (`RestorePresentedFrame`), since the back buffer
  then holds only the scene. Split screen works: every view's scene is done before the first HUD.
- **Shaders**: `src/gfx_d3d9emu/shaders/fsr1_*.glsl`, GLSL 4.30 ports of the 32-bit paths of `ffx_fsr1.h`
  (`third_party/fidelityfx_fsr1`).
  - EASU reads the source with `textureGather`. RCAS reads it with `texelFetch`, clamped at the edges (HLSL's Load
    would return black there).
  - RCAS's divisors are kept off zero: AMD's code relies on the hardware's min/max dropping a NaN, which GLSL leaves
    undefined.
  - `tools/embed_shaders.py` embeds them in a generated header as GLSL, in the Switch build also as DKSH from uam
    (under `setarch -R`, deterministic), and with the Vulkan backend also as SPIR-V. The frontend hands the backend the form its `shaders.pack` has
    (`ShaderPackForm`), under fixed hashes (`b01f5a1000000001` to `03`) that no shader of the zombies zones' pack has.
  - Without a usable form (no pack, a DKSH pack in a build without the DKSH), the frame is stretched by a linear
    `Blit`, logged once.
- **Tests**:
  - `d3d9emu_test` checks the calls on the null backend: swapchain size, three shaders, copy, two passes, the
    presented image, and nothing new on the next frame; after `Bo1Emu_SceneComplete`, the 2D's pass on the
    output-size target with its viewport and clear rects scaled, a second call doing nothing, that target presented
    as it is, a screenshot of the last frame bringing it back once, and a frame without a scene upscaled whole.
  - `SDL_VIDEODRIVER=offscreen ./upscale_gl_test [--image in.ppm --out dir]` upscales on GL and checks:
    - a flat image stays flat;
    - rows stay the right way up;
    - the sharpening's halo stays under a tenth of an edge (14-15 of 180 levels at 0.2 on llvmpipe; EASU alone stays
      in range);
    - an edge comes out narrower than with the linear stretch.

    On a game capture rendered at 960x540, the 1280x720 result is closer to the native 720p one than the stretch
    (PSNR 37.6 against 36.1 dB, 2026-11-22).

## The null backend (`src/gfx_backend/null`)
It implements the whole header without a GPU: it draws nothing and keeps no texel, and its results are those of a
device that drew nothing (occlusion queries count 0, fences are reached at once, readbacks return zeros). It checks
every call against the contract and ends the process on a breach (a draw outside a pass, a pipeline whose formats do
not match the pass, an upload outside a resource, a sampled attachment, a blit inside a pass…), so a headless run on
it proves the frontend keeps the contract. `gb_null.h` records every call as a line, which `tests/gfx_d3d9emu` checks.

## The GL backend (`src/gfx_backend/gl`)
OpenGL 4.3 core with `glClipControl` (4.5 or `ARB_clip_control`); `EXT_texture_compression_s3tc` for the BC formats.
It links against no GL library: its host (`gb_gl_host.h`, implemented by `src/platform/posix/posix_glhost.cpp` with
SDL2) makes the context on a hidden 1x1 window, gives the entry points (`gb_gl_functions.h` lists every one it calls)
and the windows to present to; the Switch would implement the same host with EGL.

- **One thread owns the context** (`gb_gl_device.cpp`). The side the frontend calls (`gb_gl.cpp`) hands out the
  objects at once and records the work into chunks, handed over every 512 commands or 1 MB of payload and at each
  `Present`. Compiles and links go on a second lane, served between commands: a `GetPipeline` waits for its link, not
  for the frames queued before it. The only other waits are the contract's sync points (`ReadTexture`, `WaitIdle`,
  `DestroySwapchain` so that the window can go) and `Present` once the thread is a frame behind. A query or fence
  still being recorded is handed over when it is polled (`D3DGETDATA_FLUSH`). The thread's log lines reach the engine
  through the frontend's calls.
- **State**: one vertex array per vertex layout (`glVertexAttribFormat`/`Binding`), framebuffers cached by
  attachments, sampler objects, and a cache of everything bound so that a draw makes only the calls that change
  something. Uploads bind on texture unit 16, which no draw samples, and make it the active unit first: a draw
  leaves another one active, and a call on a target acts on the active unit.
- **Uniforms**: frame-local blocks of 1 MB, persistently mapped when the context has buffer storage, recycled behind
  a fence per frame; the frontend side places each `AllocUniforms` (never across a block) and the backend's thread
  writes it at that offset.
- **Conventions**: `glClipControl(GL_UPPER_LEFT, GL_ZERO_TO_ONE)` makes window row 0 an attachment's first row, so
  viewports, scissors, blits and readbacks take D3D9's rows unchanged; the upper-left origin leaves GL judging facing
  as with its own, so D3D9's clockwise front faces are `GL_CW`. Depth bias: `glPolygonOffset(slope, bias * 2^24)`
  (2^16 on D16). `Present` draws the image into the window's bottom-up framebuffer through the gamma ramp (a 256x1
  texture), scaled to the drawable.
- **Formats**: BGRA8 is `GL_RGBA8` uploaded as `GL_BGRA`; BGRX8 is `GL_RGB8`, so that its alpha reads 1 as D3D9's
  X8 formats do; B5G6R5 and B5G5R5A1 are `GL_RGB565` and `GL_RGB5_A1` with the packed types; BC1-3 the S3TC formats;
  D24S8 `GL_DEPTH24_STENCIL8`. Which formats are sampled and rendered into is tested at start-up with a framebuffer
  per format. The swizzle is `GL_TEXTURE_SWIZZLE_RGBA`.
- `BO1_GL_DEBUG=1` turns on the debug output (synchronous, the first 64 messages into the log).
- Every 10 s `Present` logs a `gl perf:` line: frames, draws a frame, bytes uploaded, new pipelines and links, where
  the frontend side waited (frames, links, sync points) and how long the backend's thread spent on commands, builds
  and swaps.

`tests/gfx_backend/gb_backend_test.cpp`, built as `gb_gl_test`, draws with the backend alone under SDL's offscreen driver and reads the pixels
back: row 0 on top, fragment coordinates, depth and the viewport's depth range, viewport and scissor rows, clockwise
front faces and two-sided stencil, pixel centres through `bo1_pos_fixup` (with the fixup turned off it fails),
4-sample edge pixels (with the old half-pixel viewport it fails), texture rows and formats (B5G6R5, B5G5R5A1,
RGBA8, BC1, an L8 swizzle), an upload after a draw that left another unit active, BGRX8 alpha, `Clear` rects,
`Blit` copies and scaling, a hardware shadow map compare, occlusion counts, timestamps and fences, and a shader that
does not compile.

## The Vulkan backend (`src/gfx_backend/vulkan`)
Vulkan 1.3 with dynamic rendering, timeline semaphores, host query reset and `VK_KHR_push_descriptor`. Opt-in:
`BO1_GFX_BACKEND=vulkan` (docs/VULKAN.md; the dispatcher never falls back from it, so a failure is seen). The loader is
opened at run time by volk and memory comes from the Vulkan Memory Allocator (`third_party/volk`, `third_party/vma`,
headers in `third_party/vulkan-headers`). Its host (`gb_vk_host.h`) gives the instance extensions and a surface per
window: on posix SDL2 (`posix_vkhost.cpp`), which makes the game windows Vulkan ones once the backend runs. A headless
run has no surface; it renders into its textures and `Present` only submits.

- **Recording**, as deko3d's:
  - the frame is recorded into command buffers and submitted at `Present`, two frames in flight, each slot with its
    command pool, uniform blocks (4 MB, host-visible), staging chunks and query pools;
  - every submission signals one timeline semaphore, whose values order frames, fences, queries and the destruction
    of objects the GPU may still use;
  - a readback, or a fence or query polled before its work was submitted, submits the frame so far (an open pass is
    ended and begun again with load ops `Load`); a poll while an occlusion query is open returns "not ready" instead,
    since a query cannot span two command buffers.
- **Images** stay in `VK_IMAGE_LAYOUT_GENERAL` from their creation (the transition goes into the setup commands), and
  a full memory barrier at each pass boundary, copy and readback resolves the contract's hazards. Colour targets are
  always created sampled, since `Present` reads its image through a shader.
- **Uploads** go into a "setup" command buffer submitted before the frame's, unless work recorded in the frame's open
  commands already uses the resource: then they go in order into the frame, the pass suspended around the copy.
  Dynamic and shared buffers are host-visible: `NoOverwrite`, or a store the GPU is done with, is written in place;
  `Discard` on a store in use renames it (up to 8 spare stores per buffer); `Ordered` on a store in use is a staged
  copy in order.
- **Draws**: one pipeline layout for all, one descriptor set pushed per draw: samplers at 0-15, the vertex and pixel
  constant blocks at 16 and 17, as `make_spirv_pack.py` moves them. Pipelines are built at `GetPipeline` with dynamic
  viewport, scissor, stencil reference, blend constants, topology (within the pipeline's class) and vertex strides.
  - A sampler the shader reads (reflected from its SPIR-V: binding, dimension, depth comparison) that the draw leaves
    unbound reads a 1x1 dummy of its kind: opaque black, or depth 1 for a shadow map.
  - A vertex input the declaration does not give reads (0, 0, 0, 1) from a dummy stream at binding 8, as D3D9 does;
    Vulkan would leave it undefined.
- **Conventions**:
  - the viewport goes in with a negative height (y + height, -height), so clip-space +y is row 0 and the winding on
    screen is D3D9's: `VK_FRONT_FACE_CLOCKWISE`;
  - depth bias × 2^24 (2^16 on D16);
  - D24S8 is `D24_UNORM_S8_UINT`, or `D32_SFLOAT_S8_UINT` where the device cannot render the former (AMD);
  - BGRX8 is `B8G8R8A8_UNORM` whose alpha stays 1: cleared to 1, never written by a pipeline, sampled through an
    alpha-one swizzle and read back as 0xFF;
  - `ReadTexture` of D24S8 packs depth in the top 24 bits and stencil in the low byte, as GL reads it;
  - a multisampled depth buffer `Blit` into a single-sample depth texture (D3D9's RESZ with `r_aaSamples` above 1)
    resolves at the end of an empty rendering scope, `VK_RESOLVE_MODE_SAMPLE_ZERO_BIT`: `vkCmdResolveImage` takes
    colour only, and the Intel Iris Xe driver lost the device on it at the first frame in game;
  - point lists need `VK_KHR_maintenance5` (a point whose vertex shader writes no `PointSize` is 1 pixel, as in D3D9);
    without it their draws are skipped;
  - `MipFilter::None` clamps the level of detail to 0.25.
- **Present** draws the image into the swapchain's through D3D9's gamma ramp (a 256x1 RGBA16 texture), filtered to
  the window's size, with the backend's own SPIR-V shaders (`vulkan/shaders`, embedded by `tools/embed_shaders.py`).
  The swapchain is UNORM (as the GL window), FIFO with vsync, else mailbox or immediate; it is made again when the
  window changes size or the surface says it is out of date.
- **Caps** come from the device's format features: a colour target must also blit both ways; BC1-3 need
  `textureCompressionBC`.
- `BO1_VK_DEBUG=1` loads the Khronos validation layer when it is installed and logs its first 64 messages. Every 10 s a
  `vk perf:` line gives frames, draws a frame, submissions and suspended passes a frame, renames, new pipelines (and the
  milliseconds the driver spent compiling them) and the memory VMA holds. A frame longer than 50 ms logs a `vk hitch:`
  line (the first 500): the backend's share of it (GPU waits, acquire, present, pipelines, new textures, staged bytes,
  submissions); the rest of the frame was the engine's.
- In the game, pipelines compile on background threads (1 to 3, `host::AsyncPipelines`; the tests keep them
  synchronous): `GetPipeline` returns at once and a draw whose pipeline is not ready is skipped (`vk perf:` counts
  them). The user's Intel Iris Xe spends 100-500 ms on one pipeline, so every new combination of shaders and states
  (the first shots, effects, zombies) stopped the game that long; now an object misses a few frames instead. A shader
  is freed only once the queue is empty, and the threads stop before the pipelines are freed.
- The pipeline cache is kept between runs in `vk_pipelines.bin` beside the program (`host::PipelineCachePath`). Its
  Vulkan header must name this device, vendor and driver (`pipelineCacheUUID`) or it is not read. It is written once
  ten seconds go by without a new pipeline, and at shutdown, through a temporary file.

`gb_vk_test` is `gb_backend_test.cpp` built for this backend (`GB_TEST_VULKAN`): the same 46 checks with no window,
on any Vulkan 1.3 device (lavapipe included).

### On win64 (`r_mod_gfxApi vulkan`, docs/VULKAN.md step 5)
`win64-msvc` also builds the frontend (without `d3dx9emu.cpp`) and the null and Vulkan backends (`BO1_WIN_VULKAN`).
The system's Direct3D 9 stays the default; with `r_mod_gfxApi vulkan`, `R_PreCreateWindow` takes the emulated
`IDirect3D9` from `Bo1_EmulatedDirect3D` (`src/platform/windows/win_d3d9host.cpp`), and falls back to the system's
when `shaders.spv` is missing beside the exe or Vulkan does not start. On Windows the emulator's entry points are
`Bo1Emu_Direct3DCreate9`/`Bo1Emu_Direct3DCreate9Ex`, so `d3d9.lib`'s keep their names; D3DX remains `d3dx9.lib`'s and
works on the emulated surfaces (screenshots). The surface is `VK_KHR_win32_surface` on the game's `HWND`
(`win_vkhost.cpp`). FSR 1.0 there is `r_mod_upscale`: the engine makes its back buffer (and vidConfig) the window's
size over the mode's factor, the window keeps its size, and the host hands the frontend the window as the upscaler's
output (`Bo1_SetUpscale`); the mouse is moved into back buffer pixels (`Bo1_ClientToBackBuffer`).

## Shaders
`ffconv` translates D3D9 SM3 bytecode with MojoShader (`third_party/mojoshader`, GLSL profile) and normalises the
result to GLSL 4.60 core without extensions (`tools/ffconv/src/ff_glsl.cpp`). Every shader of the zombies zones is
vs_3_0 or ps_3_0 and only uses float constants (`c#`) and samplers (`s#`); none samples in a vertex shader.

The GL backend compiles this GLSL with mesa. The deko3d backend uses the same GLSL compiled offline by `uam` into
DKSH (`tools/ffconv/gen/make_dksh_pack.py`), and rewrites each program's control words when it loads it
(`UseMesaSchedule`): uam dual-issues where Mesa never does, which corrupts whole warps on the console under load
(`docs/PORTING.md`, phase 7, twelfth console run).

### Shader interface
A shader is found by the FNV-1a 64 hash of its D3D9 bytecode (`ShaderPack_Hash`). The device only receives a pointer:
the frontend measures the bytecode up to its end token (`ShaderBytecodeSize`), which gives the length `ffconv`
hashed for all 13 704 shaders of the zones.

| What | GLSL | Filled from |
|---|---|---|
| Vertex constants `c0..c255` | `layout(std140, binding = 0) uniform BO1VertexConstants { vec4 vs_c_reg[256]; vec4 bo1_pos_fixup; }` | `SetVertexShaderConstantF` registers, then a state vector |
| `bo1_pos_fixup.xy` | `gl_Position.xy += bo1_pos_fixup.xy * gl_Position.w` at the end of `main` | (63/64 / width, -63/64 / height) of the viewport: the vertices move right and down by just under half a pixel before clipping, as D3D9 hardware moves them after the viewport transform; 63/128 rather than 1/2 (wined3d's value) keeps an edge through a D3D9 pixel centre on D3D9's side whichever way the backend breaks ties |
| Position invariance | `invariant gl_Position;` in every vertex shader | — (the depth prepass and the lit passes compare equal depths from different vertex shaders, as D3D9 hardware allows; without it uam fuses their multiply-adds differently and whole walls fail the depth test) |
| Pixel constants `c0..c255` | `layout(std140, binding = 1) uniform BO1PixelConstants { vec4 ps_c_reg[256]; vec4 bo1_alpha_test; }` | `SetPixelShaderConstantF` registers, then a state vector |
| `vPos` | `vec4 ps_vPos = vec4(gl_FragCoord.xy - 0.5, gl_FragCoord.zw)` | — (D3D9's integer pixel position; fragment rows already count from the top) |
| `bo1_alpha_test` | `x`: 0 off, 1 `alpha > ref`, 2 `alpha >= ref`; `y`: ref, 0-255 | `D3DRS_ALPHATESTENABLE`, `ALPHAFUNC` (the engine only sets `GREATER` and `GREATEREQUAL`), `ALPHAREF` |
| Sampler `s#` | `layout(binding = #)` | `SetTexture(#)` and its sampler state |
| Shadow map sampler `s#` | `sampler2DShadow` for the samplers the constant table names `shadowmapSamplerSun` or `shadowmapSamplerSpot`; each lookup returns `vec4(...)` of the comparison, with the reference from z (`textureProj`: z / w; `texture` and `textureLod` take `.xyz` where MojoShader passed `.xy`) | the shadow map's depth texture, with a `depthCompare` sampler (`LEQUAL`) |
| Vertex input | `layout(location = d) in`, `d` = `ShaderPack_InputLocation(usage, index)` (`shader_pack.h`), the material stream destination (`s_streamDestInfo`), 0-15: BLENDWEIGHT takes 15 and TEXCOORD10-13, which no shader reads, take none (GL and uam accept 16 locations) | the vertex declaration's elements |
| Varyings | `io_<usage>_<index>` at location `index` (TEXCOORD0-15) or `16 + index` (COLOR0-1), `centroid` kept on pixel inputs | — |
| COLOR output clamp | each `io_10_#` (COLOR0-1) a vertex shader writes is `clamp(..., 0.0, 1.0)` at the end of `main` | D3D9 clamps COLOR-semantic interpolators to [0, 1] at the vertex output, before interpolation; MojoShader routed them through `gl_FrontColor`/`gl_Color` (clamped by default in compatibility GL), and the rename to core-profile varyings dropped that |
| Pixel output | `layout(location = 0) out vec4 bo1_color0` | — |

Literal constants (`def`) stay in the GLSL; a `def` range the shader indexes with `a0` becomes a `const` array.

### Open for the GL backend
- `#version 460`: Mesa 20.1 on the Switch (nouveau) may offer only 4.3 to 4.5; the normaliser may have to write the
  lowest version the shaders need.
