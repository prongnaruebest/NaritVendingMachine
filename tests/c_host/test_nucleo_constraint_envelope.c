#include "nucleo_constraint_envelope.h"

#include <assert.h>
#include <stdio.h>

int main(void)
{
  NucleoConstraintLimits limits = {1000U, 30000U, 60000U, 50000U, 300000U};
  NucleoConstraintState state;
  uint32_t prior_velocity;
  int tick;
  NucleoConstraint_Init(&state);
  for (tick = 0; tick < 300; tick++) {
    prior_velocity = state.velocity_millihz;
    assert(NucleoConstraint_Tick(&state, &limits, 10000U, 30000000U) == NUCLEO_CONSTRAINT_OK);
    assert(state.velocity_millihz <= 30000000U);
    assert(state.acceleration_millihz_s <= 60000000);
    assert(state.acceleration_millihz_s >= -50000000);
    assert(state.velocity_millihz >= prior_velocity || state.braking != 0U);
  }
  prior_velocity = state.velocity_millihz;
  {
    int32_t prior_acceleration = state.acceleration_millihz_s;
    assert(NucleoConstraint_Tick(&state, &limits, 2U, 5000U) ==
           NUCLEO_CONSTRAINT_OK);
    assert(state.braking == 1U);
    assert(state.acceleration_millihz_s < prior_acceleration);
  }
  assert(state.velocity_millihz > 5000U);
  for (tick = 0; tick < 500 && state.velocity_millihz >= prior_velocity;
       tick++) {
    assert(NucleoConstraint_Tick(&state, &limits, 2U, 5000U) ==
           NUCLEO_CONSTRAINT_OK);
  }
  assert(state.velocity_millihz < prior_velocity);
  assert(NucleoConstraint_Tick(&state, &limits, 0U, 0U) == NUCLEO_CONSTRAINT_OK);
  assert(state.velocity_millihz == 0U && state.acceleration_millihz_s == 0);
  limits.control_period_us = 0U;
  assert(NucleoConstraint_Tick(&state, &limits, 10U, 1000U) == NUCLEO_CONSTRAINT_ERR_LIMIT);
  puts("constraint envelope host tests passed");
  return 0;
}
