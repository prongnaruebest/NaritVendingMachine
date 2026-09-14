#include "nucleo_profile_telemetry.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
  NucleoProfileBuffer buffer;
  NucleoProfileExecutor executor;
  NucleoPulseScheduler scheduler;
  NucleoProfileRuntime runtime;
  NucleoProfileExecutorHooks executor_hooks = {NULL, NULL, NULL};
  NucleoPulseSchedulerHooks scheduler_hooks = {NULL, NULL, NULL};
  char response[384];

  NucleoProfileBuffer_Init(&buffer);
  strcpy(buffer.command_id, "telemetry-1");
  buffer.state = NUCLEO_PROFILE_FAILED;
  NucleoProfileExecutor_Init(&executor, executor_hooks);
  executor.buffer = &buffer;
  executor.trajectory_elapsed = 1U;
  NucleoPulseScheduler_Init(&scheduler, &executor, scheduler_hooks);
  scheduler.target_steps[0] = 100U;
  scheduler.emitted_steps[0] = 99U;
  assert(NucleoProfileRuntime_Init(&runtime, &executor, &scheduler) == 1U);
  runtime.terminal_fault = NUCLEO_PROFILE_RUNTIME_FAULT_PULSE_UNDERRUN;

#if NUCLEO_XY_PROFILE_TELEMETRY_ENABLED
  char tiny[8] = "dirty";
  assert(NucleoProfileTelemetry_HandleLine(&runtime, "PROFILE_STATUS",
                                           response, sizeof(response)) == 1U);
  assert(strstr(response, "\"state\":\"FAILED\"") != NULL);
  assert(strstr(response, "\"fault\":\"PULSE_UNDERRUN\"") != NULL);
  assert(strstr(response, "\"target_steps\":100") != NULL);
  assert(strstr(response, "\"emitted_steps\":99") != NULL);
  assert(NucleoProfileTelemetry_HandleLine(&runtime, "PROFILE_STATUS extra",
                                           response, sizeof(response)) == 0U);
  assert(NucleoProfileTelemetry_HandleLine(&runtime, "PROFILE_STATUS",
                                           tiny, sizeof(tiny)) == 0U);
  assert(tiny[0] == '\0');
#else
  assert(NucleoProfileTelemetry_HandleLine(&runtime, "PROFILE_STATUS",
                                           response, sizeof(response)) == 0U);
  assert(response[0] == '\0');
#endif
  puts("profile telemetry host tests passed");
  return 0;
}
