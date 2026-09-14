#include "nucleo_control_tick.h"
#include "nucleo_profile_runtime.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
  uint32_t rates[2];
  uint32_t disables[2];
  uint32_t global_stops;
} RuntimeMock;

static void set_rate(void *context, uint8_t axis, uint32_t rate_millihz)
{
  ((RuntimeMock *)context)->rates[axis] = rate_millihz;
}

static void disable_axis(void *context, uint8_t axis)
{
  ((RuntimeMock *)context)->disables[axis]++;
}

static void disable_all(void *context)
{
  ((RuntimeMock *)context)->global_stops++;
}

static void make_frame(NucleoProfileFrame *frame)
{
  uint8_t phase;
  memset(frame, 0, sizeof(*frame));
  strcpy(frame->command_id, "runtime-test");
  frame->axis = 0U;
  frame->sequence = 0U;
  frame->steps = 70U;
  for (phase = 0U; phase < NUCLEO_PROFILE_PHASE_COUNT; phase++) {
    frame->phases[phase].duration_us = 1000U;
    frame->phases[phase].end_step = (uint32_t)(phase + 1U) * 10U;
    frame->phases[phase].start_rate_millihz = 1000000U;
    frame->phases[phase].end_rate_millihz = 1000000U;
  }
}

int main(void)
{
  NucleoProfileBuffer buffer;
  NucleoProfileExecutor executor;
  NucleoPulseScheduler scheduler;
  NucleoProfileRuntime runtime;
  NucleoControlTick control;
  NucleoProfileFrame frame;
  RuntimeMock mock = {{0U, 0U}, {0U, 0U}, 0U};
  NucleoProfileExecutorHooks executor_hooks = {disable_all, NULL, &mock};
  NucleoPulseSchedulerHooks scheduler_hooks = {set_rate, disable_axis, &mock};
  NucleoControlTickHooks tick_hooks = {
      NucleoProfileRuntime_ControlTick,
      NucleoProfileRuntime_SafetyStop,
      &runtime};

  NucleoProfileBuffer_Init(&buffer);
  make_frame(&frame);
  assert(NucleoProfileBuffer_Stage(&buffer, &frame) == NUCLEO_PROFILE_OK);
  NucleoProfileExecutor_Init(&executor, executor_hooks);
  NucleoPulseScheduler_Init(&scheduler, &executor, scheduler_hooks);
  assert(NucleoProfileRuntime_Init(&runtime, &executor, &scheduler) == 1U);
  assert(NucleoControlTick_Init(&control, tick_hooks) == 1U);
  NucleoProfileRuntime_SetSafety(&runtime, 0ULL, 1U);
  assert(NucleoProfileRuntime_Start(&runtime, &buffer, 0ULL) ==
         NUCLEO_PROFILE_OK);
  assert(NucleoControlTick_Arm(&control, 0ULL, 1U) == 1U);
  NucleoControlTick_OnTimer(&control, 1000ULL, 1U);
  assert(mock.rates[0] > 0U);

  NucleoProfileRuntime_SetSafety(&runtime, 2000ULL, 0U);
  assert(buffer.state == NUCLEO_PROFILE_SAFETY_STOP);
  assert(mock.global_stops > 0U && mock.disables[0] > 0U);

  /* Time expiry without 70 emitted edges must fail, never report COMPLETE. */
  NucleoProfileBuffer_Init(&buffer);
  make_frame(&frame);
  assert(NucleoProfileBuffer_Stage(&buffer, &frame) == NUCLEO_PROFILE_OK);
  NucleoProfileExecutor_Init(&executor, executor_hooks);
  NucleoPulseScheduler_Init(&scheduler, &executor, scheduler_hooks);
  assert(NucleoProfileRuntime_Init(&runtime, &executor, &scheduler) == 1U);
  NucleoProfileRuntime_SetSafety(&runtime, 10000ULL, 1U);
  assert(NucleoProfileExecutor_Start(&executor, &buffer, 10000ULL, 1U) ==
         NUCLEO_PROFILE_OK);
  assert(NucleoPulseScheduler_Start(&scheduler) == NUCLEO_PROFILE_OK);
  NucleoProfileRuntime_ControlTick(&runtime, 17000ULL);
  assert(buffer.state == NUCLEO_PROFILE_FAILED);
  assert(runtime.terminal_fault ==
         NUCLEO_PROFILE_RUNTIME_FAULT_PULSE_UNDERRUN);

  {
    NucleoProfileRuntimeTelemetry telemetry;
    assert(NucleoProfileRuntime_GetTelemetry(&runtime, &telemetry) == 1U);
    assert(telemetry.state == NUCLEO_PROFILE_FAILED);
    assert(telemetry.terminal_fault ==
           NUCLEO_PROFILE_RUNTIME_FAULT_PULSE_UNDERRUN);
    assert(telemetry.target_steps[0] == 70U);
    assert(telemetry.emitted_steps[0] == 0U);
    assert(strcmp(telemetry.command_id, "runtime-test") == 0);
    assert(strcmp(NucleoProfileRuntime_StateName(telemetry.state), "FAILED") == 0);
    assert(strcmp(NucleoProfileRuntime_FaultName(telemetry.terminal_fault),
                  "PULSE_UNDERRUN") == 0);
  }

  /* Exact emitted count is the only bounded-move completion authority. */
  NucleoProfileBuffer_Init(&buffer);
  make_frame(&frame);
  assert(NucleoProfileBuffer_Stage(&buffer, &frame) == NUCLEO_PROFILE_OK);
  NucleoProfileExecutor_Init(&executor, executor_hooks);
  NucleoPulseScheduler_Init(&scheduler, &executor, scheduler_hooks);
  assert(NucleoProfileRuntime_Init(&runtime, &executor, &scheduler) == 1U);
  NucleoProfileRuntime_SetSafety(&runtime, 20000ULL, 1U);
  assert(NucleoProfileExecutor_Start(&executor, &buffer, 20000ULL, 1U) ==
         NUCLEO_PROFILE_OK);
  assert(NucleoPulseScheduler_Start(&scheduler) == NUCLEO_PROFILE_OK);
  for (uint32_t pulse = 0U; pulse < 70U; pulse++) {
    assert(NucleoPulseScheduler_OnPulse(&scheduler, 0U) == 1U);
  }
  NucleoProfileRuntime_ControlTick(&runtime, 27000ULL);
  assert(buffer.state == NUCLEO_PROFILE_COMPLETE);
  assert(runtime.terminal_fault == NUCLEO_PROFILE_RUNTIME_FAULT_NONE);

  /* A terminal state requires an explicit safe reset before another frame. */
  assert(NucleoProfileRuntime_Reset(&runtime, &buffer) == NUCLEO_PROFILE_OK);
  assert(buffer.state == NUCLEO_PROFILE_EMPTY);
  assert(executor.buffer == NULL);
  assert(scheduler.target_steps[0] == 0U);
  NucleoProfileRuntime_SetSafety(&runtime, 28000ULL, 0U);
  assert(NucleoProfileRuntime_Reset(&runtime, &buffer) ==
         NUCLEO_PROFILE_ERR_STATE);

  puts("profile runtime host tests passed");
  return 0;
}
