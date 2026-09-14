#ifndef NUCLEO_VIRTUAL_KP_H
#define NUCLEO_VIRTUAL_KP_H

#include <stdint.h>

typedef struct {
  uint8_t enabled;
  /* Kp has units 1/s and is stored as 1/1000 per second. */
  uint32_t kp_approach_milliper_s;
  uint32_t max_velocity_hz;
} NucleoVirtualKpConfig;

typedef enum {
  NUCLEO_VIRTUAL_KP_OK = 0,
  NUCLEO_VIRTUAL_KP_ERR_ARGUMENT,
  NUCLEO_VIRTUAL_KP_ERR_AXIS,
  NUCLEO_VIRTUAL_KP_ERR_CONFIG
} NucleoVirtualKpResult;

/* Produces a request only; the S-curve planner still owns all constraints. */
NucleoVirtualKpResult NucleoVirtualKp_RequestRate(
    uint8_t axis, uint32_t remaining_pulses,
    const NucleoVirtualKpConfig *config, uint32_t *requested_rate_hz);

#endif
