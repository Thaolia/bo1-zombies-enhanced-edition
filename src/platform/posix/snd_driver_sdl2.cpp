// The sound driver on posix: a software mixer on an SDL2 audio device, in place of the XAudio2 driver
// (snd_driver_xaudio2.cpp). It implements the engine-facing contract of sound/snd_driver.h and keeps the engine's
// voice model: the engine owns the voice table (g_snd.voice[], free-ness in g_snd.voiceAliasHash), picks aliases,
// computes each voice's speaker map and send levels, and drives the driver through SD_StartAlias / SD_UpdateVoice /
// SD_StopVoice. This driver turns that per-voice state into samples (snd_mix.h, ported from SDXA2_UpdateVoiceSends)
// and mixes the RAM voices to the device.
//
// Threading. SDL owns the audio thread and calls AudioCallback when it needs samples; a game-loop refill would
// starve on long frames (the libnx note in .claude/rules/switch-homebrew.md), so the pull model is deliberate. The
// game thread mutates the voice table in the SD_* entry points; the callback reads it. One mutex guards the table,
// held only briefly and never across an allocation or I/O: the callback allocates nothing (its scratch is
// pre-allocated in SD_Init) and reads only RAM, and every decode/alloc happens on the game thread (at a voice start or
// a stream window).
//
// Scope (docs/PORTING.md, phase 4b). RAM voices (indices 10..73) and streamed voices (0..9: music, long ambience).
// A streamed voice follows SD_UpdateStreamVoice of the XAudio2 driver: the engine's stream thread (snd_stream.cpp)
// reads the file into windows; the game thread acquires a window, decodes it to float into one of the voice's two
// chunks (XAudio2 queues at most two buffers too) and gives the window back at once, since the chunk holds the
// samples. The buses and their DSP are XAudio2's (RenderBlock): reverb, the novoice compressor, the master EQ and
// limiter, with the parameters SD_PreUpdate computes as the XAudio2 driver does. Each voice first runs XAudio2's source
// effect (SDXA2SourceEffect: the occlusion low-pass and the futz radio effect), with the parameters
// SDXA2_UpdateVoiceSends computes. The decoders (snd_adpcm) and the send matrices (snd_mix) are unit-tested offline;
// audible correctness, 3D and the non-unity resampler are verified on hardware, not here.

#include "snd_adpcm.h"
#include "snd_mix.h"

#include <sound/snd_bank.h>
#include <sound/snd_db.h>
#include <sound/snd_driver.h>
#include <sound/snd_dsp.h>
#include <sound/snd_dvar.h>
#include <sound/snd_globals.h>
#include <sound/snd_radverb.h>
#include <sound/snd_public_async.h>
#include <sound/snd_stream.h>

#include <qcommon/common.h>

#include <SDL.h>

#include <atomic>
#include <cmath>
#include <cstring>
#include <mutex>
#include <vector>

// The XAudio2 driver declares these in snd_driver_xaudio2.h, which names XAudio2 types; only this file uses them here.
unsigned int __cdecl iSND_GetStreamChannel(unsigned int index);
void __cdecl SD_UpdateStreamVoice(int voiceIndex);
void __cdecl iSND_ChannelError(int voiceIndex);

namespace
{
constexpr int kDeviceRate = 48000;
constexpr int kDeviceChannels = 2; // the device is stereo; snd_speakerConfiguration defaults to "Stereo" (index 0),
                                   // so the engine fills each voice's pan with output_channel_count == 2 to match.

// One decoded stream window. The audio thread reads the chunk at `head`; the game thread fills the other slot.
struct StreamChunk
{
    std::vector<float> samples; // interleaved float PCM, frames * inputChannels
    int frames = 0;
};

struct MixerVoice
{
    bool active = false;
    bool stream = false;   // a streamed voice (0..9): samples come from `chunks`, not from `samples`
    bool started = false;  // the engine starts a voice on its first SD_UpdateVoice, as the XAudio2 driver does
    bool paused = false;
    bool looping = false;
    bool drained = false;  // set by the callback when a non-looping voice runs out; SD_UpdateVoice then stops it
    int inputChannels = 1;
    int outputChannels = kDeviceChannels;
    int frameCount = 0;          // decoded source frames held in `samples`
    int assetRate = kDeviceRate; // the asset's native frame rate, for the resample step
    double readPos = 0.0;        // source read cursor in frames (audio thread)
    double playedSrc = 0.0;      // cumulative source frames consumed, monotonic across loops (SamplesPlayed)
    double step = 1.0;           // source frames per output frame = pitch * assetRate / deviceRate
    float dry[2 * 8] = {};       // the dry send matrix, destination-major (dest * inputChannels + src)
    float wet[2 * 4] = {};       // the wet send to the 4-channel radverb bus, same layout
    bool toMasterBus = false;    // the dry send's bus: master, else novoice (alias flags, bus 2)
    std::vector<float> samples;  // interleaved float PCM, frameCount * inputChannels; owned by the game thread
    StreamChunk chunks[2];       // streamed voices only
    int chunkHead = 0;           // the chunk being played
    int chunkCount = 0;          // chunks queued, the one being played included (XAudio2's BuffersQueued)
    snd_dsp_source_params fx = {};      // the source effect's parameters, zero (no filter) until the first update
    snd_dsp_source_state fxState[2] = {}; // one a channel, cleared at each start as iSND_CreateVoice clears its XAPO
};

std::mutex s_lock;
MixerVoice s_voices[SND_MAX_VOICES];
SDL_AudioDeviceID s_device = 0;
std::vector<float> s_scratch; // resampled source for one voice, reused each callback; sized in SD_Init
bool s_subsystemReady = false;
// The buses of one quantum, and the engine DSP's parameters and state (audio thread, under s_lock). 480 frames at
// 48 kHz is XAudio2's quantum, the frame count its XAPOs and SND_RvFrame's buffers are written for.
constexpr int kBlock = 480;
float s_masterBus[kBlock * kDeviceChannels];
float s_novoiceBus[kBlock * kDeviceChannels];
float s_radverbBus[kBlock * 4];
float s_planar[kBlock * 4];
float s_rvOut[kBlock * 4];
float s_block[kBlock * kDeviceChannels];
float s_voicePlanar[kBlock * 2]; // one voice's quantum, planar, for its source effect
float s_fxTempA[kBlock];
float s_fxTempB[kBlock];
int s_blockPos = kBlock;
snd_rv_state s_rvState;
snd_rv_params s_rvParams, s_rvPending;
snd_dsp_master_params s_masterParams, s_masterPending;
snd_dsp_master_no_voice_params s_novoiceParams, s_novoicePending;
snd_dsp_master_state s_masterState[kDeviceChannels];
snd_dsp_master_no_voice_state s_novoiceState[kDeviceChannels];
std::vector<float> s_streamSpare[SND_MAX_STREAM_VOICES]; // game thread: the next chunk is decoded here, then swapped in
std::vector<int16_t> s_streamPcm;                         // game thread: ADPCM decode output before the float step

// Decodes a RAM asset (PCM16 or MS-ADPCM) into interleaved float in [-1, 1]. Called on the game thread at voice
// start, into a local buffer, before the voice is made active, so the callback never races the decode.
void DecodeAsset(const snd_asset *snd, int frames, int channels, std::vector<float> &outF)
{
    outF.assign(size_t(frames) * channels, 0.0f);
    if (snd->format == SND_ASSET_FORMAT_MSADPCM)
    {
        // The block align is 262 bytes a channel, as iSND_CreateVoice hard-codes it (snd_driver_xaudio2.cpp:410);
        // the asset's block_size field is not used by the engine, so it is not trusted here.
        const int blockAlign = 262 * channels;
        std::vector<int16_t> pcm(size_t(frames) * channels);
        const int got = Bo1_DecodeMsAdpcm(reinterpret_cast<const uint8_t *>(snd->data), snd->data_size, channels,
                                           blockAlign, pcm.data(), frames);
        for (int i = 0; i < got * channels; ++i)
            outF[i] = pcm[i] * (1.0f / 32768.0f);
    }
    else // PCM16 (format 0): the data is interleaved signed 16-bit already
    {
        const int16_t *pcm = reinterpret_cast<const int16_t *>(snd->data);
        const int avail = int(snd->data_size / sizeof(int16_t));
        const int n = frames * channels < avail ? frames * channels : avail;
        for (int i = 0; i < n; ++i)
            outF[i] = pcm[i] * (1.0f / 32768.0f);
    }
}

// Resamples a streamed voice across its queued chunks into `src`; returns the frames produced. A chunk played to its
// end is dropped; with none left the voice is silent until the game thread queues more, or stops it (SD_UpdateVoice,
// as XAudio2 with no buffer queued).
int ProduceStream(MixerVoice &v, int frames, float *src)
{
    int produced = 0;
    for (int f = 0; f < frames && v.chunkCount > 0; ++f)
    {
        const StreamChunk *cur = &v.chunks[v.chunkHead];
        while (v.readPos >= cur->frames)
        {
            v.readPos -= cur->frames;
            v.chunkHead ^= 1;
            if (--v.chunkCount == 0)
                break;
            cur = &v.chunks[v.chunkHead];
        }
        if (v.chunkCount == 0)
            break;
        const int i0 = int(v.readPos);
        const double frac = v.readPos - i0;
        const float *a = &cur->samples[size_t(i0) * v.inputChannels];
        const float *b = a;
        if (i0 + 1 < cur->frames)
            b = a + v.inputChannels;
        else if (v.chunkCount > 1 && v.chunks[v.chunkHead ^ 1].frames > 0)
            b = v.chunks[v.chunkHead ^ 1].samples.data();
        for (int c = 0; c < v.inputChannels; ++c)
            src[f * v.inputChannels + c] = float(a[c] + (b[c] - a[c]) * frac);
        v.readPos += v.step;
        v.playedSrc += v.step;
        ++produced;
    }
    return produced;
}

// Resamples a RAM voice into `src`, linearly; returns the frames produced (fewer than `frames` if a non-looping voice
// ends inside the block).
int ProduceRam(MixerVoice &v, int frames, float *src)
{
    int produced = 0;
    for (int f = 0; f < frames; ++f)
    {
        if (v.readPos >= v.frameCount)
        {
            if (!v.looping)
            {
                v.drained = true;
                break;
            }
            v.readPos -= v.frameCount;
        }
        const int i0 = int(v.readPos);
        const double frac = v.readPos - i0;
        int i1 = i0 + 1;
        if (i1 >= v.frameCount)
            i1 = v.looping ? 0 : i0;
        for (int c = 0; c < v.inputChannels; ++c)
        {
            const float a = v.samples[size_t(i0) * v.inputChannels + c];
            const float b = v.samples[size_t(i1) * v.inputChannels + c];
            src[f * v.inputChannels + c] = float(a + (b - a) * frac);
        }
        v.readPos += v.step;
        v.playedSrc += v.step;
        ++produced;
    }
    return produced;
}

void Uninterleave(const float *in, int channels, float *planar)
{
    for (int f = 0; f < kBlock; ++f)
        for (int c = 0; c < channels; ++c)
            planar[c * kBlock + f] = in[f * channels + c];
}

// SDXA2SourceEffect::Process on one voice's quantum (interleaved in `src`, `produced` frames). XAudio2 always hands the
// effect a whole quantum, silence past a voice's end, and the engine's DSP needs a multiple of 4 frames: pad with zeros.
void RunSourceEffect(MixerVoice &v, float *src, int produced)
{
    const int channels = v.inputChannels;
    std::memset(src + size_t(produced) * channels, 0, sizeof(float) * size_t(kBlock - produced) * channels);
    Uninterleave(src, channels, s_voicePlanar);
    for (int c = 0; c < channels; ++c)
        // The cast is the XAudio2 driver's: the function reads the whole snd_dsp_source_params through it.
        SND_DspFxSourceMono(reinterpret_cast<const snd_dsp_futz_param *>(&v.fx), &v.fxState[c], kBlock,
                            &s_voicePlanar[c * kBlock], s_fxTempA, s_fxTempB);
    for (int f = 0; f < produced; ++f)
        for (int c = 0; c < channels; ++c)
            src[f * channels + c] = s_voicePlanar[c * kBlock + f];
}

// One 480-frame quantum of the XAudio2 graph (SD_Init in snd_driver_xaudio2.cpp): every voice sends dry to the master
// or the novoice bus and wet to the 4-channel radverb bus; the radverb bus (stage 1) feeds the novoice bus through the
// stereo output matrix (its channel 3 to the left, 1 to the right); the novoice bus (stage 2, its compressor) feeds
// the master bus (stage 3, EQ and limiter), which goes to the device. The DSP is the engine's own (snd_radverb.cpp,
// snd_dsp.cpp), run per channel on planar data as the XAPOs of snd_driver_xaudio2_dsp.cpp do. Called with s_lock held.
void RenderBlock()
{
    std::memset(s_masterBus, 0, sizeof(s_masterBus));
    std::memset(s_novoiceBus, 0, sizeof(s_novoiceBus));
    std::memset(s_radverbBus, 0, sizeof(s_radverbBus));

    float *src = s_scratch.data();
    for (int vi = 0; vi < SND_MAX_VOICES; ++vi)
    {
        MixerVoice &v = s_voices[vi];
        if (!v.active || v.paused || !v.started)
            continue;
        int produced;
        if (v.stream)
            produced = ProduceStream(v, kBlock, src);
        else if (v.drained || v.frameCount == 0)
            continue;
        else
            produced = ProduceRam(v, kBlock, src);
        if (produced <= 0)
            continue;
        RunSourceEffect(v, src, produced);
        bo1snd::MixAccumulate(src, produced, v.inputChannels, v.dry, kDeviceChannels,
                              v.toMasterBus ? s_masterBus : s_novoiceBus);
        bo1snd::MixAccumulate(src, produced, v.inputChannels, v.wet, 4, s_radverbBus);
    }

    // Parameters the game thread set in SD_PreUpdate, as SetEffectParameters hands them to the XAPOs.
    s_rvParams = s_rvPending;
    s_masterParams = s_masterPending;
    s_novoiceParams = s_novoicePending;

    float *planar = s_planar;
    float *rvOut = s_rvOut;
    Uninterleave(s_radverbBus, 4, planar);
    if (s_rvParams.earlySize > 0.0f) // SDXA2RadverbEffect::Process asserts it; the defaults set it
    {
        SND_RvFrame(&s_rvParams, &s_rvState, reinterpret_cast<const float *>(uintptr_t(kBlock)), &planar[3 * kBlock],
                    &planar[kBlock], planar, &planar[2 * kBlock], &rvOut[3 * kBlock], &rvOut[kBlock], rvOut,
                    &rvOut[2 * kBlock]);
        for (int f = 0; f < kBlock; ++f)
        {
            s_novoiceBus[2 * f] += rvOut[3 * kBlock + f];
            s_novoiceBus[2 * f + 1] += rvOut[kBlock + f];
        }
    }

    Uninterleave(s_novoiceBus, kDeviceChannels, planar);
    for (int c = 0; c < kDeviceChannels; ++c)
        SND_DspFxMasterNoVoiceSingleChannel(kBlock, float(kDeviceRate), &planar[c * kBlock], &s_novoiceParams,
                                            &s_novoiceState[c], &g_snd.meters[c]);
    for (int f = 0; f < kBlock; ++f)
        for (int c = 0; c < kDeviceChannels; ++c)
            s_masterBus[f * kDeviceChannels + c] += planar[c * kBlock + f];

    Uninterleave(s_masterBus, kDeviceChannels, planar);
    for (int c = 0; c < kDeviceChannels; ++c)
        SND_DspFxMasterSingleChannel(kBlock, float(kDeviceRate), &planar[c * kBlock], &s_masterParams,
                                     &s_masterState[c], &g_snd.meters[c]);
    // The limiter keeps the master bus in range; the clamp only stops a stray overshoot from wrapping at the device.
    for (int f = 0; f < kBlock; ++f)
        for (int c = 0; c < kDeviceChannels; ++c)
        {
            const float x = planar[c * kBlock + f];
            s_block[f * kDeviceChannels + c] = x < -1.0f ? -1.0f : x > 1.0f ? 1.0f : x;
        }
    s_blockPos = 0;
}

void SDLCALL AudioCallback(void *, Uint8 *stream, int len)
{
    float *out = reinterpret_cast<float *>(stream);
    int frames = len / (kDeviceChannels * int(sizeof(float)));

    std::lock_guard<std::mutex> lock(s_lock);
    while (frames > 0)
    {
        if (s_blockPos >= kBlock)
            RenderBlock();
        const int n = frames < kBlock - s_blockPos ? frames : kBlock - s_blockPos;
        std::memcpy(out, &s_block[s_blockPos * kDeviceChannels], sizeof(float) * size_t(n) * kDeviceChannels);
        out += n * kDeviceChannels;
        s_blockPos += n;
        frames -= n;
    }
}

bool EnsureSubsystem()
{
    if (s_subsystemReady)
        return true;
    // Whether sound runs is decided by whether a device actually opens (SD_Xaudio2CanInit), not by headlessness: a
    // headless run with no audio hardware fails the open and falls back to nosnd on its own.
    if (SDL_InitSubSystem(SDL_INIT_AUDIO) != 0)
        return false;
    s_subsystemReady = true;
    return true;
}
} // namespace

bool __cdecl SD_Xaudio2CanInit()
{
    // Reports whether sound can start at all; false makes the engine run as with 'nosnd' (device missing), a state it
    // already handles. Enumerating a device is not enough (WSLg lists an ALSA device it cannot open), so this opens
    // and closes one for real: only a device that actually opens turns sound on.
    if (!EnsureSubsystem())
        return false;
    SDL_AudioSpec want, have;
    SDL_zero(want);
    want.freq = kDeviceRate;
    want.format = AUDIO_F32SYS;
    want.channels = kDeviceChannels;
    want.samples = 1024;
    SDL_AudioDeviceID probe = SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0);
    if (!probe)
        return false;
    SDL_CloseAudioDevice(probe);
    return true;
}

void __cdecl SD_TruncateAudioDeviceNames(Font_s *, float, int)
{
    // The device-name list is a Windows settings-menu affordance; the SDL backend exposes no such list.
}

char __cdecl SD_Init()
{
    if (!EnsureSubsystem())
        return 0;

    SDL_AudioSpec want, have;
    SDL_zero(want);
    want.freq = kDeviceRate;
    want.format = AUDIO_F32SYS;
    want.channels = kDeviceChannels;
    want.samples = 1024; // frames a callback; a buffer the engine's frame comfortably refills
    want.callback = AudioCallback;

    s_device = SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0);
    if (!s_device)
    {
        Com_Printf(16, "snd: SDL2 device would not open (%s); running without sound\n", SDL_GetError());
        return 0;
    }

    s_scratch.assign(size_t(kBlock) * 2, 0.0f); // one quantum of a stereo asset, the worst case, pre-allocated once
    {
        std::lock_guard<std::mutex> lock(s_lock);
        // As the XAPOs start: radverb on its defaults, the master and novoice parameters zero until SD_PreUpdate.
        SND_RvParamsDefault(&s_rvPending);
        std::memset(&s_masterPending, 0, sizeof(s_masterPending));
        std::memset(&s_novoicePending, 0, sizeof(s_novoicePending));
        std::memset(&s_rvState, 0, sizeof(s_rvState));
        std::memset(s_masterState, 0, sizeof(s_masterState));
        std::memset(s_novoiceState, 0, sizeof(s_novoiceState));
        s_blockPos = kBlock;
    }
    SDL_PauseAudioDevice(s_device, 0);
    Com_Printf(16, "snd: SDL2 software mixer on %s, %d Hz, %d ch, %d-frame buffer (RAM and streamed voices, source, reverb and master DSP)\n",
               SDL_GetCurrentAudioDriver(), have.freq, have.channels, have.samples);
    return 1;
}

void SD_Shutdown()
{
    if (s_device)
    {
        SDL_CloseAudioDevice(s_device);
        s_device = 0;
    }
    std::lock_guard<std::mutex> lock(s_lock);
    for (auto &v : s_voices)
    {
        v = MixerVoice();
        std::vector<float>().swap(v.samples);
    }
}

// The XAudio2 driver's, with SetEffectParameters replaced by the pending copies RenderBlock picks up.
void __cdecl SD_PreUpdate()
{
    snd_rv_params rv;
    SND_RvParamsDefault(&rv);
    const snd_radverb *radverb = SND_GetRadverb(SND_GetCurrentReverb());
    rv.frameRate = float(kDeviceRate);
    if (radverb)
    {
        rv.smoothing = radverb->smoothing;
        rv.earlyTime = radverb->earlyTime;
        rv.lateTime = radverb->lateTime;
        rv.earlyGain = radverb->earlyGain;
        rv.lateGain = radverb->lateGain;
        rv.lateGainProx[3] = g_snd.proximityLateModifier[0];
        rv.lateGainProx[1] = g_snd.proximityLateModifier[1];
        rv.lateGainProx[2] = g_snd.proximityLateModifier[2];
        rv.lateGainProx[0] = g_snd.proximityLateModifier[3];
        rv.returnGain = radverb->returnGain;
        rv.earlyLpf = radverb->earlyLpf;
        rv.lateLpf = radverb->lateLpf;
        rv.inputLpf = radverb->inputLpf;
        rv.dampLpf = radverb->dampLpf;
        for (int i = 0; i < 4; ++i)
            rv.wallReflect[i] = radverb->wallReflect;
        rv.dryGain = radverb->dryGain;
        rv.earlySize = radverb->earlySize;
        rv.lateSize = radverb->lateSize;
        rv.diffusion = radverb->diffusion;
        rv.delayMatrix = snd_radverb_matrix->current.color[0];
        if (SND_ActiveListenerCount() == 1)
        {
            const float a = float(atan2(g_snd.listeners[0].orient.axis[0][0], g_snd.listeners[0].orient.axis[0][1]));
            const float v4 = (a + 3.1415927f) - 6.2831855f < 0.0f ? a + 3.1415927f : 6.2831855f;
            rv.angle = 0.0f - (a + 3.1415927f) < 0.0f ? v4 : 0.0f;
        }
        else
        {
            rv.angle = 0.0f;
        }
    }

    snd_dsp_master_params mp;
    std::memset(&mp, 0, sizeof(mp));
    const snd_master *master = SND_GetMasterCurrent();
    mp.lowE = master->lowE;
    mp.lowG = master->lowG;
    mp.lowF = master->lowF;
    mp.lowQ = master->lowQ;
    mp.peak1E = master->peak1E;
    mp.peak1G = master->peak1G;
    mp.peak1F = master->peak1F;
    mp.peak1Q = master->peak1Q;
    mp.peak2E = master->peak2E;
    mp.peak2G = master->peak2G;
    mp.peak2F = master->peak2F;
    mp.peak2Q = master->peak2Q;
    mp.hiE = master->hiE;
    mp.hiG = master->hiG;
    mp.hiF = master->hiF;
    mp.hiQ = master->hiQ;
    mp.eqG = master->eqG;
    mp.limitE = master->limitE;
    mp.limitPG = master->limitPG;
    mp.limitMG = master->limitMG;
    mp.limitT = master->limitT;
    mp.limitR = master->limitR;
    mp.limitTA = master->limitTA;
    mp.limitTR = master->limitTR;
    const snd_dsp_master_no_voice_params nv = *reinterpret_cast<const snd_dsp_master_no_voice_params *>(&master->compE);

    std::lock_guard<std::mutex> lock(s_lock);
    s_rvPending = rv;
    s_masterPending = mp;
    s_novoicePending = nv;
}

void __cdecl SD_StopVoice(int voiceIndex)
{
    {
        std::vector<float> freed[3]; // released after the lock, so the callback never waits on a free
        std::lock_guard<std::mutex> lock(s_lock);
        MixerVoice &v = s_voices[voiceIndex];
        v.active = false;
        v.started = false;
        v.drained = false;
        v.samples.swap(freed[0]);
        v.frameCount = 0;
        v.stream = false;
        v.chunkHead = 0;
        v.chunkCount = 0;
        for (int i = 0; i < 2; ++i)
        {
            v.chunks[i].samples.swap(freed[1 + i]);
            v.chunks[i].frames = 0;
        }
    }
    // As the XAudio2 driver: a streamed voice closes its file stream. Its windows were given back when decoded.
    if (SND_IsStream(voiceIndex))
    {
        const unsigned int streamVoice = iSND_GetStreamChannel(voiceIndex);
        if (Snd_StreamStatus(streamVoice))
            Snd_StreamClose(streamVoice);
    }
}

void __cdecl SD_PauseVoice(int voiceIndex)
{
    g_snd.voice[voiceIndex].paused = 1;
    std::lock_guard<std::mutex> lock(s_lock);
    s_voices[voiceIndex].paused = true;
}

void __cdecl SD_UnpauseVoice(int voiceIndex)
{
    std::lock_guard<std::mutex> lock(s_lock);
    s_voices[voiceIndex].paused = false;
}

__int64 SD_BO1SamplesPlayed(int voiceIndex)
{
    if (g_snd.voice[voiceIndex].soundFileInfo.loadingState == SFLS_LOADING)
        return -1;
    std::lock_guard<std::mutex> lock(s_lock);
    const MixerVoice &v = s_voices[voiceIndex];
    if (!v.active)
        return -1;
    return (__int64)(v.playedSrc);
}

void __cdecl SD_UpdateVoice(unsigned int voiceIndex)
{
    // As the XAudio2 driver: a streamed voice first queues the windows its stream has read; that may stop it.
    if (SND_IsStream(voiceIndex))
    {
        SD_UpdateStreamVoice(int(voiceIndex));
        if (!g_snd.voiceAliasHash[voiceIndex])
            return;
    }
    snd_voice_t *voice = &g_snd.voice[voiceIndex];
    if (voice->soundFileInfo.loadingState == SFLS_LOADING)
        return;

    std::unique_lock<std::mutex> lock(s_lock);
    MixerVoice &v = s_voices[voiceIndex];
    if (!v.active)
        return;
    // Ran out since the last update (a RAM voice played to its end, a streamed one with no chunk left): let the engine
    // tear it down, as the XAudio2 path does when no buffer is queued. SND_StopVoice comes back into SD_StopVoice,
    // which takes the lock: drop it first.
    if (v.stream ? v.chunkCount == 0 : v.drained)
    {
        lock.unlock();
        SND_StopVoice(int(voiceIndex));
        return;
    }

    // Rebuild the dry send matrix from the engine's current speaker map and dry level, and refresh the pitch. The
    // decoded channel count (v.inputChannels, fixed at start) is the stride of the sample buffer and of the matrix,
    // so it is what the matrix is built with, not voice->pan.input_channel_count: were they ever to disagree, reading
    // the buffer with the pan's count would run off its end. The wet send feeds the radverb bus.
    // The device is stereo, so the dry matrix must be exactly kDeviceChannels wide; the speaker map's volumes[] is
    // laid out for output_channel_count outputs, so that count has to be kDeviceChannels too (it is: the engine
    // defaults snd_speakerConfiguration to "Stereo"). A different count would need an N->2 down-mix the mixer does
    // not do; skip the voice rather than read the matrix or the buffer out of range.
    if (voice->pan.output_channel_count != kDeviceChannels || v.inputChannels < 1 || v.inputChannels > 2)
        return;
    // SDXA2_UpdateVoiceSends' source effect parameters. They read the engine's voice and dvars only, but are copied
    // under the lock like the sends, since the callback reads them.
    snd_dsp_source_params fx;
    fx.lpfAttenuation = float(SND_GetLpfLevel(voice));
    fx.lpfRatio = 0.25f;
    fx.frameRate = float(kDeviceRate);
    fx.futz.blend = voice->futzBlend;
    fx.futz.bpfF = snd_futz_bpf_f->current.value;
    fx.futz.bpfQ = snd_futz_bpf_q->current.value;
    fx.futz.lsG = snd_futz_ls_g->current.value;
    fx.futz.lsF = snd_futz_ls_f->current.value;
    fx.futz.lsQ = snd_futz_ls_q->current.value;
    fx.futz.distortion = snd_futz_distortion->current.value;
    fx.futz.pregain = snd_futz_preg->current.value;
    fx.futz.postgain = snd_futz_postg->current.value;
    fx.futz.squelch.tg = snd_futz_tg->current.value;
    fx.futz.squelch.th = snd_futz_th->current.value;
    fx.futz.preclip = snd_futz_clip_pre->current.value;
    fx.futz.postclip = snd_futz_clip_post->current.value;
    v.fx = fx;

    bo1snd::VoiceSends sends;
    bo1snd::BuildVoiceSends(voice->pan.volumes, v.inputChannels, kDeviceChannels, voice->dryLevel, voice->wetLevel,
                            voice->alias->flags, &sends);
    v.outputChannels = kDeviceChannels;
    std::memcpy(v.dry, sends.dry, sizeof(v.dry));
    std::memcpy(v.wet, sends.wet, sizeof(v.wet));
    v.toMasterBus = sends.toMasterBus;
    v.step = SND_GetPitch(voice) * (double(v.assetRate) / kDeviceRate);

    if (!v.started && !voice->paused && !voice->startDelay)
        v.started = true;
}

void __cdecl iSND_ChannelError(int voiceIndex)
{
    const snd_alias_t *alias = g_snd.voice[voiceIndex].alias;
    SND_LengthNotify(voiceIndex, 0);
    SND_StopVoice(voiceIndex);
    alias->soundFile->exists = 0;
}

unsigned int __cdecl iSND_GetStreamChannel(unsigned int index)
{
    iassert(index < SND_MAX_STREAM_VOICES);
    return index;
}

namespace
{
// Decodes one stream window (whole MS-ADPCM blocks, or PCM16) into `out`; returns the frames decoded.
int DecodeWindow(const snd_asset *header, const char *data, unsigned int size, std::vector<float> &out)
{
    const int channels = int(header->channel_count);
    int frames = 0;
    if (header->format == SND_ASSET_FORMAT_MSADPCM)
    {
        const int blockAlign = 262 * channels;
        const int blocks = int((size + blockAlign - 1) / blockAlign);
        const int capacity = blocks * Bo1_MsAdpcmFramesPerBlock(channels, blockAlign);
        if (s_streamPcm.size() < size_t(capacity) * channels)
            s_streamPcm.resize(size_t(capacity) * channels);
        frames = Bo1_DecodeMsAdpcm(reinterpret_cast<const uint8_t *>(data), size, channels, blockAlign,
                                   s_streamPcm.data(), capacity);
        out.resize(size_t(frames) * channels);
        for (int i = 0; i < frames * channels; ++i)
            out[i] = s_streamPcm[i] * (1.0f / 32768.0f);
    }
    else
    {
        frames = int(size / (sizeof(int16_t) * channels));
        out.resize(size_t(frames) * channels);
        const int16_t *pcm = reinterpret_cast<const int16_t *>(data);
        for (int i = 0; i < frames * channels; ++i)
            out[i] = pcm[i] * (1.0f / 32768.0f);
    }
    return frames;
}

int QueuedChunks(int voiceIndex)
{
    std::lock_guard<std::mutex> lock(s_lock);
    return s_voices[voiceIndex].chunkCount;
}

// iSND_CreateVoice's part for a stream: the mixer voice, from the header the stream thread read.
bool CreateStreamVoice(int voiceIndex, const snd_asset *header)
{
    if (header->format != SND_ASSET_FORMAT_MSADPCM && header->format != 0 /*PCM16*/)
        return false;
    if (header->channel_count < 1 || header->channel_count > 2 || !header->frame_rate)
        return false;
    std::lock_guard<std::mutex> lock(s_lock);
    MixerVoice &v = s_voices[voiceIndex];
    v.stream = true;
    v.inputChannels = int(header->channel_count);
    v.outputChannels = kDeviceChannels;
    v.frameCount = 0;
    v.assetRate = int(header->frame_rate);
    v.looping = false; // the stream wraps a looping file itself
    v.readPos = 0.0;
    v.playedSrc = 0.0;
    v.step = double(header->frame_rate) / kDeviceRate;
    v.started = false;
    v.paused = false;
    v.drained = false;
    v.chunkHead = 0;
    v.chunkCount = 0;
    for (float &g : v.dry)
        g = 0.0f;
    for (float &g : v.wet)
        g = 0.0f;
    v.fx = snd_dsp_source_params{};
    std::memset(v.fxState, 0, sizeof(v.fxState));
    v.active = true;
    return true;
}
} // namespace

void __cdecl SD_UpdateStreamVoice(int voiceIndex)
{
    const unsigned int streamVoice = iSND_GetStreamChannel(voiceIndex);
    snd_stream_status status = Snd_StreamStatus(streamVoice);
    if (!status || status == SND_STREAM_STARVING || !Snd_StreamGetHeader(streamVoice))
        return;
    if (status == SND_STREAM_ERROR)
    {
        iSND_ChannelError(voiceIndex);
        return;
    }

    bool created;
    {
        std::lock_guard<std::mutex> lock(s_lock);
        created = s_voices[voiceIndex].active && s_voices[voiceIndex].stream;
    }
    const snd_asset *header = Snd_StreamGetHeader(streamVoice);
    if (!created)
    {
        if (status != SND_STREAM_OK)
            return;
        if (!CreateStreamVoice(voiceIndex, header))
        {
            iSND_ChannelError(voiceIndex);
            return;
        }
        // One line a stream start, so a player's log shows which music and long sounds played.
        Com_Printf(16, "snd: stream %u '%s', %u ch, %u Hz, %u frames\n", streamVoice,
                   g_snd.voice[voiceIndex].alias ? g_snd.voice[voiceIndex].alias->name : "?",
                   header->channel_count, header->frame_rate, header->frame_count);
        const unsigned int lengthMS = unsigned(1000LL * header->frame_count / header->frame_rate);
        SND_SetSoundFileVoiceInfo(voiceIndex, header->channel_count, header->frame_rate, lengthMS, 0, SFLS_LOADED);
        SND_UpdateVoice(&g_snd.voice[voiceIndex], 0.0f);
    }

    while (Snd_StreamGetFreeWindows(streamVoice))
    {
        const int queued = QueuedChunks(voiceIndex);
        if (queued >= 2)
            break;
        unsigned int size = 0, position = 0;
        char *data = nullptr;
        status = Snd_StreamAcquireWindow(streamVoice, &size, &position, &data);
        switch (status)
        {
        case SND_STREAM_OK:
        {
            std::vector<float> &spare = s_streamSpare[streamVoice];
            const int frames = DecodeWindow(header, data, size, spare);
            Snd_StreamReleaseWindow(streamVoice, data);
            if (frames <= 0)
                break;
            std::lock_guard<std::mutex> lock(s_lock);
            MixerVoice &v = s_voices[voiceIndex];
            StreamChunk &slot = v.chunks[(v.chunkHead + v.chunkCount) & 1];
            slot.samples.swap(spare); // the slot's old samples (a played chunk) become the next spare
            slot.frames = frames;
            ++v.chunkCount;
            break;
        }
        case SND_STREAM_STARVING:
            return;
        case SND_STREAM_EOF:
            if (!queued)
                SND_StopVoice(voiceIndex);
            return;
        case SND_STREAM_ERROR:
            iSND_ChannelError(voiceIndex);
            return;
        default:
            return;
        }
    }
}

// The XAudio2 driver's, word for word: open the file stream (primed from RAM when the alias has a prime), then let
// SD_UpdateVoice create the voice once the stream thread has read the header.
int __cdecl SND_StartAliasStream(SndStartAliasInfo *startAliasInfo, unsigned int voiceIndex)
{
    const snd_alias_t *alias = startAliasInfo->alias;
    const unsigned int streamVoice = iSND_GetStreamChannel(voiceIndex);
    char filename[260];
    SND_AliasGetFileName(alias, filename, 256);
    if (!alias->soundFile->exists)
    {
        Com_PrintError(1, "Tried to play streamed sound '%s' from alias '%s', but it was not found at load time.\n",
                       filename, alias->name);
        return SND_SetPlaybackIdNotPlayed(voiceIndex);
    }
    unsigned int primeSize = 0;
    char *primeData = nullptr;
    if ((alias->flags & 0xC000) >> 14 == 3 && alias->soundFile->u.streamSnd->primeSnd)
    {
        primeData = alias->soundFile->u.streamSnd->primeSnd->buffer;
        primeSize = alias->soundFile->u.streamSnd->primeSnd->size;
    }
    Snd_StreamOpen(streamVoice, filename, (alias->flags & 1) != 0, primeSize, primeData);
    SND_SetVoiceStartInfo(voiceIndex, startAliasInfo);
    SND_SetSoundFileVoiceInfo(voiceIndex, 0, 0, 0, 0, SFLS_LOADING);
    SD_UpdateVoice(voiceIndex);
    return g_snd.voice[voiceIndex].alias ? startAliasInfo->playbackId : -1;
}

int __cdecl SD_StartAlias(SndStartAliasInfo *startAliasInfo, unsigned int voice)
{
    if (SND_IsStream(voice))
        return SND_StartAliasStream(startAliasInfo, voice);
    return SND_StartAliasRam(startAliasInfo, int(voice));
}

int __cdecl SND_StartAliasRam(SndStartAliasInfo *startAliasInfo, int voiceIndex)
{
    const bool isLooping = (startAliasInfo->alias->flags & 1) != 0;
    const snd_asset *snd = &startAliasInfo->alias->soundFile->u.loadSnd->sound;

    if (snd->format != SND_ASSET_FORMAT_MSADPCM && snd->format != 0 /*PCM16*/)
        return -1; // WMA has no RAM asset in the zombies zones; nothing to decode

    const int channels = int(snd->channel_count);
    const int frames = int(snd->frame_count);

    // Decode into a local buffer before touching the shared voice, so the callback never sees a half-filled vector.
    std::vector<float> decoded;
    DecodeAsset(snd, frames, channels, decoded);

    {
        std::lock_guard<std::mutex> lock(s_lock);
        MixerVoice &v = s_voices[voiceIndex];
        v.samples.swap(decoded);
        v.frameCount = frames;
        v.inputChannels = channels;
        v.outputChannels = kDeviceChannels;
        v.assetRate = int(snd->frame_rate);
        v.looping = isLooping;
        v.readPos = 0.0;
        v.playedSrc = 0.0;
        v.step = double(snd->frame_rate) / kDeviceRate;
        v.started = false;
        v.paused = false;
        v.drained = false;
        for (float &g : v.dry)
            g = 0.0f;
        for (float &g : v.wet)
            g = 0.0f;
        v.fx = snd_dsp_source_params{};
        std::memset(v.fxState, 0, sizeof(v.fxState));
        v.active = true;
    }

    const unsigned int rate = snd->frame_rate;
    const unsigned int total_msec =
        isLooping ? 0u : unsigned(startAliasInfo->startDelay + (__int64)(double(snd->frame_count) * 1000.0 / rate));
    SND_SetSoundFileVoiceInfo(voiceIndex, channels, int(rate), total_msec, 0, SFLS_LOADED);
    SND_SetVoiceStartInfo(voiceIndex, startAliasInfo);
    return startAliasInfo->playbackId;
}
