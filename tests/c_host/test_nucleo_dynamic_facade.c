#include "nucleo_dynamic_facade.h"

#include <assert.h>
#include <stdio.h>

typedef struct {
  uint32_t rate_millihz[2];
  uint32_t disable_calls;
} FacadeMock;

static void set_rate(void *context, uint8_t axis, uint32_t rate_millihz)
{
  FacadeMock *mock = (FacadeMock *)context;
  assert(axis < 2U);
  mock->rate_millihz[axis] = rate_millihz;
}

static void disable_all(void *context)
{
  FacadeMock *mock = (FacadeMock *)context;
  mock->rate_millihz[0] = 0U;
  mock->rate_millihz[1] = 0U;
  ++mock->disable_calls;
}

int main(void)
{
  const char *config_x =
      "DYN_CONFIG X 0 1000 100000 1 2500 30000000 60000000 50000000 300000000 cfg-1";
  const char *config_y =
      "DYN_CONFIG Y 0 1000 100000 1 2500 30000000 60000000 50000000 300000000 cfg-1";
  NucleoDynamicFacade facade;
  FacadeMock mock = {{0U, 0U}, 0U};
  NucleoDynamicRuntimeHooks hooks = {set_rate, disable_all, &mock};

  assert(NucleoDynamicFacade_Init(&facade, hooks) == 1U);
  assert(NucleoDynamicFacade_ApplyConfig(&facade, config_x, 0U) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(facade.runtime_ready == 0U);
  assert(NucleoDynamicFacade_ApplyConfig(&facade, config_y, 0U) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(facade.runtime_ready == 1U);
  assert(NucleoDynamicFacade_ApplyConfig(&facade, config_x, 1U) ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE);

  assert(NucleoDynamicFacade_SetPosition(&facade, 0U, 100U) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(NucleoDynamicFacade_SetPosition(&facade, 1U, 200U) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(NucleoDynamicFacade_StageTarget(
             &facade, "DYN_TARGET move-1 X 103 cfg-1") ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(NucleoDynamicFacade_StageTarget(
             &facade, "DYN_TARGET move-1 Y 195 cfg-1") ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(NucleoDynamicFacade_Start(&facade, "move-1", 3U, 0ULL, 1U) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  NucleoDynamicFacade_ControlTick(&facade, 1000ULL);
  assert(mock.rate_millihz[0] > 0U && mock.rate_millihz[1] > 0U);

  assert(NucleoDynamicFacade_OnEmittedPulse(&facade, 0U) == 1U);
  assert(NucleoDynamicFacade_OnEmittedPulse(&facade, 0U) == 1U);
  assert(NucleoDynamicFacade_OnEmittedPulse(&facade, 0U) == 0U);
  assert(facade.protocol.estimated_position_pulses[0] == 103U);
  assert(facade.coordinator.active_mask == 2U);
  assert(NucleoDynamicFacade_OnEmittedPulse(&facade, 1U) == 1U);
  assert(NucleoDynamicFacade_OnEmittedPulse(&facade, 1U) == 1U);
  assert(NucleoDynamicFacade_OnEmittedPulse(&facade, 1U) == 1U);
  assert(NucleoDynamicFacade_OnEmittedPulse(&facade, 1U) == 1U);
  assert(NucleoDynamicFacade_OnEmittedPulse(&facade, 1U) == 0U);
  assert(facade.protocol.estimated_position_pulses[1] == 195U);
  assert(facade.coordinator.active_mask == 0U);
  assert(NucleoDynamicFacade_StageTarget(
             &facade, "DYN_TARGET move-1 X 103 cfg-1") ==
         NUCLEO_DYNAMIC_PROTOCOL_DUPLICATE);

  assert(NucleoDynamicFacade_StageTarget(
             &facade, "DYN_TARGET stale X 120 wrong-rev") ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_REVISION);
  assert(NucleoDynamicFacade_StageTarget(
             &facade, "DYN_TARGET range X 1001 cfg-1") ==
         NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE);

  assert(NucleoDynamicFacade_StageTarget(
             &facade, "DYN_TARGET move-2 X 500 cfg-1") ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  assert(NucleoDynamicFacade_Start(&facade, "move-2", 1U, 2000ULL, 1U) ==
         NUCLEO_DYNAMIC_PROTOCOL_OK);
  NucleoDynamicFacade_Stop(&facade);
  assert(facade.protocol.position_valid[0] == 0U);
  assert(facade.protocol.position_valid[1] == 0U);
  assert(facade.coordinator.active_mask == 0U);
  assert(mock.disable_calls > 0U);

  puts("dynamic facade host tests passed");
  return 0;
}
