#include "nucleo_motion.h"

#include <string.h>

#define TIMER_TICK_HZ 1000000U
#define FIRST_COMPARE_DELAY_TICKS 20U
#define AXIS_COUNT 3U

TIM_HandleTypeDef htim1;
TIM_HandleTypeDef htim2;

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

static StepperState steppers[AXIS_COUNT];
static volatile uint8_t motion_armed;
static volatile uint8_t watchdog_healthy;
static volatile uint32_t last_heartbeat_ms;

static uint32_t timer_clock_hz(TIM_TypeDef *instance)
{
    if (instance == TIM1) {
        uint32_t clock = HAL_RCC_GetPCLK2Freq();
        return ((RCC->CFGR & RCC_CFGR_PPRE2) == RCC_HCLK_DIV1) ? clock : clock * 2U;
    }

    {
        uint32_t clock = HAL_RCC_GetPCLK1Freq();
        return ((RCC->CFGR & RCC_CFGR_PPRE1) == RCC_HCLK_DIV1) ? clock : clock * 2U;
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
    (void)HAL_TIM_OC_Init(htim);

    output_compare.OCMode = TIM_OCMODE_TOGGLE;
    output_compare.Pulse = 0U;
    output_compare.OCPolarity = TIM_OCPOLARITY_HIGH;
    output_compare.OCFastMode = TIM_OCFAST_DISABLE;
    (void)HAL_TIM_OC_ConfigChannel(htim, &output_compare, TIM_CHANNEL_1);
    if (instance == TIM1) {
        (void)HAL_TIM_OC_ConfigChannel(htim, &output_compare, TIM_CHANNEL_2);
    }
    (void)HAL_TIM_Base_Start(htim);
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
        GPIO_AF1_TIM1, GPIOB, GPIO_PIN_0, &htim1, TIM_CHANNEL_1};
    steppers[AXIS_Y] = (StepperState){0U, 0U, GPIOA, GPIO_PIN_9,
        GPIO_AF1_TIM1, GPIOB, GPIO_PIN_1, &htim1, TIM_CHANNEL_2};
    steppers[AXIS_Z] = (StepperState){0U, 0U, GPIOA, GPIO_PIN_5,
        GPIO_AF1_TIM2, GPIOB, GPIO_PIN_2, &htim2, TIM_CHANNEL_1};

    gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB, &gpio);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2,
                      GPIO_PIN_RESET);

    timer_init(&htim1, TIM1, 0xffffU);
    timer_init(&htim2, TIM2, 0xffffffffU);

    HAL_NVIC_SetPriority(TIM1_CC_IRQn, 5U, 0U);
    HAL_NVIC_EnableIRQ(TIM1_CC_IRQn);
    HAL_NVIC_SetPriority(TIM2_IRQn, 5U, 0U);
    HAL_NVIC_EnableIRQ(TIM2_IRQn);

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
}

void NucleoMotion_Disarm(void)
{
    motion_armed = 0U;
    watchdog_healthy = 0U;
    NucleoMotion_StopAll();
}

void NucleoMotion_StopAll(void)
{
    uint32_t axis;
    uint32_t primask = __get_PRIMASK();

    __disable_irq();
    for (axis = 0U; axis < AXIS_COUNT; ++axis) {
        pulse_as_gpio_low(&steppers[axis]);
    }
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2,
                      GPIO_PIN_RESET);
    if (primask == 0U) {
        __enable_irq();
    }
}

void NucleoMotion_Poll(void)
{
    if ((motion_armed != 0U) &&
        ((uint32_t)(HAL_GetTick() - last_heartbeat_ms) >
         NUCLEO_MOTION_WATCHDOG_MS)) {
        NucleoMotion_Disarm();
    }
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
    uint32_t index;

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
    for (index = 0U; index < AXIS_COUNT; ++index) {
        if (steppers[index].toggles_remaining != 0U) {
            return NUCLEO_MOTION_ERR_BUSY;
        }
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

uint8_t Stepper_IsMoving(uint8_t axis)
{
    return (axis < AXIS_COUNT) && (steppers[axis].toggles_remaining != 0U);
}

void HAL_TIM_OC_DelayElapsedCallback(TIM_HandleTypeDef *htim)
{
    uint8_t axis = 0xffU;
    StepperState *stepper;

    if (htim->Instance == TIM1) {
        if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_1) axis = AXIS_X;
        else if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_2) axis = AXIS_Y;
    } else if ((htim->Instance == TIM2) &&
               (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_1)) {
        axis = AXIS_Z;
    }
    if (axis >= AXIS_COUNT) return;

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

void TIM1_CC_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim1);
}

void TIM2_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim2);
}
