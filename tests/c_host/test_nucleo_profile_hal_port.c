#include "nucleo_profile_hal_port.h"

#include <assert.h>
#include <stdio.h>

static unsigned int starts[2];
static unsigned int stops[2];
static unsigned int completed[2];
static uint32_t primask;

uint32_t host_get_primask(void) { return primask; }
void host_disable_irq(void) { primask = 1U; }
void host_enable_irq(void) { primask = 0U; }
void host_set_compare(TIM_HandleTypeDef *timer, uint32_t channel, uint32_t value) { timer->Instance->compare[channel] = value; }
uint32_t host_get_compare(TIM_HandleTypeDef *timer, uint32_t channel) { return timer->Instance->compare[channel]; }
uint32_t host_get_counter(TIM_HandleTypeDef *timer) { return timer->Instance->counter; }
int HAL_TIM_OC_Start_IT(TIM_HandleTypeDef *timer, uint32_t channel) { (void)timer; starts[channel]++; return 0; }
int HAL_TIM_OC_Stop_IT(TIM_HandleTypeDef *timer, uint32_t channel) { (void)timer; stops[channel]++; return 0; }
void HAL_GPIO_Init(GPIO_TypeDef *port, GPIO_InitTypeDef *gpio) { (void)port; (void)gpio; }
void HAL_GPIO_WritePin(GPIO_TypeDef *port, uint16_t pin, uint32_t state) { (void)port; (void)pin; (void)state; }

static uint8_t pulse_complete(void *context, uint8_t axis)
{
  unsigned int *limit = (unsigned int *)context;
  completed[axis]++;
  return completed[axis] < limit[axis] ? 1U : 0U;
}

int main(void)
{
  TIM_TypeDef tim1_instance = {100U, {0U, 0U}};
  TIM_HandleTypeDef tim1 = {&tim1_instance};
  GPIO_TypeDef gpio_a = {0U};
  NucleoProfileHalPort port;
  unsigned int limits[2] = {2U, 3U};

  assert(NucleoProfileHalPort_Init(&port, &tim1, &gpio_a, 0x0100U,
                                   &gpio_a, 0x0200U, 1000000U,
                                   pulse_complete, limits) == 1U);
  assert(NucleoCompareAdapter_SetRate(&port.compare_adapter, 0U, 1000000U) == 1U);
  assert(NucleoCompareAdapter_SetRate(&port.compare_adapter, 1U, 2000000U) == 1U);
  assert(starts[0] == 1U && starts[1] == 1U);
  assert(tim1_instance.compare[0] == 120U && tim1_instance.compare[1] == 120U);

  NucleoProfileHalPort_OnCompare(&port, 0U);
  assert(tim1_instance.compare[0] == 620U);
  assert(completed[0] == 0U);
  NucleoProfileHalPort_OnCompare(&port, 0U);
  assert(completed[0] == 1U && stops[0] == 0U);
  NucleoProfileHalPort_OnCompare(&port, 0U);
  NucleoProfileHalPort_OnCompare(&port, 0U);
  assert(completed[0] == 2U && stops[0] == 1U);

  /* X completion never stops shared TIM1 channel Y. */
  assert(port.compare_adapter.enabled[1] == 1U && stops[1] == 0U);
  NucleoProfileHalPort_DisableAll(&port);
  assert(stops[1] == 1U);

  puts("nucleo_profile_hal_port host tests passed");
  return 0;
}
