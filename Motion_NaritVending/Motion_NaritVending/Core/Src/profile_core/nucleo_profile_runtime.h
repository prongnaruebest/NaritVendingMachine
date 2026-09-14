#ifndef NUCLEO_PROFILE_RUNTIME_H
#define NUCLEO_PROFILE_RUNTIME_H

#include "nucleo_pulse_scheduler.h"

#include <stdint.h>

typedef struct {
  NucleoProfileExecutor *executor;
  NucleoPulseScheduler *scheduler;
  uint8_t safety_permissive;
  uint8_t initialized;
} NucleoProfileRuntime;

uint8_t NucleoProfileRuntime_Init(NucleoProfileRuntime *runtime,
                                  NucleoProfileExecutor *executor,
                                  NucleoPulseScheduler *scheduler);
void NucleoProfileRuntime_SetSafety(NucleoProfileRuntime *runtime,
                                    uint64_t now_us,
                                    uint8_t safety_permissive);
void NucleoProfileRuntime_ControlTick(void *context, uint64_t now_us);
void NucleoProfileRuntime_SafetyStop(void *context);

#endif
