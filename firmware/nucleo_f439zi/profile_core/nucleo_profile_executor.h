#ifndef NUCLEO_PROFILE_EXECUTOR_H
#define NUCLEO_PROFILE_EXECUTOR_H

#include "nucleo_profile_buffer.h"

#include <stdint.h>

#define NUCLEO_PROFILE_WATCHDOG_US 500000ULL
#define NUCLEO_PROFILE_NO_PHASE 0xffU

typedef void (*NucleoProfileDisableAllFn)(void *context);
typedef void (*NucleoProfilePhaseFn)(void *context, uint8_t axis,
                                     uint8_t phase_index);

typedef struct {
  NucleoProfileDisableAllFn disable_all;
  NucleoProfilePhaseFn phase_changed;
  void *context;
} NucleoProfileExecutorHooks;

typedef struct {
  NucleoProfileBuffer *buffer;
  NucleoProfileExecutorHooks hooks;
  uint64_t started_at_us;
  uint64_t last_heartbeat_us;
  uint64_t total_duration_us[NUCLEO_PROFILE_BUFFER_CAPACITY];
  uint8_t phase_index[NUCLEO_PROFILE_BUFFER_CAPACITY];
  uint8_t running;
} NucleoProfileExecutor;

void NucleoProfileExecutor_Init(NucleoProfileExecutor *executor,
                                NucleoProfileExecutorHooks hooks);
NucleoProfileResult NucleoProfileExecutor_Start(
    NucleoProfileExecutor *executor, NucleoProfileBuffer *buffer,
    uint64_t now_us, uint8_t safety_permissive);
void NucleoProfileExecutor_Heartbeat(NucleoProfileExecutor *executor,
                                    uint64_t now_us,
                                    uint8_t safety_permissive);
NucleoProfileState NucleoProfileExecutor_Tick(
    NucleoProfileExecutor *executor, uint64_t now_us,
    uint8_t safety_permissive);
void NucleoProfileExecutor_SafetyStop(NucleoProfileExecutor *executor);

#endif
