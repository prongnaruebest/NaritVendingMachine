#include "nucleo_compare_adapter.h"

#include <assert.h>
#include <stdio.h>

typedef struct {
  unsigned int apply_count[2];
  unsigned int enable_count[2];
  unsigned int disable_count[2];
  uint32_t half_period[2];
  uint8_t apply_ok;
} CompareMock;

static uint8_t apply_atomic(void *context, uint8_t axis, uint32_t half_period)
{
  CompareMock *mock = (CompareMock *)context;
  mock->apply_count[axis]++;
  mock->half_period[axis] = half_period;
  return mock->apply_ok;
}

static void enable(void *context, uint8_t axis)
{
  ((CompareMock *)context)->enable_count[axis]++;
}

static void disable(void *context, uint8_t axis)
{
  ((CompareMock *)context)->disable_count[axis]++;
}

int main(void)
{
  NucleoCompareAdapter adapter;
  CompareMock mock = {{0U, 0U}, {0U, 0U}, {0U, 0U}, {0U, 0U}, 1U};
  NucleoComparePort port = {apply_atomic, enable, disable, &mock};

  /* TIM1 remains at one shared 1 MHz timebase for X CH1 and Y CH2. */
  assert(NucleoCompareAdapter_Init(&adapter, 1000000U, port) == 1U);
  assert(NucleoCompareAdapter_SetRate(&adapter, 0U, 1000000U) == 1U);
  assert(mock.half_period[0] == 500U);
  assert(NucleoCompareAdapter_SetRate(&adapter, 1U, 2000000U) == 1U);
  assert(mock.half_period[1] == 250U);
  assert(mock.enable_count[0] == 1U && mock.enable_count[1] == 1U);

  /* Updating X cannot reconfigure or interrupt Y's shared timer channel. */
  assert(NucleoCompareAdapter_SetRate(&adapter, 0U, 4000000U) == 1U);
  assert(mock.half_period[0] == 125U);
  assert(mock.half_period[1] == 250U);
  assert(mock.enable_count[0] == 1U && mock.disable_count[0] == 0U);
  assert(mock.apply_count[1] == 1U && mock.disable_count[1] == 0U);

  assert(NucleoCompareAdapter_SetRate(&adapter, 0U, 50000000U) == 1U);
  assert(mock.half_period[0] == 10U);
  assert(NucleoCompareAdapter_SetRate(&adapter, 0U, 50000001U) == 0U);

  mock.apply_ok = 0U;
  assert(NucleoCompareAdapter_SetRate(&adapter, 1U, 1000000U) == 0U);
  assert(adapter.faulted == 1U);
  assert(mock.disable_count[0] == 1U && mock.disable_count[1] == 1U);

  puts("nucleo_compare_adapter host tests passed");
  return 0;
}
