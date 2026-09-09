#include "nucleo_profile_executor.h"

#include <stddef.h>
#include <string.h>

static void disable_outputs(NucleoProfileExecutor *executor)
{
  if (executor->hooks.disable_all != NULL) {
    executor->hooks.disable_all(executor->hooks.context);
  }
}

static uint64_t frame_duration(const NucleoProfileFrame *frame)
{
  uint8_t index;
  uint64_t total = 0ULL;
  for (index = 0U; index < NUCLEO_PROFILE_PHASE_COUNT; index++) {
    total += (uint64_t)frame->phases[index].duration_us;
  }
  return total;
}

static uint8_t phase_at_elapsed(const NucleoProfileFrame *frame,
                                uint64_t elapsed_us)
{
  uint8_t index;
  uint64_t boundary = 0ULL;
  for (index = 0U; index < NUCLEO_PROFILE_PHASE_COUNT; index++) {
    boundary += (uint64_t)frame->phases[index].duration_us;
    if (elapsed_us < boundary) return index;
  }
  return NUCLEO_PROFILE_NO_PHASE;
}

void NucleoProfileExecutor_Init(NucleoProfileExecutor *executor,
                                NucleoProfileExecutorHooks hooks)
{
  if (executor == NULL) return;
  memset(executor, 0, sizeof(*executor));
  executor->hooks = hooks;
  executor->phase_index[0] = NUCLEO_PROFILE_NO_PHASE;
  executor->phase_index[1] = NUCLEO_PROFILE_NO_PHASE;
}

NucleoProfileResult NucleoProfileExecutor_Start(
    NucleoProfileExecutor *executor, NucleoProfileBuffer *buffer,
    uint64_t now_us, uint8_t safety_permissive)
{
  uint32_t index;
  if ((executor == NULL) || (buffer == NULL)) return NUCLEO_PROFILE_ERR_FORMAT;
  if ((safety_permissive == 0U) || (buffer->state != NUCLEO_PROFILE_BUFFERED) ||
      (buffer->count == 0U)) {
    disable_outputs(executor);
    return NUCLEO_PROFILE_ERR_STATE;
  }
  for (index = 0U; index < buffer->count; index++) {
    uint64_t duration = frame_duration(&buffer->frames[index]);
    if (duration == 0ULL) return NUCLEO_PROFILE_ERR_RANGE;
    executor->total_duration_us[index] = duration;
    executor->phase_index[index] = NUCLEO_PROFILE_NO_PHASE;
  }
  executor->buffer = buffer;
  executor->started_at_us = now_us;
  executor->last_heartbeat_us = now_us;
  executor->running = 1U;
  buffer->state = NUCLEO_PROFILE_RUNNING;
  return NUCLEO_PROFILE_OK;
}

void NucleoProfileExecutor_Heartbeat(NucleoProfileExecutor *executor,
                                    uint64_t now_us,
                                    uint8_t safety_permissive)
{
  if ((executor == NULL) || (executor->running == 0U)) return;
  if (safety_permissive == 0U) {
    NucleoProfileExecutor_SafetyStop(executor);
    return;
  }
  executor->last_heartbeat_us = now_us;
}

NucleoProfileState NucleoProfileExecutor_Tick(
    NucleoProfileExecutor *executor, uint64_t now_us,
    uint8_t safety_permissive)
{
  uint32_t index;
  uint8_t all_complete = 1U;
  uint64_t elapsed_us;
  if ((executor == NULL) || (executor->buffer == NULL)) return NUCLEO_PROFILE_EMPTY;
  if (executor->running == 0U) return executor->buffer->state;
  if ((safety_permissive == 0U) || (now_us < executor->last_heartbeat_us) ||
      ((now_us - executor->last_heartbeat_us) > NUCLEO_PROFILE_WATCHDOG_US)) {
    NucleoProfileExecutor_SafetyStop(executor);
    return NUCLEO_PROFILE_SAFETY_STOP;
  }
  if (now_us < executor->started_at_us) {
    NucleoProfileExecutor_SafetyStop(executor);
    return NUCLEO_PROFILE_SAFETY_STOP;
  }
  elapsed_us = now_us - executor->started_at_us;
  for (index = 0U; index < executor->buffer->count; index++) {
    uint8_t phase = phase_at_elapsed(&executor->buffer->frames[index], elapsed_us);
    if (phase != NUCLEO_PROFILE_NO_PHASE) all_complete = 0U;
    if (phase != executor->phase_index[index]) {
      executor->phase_index[index] = phase;
      if (executor->hooks.phase_changed != NULL) {
        executor->hooks.phase_changed(executor->hooks.context,
                                      executor->buffer->frames[index].axis,
                                      phase);
      }
    }
  }
  if (all_complete != 0U) {
    disable_outputs(executor);
    executor->running = 0U;
    executor->buffer->state = NUCLEO_PROFILE_COMPLETE;
  }
  return executor->buffer->state;
}

void NucleoProfileExecutor_SafetyStop(NucleoProfileExecutor *executor)
{
  if (executor == NULL) return;
  disable_outputs(executor);
  executor->running = 0U;
  if (executor->buffer != NULL) {
    NucleoProfileBuffer_SafetyStop(executor->buffer);
  }
}
