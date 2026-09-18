#include "nucleo_g491_profile_hal.h"

#include <stddef.h>
#include <string.h>

#define NUCLEO_G491_FIRST_COMPARE_DELAY_TICKS 20U
#define NUCLEO_G491_DIRECTION_SETUP_DELAY_MS 1U

static uint8_t apply_half_period(void *context, uint8_t axis,
                                 uint32_t half_period_ticks)
{
  NucleoG491ProfileHal *port = (NucleoG491ProfileHal *)context;
  uint32_t primask;
  if ((port == NULL) || (axis >= NUCLEO_COMPARE_AXIS_COUNT) ||
      (half_period_ticks == 0U)) return 0U;
  primask = __get_PRIMASK();
  __disable_irq();
  port->half_period_ticks[axis] = half_period_ticks;
  if (primask == 0U) __enable_irq();
  return 1U;
}

static void pulse_as_gpio_low(NucleoG491ProfileHal *port, uint8_t axis)
{
  GPIO_InitTypeDef gpio;
  memset(&gpio, 0, sizeof(gpio));
  (void)HAL_TIM_OC_Stop_IT(port->tim1, port->channels[axis]);
  gpio.Pin = port->pulse_pins[axis];
  gpio.Mode = GPIO_MODE_OUTPUT_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(port->pulse_ports[axis], &gpio);
  HAL_GPIO_WritePin(port->pulse_ports[axis], port->pulse_pins[axis],
                    GPIO_PIN_RESET);
  port->output_high[axis] = 0U;
}

static uint8_t enable_channel(void *context, uint8_t axis)
{
  NucleoG491ProfileHal *port = (NucleoG491ProfileHal *)context;
  GPIO_InitTypeDef gpio;
  if ((port == NULL) || (axis >= NUCLEO_COMPARE_AXIS_COUNT) ||
      (port->half_period_ticks[axis] == 0U)) return 0U;
  memset(&gpio, 0, sizeof(gpio));
  HAL_GPIO_WritePin(port->pulse_ports[axis], port->pulse_pins[axis],
                    GPIO_PIN_RESET);
  gpio.Pin = port->pulse_pins[axis];
  gpio.Mode = GPIO_MODE_AF_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_HIGH;
  gpio.Alternate = GPIO_AF6_TIM1;
  HAL_GPIO_Init(port->pulse_ports[axis], &gpio);
  __HAL_TIM_SET_COMPARE(port->tim1, port->channels[axis],
                        __HAL_TIM_GET_COUNTER(port->tim1) +
                            NUCLEO_G491_FIRST_COMPARE_DELAY_TICKS);
  port->output_high[axis] = 0U;
  (void)HAL_TIM_OC_Stop_IT(port->tim1, port->channels[axis]);
  if (HAL_TIM_OC_Start_IT(port->tim1, port->channels[axis]) != HAL_OK) {
    /* A failed OC start is a latched adapter fault; STEP remains GPIO-low. */
    pulse_as_gpio_low(port, axis);
    return 0U;
  }
  return 1U;
}

static void disable_channel(void *context, uint8_t axis)
{
  NucleoG491ProfileHal *port = (NucleoG491ProfileHal *)context;
  if ((port == NULL) || (axis >= NUCLEO_COMPARE_AXIS_COUNT)) return;
  pulse_as_gpio_low(port, axis);
}

uint8_t NucleoG491ProfileHal_Init(
    NucleoG491ProfileHal *port, TIM_HandleTypeDef *tim1,
    GPIO_TypeDef *x_port, uint16_t x_pin, GPIO_TypeDef *y_port,
    uint16_t y_pin, GPIO_TypeDef *x_direction_port,
    uint16_t x_direction_pin, GPIO_TypeDef *y_direction_port,
    uint16_t y_direction_pin, uint32_t timer_tick_hz,
    NucleoG491ProfilePulseFn pulse_completed, void *pulse_context)
{
  NucleoComparePort compare_port;
  if ((port == NULL) || (tim1 == NULL) || (x_port == NULL) ||
      (y_port == NULL) || (x_direction_port == NULL) ||
      (y_direction_port == NULL) || (pulse_completed == NULL)) return 0U;
  memset(port, 0, sizeof(*port));
  port->tim1 = tim1;
  port->channels[0] = TIM_CHANNEL_1;
  port->channels[1] = TIM_CHANNEL_2;
  port->pulse_ports[0] = x_port;
  port->pulse_ports[1] = y_port;
  port->pulse_pins[0] = x_pin;
  port->pulse_pins[1] = y_pin;
  port->direction_ports[0] = x_direction_port;
  port->direction_ports[1] = y_direction_port;
  port->direction_pins[0] = x_direction_pin;
  port->direction_pins[1] = y_direction_pin;
  port->pulse_completed = pulse_completed;
  port->pulse_context = pulse_context;
  compare_port.apply_half_period_atomic = apply_half_period;
  compare_port.enable_channel = enable_channel;
  compare_port.disable_channel = disable_channel;
  compare_port.context = port;
  return NucleoCompareAdapter_Init(&port->compare_adapter, timer_tick_hz,
                                   compare_port);
}

void NucleoG491ProfileHal_OnCompare(NucleoG491ProfileHal *port,
                                    uint8_t axis)
{
  uint32_t half_period_ticks;
  if ((port == NULL) || (axis >= NUCLEO_COMPARE_AXIS_COUNT)) return;
  half_period_ticks = port->half_period_ticks[axis];
  if ((half_period_ticks == 0U) ||
      (port->compare_adapter.enabled[axis] == 0U)) return;
  __HAL_TIM_SET_COMPARE(port->tim1, port->channels[axis],
                        __HAL_TIM_GET_COMPARE(port->tim1,
                                              port->channels[axis]) +
                            half_period_ticks);
  port->output_high[axis] ^= 1U;
  /* Count one emitted STEP on the falling edge, never when merely queued. */
  if ((port->output_high[axis] == 0U) &&
      (port->pulse_completed(port->pulse_context, axis) == 0U)) {
    NucleoCompareAdapter_DisableAxis(&port->compare_adapter, axis);
  }
}

void NucleoG491ProfileHal_DisableAll(NucleoG491ProfileHal *port)
{
  if (port == NULL) return;
  NucleoCompareAdapter_DisableAll(&port->compare_adapter);
}

void NucleoG491ProfileHal_SetRateHook(void *context, uint8_t axis,
                                      uint32_t rate_millihz)
{
  NucleoG491ProfileHal *port = (NucleoG491ProfileHal *)context;
  if ((port != NULL) &&
      (NucleoCompareAdapter_SetRate(&port->compare_adapter, axis,
                                    rate_millihz) == 0U)) {
    /* Invalid rates and HAL failures stop both shared TIM1 channels. */
    NucleoG491ProfileHal_DisableAll(port);
  }
}

void NucleoG491ProfileHal_DisableAxisHook(void *context, uint8_t axis)
{
  NucleoG491ProfileHal *port = (NucleoG491ProfileHal *)context;
  if (port != NULL) {
    NucleoCompareAdapter_DisableAxis(&port->compare_adapter, axis);
  }
}

void NucleoG491ProfileHal_DisableAllHook(void *context)
{
  NucleoG491ProfileHal_DisableAll((NucleoG491ProfileHal *)context);
}

uint8_t NucleoG491ProfileHal_PrepareDirectionHook(void *context,
                                                  uint8_t axis,
                                                  uint8_t direction)
{
  NucleoG491ProfileHal *port = (NucleoG491ProfileHal *)context;
  if ((port == NULL) || (axis >= NUCLEO_COMPARE_AXIS_COUNT) ||
      (direction > 1U)) return 0U;
  if (port->compare_adapter.enabled[axis] != 0U) return 0U;
  /* Direction polarity for Narit Vending Machine:
   *   direction 1U = positive displacement (+mm, target >= current) -> drives GPIO_PIN_RESET (LOW / forward)
   *   direction 0U = negative displacement (-mm, target < current)  -> drives GPIO_PIN_SET (HIGH / reverse)
   * This matches machine_config.iriv.json (forward_direction = 0, home_direction = 1)
   * and legacy NucleoMotion_StartMove behavior. */
  HAL_GPIO_WritePin(port->direction_ports[axis], port->direction_pins[axis],
                    direction != 0U ? GPIO_PIN_RESET : GPIO_PIN_SET);
  /* A bounded one-millisecond command-path delay exceeds the 5 us HBS860H
   * DIR setup requirement without introducing delay-based STEP generation. */
  HAL_Delay(NUCLEO_G491_DIRECTION_SETUP_DELAY_MS);
  return 1U;
}
