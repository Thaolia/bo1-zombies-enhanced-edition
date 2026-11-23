#!/bin/sh
# Installs Khronos' glslang release 16.6.0 (checked against its SHA-256) and puts it on PATH for the next steps of a
# GitHub Actions job. The build compiles the Vulkan backend's and the upscaler's shaders to SPIR-V with it
# (tools/embed_shaders.py); it is the version WSL and C:\SDKs\glslang-16.6.0 have, so CI and local builds embed the
# same SPIR-V (Ubuntu 24.04's glslang-tools is 14.0). Usage: tools/ci/install_glslang.sh [install dir].
set -eu
version=16.6.0
sha256=2c34071f56ecf39d16233294d3739cf43f981fd39080f2fd9dccb782101191ce
dir=${1:-${RUNNER_TEMP:-/tmp}/glslang-$version}
archive="$dir.tar.gz"
curl -fsSL -o "$archive" \
    "https://github.com/KhronosGroup/glslang/releases/download/$version/glslang-$version-linux-x86_64-release.tar.gz"
echo "$sha256  $archive" | sha256sum -c -
mkdir -p "$dir"
tar -xzf "$archive" -C "$dir"
bin=$(find "$dir" -type f \( -name glslang -o -name glslangValidator \) -path '*/bin/*' | head -n 1)
[ -n "$bin" ] || { echo "no glslang in the release archive"; exit 1; }
"$bin" --version | head -n 1
[ -z "${GITHUB_PATH:-}" ] || dirname "$bin" >> "$GITHUB_PATH"
