#ifndef NUCLEO_DYNAMIC_COORDINATOR_H
#define NUCLEO_DYNAMIC_COORDINATOR_H

#include "nucleo_dynamic_runtime.h"

#include <stdint.h>

#define NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT 2U

typedef struct {
  NucleoDynamicRuntime axes[NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT];
  uint8_t active_mask;
  uint8_t initialized;
} NucleoDynamicCoordinator;

uint8_t NucleoDynamicCoordinator_Init(
    NucleoDynamicCoordinator *coordinator,
    const NucleoDynamicConfig configs[NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT],
    NucleoDynamicRuntimeHooks hooks);
uint8_t NucleoDynamicCoordinator_Start(
    NucleoDynamicCoordinator *coordinator, uint8_t axis_mask,
    const uint8_t directions[NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT],
    const uint32_t distance_pulses[NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT],
    uint64_t now_us, uint8_t safety_permissive);
void NucleoDynamicCoordinator_Heartbeat(NucleoDynamicCoordinator *coordinator,
                                        uint64_t now_us,
                                        uint8_t safety_permissive);
void NucleoDynamicCoordinator_ControlTick(NucleoDynamicCoordinator *coordinator,
                                          uint64_t now_us);
uint8_t NucleoDynamicCoordinator_OnEmittedPulse(void *context, uint8_t axis);
void NucleoDynamicCoordinator_StopAll(NucleoDynamicCoordinator *coordinator);
void NucleoDynamicCoordinator_ControlledStopAll(
    NucleoDynamicCoordinator *coordinator);
void NucleoDynamicCoordinator_DisarmAll(NucleoDynamicCoordinator *coordinator);
void NucleoDynamicCoordinator_SafetyLoss(NucleoDynamicCoordinator *coordinator);

#endif
