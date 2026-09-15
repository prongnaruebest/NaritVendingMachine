#include "nucleo_dynamic_dispatcher.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
  uint32_t rates[2];
  uint32_t disable_calls;
} DispatcherMock;

static void set_rate(void *context, uint8_t axis, uint32_t rate_millihz)
{
  DispatcherMock *mock = (DispatcherMock *)context;
  assert(axis < 2U);
  mock->rates[axis] = rate_millihz;
}

static void disable_all(void *context)
{
  DispatcherMock *mock = (DispatcherMock *)context;
  mock->rates[0] = 0U;
  mock->rates[1] = 0U;
  ++mock->disable_calls;
}

int main(void)
{
  NucleoDynamicFacade facade;
  NucleoDynamicDispatcher dispatcher;
  DispatcherMock mock = {{0U, 0U}, 0U};
  NucleoDynamicRuntimeHooks hooks = {set_rate, disable_all, &mock};
  char response[128];
  char oversized[321];

  assert(NucleoDynamicFacade_Init(&facade, hooks) == 1U);
  NucleoDynamicDispatcher_Init(&dispatcher, &facade);

  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, "STOP", 0ULL, 0U, 1U,
             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"status\":\"stopped\"") != NULL);
  assert(mock.disable_calls > 0U);

#if NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher,
             "DYN_CONFIG X 0 1000 100000 1 2500 30000000 60000000 50000000 300000000 cfg-1",
             0ULL, 1U, 0U, response, sizeof(response)) == 1U);
  assert(strstr(response, "configured") != NULL);
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher,
             "DYN_CONFIG Y 0 1000 100000 1 2500 30000000 60000000 50000000 300000000 cfg-1",
             0ULL, 1U, 0U, response, sizeof(response)) == 1U);
  assert(strstr(response, "configured") != NULL);
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, "DYN_POSITION X 100 cfg-1", 0ULL, 1U, 0U,
             response, sizeof(response)) == 1U);
  assert(strstr(response, "position_set") != NULL);
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, "DYN_POSITION Y 200 cfg-1", 0ULL, 1U, 0U,
             response, sizeof(response)) == 1U);
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, "DYN_TARGET move-1 X 500 cfg-1", 0ULL, 1U, 0U,
             response, sizeof(response)) == 1U);
  assert(strstr(response, "staged") != NULL);
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, "DYN_TARGET move-1 Y 600 cfg-1", 0ULL, 1U, 0U,
             response, sizeof(response)) == 1U);
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, "DYN_START move-1 XY", 0ULL, 0U, 0U,
             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"code\":\"STATE\"") != NULL);
  assert(facade.coordinator.active_mask == 0U);
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, "DYN_START move-1 XY", 0ULL, 1U, 0U,
             response, sizeof(response)) == 1U);
  assert(strstr(response, "running") != NULL);
  assert(facade.coordinator.active_mask == 3U);
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, "DISARM", 1ULL, 1U, 1U,
             response, sizeof(response)) == 1U);
  assert(facade.coordinator.active_mask == 0U);
#else
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher,
             "DYN_CONFIG X 0 1000 100000 1 2500 30000000 60000000 50000000 300000000 cfg-1",
             0ULL, 1U, 0U, response, sizeof(response)) == 1U);
  assert(strstr(response, "\"code\":\"STATE\"") != NULL);
#endif

  memset(oversized, 'A', 320U);
  oversized[320] = '\0';
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, oversized, 0ULL, 1U, 0U,
             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"code\":\"FORMAT\"") != NULL);
  assert(NucleoDynamicDispatcher_HandleLine(
             &dispatcher, "DYN_START bad\nX", 0ULL, 1U, 0U,
             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"code\":\"FORMAT\"") != NULL);
  puts("dynamic dispatcher host tests passed");
  return 0;
}
