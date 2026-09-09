#include "nucleo_pulse_scheduler.h"

#include <stddef.h>
#include <string.h>

#define MICROS_PER_SECOND 1000000LL
#define MILLIS_PER_SECOND 1000LL
#define MAX_RATE_MILLIHZ 50000000LL

static uint64_t phase_start_us(const NucleoProfileFrame *frame,
                               uint8_t phase_index)
{
  uint8_t index;
  uint64_t total = 0ULL;
  for (index = 0U; index < phase_index; index++) {
    total += frame->phases[index].duration_us;
  }
  return total;
}

static uint32_t phase_rate(const NucleoProfilePhase *phase,
                           uint64_t elapsed_us)
{
  int64_t elapsed_ms = (int64_t)(elapsed_us / 1000ULL);
  int64_t rate = (int64_t)phase->start_rate_millihz;
  rate += ((int64_t)phase->start_accel_millihz_s * elapsed_ms) /
          MILLIS_PER_SECOND;
  rate += ((int64_t)phase->jerk_millihz_s2 * elapsed_ms * elapsed_ms) /
          (2LL * MILLIS_PER_SECOND * MILLIS_PER_SECOND);
  if (rate < 0LL) return 0U;
  if (rate > MAX_RATE_MILLIHZ) return (uint32_t)MAX_RATE_MILLIHZ;
  return (uint32_t)rate;
}

void NucleoPulseScheduler_Init(NucleoPulseScheduler *scheduler,
                               NucleoProfileExecutor *executor,
                               NucleoPulseSchedulerHooks hooks)
{
  if (scheduler == NULL) return;
  memset(scheduler, 0, sizeof(*scheduler));
  scheduler->executor = executor;
  scheduler->hooks = hooks;
  scheduler->frame_for_axis[0] = NUCLEO_PROFILE_NO_PHASE;
  scheduler->frame_for_axis[1] = NUCLEO_PROFILE_NO_PHASE;
}

NucleoProfileResult NucleoPulseScheduler_Start(NucleoPulseScheduler *scheduler)
{
  uint32_t index;
  NucleoProfileBuffer *buffer;
  if ((scheduler == NULL) || (scheduler->executor == NULL) ||
      (scheduler->executor->buffer == NULL)) return NUCLEO_PROFILE_ERR_STATE;
  buffer = scheduler->executor->buffer;
  if ((buffer->state != NUCLEO_PROFILE_RUNNING) ||
      (scheduler->executor->running == 0U)) return NUCLEO_PROFILE_ERR_STATE;
  for (index = 0U; index < buffer->count; index++) {
    uint8_t axis = buffer->frames[index].axis;
    if (axis > 1U) return NUCLEO_PROFILE_ERR_AXIS;
    if (scheduler->active[axis] != 0U) return NUCLEO_PROFILE_ERR_AXIS;
    scheduler->frame_for_axis[axis] = (uint8_t)index;
    scheduler->target_steps[axis] = buffer->frames[index].steps;
    scheduler->emitted_steps[axis] = 0U;
    scheduler->active[axis] = 1U;
  }
  return NUCLEO_PROFILE_OK;
}

void NucleoPulseScheduler_ControlTick(NucleoPulseScheduler *scheduler,
                                      uint64_t now_us)
{
  uint8_t axis;
  uint64_t elapsed;
  if ((scheduler == NULL) || (scheduler->executor == NULL) ||
      (scheduler->executor->running == 0U) ||
      (now_us < scheduler->executor->started_at_us)) return;
  elapsed = now_us - scheduler->executor->started_at_us;
  for (axis = 0U; axis < 2U; axis++) {
    uint8_t frame_index = scheduler->frame_for_axis[axis];
    uint8_t phase_index;
    const NucleoProfileFrame *frame;
    const NucleoProfilePhase *phase;
    uint64_t local_elapsed;
    if ((scheduler->active[axis] == 0U) ||
        (frame_index == NUCLEO_PROFILE_NO_PHASE)) continue;
    phase_index = scheduler->executor->phase_index[frame_index];
    if (phase_index == NUCLEO_PROFILE_NO_PHASE) continue;
    frame = &scheduler->executor->buffer->frames[frame_index];
    phase = &frame->phases[phase_index];
    local_elapsed = elapsed - phase_start_us(frame, phase_index);
    if (local_elapsed > phase->duration_us) local_elapsed = phase->duration_us;
    if (scheduler->hooks.set_rate != NULL) {
      scheduler->hooks.set_rate(scheduler->hooks.context, axis,
                                phase_rate(phase, local_elapsed));
    }
  }
}

uint8_t NucleoPulseScheduler_OnPulse(NucleoPulseScheduler *scheduler,
                                    uint8_t axis)
{
  if ((scheduler == NULL) || (axis > 1U) || (scheduler->active[axis] == 0U)) {
    return 0U;
  }
  if (scheduler->emitted_steps[axis] >= scheduler->target_steps[axis]) {
    return 0U;
  }
  scheduler->emitted_steps[axis]++;
  if (scheduler->emitted_steps[axis] == scheduler->target_steps[axis]) {
    scheduler->active[axis] = 0U;
    if (scheduler->hooks.disable_axis != NULL) {
      scheduler->hooks.disable_axis(scheduler->hooks.context, axis);
    }
  }
  return 1U;
}

void NucleoPulseScheduler_SafetyStop(NucleoPulseScheduler *scheduler)
{
  uint8_t axis;
  if (scheduler == NULL) return;
  for (axis = 0U; axis < 2U; axis++) {
    if ((scheduler->active[axis] != 0U) &&
        (scheduler->hooks.disable_axis != NULL)) {
      scheduler->hooks.disable_axis(scheduler->hooks.context, axis);
    }
    scheduler->active[axis] = 0U;
  }
  if (scheduler->executor != NULL) {
    NucleoProfileExecutor_SafetyStop(scheduler->executor);
  }
}
