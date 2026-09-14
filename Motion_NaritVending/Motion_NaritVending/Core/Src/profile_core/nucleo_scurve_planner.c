#include "nucleo_scurve_planner.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#define NUCLEO_SCURVE_MICROS_PER_SECOND 1000000.0
#define NUCLEO_SCURVE_MAX_PULSE_HZ 50000U

static uint32_t rounded_u32(double value)
{
  if (value <= 0.0) return 0U;
  if (value >= 4294967295.0) return UINT32_MAX;
  return (uint32_t)(value + 0.5);
}

static int32_t rounded_i32(double value)
{
  if (value >= 2147483647.0) return INT32_MAX;
  if (value <= -2147483648.0) return INT32_MIN;
  return (int32_t)((value >= 0.0) ? (value + 0.5) : (value - 0.5));
}

static uint32_t duration_us(double duration_s)
{
  double value_us = ceil(duration_s * NUCLEO_SCURVE_MICROS_PER_SECOND);
  if (value_us < 1.0) return 0U;
  return rounded_u32(value_us);
}

NucleoScurveResult NucleoScurvePlanner_Build(
    const char *command_id, uint8_t axis, uint8_t direction,
    uint32_t target_steps, uint32_t sequence,
    const NucleoScurveLimits *limits, NucleoProfileFrame *frame)
{
  double max_velocity_hz;
  double max_acceleration_hz_s;
  double max_jerk_hz_s2;
  double jerk_time_s;
  double constant_accel_time_s;
  double cruise_time_s;
  double peak_velocity_hz;
  double no_cruise_steps;
  double accel_limited_distance_steps;
  double phase_duration_s[NUCLEO_PROFILE_PHASE_COUNT];
  double phase_jerk_hz_s2[NUCLEO_PROFILE_PHASE_COUNT];
  double velocity_hz = 0.0;
  double acceleration_hz_s = 0.0;
  double position_steps = 0.0;
  uint32_t index;

  if ((command_id == NULL) || (limits == NULL) || (frame == NULL)) {
    return NUCLEO_SCURVE_ERR_ARGUMENT;
  }
  if (axis > 1U) return NUCLEO_SCURVE_ERR_AXIS;
  if (target_steps == 0U) return NUCLEO_SCURVE_NO_MOTION;
  if ((limits->max_velocity_hz == 0U) ||
      (limits->max_velocity_hz > NUCLEO_SCURVE_MAX_PULSE_HZ) ||
      (limits->max_acceleration_hz_s == 0U) ||
      (limits->max_deceleration_hz_s == 0U) ||
      (limits->max_jerk_hz_s2 == 0U)) {
    return NUCLEO_SCURVE_ERR_LIMIT;
  }

  max_velocity_hz = (double)limits->max_velocity_hz;
  /* A symmetric first release uses the more restrictive acceleration limit. */
  max_acceleration_hz_s = (double)((limits->max_acceleration_hz_s <
                                    limits->max_deceleration_hz_s)
                                       ? limits->max_acceleration_hz_s
                                       : limits->max_deceleration_hz_s);
  max_jerk_hz_s2 = (double)limits->max_jerk_hz_s2;
  jerk_time_s = max_acceleration_hz_s / max_jerk_hz_s2;

  if (max_velocity_hz <=
      ((max_acceleration_hz_s * max_acceleration_hz_s) /
       max_jerk_hz_s2)) {
    jerk_time_s = sqrt(max_velocity_hz / max_jerk_hz_s2);
    constant_accel_time_s = 0.0;
  } else {
    constant_accel_time_s =
        (max_velocity_hz / max_acceleration_hz_s) - jerk_time_s;
  }

  no_cruise_steps =
      max_velocity_hz * ((2.0 * jerk_time_s) + constant_accel_time_s);
  if ((double)target_steps >= no_cruise_steps) {
    peak_velocity_hz = max_velocity_hz;
    cruise_time_s = ((double)target_steps - no_cruise_steps) / peak_velocity_hz;
  } else {
    accel_limited_distance_steps =
        (2.0 * max_acceleration_hz_s * max_acceleration_hz_s *
         max_acceleration_hz_s) /
        (max_jerk_hz_s2 * max_jerk_hz_s2);
    cruise_time_s = 0.0;
    if ((double)target_steps < accel_limited_distance_steps) {
      jerk_time_s = cbrt((double)target_steps / (2.0 * max_jerk_hz_s2));
      constant_accel_time_s = 0.0;
    } else {
      double root = sqrt((jerk_time_s * jerk_time_s) +
                         ((4.0 * (double)target_steps) /
                          max_acceleration_hz_s));
      constant_accel_time_s = (-3.0 * jerk_time_s + root) / 2.0;
    }
    peak_velocity_hz = max_jerk_hz_s2 * jerk_time_s *
                       (jerk_time_s + constant_accel_time_s);
  }

  phase_duration_s[0] = jerk_time_s;
  phase_duration_s[1] = constant_accel_time_s;
  phase_duration_s[2] = jerk_time_s;
  phase_duration_s[3] = cruise_time_s;
  phase_duration_s[4] = jerk_time_s;
  phase_duration_s[5] = constant_accel_time_s;
  phase_duration_s[6] = jerk_time_s;
  phase_jerk_hz_s2[0] = max_jerk_hz_s2;
  phase_jerk_hz_s2[1] = 0.0;
  phase_jerk_hz_s2[2] = -max_jerk_hz_s2;
  phase_jerk_hz_s2[3] = 0.0;
  phase_jerk_hz_s2[4] = -max_jerk_hz_s2;
  phase_jerk_hz_s2[5] = 0.0;
  phase_jerk_hz_s2[6] = max_jerk_hz_s2;

  memset(frame, 0, sizeof(*frame));
  strncpy(frame->command_id, command_id, NUCLEO_PROFILE_COMMAND_ID_MAX);
  frame->command_id[NUCLEO_PROFILE_COMMAND_ID_MAX] = '\0';
  frame->axis = axis;
  frame->direction = (direction != 0U) ? 1U : 0U;
  frame->steps = target_steps;
  frame->sequence = sequence;

  for (index = 0U; index < NUCLEO_PROFILE_PHASE_COUNT; index++) {
    double dt_s = phase_duration_s[index];
    double jerk_hz_s2 = phase_jerk_hz_s2[index];
    double end_acceleration_hz_s = acceleration_hz_s + jerk_hz_s2 * dt_s;
    double end_velocity_hz = velocity_hz + acceleration_hz_s * dt_s +
                             0.5 * jerk_hz_s2 * dt_s * dt_s;
    double end_position_steps = position_steps + velocity_hz * dt_s +
                                0.5 * acceleration_hz_s * dt_s * dt_s +
                                (jerk_hz_s2 * dt_s * dt_s * dt_s) / 6.0;
    NucleoProfilePhase *phase = &frame->phases[index];

    phase->duration_us = duration_us(dt_s);
    phase->start_rate_millihz = rounded_u32(velocity_hz * 1000.0);
    phase->end_rate_millihz = rounded_u32(end_velocity_hz * 1000.0);
    phase->start_accel_millihz_s = rounded_i32(acceleration_hz_s * 1000.0);
    phase->end_accel_millihz_s = rounded_i32(end_acceleration_hz_s * 1000.0);
    phase->jerk_millihz_s2 = rounded_i32(jerk_hz_s2 * 1000.0);
    phase->end_step = rounded_u32(end_position_steps);
    if (phase->end_step > target_steps) phase->end_step = target_steps;

    position_steps = end_position_steps;
    velocity_hz = end_velocity_hz;
    acceleration_hz_s = end_acceleration_hz_s;
  }

  /* Integer pulse count, not floating-point integration, owns completion. */
  frame->phases[NUCLEO_PROFILE_PHASE_COUNT - 1U].end_step = target_steps;
  frame->phases[NUCLEO_PROFILE_PHASE_COUNT - 1U].end_rate_millihz = 0U;
  frame->phases[NUCLEO_PROFILE_PHASE_COUNT - 1U].end_accel_millihz_s = 0;
  (void)peak_velocity_hz;
  return NUCLEO_SCURVE_OK;
}
