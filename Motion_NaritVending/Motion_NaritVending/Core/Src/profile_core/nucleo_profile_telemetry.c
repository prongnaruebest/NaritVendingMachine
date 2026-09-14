#include "nucleo_profile_telemetry.h"

#include <stdio.h>
#include <string.h>

uint8_t NucleoProfileTelemetry_HandleLine(
    const NucleoProfileRuntime *runtime, const char *line,
    char *response, size_t response_size)
{
  NucleoProfileRuntimeTelemetry telemetry;
  int written;
  if ((response == NULL) || (response_size == 0U)) return 0U;
  response[0] = '\0';
  if ((NUCLEO_XY_PROFILE_TELEMETRY_ENABLED == 0) ||
      (line == NULL) || (strcmp(line, "PROFILE_STATUS") != 0)) return 0U;
  if (NucleoProfileRuntime_GetTelemetry(runtime, &telemetry) == 0U) return 0U;
  written = snprintf(
      response, response_size,
      "{\"type\":\"profile_status\",\"state\":\"%s\"," 
      "\"fault\":\"%s\",\"command_id\":\"%s\"," 
      "\"safety_permissive\":%s,\"trajectory_elapsed\":%s," 
      "\"axes\":{\"x\":{\"target_steps\":%lu,\"emitted_steps\":%lu,"
      "\"active\":%s},\"y\":{\"target_steps\":%lu,"
      "\"emitted_steps\":%lu,\"active\":%s}}}",
      NucleoProfileRuntime_StateName(telemetry.state),
      NucleoProfileRuntime_FaultName(telemetry.terminal_fault),
      telemetry.command_id,
      telemetry.safety_permissive != 0U ? "true" : "false",
      telemetry.trajectory_elapsed != 0U ? "true" : "false",
      (unsigned long)telemetry.target_steps[0],
      (unsigned long)telemetry.emitted_steps[0],
      telemetry.axis_active[0] != 0U ? "true" : "false",
      (unsigned long)telemetry.target_steps[1],
      (unsigned long)telemetry.emitted_steps[1],
      telemetry.axis_active[1] != 0U ? "true" : "false");
  if ((written < 0) || ((size_t)written >= response_size)) {
    response[0] = '\0';
    return 0U;
  }
  return 1U;
}
