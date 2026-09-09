#ifndef NUCLEO_PROFILE_HAL_PORT_H
#define NUCLEO_PROFILE_HAL_PORT_H

#include "nucleo_compare_adapter.h"
#include "stm32f4xx_hal.h"

#include <stdint.h>

typedef uint8_t (*NucleoProfilePulseFn)(void *context, uint8_t axis);

typedef struct {
  TIM_HandleTypeDef *timer;
  uint32_t channels[2];
  GPIO_TypeDef *pulse_ports[2];
  uint16_t pulse_pins[2];
  uint32_t pulse_alternate;
  volatile uint32_t half_period_ticks[2];
  volatile uint8_t output_high[2];
  NucleoProfilePulseFn pulse_completed;
  void *pulse_context;
  NucleoCompareAdapter compare_adapter;
} NucleoProfileHalPort;

uint8_t NucleoProfileHalPort_Init(
    NucleoProfileHalPort *port, TIM_HandleTypeDef *tim1,
    GPIO_TypeDef *x_port, uint16_t x_pin, GPIO_TypeDef *y_port,
    uint16_t y_pin, uint32_t timer_tick_hz,
    NucleoProfilePulseFn pulse_completed, void *pulse_context);
void NucleoProfileHalPort_OnCompare(NucleoProfileHalPort *port,
                                    uint8_t axis);
void NucleoProfileHalPort_DisableAll(NucleoProfileHalPort *port);

#endif
