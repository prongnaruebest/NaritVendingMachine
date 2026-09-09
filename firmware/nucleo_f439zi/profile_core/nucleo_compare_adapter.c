#include "nucleo_compare_adapter.h"

#include <stddef.h>
#include <string.h>

uint8_t NucleoCompareAdapter_Init(NucleoCompareAdapter *adapter,
                                  uint32_t timer_tick_hz,
                                  NucleoComparePort port)
{
  if ((adapter == NULL) || (timer_tick_hz == 0U) ||
      (port.apply_half_period_atomic == NULL) ||
      (port.enable_channel == NULL) || (port.disable_channel == NULL)) {
    return 0U;
  }
  memset(adapter, 0, sizeof(*adapter));
  adapter->timer_tick_hz = timer_tick_hz;
  adapter->port = port;
  return 1U;
}

uint8_t NucleoCompareAdapter_SetRate(NucleoCompareAdapter *adapter,
                                     uint8_t axis,
                                     uint32_t rate_millihz)
{
  uint64_t denominator;
  uint64_t half_period;
  if ((adapter == NULL) || (axis >= NUCLEO_COMPARE_AXIS_COUNT) ||
      (adapter->faulted != 0U)) return 0U;
  if (rate_millihz == 0U) {
    NucleoCompareAdapter_DisableAxis(adapter, axis);
    return 1U;
  }
  if (rate_millihz > NUCLEO_COMPARE_MAX_RATE_MILLIHZ) return 0U;
  denominator = (uint64_t)rate_millihz * 2ULL;
  half_period = ((uint64_t)adapter->timer_tick_hz * 1000ULL +
                 denominator / 2ULL) / denominator;
  if ((half_period == 0ULL) || (half_period > 0xffffffffULL)) return 0U;
  if (adapter->port.apply_half_period_atomic(
          adapter->port.context, axis, (uint32_t)half_period) == 0U) {
    adapter->faulted = 1U;
    NucleoCompareAdapter_DisableAll(adapter);
    return 0U;
  }
  adapter->half_period_ticks[axis] = (uint32_t)half_period;
  if (adapter->enabled[axis] == 0U) {
    adapter->port.enable_channel(adapter->port.context, axis);
    adapter->enabled[axis] = 1U;
  }
  return 1U;
}

void NucleoCompareAdapter_DisableAxis(NucleoCompareAdapter *adapter,
                                      uint8_t axis)
{
  if ((adapter == NULL) || (axis >= NUCLEO_COMPARE_AXIS_COUNT)) return;
  adapter->port.disable_channel(adapter->port.context, axis);
  adapter->enabled[axis] = 0U;
  adapter->half_period_ticks[axis] = 0U;
}

void NucleoCompareAdapter_DisableAll(NucleoCompareAdapter *adapter)
{
  uint8_t axis;
  if (adapter == NULL) return;
  for (axis = 0U; axis < NUCLEO_COMPARE_AXIS_COUNT; axis++) {
    NucleoCompareAdapter_DisableAxis(adapter, axis);
  }
}
