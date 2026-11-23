# glslang (licence only)

`LICENSE.txt` is glslang's licence file at tag `16.6.0` (https://github.com/KhronosGroup/glslang, `LICENSE.txt`).
No glslang source is vendored here: `tools/make_dist.sh` puts the `glslang.exe` of Khronos' 16.6.0 Windows release
(`C:\SDKs\glslang-16.6.0\bin` on a PC, `build/glslang/windows` in the release CI) into the Windows package as
`glslang.exe`, with this file as `glslang-LICENSE.txt`. ZmClient runs it to compile the player's `shaders.pack` to
`shaders.spv` for the Vulkan renderer (`tools/zmclient/zmclient/spirvpack.py`). On Linux, ZmClient uses the system's
glslang (the `glslang-tools` package).
