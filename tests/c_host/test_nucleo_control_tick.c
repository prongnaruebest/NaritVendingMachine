#include "nucleo_control_tick.h"

#include <assert.h>
#include <stdio.h>

typedef struct {
  uint32_t ticks;
  uint32_t stops;
  uint64_t last_now_us;
} TickMock;

static void on_tick(void *context, uint64_t now_us)
{
  TickMock *mock = (TickMock *)context;
  mock->ticks++;
  mock->last_now_us = now_us;
}

static void on_stop(void *context)
{
  ((TickMock *)context)->stops++;
}

int main(void)
{
  NucleoControlTick control;
  TickMock mock = {0U, 0U, 0ULL};
  NucleoControlTickHooks hooks = {on_tick, on_stop, &mock};
  uint64_t now_us;

  assert(NucleoControlTick_Init(&control, hooks) == 1U);
  assert(NucleoControlTick_Arm(&control, 1000ULL, 1U) == 1U);
  NucleoControlTick_OnTimer(&control, 2000ULL, 1U);
  assert(mock.ticks == 1U && mock.last_now_us == 2000ULL);
  NucleoControlTick_Heartbeat(&control, 3000ULL, 1U);
  NucleoControlTick_OnTimer(&control, 4000ULL, 1U);
  assert(mock.ticks == 2U && mock.stops == 0U);

  /* A delayed ISR must stop instead of compressing missed planner ticks. */
  NucleoControlTick_OnTimer(&control, 7001ULL, 1U);
  assert(control.faulted == 1U && control.armed == 0U);
  assert(mock.stops == 1U && mock.ticks == 2U);
  assert(NucleoControlTick_Arm(&control, 8000ULL, 1U) == 0U);

  assert(NucleoControlTick_Init(&control, hooks) == 1U);
  assert(NucleoControlTick_Arm(&control, 0ULL, 1U) == 1U);
  NucleoControlTick_OnTimer(&control, 1000ULL, 0U);
  assert(control.faulted == 1U && mock.stops == 2U);

  assert(NucleoControlTick_Init(&control, hooks) == 1U);
  assert(NucleoControlTick_Arm(&control, 0ULL, 1U) == 1U);
  for (now_us = 1000ULL; now_us <= 501000ULL; now_us += 1000ULL) {
    NucleoControlTick_OnTimer(&control, now_us, 1U);
  }
  assert(control.faulted == 1U && mock.stops == 3U);

  assert(NucleoControlTick_Init(&control, hooks) == 1U);
  assert(NucleoControlTick_Arm(&control, 1000ULL, 1U) == 1U);
  NucleoControlTick_Disarm(&control);
  assert(control.armed == 0U && mock.stops == 4U);

  puts("control tick host tests passed");
  return 0;
}
