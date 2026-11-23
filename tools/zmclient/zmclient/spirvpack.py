"""shaders.spv from shaders.pack: the GLSL ffconv wrote, compiled to Vulkan SPIR-V by glslang (docs/VULKAN.md, step 2).

tools/make_dist.sh runs it through tools/ffconv/gen/make_spirv_pack.py; ZmClient runs it after converting the
player's zones (gamesetup.py), with the glslang.exe the Windows package carries or the system's glslang on Linux.

Reads the BO1GLSL1 pack and writes a BO1SPRV1 pack with the same header/entry layout (src/gfx_d3d9emu/shader_pack.h),
each payload a SPIR-V module followed by one NUL byte for the pack's NUL-termination check, as make_dksh_pack.py does.

The GLSL is never edited. glslang targets Vulkan 1.1 and moves the uniform blocks past the samplers, since Vulkan has
one binding space per descriptor set where GL has one per resource kind: descriptor set 0 holds the samplers at their
`s#` (bindings 0-15), the vertex constants at 16 and the pixel constants at 17 (`--shift-UBO-binding 16`). Every module
is then checked: spirv-val accepts it (when it is given: the packages do not carry it), and its bindings are where that
layout puts them, each used once. A shader that fails is dropped and listed.
"""
import concurrent.futures
import os
import shutil
import struct
import subprocess
import tempfile
import threading

HEADER = struct.Struct('<8sII')   # magic, version, count
ENTRY = struct.Struct('<QIIII')   # hash, stage, offset, size, reserved
STAGES = {0: 'vert', 1: 'frag'}
TARGET_ENV = 'vulkan1.1'
UBO_SHIFT = 16
SAMPLER_BINDINGS = range(16)
# SPIR-V: OpDecorate, and its Binding / DescriptorSet decorations; OpVariable and its Uniform / UniformConstant classes.
OP_DECORATE, DECORATION_BINDING, DECORATION_SET = 71, 33, 34
OP_VARIABLE, CLASS_UNIFORM_CONSTANT, CLASS_UNIFORM = 59, 0, 2
# No console window per glslang run when a GUI-less Windows program (ZmClient) starts thousands of them.
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class PackError(Exception):
    """shaders.pack is not a pack this code reads."""


def read_glsl_pack(path):
    """[(hash, stage, glsl bytes)] of a version 1 BO1GLSL1 pack."""
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < HEADER.size:
        raise PackError(f'{path}: too short for a shaders.pack')
    magic, version, count = HEADER.unpack_from(data, 0)
    if magic != b'BO1GLSL1' or version != 1:
        raise PackError(f'{path}: not a version 1 BO1GLSL1 shaders.pack')
    if HEADER.size + count * ENTRY.size > len(data):
        raise PackError(f'{path}: its {count} entries run past the end of the file')
    out = []
    for i in range(count):
        h, stage, offset, size, _ = ENTRY.unpack_from(data, HEADER.size + i * ENTRY.size)
        if stage not in STAGES:
            raise PackError(f'{path}: entry {h:016x} has unknown stage {stage}')
        if offset + size > len(data):
            raise PackError(f'{path}: entry {h:016x} runs past the end of the file')
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


def compile_one(glslang, spirv_val, work, shader):
    """(hash, stage, SPIR-V or None, the problem or None)."""
    h, stage, glsl = shader
    src = os.path.join(work, f'{h:016x}.{STAGES[stage]}')
    dst = src + '.spv'
    with open(src, 'wb') as f:
        f.write(glsl)
    proc = subprocess.run([glslang, '-V', '--target-env', TARGET_ENV, '--shift-UBO-binding', str(UBO_SHIFT),
                           '-S', STAGES[stage], src, '-o', dst], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, creationflags=_NO_WINDOW)
    if proc.returncode or not os.path.exists(dst):
        lines = [l for l in (proc.stdout + proc.stderr).splitlines() if 'ERROR' in l]
        return (h, stage, None, lines[0] if lines else 'glslang failed')
    if spirv_val:
        proc = subprocess.run([spirv_val, '--target-env', TARGET_ENV, dst], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, creationflags=_NO_WINDOW)
        if proc.returncode:
            return (h, stage, None, 'spirv-val: ' + ((proc.stderr or proc.stdout).strip().splitlines() or ['?'])[0])
    with open(dst, 'rb') as f:
        spirv = f.read()
    os.remove(src)
    os.remove(dst)
    problem = binding_problems(spirv, stage)
    return (h, stage, None if problem else spirv, problem or None)


def write_spirv_pack(path, good):
    """`good`: [(hash, stage, SPIR-V)] sorted by hash. Written beside `path`, then moved over it."""
    entries = bytearray()
    payloads = bytearray()
    base = HEADER.size + len(good) * ENTRY.size
    for h, stage, spv in good:
        entries += ENTRY.pack(h, stage, base + len(payloads), len(spv), 0)
        payloads += spv + b'\x00'
    part = path + '.part'
    with open(part, 'wb') as f:
        f.write(HEADER.pack(b'BO1SPRV1', 1, len(good)))
        f.write(entries)
        f.write(payloads)
    os.replace(part, path)
    return base + len(payloads)


def build(glsl_pack, spirv_pack, glslang, spirv_val=None, jobs=None, progress=None, cancelled=None):
    """Compiles every shader of `glsl_pack` into `spirv_pack`. `progress(done, total)` is called from worker threads;
    `cancelled()` true stops it before the pack is written. Returns (shaders written, bytes, [(hash, stage,
    problem)]), or None when cancelled. Raises PackError for an unreadable pack, OSError when glslang cannot run."""
    shaders = read_glsl_pack(glsl_pack)
    total = len(shaders)
    done = [0]
    lock = threading.Lock()

    def one(shader):
        if cancelled and cancelled():
            return None
        result = compile_one(glslang, spirv_val, work, shader)
        if progress:
            with lock:
                done[0] += 1
                at = done[0]
            progress(at, total)
        return result

    with tempfile.TemporaryDirectory(prefix='bo1spirv') as work, \
            concurrent.futures.ThreadPoolExecutor(jobs or os.cpu_count() or 1) as pool:
        results = list(pool.map(one, shaders))
    if cancelled and cancelled():
        return None
    good = sorted(((h, stage, spv) for (h, stage, spv, _) in results if spv is not None), key=lambda e: e[0])
    failures = [(h, stage, err) for (h, stage, spv, err) in results if spv is None]
    size = write_spirv_pack(spirv_pack, good)
    return len(good), size, failures


def find_glslang(dist_root):
    """The glslang a package uses: the one beside the program (the Windows package carries glslang.exe), else the
    system's (Linux: the glslang-tools package). None when there is none."""
    names = ('glslang.exe',) if os.name == 'nt' else ('glslang', 'glslangValidator')
    for name in names:
        path = os.path.join(dist_root, name)
        if os.path.isfile(path):
            return path
    for name in ('glslang', 'glslangValidator'):
        found = shutil.which(name)
        if found:
            return found
    return None
