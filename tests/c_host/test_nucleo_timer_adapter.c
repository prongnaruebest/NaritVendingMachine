#include "nucleo_timer_adapter.h"

#include <assert.h>
#include <stdio.h>

typedef struct {
  unsigned int apply_count[2];
  unsigned int enable_count[2];
  unsigned int disable_count[2];
  uint16_t last_prescaler[2];
  uint16_t last_period[2];
  uint16_t last_pulse_width[2];
  uint8_t apply_ok;
} TimerPortMock;

static uint8_t apply_atomic(void *context, uint8_t axis, uint16_t prescaler,
                            uint16_t period, uint16_t pulse_width)
{
  TimerPortMock *mock = (TimerPortMock *)context;
  mock->apply_count[axis]++;
  mock->last_prescaler[axis] = prescaler;
  mock->last_period[axis] = period;
  mock->last_pulse_width[axis] = pulse_width;
  return mock->apply_ok;
}

static void enable(void *context, uint8_t axis)
{
  ((TimerPortMock *)context)->enable_count[axis]++;
}

static void disable(void *context, uint8_t axis)
{
  ((TimerPortMock *)context)->disable_count[axis]++;
}

int main(void)
{
  NucleoTimerAdapter adapter;
  TimerPortMock mock = {{0U, 0U}, {0U, 0U}, {0U, 0U}, {0U, 0U},
                        {0U, 0U}, {0U, 0U}, 1U};
  NucleoTimerPort port = {apply_atomic, enable, disable, &mock};

  assert(NucleoTimerAdapter_Init(&adapter, 90000000U, 5U, port) == 1U);
  assert(NucleoTimerAdapter_SetRate(&adapter, 0U, 1000000U) == 1U);
  assert(mock.apply_count[0] == 1U && mock.enable_count[0] == 1U);
  assert(mock.last_pulse_width[0] > 0U);
  assert(mock.last_pulse_width[0] < mock.last_period[0]);

  /* A phase-boundary rate update is atomic and does not disable/re-enable. */
  assert(NucleoTimerAdapter_SetRate(&adapter, 0U, 2000000U) == 1U);
  assert(mock.apply_count[0] == 2U);
  assert(mock.enable_count[0] == 1U);
  assert(mock.disable_count[0] == 0U);

  assert(NucleoTimerAdapter_SetRate(&adapter, 1U, 50000000U) == 1U);
  assert(mock.enable_count[1] == 1U);
  assert(NucleoTimerAdapter_SetRate(&adapter, 1U, 50000001U) == 0U);
  assert(mock.apply_count[1] == 1U);

  NucleoTimerAdapter_DisableAll(&adapter);
  assert(adapter.enabled[0] == 0U && adapter.enabled[1] == 0U);
  assert(mock.disable_count[0] == 1U && mock.disable_count[1] == 1U);

  mock.apply_ok = 0U;
  assert(NucleoTimerAdapter_SetRate(&adapter, 0U, 1000000U) == 0U);
  assert(adapter.faulted == 1U);
  assert(mock.disable_count[0] == 2U && mock.disable_count[1] == 2U);
  assert(NucleoTimerAdapter_SetRate(&adapter, 0U, 1000000U) == 0U);

  puts("nucleo_timer_adapter host tests passed");
  return 0;
}
