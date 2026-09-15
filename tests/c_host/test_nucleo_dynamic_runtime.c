#include "nucleo_control_tick.h"
#include "nucleo_dynamic_runtime.h"

#include <assert.h>
#include <stdio.h>

typedef struct {
  uint32_t rates;
  uint32_t disables;
  uint32_t last_rate_millihz;
} RuntimeMock;

static void set_rate(void *context, uint8_t axis, uint32_t rate_millihz)
{
  RuntimeMock *mock = (RuntimeMock *)context;
  assert(axis < 2U);
  mock->rates++;
  mock->last_rate_millihz = rate_millihz;
}

static void disable_all(void *context)
{
  RuntimeMock *mock = (RuntimeMock *)context;
  mock->disables++;
  mock->last_rate_millihz = 0U;
}

static void start_runtime(NucleoDynamicRuntime *runtime, RuntimeMock *mock,
                          uint64_t now_us)
{
  NucleoDynamicConfig config = {
      {1U, 2500U, 30000U},
      {1000U, 30000U, 60000U, 50000U, 300000U},
      5000U};
  NucleoDynamicRuntimeHooks hooks = {set_rate, disable_all, mock};
  assert(NucleoDynamicRuntime_Init(runtime, &config, hooks) == 1U);
  assert(NucleoDynamicRuntime_Arm(runtime, now_us, 1U) == 1U);
  assert(NucleoDynamicRuntime_Start(runtime, 0U, 1U, 10000U) ==
         NUCLEO_CONSTRAINT_OK);
}

int main(void)
{
  NucleoDynamicRuntime runtime;
  NucleoControlTick control;
  RuntimeMock mock = {0U, 0U, 0U};
  NucleoControlTickHooks tick_hooks = {
      NucleoDynamicRuntime_ControlTick,
      NucleoDynamicRuntime_ControlFault,
      &runtime};

  {
    NucleoDynamicConfig pulse_config = {
        {1U, 2500U, 30000U},
        {1000U, 30000U, 60000U, 50000U, 300000U},
        5000U};
    NucleoDynamicRuntimeHooks pulse_hooks = {set_rate, disable_all, &mock};
    assert(NucleoDynamicRuntime_Init(&runtime, &pulse_config, pulse_hooks) == 1U);
    assert(NucleoDynamicRuntime_Arm(&runtime, 0ULL, 1U) == 1U);
    assert(NucleoDynamicRuntime_Start(&runtime, 0U, 1U, 2U) ==
           NUCLEO_CONSTRAINT_OK);
    NucleoDynamicRuntime_ControlTick(&runtime, 1000ULL);
    /* A 1 kHz planner tick must not claim pulses which TIM1 never emitted. */
    assert(runtime.planner.emitted_pulses == 0U);
    assert(NucleoDynamicRuntime_OnEmittedPulse(&runtime, 0U) == 1U);
    assert(runtime.planner.emitted_pulses == 1U);
    assert(NucleoDynamicRuntime_OnEmittedPulse(&runtime, 0U) == 0U);
    assert(runtime.planner.state == NUCLEO_DYNAMIC_COMPLETE);
    assert(runtime.planner.emitted_pulses == 2U && runtime.armed == 0U);
    mock.rates = 0U;
    mock.disables = 0U;
    mock.last_rate_millihz = 0U;
  }

  start_runtime(&runtime, &mock, 0ULL);
  NucleoDynamicRuntime_ControlTick(&runtime, 1000ULL);
  assert(mock.rates == 1U && mock.last_rate_millihz > 0U);
  NucleoDynamicRuntime_Stop(&runtime);
  assert(runtime.fault == NUCLEO_DYNAMIC_FAULT_STOP);
  assert(runtime.armed == 0U && mock.last_rate_millihz == 0U);
  assert(NucleoDynamicRuntime_Arm(&runtime, 2000ULL, 1U) == 0U);
  assert(NucleoDynamicRuntime_Reset(&runtime, 1U) == 1U);

  start_runtime(&runtime, &mock, 10000ULL);
  NucleoDynamicRuntime_Disarm(&runtime);
  assert(runtime.fault == NUCLEO_DYNAMIC_FAULT_DISARM);

  start_runtime(&runtime, &mock, 20000ULL);
  NucleoDynamicRuntime_ControlTick(&runtime, 520001ULL);
  assert(runtime.fault == NUCLEO_DYNAMIC_FAULT_WATCHDOG);

  start_runtime(&runtime, &mock, 600000ULL);
  NucleoDynamicRuntime_SafetyLoss(&runtime);
  assert(runtime.fault == NUCLEO_DYNAMIC_FAULT_SAFETY);
  assert(NucleoDynamicRuntime_Reset(&runtime, 0U) == 0U);

  start_runtime(&runtime, &mock, 700000ULL);
  assert(NucleoControlTick_Init(&control, tick_hooks) == 1U);
  assert(NucleoControlTick_Arm(&control, 700000ULL, 1U) == 1U);
  NucleoControlTick_OnTimer(&control, 701000ULL, 1U);
  assert(mock.last_rate_millihz > 0U);
  NucleoControlTick_OnTimer(&control, 704001ULL, 1U);
  assert(runtime.fault == NUCLEO_DYNAMIC_FAULT_CONTROL_TICK);
  assert(control.faulted == 1U && mock.last_rate_millihz == 0U);
  puts("dynamic runtime host tests passed");
  return 0;
}
