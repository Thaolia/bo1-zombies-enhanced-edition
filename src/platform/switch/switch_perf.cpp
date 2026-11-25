// Per-thread CPU use and the CPU/GPU/memory clocks on the console: a "perf:" line in the boot log every 5 s
// (switch_perf.h).
#include <switch.h>

#include "switch_perf.h"

#include <atomic>
#include <cstdio>
#include <cstdlib>
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

// The CPU, GPU and memory (EMC) clocks, read at each perf line: they change with the dock, the system's performance
// mode and overclocking tools, and a frame rate means little without them. clkrst since 8.0.0, pcv before.
const PcvModuleId kClockIds[3] = {PcvModuleId_CpuBus, PcvModuleId_GPU, PcvModuleId_EMC};
const PcvModule kClockModules[3] = {PcvModule_CpuBus, PcvModule_GPU, PcvModule_EMC};
ClkrstSession s_clockSessions[3];
bool s_clocksTried = false;
bool s_clocksOpen = false;
bool s_clocksClkrst = false;

void ClocksExit()
{
    if (!s_clocksOpen)
        return;
    s_clocksOpen = false;
    if (s_clocksClkrst)
    {
        for (ClkrstSession &session : s_clockSessions)
            clkrstCloseSession(&session);
        clkrstExit();
    }
    else
        pcvExit();
}

void ClocksOpen()
{
    s_clocksTried = true;
    s_clocksClkrst = hosversionAtLeast(8, 0, 0);
    Result rc = s_clocksClkrst ? clkrstInitialize() : pcvInitialize();
    int opened = 0;
    if (R_SUCCEEDED(rc) && s_clocksClkrst)
    {
        for (; opened < 3; ++opened)
        {
            rc = clkrstOpenSession(&s_clockSessions[opened], kClockIds[opened], 3);
            if (R_FAILED(rc))
                break;
        }
        if (R_FAILED(rc))
        {
            while (opened > 0)
                clkrstCloseSession(&s_clockSessions[--opened]);
            clkrstExit();
        }
    }
    char note[128];
    if (R_FAILED(rc))
    {
        snprintf(note, sizeof(note), "perf: no clock rates (%s: 0x%X)\n", s_clocksClkrst ? "clkrst" : "pcv",
                 (unsigned)rc);
        Switch_BootLogWrite(note);
        return;
    }
    s_clocksOpen = true;
    std::atexit(ClocksExit);
    snprintf(note, sizeof(note), "perf: clock rates from %s\n", s_clocksClkrst ? "clkrst" : "pcv");
    Switch_BootLogWrite(note);
}

// " cpu 1020 gpu 384 emc 1600 MHz, handheld" (a rate that cannot be read shows as ?)
int ClocksFormat(char *out, int size)
{
    if (!s_clocksTried)
        ClocksOpen();
    int used = 0;
    if (s_clocksOpen)
    {
        static const char *const names[3] = {"cpu", "gpu", "emc"};
        for (int i = 0; i < 3; ++i)
        {
            u32 hz = 0;
            const Result rc = s_clocksClkrst ? clkrstGetClockRate(&s_clockSessions[i], &hz)
                                             : pcvGetClockRate(kClockModules[i], &hz);
            if (R_SUCCEEDED(rc))
                used += snprintf(out + used, size - used, " %s %u", names[i], (unsigned)(hz / 1000000));
            else
                used += snprintf(out + used, size - used, " %s ?", names[i]);
        }
        used += snprintf(out + used, size - used, " MHz,");
    }
    const AppletOperationMode mode = appletGetOperationMode();
    used += snprintf(out + used, size - used, " %s", mode == AppletOperationMode_Console ? "docked" : "handheld");
    return used;
}
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
    int used = snprintf(line, sizeof(line), "perf: %.1f s, %.1f fps,", seconds, frames / seconds);
    used += ClocksFormat(line + used, (int)sizeof(line) - used);
    used += snprintf(line + used, sizeof(line) - used, " |");
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
