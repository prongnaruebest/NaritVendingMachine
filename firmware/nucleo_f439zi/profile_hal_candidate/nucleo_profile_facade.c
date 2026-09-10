#include "nucleo_profile_facade.h"

#include <stddef.h>
#include <string.h>

static uint8_t pulse_completed(void *context, uint8_t axis)
{
  NucleoProfileFacade *facade = (NucleoProfileFacade *)context;
  return NucleoPulseScheduler_OnPulse(&facade->scheduler, axis);
}

static void disable_all(void *context)
{
  NucleoProfileFacade *facade = (NucleoProfileFacade *)context;
  NucleoProfileHalPort_DisableAll(&facade->hal_port);
}

uint8_t NucleoProfileFacade_Init(
    NucleoProfileFacade *facade, TIM_HandleTypeDef *tim1,
    GPIO_TypeDef *x_port, uint16_t x_pin, GPIO_TypeDef *y_port,
    uint16_t y_pin, uint32_t timer_tick_hz)
{
  NucleoProfileExecutorHooks executor_hooks;
  NucleoPulseSchedulerHooks scheduler_hooks;
  if (facade == NULL) return 0U;
  memset(facade, 0, sizeof(*facade));
  NucleoProfileBuffer_Init(&facade->buffer);
  NucleoSensorStop_Init(&facade->sensor_stop);
  executor_hooks.disable_all = disable_all;
  executor_hooks.phase_changed = NULL;
  executor_hooks.context = facade;
  NucleoProfileExecutor_Init(&facade->executor, executor_hooks);
  scheduler_hooks.set_rate = NucleoProfileHalPort_SetRateHook;
  scheduler_hooks.disable_axis = NucleoProfileHalPort_DisableAxisHook;
  scheduler_hooks.context = &facade->hal_port;
  NucleoPulseScheduler_Init(&facade->scheduler, &facade->executor,
                            scheduler_hooks);
  if (NucleoProfileHalPort_Init(&facade->hal_port, tim1, x_port, x_pin,
                                y_port, y_pin, timer_tick_hz,
                                pulse_completed, facade) == 0U) return 0U;
  facade->initialized = 1U;
  return 1U;
}

uint32_t NucleoProfileFacade_AdvertisedProtocol(void)
{
  return NUCLEO_XY_PROFILE_FEATURE_ENABLED ? 4U : 3U;
}

uint8_t NucleoProfileFacade_FeatureEnabled(void)
{
  return NUCLEO_XY_PROFILE_FEATURE_ENABLED ? 1U : 0U;
}

NucleoProfileResult NucleoProfileFacade_StageLine(
    NucleoProfileFacade *facade, const char *line)
{
  NucleoProfileFrame frame;
  NucleoProfileResult result;
  if ((NUCLEO_XY_PROFILE_FEATURE_ENABLED == 0) || (facade == NULL) ||
      (facade->initialized == 0U)) return NUCLEO_PROFILE_ERR_STATE;
  result = NucleoProfile_ParseLine(line, &frame);
  if (result != NUCLEO_PROFILE_OK) return result;
  return NucleoProfileBuffer_Stage(&facade->buffer, &frame);
}

NucleoProfileResult NucleoProfileFacade_Start(
    NucleoProfileFacade *facade, const char *command_id,
    uint64_t now_us, uint8_t safety_permissive)
{
  uint32_t index;
  NucleoProfileResult result;
  if ((NUCLEO_XY_PROFILE_FEATURE_ENABLED == 0) || (facade == NULL) ||
      (facade->initialized == 0U) || (command_id == NULL)) {
    return NUCLEO_PROFILE_ERR_STATE;
  }
  if (strcmp(facade->buffer.command_id, command_id) != 0) {
    return NUCLEO_PROFILE_ERR_COMMAND;
  }
  for (index = 0U; index < facade->buffer.count; index++) {
    if (facade->buffer.frames[index].sensor_terminated != 0U) {
      return NUCLEO_PROFILE_ERR_STATE;
    }
  }
  result = NucleoProfileExecutor_Start(&facade->executor, &facade->buffer,
                                       now_us, safety_permissive);
  if (result != NUCLEO_PROFILE_OK) return result;
  result = NucleoPulseScheduler_Start(&facade->scheduler);
  if (result != NUCLEO_PROFILE_OK) {
    NucleoProfileFacade_SafetyStop(facade);
  }
  return result;
}

NucleoProfileResult NucleoProfileFacade_StartSensor(
    NucleoProfileFacade *facade, const char *command_id,
    uint64_t now_us, uint8_t safety_permissive,
    uint8_t x_sensor_active, uint8_t y_sensor_active)
{
  uint32_t index;
  NucleoProfileResult result;
  if ((NUCLEO_XY_PROFILE_FEATURE_ENABLED == 0) || (facade == NULL) ||
      (facade->initialized == 0U) || (command_id == NULL) ||
      (safety_permissive == 0U)) return NUCLEO_PROFILE_ERR_STATE;
  for (index = 0U; index < facade->buffer.count; index++) {
    NucleoProfileFrame *frame = &facade->buffer.frames[index];
    uint8_t sensor_active;
    NucleoSensorStopResult sensor_result;
    if (frame->sensor_terminated == 0U) return NUCLEO_PROFILE_ERR_FORMAT;
    sensor_active = (frame->axis == 0U) ? x_sensor_active : y_sensor_active;
    sensor_result = NucleoSensorStop_Start(
        &facade->sensor_stop, frame->axis,
        (NucleoTerminationSensor)frame->termination_sensor,
        (NucleoSensorStopMode)frame->sensor_stop_mode, now_us,
        frame->sensor_watchdog_us, sensor_active);
    if (sensor_result != NUCLEO_SENSOR_RESULT_OK) {
      NucleoProfileFacade_SafetyStop(facade);
      return (sensor_result == NUCLEO_SENSOR_RESULT_ERR_STUCK)
          ? NUCLEO_PROFILE_ERR_RANGE : NUCLEO_PROFILE_ERR_STATE;
    }
  }
  if (strcmp(facade->buffer.command_id, command_id) != 0) {
    NucleoProfileFacade_SafetyStop(facade);
    return NUCLEO_PROFILE_ERR_COMMAND;
  }
  result = NucleoProfileExecutor_Start(&facade->executor, &facade->buffer,
                                       now_us, safety_permissive);
  if (result == NUCLEO_PROFILE_OK) {
    result = NucleoPulseScheduler_Start(&facade->scheduler);
  }
  if (result != NUCLEO_PROFILE_OK) NucleoProfileFacade_SafetyStop(facade);
  return result;
}

void NucleoProfileFacade_Heartbeat(NucleoProfileFacade *facade,
                                   uint64_t now_us,
                                   uint8_t safety_permissive)
{
  if ((facade == NULL) || (facade->initialized == 0U)) return;
  NucleoProfileExecutor_Heartbeat(&facade->executor, now_us,
                              safety_permissive);
  if (facade->executor.running == 0U) {
    NucleoProfileHalPort_DisableAll(&facade->hal_port);
  }
}

NucleoProfileState NucleoProfileFacade_Poll(NucleoProfileFacade *facade,
                                            uint64_t now_us,
                                            uint8_t safety_permissive)
{
  NucleoProfileState state;
  if ((facade == NULL) || (facade->initialized == 0U)) {
    return NUCLEO_PROFILE_EMPTY;
  }
  state = NucleoProfileExecutor_Tick(&facade->executor, now_us,
                                     safety_permissive);
  if (state == NUCLEO_PROFILE_RUNNING) {
    NucleoPulseScheduler_ControlTick(&facade->scheduler, now_us);
  } else if (state == NUCLEO_PROFILE_SAFETY_STOP) {
    NucleoProfileHalPort_DisableAll(&facade->hal_port);
  }
  return state;
}

NucleoProfileState NucleoProfileFacade_PollSensors(
    NucleoProfileFacade *facade, uint64_t now_us,
    uint8_t safety_permissive, uint8_t x_sensor_active,
    uint8_t y_sensor_active)
{
  uint32_t events;
  if ((facade == NULL) || (facade->initialized == 0U)) {
    return NUCLEO_PROFILE_EMPTY;
  }
  events = NucleoSensorStop_Tick(&facade->sensor_stop, now_us,
      safety_permissive, x_sensor_active, y_sensor_active);
  if ((events & (NUCLEO_SENSOR_EVENT_GLOBAL_SAFETY |
                 NUCLEO_SENSOR_EVENT_X_WATCHDOG |
                 NUCLEO_SENSOR_EVENT_Y_WATCHDOG)) != 0U) {
    NucleoProfileFacade_SafetyStop(facade);
    return NUCLEO_PROFILE_SAFETY_STOP;
  }
  if ((events & (NUCLEO_SENSOR_EVENT_X_CONTROLLED |
                 NUCLEO_SENSOR_EVENT_X_IMMEDIATE)) != 0U) {
    NucleoPulseScheduler_StopAxis(&facade->scheduler, 0U);
  }
  if ((events & (NUCLEO_SENSOR_EVENT_Y_CONTROLLED |
                 NUCLEO_SENSOR_EVENT_Y_IMMEDIATE)) != 0U) {
    NucleoPulseScheduler_StopAxis(&facade->scheduler, 1U);
  }
  return NucleoProfileFacade_Poll(facade, now_us, safety_permissive);
}

void NucleoProfileFacade_SafetyStop(NucleoProfileFacade *facade)
{
  if (facade == NULL) return;
  (void)NucleoSensorStop_Tick(&facade->sensor_stop, 0ULL, 0U, 0U, 0U);
  NucleoPulseScheduler_SafetyStop(&facade->scheduler);
  NucleoProfileHalPort_DisableAll(&facade->hal_port);
}

void NucleoProfileFacade_Reset(NucleoProfileFacade *facade)
{
  NucleoPulseSchedulerHooks hooks;
  if ((facade == NULL) || (facade->initialized == 0U)) return;
  hooks = facade->scheduler.hooks;
  NucleoProfileFacade_SafetyStop(facade);
  NucleoProfileBuffer_Init(&facade->buffer);
  NucleoSensorStop_Reset(&facade->sensor_stop);
  NucleoPulseScheduler_Init(&facade->scheduler, &facade->executor, hooks);
}
