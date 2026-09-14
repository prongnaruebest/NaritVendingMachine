#include "nucleo_profile_runtime.h"

#include <stddef.h>
#include <string.h>

uint8_t NucleoProfileRuntime_Init(NucleoProfileRuntime *runtime,
                                  NucleoProfileExecutor *executor,
                                  NucleoPulseScheduler *scheduler)
{
  if ((runtime == NULL) || (executor == NULL) || (scheduler == NULL)) return 0U;
  memset(runtime, 0, sizeof(*runtime));
  runtime->executor = executor;
  runtime->scheduler = scheduler;
  runtime->initialized = 1U;
  return 1U;
}

void NucleoProfileRuntime_SetSafety(NucleoProfileRuntime *runtime,
                                    uint64_t now_us,
                                    uint8_t safety_permissive)
{
  if ((runtime == NULL) || (runtime->initialized == 0U)) return;
  runtime->safety_permissive = safety_permissive != 0U ? 1U : 0U;
  NucleoProfileExecutor_Heartbeat(runtime->executor, now_us,
                                  runtime->safety_permissive);
  if (runtime->safety_permissive == 0U) {
    NucleoPulseScheduler_SafetyStop(runtime->scheduler);
  }
}

void NucleoProfileRuntime_ControlTick(void *context, uint64_t now_us)
{
  NucleoProfileRuntime *runtime = (NucleoProfileRuntime *)context;
  NucleoProfileState state;
  if ((runtime == NULL) || (runtime->initialized == 0U)) return;
  state = NucleoProfileExecutor_Tick(runtime->executor, now_us,
                                     runtime->safety_permissive);
  if (state == NUCLEO_PROFILE_RUNNING) {
    if (runtime->executor->trajectory_elapsed != 0U) {
      if (NucleoPulseScheduler_AllComplete(runtime->scheduler) != 0U) {
        NucleoProfileExecutor_Complete(runtime->executor);
      } else {
        /* Never mask a timer underrun as successful terminal completion. */
        runtime->terminal_fault = NUCLEO_PROFILE_RUNTIME_FAULT_PULSE_UNDERRUN;
        NucleoPulseScheduler_Fail(runtime->scheduler);
      }
    } else {
      NucleoPulseScheduler_ControlTick(runtime->scheduler, now_us);
    }
  } else if (state == NUCLEO_PROFILE_SAFETY_STOP) {
    NucleoPulseScheduler_SafetyStop(runtime->scheduler);
  }
}

void NucleoProfileRuntime_SafetyStop(void *context)
{
  NucleoProfileRuntime *runtime = (NucleoProfileRuntime *)context;
  if ((runtime == NULL) || (runtime->initialized == 0U)) return;
  runtime->safety_permissive = 0U;
  NucleoPulseScheduler_SafetyStop(runtime->scheduler);
}
