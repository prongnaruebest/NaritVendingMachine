#include "nucleo_dynamic_planner.h"

#include <stddef.h>
#include <string.h>

#define PULSE_PHASE_PER_EDGE_MILLIHZ_US 1000000000ULL

void NucleoDynamicPlanner_Init(NucleoDynamicPlanner *planner)
{
  if (planner != NULL) memset(planner, 0, sizeof(*planner));
}

NucleoConstraintResult NucleoDynamicPlanner_Start(
    NucleoDynamicPlanner *planner, uint8_t axis, uint8_t direction,
    uint32_t target_pulses, const NucleoDynamicConfig *config)
{
  uint32_t ignored_rate_millihz;
  if ((planner == NULL) || (config == NULL)) {
    return NUCLEO_CONSTRAINT_ERR_ARGUMENT;
  }
  if ((axis > 1U) || (config->terminal_max_rate_millihz == 0U) ||
      (NucleoVirtualKp_RequestRateMillihz(
           axis, target_pulses, &config->kp,
           &ignored_rate_millihz) != NUCLEO_VIRTUAL_KP_OK)) {
    return NUCLEO_CONSTRAINT_ERR_LIMIT;
  }
  NucleoDynamicPlanner_Init(planner);
  planner->axis = axis;
  planner->direction = direction != 0U ? 1U : 0U;
  planner->target_pulses = target_pulses;
  planner->state = target_pulses == 0U ? NUCLEO_DYNAMIC_COMPLETE
                                      : NUCLEO_DYNAMIC_RUNNING;
  return NUCLEO_CONSTRAINT_OK;
}

static NucleoConstraintResult planner_tick(
    NucleoDynamicPlanner *planner, const NucleoDynamicConfig *config,
    uint8_t simulate_emitted_pulses)
{
  uint32_t remaining_pulses;
  uint32_t requested_rate_millihz;
  uint64_t pulses_due;
  NucleoVirtualKpResult kp_result;
  NucleoConstraintResult constraint_result;
  if ((planner == NULL) || (config == NULL)) {
    return NUCLEO_CONSTRAINT_ERR_ARGUMENT;
  }
  if ((planner->state != NUCLEO_DYNAMIC_RUNNING) &&
      (planner->state != NUCLEO_DYNAMIC_STOPPING)) return NUCLEO_CONSTRAINT_OK;
  remaining_pulses = planner->target_pulses - planner->emitted_pulses;
  if (planner->state == NUCLEO_DYNAMIC_STOPPING) {
    requested_rate_millihz = 0U;
  } else {
    kp_result = NucleoVirtualKp_RequestRateMillihz(
        planner->axis, remaining_pulses, &config->kp,
        &requested_rate_millihz);
    if (kp_result != NUCLEO_VIRTUAL_KP_OK) {
      planner->state = NUCLEO_DYNAMIC_FAILED;
      planner->output_rate_millihz = 0U;
      return NUCLEO_CONSTRAINT_ERR_LIMIT;
    }
  }
  constraint_result = NucleoConstraint_Tick(
      &planner->constraint, &config->constraints, remaining_pulses,
      requested_rate_millihz);
  if (constraint_result != NUCLEO_CONSTRAINT_OK) {
    planner->state = NUCLEO_DYNAMIC_FAILED;
    planner->output_rate_millihz = 0U;
    return constraint_result;
  }
  planner->output_rate_millihz = planner->constraint.velocity_millihz;
  if ((planner->state == NUCLEO_DYNAMIC_STOPPING) &&
      (planner->constraint.velocity_millihz == 0U) &&
      (planner->constraint.acceleration_millihz_s == 0)) {
    planner->state = NUCLEO_DYNAMIC_STOPPED;
    return NUCLEO_CONSTRAINT_OK;
  }
  if (simulate_emitted_pulses == 0U) return NUCLEO_CONSTRAINT_OK;
  planner->pulse_phase_millihz_us +=
      (uint64_t)planner->output_rate_millihz *
      config->constraints.control_period_us;
  pulses_due = planner->pulse_phase_millihz_us /
               PULSE_PHASE_PER_EDGE_MILLIHZ_US;
  planner->pulse_phase_millihz_us %= PULSE_PHASE_PER_EDGE_MILLIHZ_US;

  if (pulses_due >= remaining_pulses) {
    if (planner->output_rate_millihz >
        config->terminal_max_rate_millihz) {
      /* Hold the final edge until the jerk-limited state reaches terminal rate. */
      pulses_due = remaining_pulses > 1U ? remaining_pulses - 1U : 0U;
      planner->pulse_phase_millihz_us =
          PULSE_PHASE_PER_EDGE_MILLIHZ_US - 1ULL;
    } else {
      pulses_due = remaining_pulses;
    }
  }
  planner->emitted_pulses += (uint32_t)pulses_due;
  if (planner->emitted_pulses == planner->target_pulses) {
    planner->output_rate_millihz = 0U;
    NucleoConstraint_Init(&planner->constraint);
    planner->state = NUCLEO_DYNAMIC_COMPLETE;
  }
  return NUCLEO_CONSTRAINT_OK;
}

void NucleoDynamicPlanner_RequestControlledStop(NucleoDynamicPlanner *planner)
{
  if ((planner != NULL) && (planner->state == NUCLEO_DYNAMIC_RUNNING)) {
    planner->state = NUCLEO_DYNAMIC_STOPPING;
  }
}

NucleoConstraintResult NucleoDynamicPlanner_Tick(
    NucleoDynamicPlanner *planner, const NucleoDynamicConfig *config)
{
  /* This deterministic simulator remains useful for host trajectory proofs. */
  return planner_tick(planner, config, 1U);
}

NucleoConstraintResult NucleoDynamicPlanner_RealtimeTick(
    NucleoDynamicPlanner *planner, const NucleoDynamicConfig *config)
{
  /* Realtime position advances only from a confirmed falling STEP edge. */
  return planner_tick(planner, config, 0U);
}

NucleoConstraintResult NucleoDynamicPlanner_RecordEmittedPulse(
    NucleoDynamicPlanner *planner, const NucleoDynamicConfig *config)
{
  if ((planner == NULL) || (config == NULL)) {
    return NUCLEO_CONSTRAINT_ERR_ARGUMENT;
  }
  if (((planner->state != NUCLEO_DYNAMIC_RUNNING) &&
       (planner->state != NUCLEO_DYNAMIC_STOPPING)) ||
      (planner->emitted_pulses >= planner->target_pulses)) {
    return NUCLEO_CONSTRAINT_ERR_LIMIT;
  }
  ++planner->emitted_pulses;
  if (planner->emitted_pulses == planner->target_pulses) {
    if (planner->output_rate_millihz > config->terminal_max_rate_millihz) {
      planner->state = NUCLEO_DYNAMIC_FAILED;
      planner->output_rate_millihz = 0U;
      return NUCLEO_CONSTRAINT_ERR_LIMIT;
    }
    planner->output_rate_millihz = 0U;
    NucleoConstraint_Init(&planner->constraint);
    planner->state = NUCLEO_DYNAMIC_COMPLETE;
  }
  return NUCLEO_CONSTRAINT_OK;
}
