#include "nucleo_timer_adapter.h"

#include <stddef.h>
#include <string.h>

#define TIMER_REGISTER_TICKS 65536ULL
#define MICROS_PER_SECOND 1000000ULL

uint8_t NucleoTimerAdapter_Init(NucleoTimerAdapter *adapter,
                                uint32_t timer_clock_hz,
                                uint32_t pulse_width_us,
                                NucleoTimerPort port)
{
  if ((adapter == NULL) || (timer_clock_hz == 0U) ||
      (pulse_width_us == 0U) || (port.apply_atomic == NULL) ||
      (port.enable == NULL) || (port.disable == NULL)) return 0U;
  memset(adapter, 0, sizeof(*adapter));
  adapter->timer_clock_hz = timer_clock_hz;
  adapter->pulse_width_us = pulse_width_us;
  adapter->port = port;
  return 1U;
}

uint8_t NucleoTimerAdapter_SetRate(NucleoTimerAdapter *adapter, uint8_t axis,
                                   uint32_t rate_millihz)
{
  uint64_t raw_period_ticks;
  uint64_t divider;
  uint64_t timer_ticks;
  uint64_t pulse_ticks;
  uint16_t prescaler;
  uint16_t period;
  uint16_t pulse_width;
  if ((adapter == NULL) || (axis >= NUCLEO_TIMER_AXIS_COUNT) ||
      (adapter->faulted != 0U)) return 0U;
  if (rate_millihz == 0U) {
    NucleoTimerAdapter_DisableAxis(adapter, axis);
    return 1U;
  }
  if (rate_millihz > NUCLEO_TIMER_MAX_RATE_MILLIHZ) return 0U;

  raw_period_ticks = ((uint64_t)adapter->timer_clock_hz * 1000ULL +
                      rate_millihz / 2U) / rate_millihz;
  if (raw_period_ticks < 2ULL) return 0U;
  divider = (raw_period_ticks + TIMER_REGISTER_TICKS - 1ULL) /
            TIMER_REGISTER_TICKS;
  if ((divider == 0ULL) || (divider > TIMER_REGISTER_TICKS)) return 0U;
  timer_ticks = (raw_period_ticks + divider / 2ULL) / divider;
  if ((timer_ticks < 2ULL) || (timer_ticks > TIMER_REGISTER_TICKS)) return 0U;

  pulse_ticks = (((uint64_t)adapter->timer_clock_hz / divider) *
                 adapter->pulse_width_us + MICROS_PER_SECOND - 1ULL) /
                MICROS_PER_SECOND;
  if (pulse_ticks == 0ULL) pulse_ticks = 1ULL;
  if (pulse_ticks >= timer_ticks) pulse_ticks = timer_ticks - 1ULL;

  prescaler = (uint16_t)(divider - 1ULL);
  period = (uint16_t)(timer_ticks - 1ULL);
  pulse_width = (uint16_t)pulse_ticks;
  if (adapter->port.apply_atomic(adapter->port.context, axis, prescaler,
                                 period, pulse_width) == 0U) {
    adapter->faulted = 1U;
    NucleoTimerAdapter_DisableAll(adapter);
    return 0U;
  }
  adapter->rate_millihz[axis] = rate_millihz;
  if (adapter->enabled[axis] == 0U) {
    adapter->port.enable(adapter->port.context, axis);
    adapter->enabled[axis] = 1U;
  }
  return 1U;
}

void NucleoTimerAdapter_DisableAxis(NucleoTimerAdapter *adapter, uint8_t axis)
{
  if ((adapter == NULL) || (axis >= NUCLEO_TIMER_AXIS_COUNT)) return;
  adapter->port.disable(adapter->port.context, axis);
  adapter->enabled[axis] = 0U;
  adapter->rate_millihz[axis] = 0U;
}

void NucleoTimerAdapter_DisableAll(NucleoTimerAdapter *adapter)
{
  uint8_t axis;
  if (adapter == NULL) return;
  for (axis = 0U; axis < NUCLEO_TIMER_AXIS_COUNT; axis++) {
    NucleoTimerAdapter_DisableAxis(adapter, axis);
  }
}

void NucleoTimerAdapter_SetRateHook(void *context, uint8_t axis,
                                    uint32_t rate_millihz)
{
  NucleoTimerAdapter *adapter = (NucleoTimerAdapter *)context;
  if (NucleoTimerAdapter_SetRate(adapter, axis, rate_millihz) == 0U &&
      adapter != NULL) {
    adapter->faulted = 1U;
    NucleoTimerAdapter_DisableAll(adapter);
  }
}

void NucleoTimerAdapter_DisableAxisHook(void *context, uint8_t axis)
{
  NucleoTimerAdapter_DisableAxis((NucleoTimerAdapter *)context, axis);
}
