#ifndef NUCLEO_SCURVE_PLANNER_H
#define NUCLEO_SCURVE_PLANNER_H

#include <stdint.h>

#include "nucleo_profile_buffer.h"

typedef struct {
  uint32_t max_velocity_hz;
  uint32_t max_acceleration_hz_s;
  uint32_t max_deceleration_hz_s;
  uint32_t max_jerk_hz_s2;
} NucleoScurveLimits;

typedef enum {
  NUCLEO_SCURVE_OK = 0,
  NUCLEO_SCURVE_NO_MOTION,
  NUCLEO_SCURVE_ERR_ARGUMENT,
  NUCLEO_SCURVE_ERR_AXIS,
  NUCLEO_SCURVE_ERR_LIMIT
} NucleoScurveResult;

/*
 * Builds one deterministic seven-segment S-curve in pulse-domain units.
 * This planner is intentionally X/Y-only until the G491RE timer integration
 * and machine commissioning gates are complete.  It does not arm or move an
 * axis; the Controller remains the sole authority that may submit a frame.
 */
NucleoScurveResult NucleoScurvePlanner_Build(
    const char *command_id, uint8_t axis, uint8_t direction,
    uint32_t target_steps, uint32_t sequence,
    const NucleoScurveLimits *limits, NucleoProfileFrame *frame);

#endif
