#include "nucleo_dynamic_coordinator.h"

#include <stddef.h>
#include <string.h>

uint8_t NucleoDynamicCoordinator_Init(
    NucleoDynamicCoordinator *coordinator,
    const NucleoDynamicConfig configs[NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT],
    NucleoDynamicRuntimeHooks hooks)
{
  uint8_t axis;
  if ((coordinator == NULL) || (configs == NULL)) return 0U;
  memset(coordinator, 0, sizeof(*coordinator));
  for (axis = 0U; axis < NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT; ++axis) {
    if (NucleoDynamicRuntime_Init(&coordinator->axes[axis], &configs[axis],
                                  hooks) == 0U) return 0U;
  }
  coordinator->initialized = 1U;
  return 1U;
}

uint8_t NucleoDynamicCoordinator_Start(
    NucleoDynamicCoordinator *coordinator, uint8_t axis_mask,
    const uint8_t directions[NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT],
    const uint32_t distance_pulses[NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT],
    uint64_t now_us, uint8_t safety_permissive)
{
  uint8_t axis;
  if ((coordinator == NULL) || (directions == NULL) ||
      (distance_pulses == NULL) || (coordinator->initialized == 0U) ||
      (axis_mask == 0U) || (axis_mask > 3U) || (safety_permissive == 0U) ||
      (coordinator->active_mask != 0U)) return 0U;
  for (axis = 0U; axis < NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT; ++axis) {
    if (((axis_mask & (1U << axis)) != 0U) &&
        ((distance_pulses[axis] == 0U) || (directions[axis] > 1U) ||
         (NucleoDynamicRuntime_Arm(&coordinator->axes[axis], now_us, 1U) == 0U))) {
      NucleoDynamicCoordinator_DisarmAll(coordinator);
      return 0U;
    }
  }
  for (axis = 0U; axis < NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT; ++axis) {
    if (((axis_mask & (1U << axis)) != 0U) &&
        (NucleoDynamicRuntime_Start(&coordinator->axes[axis], axis,
                                    directions[axis], distance_pulses[axis]) !=
         NUCLEO_CONSTRAINT_OK)) {
      NucleoDynamicCoordinator_DisarmAll(coordinator);
      return 0U;
    }
  }
  coordinator->active_mask = axis_mask;
  return 1U;
}

void NucleoDynamicCoordinator_Heartbeat(NucleoDynamicCoordinator *coordinator,
                                        uint64_t now_us,
                                        uint8_t safety_permissive)
{
  uint8_t axis;
  if ((coordinator == NULL) || (coordinator->initialized == 0U)) return;
  if (safety_permissive == 0U) {
    NucleoDynamicCoordinator_SafetyLoss(coordinator);
    return;
  }
  for (axis = 0U; axis < NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT; ++axis) {
    if ((coordinator->active_mask & (1U << axis)) != 0U) {
      NucleoDynamicRuntime_Heartbeat(&coordinator->axes[axis], now_us, 1U);
    }
  }
}

void NucleoDynamicCoordinator_ControlTick(NucleoDynamicCoordinator *coordinator,
                                          uint64_t now_us)
{
  uint8_t axis;
  if ((coordinator == NULL) || (coordinator->initialized == 0U)) return;
  for (axis = 0U; axis < NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT; ++axis) {
    if ((coordinator->active_mask & (1U << axis)) != 0U) {
      NucleoDynamicRuntime_ControlTick(&coordinator->axes[axis], now_us);
      if (coordinator->axes[axis].fault != NUCLEO_DYNAMIC_FAULT_NONE) {
        NucleoDynamicCoordinator_StopAll(coordinator);
        return;
      }
      if ((coordinator->axes[axis].planner.state == NUCLEO_DYNAMIC_COMPLETE) ||
          (coordinator->axes[axis].planner.state == NUCLEO_DYNAMIC_STOPPED)) {
        coordinator->active_mask &= (uint8_t)~(1U << axis);
      }
    }
  }
}

uint8_t NucleoDynamicCoordinator_OnEmittedPulse(void *context, uint8_t axis)
{
  NucleoDynamicCoordinator *coordinator = (NucleoDynamicCoordinator *)context;
  uint8_t keep_running;
  if ((coordinator == NULL) || (axis >= NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT) ||
      ((coordinator->active_mask & (1U << axis)) == 0U)) return 0U;
  keep_running = NucleoDynamicRuntime_OnEmittedPulse(
      &coordinator->axes[axis], axis);
  if (keep_running == 0U) {
    if (coordinator->axes[axis].planner.state == NUCLEO_DYNAMIC_COMPLETE) {
      coordinator->active_mask &= (uint8_t)~(1U << axis);
    } else {
      NucleoDynamicCoordinator_StopAll(coordinator);
    }
  }
  return keep_running;
}

void NucleoDynamicCoordinator_StopAll(NucleoDynamicCoordinator *coordinator)
{
  uint8_t axis;
  if ((coordinator == NULL) || (coordinator->initialized == 0U)) return;
  for (axis = 0U; axis < NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT; ++axis) {
    if ((coordinator->active_mask & (1U << axis)) != 0U) {
      NucleoDynamicRuntime_Stop(&coordinator->axes[axis]);
    }
  }
  coordinator->active_mask = 0U;
}

void NucleoDynamicCoordinator_ControlledStopAll(
    NucleoDynamicCoordinator *coordinator)
{
  uint8_t axis;
  if ((coordinator == NULL) || (coordinator->initialized == 0U)) return;
  for (axis = 0U; axis < NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT; ++axis) {
    if ((coordinator->active_mask & (1U << axis)) != 0U) {
      NucleoDynamicRuntime_ControlledStop(&coordinator->axes[axis]);
    }
  }
}

void NucleoDynamicCoordinator_DisarmAll(NucleoDynamicCoordinator *coordinator)
{
  uint8_t axis;
  if ((coordinator == NULL) || (coordinator->initialized == 0U)) return;
  for (axis = 0U; axis < NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT; ++axis) {
    if (coordinator->axes[axis].armed != 0U) {
      NucleoDynamicRuntime_Disarm(&coordinator->axes[axis]);
    }
  }
  coordinator->active_mask = 0U;
}

void NucleoDynamicCoordinator_SafetyLoss(NucleoDynamicCoordinator *coordinator)
{
  uint8_t axis;
  if ((coordinator == NULL) || (coordinator->initialized == 0U)) return;
  for (axis = 0U; axis < NUCLEO_DYNAMIC_COORDINATED_AXIS_COUNT; ++axis) {
    if ((coordinator->active_mask & (1U << axis)) != 0U) {
      NucleoDynamicRuntime_SafetyLoss(&coordinator->axes[axis]);
    }
  }
  coordinator->active_mask = 0U;
}
