#include "nucleo_g491_control_timer.h"

#include <assert.h>
#include <stdio.h>

TIM_TypeDef host_tim6;
RCC_TypeDef host_rcc;

static NucleoG491ControlTimer *active_timer;
static unsigned int tick_count;
static int start_result;

uint32_t HAL_RCC_GetPCLK1Freq(void) { return 170000000U; }
int HAL_TIM_Base_Init(TIM_HandleTypeDef *timer)
{
  active_timer = (NucleoG491ControlTimer *)timer;
  return HAL_OK;
}
int HAL_TIM_Base_Start_IT(TIM_HandleTypeDef *timer)
{
  /* Reproduce the hardware race: UIF can enter the ISR before Start_IT
   * returns to NucleoG491ControlTimer_Start. */
  timer->Instance->flag = 1U;
  timer->Instance->it_source = 1U;
  NucleoG491ControlTimer_IRQHandler(active_timer);
  return start_result;
}
int HAL_TIM_Base_Stop_IT(TIM_HandleTypeDef *timer)
{
  timer->Instance->it_source = 0U;
  return HAL_OK;
}
void HAL_NVIC_SetPriority(uint32_t irq, uint32_t priority, uint32_t subpriority)
{
  (void)irq; (void)priority; (void)subpriority;
}
void HAL_NVIC_EnableIRQ(uint32_t irq) { (void)irq; }

static void control_tick(void *context)
{
  ++(*(unsigned int *)context);
}

int main(void)
{
  NucleoG491ControlTimer timer;
  NucleoG491ControlTimer failed_timer;

  assert(NucleoG491ControlTimer_Init(&timer, control_tick, &tick_count) == 1U);
  assert(NucleoG491ControlTimer_Start(&timer) == 1U);
  assert(timer.running == 1U);
  assert(tick_count == 1U);
  assert(host_tim6.flag == 0U);
  NucleoG491ControlTimer_Stop(&timer);
  assert(timer.running == 0U);

  start_result = 1;
  assert(NucleoG491ControlTimer_Init(&failed_timer, control_tick, &tick_count) == 1U);
  assert(NucleoG491ControlTimer_Start(&failed_timer) == 0U);
  assert(failed_timer.running == 0U);

  puts("G491RE control timer host tests passed");
  return 0;
}
