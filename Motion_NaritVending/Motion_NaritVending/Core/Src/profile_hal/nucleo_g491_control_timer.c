#include "nucleo_g491_control_timer.h"

#include <stddef.h>
#include <string.h>

#define NUCLEO_G491_TIMER_COUNTER_HZ 1000000U
#define NUCLEO_G491_TIMER_PERIOD_TICKS \
  (NUCLEO_G491_TIMER_COUNTER_HZ / NUCLEO_G491_CONTROL_TIMER_HZ)

static uint32_t timer6_clock_hz(void)
{
  uint32_t clock_hz = HAL_RCC_GetPCLK1Freq();
  return ((RCC->CFGR & RCC_CFGR_PPRE1) == RCC_HCLK_DIV1)
             ? clock_hz
             : clock_hz * 2U;
}

uint8_t NucleoG491ControlTimer_Init(NucleoG491ControlTimer *control_timer,
                                    NucleoG491ControlTimerFn control_tick,
                                    void *context)
{
  uint32_t clock_hz;
  if ((control_timer == NULL) || (control_tick == NULL)) return 0U;
  memset(control_timer, 0, sizeof(*control_timer));
  control_timer->control_tick = control_tick;
  control_timer->context = context;
  if (NUCLEO_G491_PROFILE_RUNTIME_ENABLED == 0) return 0U;

  clock_hz = timer6_clock_hz();
  if ((clock_hz < NUCLEO_G491_TIMER_COUNTER_HZ) ||
      ((clock_hz % NUCLEO_G491_TIMER_COUNTER_HZ) != 0U)) return 0U;
  __HAL_RCC_TIM6_CLK_ENABLE();
  control_timer->timer.Instance = TIM6;
  control_timer->timer.Init.Prescaler =
      (clock_hz / NUCLEO_G491_TIMER_COUNTER_HZ) - 1U;
  control_timer->timer.Init.CounterMode = TIM_COUNTERMODE_UP;
  control_timer->timer.Init.Period = NUCLEO_G491_TIMER_PERIOD_TICKS - 1U;
  control_timer->timer.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&control_timer->timer) != HAL_OK) return 0U;
  HAL_NVIC_SetPriority(TIM6_DAC_IRQn, 4U, 0U);
  HAL_NVIC_EnableIRQ(TIM6_DAC_IRQn);
  control_timer->initialized = 1U;
  return 1U;
}

uint8_t NucleoG491ControlTimer_Start(NucleoG491ControlTimer *control_timer)
{
  if ((control_timer == NULL) || (control_timer->initialized == 0U) ||
      (control_timer->running != 0U)) return 0U;
  if (HAL_TIM_Base_Start_IT(&control_timer->timer) != HAL_OK) return 0U;
  control_timer->running = 1U;
  return 1U;
}

void NucleoG491ControlTimer_Stop(NucleoG491ControlTimer *control_timer)
{
  if ((control_timer == NULL) || (control_timer->initialized == 0U)) return;
  (void)HAL_TIM_Base_Stop_IT(&control_timer->timer);
  control_timer->running = 0U;
}

void NucleoG491ControlTimer_IRQHandler(
    NucleoG491ControlTimer *control_timer)
{
  if ((control_timer == NULL) || (control_timer->running == 0U)) return;
  if ((__HAL_TIM_GET_FLAG(&control_timer->timer, TIM_FLAG_UPDATE) != RESET) &&
      (__HAL_TIM_GET_IT_SOURCE(&control_timer->timer, TIM_IT_UPDATE) != RESET)) {
    __HAL_TIM_CLEAR_IT(&control_timer->timer, TIM_IT_UPDATE);
    control_timer->control_tick(control_timer->context);
  }
}
