#include "nucleo_pulse_scheduler.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
  unsigned int rate_updates[2];
  unsigned int disables[2];
  uint32_t last_rate[2];
} TimerMock;

static void set_rate(void *context, uint8_t axis, uint32_t rate)
{
  TimerMock *mock = (TimerMock *)context;
  mock->rate_updates[axis]++;
  mock->last_rate[axis] = rate;
}

static void disable_axis(void *context, uint8_t axis)
{
  TimerMock *mock = (TimerMock *)context;
  mock->disables[axis]++;
}

static void no_op_disable_all(void *context) { (void)context; }

static void prepare(NucleoProfileBuffer *buffer, uint8_t axis, uint32_t sequence,
                    uint32_t steps)
{
  NucleoProfileFrame frame;
  uint8_t index;
  memset(&frame, 0, sizeof(frame));
  strcpy(frame.command_id, "scheduler-1");
  memset(frame.checksum, axis == 0U ? 'a' : 'b', 64U);
  frame.checksum[64] = '\0';
  frame.axis = axis;
  frame.direction = 1U;
  frame.steps = steps;
  frame.sequence = sequence;
  for (index = 0U; index < 7U; index++) {
    frame.phases[index].duration_us = 1000U;
    frame.phases[index].end_step = ((uint32_t)(index + 1U) * steps) / 7U;
    frame.phases[index].start_rate_millihz = 1000000U + index * 100000U;
    frame.phases[index].end_rate_millihz = 1100000U + index * 100000U;
    frame.phases[index].start_accel_millihz_s = 100000;
    frame.phases[index].jerk_millihz_s2 = 100000;
  }
  assert(NucleoProfileBuffer_Stage(buffer, &frame) == NUCLEO_PROFILE_OK);
}

int main(void)
{
  NucleoProfileBuffer buffer;
  NucleoProfileExecutor executor;
  NucleoPulseScheduler scheduler;
  TimerMock timer = {{0U, 0U}, {0U, 0U}, {0U, 0U}};
  NucleoProfileExecutorHooks executor_hooks = {no_op_disable_all, NULL, &timer};
  NucleoPulseSchedulerHooks scheduler_hooks = {set_rate, disable_axis, &timer};
  uint32_t index;

  NucleoProfileBuffer_Init(&buffer);
  prepare(&buffer, 0U, 0U, 5U);
  prepare(&buffer, 1U, 1U, 3U);
  NucleoProfileExecutor_Init(&executor, executor_hooks);
  assert(NucleoProfileExecutor_Start(&executor, &buffer, 100U, 1U) == NUCLEO_PROFILE_OK);
  NucleoPulseScheduler_Init(&scheduler, &executor, scheduler_hooks);
  assert(NucleoPulseScheduler_Start(&scheduler) == NUCLEO_PROFILE_OK);

  assert(NucleoProfileExecutor_Tick(&executor, 100U, 1U) == NUCLEO_PROFILE_RUNNING);
  NucleoPulseScheduler_ControlTick(&scheduler, 100U);
  assert(timer.rate_updates[0] == 1U && timer.rate_updates[1] == 1U);
  assert(timer.disables[0] == 0U && timer.disables[1] == 0U);

  assert(NucleoProfileExecutor_Tick(&executor, 1100U, 1U) == NUCLEO_PROFILE_RUNNING);
  NucleoPulseScheduler_ControlTick(&scheduler, 1100U);
  assert(timer.rate_updates[0] == 2U && timer.rate_updates[1] == 2U);
  assert(timer.disables[0] == 0U && timer.disables[1] == 0U);

  for (index = 0U; index < 5U; index++) assert(NucleoPulseScheduler_OnPulse(&scheduler, 0U) == 1U);
  assert(NucleoPulseScheduler_OnPulse(&scheduler, 0U) == 0U);
  for (index = 0U; index < 3U; index++) assert(NucleoPulseScheduler_OnPulse(&scheduler, 1U) == 1U);
  assert(NucleoPulseScheduler_OnPulse(&scheduler, 1U) == 0U);
  assert(scheduler.emitted_steps[0] == 5U && scheduler.emitted_steps[1] == 3U);
  assert(timer.disables[0] == 1U && timer.disables[1] == 1U);

  NucleoProfileBuffer_Init(&buffer);
  prepare(&buffer, 0U, 0U, 10U);
  NucleoProfileExecutor_Init(&executor, executor_hooks);
  assert(NucleoProfileExecutor_Start(&executor, &buffer, 200U, 1U) == NUCLEO_PROFILE_OK);
  NucleoPulseScheduler_Init(&scheduler, &executor, scheduler_hooks);
  assert(NucleoPulseScheduler_Start(&scheduler) == NUCLEO_PROFILE_OK);
  assert(NucleoPulseScheduler_OnPulse(&scheduler, 0U) == 1U);
  NucleoPulseScheduler_SafetyStop(&scheduler);
  assert(timer.disables[0] == 2U);
  assert(NucleoPulseScheduler_OnPulse(&scheduler, 0U) == 0U);
  assert(buffer.state == NUCLEO_PROFILE_SAFETY_STOP);

  puts("nucleo_pulse_scheduler host tests passed");
  return 0;
}
