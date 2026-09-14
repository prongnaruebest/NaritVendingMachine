#ifndef NUCLEO_PROFILE_RUNTIME_H
#define NUCLEO_PROFILE_RUNTIME_H

#include "nucleo_pulse_scheduler.h"

#include <stdint.h>

typedef enum {
  NUCLEO_PROFILE_RUNTIME_FAULT_NONE = 0,
  NUCLEO_PROFILE_RUNTIME_FAULT_PULSE_UNDERRUN
} NucleoProfileRuntimeFault;

typedef struct {
  NucleoProfileState state;
  NucleoProfileRuntimeFault terminal_fault;
  const char *command_id;
  uint32_t target_steps[2];
  uint32_t emitted_steps[2];
  uint8_t axis_active[2];
  uint8_t trajectory_elapsed;
  uint8_t safety_permissive;
} NucleoProfileRuntimeTelemetry;

typedef struct {
  NucleoProfileExecutor *executor;
  NucleoPulseScheduler *scheduler;
  NucleoProfileRuntimeFault terminal_fault;
  uint8_t safety_permissive;
  uint8_t initialized;
} NucleoProfileRuntime;

uint8_t NucleoProfileRuntime_Init(NucleoProfileRuntime *runtime,
                                  NucleoProfileExecutor *executor,
                                  NucleoPulseScheduler *scheduler);
NucleoProfileResult NucleoProfileRuntime_Start(
    NucleoProfileRuntime *runtime, NucleoProfileBuffer *buffer,
    uint64_t now_us);
NucleoProfileResult NucleoProfileRuntime_Reset(
    NucleoProfileRuntime *runtime, NucleoProfileBuffer *buffer);
uint8_t NucleoProfileRuntime_GetTelemetry(
    const NucleoProfileRuntime *runtime,
    NucleoProfileRuntimeTelemetry *telemetry);
const char *NucleoProfileRuntime_StateName(NucleoProfileState state);
const char *NucleoProfileRuntime_FaultName(NucleoProfileRuntimeFault fault);
void NucleoProfileRuntime_SetSafety(NucleoProfileRuntime *runtime,
                                    uint64_t now_us,
                                    uint8_t safety_permissive);
void NucleoProfileRuntime_ControlTick(void *context, uint64_t now_us);
void NucleoProfileRuntime_SafetyStop(void *context);

#endif
