// Win32 threads, synchronisation and processes on POSIX (Linux). Thread ids are the kernel's thread ids (gettid), so
// they match /proc/self/task, logs and debuggers.

#include "win32_handles.h"

#include <tlhelp32.h>
#include <errno.h>
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/resource.h>
#if !defined(__SWITCH__) // newlib (Switch) has no syscall()/gettid
#include <sys/syscall.h>
#endif
#include <time.h>
#include <ucontext.h>
#include <unistd.h>

#include <map>
#include <mutex>
#include <vector>

#if defined(__SWITCH__)
#include <platform/switch/switch_perf.h>
#endif

namespace
{
thread_local Bo1Thread *t_self = nullptr;
thread_local DWORD t_lastError = 0;

// Threads by id, for OpenThread and the toolhelp snapshot. Each entry holds a reference. Built on first use and never
// destroyed: static initialisers of other files may already start threads, and threads may outlive exit().
std::mutex s_threadsLock;
std::map<DWORD, Bo1Thread *> &Threads()
{
    static std::map<DWORD, Bo1Thread *> *threads = new std::map<DWORD, Bo1Thread *>();
    return *threads;
}

// SuspendThread interrupts the target with this signal; the handler records the context and waits for ResumeThread.
// newlib (Switch) has no real-time signals or SA_SIGINFO sigaction, so the signal-based suspend is desktop-only; a
// real console suspend (svcSetThreadActivity / svcGetThreadContext3) is a boot-milestone task (docs/PORTING.md).
#if defined(__OpenBSD__)
// OpenBSD has no real-time signals; nothing else in the engine or its libraries uses SIGUSR2.
const int BO1_SUSPEND_SIGNAL = SIGUSR2;
#elif !defined(__SWITCH__)
const int BO1_SUSPEND_SIGNAL = SIGRTMIN + 1;
#endif
std::once_flag s_suspendHandlerOnce;

DWORD CurrentKernelThreadId()
{
#if defined(__SWITCH__)
    // No kernel gettid on the console (and no /proc to match it to); a per-thread-unique value is all the engine
    // needs for GetCurrentThreadId.
    return (DWORD)(uintptr_t)pthread_self();
#elif defined(__OpenBSD__)
    return (DWORD)getthrid();
#else
    return (DWORD)syscall(SYS_gettid);
#endif
}

timespec DeadlineAfter(DWORD milliseconds)
{
    timespec deadline;
    clock_gettime(CLOCK_MONOTONIC, &deadline);
    deadline.tv_sec += milliseconds / 1000;
    deadline.tv_nsec += (long)(milliseconds % 1000) * 1000000L;
    if (deadline.tv_nsec >= 1000000000L)
    {
        deadline.tv_sec += 1;
        deadline.tv_nsec -= 1000000000L;
    }
    return deadline;
}

void InitMonotonicCond(pthread_cond_t *cond)
{
    pthread_condattr_t attr;
    pthread_condattr_init(&attr);
    pthread_condattr_setclock(&attr, CLOCK_MONOTONIC);
    pthread_cond_init(cond, &attr);
    pthread_condattr_destroy(&attr);
}

void RegisterThread(Bo1Thread *thread)
{
    Bo1_AddRef(thread);
    std::lock_guard<std::mutex> lock(s_threadsLock);
    Threads()[thread->id] = thread;
}

void UnregisterThread(Bo1Thread *thread)
{
    {
        std::lock_guard<std::mutex> lock(s_threadsLock);
        auto it = Threads().find(thread->id);
        if (it != Threads().end() && it->second == thread)
            Threads().erase(it);
        else
            return;
    }
    Bo1_Release(thread);
}

#if defined(__SWITCH__)
// A .nro's exit() goes back to hbloader in the same process: the threads CreateThread started keep running in code that
// hbloader then unmaps, and the first of them to wake took an instruction abort (2168-0001) at the module's address.
// Bo1_StopThreadsForExit sets s_exiting; a created thread then ends itself at its next Sleep or event wait (infinite
// waits wake every 100 ms to look).
std::atomic<bool> s_exiting{false};
std::atomic<int> s_running{0}; // created threads not yet returned

// At most every 100 ms: a svcGetInfo per sample, and the job queue's workers wait thousands of times a second.
void SampleCpu(Bo1Thread *self)
{
    timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    const long long ns = (long long)now.tv_sec * 1000000000LL + now.tv_nsec;
    if (ns - self->lastSampleNs < 100000000LL)
        return;
    self->lastSampleNs = ns;
    self->cpuTicks.store(Switch_ThreadTicks());
    self->cpuCore.store(Switch_CurrentCore());
}

// Called with no shim lock held.
void ExitIfStopping()
{
    Bo1Thread *self = t_self;
    if (!s_exiting.load() || !self || !self->created)
        return;
    self->exited.Set();
    UnregisterThread(self);
    s_running.fetch_sub(1);
    pthread_exit(nullptr);
}
#endif

// The calling thread's object, created the first time a thread that CreateThread did not start asks for it (the main
// thread, threads of libraries). It lives as long as the process.
Bo1Thread *SelfThread()
{
    if (!t_self)
    {
        Bo1Thread *thread = new Bo1Thread();
        thread->thread = pthread_self();
        thread->id = CurrentKernelThreadId();
        thread->started = true;
        t_self = thread;
        RegisterThread(thread);
    }
    return t_self;
}

Bo1Thread *ThreadFromHandle(HANDLE handle)
{
    if (handle == BO1_PSEUDO_THREAD)
        return SelfThread();
    return Bo1_HandleAs<Bo1Thread>(handle, BO1_OBJ_THREAD);
}

} // namespace

void Bo1_CaptureContext(CONTEXT *context, const ucontext_t *uc)
{
    memset(context, 0, sizeof(*context));
#if defined(__OpenBSD__) && defined(__x86_64__)
    context->ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
    context->Rax = uc->sc_rax;
    context->Rbx = uc->sc_rbx;
    context->Rcx = uc->sc_rcx;
    context->Rdx = uc->sc_rdx;
    context->Rsi = uc->sc_rsi;
    context->Rdi = uc->sc_rdi;
    context->Rbp = uc->sc_rbp;
    context->Rsp = uc->sc_rsp;
    context->R8 = uc->sc_r8;
    context->R9 = uc->sc_r9;
    context->R10 = uc->sc_r10;
    context->R11 = uc->sc_r11;
    context->R12 = uc->sc_r12;
    context->R13 = uc->sc_r13;
    context->R14 = uc->sc_r14;
    context->R15 = uc->sc_r15;
    context->Rip = uc->sc_rip;
    context->EFlags = (DWORD)uc->sc_rflags;
#elif defined(__x86_64__)
    const greg_t *r = uc->uc_mcontext.gregs;
    context->ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
    context->Rax = r[REG_RAX];
    context->Rbx = r[REG_RBX];
    context->Rcx = r[REG_RCX];
    context->Rdx = r[REG_RDX];
    context->Rsi = r[REG_RSI];
    context->Rdi = r[REG_RDI];
    context->Rbp = r[REG_RBP];
    context->Rsp = r[REG_RSP];
    context->R8 = r[REG_R8];
    context->R9 = r[REG_R9];
    context->R10 = r[REG_R10];
    context->R11 = r[REG_R11];
    context->R12 = r[REG_R12];
    context->R13 = r[REG_R13];
    context->R14 = r[REG_R14];
    context->R15 = r[REG_R15];
    context->Rip = r[REG_RIP];
    context->EFlags = (DWORD)r[REG_EFL];
#elif defined(__aarch64__)
    context->ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
    for (int i = 0; i < 31; ++i)
        context->X[i] = uc->uc_mcontext.regs[i];
    context->Sp = uc->uc_mcontext.sp;
    context->Pc = uc->uc_mcontext.pc;
    context->Cpsr = (DWORD)uc->uc_mcontext.pstate;
#endif
}

namespace
{

#if !defined(__SWITCH__)
void SuspendSignalHandler(int, siginfo_t *, void *ucontext)
{
    const int savedErrno = errno;
    Bo1Thread *self = t_self;
    if (self)
    {
        Bo1_CaptureContext(&self->context, static_cast<ucontext_t *>(ucontext));
        sem_post(&self->suspendAck);
        while (sem_wait(&self->resume) && errno == EINTR)
            ;
    }
    errno = savedErrno;
}

void InstallSuspendHandler()
{
    struct sigaction action = {};
    action.sa_sigaction = SuspendSignalHandler;
    action.sa_flags = SA_SIGINFO | SA_RESTART;
    sigemptyset(&action.sa_mask);
    sigaction(BO1_SUSPEND_SIGNAL, &action, nullptr);
}
#else
// No signal-based suspend on the console; CreateThread still calls this once, so it must exist as a no-op.
void InstallSuspendHandler()
{
}
#endif

struct ThreadStart
{
    Bo1Thread *thread;
    pthread_mutex_t mutex;
    pthread_cond_t cond;
    bool idReady = false;
};

void *ThreadTrampoline(void *arg)
{
    ThreadStart *start = static_cast<ThreadStart *>(arg);
    Bo1Thread *thread = start->thread;
    thread->id = CurrentKernelThreadId();
    t_self = thread;
    RegisterThread(thread);
    pthread_mutex_lock(&start->mutex);
    start->idReady = true;
    pthread_cond_signal(&start->cond);
    pthread_mutex_unlock(&start->mutex);

    pthread_mutex_lock(&thread->gateMutex);
    while (thread->suspendCount > 0)
        pthread_cond_wait(&thread->gateCond, &thread->gateMutex);
    thread->started = true;
    pthread_mutex_unlock(&thread->gateMutex);

    thread->exitCode = thread->start(thread->parameter);
    thread->exited.Set();
    UnregisterThread(thread);
    Bo1_Release(thread); // the reference CreateThread gave the running thread
#if defined(__SWITCH__)
    s_running.fetch_sub(1);
#endif
    return nullptr;
}
} // namespace

// ---- objects

Bo1Event::Bo1Event(bool manual, bool initialState) : Bo1Object(BO1_OBJ_EVENT), manualReset(manual), signaled(initialState)
{
    pthread_mutex_init(&mutex, nullptr);
    InitMonotonicCond(&cond);
}

Bo1Event::~Bo1Event()
{
    pthread_cond_destroy(&cond);
    pthread_mutex_destroy(&mutex);
}

bool Bo1Event::Wait(DWORD milliseconds)
{
#if defined(__SWITCH__)
    ExitIfStopping();
    if (t_self)
        SampleCpu(t_self);
#endif
    const timespec deadline = DeadlineAfter(milliseconds == INFINITE ? 0 : milliseconds);
    pthread_mutex_lock(&mutex);
    const uint64_t generation = pulseGeneration;
    ++waiters;
    bool released = false;
    while (true)
    {
        if (signaled)
        {
            if (!manualReset)
                signaled = false;
            released = true;
            break;
        }
        if (pulseGeneration != generation && (manualReset || pulseReleases > 0))
        {
            if (!manualReset)
                --pulseReleases;
            released = true;
            break;
        }
        if (milliseconds == INFINITE)
        {
#if defined(__SWITCH__)
            const timespec slice = DeadlineAfter(100);
            pthread_cond_timedwait(&cond, &mutex, &slice);
            if (s_exiting.load() && t_self && t_self->created)
            {
                --waiters;
                pthread_mutex_unlock(&mutex);
                ExitIfStopping();
            }
#else
            pthread_cond_wait(&cond, &mutex);
#endif
        }
        else if (pthread_cond_timedwait(&cond, &mutex, &deadline) == ETIMEDOUT)
            break;
    }
    --waiters;
    pthread_mutex_unlock(&mutex);
    return released;
}

void Bo1Event::Set()
{
    pthread_mutex_lock(&mutex);
    signaled = true;
    if (manualReset)
        pthread_cond_broadcast(&cond);
    else
        pthread_cond_signal(&cond);
    pthread_mutex_unlock(&mutex);
}

void Bo1Event::Reset()
{
    pthread_mutex_lock(&mutex);
    signaled = false;
    pthread_mutex_unlock(&mutex);
}

// Releases the threads waiting right now (all of them for a manual-reset event, one for an auto-reset one) and leaves
// the event non-signalled; with no waiter it only resets the event.
void Bo1Event::Pulse()
{
    pthread_mutex_lock(&mutex);
    signaled = false;
    if (waiters > 0)
    {
        ++pulseGeneration;
        pulseReleases = 1;
        pthread_cond_broadcast(&cond);
    }
    pthread_mutex_unlock(&mutex);
}

Bo1Thread::Bo1Thread() : Bo1Object(BO1_OBJ_THREAD)
{
    pthread_mutex_init(&gateMutex, nullptr);
    pthread_cond_init(&gateCond, nullptr);
    sem_init(&suspendAck, 0, 0);
    sem_init(&resume, 0, 0);
}

Bo1Thread::~Bo1Thread()
{
    sem_destroy(&resume);
    sem_destroy(&suspendAck);
    pthread_cond_destroy(&gateCond);
    pthread_mutex_destroy(&gateMutex);
}

Bo1Mutex::Bo1Mutex() : Bo1Object(BO1_OBJ_MUTEX)
{
    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);
    pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
    pthread_mutex_init(&mutex, &attr);
    pthread_mutexattr_destroy(&attr);
}

Bo1Mutex::~Bo1Mutex()
{
    pthread_mutex_destroy(&mutex);
}

void Bo1_AddRef(Bo1Object *object)
{
    object->refs.fetch_add(1, std::memory_order_relaxed);
}

void Bo1_Release(Bo1Object *object)
{
    if (object->refs.fetch_sub(1, std::memory_order_acq_rel) == 1)
        delete object;
}

void Bo1_SetLastError(DWORD error)
{
    t_lastError = error;
}

DWORD Bo1_ErrorFromErrno(int error)
{
    switch (error)
    {
    case 0:
        return ERROR_SUCCESS;
    case ENOENT:
        return ERROR_FILE_NOT_FOUND;
    case ENOTDIR:
        return ERROR_PATH_NOT_FOUND;
    case EACCES:
    case EPERM:
    case EROFS:
        return ERROR_ACCESS_DENIED;
    case EBADF:
        return ERROR_INVALID_HANDLE;
    case ENOMEM:
        return ERROR_NOT_ENOUGH_MEMORY;
    case EEXIST:
        return ERROR_ALREADY_EXISTS;
    case ENOTEMPTY:
        return ERROR_DIR_NOT_EMPTY;
    case ENOSPC:
        return ERROR_DISK_FULL;
    case ENOSYS:
    case ENOTSUP:
        return ERROR_NOT_SUPPORTED;
    default:
        return ERROR_INVALID_PARAMETER;
    }
}

// ---- completion routines (ReadFileEx), run by the issuing thread's alertable waits

namespace
{
struct QueuedCompletion
{
    LPOVERLAPPED_COMPLETION_ROUTINE routine;
    DWORD error;
    DWORD bytes;
    LPOVERLAPPED overlapped;
};
thread_local std::vector<QueuedCompletion> t_completions;
} // namespace

void Bo1_QueueCompletion(LPOVERLAPPED_COMPLETION_ROUTINE routine, DWORD error, DWORD bytes, LPOVERLAPPED overlapped)
{
    t_completions.push_back({routine, error, bytes, overlapped});
}

int Bo1_RunQueuedCompletions()
{
    int count = 0;
    while (!t_completions.empty())
    {
        const QueuedCompletion completion = t_completions.front();
        t_completions.erase(t_completions.begin());
        completion.routine(completion.error, completion.bytes, completion.overlapped);
        ++count;
    }
    return count;
}

// ---- Win32 API

extern "C" {

DWORD GetLastError(void)
{
    return t_lastError;
}

void SetLastError(DWORD dwErrCode)
{
    t_lastError = dwErrCode;
}

BOOL CloseHandle(HANDLE hObject)
{
    if (hObject == BO1_PSEUDO_PROCESS || hObject == BO1_PSEUDO_THREAD)
        return TRUE;
    if (!hObject || hObject == INVALID_HANDLE_VALUE)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return FALSE;
    }
    Bo1_Release(static_cast<Bo1Object *>(hObject));
    return TRUE;
}

BOOL DuplicateHandle(HANDLE hSourceProcessHandle, HANDLE hSourceHandle, HANDLE hTargetProcessHandle,
                     LPHANDLE lpTargetHandle, DWORD, BOOL, DWORD)
{
    if (hSourceProcessHandle != BO1_PSEUDO_PROCESS || hTargetProcessHandle != BO1_PSEUDO_PROCESS || !lpTargetHandle)
    {
        Bo1_SetLastError(ERROR_INVALID_PARAMETER);
        return FALSE;
    }
    if (hSourceHandle == BO1_PSEUDO_PROCESS)
    {
        *lpTargetHandle = BO1_PSEUDO_PROCESS;
        return TRUE;
    }
    Bo1Object *object =
        hSourceHandle == BO1_PSEUDO_THREAD ? SelfThread() : static_cast<Bo1Object *>(hSourceHandle);
    if (!object || hSourceHandle == INVALID_HANDLE_VALUE)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return FALSE;
    }
    Bo1_AddRef(object);
    *lpTargetHandle = object;
    return TRUE;
}

HANDLE GetCurrentProcess(void)
{
    return BO1_PSEUDO_PROCESS;
}

DWORD GetCurrentProcessId(void)
{
    return (DWORD)getpid();
}

// The engine only opens its own process (tl_system.cpp, for its memory counters).
HANDLE OpenProcess(DWORD, BOOL, DWORD dwProcessId)
{
    if (dwProcessId == (DWORD)getpid())
        return BO1_PSEUDO_PROCESS;
    Bo1_SetLastError(ERROR_ACCESS_DENIED);
    return nullptr;
}

HANDLE CreateThread(LPSECURITY_ATTRIBUTES, SIZE_T dwStackSize, LPTHREAD_START_ROUTINE lpStartAddress,
                    LPVOID lpParameter, DWORD dwCreationFlags, LPDWORD lpThreadId)
{
    std::call_once(s_suspendHandlerOnce, InstallSuspendHandler);
    Bo1Thread *thread = new Bo1Thread();
    thread->created = true;
    thread->start = lpStartAddress;
    thread->parameter = lpParameter;
    thread->suspendCount = (dwCreationFlags & CREATE_SUSPENDED) ? 1 : 0;
    Bo1_AddRef(thread); // held by the running thread until it returns

    ThreadStart start = {thread};
    pthread_mutex_init(&start.mutex, nullptr);
    pthread_cond_init(&start.cond, nullptr);
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
    // Windows takes dwStackSize as the stack's initial commit: the thread still grows up to the exe's reserve (1 MiB,
    // the MSVC /STACK default; a larger size rounds the reserve up to a MiB multiple). A pthread stack is fixed at
    // creation, so the job-queue workers' 0x10000 and devkitA64's default (0 here, 128 KiB in libnx) would cap 64-bit
    // frames far below what the Windows threads get. Give every thread at least the Windows reserve.
    const size_t windowsReserve = size_t(1) << 20;
    size_t stackSize = (dwStackSize + windowsReserve - 1) & ~(windowsReserve - 1);
    if (stackSize < windowsReserve)
        stackSize = windowsReserve;
    size_t defaultSize = 0;
    pthread_attr_getstacksize(&attr, &defaultSize); // glibc: RLIMIT_STACK (8 MiB)
    if (defaultSize > stackSize)
        stackSize = defaultSize;
    pthread_attr_setstacksize(&attr, stackSize);
#if defined(__SWITCH__)
    s_running.fetch_add(1);
#endif
    const int error = pthread_create(&thread->thread, &attr, ThreadTrampoline, &start);
    pthread_attr_destroy(&attr);
    if (error)
    {
#if defined(__SWITCH__)
        s_running.fetch_sub(1);
#endif
        pthread_cond_destroy(&start.cond);
        pthread_mutex_destroy(&start.mutex);
        delete thread;
        Bo1_SetLastError(ERROR_NOT_ENOUGH_MEMORY);
        return nullptr;
    }
    pthread_mutex_lock(&start.mutex);
    while (!start.idReady)
        pthread_cond_wait(&start.cond, &start.mutex);
    pthread_mutex_unlock(&start.mutex);
    pthread_cond_destroy(&start.cond);
    pthread_mutex_destroy(&start.mutex);
    if (lpThreadId)
        *lpThreadId = thread->id;
    return Bo1_ToHandle(thread);
}

HANDLE GetCurrentThread(void)
{
    return BO1_PSEUDO_THREAD;
}

DWORD GetCurrentThreadId(void)
{
    return SelfThread()->id;
}

DWORD GetCurrentProcessorNumber(void)
{
#if defined(__OpenBSD__)
    return 0; // OpenBSD does not tell a thread which CPU runs it
#else
    const int cpu = sched_getcpu();
    return cpu < 0 ? 0 : (DWORD)cpu;
#endif
}

HANDLE OpenThread(DWORD, BOOL, DWORD dwThreadId)
{
    std::lock_guard<std::mutex> lock(s_threadsLock);
    auto it = Threads().find(dwThreadId);
    if (it == Threads().end())
    {
        Bo1_SetLastError(ERROR_INVALID_PARAMETER);
        return nullptr;
    }
    Bo1_AddRef(it->second);
    return Bo1_ToHandle(it->second);
}

DWORD SuspendThread(HANDLE hThread)
{
    Bo1Thread *thread = ThreadFromHandle(hThread);
    if (!thread || thread == t_self)
    {
        // Suspending oneself would never return here: the engine only suspends other threads.
        Bo1_SetLastError(thread ? ERROR_NOT_SUPPORTED : ERROR_INVALID_HANDLE);
        return (DWORD)-1;
    }
    pthread_mutex_lock(&thread->gateMutex);
    const int previous = thread->suspendCount.fetch_add(1);
    const bool interrupt = previous == 0 && thread->started;
    pthread_mutex_unlock(&thread->gateMutex);
#if !defined(__SWITCH__)
    if (interrupt)
    {
        if (pthread_kill(thread->thread, BO1_SUSPEND_SIGNAL))
        {
            thread->suspendCount.fetch_sub(1);
            Bo1_SetLastError(ERROR_INVALID_HANDLE);
            return (DWORD)-1;
        }
        while (sem_wait(&thread->suspendAck) && errno == EINTR)
            ;
    }
#else
    // The console has no signal-based interrupt yet: the count is tracked but the target is not actually stopped
    // (GetThreadContext then reads an empty context, which its callers already guard against). (docs/PORTING.md)
    (void)interrupt;
#endif
    return (DWORD)previous;
}

BOOL GetExitCodeThread(HANDLE hThread, LPDWORD lpExitCode)
{
    Bo1Thread *thread = ThreadFromHandle(hThread);
    if (!thread || !lpExitCode)
    {
        Bo1_SetLastError(thread ? ERROR_INVALID_PARAMETER : ERROR_INVALID_HANDLE);
        return FALSE;
    }
    *lpExitCode = thread->exited.Wait(0) ? thread->exitCode : STILL_ACTIVE;
    return TRUE;
}

// POSIX has no safe way to end another thread where it stands (pthread_cancel only stops at cancellation points and
// runs no Windows semantics), so a running thread is left alone and the call fails. CubeMapGenLib, the only caller,
// reaches it after its filter threads have finished.
BOOL TerminateThread(HANDLE hThread, DWORD)
{
    Bo1Thread *thread = ThreadFromHandle(hThread);
    if (!thread)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return FALSE;
    }
    if (thread->exited.Wait(0))
        return TRUE;
    Bo1_SetLastError(ERROR_NOT_SUPPORTED);
    return FALSE;
}

DWORD ResumeThread(HANDLE hThread)
{
    Bo1Thread *thread = ThreadFromHandle(hThread);
    if (!thread)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return (DWORD)-1;
    }
    pthread_mutex_lock(&thread->gateMutex);
    const int previous = thread->suspendCount;
    if (previous > 0 && --thread->suspendCount == 0)
    {
        if (thread->started)
            sem_post(&thread->resume);
        else
            pthread_cond_signal(&thread->gateCond);
    }
    pthread_mutex_unlock(&thread->gateMutex);
    return (DWORD)previous;
}

// Valid while the thread is suspended, as on Windows: the context is the one its suspend signal interrupted.
BOOL GetThreadContext(HANDLE hThread, LPCONTEXT lpContext)
{
    Bo1Thread *thread = ThreadFromHandle(hThread);
    if (!thread || !lpContext || thread->suspendCount == 0 || !thread->started)
    {
        Bo1_SetLastError(ERROR_INVALID_PARAMETER);
        return FALSE;
    }
    const DWORD flags = lpContext->ContextFlags;
    *lpContext = thread->context;
    lpContext->ContextFlags = flags;
    return TRUE;
}

int GetThreadPriority(HANDLE hThread)
{
    Bo1Thread *thread = ThreadFromHandle(hThread);
    return thread ? thread->priority : 0x7FFFFFFF; // THREAD_PRIORITY_ERROR_RETURN
}

// Linux schedules threads by their nice value; an unprivileged process may lower its threads' priority but not raise
// it, so a raise fails as it would for a Windows process without the privilege.
BOOL SetThreadPriority(HANDLE hThread, int nPriority)
{
    Bo1Thread *thread = ThreadFromHandle(hThread);
    if (!thread)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return FALSE;
    }
#if defined(__SWITCH__)
    // Per-thread priority is set with svcSetThreadPriority at the boot milestone; record the value for now.
    thread->priority = nPriority;
    return TRUE;
#else
    const int nice = nPriority >= 15 ? -15 : nPriority <= -15 ? 19 : -nPriority * 2;
    if (setpriority(PRIO_PROCESS, (id_t)thread->id, nice))
    {
        Bo1_SetLastError(Bo1_ErrorFromErrno(errno));
        return FALSE;
    }
    thread->priority = nPriority;
    return TRUE;
#endif
}

DWORD_PTR SetThreadAffinityMask(HANDLE hThread, DWORD_PTR dwThreadAffinityMask)
{
    Bo1Thread *thread = ThreadFromHandle(hThread);
    if (!thread)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return 0;
    }
#if defined(__SWITCH__)
    // Core affinity is a per-thread svcSetThreadCoreMask at the boot milestone; applications run on cores 0-2, so
    // report that as the previous mask (non-zero means success).
    (void)dwThreadAffinityMask;
    return 0x7;
#elif defined(__OpenBSD__)
    // OpenBSD has no thread affinity: as on the Switch, the request is ignored and the previous mask reported is every
    // online CPU (non-zero means success).
    (void)dwThreadAffinityMask;
    const long cpus = sysconf(_SC_NPROCESSORS_ONLN);
    if (cpus >= (long)(sizeof(DWORD_PTR) * 8))
        return ~(DWORD_PTR)0;
    return cpus > 0 ? ((DWORD_PTR)1 << cpus) - 1 : 1;
#else
    cpu_set_t previous;
    CPU_ZERO(&previous);
    if (pthread_getaffinity_np(thread->thread, sizeof(previous), &previous))
        return 0;
    cpu_set_t wanted;
    CPU_ZERO(&wanted);
    for (int cpu = 0; cpu < (int)(sizeof(DWORD_PTR) * 8); ++cpu)
    {
        if (dwThreadAffinityMask & ((DWORD_PTR)1 << cpu))
            CPU_SET(cpu, &wanted);
    }
    if (pthread_setaffinity_np(thread->thread, sizeof(wanted), &wanted))
    {
        Bo1_SetLastError(ERROR_INVALID_PARAMETER);
        return 0;
    }
    DWORD_PTR mask = 0;
    for (int cpu = 0; cpu < (int)(sizeof(DWORD_PTR) * 8); ++cpu)
    {
        if (CPU_ISSET(cpu, &previous))
            mask |= (DWORD_PTR)1 << cpu;
    }
    return mask;
#endif
}

// Linux has no ideal-processor hint: the call fails, as Windows reports it when the hint cannot be set.
DWORD SetThreadIdealProcessor(HANDLE, DWORD)
{
    Bo1_SetLastError(ERROR_NOT_SUPPORTED);
    return (DWORD)-1;
}

#if defined(__SWITCH__)
extern "C" void Bo1_SampleCurrentThread(void)
{
    SampleCpu(SelfThread());
}

extern "C" int Bo1_ThreadPerfSnapshot(Bo1ThreadPerf *out, int max)
{
    Bo1Thread *self = SelfThread();
    std::lock_guard<std::mutex> lock(s_threadsLock);
    int count = 0;
    for (const auto &entry : Threads())
    {
        if (count >= max)
            break;
        Bo1Thread *thread = entry.second;
        Bo1ThreadPerf &t = out[count++];
        t.id = (unsigned)thread->id;
        t.param = (unsigned long long)(uintptr_t)thread->parameter;
        t.created = thread->created ? 1 : 0;
        t.self = thread == self ? 1 : 0;
        t.ticks = thread->cpuTicks.load();
        t.core = thread->cpuCore.load();
    }
    return count;
}

extern "C" int Bo1_StopThreadsForExit(unsigned timeoutMs)
{
    s_exiting.store(true);
    const timespec step = {0, 5000000L};
    for (unsigned waited = 0; s_running.load() > 0 && waited < timeoutMs; waited += 5)
        nanosleep(&step, nullptr);
    return s_running.load();
}
#endif

void Sleep(DWORD dwMilliseconds)
{
#if defined(__SWITCH__)
    ExitIfStopping();
    if (t_self)
        SampleCpu(t_self);
#endif
    if (!dwMilliseconds)
    {
        sched_yield();
        return;
    }
    timespec duration = {(time_t)(dwMilliseconds / 1000), (long)(dwMilliseconds % 1000) * 1000000L};
    while (nanosleep(&duration, &duration) && errno == EINTR)
        ;
}

DWORD SleepEx(DWORD dwMilliseconds, BOOL bAlertable)
{
    if (bAlertable && Bo1_RunQueuedCompletions())
        return WAIT_IO_COMPLETION;
    if (dwMilliseconds == INFINITE)
    {
        // Completions are queued by this thread's own ReadFileEx calls, so nothing can end this wait.
        fprintf(stderr, "SleepEx(INFINITE) with no queued completion: the thread waits forever\n");
        while (true)
            pause();
    }
    Sleep(dwMilliseconds);
    return 0;
}

BOOL SwitchToThread(void)
{
    sched_yield();
    return TRUE;
}

// ---- synchronisation

DWORD WaitForSingleObject(HANDLE hHandle, DWORD dwMilliseconds)
{
    if (hHandle == BO1_PSEUDO_THREAD || hHandle == BO1_PSEUDO_PROCESS || !hHandle || hHandle == INVALID_HANDLE_VALUE)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return WAIT_FAILED;
    }
    Bo1Object *object = static_cast<Bo1Object *>(hHandle);
    switch (object->type)
    {
    case BO1_OBJ_EVENT:
        return static_cast<Bo1Event *>(object)->Wait(dwMilliseconds) ? WAIT_OBJECT_0 : WAIT_TIMEOUT;
    case BO1_OBJ_THREAD:
        return static_cast<Bo1Thread *>(object)->exited.Wait(dwMilliseconds) ? WAIT_OBJECT_0 : WAIT_TIMEOUT;
    case BO1_OBJ_MUTEX:
    {
        Bo1Mutex *mutex = static_cast<Bo1Mutex *>(object);
        if (dwMilliseconds == INFINITE)
            return pthread_mutex_lock(&mutex->mutex) ? WAIT_FAILED : WAIT_OBJECT_0;
        timespec deadline;
        clock_gettime(CLOCK_REALTIME, &deadline);
        deadline.tv_sec += dwMilliseconds / 1000;
        deadline.tv_nsec += (long)(dwMilliseconds % 1000) * 1000000L;
        if (deadline.tv_nsec >= 1000000000L)
        {
            deadline.tv_sec += 1;
            deadline.tv_nsec -= 1000000000L;
        }
        int error;
#if defined(__SWITCH__)
        // newlib has no pthread_mutex_timedlock; poll trylock until the deadline (millisecond granularity is fine for
        // the engine's timed waits on a mutex).
        while ((error = pthread_mutex_trylock(&mutex->mutex)) == EBUSY)
        {
            struct timespec now;
            clock_gettime(CLOCK_REALTIME, &now);
            if (now.tv_sec > deadline.tv_sec || (now.tv_sec == deadline.tv_sec && now.tv_nsec >= deadline.tv_nsec))
            {
                error = ETIMEDOUT;
                break;
            }
            const struct timespec nap = {0, 1000000L}; // 1 ms
            nanosleep(&nap, nullptr);
        }
#else
        error = pthread_mutex_timedlock(&mutex->mutex, &deadline);
#endif
        return !error ? WAIT_OBJECT_0 : error == ETIMEDOUT ? WAIT_TIMEOUT : WAIT_FAILED;
    }
    default:
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return WAIT_FAILED;
    }
}

HANDLE CreateEventA(LPSECURITY_ATTRIBUTES, BOOL bManualReset, BOOL bInitialState, LPCSTR lpName)
{
    if (lpName)
    {
        // Named events are shared between processes; the engine never names one.
        Bo1_SetLastError(ERROR_NOT_SUPPORTED);
        return nullptr;
    }
    return Bo1_ToHandle(new Bo1Event(bManualReset != 0, bInitialState != 0));
}

BOOL SetEvent(HANDLE hEvent)
{
    Bo1Event *event = Bo1_HandleAs<Bo1Event>(hEvent, BO1_OBJ_EVENT);
    if (!event)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return FALSE;
    }
    event->Set();
    return TRUE;
}

BOOL ResetEvent(HANDLE hEvent)
{
    Bo1Event *event = Bo1_HandleAs<Bo1Event>(hEvent, BO1_OBJ_EVENT);
    if (!event)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return FALSE;
    }
    event->Reset();
    return TRUE;
}

BOOL PulseEvent(HANDLE hEvent)
{
    Bo1Event *event = Bo1_HandleAs<Bo1Event>(hEvent, BO1_OBJ_EVENT);
    if (!event)
    {
        Bo1_SetLastError(ERROR_INVALID_HANDLE);
        return FALSE;
    }
    event->Pulse();
    return TRUE;
}

HANDLE CreateMutexA(LPSECURITY_ATTRIBUTES, BOOL bInitialOwner, LPCSTR lpName)
{
    if (lpName)
    {
        Bo1_SetLastError(ERROR_NOT_SUPPORTED);
        return nullptr;
    }
    Bo1Mutex *mutex = new Bo1Mutex();
    if (bInitialOwner)
        pthread_mutex_lock(&mutex->mutex);
    return Bo1_ToHandle(mutex);
}

BOOL ReleaseMutex(HANDLE hMutex)
{
    Bo1Mutex *mutex = Bo1_HandleAs<Bo1Mutex>(hMutex, BO1_OBJ_MUTEX);
    if (!mutex || pthread_mutex_unlock(&mutex->mutex))
    {
        Bo1_SetLastError(mutex ? ERROR_NOT_OWNER : ERROR_INVALID_HANDLE);
        return FALSE;
    }
    return TRUE;
}

void InitializeCriticalSection(LPCRITICAL_SECTION lpCriticalSection)
{
    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);
    pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
    pthread_mutex_init(&lpCriticalSection->Mutex, &attr);
    pthread_mutexattr_destroy(&attr);
}

void EnterCriticalSection(LPCRITICAL_SECTION lpCriticalSection)
{
    pthread_mutex_lock(&lpCriticalSection->Mutex);
}

BOOL TryEnterCriticalSection(LPCRITICAL_SECTION lpCriticalSection)
{
    return pthread_mutex_trylock(&lpCriticalSection->Mutex) == 0;
}

void LeaveCriticalSection(LPCRITICAL_SECTION lpCriticalSection)
{
    pthread_mutex_unlock(&lpCriticalSection->Mutex);
}

void AcquireSRWLockExclusive(PSRWLOCK SRWLock)
{
    pthread_rwlock_wrlock(&SRWLock->Lock);
}

void ReleaseSRWLockExclusive(PSRWLOCK SRWLock)
{
    pthread_rwlock_unlock(&SRWLock->Lock);
}

void AcquireSRWLockShared(PSRWLOCK SRWLock)
{
    pthread_rwlock_rdlock(&SRWLock->Lock);
}

void ReleaseSRWLockShared(PSRWLOCK SRWLock)
{
    pthread_rwlock_unlock(&SRWLock->Lock);
}

} // extern "C"

// Toolhelp snapshot of the threads (tlhelp32.h), from the registry above.
namespace
{
struct Bo1Snapshot : Bo1Object
{
    Bo1Snapshot() : Bo1Object(BO1_OBJ_SNAPSHOT) {}
    std::vector<DWORD> threadIds;
    size_t next = 0;
};

BOOL FillThreadEntry(Bo1Snapshot *snapshot, LPTHREADENTRY32 entry)
{
    if (!snapshot || !entry || snapshot->next >= snapshot->threadIds.size())
    {
        Bo1_SetLastError(ERROR_NO_MORE_FILES);
        return FALSE;
    }
    entry->cntUsage = 0;
    entry->th32ThreadID = snapshot->threadIds[snapshot->next++];
    entry->th32OwnerProcessID = (DWORD)getpid();
    entry->tpBasePri = 8;
    entry->tpDeltaPri = 0;
    entry->dwFlags = 0;
    return TRUE;
}
} // namespace

extern "C" {

HANDLE CreateToolhelp32Snapshot(DWORD dwFlags, DWORD)
{
    if (!(dwFlags & TH32CS_SNAPTHREAD))
    {
        Bo1_SetLastError(ERROR_NOT_SUPPORTED);
        return INVALID_HANDLE_VALUE;
    }
    Bo1Snapshot *snapshot = new Bo1Snapshot();
    std::lock_guard<std::mutex> lock(s_threadsLock);
    for (const auto &entry : Threads())
        snapshot->threadIds.push_back(entry.first);
    return Bo1_ToHandle(snapshot);
}

BOOL Thread32First(HANDLE hSnapshot, LPTHREADENTRY32 lpte)
{
    Bo1Snapshot *snapshot = Bo1_HandleAs<Bo1Snapshot>(hSnapshot, BO1_OBJ_SNAPSHOT);
    if (snapshot)
        snapshot->next = 0;
    return FillThreadEntry(snapshot, lpte);
}

BOOL Thread32Next(HANDLE hSnapshot, LPTHREADENTRY32 lpte)
{
    return FillThreadEntry(Bo1_HandleAs<Bo1Snapshot>(hSnapshot, BO1_OBJ_SNAPSHOT), lpte);
}

// Snapshots only list threads (TH32CS_SNAPMODULE is refused): none has a module entry.
BOOL Module32First(HANDLE hSnapshot, LPMODULEENTRY32)
{
    Bo1_SetLastError(Bo1_HandleAs<Bo1Snapshot>(hSnapshot, BO1_OBJ_SNAPSHOT) ? ERROR_NO_MORE_FILES : ERROR_INVALID_HANDLE);
    return FALSE;
}

BOOL Module32Next(HANDLE hSnapshot, LPMODULEENTRY32 lpme)
{
    return Module32First(hSnapshot, lpme);
}

} // extern "C"
