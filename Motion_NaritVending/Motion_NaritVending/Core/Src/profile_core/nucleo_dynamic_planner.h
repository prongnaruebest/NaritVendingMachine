#ifndef NUCLEO_DYNAMIC_PLANNER_H
#define NUCLEO_DYNAMIC_PLANNER_H

#include "nucleo_constraint_envelope.h"
#include "nucleo_virtual_kp.h"

#include <stdint.h>

typedef enum {
  NUCLEO_DYNAMIC_IDLE = 0,
  NUCLEO_DYNAMIC_RUNNING,
  NUCLEO_DYNAMIC_COMPLETE,
  NUCLEO_DYNAMIC_FAILED
} NucleoDynamicState;

typedef struct {
  NucleoVirtualKpConfig kp;
  NucleoConstraintLimits constraints;
  uint32_t terminal_max_rate_millihz;
} NucleoDynamicConfig;

typedef struct {
  NucleoConstraintState constraint;
  uint64_t pulse_phase_millihz_us;
  uint32_t target_pulses;
  uint32_t emitted_pulses;
  uint32_t output_rate_millihz;
  uint8_t axis;
  uint8_t direction;
  NucleoDynamicState state;
} NucleoDynamicPlanner;

void NucleoDynamicPlanner_Init(NucleoDynamicPlanner *planner);
NucleoConstraintResult NucleoDynamicPlanner_Start(
    NucleoDynamicPlanner *planner, uint8_t axis, uint8_t direction,
    uint32_t target_pulses, const NucleoDynamicConfig *config);
NucleoConstraintResult NucleoDynamicPlanner_Tick(
    NucleoDynamicPlanner *planner, const NucleoDynamicConfig *config);

#endif
