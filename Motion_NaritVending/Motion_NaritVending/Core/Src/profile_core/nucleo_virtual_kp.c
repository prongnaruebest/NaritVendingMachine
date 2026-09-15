#include "nucleo_virtual_kp.h"

#include <stddef.h>

#define NUCLEO_VIRTUAL_KP_SCALE 1000ULL
#define NUCLEO_VIRTUAL_KP_MAX_RATE_HZ 50000U
#define NUCLEO_VIRTUAL_KP_MAX_GAIN_MILLIPER_S 100000U

NucleoVirtualKpResult NucleoVirtualKp_RequestRate(
    uint8_t axis, uint32_t remaining_pulses,
    const NucleoVirtualKpConfig *config, uint32_t *requested_rate_hz)
{
  uint32_t requested_rate_millihz = 0U;
  if (requested_rate_hz == NULL) return NUCLEO_VIRTUAL_KP_ERR_ARGUMENT;
  NucleoVirtualKpResult result = NucleoVirtualKp_RequestRateMillihz(
      axis, remaining_pulses, config, &requested_rate_millihz);
  *requested_rate_hz = requested_rate_millihz / 1000U;
  return result;
}

NucleoVirtualKpResult NucleoVirtualKp_RequestRateMillihz(
    uint8_t axis, uint32_t remaining_pulses,
    const NucleoVirtualKpConfig *config, uint32_t *requested_rate_millihz)
{
  uint64_t proportional_rate_millihz;
  if ((config == NULL) || (requested_rate_millihz == NULL)) {
    return NUCLEO_VIRTUAL_KP_ERR_ARGUMENT;
  }
  *requested_rate_millihz = 0U;
  if (axis > 1U) return NUCLEO_VIRTUAL_KP_ERR_AXIS;
  if ((config->max_velocity_hz == 0U) ||
      (config->max_velocity_hz > NUCLEO_VIRTUAL_KP_MAX_RATE_HZ) ||
      ((config->enabled != 0U) &&
       ((config->kp_approach_milliper_s == 0U) ||
        (config->kp_approach_milliper_s >
         NUCLEO_VIRTUAL_KP_MAX_GAIN_MILLIPER_S)))) {
    return NUCLEO_VIRTUAL_KP_ERR_CONFIG;
  }
  if (remaining_pulses == 0U) return NUCLEO_VIRTUAL_KP_OK;
  if (config->enabled == 0U) {
    *requested_rate_millihz = config->max_velocity_hz * 1000U;
    return NUCLEO_VIRTUAL_KP_OK;
  }
  /* uint64_t keeps the gain/error product deterministic and overflow-safe. */
  proportional_rate_millihz =
      (uint64_t)config->kp_approach_milliper_s * remaining_pulses;
  if (proportional_rate_millihz >
      ((uint64_t)config->max_velocity_hz * NUCLEO_VIRTUAL_KP_SCALE)) {
    proportional_rate_millihz =
        (uint64_t)config->max_velocity_hz * NUCLEO_VIRTUAL_KP_SCALE;
  }
  *requested_rate_millihz = (uint32_t)proportional_rate_millihz;
  return NUCLEO_VIRTUAL_KP_OK;
}
