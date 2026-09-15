#include "nucleo_dynamic_app.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
  uint32_t inhibits;
} AppMock;

static void set_rate(void *context, uint8_t axis, uint32_t rate_millihz)
{
  (void)context; (void)axis; (void)rate_millihz;
}
static void disable_all(void *context) { (void)context; }
static uint8_t prepare_direction(void *context, uint8_t axis,
                                 uint8_t direction)
{
  (void)context;
  return (axis < 2U) && (direction < 2U);
}
static void emergency_inhibit(void *context)
{
  ++((AppMock *)context)->inhibits;
}

int main(void)
{
  NucleoDynamicApp app;
  AppMock mock = {0U};
  NucleoDynamicRuntimeHooks hooks = {
      set_rate, disable_all, &mock, prepare_direction};
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  char response[128];
  assert(NucleoDynamicApp_Init(&app, hooks, emergency_inhibit, &mock) == 1U);
  assert(NucleoDynamicApp_HandleLine(&app, "STOP", 0ULL, 0U, 0U,
                                     response, sizeof(response)) == 1U);
  assert(mock.inhibits == 1U);
  assert(strstr(response, "stopped") != NULL);
  assert(NucleoDynamicApp_HandleLine(&app, "DISARM", 0ULL, 0U, 0U,
                                     response, sizeof(response)) == 1U);
  assert(mock.inhibits == 2U);
  NucleoDynamicApp_EmergencyStop(&app);
  assert(mock.inhibits == 3U);
#else
  assert(NucleoDynamicApp_Init(&app, hooks, emergency_inhibit, &mock) == 0U);
  assert(app.initialized == 0U);
#endif
  puts("dynamic application bridge host tests passed");
  return 0;
}
