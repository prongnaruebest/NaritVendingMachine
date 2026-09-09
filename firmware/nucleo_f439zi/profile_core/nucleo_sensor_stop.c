#include "nucleo_sensor_stop.h"

#include <stddef.h>
#include <string.h>

static uint8_t sensor_matches_axis(uint8_t axis,
                                   NucleoTerminationSensor sensor)
{
  if (axis == 0U) {
    return (sensor == NUCLEO_SENSOR_X_MIN) ||
           (sensor == NUCLEO_SENSOR_X_MAX);
  }
  if (axis == 1U) {
    return (sensor == NUCLEO_SENSOR_Y_MIN) ||
           (sensor == NUCLEO_SENSOR_Y_MAX);
  }
  return 0U;
}

void NucleoSensorStop_Init(NucleoSensorStopSupervisor *supervisor)
{
  if (supervisor == NULL) return;
  memset(supervisor, 0, sizeof(*supervisor));
  supervisor->axes[0].state = NUCLEO_SENSOR_IDLE;
  supervisor->axes[1].state = NUCLEO_SENSOR_IDLE;
}

NucleoSensorStopResult NucleoSensorStop_Start(
    NucleoSensorStopSupervisor *supervisor, uint8_t axis,
    NucleoTerminationSensor sensor, NucleoSensorStopMode stop_mode,
    uint64_t now_us, uint64_t watchdog_us, uint8_t sensor_active)
{
  NucleoSensorStopChannel *channel;
  if ((supervisor == NULL) || (axis > 1U)) {
    return NUCLEO_SENSOR_RESULT_ERR_AXIS;
  }
  if (supervisor->safety_latched != 0U) {
    return NUCLEO_SENSOR_RESULT_ERR_STATE;
  }
  if (!sensor_matches_axis(axis, sensor)) {
    return NUCLEO_SENSOR_RESULT_ERR_SENSOR;
  }
  if ((stop_mode != NUCLEO_SENSOR_STOP_CONTROLLED) &&
      (stop_mode != NUCLEO_SENSOR_STOP_IMMEDIATE)) {
    return NUCLEO_SENSOR_RESULT_ERR_RANGE;
  }
  if ((watchdog_us < NUCLEO_SENSOR_WATCHDOG_MIN_US) ||
      (watchdog_us > NUCLEO_SENSOR_WATCHDOG_MAX_US)) {
    return NUCLEO_SENSOR_RESULT_ERR_RANGE;
  }
  channel = &supervisor->axes[axis];
  if (channel->active != 0U) return NUCLEO_SENSOR_RESULT_ERR_BUSY;
  if (sensor_active != 0U) {
    channel->state = NUCLEO_SENSOR_STUCK_ACTIVE;
    return NUCLEO_SENSOR_RESULT_ERR_STUCK;
  }
  channel->active = 1U;
  channel->sensor = sensor;
  channel->stop_mode = stop_mode;
  channel->state = NUCLEO_SENSOR_SEARCHING;
  channel->started_at_us = now_us;
  channel->watchdog_us = watchdog_us;
  return NUCLEO_SENSOR_RESULT_OK;
}

static uint32_t axis_stop_event(uint8_t axis, NucleoSensorStopMode mode)
{
  if (axis == 0U) {
    return (mode == NUCLEO_SENSOR_STOP_IMMEDIATE)
               ? NUCLEO_SENSOR_EVENT_X_IMMEDIATE
               : NUCLEO_SENSOR_EVENT_X_CONTROLLED;
  }
  return (mode == NUCLEO_SENSOR_STOP_IMMEDIATE)
             ? NUCLEO_SENSOR_EVENT_Y_IMMEDIATE
             : NUCLEO_SENSOR_EVENT_Y_CONTROLLED;
}

uint32_t NucleoSensorStop_Tick(
    NucleoSensorStopSupervisor *supervisor, uint64_t now_us,
    uint8_t safety_permissive, uint8_t x_sensor_active,
    uint8_t y_sensor_active)
{
  uint8_t axis;
  uint8_t sensor_states[2];
  uint32_t events = NUCLEO_SENSOR_EVENT_NONE;
  if (supervisor == NULL) return NUCLEO_SENSOR_EVENT_GLOBAL_SAFETY;
  if (safety_permissive == 0U) {
    for (axis = 0U; axis < 2U; axis++) {
      if (supervisor->axes[axis].active != 0U) {
        supervisor->axes[axis].active = 0U;
        supervisor->axes[axis].state = NUCLEO_SENSOR_SAFETY_STOP;
      }
    }
    supervisor->safety_latched = 1U;
    return NUCLEO_SENSOR_EVENT_GLOBAL_SAFETY;
  }
  sensor_states[0] = x_sensor_active;
  sensor_states[1] = y_sensor_active;
  for (axis = 0U; axis < 2U; axis++) {
    NucleoSensorStopChannel *channel = &supervisor->axes[axis];
    if (channel->active == 0U) continue;
    if (sensor_states[axis] != 0U) {
      channel->active = 0U;
      channel->state = NUCLEO_SENSOR_FOUND;
      events |= axis_stop_event(axis, channel->stop_mode);
    } else if ((now_us - channel->started_at_us) >= channel->watchdog_us) {
      channel->active = 0U;
      channel->state = NUCLEO_SENSOR_WATCHDOG_TIMEOUT;
      events |= (axis == 0U) ? NUCLEO_SENSOR_EVENT_X_WATCHDOG
                             : NUCLEO_SENSOR_EVENT_Y_WATCHDOG;
    }
  }
  return events;
}

void NucleoSensorStop_Reset(NucleoSensorStopSupervisor *supervisor)
{
  NucleoSensorStop_Init(supervisor);
}
