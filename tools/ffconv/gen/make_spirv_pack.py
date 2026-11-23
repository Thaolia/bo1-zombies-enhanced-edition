#!/usr/bin/env python3
"""ffconv --spirv: compile the GLSL in a shaders.pack to Vulkan SPIR-V offline, for the Vulkan backend
(docs/VULKAN.md, step 2).

    tools/ffconv/gen/make_spirv_pack.py OUT_DIR/shaders.pack OUT_DIR/shaders.spv [--glslang PATH] [--jobs N]

Reads the BO1GLSL1 pack and writes a BO1SPRV1 pack with the same header/entry layout (src/gfx_d3d9emu/shader_pack.h),
each payload a SPIR-V module followed by one NUL byte for the pack's NUL-termination check, as make_dksh_pack.py does.

The GLSL is never edited. glslang targets Vulkan 1.1 and moves the uniform blocks past the samplers, since Vulkan has
one binding space per descriptor set where GL has one per resource kind: descriptor set 0 holds the samplers at their
`s#` (bindings 0-15), the vertex constants at 16 and the pixel constants at 17 (`--shift-UBO-binding 16`). Every module
is then checked: spirv-val accepts it, and its bindings are where that layout puts them, each used once. A shader that
fails is dropped and listed, and the exit status is 1.
"""
import argparse
import concurrent.futures
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HEADER = struct.Struct('<8sII')   # magic, version, count
ENTRY = struct.Struct('<QIIII')   # hash, stage, offset, size, reserved
STAGES = {0: 'vert', 1: 'frag'}
TARGET_ENV = 'vulkan1.1'
UBO_SHIFT = 16
SAMPLER_BINDINGS = range(16)
# SPIR-V: OpDecorate, and its Binding / DescriptorSet decorations; OpVariable and its Uniform / UniformConstant classes.
OP_DECORATE, DECORATION_BINDING, DECORATION_SET = 71, 33, 34
OP_VARIABLE, CLASS_UNIFORM_CONSTANT, CLASS_UNIFORM = 59, 0, 2


def read_glsl_pack(path):
    with open(path, 'rb') as f:
        data = f.read()
    magic, version, count = HEADER.unpack_from(data, 0)
    if magic != b'BO1GLSL1' or version != 1:
        raise SystemExit(f'{path}: not a version 1 BO1GLSL1 shaders.pack')
    out = []
    for i in range(count):
        h, stage, offset, size, _ = ENTRY.unpack_from(data, HEADER.size + i * ENTRY.size)
        if stage not in STAGES:
            raise SystemExit(f'{path}: entry {h:016x} has unknown stage {stage}')
        out.append((h, stage, data[offset:offset + size]))
    return out


def binding_problems(spirv, stage):
    """What is wrong with a module's resource bindings, or '' (the layout in the module docstring)."""
    if len(spirv) < 20 or len(spirv) % 4 or struct.unpack_from('<I', spirv, 0)[0] != 0x07230203:
        return 'not a little-endian SPIR-V module'
    words = struct.unpack_from(f'<{len(spirv) // 4}I', spirv)
    binding, dset, storage = {}, {}, {}
    at = 5
    while at < len(words):
        count, opcode = words[at] >> 16, words[at] & 0xFFFF
        if count == 0 or at + count > len(words):
            return 'truncated instruction'
        if opcode == OP_DECORATE and count >= 4 and words[at + 2] in (DECORATION_BINDING, DECORATION_SET):
            (binding if words[at + 2] == DECORATION_BINDING else dset)[words[at + 1]] = words[at + 3]
        elif opcode == OP_VARIABLE and count >= 4:
            storage[words[at + 2]] = words[at + 3]
        at += count
    seen = set()
    for var, slot in binding.items():
        kind = storage.get(var)
        if dset.get(var, 0) != 0:
            return f'binding {slot} is in descriptor set {dset[var]}'
        if kind == CLASS_UNIFORM:
            want = UBO_SHIFT + (0 if stage == 0 else 1)
            if slot != want:
                return f'a uniform block at binding {slot}, not {want}'
        elif kind == CLASS_UNIFORM_CONSTANT:
            if slot not in SAMPLER_BINDINGS:
                return f'a sampler at binding {slot}'
        else:
            return f'binding {slot} on a variable of storage class {kind}'
        if slot in seen:
            return f'binding {slot} used twice'
        seen.add(slot)
    return ''


def compile_one(tools, work, shader):
    glslang, spirv_val = tools
    h, stage, glsl = shader
    src = os.path.join(work, f'{h:016x}.{STAGES[stage]}')
    dst = src + '.spv'
    with open(src, 'wb') as f:
        f.write(glsl)
    proc = subprocess.run([glslang, '-V', '--target-env', TARGET_ENV, '--shift-UBO-binding', str(UBO_SHIFT),
                           '-S', STAGES[stage], src, '-o', dst], capture_output=True, text=True)
    if proc.returncode or not os.path.exists(dst):
        lines = [l for l in (proc.stdout + proc.stderr).splitlines() if 'ERROR' in l]
        return (h, stage, None, lines[0] if lines else 'glslang failed')
    proc = subprocess.run([spirv_val, '--target-env', TARGET_ENV, dst], capture_output=True, text=True)
    if proc.returncode:
        return (h, stage, None, 'spirv-val: ' + ((proc.stderr or proc.stdout).strip().splitlines() or ['?'])[0])
    with open(dst, 'rb') as f:
        spirv = f.read()
    problem = binding_problems(spirv, stage)
    return (h, stage, None if problem else spirv, problem or None)


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

    shaders = read_glsl_pack(opts.glsl_pack)
    print(f'{opts.glsl_pack}: {len(shaders)} GLSL shaders -> SPIR-V for {TARGET_ENV} (jobs={opts.jobs})')
    with tempfile.TemporaryDirectory() as work, concurrent.futures.ThreadPoolExecutor(opts.jobs) as pool:
        results = list(pool.map(lambda s: compile_one((opts.glslang, opts.spirv_val), work, s), shaders))

    good = sorted(((h, stage, spv) for (h, stage, spv, _) in results if spv is not None), key=lambda e: e[0])
    failures = [(h, stage, err) for (h, stage, spv, err) in results if spv is None]

    entries = bytearray()
    payloads = bytearray()
    base = HEADER.size + len(good) * ENTRY.size
    for h, stage, spv in good:
        entries += ENTRY.pack(h, stage, base + len(payloads), len(spv), 0)
        payloads += spv + b'\x00'
    with open(opts.spirv_pack, 'wb') as f:
        f.write(HEADER.pack(b'BO1SPRV1', 1, len(good)))
        f.write(entries)
        f.write(payloads)

    size_mb = (base + len(payloads)) / (1 << 20)
    print(f'{opts.spirv_pack}: {len(good)} SPIR-V shaders, {size_mb:.1f} MB, {len(failures)} rejected')
    for h, stage, err in failures[:20]:
        print(f'  {h:016x}.{STAGES[stage]}: {err}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
