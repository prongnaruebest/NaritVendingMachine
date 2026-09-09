#include "nucleo_profile_executor.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
  unsigned int disable_count;
  unsigned int phase_count;
  uint8_t last_axis;
  uint8_t last_phase;
} HookState;

static void disable_all(void *context)
{
  HookState *state = (HookState *)context;
  state->disable_count++;
}

static void phase_changed(void *context, uint8_t axis, uint8_t phase)
{
  HookState *state = (HookState *)context;
  state->phase_count++;
  state->last_axis = axis;
  state->last_phase = phase;
}

static void make_frame(NucleoProfileFrame *frame, uint8_t axis,
                       uint32_t sequence, uint32_t phase_us)
{
  uint8_t index;
  memset(frame, 0, sizeof(*frame));
  strcpy(frame->command_id, "xy-move-1");
  memset(frame->checksum, axis == 0U ? 'a' : 'b', 64U);
  frame->checksum[64] = '\0';
  frame->axis = axis;
  frame->direction = 1U;
  frame->steps = 1000U;
  frame->sequence = sequence;
  for (index = 0U; index < NUCLEO_PROFILE_PHASE_COUNT; index++) {
    frame->phases[index].duration_us = phase_us;
    frame->phases[index].end_step = ((uint32_t)(index + 1U) * 1000U) / 7U;
    frame->phases[index].start_rate_millihz = 1000000U;
    frame->phases[index].end_rate_millihz = 1000000U;
  }
}

static void stage_xy(NucleoProfileBuffer *buffer, uint32_t x_phase_us,
                     uint32_t y_phase_us)
{
  NucleoProfileFrame frame;
  NucleoProfileBuffer_Init(buffer);
  make_frame(&frame, 0U, 0U, x_phase_us);
  assert(NucleoProfileBuffer_Stage(buffer, &frame) == NUCLEO_PROFILE_OK);
  make_frame(&frame, 1U, 1U, y_phase_us);
  assert(NucleoProfileBuffer_Stage(buffer, &frame) == NUCLEO_PROFILE_OK);
}

int main(void)
{
  NucleoProfileBuffer buffer;
  NucleoProfileExecutor executor;
  HookState hooks_state = {0U, 0U, 0U, 0U};
  NucleoProfileExecutorHooks hooks = {disable_all, phase_changed, &hooks_state};

  stage_xy(&buffer, 1000U, 1000U);
  NucleoProfileExecutor_Init(&executor, hooks);
  assert(NucleoProfileExecutor_Start(&executor, &buffer, 100U, 0U) ==
         NUCLEO_PROFILE_ERR_STATE);
  assert(hooks_state.disable_count == 1U);
  assert(NucleoProfileExecutor_Start(&executor, &buffer, 100U, 1U) ==
         NUCLEO_PROFILE_OK);
  assert(NucleoProfileExecutor_Tick(&executor, 100U, 1U) ==
         NUCLEO_PROFILE_RUNNING);
  assert(hooks_state.phase_count == 2U);
  assert(NucleoProfileExecutor_Tick(&executor, 1100U, 1U) ==
         NUCLEO_PROFILE_RUNNING);
  assert(hooks_state.phase_count == 4U);
  NucleoProfileExecutor_Heartbeat(&executor, 5000U, 1U);
  assert(NucleoProfileExecutor_Tick(&executor, 7100U, 1U) ==
         NUCLEO_PROFILE_COMPLETE);
  assert(hooks_state.disable_count == 2U);

  stage_xy(&buffer, 100000U, 100000U);
  NucleoProfileExecutor_Init(&executor, hooks);
  assert(NucleoProfileExecutor_Start(&executor, &buffer, 1000U, 1U) ==
         NUCLEO_PROFILE_OK);
  assert(NucleoProfileExecutor_Tick(&executor, 501001U, 1U) ==
         NUCLEO_PROFILE_SAFETY_STOP);
  assert(hooks_state.disable_count == 3U);

  stage_xy(&buffer, 100000U, 100000U);
  NucleoProfileExecutor_Init(&executor, hooks);
  assert(NucleoProfileExecutor_Start(&executor, &buffer, 2000U, 1U) ==
         NUCLEO_PROFILE_OK);
  NucleoProfileExecutor_Heartbeat(&executor, 3000U, 0U);
  assert(buffer.state == NUCLEO_PROFILE_SAFETY_STOP);
  assert(hooks_state.disable_count == 4U);

  puts("nucleo_profile_executor host tests passed");
  return 0;
}
