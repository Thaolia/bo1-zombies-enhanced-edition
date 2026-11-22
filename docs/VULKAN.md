# Vulkan backend and upscalers — plan

Status (2026-11-22): step 1 (FSR1) done, checked on the host, on Ryujinx and on the user's console; steps 2 (SPIR-V
pack) and 3 (Vulkan backend on Linux) done on branch `vulkan`; steps 4 (parity on Linux) and 5 (win64) in
progress; steps 6-7 planned. Each step updates this file, `docs/RENDERER.md` and `docs/PORTING.md` (phase 9) in the session that does it.

## Goals and constraints
- A Vulkan backend behind `src/gfx_backend/gfx_backend.h`, opt-in on **Linux**, **win64** and, last of all (after ASR), **OpenBSD**.
- **OpenGL stays the default** backend on Linux and OpenBSD. On win64, native Direct3D 9 stays the default.
- **`win32-msvc` changes as little as possible**: it compiles none of the new files, and every engine edit it does see
  is guarded so its code stays identical (`tools/codediff.py`).
- Upscaling in this order:
  1. **FSR1** first (spatial, all emulated backends, the Switch included);
  2. **Arm ASR** last, after the win64 port (temporal); only Vulkan on OpenBSD comes after it.
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
- Checked on the user's Intel Iris Xe: Kino on the headless client's private desktop renders on Vulkan at the 30 fps
  cap, quits cleanly; native D3D9 with the same exe unchanged; the fallback without `shaders.spv` renders on D3D9.

Still to do in this step:
- FSR1 on win64. The Win32 surface takes the window's size and the engine sizes its back buffer to the window (the
  borderless one to the monitor): it needs a render scale in the engine (`BO1_WIN_VULKAN` only), a back buffer smaller
  than the borderless window, and the mouse mapped from the window to the back buffer.
- `shaders.spv` for players: the install's conversion (ZmClient's Installation view, `ffconv`) must also make the
  SPIR-V pack, with a redistributable glslang/spirv-val in the Windows package, and the pack compressed (477.6 MB).
- The cyan glow of Kino's ticket counter (lobby, left arch) is missing on Vulkan and GL alike, present with native D3D9
  (and with D3D9 run on the same exe): a frontend difference older than Vulkan, to explain.
- **NVIDIA and AMD on the user's machines.**
- `win32-msvc` builds once before the merge.

## Step 6 — Arm ASR (after the Windows port)
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

## Step 7 — OpenBSD (last, after ASR)
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
| Vulkan on OpenBSD (step 7, last) | 0.5-1 |

## Working rules for this plan
- Work in a sibling worktree `../BO-Zombies_switch_vulkan` (every step touches 5+ files); merge into `switch` step by
  step.
- Build posix from the ext4 mirror; between merges build only `win64-msvc`; build `win32-msvc` before each merge.
- `src/gfx_d3d9emu/` stays free of Vulkan calls; the Vulkan backend talks only to its host and to the contract.

## Assumptions to confirm
- FSR1 starts with variant A (whole frame, HUD included); variant B (native HUD) comes with ASR's scene/HUD split.
- On Windows the default stays native D3D9; Vulkan is chosen in ZmClient or by the dvar.
- OpenBSD provides `libvulkan` and Mesa's Vulkan drivers (radv, anv) on the players' machines.
