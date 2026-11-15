#pragma once
// OpenBSD ships no <ucontext.h>: <signal.h> defines ucontext_t as struct sigcontext (what an SA_SIGINFO handler
// receives), read by the __OpenBSD__ branches of Bo1_CaptureContext and CrashSignalHandler. There is no getcontext.
#include <signal.h>
#include <string.h>

// RaiseException captures the caller's context only to hand it to a reporting filter (as on the Switch, which has no
// getcontext either): an empty context is what that filter then reports.
static inline int getcontext(ucontext_t *uc)
{
    memset(uc, 0, sizeof(*uc));
    return 0;
}
