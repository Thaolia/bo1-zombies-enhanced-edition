# AMD FidelityFX Super Resolution 1.0

`ffx_a.h` and `ffx_fsr1.h` from https://github.com/GPUOpen-Effects/FidelityFX-FSR (`ffx-fsr/`, branch `master` at
commit `a21ffb8`), unmodified, with the repository's `license.txt` as `LICENSE` (MIT, Copyright (c) 2021 Advanced Micro
Devices, Inc.).

Nothing compiles these headers. They are the reference for the GLSL port in `src/gfx_d3d9emu/shaders/` (EASU and RCAS,
the non-packed 32-bit paths, `FsrEasuF` and `FsrRcasF` with the `APrx*` approximations of `ffx_a.h`) and for the
constant setup in `src/gfx_d3d9emu/d3d9emu_upscale.cpp` (`FsrEasuCon`, `FsrRcasCon`). The frontend upscales the
presented frame with them (`docs/RENDERER.md`, "Upscaling").
