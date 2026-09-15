#ifndef NUCLEO_CONSTRAINT_ENVELOPE_H
#define NUCLEO_CONSTRAINT_ENVELOPE_H

#include <stdint.h>

typedef struct {
  uint32_t control_period_us;
  uint32_t max_velocity_hz;
  uint32_t max_acceleration_hz_s;
  uint32_t max_deceleration_hz_s;
  uint32_t max_jerk_hz_s2;
} NucleoConstraintLimits;

typedef struct {
  uint32_t velocity_millihz;
  int32_t acceleration_millihz_s;
  uint32_t stopping_distance_millipulses;
  uint8_t braking;
} NucleoConstraintState;

typedef enum {
  NUCLEO_CONSTRAINT_OK = 0,
  NUCLEO_CONSTRAINT_ERR_ARGUMENT,
  NUCLEO_CONSTRAINT_ERR_LIMIT
} NucleoConstraintResult;

void NucleoConstraint_Init(NucleoConstraintState *state);
NucleoConstraintResult NucleoConstraint_Tick(
    NucleoConstraintState *state, const NucleoConstraintLimits *limits,
    uint32_t remaining_pulses, uint32_t requested_rate_millihz);

#endif
