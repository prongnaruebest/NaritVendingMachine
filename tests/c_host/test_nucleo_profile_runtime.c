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
  assert(NucleoProfileExecutor_Start(&executor, &buffer, 0ULL, 1U) ==
         NUCLEO_PROFILE_OK);
  assert(NucleoPulseScheduler_Start(&scheduler) == NUCLEO_PROFILE_OK);
  assert(NucleoControlTick_Arm(&control, 0ULL, 1U) == 1U);
  NucleoControlTick_OnTimer(&control, 1000ULL, 1U);
  assert(mock.rates[0] > 0U);

  NucleoProfileRuntime_SetSafety(&runtime, 2000ULL, 0U);
  assert(buffer.state == NUCLEO_PROFILE_SAFETY_STOP);
  assert(mock.global_stops > 0U && mock.disables[0] > 0U);

  puts("profile runtime host tests passed");
  return 0;
}
