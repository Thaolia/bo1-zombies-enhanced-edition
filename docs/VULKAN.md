# Vulkan backend and upscalers — plan

Status (2026-11-23): steps 1-7 done (FSR1 checked on the console too; Vulkan on Linux and win64; Arm ASR with its
reactive mask; native AA; SSAA), merged into `switch`. Open: ASR on the Switch (step 6, item 4) and OpenBSD (step 8).
Each step updates this file, `docs/RENDERER.md` and `docs/PORTING.md` (phase 9) in the session that does it.

## Goals and constraints
- A Vulkan backend behind `src/gfx_backend/gfx_backend.h`, opt-in on **Linux**, **win64** and, last of all (after ASR and SSAA), **OpenBSD**.
- **OpenGL stays the default** backend on Linux and OpenBSD. On win64, native Direct3D 9 stays the default.
- **`win32-msvc` changes as little as possible**: it compiles none of the new files, and every engine edit it does see
  is guarded so its code stays identical (`tools/codediff.py`).
- Upscaling in this order:
  1. **FSR1** first (spatial, all emulated backends, the Switch included);
  2. **Arm ASR** after the win64 port (temporal);
  3. **SSAA and native AA** (rendering above the window's size, or ASR at 1:1), then only Vulkan on OpenBSD.
- The Switch keeps deko3d: Vulkan is not a Switch backend.

## Facts the plan rests on (checked 2026-11-22)
- win32 and win64 call the real `d3d9.dll` (`src/gfx_d3d/r_init.cpp`, `Direct3DCreate9` / `Direct3DCreate9Ex`).
  The emulated D3D9 frontend (`src/gfx_d3d9emu`) and the backends (`src/gfx_backend`) only build on posix and the
  Switch.
- The contract is explicit (passes, immutable pipelines and samplers, explicit uploads, sync points only at
  `ReadTexture` / `WaitIdle` / `Present`). deko3d (`gb_deko3d.cpp`) is the backend closest to Vulkan: a whole frame
  recorded then submitted, dynamic buffers renamed on DISCARD, two frames in flight, suballocated memory blocks,
  uploads recorded into the frame.
- Shaders: the frontend finds a shader's GLSL in `shaders.pack` by the hash of its D3D9 bytecode and calls
  `gb::CreateShader(stage, hash, text, size)` (`d3d9emu_shaders.cpp`). deko3d reads a parallel DKSH pack compiled
  offline by uam (`tools/ffconv/gen/make_dksh_pack.py`). The GLSL is 4.60 core with explicit bindings: UBOs 0 (vertex
  constants) and 1 (pixel constants), samplers at `binding = s#`.
- Switch 540p: the swapchain is 960x540 and the console's compositor stretches it bilinearly, HUD included. The GPU
  took 29.4 ms a frame at 720p on the user's console (fill-rate bound); 540p is expected near 22 ms but has not been
  measured on the console yet.
- The engine has no sub-pixel jitter and no per-pixel motion vectors. Its motion blur (`r_motionblur_*`) is
  camera-based.

## Step 1 — FSR1 in the frontend (every emulated backend at once) — done
What was built is described in `docs/RENDERER.md`, "Upscaling". In short, and where it departs from the first plan:
- EASU and RCAS are GLSL **4.30** ports (`src/gfx_d3d9emu/shaders/`) of `ffx_fsr1.h` (MIT,
  `third_party/fidelityfx_fsr1`). They are **embedded in the program**, not added to `shaders.pack`: the packs come from the player's own zones, and a
  program shader must not depend on regenerating them. `tools/embed_shaders.py` writes them into a generated header,
  as GLSL and, in the Switch build, as DKSH from uam (SPIR-V too since step 3). The frontend hands the backend the form of its pack.
- Variant A as planned: the swapchain takes the output size, `Present` copies the back buffer, then draws EASU, then
  RCAS. `gfx_backend.h` is unchanged; the HUD goes through the upscale.
- The settings are **host settings, not dvars**: the frontend sits below the engine and reads none.
  - posix and the Switch read `BO1_UPSCALE=fsr1`, `BO1_UPSCALE_OUTPUT=WxH` and `BO1_UPSCALE_SHARPNESS`.
  - The Switch start menu has "FSR 1.0" (Oui/Non) and "Nettete FSR" (Maximale, Forte (AMD's 0.2, default), Moyenne,
    Douce, Faible) under "Resolution". Both only apply below 720p; menu.cfg keys `fsr1` and `fsr_sharpness`.
  - `switch_main.cpp` turns them into the variables in every boot (`skip_menu` too). The output is always 1280x720.
- Checks run (host):
  - `d3d9emu_test`;
  - `upscale_gl_test`: flat image, row order, halo, edge width;
  - a 960x540 game capture → 1280x720: PSNR against native 720p 37.6 dB with FSR 1.0 against 36.1 with the stretch;
  - `launcher_config_test`;
  - Linux and Switch builds.
- Ryujinx (deko3d): Kino at 960x540, a 1280x720 swapchain, clean in-game frames through FSR over 225 s.
- The user's console (2026-11-22): Kino at 480p + FSR 1.0 (854x480 to 1280x720, sharpness 0.2), shadows off, 30 fps
  cap.
  - Steady 30.3 fps over ~2 min 45 s; GPU 13.9 ms a frame median (p90 16.4, max 19.1), FSR included.
  - No renderer warning; a clean exit.
  - The user finds the image sharper than before.
  - Not measured: FSR's own cost. That needs a run with the same settings and FSR off; the old 480p multiplayer
    logs, 15.7 ms, were not the same scene.

## Step 2 — SPIR-V pack, offline — done (2026-11-22)
- `tools/ffconv/gen/make_spirv_pack.py OUT/shaders.pack OUT/shaders.spv`, modelled on `make_dksh_pack.py`: glslang
  `-V --target-env vulkan1.1 --shift-UBO-binding 16`, the GLSL never edited. Vulkan has one binding space per
  descriptor set, so set 0 holds the samplers at their `s#` (0-15), the vertex constants at 16 and the pixel
  constants at 17. Each module goes through `spirv-val`, then a check of its own bindings (decoded from the SPIR-V),
  and lands in a `BO1SPRV1` pack laid out as `shader_pack.h`.
- Results on the zombies zones' pack (13 704 shaders): 0 rejected, two runs byte-identical (md5 `9414a2c5…`), 6 min 42
  s on 8 threads.
- Open: the pack is **477.6 MB** against 132.8 MB of GLSL. SPIR-V is that verbose; stripping debug names saves only
  1.5 %, zlib about 70 %. Compressing each payload (the entry's reserved field holding the inflated size) is planned
  before the packages carry it (step 5).
- `#version 430` and `GL_ARB_shader_texture_lod`: the pack's `#if GL_ARB_shader_texture_lod` block keeps
  `textureLod` only when that macro is defined. glslang (GL and Vulkan) and uam both define it, so nothing changes.
- The FSR 1.0 vertex shader reads `gl_VertexIndex` when glslang targets Vulkan (`#ifdef VULKAN`); its GL and DKSH
  builds are unchanged (the DKSH byte-identical).

## Step 3 — Vulkan backend on Linux (opt-in) — done (2026-11-22)
Described in `docs/RENDERER.md`, "The Vulkan backend". In short:
- `src/gfx_backend/vulkan/` (`gb_vk.cpp`), opt-in with `BO1_GFX_BACKEND=vulkan` (the dispatcher never falls back from
  it). CMake option `BO1_VULKAN` (ON on posix; needs `glslangValidator` at build time).
- Vulkan-Headers (SDK 1.3.296), volk and VMA 3.1.0 are vendored in `third_party/`: no Vulkan SDK to build, and the
  game starts without Vulkan.
- Host `gb_vk_host.h`; on posix SDL2 (`posix_vkhost.cpp`), whose windows become Vulkan windows once the backend runs.
  A headless run has no surface and renders into its textures.
- Requires Vulkan 1.3 (dynamic rendering, timeline semaphores, host query reset) and `VK_KHR_push_descriptor`.
- Differences from the first plan:
  - images stay in `GENERAL`, with full barriers at pass boundaries (simple and correct; to measure in step 4);
  - a render-target format the device cannot render is reported as such in `Caps` instead of being swapped for
    RGBA8.
- Checks:
  - `tests/gfx_backend/gb_backend_test.cpp` is now built twice: `gb_gl_test` 46/46 and `gb_vk_test` 46/46 on
    lavapipe;
  - with `BO1_VK_DEBUG=1`, the Khronos validation layer and its synchronisation validation report nothing (a
    deliberate misuse in a separate program proved the messages reach the log);
  - `d3d9emu_test`, `upscale_gl_test`, `launcher_config_test`.

## Step 4 — Parity on Linux
- GL against Vulkan screenshots: main menu, Kino, Five, one imported BSP map. Explain every difference.
- FSR1 on Vulkan.
- The usual posix gate: a headless run against win64, paths and numbers masked.
- Estimate: 1-2 sessions.

## Step 5 — win64: the emulated frontend and Vulkan, native D3D9 by default — in progress
Done on branch `vulkan` (2026-11-22):
- CMake: the shader headers (`upscale_shaders.h`, `vk_shaders.h`) are generated in one block shared by posix, the
  Switch and win64; 32-bit Windows needs neither Python nor glslang. Under `if(BO1_ARCH_64 AND BO1_VULKAN)` on win32
  platforms, `win64-msvc` builds `GFX_D3D9EMU_FILES` (without `d3dx9emu.cpp`: D3DX stays `d3dx9.lib`'s, and its
  screenshots work on the emulated surfaces), the null and Vulkan backends, and defines `BO1_WIN_VULKAN`.
  `win32-msvc` builds none of it. Windows has no glslang: the Khronos release 16.6.0 (`glslang.exe`, the same version
  as WSL's, so the same SPIR-V) unpacked in `C:\SDKs\glslang-16.6.0`, which `find_program` looks in.
- MSVC portability of the frontend and the backends: `BO1_PRINTF_FORMAT` instead of `__attribute__((format))`,
  `std::countr_zero`/`std::countl_zero` instead of `__builtin_ctz`/`__builtin_clz`, `__FUNCSIG__` for `Unemulated`'s
  name, `NOMINMAX` on these files, `#undef DrawState` (winuser.h's macro renamed `gb::DrawState`), a no-op
  `Bo1LoadScope` (`platform/load_profile.h`, `#elif defined(BO1_WIN_VULKAN)`).
- The emulator's `Direct3DCreate9`/`Direct3DCreate9Ex` are `Bo1Emu_*` on `_WIN32` (a macro in
  `d3d9emu_direct3d.cpp`): `d3d9.lib`'s keep their names, the engine keeps calling them by default.
- Hosts in `src/platform/windows/`: `win_d3d9host.cpp` (primary monitor's modes, the game's `HWND`, `shaders.spv`
  beside the exe, `BO1_UPSCALE*` as on posix) and `win_vkhost.cpp` (`VK_KHR_win32_surface`, looked up with
  `vkGetInstanceProcAddr` since volk is built without platform defines).
- `r_mod_gfxApi` (`d3d9` default, `vulkan`; archived and latched, registered only with `BO1_WIN_VULKAN`), read in
  `R_PreCreateWindow`: `Bo1_EmulatedDirect3D` (9Ex for the headless client). Without `shaders.spv` or without a
  Vulkan driver it logs why and the system's Direct3D 9 takes over. `tools/codediff.py` on mingw32-gcc: `r_init.cpp`,
  `r_dvars.cpp` and `db_file_load.cpp` identical.
- Bink is a stub on win64 (`BO1_OFFLINE`), so `dx9rad3d.cpp` never runs; `win_configure.cpp` keeps the system's D3D9.
- ZmClient: Launch view (F4), "API graphique": `+set r_mod_gfxApi d3d9|vulkan` (always, the dvar is archived), and
  `BO1_GFX_BACKEND=vulkan` in the environment for Linux.
- MSAA (`r_aaSamples` 4, the user's config): the RESZ depth resolve went through `vkCmdResolveImage`, which Vulkan
  allows for colour only; the Intel driver lost the device (`VK_ERROR_DEVICE_LOST`, a GPU load spike) at the first
  frame in game, while lavapipe went on. It now resolves through dynamic rendering (sample 0), point lists use
  `VK_KHR_maintenance5`, and `gb_backend_test` checks the depth resolve (47 checks, GL and Vulkan, no validation
  message). Headless runs force `r_aaSamples 1`: an MSAA run needs `headless.ps1 -ClientAA 4` (or
  `+set bo1_headless_aa 4`), without back-buffer screenshots.
- Hitches on the user's Iris Xe (lags at the start and when shooting): `vk hitch:` lines showed them all spent in
  `vkCreateGraphicsPipelines`, 100-500 ms for a single pipeline, 124 frames over 50 ms in the user's first game and
  92 in the second with the new on-disk cache (`vk_pipelines.bin`). Pipelines now compile on background threads,
  their draws skipped until ready: the same headless Kino run went from a 388 ms freeze after spawning to no frame
  over 50 ms (1 327 draws skipped in the first 10 s, then a handful). Still possible: fewer pipelines by moving the
  depth, stencil and cull state to Vulkan 1.3's dynamic state.
- Checked on the user's Intel Iris Xe: Kino on the headless client's private desktop renders on Vulkan at the 30 fps
  cap, quits cleanly; native D3D9 with the same exe unchanged; the fallback without `shaders.spv` renders on D3D9;
  with 4x MSAA, shadows and depth of field, 30 fps at ~3 400 draws a frame.

- FSR1 on win64 (2026-11-23): `r_mod_upscale` (`off`, `ultra` x1.3, `quality` x1.5, `balanced` x1.7, `performance`
  x2, AMD's factors) and `r_mod_upscaleSharpness` (0 to 2, default 0.2), latched and archived, registered with
  `BO1_WIN_VULKAN` only and active only on the emulated Direct3D. The engine ties the back buffer to the window in two
  places, `R_SetD3DPresentParameters` and `R_StoreWindowSettings` (vidConfig): both take the window's size over the
  factor (`R_ModUpscaleSize`), the windows keep theirs, `Bo1_SetUpscale` hands the frontend the window as the output,
  and `IN_MouseMove` moves the cursor from client to back buffer pixels (`Bo1_ClientToBackBuffer`). The `BO1_UPSCALE*`
  variables stay posix's. ZmClient: "FSR 1.0" and "Netteté FSR" under the Vulkan API. `tools/codediff.py`:
  `r_init.cpp`, `r_dvars.cpp`, `win_input.cpp` identical. Checked on the Iris Xe: a 1920x1080 borderless window renders
  1280x720 (`quality`) and FSR 1.0 upscales it, steady at the test's 30 fps cap.

Still to do in this step:
- FSR1 on win64 on the player's screen: the mouse in the menus and the image itself (a headless run's screenshot reads
  the back buffer, not the upscaled output).
- `shaders.spv` for players: the install's conversion (ZmClient's Installation view, `ffconv`) must also make the
  SPIR-V pack, with a redistributable glslang/spirv-val in the Windows package, and the pack compressed (477.6 MB).
- The cyan glow of Kino's ticket counter (lobby, left arch) is missing on Vulkan and GL alike, present with native D3D9
  (and with D3D9 run on the same exe): a frontend difference older than Vulkan, to explain.
- **NVIDIA and AMD on the user's machines.**
- `win32-msvc` builds once before the merge.

## Step 6 — Arm ASR (after the Windows port) — in progress
Arm Accuracy Super Resolution (`github.com/arm/accuracy-super-resolution`, generic library, MIT) is FSR 2.2.2
optimised for mobile GPUs:
- it takes FSR2's inputs (colour, depth, motion vectors, jitter, optional reactive mask);
- it has Quality / Balanced / Performance shader presets, chosen independently of the upscaling ratio;
- it ships a stand-alone Vulkan backend with prebuilt shaders, and a "tight integration" in which the engine
  implements `FfxmInterface` (also a GLES 3.2 mode);
- most passes are fragment shaders; the luminance pyramid and the lock pass stay compute.

1. Split the scene from the HUD in the engine: the 3D scene at the render resolution, the 2D at the output resolution.
   This also gives FSR1's variant B (a native-resolution HUD). 2-3 sessions.
   **Done (2026-11-23), in the frontend rather than in the engine's render targets.** The engine renders as before at
   the back buffer's size and makes one call, `Bo1Emu_SceneComplete` (`src/gfx_d3d9emu/d3d9emu_scene.h`) at the end
   of `RB_Draw3D` (`rb_backend.cpp`, under `!_WIN32 || BO1_WIN_VULKAN`, and on win64 only while the emulated
   Direct3D is the one in use: `tools/codediff.py` identical). There every view's scene, post effects included, is in
   the back buffer and no 2D has been drawn yet: the HUD of each view comes after, in `RB_Draw3DCommon`. The frontend
   upscales the scene with FSR 1.0 into an output-size target and draws the rest of the frame there, the engine's
   back-buffer viewports, scissors, clears and copies scaled (docs/RENDERER.md, "Upscaling"). Frames without a scene
   are upscaled whole as before. It works on every backend of the frontend: GL, Vulkan and deko3d on the Switch (540p
   and 480p get a sharp 720p HUD). Checked:
   - `d3d9emu_test` (the redirected pass, scaled viewport and clear rects, the presented target, the screenshot of the
     last frame), `gb_gl_test`, `gb_vk_test`;
   - a headless Kino on win64 Vulkan, 1280x720 to 1920x1080 (`quality`): the log's "the 3D scene is upscaled before
     the 2D", the HUD in place on the back-buffer screenshot, no validation or device error.

   Still to see on the player's screen: the HUD's sharpness itself (a headless screenshot reads the frame brought
   back to the back buffer's size), and the Switch on the console. The upscaler ASR will replace sits at this same
   call, so its inputs (scene colour and depth at the render resolution) are ready there.
2. **Done (2026-11-23)**, with point 3 wired end to end: `r_mod_upscaler` (`fsr1`, `asr_quality`, `asr_balanced`,
   `asr_performance`; `BO1_UPSCALE=asr|asr_balanced|asr_performance` on posix) picks Arm ASR for `r_mod_upscale`'s
   factor. `R_RenderScene` adds `Bo1Emu_TemporalJitter`'s offset (FSR 2's Halton 2/3 sequence and phase count, in
   the frontend so that GL and Switch builds need no ASR) to the main view's projection `[2][0]`/`[2][1]`, which an
   ordinary projection leaves at 0. `RB_Draw3D` hands `Bo1Emu_SceneComplete` that camera (jittered view-projection,
   its inverse, the projection, near plane, vertical field of view) when the frame is one plain view. The frontend
   (`d3d9emu_temporal.cpp`) then copies the scene to RGBA8 and the depth buffer last drawn with a back-buffer-sized
   target, runs one full-screen pass that writes the camera's motion (this frame's clip space to the previous
   frame's, homogeneous so the sky moves with rotation only, jitter included: ASR's jitter cancellation is on) into
   RG16F and the depth into R32F, calls `gb::TemporalUpscale`, and copies the result into the output-size target the
   2D then goes to. Without a camera, the caps or after a failure, FSR 1.0 as before. `tools/codediff.py`:
   `r_scene.cpp`, `rb_backend.cpp`, `r_init.cpp`, `r_dvars.cpp` identical. Checked: `d3d9emu_test` (jitter, copies,
   motion pass, the upscale's inputs and reset flag, the history on the next frame), and Kino headless on the user's
   Iris Xe, 1280x720 to 1920x1080, `asr_quality`: "Arm ASR (quality shaders)" in the log, a clean frame with the
   HUD, 28-43 fps over 110 s against 27-41 with FSR 1.0 in the same test. Not yet: the viewmodel and zombies get
   the camera's motion (ghosting possible on them), a split screen falls back to FSR 1.0 on a jittered frame, the
   mip bias is not lowered; the image in motion is the player's to judge.
   **Reactive mask done (2026-11-23)**: `RB_StandardDrawCommands` brackets `R_DrawEmissive` (particles, smoke, glows,
   muzzle flashes) with `Bo1Emu_SceneTransparents(device, false/true)` (`rb_draw3d.cpp`, guarded, plain views only).
   The frontend copies the scene's target to RGBA8 before and after those draws and one pass
   (`shaders/temporal_reactive.glsl`) writes an R8 mask: the largest component's change, minus 0.08, times 2.5, at
   most 0.9 (FSR 2's advice for blended effects). The 0.08 dead zone is measured: Kino has a full-screen emissive
   layer that changes every pixel by about 0.06, and without it the whole screen read 0.125 (99 % of the pixels),
   which would cost the whole image some of its anti-aliasing; with it the median is 0 and the lamp's glow keeps
   0.5-0.9. A frame without both calls (split screen, missile camera, a multisampled scene) has no mask; the last one
   is never reused. Checked: `d3d9emu_test` (two copies, the R8 pass, `r=` the mask in the upscale, none on the
   next frame without the calls), `gb_vk_test` with the mask on the last 4 frames under the validation layers (no new
   message), and Kino headless on the Iris Xe with the mask blitted over the output for one run (not committed).
   Original plan of this point: jitter (`ffxmFsr2GetJitterOffset`) in the projection while the temporal upscaler is on. Motion vectors for the
   **camera only**, from the depth and the previous frame's view-projection, in a full-screen pass. A reactive mask
   (`ffxmFsr2ContextGenerateReactiveMask`, or the particles' alpha). Leave the view model out. 2 sessions.
3. **Backend side done (2026-11-23)**: `gb::TemporalUpscale(const TemporalUpscaleDesc &)` and
   `Caps::temporalUpscale` (`gfx_backend.h`). Null records and checks it, GL and deko3d return false. Vulkan runs Arm
   ASR (`third_party/arm_asr`, generic library `0501f49`) with its standalone Vulkan backend and prebuilt 16-bit SPIR-V
   on the backend's own device and command buffer: our images stay in `GENERAL`, which ASR's generic-read and
   unordered-access states map to, and it puts them back there after each dispatch. The device enables what those
   shaders need when it has all of it, and only then reports the caps: `shaderFloat16`, `shaderInt16`,
   `shaderSubgroupExtendedTypes`, `shaderStorageImageExtendedFormats`, `fragmentStoresAndAtomics`, quad subgroup
   operations in fragment and compute shaders. ASR has no BGRA format: inputs and output are RGBA8, R32F depth, RG16F
   motion. One fix in ASR (its README): memory for a unified-memory device. `gb_vk_test` upscales a still two-colour
   scene 64 to 128 over 8 jittered frames on lavapipe, halves in place, no validation error; ASR's own shaders give
   format-operand warnings on its internal storage images (R32f declared, R8/R16F images), left as they are.
   Original plan of this point: contract addition `gb::Upscale(const UpscaleDesc &)` and a `Caps` flag, through the
   checklist in `docs/RENDERER.md`:
   - null implements it and GL reports the flag as absent;
   - Vulkan uses ASR's Vulkan backend on the backend's own `VkDevice`;
   - check `shaderFloat16` (`VK_KHR_shader_float16_int8`) and build a 32-bit permutation (`FFXM_HALF 0`) for GPUs
     without it (older NVIDIA, AMD Polaris).

   2 sessions.
4. Optional, Switch: ASR's tight integration on deko3d (ASR's GLSL through uam and `UseMesaSchedule`, the two compute
   passes added to `gb_deko3d.cpp`). **A prototype measured on the console first.** Arm reports 2.9-5.3 ms at 2400x1080
   on Immortalis GPUs. On the Tegra X1 at 720p the cost may eat what 540p saves, so only a console measurement
   decides. 3-5 sessions.
   **Asked by the user (2026-11-23). First finding:** uam 1.1.0 (Mesa's GL GLSL front end) rejects every ASR shader
   as written: `GL_EXT_samplerless_texture_functions`, `GL_EXT_shader_explicit_arithmetic_types` (float16_t) and
   separate texture/sampler objects in descriptor sets are Vulkan GLSL only (tried on the 7 passes, preprocessed with
   `glslangValidator -E`). The work, in order:
   1. A GL-dialect variant of ASR's GPU glue (`include/gpu/ffxm_core_glsl.h`, `fsr2/ffxm_fsr2_callbacks_glsl.h`,
      the passes' resource declarations) in `src/gfx_backend/deko3d/asr/`, never editing `third_party/arm_asr`:
      combined samplers at deko3d's per-stage bindings, `FFXM_HALF 0` (the 32-bit paths; uam has no float16 type),
      quad operations replaced where uam lacks `GL_KHR_shader_subgroup_quad`, images with explicit formats.
      Checked by compiling every permutation `getPipelinePermutationFlags` can ask for with uam (and `UseMesaSchedule`
      on the result), then on GL first: the same GLSL through the GL backend would give a desktop reference.
   2. A deko3d `FfxmInterface` (the 15 callbacks the Vulkan backend has in `ffxm_vk.cpp`): resources from the
      backend's pools, compute and graphics pipelines from embedded DKSH, the jobs (clear, copy, compute dispatch,
      full-screen draw) recorded into the frame's command buffer with the barriers `gb_deko3d.cpp` already uses.
      `Caps::temporalUpscale` on deko3d then, and the start menu's 540p offers ASR.
   3. Ryujinx for correctness (it runs deko3d), **the console for the cost**: the user's `perf:` line at 540p with
      FSR 1.0 against ASR quality and performance. Kept only if it fits the frame budget (GPU 22-29 ms today).

Known limit: with camera-only motion vectors, zombies and other animated models may ghost. Per-object motion vectors
would mean changing every skinned material's generated shaders, which is out of scope.

## Step 7 — SSAA and native AA (rendering above the window's resolution) — done
Asked by the user (2026-11-23): let the game render larger than the screen or the window, for image quality on GPUs
with headroom. Two modes:
- **SSAA** (supersampling): the inverse of FSR1's render scale. The back buffer is the window's size times a factor above
  1 (1.5, 2; `R_ModUpscaleSize` with factors below 1 on win64, the same output/back buffer split on posix), and the
  frontend reduces it into the window at Present with a proper downsampling filter: a box filter for a whole factor,
  a separable Lanczos or bicubic one otherwise (a plain bilinear `Blit` aliases above 2x). It works on every emulated
  backend (GL, Vulkan, deko3d) since it lives in the frontend, like FSR1; the cost is the fill rate (2x = 4 times the
  pixels), so the Switch only gets it if a console measurement allows it.
- **Native AA**: ASR (step 6) at a 1:1 ratio, its temporal accumulation used as anti-aliasing at the window's size
  (AMD's and Arm's "native AA" mode). Needs step 6's jitter, motion vectors and reactive mask, so it follows it.
  **Done (2026-11-23)**: `r_mod_upscale native` (factor 1, `R_ModUpscaleSize` now says whether a mode asks for the
  upscaler) with `r_mod_upscaler asr_*`; the frontend accepts an output of the back buffer's own size only when the
  temporal upscaler is asked for (`ChooseOutput`; with FSR 1.0 it logs and does nothing). Frames without a scene go
  through FSR 1.0 at 1:1 (RCAS only sharpens). ZmClient: "Natif (anti-aliasing ASR)". `d3d9emu_test` checks both
  cases; Kino headless on the Iris Xe, 1920x1080 native with ASR quality: a clean frame, about 30 fps (the run's
  cap); `r_init.cpp`, `r_dvars.cpp` identical on 32-bit. The reactive mask followed (step 6, item 2).
- **SSAA done (2026-11-23)**: `r_mod_upscale ssaa_1.5x` and `ssaa_2x` (factors 1/1.5 and 1/2 in
  `R_ModUpscaleSize`: a 1920x1080 window renders 2880x1620 or 3840x2160). `ChooseOutput` takes an output smaller than
  the back buffer on both axes as supersampling (never with the temporal upscaler, which only enlarges: logged, no
  jitter); the upscaler averages the scene down in one pass (`shaders/downsample.glsl`): each output pixel is the mean
  of the source pixels under it, weighted by the part of each it covers, a box filter exact at any ratio (bilinear
  reads only 4 of the 9 pixels a 1.5x pixel covers). The planned Lanczos was not needed for these two factors. The 2D
  still goes to the output-size target after `SceneComplete`, so it costs nothing extra. On posix,
  `BO1_UPSCALE_OUTPUT` smaller than the back buffer does the same. ZmClient: "Suréchantillonnage x1,5 / x2 (SSAA)",
  the method and sharpness rows greyed. Checked: `d3d9emu_test` (1280x960 to 640x480 in one draw, no jitter, an
  output larger on one axis only refused), Kino headless on the Iris Xe at `ssaa_2x`: 3840x2160 to 1920x1080, clean
  edges, crosshair in place, ~30 fps (the run's cap). The Switch start menu does not offer it (the console is
  fill-rate bound already).
- Points to check: the engine's render targets sized from vidConfig (post effects, shadow maps) at 2x the window;
  the 2D HUD (rendered at the back buffer's size, so sharp at 2x, but text sizes follow vidConfig); the mouse mapped
  into back buffer pixels (`Bo1_ClientToBackBuffer` already handles any ratio); memory (a 4K back buffer with MSAA);
  MSAA and SSAA together (allowed, but SSAA alone may be enough).
- Settings: `r_mod_upscale` gains `ssaa1.5` and `ssaa2` (or a separate `r_mod_renderScale`), `native` under ASR;
  ZmClient and the Switch start menu offer them.
- Checks: `upscale_gl_test`-style host test of the downsampling filter (a 2x checkerboard reduces to flat grey, an edge
  keeps its position); screenshots on win64 and Linux; frame times at 1.5x and 2x on the user's Iris Xe.
- Estimate: 1-2 sessions for SSAA, 1 for native AA once ASR works.

## Step 8 — OpenBSD (last, after ASR and SSAA)
- Cross-build with `BO1_VULKAN` (`~/cross-pkg-openbsd`, mirror `/home/james/build/bo1-openbsd`). volk loads
  `libvulkan.so` at run time and the headers are vendored: no new build dependency.
- Packaging is unchanged apart from a README line.
- Never run on real OpenBSD by us: Vulkan there is "for a player to try", and GL stays the default.
- Estimate: 0.5-1 session.

## Totals
| Part | Sessions |
|---|---|
| FSR1 (step 1) | 1-2 |
| Vulkan on Linux and win64 (steps 2-5) | 9-12 |
| ASR on PC (step 6, items 1-3) | 6-7 |
| ASR on the Switch (step 6, item 4) | +3-5 |
| SSAA and native AA (step 7) | 2-3 |
| Vulkan on OpenBSD (step 8, last) | 0.5-1 |

## Working rules for this plan
- Work in a sibling worktree `../BO-Zombies_switch_vulkan` (every step touches 5+ files); merge into `switch` step by
  step.
- Build posix from the ext4 mirror; between merges build only `win64-msvc`; build `win32-msvc` before each merge.
- `src/gfx_d3d9emu/` stays free of Vulkan calls; the Vulkan backend talks only to its host and to the contract.

## Assumptions to confirm
- FSR1 starts with variant A (whole frame, HUD included); variant B (native HUD) comes with ASR's scene/HUD split.
- On Windows the default stays native D3D9; Vulkan is chosen in ZmClient or by the dvar.
- OpenBSD provides `libvulkan` and Mesa's Vulkan drivers (radv, anv) on the players' machines.
