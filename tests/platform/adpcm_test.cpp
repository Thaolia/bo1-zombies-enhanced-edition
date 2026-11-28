// The MS-ADPCM decoder (src/platform/posix/snd_adpcm) against ffmpeg. Given a MS-ADPCM WAV and ffmpeg's own s16le
// decode of it, it decodes the WAV with Bo1_DecodeMsAdpcm and checks the samples match. The driver (the build step)
// makes the pair with ffmpeg; standard MS-ADPCM decodes deterministically, so the match must be exact.
//
//   adpcm_test <adpcm.wav> <reference.s16le>

#include <platform/posix/snd_adpcm.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

namespace
{
std::vector<uint8_t> ReadFile(const char *path)
{
    std::vector<uint8_t> data;
    FILE *f = std::fopen(path, "rb");
    if (!f)
        return data;
    std::fseek(f, 0, SEEK_END);
    data.resize(size_t(std::ftell(f)));
    std::fseek(f, 0, SEEK_SET);
    if (std::fread(data.data(), 1, data.size(), f) != data.size())
        data.clear();
    std::fclose(f);
    return data;
}

uint32_t U32(const uint8_t *p)
{
    return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24;
}
uint16_t U16(const uint8_t *p)
{
    return uint16_t(uint16_t(p[0]) | uint16_t(p[1]) << 8);
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 3)
    {
        std::printf("usage: adpcm_test <adpcm.wav> <reference.s16le>\n");
        return 2;
    }
    const std::vector<uint8_t> wav = ReadFile(argv[1]);
    const std::vector<uint8_t> ref = ReadFile(argv[2]);
    if (wav.size() < 12 || std::memcmp(wav.data(), "RIFF", 4) || std::memcmp(wav.data() + 8, "WAVE", 4))
    {
        std::printf("FAIL: %s is not a WAV\n", argv[1]);
        return 1;
    }

    int channels = 0, blockAlign = 0, formatTag = 0;
    uint32_t factFrames = 0;
    const uint8_t *adpcm = nullptr;
    size_t adpcmSize = 0;
    for (size_t i = 12; i + 8 <= wav.size();)
    {
        const uint8_t *id = wav.data() + i;
        const uint32_t size = U32(wav.data() + i + 4);
        const uint8_t *body = wav.data() + i + 8;
        if (!std::memcmp(id, "fmt ", 4) && size >= 16)
        {
            formatTag = U16(body);
            channels = U16(body + 2);
            blockAlign = U16(body + 12);
        }
        else if (!std::memcmp(id, "fact", 4) && size >= 4)
            factFrames = U32(body);
        else if (!std::memcmp(id, "data", 4))
        {
            adpcm = body;
            adpcmSize = size <= wav.size() - (i + 8) ? size : wav.size() - (i + 8);
        }
        i += 8 + size + (size & 1);
    }
    if (formatTag != 2 || channels < 1 || !blockAlign || !adpcm)
    {
        std::printf("FAIL: %s is not MS-ADPCM (tag %d, %d ch, block %d)\n", argv[1], formatTag, channels, blockAlign);
        return 1;
    }

    // ffmpeg's raw decode emits every complete block, padding included: it does not trim to the fact chunk. The
    // strongest check is the whole decode, every nibble, so the reference length is the target, not fact (the engine
    // stops at the asset's frame_count at runtime; here the padding frames are real ADPCM and must match too).
    const uint32_t refFrames = uint32_t(ref.size() / (2 * channels));
    const int wantFrames = int(refFrames);
    std::vector<int16_t> out(size_t(wantFrames) * channels + channels);
    const int got = Bo1_DecodeMsAdpcm(adpcm, adpcmSize, channels, blockAlign, out.data(), wantFrames);

    std::printf("%s: %d ch, block %d, %d frames (fact %u, ref %u, decoded %d)\n", argv[1], channels, blockAlign,
                wantFrames, factFrames, refFrames, got);
    if (got != wantFrames || uint32_t(got) != refFrames)
    {
        std::printf("FAIL: decoded %d frames, ffmpeg %u\n", got, refFrames);
        return 1;
    }
    const int16_t *refSamples = reinterpret_cast<const int16_t *>(ref.data());
    int mismatches = 0, firstBad = -1;
    for (int i = 0; i < got * channels; ++i)
        if (out[i] != refSamples[i])
        {
            if (firstBad < 0)
                firstBad = i;
            ++mismatches;
        }
    if (mismatches)
    {
        std::printf("FAIL: %d of %d samples differ; first at %d: mine %d, ffmpeg %d\n", mismatches, got * channels,
                    firstBad, out[firstBad], refSamples[firstBad]);
        return 1;
    }
    // The SDL2 driver decodes a RAM voice one block at a time, at the block's own offset (snd_driver_sdl2.cpp,
    // RamFrame): each block must decode to the same samples as in the whole decode.
    const int blockFrames = Bo1_MsAdpcmFramesPerBlock(channels, blockAlign);
    std::vector<int16_t> block(size_t(blockFrames) * channels);
    for (size_t base = 0, frame = 0; base < adpcmSize; base += size_t(blockAlign), frame += size_t(blockFrames))
    {
        const size_t bytes = adpcmSize - base < size_t(blockAlign) ? adpcmSize - base : size_t(blockAlign);
        const int n = Bo1_DecodeMsAdpcm(adpcm + base, bytes, channels, blockAlign, block.data(), blockFrames);
        for (int i = 0; i < n * channels && frame * channels + i < size_t(got) * channels; ++i)
            if (block[i] != out[frame * channels + i])
            {
                std::printf("FAIL: block at byte %zu differs from the whole decode at sample %d\n", base, i);
                return 1;
            }
    }
    std::printf("PASS: %d samples match ffmpeg exactly, block by block too\n", got * channels);
    return 0;
}
