#ifndef NUCLEO_PULSE_SCHEDULER_H
#define NUCLEO_PULSE_SCHEDULER_H

#include "nucleo_profile_executor.h"

#include <stdint.h>

typedef void (*NucleoPulseSetRateFn)(void *context, uint8_t axis,
                                     uint32_t rate_millihz);
typedef void (*NucleoPulseDisableAxisFn)(void *context, uint8_t axis);

typedef struct {
  NucleoPulseSetRateFn set_rate;
  NucleoPulseDisableAxisFn disable_axis;
  void *context;
} NucleoPulseSchedulerHooks;

typedef struct {
  NucleoProfileExecutor *executor;
  NucleoPulseSchedulerHooks hooks;
  uint32_t emitted_steps[2];
  uint32_t target_steps[2];
  uint8_t frame_for_axis[2];
  uint8_t active[2];
} NucleoPulseScheduler;

void NucleoPulseScheduler_Init(NucleoPulseScheduler *scheduler,
                               NucleoProfileExecutor *executor,
                               NucleoPulseSchedulerHooks hooks);
NucleoProfileResult NucleoPulseScheduler_Start(NucleoPulseScheduler *scheduler);
void NucleoPulseScheduler_ControlTick(NucleoPulseScheduler *scheduler,
                                      uint64_t now_us);
uint8_t NucleoPulseScheduler_OnPulse(NucleoPulseScheduler *scheduler,
                                    uint8_t axis);
void NucleoPulseScheduler_SafetyStop(NucleoPulseScheduler *scheduler);

#endif
