#include "nucleo_profile_hal_port.h"

#include <stddef.h>
#include <string.h>

#define FIRST_COMPARE_DELAY_TICKS 20U

static uint8_t apply_half_period(void *context, uint8_t axis,
                                 uint32_t half_period_ticks)
{
  NucleoProfileHalPort *port = (NucleoProfileHalPort *)context;
  uint32_t primask;
  if ((port == NULL) || (axis > 1U) || (half_period_ticks == 0U)) return 0U;
  primask = __get_PRIMASK();
  __disable_irq();
  port->half_period_ticks[axis] = half_period_ticks;
  if (primask == 0U) __enable_irq();
  return 1U;
}

static void pulse_as_gpio_low(NucleoProfileHalPort *port, uint8_t axis)
{
  GPIO_InitTypeDef gpio;
  memset(&gpio, 0, sizeof(gpio));
  (void)HAL_TIM_OC_Stop_IT(port->timer, port->channels[axis]);
  gpio.Pin = port->pulse_pins[axis];
  gpio.Mode = GPIO_MODE_OUTPUT_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(port->pulse_ports[axis], &gpio);
  HAL_GPIO_WritePin(port->pulse_ports[axis], port->pulse_pins[axis],
                    GPIO_PIN_RESET);
  port->output_high[axis] = 0U;
}

static void enable_channel(void *context, uint8_t axis)
{
  NucleoProfileHalPort *port = (NucleoProfileHalPort *)context;
  GPIO_InitTypeDef gpio;
  memset(&gpio, 0, sizeof(gpio));
  if ((port == NULL) || (axis > 1U) || (port->half_period_ticks[axis] == 0U)) return;
  HAL_GPIO_WritePin(port->pulse_ports[axis], port->pulse_pins[axis],
                    GPIO_PIN_RESET);
  gpio.Pin = port->pulse_pins[axis];
  gpio.Mode = GPIO_MODE_AF_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_HIGH;
  gpio.Alternate = port->pulse_alternate;
  HAL_GPIO_Init(port->pulse_ports[axis], &gpio);
  __HAL_TIM_SET_COMPARE(port->timer, port->channels[axis],
                        __HAL_TIM_GET_COUNTER(port->timer) +
                            FIRST_COMPARE_DELAY_TICKS);
  port->output_high[axis] = 0U;
  (void)HAL_TIM_OC_Start_IT(port->timer, port->channels[axis]);
}

static void disable_channel(void *context, uint8_t axis)
{
  NucleoProfileHalPort *port = (NucleoProfileHalPort *)context;
  if ((port == NULL) || (axis > 1U)) return;
  pulse_as_gpio_low(port, axis);
}

uint8_t NucleoProfileHalPort_Init(
    NucleoProfileHalPort *port, TIM_HandleTypeDef *tim1,
    GPIO_TypeDef *x_port, uint16_t x_pin, GPIO_TypeDef *y_port,
    uint16_t y_pin, uint32_t timer_tick_hz,
    NucleoProfilePulseFn pulse_completed, void *pulse_context)
{
  NucleoComparePort compare_port;
  if ((port == NULL) || (tim1 == NULL) || (x_port == NULL) ||
      (y_port == NULL) || (pulse_completed == NULL)) return 0U;
  memset(port, 0, sizeof(*port));
  port->timer = tim1;
  port->channels[0] = TIM_CHANNEL_1;
  port->channels[1] = TIM_CHANNEL_2;
  port->pulse_ports[0] = x_port;
  port->pulse_ports[1] = y_port;
  port->pulse_pins[0] = x_pin;
  port->pulse_pins[1] = y_pin;
  port->pulse_alternate = GPIO_AF1_TIM1;
  port->pulse_completed = pulse_completed;
  port->pulse_context = pulse_context;
  compare_port.apply_half_period_atomic = apply_half_period;
  compare_port.enable_channel = enable_channel;
  compare_port.disable_channel = disable_channel;
  compare_port.context = port;
  return NucleoCompareAdapter_Init(&port->compare_adapter, timer_tick_hz,
                                   compare_port);
}

void NucleoProfileHalPort_OnCompare(NucleoProfileHalPort *port,
                                    uint8_t axis)
{
  uint32_t half_period;
  if ((port == NULL) || (axis > 1U)) return;
  half_period = port->half_period_ticks[axis];
  if ((half_period == 0U) ||
      (port->compare_adapter.enabled[axis] == 0U)) return;
  __HAL_TIM_SET_COMPARE(port->timer, port->channels[axis],
                        __HAL_TIM_GET_COMPARE(port->timer,
                                              port->channels[axis]) +
                            half_period);
  port->output_high[axis] ^= 1U;
  if ((port->output_high[axis] == 0U) &&
      (port->pulse_completed(port->pulse_context, axis) == 0U)) {
    NucleoCompareAdapter_DisableAxis(&port->compare_adapter, axis);
  }
}

void NucleoProfileHalPort_DisableAll(NucleoProfileHalPort *port)
{
  if (port == NULL) return;
  NucleoCompareAdapter_DisableAll(&port->compare_adapter);
}
