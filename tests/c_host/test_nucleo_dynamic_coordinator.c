#include "nucleo_dynamic_coordinator.h"

#include <assert.h>
#include <stdio.h>

typedef struct {
  uint32_t rate_millihz[2];
  uint32_t disable_calls;
} CoordinatorMock;

static void set_rate(void *context, uint8_t axis, uint32_t rate_millihz)
{
  CoordinatorMock *mock = (CoordinatorMock *)context;
  assert(axis < 2U);
  mock->rate_millihz[axis] = rate_millihz;
}

static void disable_all(void *context)
{
  CoordinatorMock *mock = (CoordinatorMock *)context;
  mock->rate_millihz[0] = 0U;
  mock->rate_millihz[1] = 0U;
  ++mock->disable_calls;
}

static NucleoDynamicConfig config(void)
{
  NucleoDynamicConfig result = {
      {1U, 2500U, 30000U},
      {1000U, 30000U, 60000U, 50000U, 300000U},
      5000U};
  return result;
}

int main(void)
{
  NucleoDynamicCoordinator coordinator;
  CoordinatorMock mock = {{0U, 0U}, 0U};
  NucleoDynamicConfig configs[2] = {config(), config()};
  NucleoDynamicRuntimeHooks hooks = {set_rate, disable_all, &mock, NULL};
  uint8_t directions[2] = {1U, 0U};
  uint32_t distances[2] = {2U, 3U};

  assert(NucleoDynamicCoordinator_Init(&coordinator, configs, hooks) == 1U);
  assert(NucleoDynamicCoordinator_Start(&coordinator, 3U, directions,
                                        distances, 0ULL, 1U) == 1U);
  NucleoDynamicCoordinator_ControlTick(&coordinator, 1000ULL);
  assert(mock.rate_millihz[0] > 0U && mock.rate_millihz[1] > 0U);
  assert(NucleoDynamicCoordinator_OnEmittedPulse(&coordinator, 0U) == 1U);
  assert(NucleoDynamicCoordinator_OnEmittedPulse(&coordinator, 0U) == 0U);
  assert(coordinator.active_mask == 2U);
  assert(coordinator.axes[0].planner.state == NUCLEO_DYNAMIC_COMPLETE);
  assert(coordinator.axes[1].planner.state == NUCLEO_DYNAMIC_RUNNING);
  assert(NucleoDynamicCoordinator_OnEmittedPulse(&coordinator, 1U) == 1U);
  assert(NucleoDynamicCoordinator_OnEmittedPulse(&coordinator, 1U) == 1U);
  assert(NucleoDynamicCoordinator_OnEmittedPulse(&coordinator, 1U) == 0U);
  assert(coordinator.active_mask == 0U);
  assert(coordinator.axes[1].planner.state == NUCLEO_DYNAMIC_COMPLETE);

  assert(NucleoDynamicRuntime_Reset(&coordinator.axes[0], 1U) == 1U);
  assert(NucleoDynamicRuntime_Reset(&coordinator.axes[1], 1U) == 1U);
  distances[0] = 100U;
  distances[1] = 100U;
  assert(NucleoDynamicCoordinator_Start(&coordinator, 3U, directions,
                                        distances, 10000ULL, 1U) == 1U);
  NucleoDynamicCoordinator_SafetyLoss(&coordinator);
  assert(coordinator.active_mask == 0U);
  assert(coordinator.axes[0].fault == NUCLEO_DYNAMIC_FAULT_SAFETY);
  assert(coordinator.axes[1].fault == NUCLEO_DYNAMIC_FAULT_SAFETY);
  assert(mock.rate_millihz[0] == 0U && mock.rate_millihz[1] == 0U);
  assert(mock.disable_calls >= 1U);
  puts("dynamic coordinator host tests passed");
  return 0;
}
