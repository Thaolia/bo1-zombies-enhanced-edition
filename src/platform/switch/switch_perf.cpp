// Per-thread CPU use on the console: a "perf:" line in the boot log every 5 s (switch_perf.h).
#include <switch.h>

#include "switch_perf.h"

#include <atomic>
#include <cstdio>
#include <cstring>
#include <map>

extern "C" void Switch_BootLogWrite(const char *text);
extern const char *s_threadNames[15]; // qcommon/threads.cpp, indexed by the thread context

namespace
{
// svcGetInfo's thread tick count: type 25 since 13.0.0, 0xF0000002 before; the handle it wants is tried once
struct TickQuery
{
    u32 type;
    Handle handle;
};
const TickQuery kTickQueries[] = {
    {InfoType_ThreadTickCount, CUR_THREAD_HANDLE},
    {InfoType_ThreadTickCount, INVALID_HANDLE},
    {InfoType_ThreadTickCountDeprecated, CUR_THREAD_HANDLE},
    {InfoType_ThreadTickCountDeprecated, INVALID_HANDLE},
};
const int kTickQueryCount = sizeof(kTickQueries) / sizeof(kTickQueries[0]);
std::atomic<int> s_tickQuery{-1}; // index into kTickQueries, kTickQueryCount when none works
Result s_tickFailure = 0;

const double kWindowSeconds = 5.0;
} // namespace

extern "C" unsigned long long Switch_ThreadTicks(void)
{
    u64 ticks = 0;
    const int known = s_tickQuery.load();
    if (known >= 0)
    {
        if (known < kTickQueryCount)
            svcGetInfo(&ticks, kTickQueries[known].type, kTickQueries[known].handle, UINT64_MAX);
        return ticks;
    }
    for (int i = 0; i < kTickQueryCount; ++i)
    {
        const Result rc = svcGetInfo(&ticks, kTickQueries[i].type, kTickQueries[i].handle, UINT64_MAX);
        if (R_SUCCEEDED(rc))
        {
            s_tickQuery.store(i);
            return ticks;
        }
        s_tickFailure = rc;
    }
    s_tickQuery.store(kTickQueryCount);
    return 0;
}

extern "C" int Switch_CurrentCore(void)
{
    return (int)svcGetCurrentProcessorNumber();
}

extern "C" void Switch_PerfFrame(void)
{
    static u64 windowStart = 0;
    static unsigned frames = 0;
    static std::map<unsigned, unsigned long long> previous;
    static bool reported = false;

    Bo1_SampleCurrentThread();
    const u64 now = armGetSystemTick();
    Bo1ThreadPerf threads[32];
    if (!windowStart)
    {
        windowStart = now;
        const int count = Bo1_ThreadPerfSnapshot(threads, 32);
        for (int i = 0; i < count; ++i)
            previous[threads[i].id] = threads[i].ticks;
        return;
    }
    ++frames;
    const double freq = (double)armGetSystemTickFreq();
    const double seconds = (double)(now - windowStart) / freq;
    if (seconds < kWindowSeconds)
        return;

    if (!reported)
    {
        reported = true;
        char note[160];
        const int query = s_tickQuery.load();
        if (query >= 0 && query < kTickQueryCount)
            snprintf(note, sizeof(note), "perf: thread CPU ticks from svcGetInfo(0x%X, handle 0x%X)\n",
                     (unsigned)kTickQueries[query].type, (unsigned)kTickQueries[query].handle);
        else
            snprintf(note, sizeof(note), "perf: no thread CPU ticks (svcGetInfo 0x%X): the CPU %% below read 0\n",
                     (unsigned)s_tickFailure);
        Switch_BootLogWrite(note);
    }

    // one line: the window's frame rate, then each thread: name, CPU % of one core over the window, last core seen
    char line[1024];
    int used = snprintf(line, sizeof(line), "perf: %.1f s, %.1f fps |", seconds, frames / seconds);
    const int count = Bo1_ThreadPerfSnapshot(threads, 32);
    std::map<unsigned, unsigned long long> current;
    for (int i = 0; i < count && used < (int)sizeof(line) - 48; ++i)
    {
        const Bo1ThreadPerf &t = threads[i];
        current[t.id] = t.ticks;
        auto it = previous.find(t.id);
        const unsigned long long before = it != previous.end() ? it->second : t.ticks;
        const double percent = t.ticks >= before ? 100.0 * (double)(t.ticks - before) / (seconds * freq) : 0.0;
        char name[24];
        if (t.self)
            snprintf(name, sizeof(name), "Main");
        else if (t.created && t.param < 15)
            snprintf(name, sizeof(name), "%s", s_threadNames[t.param]);
        else
            snprintf(name, sizeof(name), "other%u", t.id & 0xFFFF);
        used += snprintf(line + used, sizeof(line) - used, " %s %.0f%% c%d", name, percent, t.core);
    }
    snprintf(line + used, sizeof(line) - used, "\n");
    Switch_BootLogWrite(line);

    previous.swap(current);
    windowStart = now;
    frames = 0;
}
