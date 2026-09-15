#include "nucleo_virtual_kp.h"

#include <assert.h>
#include <stdio.h>

int main(void)
{
  NucleoVirtualKpConfig config = {1U, 2500U, 30000U};
  uint32_t requested_rate_hz = 123U;
  assert(NucleoVirtualKp_RequestRate(0U, 0U, &config, &requested_rate_hz) == NUCLEO_VIRTUAL_KP_OK);
  assert(requested_rate_hz == 0U);
  assert(NucleoVirtualKp_RequestRate(0U, 4000U, &config, &requested_rate_hz) == NUCLEO_VIRTUAL_KP_OK);
  assert(requested_rate_hz == 10000U);
  assert(NucleoVirtualKp_RequestRate(1U, 20000U, &config, &requested_rate_hz) == NUCLEO_VIRTUAL_KP_OK);
  assert(requested_rate_hz == 30000U);
  config.kp_approach_milliper_s = 500U;
  assert(NucleoVirtualKp_RequestRateMillihz(0U, 1U, &config,
                                           &requested_rate_hz) ==
         NUCLEO_VIRTUAL_KP_OK);
  assert(requested_rate_hz == 500U);
  config.enabled = 0U;
  config.kp_approach_milliper_s = 0U;
  assert(NucleoVirtualKp_RequestRate(0U, 1U, &config, &requested_rate_hz) == NUCLEO_VIRTUAL_KP_OK);
  assert(requested_rate_hz == 30000U);
  config.enabled = 1U;
  assert(NucleoVirtualKp_RequestRate(2U, 100U, &config, &requested_rate_hz) == NUCLEO_VIRTUAL_KP_ERR_AXIS);
  config.max_velocity_hz = 50001U;
  assert(NucleoVirtualKp_RequestRate(0U, 100U, &config, &requested_rate_hz) == NUCLEO_VIRTUAL_KP_ERR_CONFIG);
  puts("virtual Kp host tests passed");
  return 0;
}
