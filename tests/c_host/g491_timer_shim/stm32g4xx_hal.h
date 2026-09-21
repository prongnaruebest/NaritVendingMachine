#ifndef STM32G4XX_HAL_H
#define STM32G4XX_HAL_H

#include <stdint.h>

typedef struct { uint32_t flag; uint32_t it_source; } TIM_TypeDef;
typedef struct {
  uint32_t Prescaler;
  uint32_t CounterMode;
  uint32_t Period;
  uint32_t AutoReloadPreload;
} TIM_Base_InitTypeDef;
typedef struct { TIM_TypeDef *Instance; TIM_Base_InitTypeDef Init; } TIM_HandleTypeDef;
typedef struct { uint32_t CFGR; } RCC_TypeDef;

extern TIM_TypeDef host_tim6;
extern RCC_TypeDef host_rcc;

#define TIM6 (&host_tim6)
#define RCC (&host_rcc)
#define RCC_CFGR_PPRE1 0x00000700U
#define RCC_HCLK_DIV1 0U
#define TIM_COUNTERMODE_UP 0U
#define TIM_AUTORELOAD_PRELOAD_DISABLE 0U
#define TIM6_DAC_IRQn 54U
#define TIM_FLAG_UPDATE 1U
#define TIM_IT_UPDATE 1U
#define RESET 0U
#define HAL_OK 0

uint32_t HAL_RCC_GetPCLK1Freq(void);
int HAL_TIM_Base_Init(TIM_HandleTypeDef *timer);
int HAL_TIM_Base_Start_IT(TIM_HandleTypeDef *timer);
int HAL_TIM_Base_Stop_IT(TIM_HandleTypeDef *timer);
void HAL_NVIC_SetPriority(uint32_t irq, uint32_t priority, uint32_t subpriority);
void HAL_NVIC_EnableIRQ(uint32_t irq);

#define __HAL_RCC_TIM6_CLK_ENABLE() ((void)0)
#define __HAL_TIM_GET_FLAG(timer, ignored) ((timer)->Instance->flag)
#define __HAL_TIM_GET_IT_SOURCE(timer, ignored) ((timer)->Instance->it_source)
#define __HAL_TIM_CLEAR_IT(timer, ignored) ((timer)->Instance->flag = 0U)

#endif
