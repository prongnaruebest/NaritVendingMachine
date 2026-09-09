#ifndef STM32F4XX_HAL_H
#define STM32F4XX_HAL_H

#include <stdint.h>

typedef struct { uint32_t counter; uint32_t compare[2]; } TIM_TypeDef;
typedef struct { TIM_TypeDef *Instance; } TIM_HandleTypeDef;
typedef struct { uint32_t marker; } GPIO_TypeDef;
typedef struct {
  uint32_t Pin;
  uint32_t Mode;
  uint32_t Pull;
  uint32_t Speed;
  uint32_t Alternate;
} GPIO_InitTypeDef;

#define TIM_CHANNEL_1 0U
#define TIM_CHANNEL_2 1U
#define GPIO_AF1_TIM1 1U
#define GPIO_MODE_OUTPUT_PP 1U
#define GPIO_MODE_AF_PP 2U
#define GPIO_NOPULL 0U
#define GPIO_SPEED_FREQ_LOW 0U
#define GPIO_SPEED_FREQ_HIGH 2U
#define GPIO_PIN_RESET 0U

uint32_t host_get_primask(void);
void host_disable_irq(void);
void host_enable_irq(void);
void host_set_compare(TIM_HandleTypeDef *timer, uint32_t channel, uint32_t value);
uint32_t host_get_compare(TIM_HandleTypeDef *timer, uint32_t channel);
uint32_t host_get_counter(TIM_HandleTypeDef *timer);
int HAL_TIM_OC_Start_IT(TIM_HandleTypeDef *timer, uint32_t channel);
int HAL_TIM_OC_Stop_IT(TIM_HandleTypeDef *timer, uint32_t channel);
void HAL_GPIO_Init(GPIO_TypeDef *port, GPIO_InitTypeDef *gpio);
void HAL_GPIO_WritePin(GPIO_TypeDef *port, uint16_t pin, uint32_t state);

#define __get_PRIMASK() host_get_primask()
#define __disable_irq() host_disable_irq()
#define __enable_irq() host_enable_irq()
#define __HAL_TIM_SET_COMPARE(timer, channel, value) host_set_compare((timer), (channel), (value))
#define __HAL_TIM_GET_COMPARE(timer, channel) host_get_compare((timer), (channel))
#define __HAL_TIM_GET_COUNTER(timer) host_get_counter((timer))

#endif
