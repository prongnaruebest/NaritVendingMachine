#include "nucleo_dynamic_runtime.h"

#include <stddef.h>
#include <string.h>

static void latch_fault(NucleoDynamicRuntime *runtime,
                        NucleoDynamicFault fault)
{
  if ((runtime == NULL) || (runtime->initialized == 0U)) return;
  runtime->armed = 0U;
  runtime->fault = fault;
  runtime->planner.output_rate_millihz = 0U;
  if (runtime->planner.state == NUCLEO_DYNAMIC_RUNNING) {
    runtime->planner.state = NUCLEO_DYNAMIC_FAILED;
  }
  if (runtime->hooks.disable_all != NULL) {
    runtime->hooks.disable_all(runtime->hooks.context);
  }
}

uint8_t NucleoDynamicRuntime_Init(NucleoDynamicRuntime *runtime,
                                  const NucleoDynamicConfig *config,
                                  NucleoDynamicRuntimeHooks hooks)
{
  if ((runtime == NULL) || (config == NULL) ||
      (hooks.set_rate == NULL) || (hooks.disable_all == NULL)) return 0U;
  memset(runtime, 0, sizeof(*runtime));
  runtime->config = *config;
  runtime->hooks = hooks;
  NucleoDynamicPlanner_Init(&runtime->planner);
  runtime->initialized = 1U;
  return 1U;
}

uint8_t NucleoDynamicRuntime_Arm(NucleoDynamicRuntime *runtime,
                                 uint64_t now_us,
                                 uint8_t safety_permissive)
{
  if ((runtime == NULL) || (runtime->initialized == 0U) ||
      (safety_permissive == 0U) || (runtime->fault != NUCLEO_DYNAMIC_FAULT_NONE) ||
      (runtime->planner.state == NUCLEO_DYNAMIC_RUNNING)) return 0U;
  runtime->last_heartbeat_us = now_us;
  runtime->safety_permissive = 1U;
  runtime->armed = 1U;
  return 1U;
}

NucleoConstraintResult NucleoDynamicRuntime_Start(
    NucleoDynamicRuntime *runtime, uint8_t axis, uint8_t direction,
    uint32_t target_pulses)
{
  if ((runtime == NULL) || (runtime->initialized == 0U) ||
      (runtime->armed == 0U) || (runtime->safety_permissive == 0U)) {
    return NUCLEO_CONSTRAINT_ERR_ARGUMENT;
  }
  return NucleoDynamicPlanner_Start(&runtime->planner, axis, direction,
                                    target_pulses, &runtime->config);
}

void NucleoDynamicRuntime_Heartbeat(NucleoDynamicRuntime *runtime,
                                    uint64_t now_us,
                                    uint8_t safety_permissive)
{
  if ((runtime == NULL) || (runtime->armed == 0U)) return;
  if ((safety_permissive == 0U) || (now_us < runtime->last_heartbeat_us)) {
    latch_fault(runtime, NUCLEO_DYNAMIC_FAULT_SAFETY);
    return;
  }
  runtime->last_heartbeat_us = now_us;
  runtime->safety_permissive = 1U;
}

void NucleoDynamicRuntime_ControlTick(void *context, uint64_t now_us)
{
  NucleoDynamicRuntime *runtime = (NucleoDynamicRuntime *)context;
  if ((runtime == NULL) || (runtime->armed == 0U) ||
      (runtime->planner.state != NUCLEO_DYNAMIC_RUNNING)) return;
  if ((runtime->safety_permissive == 0U) ||
      (now_us < runtime->last_heartbeat_us)) {
    latch_fault(runtime, NUCLEO_DYNAMIC_FAULT_SAFETY);
    return;
  }
  if ((now_us - runtime->last_heartbeat_us) > NUCLEO_DYNAMIC_WATCHDOG_US) {
    latch_fault(runtime, NUCLEO_DYNAMIC_FAULT_WATCHDOG);
    return;
  }
  if (NucleoDynamicPlanner_Tick(&runtime->planner, &runtime->config) !=
      NUCLEO_CONSTRAINT_OK) {
    latch_fault(runtime, NUCLEO_DYNAMIC_FAULT_CONTROL_TICK);
    return;
  }
  if (runtime->planner.state == NUCLEO_DYNAMIC_COMPLETE) {
    runtime->armed = 0U;
    runtime->hooks.disable_all(runtime->hooks.context);
  } else {
    runtime->hooks.set_rate(runtime->hooks.context, runtime->planner.axis,
                            runtime->planner.output_rate_millihz);
  }
}

void NucleoDynamicRuntime_Stop(NucleoDynamicRuntime *runtime)
{
  latch_fault(runtime, NUCLEO_DYNAMIC_FAULT_STOP);
}

void NucleoDynamicRuntime_Disarm(NucleoDynamicRuntime *runtime)
{
  latch_fault(runtime, NUCLEO_DYNAMIC_FAULT_DISARM);
}

void NucleoDynamicRuntime_SafetyLoss(NucleoDynamicRuntime *runtime)
{
  if (runtime != NULL) runtime->safety_permissive = 0U;
  latch_fault(runtime, NUCLEO_DYNAMIC_FAULT_SAFETY);
}

void NucleoDynamicRuntime_ControlFault(void *context)
{
  latch_fault((NucleoDynamicRuntime *)context,
              NUCLEO_DYNAMIC_FAULT_CONTROL_TICK);
}

uint8_t NucleoDynamicRuntime_Reset(NucleoDynamicRuntime *runtime,
                                   uint8_t safety_permissive)
{
  if ((runtime == NULL) || (runtime->initialized == 0U) ||
      (safety_permissive == 0U) ||
      (runtime->planner.state == NUCLEO_DYNAMIC_RUNNING)) return 0U;
  NucleoDynamicPlanner_Init(&runtime->planner);
  runtime->fault = NUCLEO_DYNAMIC_FAULT_NONE;
  runtime->safety_permissive = 1U;
  runtime->armed = 0U;
  return 1U;
}
