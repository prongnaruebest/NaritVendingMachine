#ifndef NUCLEO_G491_CONTROL_TIMER_H
#define NUCLEO_G491_CONTROL_TIMER_H

#include "stm32g4xx_hal.h"
#include "nucleo_motion_features.h"

#include <stdint.h>

#define NUCLEO_G491_CONTROL_TIMER_HZ 1000U

typedef void (*NucleoG491ControlTimerFn)(void *context);

typedef struct {
  TIM_HandleTypeDef timer;
  NucleoG491ControlTimerFn control_tick;
  void *context;
  uint8_t initialized;
  uint8_t running;
} NucleoG491ControlTimer;

uint8_t NucleoG491ControlTimer_Init(NucleoG491ControlTimer *control_timer,
                                    NucleoG491ControlTimerFn control_tick,
                                    void *context);
uint8_t NucleoG491ControlTimer_Start(NucleoG491ControlTimer *control_timer);
void NucleoG491ControlTimer_Stop(NucleoG491ControlTimer *control_timer);
void NucleoG491ControlTimer_IRQHandler(
    NucleoG491ControlTimer *control_timer);

#endif
