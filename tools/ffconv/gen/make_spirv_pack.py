#!/usr/bin/env python3
"""ffconv --spirv: compile the GLSL in a shaders.pack to Vulkan SPIR-V offline, for the Vulkan backend
(docs/VULKAN.md, step 2).

    tools/ffconv/gen/make_spirv_pack.py OUT_DIR/shaders.pack OUT_DIR/shaders.spv [--glslang PATH] [--jobs N]

The work is ZmClient's tools/zmclient/zmclient/spirvpack.py (its docstring has the layout), shared so that
tools/make_dist.sh and ZmClient, which compiles the pack it converts for the player, write the same shaders.spv. Here
spirv-val is required and checks every module; a shader that fails is dropped and listed, and the exit status is 1.
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'zmclient'))
from zmclient import spirvpack  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('glsl_pack')
    parser.add_argument('spirv_pack')
    parser.add_argument('--glslang', default=shutil.which('glslangValidator') or 'glslangValidator')
    parser.add_argument('--spirv-val', default=shutil.which('spirv-val') or 'spirv-val')
    parser.add_argument('--jobs', type=int, default=os.cpu_count())
    opts = parser.parse_args()
    for tool in (opts.glslang, opts.spirv_val):
        if not shutil.which(tool):
            raise SystemExit(f'{tool} not found (glslang-tools and spirv-tools)')

    try:
        count = len(spirvpack.read_glsl_pack(opts.glsl_pack))
    except spirvpack.PackError as e:
        raise SystemExit(str(e))
    print(f'{opts.glsl_pack}: {count} GLSL shaders -> SPIR-V for {spirvpack.TARGET_ENV} (jobs={opts.jobs})')
    good, size, failures = spirvpack.build(opts.glsl_pack, opts.spirv_pack, opts.glslang, opts.spirv_val, opts.jobs)
    print(f'{opts.spirv_pack}: {good} SPIR-V shaders, {size / (1 << 20):.1f} MB, {len(failures)} rejected')
    for h, stage, err in failures[:20]:
        print(f'  {h:016x}.{spirvpack.STAGES[stage]}: {err}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
