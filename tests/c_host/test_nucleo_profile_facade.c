#include "nucleo_profile_facade.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned int starts[2];
static unsigned int stops[2];
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

#if NUCLEO_XY_PROFILE_FEATURE_ENABLED
static void make_sensor_line(char *line)
{
  unsigned int index;
  char phase[96];
  sprintf(line, "SENSOR_PROFILE seek-x X 1 6471 0 X_MAX immediate 1000000 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
  for (index = 0U; index < 7U; index++) {
    unsigned long end_step = (index == 6U) ? 6471UL : (unsigned long)(index + 1U) * 900UL;
    sprintf(phase, " 1000 %lu 1000 2000 10000 10000 100000", end_step);
    strcat(line, phase);
  }
}
#endif

int main(void)
{
  TIM_TypeDef instance = {0U, {0U, 0U}};
  TIM_HandleTypeDef tim1 = {&instance};
  GPIO_TypeDef gpio_a = {0U};
  NucleoProfileFacade facade;
  assert(NucleoProfileFacade_Init(&facade, &tim1, &gpio_a, 0x100U,
                                  &gpio_a, 0x200U, 1000000U) == 1U);
#if NUCLEO_XY_PROFILE_FEATURE_ENABLED
  char sensor_line[1024];
  assert(NucleoProfileFacade_FeatureEnabled() == 1U);
  assert(NucleoProfileFacade_AdvertisedProtocol() == 4U);
  assert(NucleoProfileFacade_Start(&facade, "missing", 0U, 1U) ==
         NUCLEO_PROFILE_ERR_COMMAND);
  make_sensor_line(sensor_line);
  assert(NucleoProfileFacade_StageLine(&facade, sensor_line) ==
         NUCLEO_PROFILE_OK);
  assert(NucleoProfileFacade_Start(&facade, "seek-x", 0U, 1U) ==
         NUCLEO_PROFILE_ERR_STATE);
  assert(NucleoProfileFacade_StartSensor(&facade, "seek-x", 0U, 1U, 0U, 0U) ==
         NUCLEO_PROFILE_OK);
  assert(facade.scheduler.active[0] == 1U);
  assert(NucleoProfileFacade_PollSensors(&facade, 100U, 1U, 1U, 0U) ==
         NUCLEO_PROFILE_RUNNING);
  assert(facade.scheduler.active[0] == 0U);
  assert(stops[0] > 0U);
  NucleoProfileFacade_SafetyStop(&facade);
  assert(NucleoProfileFacade_StartSensor(&facade, "seek-x", 200U, 1U, 0U, 0U) ==
         NUCLEO_PROFILE_ERR_STATE);
  NucleoProfileFacade_Reset(&facade);
  assert(NucleoProfileFacade_StageLine(&facade, sensor_line) ==
         NUCLEO_PROFILE_OK);
  assert(NucleoProfileFacade_StartSensor(&facade, "seek-x", 0U, 1U, 0U, 0U) ==
         NUCLEO_PROFILE_OK);
  assert(NucleoProfileFacade_PollSensors(&facade, 1000000U, 1U, 0U, 0U) ==
         NUCLEO_PROFILE_SAFETY_STOP);
  assert(facade.scheduler.active[0] == 0U);
#else
  assert(NucleoProfileFacade_FeatureEnabled() == 0U);
  assert(NucleoProfileFacade_AdvertisedProtocol() == 3U);
  assert(NucleoProfileFacade_StageLine(&facade, "PROFILE") ==
         NUCLEO_PROFILE_ERR_STATE);
  assert(NucleoProfileFacade_Start(&facade, "missing", 0U, 1U) ==
         NUCLEO_PROFILE_ERR_STATE);
  assert(starts[0] == 0U && starts[1] == 0U);
#endif
  NucleoProfileFacade_SafetyStop(&facade);
  assert(stops[0] > 0U && stops[1] > 0U);
  puts("nucleo_profile_facade host tests passed");
  return 0;
}
