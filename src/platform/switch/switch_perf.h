#pragma once
// Per-thread CPU use on the console (switch_perf.cpp): every thread the Win32 shim knows samples its own CPU ticks and
// core when it sleeps or waits (win32_threads.cpp), and the main thread logs a "perf:" line every 5 s, with the CPU,
// GPU and memory clocks and the dock mode. No libnx types here: the shim includes this next to its Win32 headers.

#ifdef __cplusplus
extern "C" {
#endif

struct Bo1ThreadPerf
{
    unsigned id;
    unsigned long long param;  // CreateThread's parameter: the engine's thread context (s_threadNames)
    int created;               // started by CreateThread
    int self;                  // the thread taking the snapshot
    unsigned long long ticks;  // CPU ticks the thread had used at its last sample
    int core;                  // the core it ran on at its last sample
};

// switch_perf.cpp
unsigned long long Switch_ThreadTicks(void); // the calling thread's CPU ticks (0 when the kernel will not say)
int Switch_CurrentCore(void);
void Switch_PerfFrame(void);                 // once a frame, from the main thread (Com_Frame)

// win32_threads.cpp
void Bo1_SampleCurrentThread(void);
int Bo1_ThreadPerfSnapshot(struct Bo1ThreadPerf *out, int max);

#ifdef __cplusplus
}
#endif
