#include "nucleo_motion.h"

#include "main.h"
#include "nucleo_motion_features.h"

#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
#include "profile_core/nucleo_dynamic_app.h"
#include "profile_hal/nucleo_g491_control_timer.h"
#include "profile_hal/nucleo_g491_profile_hal.h"
#endif

#include <string.h>

#define TIMER_TICK_HZ 1000000U
#define FIRST_COMPARE_DELAY_TICKS 20U
#define AXIS_COUNT 3U

typedef struct {
  volatile uint32_t toggles_remaining;
  uint32_t half_period_ticks;
  GPIO_TypeDef *pulse_port;
  uint16_t pulse_pin;
  uint8_t pulse_alternate;
  GPIO_TypeDef *dir_port;
  uint16_t dir_pin;
  TIM_HandleTypeDef *htim;
  uint32_t channel;
} StepperState;

static TIM_HandleTypeDef htim1_motion;
static TIM_HandleTypeDef htim2_motion;
static StepperState steppers[AXIS_COUNT];
static volatile uint8_t motion_armed;
static volatile uint8_t watchdog_healthy;
static volatile uint32_t last_heartbeat_ms;

#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
static NucleoDynamicApp dynamic_app;
static NucleoG491ProfileHal dynamic_profile_hal;
static volatile uint64_t dynamic_now_us;
static uint8_t dynamic_hal_ready;
#endif

static uint32_t timer_clock_hz(TIM_TypeDef *instance)
{
  if (instance == TIM1) {
    uint32_t clock_hz = HAL_RCC_GetPCLK2Freq();
    return ((RCC->CFGR & RCC_CFGR_PPRE2) == RCC_HCLK_DIV1)
               ? clock_hz
               : clock_hz * 2U;
  }

  {
    uint32_t clock_hz = HAL_RCC_GetPCLK1Freq();
    return ((RCC->CFGR & RCC_CFGR_PPRE1) == RCC_HCLK_DIV1)
               ? clock_hz
               : clock_hz * 2U;
  }
}

static void pulse_as_gpio_low(StepperState *stepper)
{
  GPIO_InitTypeDef gpio = {0};

  (void)HAL_TIM_OC_Stop_IT(stepper->htim, stepper->channel);
  gpio.Pin = stepper->pulse_pin;
  gpio.Mode = GPIO_MODE_OUTPUT_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(stepper->pulse_port, &gpio);
  HAL_GPIO_WritePin(stepper->pulse_port, stepper->pulse_pin, GPIO_PIN_RESET);
  stepper->toggles_remaining = 0U;
}

static void pulse_as_timer_output(StepperState *stepper)
{
  GPIO_InitTypeDef gpio = {0};

  HAL_GPIO_WritePin(stepper->pulse_port, stepper->pulse_pin, GPIO_PIN_RESET);
  gpio.Pin = stepper->pulse_pin;
  gpio.Mode = GPIO_MODE_AF_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_HIGH;
  gpio.Alternate = stepper->pulse_alternate;
  HAL_GPIO_Init(stepper->pulse_port, &gpio);
}

static void physical_stop_all(void)
{
  uint32_t axis;
  uint32_t primask = __get_PRIMASK();

  __disable_irq();
  for (axis = 0U; axis < AXIS_COUNT; ++axis) {
    pulse_as_gpio_low(&steppers[axis]);
  }
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if (dynamic_hal_ready != 0U) {
    NucleoG491ProfileHal_DisableAll(&dynamic_profile_hal);
  }
#endif
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2,
                    GPIO_PIN_RESET);
  if (primask == 0U) {
    __enable_irq();
  }
}

#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
static uint64_t dynamic_time_us(void)
{
  uint64_t now_us;
  uint32_t primask = __get_PRIMASK();
  __disable_irq();
  now_us = dynamic_now_us;
  if (primask == 0U) __enable_irq();
  return now_us;
}

static void dynamic_emergency_inhibit(void *context)
{
  (void)context;
  physical_stop_all();
}

static void dynamic_runtime_init(void)
{
  NucleoDynamicRuntimeHooks hooks;
  dynamic_hal_ready = NucleoG491ProfileHal_Init(
      &dynamic_profile_hal, &htim1_motion,
      GPIOA, GPIO_PIN_8, GPIOA, GPIO_PIN_9,
      GPIOB, GPIO_PIN_0, GPIOB, GPIO_PIN_1,
      TIMER_TICK_HZ, NucleoDynamicApp_OnEmittedPulse, &dynamic_app);
  if (dynamic_hal_ready == 0U) return;

  hooks.set_rate = NucleoG491ProfileHal_SetRateHook;
  hooks.disable_all = NucleoG491ProfileHal_DisableAllHook;
  hooks.context = &dynamic_profile_hal;
  hooks.prepare_direction = NucleoG491ProfileHal_PrepareDirectionHook;
  if (NucleoDynamicApp_Init(&dynamic_app, hooks, dynamic_emergency_inhibit,
                            NULL) == 0U) {
    physical_stop_all();
    dynamic_hal_ready = 0U;
    return;
  }
  {
    NucleoDynamicConfig configs[NUCLEO_DYNAMIC_AXIS_COUNT];
    uint8_t a;
    for (a = 0U; a < NUCLEO_DYNAMIC_AXIS_COUNT; ++a) {
      memset(&configs[a], 0, sizeof(configs[a]));
      configs[a].kp.enabled = 0U;
      configs[a].kp.kp_approach_milliper_s = 2500U;
      configs[a].kp.max_velocity_hz = NUCLEO_MOTION_MAX_SPEED_HZ;
      configs[a].constraints.control_period_us = 1000U;
      configs[a].constraints.max_velocity_hz = NUCLEO_MOTION_MAX_SPEED_HZ;
      configs[a].constraints.max_acceleration_hz_s = 20000U;
      configs[a].constraints.max_deceleration_hz_s = 20000U;
      configs[a].constraints.max_jerk_hz_s2 = 100000U;
      configs[a].terminal_max_rate_millihz = 5000U;
    }
    dynamic_app.facade.runtime_ready = NucleoDynamicCoordinator_Init(
        &dynamic_app.facade.coordinator, configs, dynamic_app.facade.hooks);
  }
  dynamic_now_us = (uint64_t)HAL_GetTick() * 1000ULL;
}
#endif

static void timer_init(TIM_HandleTypeDef *htim, TIM_TypeDef *instance,
                       uint32_t period)
{
  TIM_OC_InitTypeDef output_compare = {0};
  uint32_t clock_hz = timer_clock_hz(instance);

  htim->Instance = instance;
  htim->Init.Prescaler = (clock_hz / TIMER_TICK_HZ) - 1U;
  htim->Init.CounterMode = TIM_COUNTERMODE_UP;
  htim->Init.Period = period;
  htim->Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim->Init.RepetitionCounter = 0U;
  htim->Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_OC_Init(htim) != HAL_OK) {
    Error_Handler();
  }

  output_compare.OCMode = TIM_OCMODE_TOGGLE;
  output_compare.Pulse = 0U;
  output_compare.OCPolarity = TIM_OCPOLARITY_HIGH;
  output_compare.OCNPolarity = TIM_OCNPOLARITY_HIGH;
  output_compare.OCFastMode = TIM_OCFAST_DISABLE;
  output_compare.OCIdleState = TIM_OCIDLESTATE_RESET;
  output_compare.OCNIdleState = TIM_OCNIDLESTATE_RESET;
  if (HAL_TIM_OC_ConfigChannel(htim, &output_compare, TIM_CHANNEL_1) != HAL_OK) {
    Error_Handler();
  }
  if ((instance == TIM1) &&
      (HAL_TIM_OC_ConfigChannel(htim, &output_compare, TIM_CHANNEL_2) != HAL_OK)) {
    Error_Handler();
  }
  if (HAL_TIM_Base_Start(htim) != HAL_OK) {
    Error_Handler();
  }
}

void NucleoMotion_Init(void)
{
  GPIO_InitTypeDef gpio = {0};

  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_TIM1_CLK_ENABLE();
  __HAL_RCC_TIM2_CLK_ENABLE();

  memset(steppers, 0, sizeof(steppers));
  steppers[AXIS_X] = (StepperState){0U, 0U, GPIOA, GPIO_PIN_8,
      GPIO_AF6_TIM1, GPIOB, GPIO_PIN_0, &htim1_motion, TIM_CHANNEL_1};
  steppers[AXIS_Y] = (StepperState){0U, 0U, GPIOA, GPIO_PIN_9,
      GPIO_AF6_TIM1, GPIOB, GPIO_PIN_1, &htim1_motion, TIM_CHANNEL_2};
  steppers[AXIS_Z] = (StepperState){0U, 0U, GPIOA, GPIO_PIN_5,
      GPIO_AF1_TIM2, GPIOB, GPIO_PIN_2, &htim2_motion, TIM_CHANNEL_1};

  /* DIR is forced low before timer setup; STEP remains GPIO-low until MOVE. */
  gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2;
  gpio.Mode = GPIO_MODE_OUTPUT_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &gpio);
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2,
                    GPIO_PIN_RESET);

  timer_init(&htim1_motion, TIM1, 0xffffU);
  timer_init(&htim2_motion, TIM2, 0xffffffffU);

  HAL_NVIC_SetPriority(TIM1_CC_IRQn, 5U, 0U);
  HAL_NVIC_EnableIRQ(TIM1_CC_IRQn);
  HAL_NVIC_SetPriority(TIM2_IRQn, 5U, 0U);
  HAL_NVIC_EnableIRQ(TIM2_IRQn);

#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  dynamic_runtime_init();
#endif

  motion_armed = 0U;
  watchdog_healthy = 0U;
  last_heartbeat_ms = HAL_GetTick();
  NucleoMotion_StopAll();
}

uint8_t NucleoMotion_Arm(uint8_t safety_permissive)
{
  if (safety_permissive == 0U) {
    NucleoMotion_Disarm();
    return 0U;
  }

  last_heartbeat_ms = HAL_GetTick();
  watchdog_healthy = 1U;
  motion_armed = 1U;
  return 1U;
}

void NucleoMotion_Heartbeat(uint8_t safety_permissive)
{
  if ((safety_permissive == 0U) || (motion_armed == 0U)) {
    NucleoMotion_Disarm();
    return;
  }

  last_heartbeat_ms = HAL_GetTick();
  watchdog_healthy = 1U;
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if (dynamic_hal_ready != 0U) {
    NucleoDynamicApp_Heartbeat(&dynamic_app, dynamic_time_us(), 1U);
  }
#endif
}

void NucleoMotion_Disarm(void)
{
  motion_armed = 0U;
  watchdog_healthy = 0U;
  physical_stop_all();
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if (dynamic_hal_ready != 0U) {
    NucleoDynamicFacade_Disarm(&dynamic_app.facade);
  }
#endif
}

void NucleoMotion_StopAll(void)
{
  physical_stop_all();
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if (dynamic_hal_ready != 0U) {
    NucleoDynamicFacade_Stop(&dynamic_app.facade);
  }
#endif
}

void NucleoMotion_Poll(void)
{
  uint32_t now_ms = HAL_GetTick();
  if ((motion_armed != 0U) &&
      ((uint32_t)(now_ms - last_heartbeat_ms) >
       NUCLEO_MOTION_WATCHDOG_MS)) {
    NucleoMotion_Disarm();
  }
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if (dynamic_hal_ready != 0U) {
    uint64_t now_us = (uint64_t)now_ms * 1000ULL;
    if (now_us >= (dynamic_now_us + 1000ULL)) {
      dynamic_now_us = now_us;
      NucleoDynamicApp_ControlTick(&dynamic_app, dynamic_now_us);
    }
  }
#endif
}

uint8_t NucleoMotion_IsArmed(void)
{
  return motion_armed;
}

uint8_t NucleoMotion_WatchdogHealthy(void)
{
  return watchdog_healthy;
}

NucleoMotionResult Stepper_Move(uint8_t axis, uint8_t dir,
                               uint32_t steps, uint32_t speed_hz)
{
  StepperState *stepper;

  NucleoMotion_Poll();
  if (motion_armed == 0U) {
    return NUCLEO_MOTION_ERR_NOT_ARMED;
  }
  if (watchdog_healthy == 0U) {
    return NUCLEO_MOTION_ERR_WATCHDOG;
  }
  if ((axis >= AXIS_COUNT) || (dir > 1U) || (steps == 0U) ||
      (steps > NUCLEO_MOTION_MAX_STEPS) ||
      (speed_hz < NUCLEO_MOTION_MIN_SPEED_HZ) ||
      (speed_hz > NUCLEO_MOTION_MAX_SPEED_HZ)) {
    return NUCLEO_MOTION_ERR_ARGUMENT;
  }
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if ((axis < AXIS_Z) && (dynamic_hal_ready != 0U) &&
      ((dynamic_app.facade.coordinator.active_mask & (1U << axis)) != 0U)) {
    return NUCLEO_MOTION_ERR_BUSY;
  }
#endif
  if (steppers[axis].toggles_remaining != 0U) {
    return NUCLEO_MOTION_ERR_BUSY;
  }

  stepper = &steppers[axis];
  HAL_GPIO_WritePin(stepper->dir_port, stepper->dir_pin,
                    dir != 0U ? GPIO_PIN_SET : GPIO_PIN_RESET);
  stepper->half_period_ticks = TIMER_TICK_HZ / (speed_hz * 2U);
  stepper->toggles_remaining = steps * 2U;
  pulse_as_timer_output(stepper);
  __HAL_TIM_SET_COMPARE(stepper->htim, stepper->channel,
                        __HAL_TIM_GET_COUNTER(stepper->htim) +
                        FIRST_COMPARE_DELAY_TICKS);
  (void)HAL_TIM_OC_Start_IT(stepper->htim, stepper->channel);
  return NUCLEO_MOTION_OK;
}

void NucleoMotion_StopAxis(uint8_t axis)
{
  if (axis >= AXIS_COUNT) {
    return;
  }
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if ((axis < AXIS_Z) && (dynamic_hal_ready != 0U) &&
      ((dynamic_app.facade.coordinator.active_mask & (1U << axis)) != 0U)) {
    NucleoDynamicCoordinator_StopAll(&dynamic_app.facade.coordinator);
  }
#endif
  steppers[axis].toggles_remaining = 0U;
  (void)HAL_TIM_OC_Stop_IT(steppers[axis].htim, steppers[axis].channel);
  pulse_as_gpio_low(&steppers[axis]);
}

uint8_t Stepper_IsMoving(uint8_t axis)
{
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if ((axis < AXIS_Z) && (dynamic_hal_ready != 0U) &&
      ((dynamic_app.facade.coordinator.active_mask & (1U << axis)) != 0U)) {
    return 1U;
  }
#endif
  return (axis < AXIS_COUNT) && (steppers[axis].toggles_remaining != 0U);
}

void HAL_TIM_OC_DelayElapsedCallback(TIM_HandleTypeDef *htim)
{
  uint8_t axis = 0xffU;
  StepperState *stepper;

  if (htim->Instance == TIM1) {
    if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_1) {
      axis = AXIS_X;
    } else if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_2) {
      axis = AXIS_Y;
    }
  } else if ((htim->Instance == TIM2) &&
             (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_1)) {
    axis = AXIS_Z;
  }
  if (axis >= AXIS_COUNT) {
    return;
  }

#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  if ((axis < AXIS_Z) && (dynamic_hal_ready != 0U) &&
      ((dynamic_app.facade.coordinator.active_mask & (1U << axis)) != 0U)) {
    NucleoG491ProfileHal_OnCompare(&dynamic_profile_hal, axis);
    return;
  }
#endif

  stepper = &steppers[axis];
  if (stepper->toggles_remaining > 0U) {
    --stepper->toggles_remaining;
  }
  if (stepper->toggles_remaining == 0U) {
    pulse_as_gpio_low(stepper);
    return;
  }
  __HAL_TIM_SET_COMPARE(htim, stepper->channel,
      __HAL_TIM_GET_COMPARE(htim, stepper->channel) +
      stepper->half_period_ticks);
}

void NucleoMotion_TIM1_IRQHandler(void)
{
  HAL_TIM_IRQHandler(&htim1_motion);
}

void NucleoMotion_TIM2_IRQHandler(void)
{
  HAL_TIM_IRQHandler(&htim2_motion);
}

void NucleoMotion_TIM6_IRQHandler(void)
{
}

#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
uint8_t NucleoMotion_HandleDynamicLine(const char *line, char *response,
                                       size_t response_size)
{
  if (dynamic_hal_ready == 0U) return 0U;
  return NucleoDynamicApp_HandleLine(
      &dynamic_app, line, dynamic_time_us(),
      watchdog_healthy != 0U, motion_armed != 0U,
      response, response_size);
}
#endif
