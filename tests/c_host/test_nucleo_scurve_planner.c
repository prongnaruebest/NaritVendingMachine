#include "nucleo_scurve_planner.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void assert_valid_plan(uint32_t steps, uint8_t direction)
{
  NucleoScurveLimits limits = {50000U, 120000U, 90000U, 500000U};
  NucleoProfileFrame frame;
  uint32_t index;
  uint32_t previous_step = 0U;
  assert(NucleoScurvePlanner_Build("host-plan", 0U, direction, steps, 7U,
                                  &limits, &frame) == NUCLEO_SCURVE_OK);
  assert(frame.steps == steps);
  assert(frame.direction == direction);
  for (index = 0U; index < NUCLEO_PROFILE_PHASE_COUNT; index++) {
    assert(frame.phases[index].end_step >= previous_step);
    assert(frame.phases[index].end_step <= steps);
    assert(frame.phases[index].start_rate_millihz <= 50000000U);
    assert(frame.phases[index].end_rate_millihz <= 50000000U);
    previous_step = frame.phases[index].end_step;
  }
  assert(frame.phases[6].end_step == steps);
  assert(frame.phases[6].end_rate_millihz == 0U);
  assert(frame.phases[6].end_accel_millihz_s == 0);
}

int main(void)
{
  NucleoScurveLimits limits = {30000U, 60000U, 60000U, 300000U};
  NucleoProfileFrame frame;
  assert(NucleoScurvePlanner_Build("zero", 0U, 0U, 0U, 0U, &limits,
                                  &frame) == NUCLEO_SCURVE_NO_MOTION);
  assert(NucleoScurvePlanner_Build("z", 2U, 0U, 100U, 0U, &limits,
                                  &frame) == NUCLEO_SCURVE_ERR_AXIS);
  limits.max_velocity_hz = 50001U;
  assert(NucleoScurvePlanner_Build("fast", 0U, 0U, 100U, 0U, &limits,
                                  &frame) == NUCLEO_SCURVE_ERR_LIMIT);
  assert_valid_plan(1U, 0U);
  assert_valid_plan(137U, 1U);
  assert_valid_plan(170000U, 0U);
  puts("S-curve planner host tests passed");
  return 0;
}
