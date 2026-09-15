#ifndef NUCLEO_G491_PROFILE_HAL_H
#define NUCLEO_G491_PROFILE_HAL_H

#include "../profile_core/nucleo_compare_adapter.h"
#include "stm32g4xx_hal.h"

#include <stdint.h>

typedef uint8_t (*NucleoG491ProfilePulseFn)(void *context, uint8_t axis);

typedef struct {
  TIM_HandleTypeDef *tim1;
  uint32_t channels[NUCLEO_COMPARE_AXIS_COUNT];
  GPIO_TypeDef *pulse_ports[NUCLEO_COMPARE_AXIS_COUNT];
  uint16_t pulse_pins[NUCLEO_COMPARE_AXIS_COUNT];
  GPIO_TypeDef *direction_ports[NUCLEO_COMPARE_AXIS_COUNT];
  uint16_t direction_pins[NUCLEO_COMPARE_AXIS_COUNT];
  volatile uint32_t half_period_ticks[NUCLEO_COMPARE_AXIS_COUNT];
  volatile uint8_t output_high[NUCLEO_COMPARE_AXIS_COUNT];
  NucleoG491ProfilePulseFn pulse_completed;
  void *pulse_context;
  NucleoCompareAdapter compare_adapter;
} NucleoG491ProfileHal;

uint8_t NucleoG491ProfileHal_Init(
    NucleoG491ProfileHal *port, TIM_HandleTypeDef *tim1,
    GPIO_TypeDef *x_port, uint16_t x_pin, GPIO_TypeDef *y_port,
    uint16_t y_pin, GPIO_TypeDef *x_direction_port,
    uint16_t x_direction_pin, GPIO_TypeDef *y_direction_port,
    uint16_t y_direction_pin, uint32_t timer_tick_hz,
    NucleoG491ProfilePulseFn pulse_completed, void *pulse_context);
void NucleoG491ProfileHal_OnCompare(NucleoG491ProfileHal *port,
                                    uint8_t axis);
void NucleoG491ProfileHal_DisableAll(NucleoG491ProfileHal *port);
void NucleoG491ProfileHal_SetRateHook(void *context, uint8_t axis,
                                      uint32_t rate_millihz);
void NucleoG491ProfileHal_DisableAxisHook(void *context, uint8_t axis);
void NucleoG491ProfileHal_DisableAllHook(void *context);
uint8_t NucleoG491ProfileHal_PrepareDirectionHook(void *context,
                                                  uint8_t axis,
                                                  uint8_t direction);

#endif
