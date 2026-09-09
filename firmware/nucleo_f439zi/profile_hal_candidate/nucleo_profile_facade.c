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
  NucleoProfileResult result;
  if ((NUCLEO_XY_PROFILE_FEATURE_ENABLED == 0) || (facade == NULL) ||
      (facade->initialized == 0U) || (command_id == NULL)) {
    return NUCLEO_PROFILE_ERR_STATE;
  }
  if (strcmp(facade->buffer.command_id, command_id) != 0) {
    return NUCLEO_PROFILE_ERR_COMMAND;
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

void NucleoProfileFacade_SafetyStop(NucleoProfileFacade *facade)
{
  if (facade == NULL) return;
  NucleoPulseScheduler_SafetyStop(&facade->scheduler);
  NucleoProfileHalPort_DisableAll(&facade->hal_port);
}
