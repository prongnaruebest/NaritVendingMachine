#ifndef NUCLEO_DYNAMIC_RUNTIME_H
#define NUCLEO_DYNAMIC_RUNTIME_H

#include "nucleo_dynamic_planner.h"

#include <stdint.h>

#define NUCLEO_DYNAMIC_WATCHDOG_US 500000ULL

typedef enum {
  NUCLEO_DYNAMIC_FAULT_NONE = 0,
  NUCLEO_DYNAMIC_FAULT_STOP,
  NUCLEO_DYNAMIC_FAULT_DISARM,
  NUCLEO_DYNAMIC_FAULT_WATCHDOG,
  NUCLEO_DYNAMIC_FAULT_SAFETY,
  NUCLEO_DYNAMIC_FAULT_CONTROL_TICK
} NucleoDynamicFault;

typedef void (*NucleoDynamicSetRateFn)(void *context, uint8_t axis,
                                       uint32_t rate_millihz);
typedef void (*NucleoDynamicDisableAllFn)(void *context);

typedef struct {
  NucleoDynamicSetRateFn set_rate;
  NucleoDynamicDisableAllFn disable_all;
  void *context;
} NucleoDynamicRuntimeHooks;

typedef struct {
  NucleoDynamicPlanner planner;
  NucleoDynamicConfig config;
  NucleoDynamicRuntimeHooks hooks;
  uint64_t last_heartbeat_us;
  NucleoDynamicFault fault;
  uint8_t initialized;
  uint8_t armed;
  uint8_t safety_permissive;
} NucleoDynamicRuntime;

uint8_t NucleoDynamicRuntime_Init(NucleoDynamicRuntime *runtime,
                                  const NucleoDynamicConfig *config,
                                  NucleoDynamicRuntimeHooks hooks);
uint8_t NucleoDynamicRuntime_Arm(NucleoDynamicRuntime *runtime,
                                 uint64_t now_us,
                                 uint8_t safety_permissive);
NucleoConstraintResult NucleoDynamicRuntime_Start(
    NucleoDynamicRuntime *runtime, uint8_t axis, uint8_t direction,
    uint32_t target_pulses);
void NucleoDynamicRuntime_Heartbeat(NucleoDynamicRuntime *runtime,
                                    uint64_t now_us,
                                    uint8_t safety_permissive);
void NucleoDynamicRuntime_ControlTick(void *context, uint64_t now_us);
void NucleoDynamicRuntime_Stop(NucleoDynamicRuntime *runtime);
void NucleoDynamicRuntime_Disarm(NucleoDynamicRuntime *runtime);
void NucleoDynamicRuntime_SafetyLoss(NucleoDynamicRuntime *runtime);
void NucleoDynamicRuntime_ControlFault(void *context);
uint8_t NucleoDynamicRuntime_Reset(NucleoDynamicRuntime *runtime,
                                   uint8_t safety_permissive);

#endif
