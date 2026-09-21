#include "nucleo_dynamic_planner.h"

#include <assert.h>
#include <stdio.h>

static void run_move(uint8_t axis, uint8_t direction, uint32_t target_pulses)
{
  NucleoDynamicConfig config = {
      {1U, 2500U, 30000U},
      {1000U, 30000U, 60000U, 50000U, 300000U},
      5000U};
  NucleoDynamicPlanner planner;
  uint32_t previous_emitted = 0U;
  uint32_t tick;
  assert(NucleoDynamicPlanner_Start(&planner, axis, direction, target_pulses,
                                    &config) == NUCLEO_CONSTRAINT_OK);
  for (tick = 0U; tick < 180000U &&
                  planner.state == NUCLEO_DYNAMIC_RUNNING; tick++) {
    assert(NucleoDynamicPlanner_Tick(&planner, &config) ==
           NUCLEO_CONSTRAINT_OK);
    assert(planner.emitted_pulses >= previous_emitted);
    assert(planner.emitted_pulses <= target_pulses);
    assert(planner.output_rate_millihz <= 30000000U);
    assert(planner.constraint.acceleration_millihz_s <= 60000000);
    assert(planner.constraint.acceleration_millihz_s >= -50000000);
    previous_emitted = planner.emitted_pulses;
  }
  if (planner.state != NUCLEO_DYNAMIC_COMPLETE) {
    fprintf(stderr, "axis=%u target=%lu emitted=%lu rate=%lu ticks=%lu\n",
            (unsigned int)axis, (unsigned long)target_pulses,
            (unsigned long)planner.emitted_pulses,
            (unsigned long)planner.output_rate_millihz,
            (unsigned long)tick);
  }
  assert(planner.state == NUCLEO_DYNAMIC_COMPLETE);
  assert(planner.emitted_pulses == target_pulses);
  assert(planner.output_rate_millihz == 0U);
  assert(planner.constraint.acceleration_millihz_s == 0);
}

int main(void)
{
  run_move(0U, 0U, 0U);
  run_move(0U, 1U, 1U);
  run_move(1U, 0U, 137U);
  run_move(0U, 1U, 170000U);
  /* Slot 27 regression: 340 mm at the commissioned Y conversion is 22,000
   * pulses. Virtual Kp must finish the terminal edge without oscillation. */
  run_move(1U, 1U, 22000U);
  puts("dynamic planner host tests passed");
  return 0;
}
