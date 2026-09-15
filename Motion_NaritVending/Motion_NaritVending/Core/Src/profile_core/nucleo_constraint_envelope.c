#include "nucleo_constraint_envelope.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#define NUCLEO_MILLI_UNITS 1000.0
#define MICROS_PER_SECOND 1000000.0

static double jerk_aware_stop_pulses(double velocity_hz,
                                     double acceleration_hz_s,
                                     double deceleration_hz_s,
                                     double jerk_hz_s2)
{
  double ramp_time_s = (acceleration_hz_s + deceleration_hz_s) / jerk_hz_s2;
  double velocity_after_ramp_hz;
  double ramp_distance_pulses;
  if (ramp_time_s < 0.0) ramp_time_s = 0.0;
  velocity_after_ramp_hz = velocity_hz + acceleration_hz_s * ramp_time_s -
                           0.5 * jerk_hz_s2 * ramp_time_s * ramp_time_s;
  ramp_distance_pulses = velocity_hz * ramp_time_s +
      0.5 * acceleration_hz_s * ramp_time_s * ramp_time_s -
      (jerk_hz_s2 * ramp_time_s * ramp_time_s * ramp_time_s) / 6.0;
  if (ramp_distance_pulses < 0.0) ramp_distance_pulses = 0.0;
  if (velocity_after_ramp_hz > 0.0) {
    ramp_distance_pulses += (velocity_after_ramp_hz * velocity_after_ramp_hz) /
                            (2.0 * deceleration_hz_s);
  }
  return ramp_distance_pulses;
}

void NucleoConstraint_Init(NucleoConstraintState *state)
{
  if (state != NULL) memset(state, 0, sizeof(*state));
}

NucleoConstraintResult NucleoConstraint_Tick(
    NucleoConstraintState *state, const NucleoConstraintLimits *limits,
    uint32_t remaining_pulses, uint32_t requested_rate_millihz)
{
  double dt_s;
  double velocity_hz;
  double acceleration_hz_s;
  double stop_pulses;
  double latency_pulses;
  double desired_acceleration_hz_s;
  double jerk_step_hz_s;
  double next_acceleration_hz_s;
  double next_velocity_hz;
  double requested_rate_hz;
  if ((state == NULL) || (limits == NULL)) return NUCLEO_CONSTRAINT_ERR_ARGUMENT;
  if ((limits->control_period_us == 0U) ||
      (limits->control_period_us > 10000U) ||
      (limits->max_velocity_hz == 0U) ||
      (limits->max_velocity_hz > 50000U) ||
      (limits->max_acceleration_hz_s == 0U) ||
      (limits->max_deceleration_hz_s == 0U) ||
      (limits->max_jerk_hz_s2 == 0U) ||
      (requested_rate_millihz > limits->max_velocity_hz * 1000U)) {
    return NUCLEO_CONSTRAINT_ERR_LIMIT;
  }
  if (remaining_pulses == 0U) {
    NucleoConstraint_Init(state);
    return NUCLEO_CONSTRAINT_OK;
  }

  dt_s = (double)limits->control_period_us / MICROS_PER_SECOND;
  velocity_hz = (double)state->velocity_millihz / NUCLEO_MILLI_UNITS;
  acceleration_hz_s =
      (double)state->acceleration_millihz_s / NUCLEO_MILLI_UNITS;
  requested_rate_hz =
      (double)requested_rate_millihz / NUCLEO_MILLI_UNITS;
  stop_pulses = jerk_aware_stop_pulses(
      velocity_hz, acceleration_hz_s,
      (double)limits->max_deceleration_hz_s,
      (double)limits->max_jerk_hz_s2);
  /* Discrete final-edge ownership belongs to the pulse-phase accumulator. */
  latency_pulses = velocity_hz * dt_s;
  state->stopping_distance_millipulses =
      (uint32_t)ceil((stop_pulses + latency_pulses) * NUCLEO_MILLI_UNITS);
  state->braking = ((stop_pulses + latency_pulses) >= remaining_pulses) ? 1U : 0U;

  if ((state->braking != 0U) || (requested_rate_hz < velocity_hz)) {
    desired_acceleration_hz_s = -(double)limits->max_deceleration_hz_s;
  } else if (requested_rate_hz > velocity_hz) {
    desired_acceleration_hz_s = (double)limits->max_acceleration_hz_s;
  } else {
    desired_acceleration_hz_s = 0.0;
  }
  jerk_step_hz_s = (double)limits->max_jerk_hz_s2 * dt_s;
  next_acceleration_hz_s = acceleration_hz_s;
  if (next_acceleration_hz_s < desired_acceleration_hz_s) {
    next_acceleration_hz_s += jerk_step_hz_s;
    if (next_acceleration_hz_s > desired_acceleration_hz_s)
      next_acceleration_hz_s = desired_acceleration_hz_s;
  } else if (next_acceleration_hz_s > desired_acceleration_hz_s) {
    next_acceleration_hz_s -= jerk_step_hz_s;
    if (next_acceleration_hz_s < desired_acceleration_hz_s)
      next_acceleration_hz_s = desired_acceleration_hz_s;
  }
  next_velocity_hz = velocity_hz +
      0.5 * (acceleration_hz_s + next_acceleration_hz_s) * dt_s;
  if (next_velocity_hz < 0.0) next_velocity_hz = 0.0;
  if (next_velocity_hz > limits->max_velocity_hz)
    next_velocity_hz = limits->max_velocity_hz;
  /* Do not clamp to a falling Kp request; deceleration must remain continuous. */
  state->velocity_millihz =
      (uint32_t)(next_velocity_hz * NUCLEO_MILLI_UNITS + 0.5);
  state->acceleration_millihz_s =
      (int32_t)(next_acceleration_hz_s * NUCLEO_MILLI_UNITS);
  return NUCLEO_CONSTRAINT_OK;
}
