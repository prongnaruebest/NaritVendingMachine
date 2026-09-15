#include "nucleo_dynamic_facade.h"

#include <stddef.h>
#include <string.h>

#define DYNAMIC_CONTROL_PERIOD_US 1000U
#define DYNAMIC_TERMINAL_RATE_MILLIHZ 5000U

static uint32_t conservative_whole_units(uint32_t milli_units)
{
  uint32_t whole = milli_units / 1000U;
  return whole == 0U ? 1U : whole;
}

static NucleoDynamicConfig runtime_config(
    const NucleoDynamicAxisProtocolConfig *wire)
{
  NucleoDynamicConfig result;
  memset(&result, 0, sizeof(result));
  result.kp.enabled = wire->kp_enabled;
  result.kp.kp_approach_milliper_s = wire->kp_approach_milliper_s;
  result.kp.max_velocity_hz = conservative_whole_units(
      wire->max_velocity_millihz);
  result.constraints.control_period_us = DYNAMIC_CONTROL_PERIOD_US;
  result.constraints.max_velocity_hz = conservative_whole_units(
      wire->max_velocity_millihz);
  result.constraints.max_acceleration_hz_s = conservative_whole_units(
      wire->max_acceleration_millihz_s);
  result.constraints.max_deceleration_hz_s = conservative_whole_units(
      wire->max_deceleration_millihz_s);
  result.constraints.max_jerk_hz_s2 = conservative_whole_units(
      wire->max_jerk_millihz_s2);
  result.terminal_max_rate_millihz = DYNAMIC_TERMINAL_RATE_MILLIHZ;
  return result;
}

static uint8_t rebuild_runtime(NucleoDynamicFacade *facade)
{
  NucleoDynamicConfig configs[NUCLEO_DYNAMIC_AXIS_COUNT];
  uint8_t axis;
  for (axis = 0U; axis < NUCLEO_DYNAMIC_AXIS_COUNT; ++axis) {
    if (facade->protocol.config[axis].valid == 0U) return 0U;
    configs[axis] = runtime_config(&facade->protocol.config[axis]);
  }
  facade->runtime_ready = NucleoDynamicCoordinator_Init(
      &facade->coordinator, configs, facade->hooks);
  facade->staged_mask = 0U;
  return facade->runtime_ready;
}

static void invalidate_all_positions(NucleoDynamicFacade *facade)
{
  uint8_t axis;
  if (facade == NULL) return;
  for (axis = 0U; axis < NUCLEO_DYNAMIC_AXIS_COUNT; ++axis) {
    facade->protocol.position_valid[axis] = 0U;
  }
  facade->staged_mask = 0U;
}

uint8_t NucleoDynamicFacade_Init(NucleoDynamicFacade *facade,
                                 NucleoDynamicRuntimeHooks hooks)
{
  if ((facade == NULL) || (hooks.set_rate == NULL) ||
      (hooks.disable_all == NULL)) return 0U;
  memset(facade, 0, sizeof(*facade));
  facade->hooks = hooks;
  NucleoDynamicProtocol_Init(&facade->protocol);
  facade->initialized = 1U;
  return 1U;
}

NucleoDynamicProtocolResult NucleoDynamicFacade_ApplyConfig(
    NucleoDynamicFacade *facade, const char *line, uint8_t armed)
{
  NucleoDynamicProtocolResult result;
  if ((facade == NULL) || (facade->initialized == 0U)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  }
  if ((armed != 0U) || (facade->coordinator.active_mask != 0U)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  }
  result = NucleoDynamicProtocol_ApplyConfig(&facade->protocol, line, 0U);
  if (result != NUCLEO_DYNAMIC_PROTOCOL_OK) return result;
  /* Runtime becomes ready only after both X and Y revisions are configured. */
  (void)rebuild_runtime(facade);
  return NUCLEO_DYNAMIC_PROTOCOL_OK;
}

NucleoDynamicProtocolResult NucleoDynamicFacade_SetPosition(
    NucleoDynamicFacade *facade, uint8_t axis,
    uint32_t estimated_position_pulses)
{
  if ((facade == NULL) || (facade->runtime_ready == 0U) ||
      (facade->coordinator.active_mask != 0U)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  }
  return NucleoDynamicProtocol_SetPosition(
      &facade->protocol, axis, estimated_position_pulses);
}

NucleoDynamicProtocolResult NucleoDynamicFacade_ApplyPosition(
    NucleoDynamicFacade *facade, const char *line, uint8_t armed)
{
  if ((facade == NULL) || (facade->runtime_ready == 0U) ||
      (facade->coordinator.active_mask != 0U)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  }
  return NucleoDynamicProtocol_ApplyPosition(&facade->protocol, line, armed);
}

NucleoDynamicProtocolResult NucleoDynamicFacade_StageTarget(
    NucleoDynamicFacade *facade, const char *line)
{
  NucleoDynamicTarget target;
  NucleoDynamicProtocolResult result;
  uint8_t bit;
  if ((facade == NULL) || (facade->runtime_ready == 0U)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  }
  result = NucleoDynamicProtocol_ParseTarget(
      &facade->protocol, line,
      facade->coordinator.active_mask != 0U, &target);
  if (result != NUCLEO_DYNAMIC_PROTOCOL_OK) return result;
  bit = (uint8_t)(1U << target.axis);
  if ((facade->staged_mask != 0U) &&
      (strcmp(target.command_id,
              facade->staged[(facade->staged_mask & 1U) ? 0U : 1U].command_id) != 0)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_CONFLICT;
  }
  facade->staged[target.axis] = target;
  facade->staged_mask |= bit;
  return NUCLEO_DYNAMIC_PROTOCOL_OK;
}

NucleoDynamicProtocolResult NucleoDynamicFacade_Start(
    NucleoDynamicFacade *facade, const char *command_id, uint8_t axis_mask,
    uint64_t now_us, uint8_t safety_permissive)
{
  uint8_t directions[NUCLEO_DYNAMIC_AXIS_COUNT] = {0U, 0U};
  uint32_t distances[NUCLEO_DYNAMIC_AXIS_COUNT] = {0U, 0U};
  uint8_t moving_mask;
  uint8_t axis;
  if ((facade == NULL) || (command_id == NULL) ||
      (facade->runtime_ready == 0U) || (axis_mask == 0U) ||
      (axis_mask > 3U) || (safety_permissive == 0U) ||
      (facade->coordinator.active_mask != 0U) ||
      ((facade->staged_mask & axis_mask) != axis_mask)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  }
  moving_mask = axis_mask;
  for (axis = 0U; axis < NUCLEO_DYNAMIC_AXIS_COUNT; ++axis) {
    if ((axis_mask & (1U << axis)) != 0U) {
      if (strcmp(facade->staged[axis].command_id, command_id) != 0) {
        return NUCLEO_DYNAMIC_PROTOCOL_ERR_CONFLICT;
      }
      directions[axis] = facade->staged[axis].direction;
      distances[axis] = facade->staged[axis].distance_pulses;
      if (distances[axis] == 0U) moving_mask &= (uint8_t)~(1U << axis);
    }
  }
  if ((moving_mask != 0U) &&
      (NucleoDynamicCoordinator_Start(&facade->coordinator, moving_mask,
                                      directions, distances, now_us, 1U) == 0U)) {
    return NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE;
  }
  /* Commit no-op axes only after every moving axis starts successfully. */
  for (axis = 0U; axis < NUCLEO_DYNAMIC_AXIS_COUNT; ++axis) {
    if (((axis_mask & (1U << axis)) != 0U) && (distances[axis] == 0U)) {
      NucleoDynamicProtocol_CommitTarget(&facade->protocol,
                                         &facade->staged[axis]);
    }
  }
  facade->staged_mask = moving_mask;
  return NUCLEO_DYNAMIC_PROTOCOL_OK;
}

NucleoDynamicProtocolResult NucleoDynamicFacade_StartLine(
    NucleoDynamicFacade *facade, const char *line, uint64_t now_us,
    uint8_t safety_permissive)
{
  NucleoDynamicStart start;
  NucleoDynamicProtocolResult result =
      NucleoDynamicProtocol_ParseStart(line, &start);
  if (result != NUCLEO_DYNAMIC_PROTOCOL_OK) return result;
  return NucleoDynamicFacade_Start(facade, start.command_id, start.axis_mask,
                                   now_us, safety_permissive);
}

void NucleoDynamicFacade_Heartbeat(NucleoDynamicFacade *facade,
                                   uint64_t now_us,
                                   uint8_t safety_permissive)
{
  if ((facade != NULL) && (facade->runtime_ready != 0U)) {
    NucleoDynamicCoordinator_Heartbeat(&facade->coordinator, now_us,
                                       safety_permissive);
    if (safety_permissive == 0U) invalidate_all_positions(facade);
  }
}

void NucleoDynamicFacade_ControlTick(NucleoDynamicFacade *facade,
                                     uint64_t now_us)
{
  uint8_t before;
  uint8_t axis;
  if ((facade == NULL) || (facade->runtime_ready == 0U)) return;
  before = facade->coordinator.active_mask;
  NucleoDynamicCoordinator_ControlTick(&facade->coordinator, now_us);
  if ((before != 0U) && (facade->coordinator.active_mask == 0U)) {
    for (axis = 0U; axis < NUCLEO_DYNAMIC_AXIS_COUNT; ++axis) {
      if (facade->coordinator.axes[axis].fault != NUCLEO_DYNAMIC_FAULT_NONE) {
        invalidate_all_positions(facade);
        break;
      }
    }
  }
}

uint8_t NucleoDynamicFacade_OnEmittedPulse(void *context, uint8_t axis)
{
  NucleoDynamicFacade *facade = (NucleoDynamicFacade *)context;
  NucleoDynamicTarget *target;
  uint8_t keep_running;
  if ((facade == NULL) || (axis >= NUCLEO_DYNAMIC_AXIS_COUNT) ||
      ((facade->staged_mask & (1U << axis)) == 0U) ||
      (facade->protocol.position_valid[axis] == 0U)) return 0U;
  target = &facade->staged[axis];
  keep_running = NucleoDynamicCoordinator_OnEmittedPulse(
      &facade->coordinator, axis);
  if (target->direction != 0U) {
    ++facade->protocol.estimated_position_pulses[axis];
  } else if (facade->protocol.estimated_position_pulses[axis] > 0U) {
    --facade->protocol.estimated_position_pulses[axis];
  } else {
    invalidate_all_positions(facade);
    return 0U;
  }
  if (facade->coordinator.axes[axis].planner.state == NUCLEO_DYNAMIC_COMPLETE) {
    NucleoDynamicProtocol_CommitTarget(&facade->protocol, target);
    facade->staged_mask &= (uint8_t)~(1U << axis);
  } else if (facade->coordinator.axes[axis].fault != NUCLEO_DYNAMIC_FAULT_NONE) {
    invalidate_all_positions(facade);
  }
  return keep_running;
}

void NucleoDynamicFacade_Stop(NucleoDynamicFacade *facade)
{
  if (facade == NULL) return;
  NucleoDynamicCoordinator_StopAll(&facade->coordinator);
  invalidate_all_positions(facade);
}

void NucleoDynamicFacade_ControlledStop(NucleoDynamicFacade *facade)
{
  if (facade != NULL) {
    NucleoDynamicCoordinator_ControlledStopAll(&facade->coordinator);
  }
}

void NucleoDynamicFacade_Disarm(NucleoDynamicFacade *facade)
{
  if (facade == NULL) return;
  NucleoDynamicCoordinator_DisarmAll(&facade->coordinator);
  invalidate_all_positions(facade);
}
