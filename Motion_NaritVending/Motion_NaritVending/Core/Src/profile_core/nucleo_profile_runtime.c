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

NucleoProfileResult NucleoProfileRuntime_Start(
    NucleoProfileRuntime *runtime, NucleoProfileBuffer *buffer,
    uint64_t now_us)
{
  NucleoProfileResult result;
  if ((runtime == NULL) || (runtime->initialized == 0U) || (buffer == NULL) ||
      (runtime->safety_permissive == 0U)) return NUCLEO_PROFILE_ERR_STATE;
  result = NucleoProfileExecutor_Start(runtime->executor, buffer, now_us, 1U);
  if (result != NUCLEO_PROFILE_OK) return result;
  result = NucleoPulseScheduler_Start(runtime->scheduler);
  if (result != NUCLEO_PROFILE_OK) {
    NucleoPulseScheduler_Fail(runtime->scheduler);
    return result;
  }
  runtime->terminal_fault = NUCLEO_PROFILE_RUNTIME_FAULT_NONE;
  return NUCLEO_PROFILE_OK;
}

NucleoProfileResult NucleoProfileRuntime_Reset(
    NucleoProfileRuntime *runtime, NucleoProfileBuffer *buffer)
{
  if ((runtime == NULL) || (runtime->initialized == 0U) || (buffer == NULL) ||
      (runtime->safety_permissive == 0U) ||
      (runtime->executor->running != 0U)) return NUCLEO_PROFILE_ERR_STATE;
  /* Reset acknowledges a terminal state; it never rearms or starts motion. */
  NucleoProfileBuffer_Init(buffer);
  NucleoProfileExecutor_Reset(runtime->executor);
  NucleoPulseScheduler_Reset(runtime->scheduler);
  runtime->terminal_fault = NUCLEO_PROFILE_RUNTIME_FAULT_NONE;
  return NUCLEO_PROFILE_OK;
}

uint8_t NucleoProfileRuntime_GetTelemetry(
    const NucleoProfileRuntime *runtime,
    NucleoProfileRuntimeTelemetry *telemetry)
{
  uint8_t axis;
  if ((runtime == NULL) || (runtime->initialized == 0U) ||
      (runtime->executor == NULL) || (runtime->scheduler == NULL) ||
      (runtime->executor->buffer == NULL) || (telemetry == NULL)) return 0U;
  memset(telemetry, 0, sizeof(*telemetry));
  telemetry->state = runtime->executor->buffer->state;
  telemetry->terminal_fault = runtime->terminal_fault;
  telemetry->command_id = runtime->executor->buffer->command_id;
  telemetry->trajectory_elapsed = runtime->executor->trajectory_elapsed;
  telemetry->safety_permissive = runtime->safety_permissive;
  for (axis = 0U; axis < 2U; axis++) {
    telemetry->target_steps[axis] = runtime->scheduler->target_steps[axis];
    telemetry->emitted_steps[axis] = runtime->scheduler->emitted_steps[axis];
    telemetry->axis_active[axis] = runtime->scheduler->active[axis];
  }
  return 1U;
}

const char *NucleoProfileRuntime_StateName(NucleoProfileState state)
{
  switch (state) {
    case NUCLEO_PROFILE_EMPTY: return "EMPTY";
    case NUCLEO_PROFILE_BUFFERED: return "BUFFERED";
    case NUCLEO_PROFILE_RUNNING: return "RUNNING";
    case NUCLEO_PROFILE_COMPLETE: return "COMPLETE";
    case NUCLEO_PROFILE_SAFETY_STOP: return "SAFETY_STOP";
    case NUCLEO_PROFILE_FAILED: return "FAILED";
    default: return "UNKNOWN";
  }
}

const char *NucleoProfileRuntime_FaultName(NucleoProfileRuntimeFault fault)
{
  switch (fault) {
    case NUCLEO_PROFILE_RUNTIME_FAULT_NONE: return "NONE";
    case NUCLEO_PROFILE_RUNTIME_FAULT_PULSE_UNDERRUN:
      return "PULSE_UNDERRUN";
    default: return "UNKNOWN";
  }
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
