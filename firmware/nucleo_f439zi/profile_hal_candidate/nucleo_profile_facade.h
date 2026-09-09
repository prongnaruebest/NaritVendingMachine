#ifndef NUCLEO_PROFILE_FACADE_H
#define NUCLEO_PROFILE_FACADE_H

#include "nucleo_profile_hal_port.h"
#include "nucleo_pulse_scheduler.h"

#ifndef NUCLEO_XY_PROFILE_FEATURE_ENABLED
#define NUCLEO_XY_PROFILE_FEATURE_ENABLED 0
#endif

typedef struct {
  NucleoProfileBuffer buffer;
  NucleoProfileExecutor executor;
  NucleoPulseScheduler scheduler;
  NucleoProfileHalPort hal_port;
  uint8_t initialized;
} NucleoProfileFacade;

uint8_t NucleoProfileFacade_Init(
    NucleoProfileFacade *facade, TIM_HandleTypeDef *tim1,
    GPIO_TypeDef *x_port, uint16_t x_pin, GPIO_TypeDef *y_port,
    uint16_t y_pin, uint32_t timer_tick_hz);
uint32_t NucleoProfileFacade_AdvertisedProtocol(void);
uint8_t NucleoProfileFacade_FeatureEnabled(void);
NucleoProfileResult NucleoProfileFacade_StageLine(
    NucleoProfileFacade *facade, const char *line);
NucleoProfileResult NucleoProfileFacade_Start(
    NucleoProfileFacade *facade, const char *command_id,
    uint64_t now_us, uint8_t safety_permissive);
void NucleoProfileFacade_Heartbeat(NucleoProfileFacade *facade,
                                   uint64_t now_us,
                                   uint8_t safety_permissive);
NucleoProfileState NucleoProfileFacade_Poll(NucleoProfileFacade *facade,
                                            uint64_t now_us,
                                            uint8_t safety_permissive);
void NucleoProfileFacade_SafetyStop(NucleoProfileFacade *facade);

#endif
