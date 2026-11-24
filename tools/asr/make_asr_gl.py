#!/usr/bin/env python3
"""Arm ASR's shaders in the GL dialect uam compiles, for the deko3d backend (docs/VULKAN.md, step 6, item 4).

    tools/asr/make_asr_gl.py [--glslang PATH] [--spirv-cross PATH] [--out DIR]

uam (Mesa's GL front end) rejects ASR's Vulkan GLSL. Each pass goes through glslang (Vulkan GLSL -> SPIR-V, FFXM_HALF 0:
uam has no 16-bit types; SPD without wave operations: uam has no subgroup quad operations), then SPIRV-Cross (SPIR-V ->
GLSL 4.50 for GL, samplers combined with their textures). GL gives uniform blocks, samplers and images separate binding
spaces, and a texture read through two samplers becomes two combined samplers on one Vulkan binding: every binding is
renumbered from 0 within its class, and asr_table.h keeps, per shader, which Vulkan resource and sampler each deko3d
slot takes (the reflection the FfxmInterface fills FfxmPipelineState from; Arm's prebuilt reflection is per 16-bit
permutation and differs).

Only the permutations BO1 can ask for are made: the context flags gb_vk.cpp uses (low-resolution motion vectors,
jitter cancellation; no HDR, no inverted depth, no FP16) with each shader quality preset and the accumulate pass with
and without sharpening. Identical outputs are written once.

The output is committed (src/gfx_backend/deko3d/asr): the Switch build then needs only uam, which it already has.
Rerun this script after updating third_party/arm_asr; never edit its output by hand.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
ASR = os.path.join(ROOT, 'third_party', 'arm_asr')
GLSL_DIR = os.path.join(ASR, 'src', 'backends', 'vk', 'shaders', 'fsr2', 'glsl')

# FfxmFsr2Pass (third_party/arm_asr/include/host/ffxm_fsr2.h) -> source, stage. The vertex shader is shared by the
# fragment passes; it gets pass id 255.
PASSES = [
    (0, 'depth_clip', 'ffxm_fsr2_depth_clip_pass_fs', 'frag'),
    (1, 'reconstruct_previous_depth', 'ffxm_fsr2_reconstruct_previous_depth_pass_fs', 'frag'),
    (2, 'lock', 'ffxm_fsr2_lock_pass', 'comp'),
    (3, 'accumulate', 'ffxm_fsr2_accumulate_pass_fs', 'frag'),
    (4, 'accumulate_sharpen', 'ffxm_fsr2_accumulate_pass_fs', 'frag'),
    (5, 'rcas', 'ffxm_fsr2_rcas_pass_fs', 'frag'),
    (6, 'compute_luminance_pyramid', 'ffxm_fsr2_compute_luminance_pyramid_pass', 'comp'),
    (7, 'generate_reactive', 'ffxm_fsr2_autogen_reactive_pass_fs', 'frag'),
    (255, 'vs', 'ffxm_fsr2_vs', 'vert'),
]
STAGE_IDS = {'vert': 0, 'frag': 1, 'comp': 2}

# FSR2_SHADER_PERMUTATION_* (third_party/arm_asr/src/components/fsr2/ffxm_fsr2_private.h)
LOW_RES_MOTION_VECTORS = 1 << 2
JITTER_MOTION_VECTORS = 1 << 3
ENABLE_SHARPENING = 1 << 5
APPLY_BALANCED_OPT = 1 << 8
APPLY_PERFORMANCE_OPT = 1 << 9
FIXED_FLAGS = LOW_RES_MOTION_VECTORS | JITTER_MOTION_VECTORS
VARIED_FLAGS = ENABLE_SHARPENING | APPLY_BALANCED_OPT | APPLY_PERFORMANCE_OPT
QUALITIES = [0, APPLY_BALANCED_OPT, APPLY_BALANCED_OPT | APPLY_PERFORMANCE_OPT]  # quality, balanced, performance

# sampler kinds in the table: what the deko3d slot's sampler descriptor must be
SAMPLER_KINDS = {'SPIRV_Cross_DummySampler': 0, 's_PointClamp': 1, 's_LinearClamp': 2}


def defines(flags):
    d = ['FFXM_HALF=0', 'FFXM_SPD_NO_WAVE_OPERATIONS=1',
         'FFXM_FSR2_OPTION_LOW_RESOLUTION_MOTION_VECTORS=1', 'FFXM_FSR2_OPTION_JITTERED_MOTION_VECTORS=1']
    if flags & ENABLE_SHARPENING:
        d.append('FFXM_FSR2_OPTION_APPLY_SHARPENING=1')
    if flags & APPLY_BALANCED_OPT:
        d.append('FFXM_FSR2_OPTION_SHADER_OPT_BALANCED=1')
    if flags & APPLY_PERFORMANCE_OPT:
        d.append('FFXM_FSR2_OPTION_SHADER_OPT_PERFORMANCE=1')
    return d


def run(command):
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit(f'{os.path.basename(command[0])} failed:\n{" ".join(command)}\n{(proc.stdout + proc.stderr).strip()}')
    return proc.stdout


DECL = re.compile(r'^layout\((?P<head>binding = (?P<binding>\d+))(?P<rest>[^)]*)\)(?P<decl>[^\n]*)$', re.M)
OUTPUT = re.compile(r'^layout\(location = (\d+)\) out \w+ (\w+);$', re.M)


def translate(glslang, spirv_cross, source, stage, flags, tmp):
    spv = os.path.join(tmp, 'pass.spv')
    run([glslang, '-V', '-S', stage, '-I' + os.path.join(ASR, 'include', 'gpu')] +
        ['-D' + d for d in defines(flags)] + [source, '-o', spv])
    reflect = json.loads(run([spirv_cross, spv, '--reflect']))
    glsl = run([spirv_cross, spv, '--version', '450', '--no-es', '--combined-samplers-inherit-bindings'])

    images = {e['name']: e['binding'] for e in reflect.get('separate_images', [])}
    samplers = {e['name'] for e in reflect.get('separate_samplers', [])}
    ubos = {e['binding']: re.sub(r'_t$', '', e['type_name'] if 'type_name' in e else e['name'])
            for e in reflect.get('ubos', [])}
    storage = {e['name']: e['binding'] for e in reflect.get('images', [])}

    table = {'cbv': [], 'srv': [], 'uav': [], 'rt': []}
    counters = {'cbv': 0, 'srv': 0, 'uav': 0}

    def renumber(m):
        decl, rest, vk = m.group('decl'), m.group('rest'), int(m.group('binding'))
        name = re.findall(r'(\w+)\s*;?\s*$', decl.strip())[-1]
        if 'std140' in rest:
            kind, entry = 'cbv', (ubos.get(vk, name), vk, 0)
        elif re.search(r'\bu?image\w*\b', decl):
            kind, entry = 'uav', (name, storage[name], 0)
        else:
            combined = re.match(r'SPIRV_Cross_Combined(\w+)$', name)
            if not combined:
                raise SystemExit(f'{source}: unexpected sampler {name}')
            rest_name = combined.group(1)
            sampler = next(s for s in sorted(samplers | {'SPIRV_Cross_DummySampler'}, key=len, reverse=True)
                           if rest_name.endswith(s))
            texture = rest_name[:-len(sampler)]
            kind, entry = 'srv', (texture, images[texture], SAMPLER_KINDS[sampler])
        slot = counters[kind]
        counters[kind] += 1
        table[kind].append((slot,) + entry)
        return f'layout(binding = {slot}{rest}){decl}'

    glsl = DECL.sub(renumber, glsl)
    table['rt'] = sorted((int(loc), name, int(loc), 0) for loc, name in OUTPUT.findall(glsl)) if stage == 'frag' else []
    group = re.search(r'local_size_x = (\d+), local_size_y = (\d+), local_size_z = (\d+)', glsl)
    table['group'] = tuple(int(g) for g in group.groups()) if group else (0, 0, 0)
    return glsl, table


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--glslang', default='glslang')
    parser.add_argument('--spirv-cross', default='spirv-cross')
    parser.add_argument('--out', default=os.path.join(ROOT, 'src', 'gfx_backend', 'deko3d', 'asr'))
    args = parser.parse_args()

    shaders = {}   # glsl hash -> (index, file name, stage, table)
    entries = []   # (pass id, flags, shader index)
    with tempfile.TemporaryDirectory() as tmp:
        for pass_id, pass_name, source, stage in PASSES:
            variants = [q | (ENABLE_SHARPENING if pass_id == 4 else 0) for q in QUALITIES]
            for flags in variants:
                glsl, table = translate(args.glslang, args.spirv_cross, os.path.join(GLSL_DIR, source + '.glsl'),
                                        stage, flags, tmp)
                digest = hashlib.sha256(glsl.encode()).hexdigest()[:12]
                if digest not in shaders:
                    shaders[digest] = (len(shaders), f'{source}_{digest}.glsl', stage, table, glsl)
                entries.append((pass_id, flags, shaders[digest][0]))
                print(f'{pass_name:28} flags 0x{flags:03x} -> {shaders[digest][1]}')

    os.makedirs(args.out, exist_ok=True)
    for name in os.listdir(args.out):
        if name.endswith('.glsl'):
            os.remove(os.path.join(args.out, name))
    banner = ('// Generated by tools/asr/make_asr_gl.py from third_party/arm_asr (MIT, see its LICENSE): do not edit.\n')
    ordered = sorted(shaders.values())
    for index, file_name, stage, table, glsl in ordered:
        with open(os.path.join(args.out, file_name), 'w', newline='\n') as f:
            f.write(glsl.replace('#version 450\n', '#version 450\n' + banner, 1))

    with open(os.path.join(args.out, 'asr_shaders.cmake'), 'w', newline='\n') as f:
        f.write('# Generated by tools/asr/make_asr_gl.py: NAME=FILE:STAGE for tools/embed_shaders.py --uam\n')
        f.write('set(BO1_ASR_DK_SHADERS\n')
        for index, file_name, stage, _, _ in ordered:
            f.write(f'    "AsrS{index}=${{BO1_ASR_DK_DIR}}/{file_name}:{stage}"\n')
        f.write(')\n')

    out = [banner.rstrip('\n'), '#pragma once', '#include <cstdint>', '',
           '// Arm ASR on deko3d: per shader, the deko3d slot of each resource (docs/VULKAN.md, step 6, item 4).',
           'namespace gb::deko3d::asr', '{', 'struct Binding', '{',
           '    const char *name;    // the resource name Arm\'s FSR2 component binds by',
           '    uint8_t slot;        // deko3d slot in its class (uniform block, texture, image, render target)',
           '    uint8_t vkBinding;   // the binding of the Vulkan GLSL (the pass\'s FSR2_BIND_* define)',
           '    uint8_t sampler;     // textures: 0 none (texelFetch only), 1 point clamp, 2 linear clamp',
           '};', 'struct Shader', '{', '    uint8_t stage; // 0 vertex, 1 fragment, 2 compute',
           '    uint16_t groupSize[3];',
           '    const Binding *cbv, *srv, *uav, *rt;', '    uint8_t cbvCount, srvCount, uavCount, rtCount;', '};',
           'struct Permutation', '{', '    uint8_t pass; // FfxmFsr2Pass, 255 for the shared vertex shader',
           '    uint16_t flags; // FSR2_SHADER_PERMUTATION_* within kVariedFlags', '    uint16_t shader;', '};',
           f'inline constexpr uint32_t kFixedFlags = 0x{FIXED_FLAGS:x};  // low-res motion vectors, jitter cancellation',
           f'inline constexpr uint32_t kVariedFlags = 0x{VARIED_FLAGS:x}; // sharpening, balanced, performance', '']
    for index, file_name, stage, table, _ in ordered:
        for kind in ('cbv', 'srv', 'uav', 'rt'):
            if table[kind]:
                rows = ', '.join(f'{{"{name}", {slot}, {vk}, {sampler}}}' for slot, name, vk, sampler in table[kind])
                out.append(f'inline constexpr Binding kS{index}{kind.capitalize()}[] = {{{rows}}};')
    out.append('inline constexpr Shader kShaders[] = {')
    for index, file_name, stage, table, _ in ordered:
        refs = ', '.join(f'kS{index}{k.capitalize()}' if table[k] else 'nullptr' for k in ('cbv', 'srv', 'uav', 'rt'))
        counts = ', '.join(str(len(table[k])) for k in ('cbv', 'srv', 'uav', 'rt'))
        g = table['group']
        out.append(f'    {{{STAGE_IDS[stage]}, {{{g[0]}, {g[1]}, {g[2]}}}, {refs}, {counts}}}, // {file_name}')
    out.append('};')
    out.append('inline constexpr Permutation kPermutations[] = {')
    for pass_id, flags, index in entries:
        out.append(f'    {{{pass_id}, 0x{flags:x}, {index}}},')
    out.append('};')
    out.append('// X(index) for each kDkshAsrS<index> tools/embed_shaders.py writes')
    out.append('#define BO1_ASR_DKSH_LIST(X) ' + ' '.join(f'X({i})' for i in range(len(ordered))))
    out.append('} // namespace gb::deko3d::asr')
    with open(os.path.join(args.out, 'asr_table.h'), 'w', newline='\n') as f:
        f.write('\n'.join(out) + '\n')
    print(f'{len(entries)} permutations, {len(ordered)} shaders in {args.out}')


if __name__ == '__main__':
    sys.exit(main())
