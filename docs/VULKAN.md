# Vulkan backend and upscalers — plan

Status (2026-11-22): step 1 (FSR1) done, checked on the host, on Ryujinx and on the user's console; steps 2-7
planned. Each step updates this file, `docs/RENDERER.md` and `docs/PORTING.md` (phase 9) in the session that does it.

## Goals and constraints
- A Vulkan backend behind `src/gfx_backend/gfx_backend.h`, opt-in on **win64**, **Linux** and **OpenBSD**.
- **OpenGL stays the default** backend on Linux and OpenBSD. On win64, native Direct3D 9 stays the default.
- **`win32-msvc` changes as little as possible**: it compiles none of the new files, and every engine edit it does see
  is guarded so its code stays identical (`tools/codediff.py`).
- Upscaling in this order:
  1. **FSR1** first (spatial, all emulated backends, the Switch included);
  2. **Arm ASR** last, at the end of the Vulkan port (temporal).
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

## Step 2 — SPIR-V pack, offline
- `tools/ffconv/gen/make_spirv_pack.py`, modelled on `make_dksh_pack.py`: glslang `-V --target-env vulkan1.1`.
  Bindings are remapped by glslang's options (`--shift-*-binding`, `--resource-set-binding`), never by editing the
  GLSL. In Vulkan, UBOs and samplers share one binding space per set.
- The output must be deterministic: two builds of the same `shaders.pack` give the same bytes.
- Checks: all 13 704 shaders plus the FSR1 ones compile, `spirv-val` accepts each module, two packs are identical.
- Estimate: 1 session.

## Step 3 — Vulkan backend on Linux (opt-in)
- `src/gfx_backend/vulkan/`, table `gb::vulkan::Table()`. Only the dispatcher (`gb_backend.cpp`) sees `BO1_GB_VULKAN`,
  as with `BO1_GB_DEKO3D`. `BO1_GFX_BACKEND=vulkan` picks it; without the variable the choice stays GL, then null.
- Vendored in `third_party/`:
  - Vulkan-Headers;
  - volk, which loads the loader at run time, so the game still starts on a machine without Vulkan;
  - Vulkan Memory Allocator.

  CMake option `BO1_VULKAN` (ON for posix x86-64).
- Host interface `gb_vk_host.h`, like `gb_gl_host.h`: instance extensions and surface creation for a window.
  Implemented on posix with SDL2 (`SDL_Vulkan_GetInstanceExtensions`, `SDL_Vulkan_CreateSurface`) in
  `src/platform/posix/`.
- D3D9 conventions:
  - row 0 on top through a negative-height viewport (Vulkan 1.1), with the front face set to match;
  - clip depth 0..1 is native;
  - `bo1_pos_fixup` is unchanged;
  - depth bias × 2^24 (2^16 on D16).
- Carried over from deko3d:
  - render targets in B5G6R5 / B5G5R5A1 fall back to RGBA8 where the format cannot be rendered to;
  - INTZ and the RESZ resolve;
  - hardware shadow compare;
  - the scissor is always on (set it to the whole target when the pipeline's scissor test is off);
  - DISCARD renames;
  - two frames in flight;
  - uploads recorded into the frame;
  - occlusion queries and timestamps;
  - `ReadTexture`.
- A `vk perf:` line every 10 s like `gl perf:`. `BO1_VK_DEBUG=1` turns on the validation layers, with their
  messages in the log.
- Checks:
  - `gb_vk_test`: `gb_gl_test`'s cases on lavapipe, without a surface (render to textures, read back);
  - `d3d9emu_test`;
  - no validation message on the main menu and on a map.
- Estimate: 4-6 sessions.

## Step 4 — Parity on Linux
- GL against Vulkan screenshots: main menu, Kino, Five, one imported BSP map. Explain every difference.
- FSR1 on Vulkan.
- The usual posix gate: a headless run against win64, paths and numbers masked.
- Estimate: 1-2 sessions.

## Step 5 — OpenBSD
- Cross-build with `BO1_VULKAN` (`~/cross-pkg-openbsd`, mirror `/home/james/build/bo1-openbsd`). volk loads
  `libvulkan.so` at run time and the headers are vendored: no new build dependency.
- Packaging is unchanged apart from a README line.
- Never run on real OpenBSD by us: Vulkan there is "for a player to try", and GL stays the default.
- Estimate: 0.5-1 session.

## Step 6 — win64: the emulated frontend and Vulkan, native D3D9 by default
- CMake: only under `if(BO1_ARCH_64)` on win32 platforms, build `GFX_D3D9EMU_FILES`, the null and the Vulkan backends
  into `win64-msvc`. `win32-msvc` builds none of them.
- A Win32 host for the frontend (`d3d9emu_host.h`, 10 functions) and a Vulkan host (`VK_KHR_win32_surface` on the
  game's `HWND`) in `src/platform/win32/`.
- Selection in `r_init.cpp`: a dvar `r_mod_gfxApi` (`d3d9` by default, `vulkan`) read before the device is created.
  The call into the emulator sits under `#if BO1_ARCH_64`, so the 32-bit code is unchanged. Check it with
  `tools/codediff.py build/mingw32-gcc src/gfx_d3d/r_init.cpp`, which must say "identical".
- To settle before writing code:
  - the emulator's `Direct3DCreate9` / `Direct3DCreate9Ex` against `d3d9.lib`'s: rename the emulator's entry points on
    Windows (macro) so both link into one exe;
  - Bink: `dx9rad3d.cpp` creates its own D3D9 and uses the fixed-function pipeline, which the frontend does not
    emulate. On the Vulkan path, Bink gets the treatment posix gives it;
  - `win_configure.cpp` (its own `Direct3DCreate9`);
  - the headless client on its private desktop.
- ZmClient: a "Graphics API: Direct3D 9 / Vulkan" setting, with FSR1 under Vulkan.
- Checks:
  - `win64-msvc` builds;
  - native D3D9 against Vulkan screenshots, same zones;
  - **NVIDIA, AMD and Intel on the user's machines**;
  - `win32-msvc` builds once before the merge.
- Estimate: 3-4 sessions.

## Step 7 — Arm ASR (end of the Vulkan port)
Arm Accuracy Super Resolution (`github.com/arm/accuracy-super-resolution`, generic library, MIT) is FSR 2.2.2
optimised for mobile GPUs:
- it takes FSR2's inputs (colour, depth, motion vectors, jitter, optional reactive mask);
- it has Quality / Balanced / Performance shader presets, chosen independently of the upscaling ratio;
- it ships a stand-alone Vulkan backend with prebuilt shaders, and a "tight integration" in which the engine
  implements `FfxmInterface` (also a GLES 3.2 mode);
- most passes are fragment shaders; the luminance pyramid and the lock pass stay compute.

1. Split the scene from the HUD in the engine: the 3D scene at the render resolution, the 2D at the output resolution.
   This also gives FSR1's variant B (a native-resolution HUD). 2-3 sessions.
2. Jitter (`ffxmFsr2GetJitterOffset`) in the projection while the temporal upscaler is on. Motion vectors for the
   **camera only**, from the depth and the previous frame's view-projection, in a full-screen pass. A reactive mask
   (`ffxmFsr2ContextGenerateReactiveMask`, or the particles' alpha). Leave the view model out. 2 sessions.
3. Contract addition: `gb::Upscale(const UpscaleDesc &)` and a `Caps` flag, through the checklist in
   `docs/RENDERER.md`:
   - null implements it and GL reports the flag as absent;
   - Vulkan uses ASR's Vulkan backend on the backend's own `VkDevice`;
   - check `shaderFloat16` (`VK_KHR_shader_float16_int8`) and build a 32-bit permutation (`FFXM_HALF 0`) for GPUs
     without it (older NVIDIA, AMD Polaris).

   2 sessions.
4. Optional, Switch: ASR's tight integration on deko3d (ASR's GLSL through uam and `UseMesaSchedule`, the two compute
   passes added to `gb_deko3d.cpp`). **A prototype measured on the console first.** Arm reports 2.9-5.3 ms at 2400x1080
   on Immortalis GPUs. On the Tegra X1 at 720p the cost may eat what 540p saves, so only a console measurement
   decides. 3-5 sessions.

Known limit: with camera-only motion vectors, zombies and other animated models may ghost. Per-object motion vectors
would mean changing every skinned material's generated shaders, which is out of scope.

## Totals
| Part | Sessions |
|---|---|
| FSR1 (step 1) | 1-2 |
| Vulkan on Linux, OpenBSD and win64 (steps 2-6) | 10-14 |
| ASR on PC (step 7, items 1-3) | 6-7 |
| ASR on the Switch (step 7, item 4) | +3-5 |

## Working rules for this plan
- Work in a sibling worktree `../BO-Zombies_switch_vulkan` (every step touches 5+ files); merge into `switch` step by
  step.
- Build posix from the ext4 mirror; between merges build only `win64-msvc`; build `win32-msvc` before each merge.
- `src/gfx_d3d9emu/` stays free of Vulkan calls; the Vulkan backend talks only to its host and to the contract.

## Assumptions to confirm
- FSR1 starts with variant A (whole frame, HUD included); variant B (native HUD) comes with ASR's scene/HUD split.
- On Windows the default stays native D3D9; Vulkan is chosen in ZmClient or by the dvar.
- OpenBSD provides `libvulkan` and Mesa's Vulkan drivers (radv, anv) on the players' machines.
