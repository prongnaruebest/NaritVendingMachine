#include "nucleo_dynamic_telemetry.h"

#include <stdio.h>

static const char *state_name(NucleoDynamicState state)
{
  switch (state) {
    case NUCLEO_DYNAMIC_IDLE: return "IDLE";
    case NUCLEO_DYNAMIC_RUNNING: return "RUNNING";
    case NUCLEO_DYNAMIC_STOPPING: return "STOPPING";
    case NUCLEO_DYNAMIC_STOPPED: return "STOPPED";
    case NUCLEO_DYNAMIC_COMPLETE: return "COMPLETE";
    case NUCLEO_DYNAMIC_FAILED: return "FAILED";
    default: return "UNKNOWN";
  }
}

static const char *fault_name(NucleoDynamicFault fault)
{
  switch (fault) {
    case NUCLEO_DYNAMIC_FAULT_NONE: return "NONE";
    case NUCLEO_DYNAMIC_FAULT_STOP: return "STOP";
    case NUCLEO_DYNAMIC_FAULT_DISARM: return "DISARM";
    case NUCLEO_DYNAMIC_FAULT_WATCHDOG: return "WATCHDOG";
    case NUCLEO_DYNAMIC_FAULT_SAFETY: return "SAFETY";
    case NUCLEO_DYNAMIC_FAULT_CONTROL_TICK: return "CONTROL_TICK";
    case NUCLEO_DYNAMIC_FAULT_TERMINAL_RATE: return "TERMINAL_RATE";
    default: return "UNKNOWN";
  }
}

static uint32_t remaining_pulses(const NucleoDynamicRuntime *runtime)
{
  /* Saturate diagnostic arithmetic so a corrupted/late counter cannot wrap
     into a misleading multi-billion-pulse remaining distance. */
  return runtime->planner.target_pulses >= runtime->planner.emitted_pulses
             ? runtime->planner.target_pulses - runtime->planner.emitted_pulses
             : 0U;
}

uint8_t NucleoDynamicTelemetry_Write(const NucleoDynamicFacade *facade,
                                     char *response, size_t response_size)
{
  const NucleoDynamicRuntime *x;
  const NucleoDynamicRuntime *y;
  int written;
  if ((facade == NULL) || (response == NULL) || (response_size == 0U)) {
    return 0U;
  }
  x = &facade->coordinator.axes[0];
  y = &facade->coordinator.axes[1];
  written = snprintf(
      response, response_size,
      "{\"type\":\"dynamic_status\",\"runtime_ready\":%s,"
      "\"active_mask\":%u,\"axes\":{"
      "\"x\":{\"position_valid\":%s,\"position_pulses\":%lu,"
      "\"target_pulses\":%lu,\"emitted_pulses\":%lu,"
      "\"remaining_pulses\":%lu,\"rate_millihz\":%lu,"
      "\"acceleration_millihz_s\":%ld,\"braking\":%s,"
      "\"state\":\"%s\",\"fault\":\"%s\"},"
      "\"y\":{\"position_valid\":%s,\"position_pulses\":%lu,"
      "\"target_pulses\":%lu,\"emitted_pulses\":%lu,"
      "\"remaining_pulses\":%lu,\"rate_millihz\":%lu,"
      "\"acceleration_millihz_s\":%ld,\"braking\":%s,"
      "\"state\":\"%s\",\"fault\":\"%s\"}}}",
      facade->runtime_ready != 0U ? "true" : "false",
      (unsigned int)facade->coordinator.active_mask,
      facade->protocol.position_valid[0] != 0U ? "true" : "false",
      (unsigned long)facade->protocol.estimated_position_pulses[0],
      (unsigned long)facade->staged[0].target_position_pulses,
      (unsigned long)x->planner.emitted_pulses,
      (unsigned long)remaining_pulses(x),
      (unsigned long)x->planner.output_rate_millihz,
      (long)x->planner.constraint.acceleration_millihz_s,
      x->planner.constraint.braking != 0U ? "true" : "false",
      state_name(x->planner.state), fault_name(x->fault),
      facade->protocol.position_valid[1] != 0U ? "true" : "false",
      (unsigned long)facade->protocol.estimated_position_pulses[1],
      (unsigned long)facade->staged[1].target_position_pulses,
      (unsigned long)y->planner.emitted_pulses,
      (unsigned long)remaining_pulses(y),
      (unsigned long)y->planner.output_rate_millihz,
      (long)y->planner.constraint.acceleration_millihz_s,
      y->planner.constraint.braking != 0U ? "true" : "false",
      state_name(y->planner.state), fault_name(y->fault));
  if ((written < 0) || ((size_t)written >= response_size)) {
    response[0] = '\0';
    return 0U;
  }
  return 1U;
}
