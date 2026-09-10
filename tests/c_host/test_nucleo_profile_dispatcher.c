#include "nucleo_profile_dispatcher.h"

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

int main(void)
{
  TIM_TypeDef instance = {0U, {0U, 0U}};
  TIM_HandleTypeDef tim1 = {&instance};
  GPIO_TypeDef gpio_a = {0U};
  NucleoProfileFacade facade;
  NucleoProfileDispatcher dispatcher;
  char line[1100];
  char response[256];
  char tiny[2] = {'x', '\0'};
  uint32_t seed = 0x12345678U;
  unsigned int fuzz_case;

  assert(NucleoProfileFacade_Init(&facade, &tim1, &gpio_a, 0x100U,
                                  &gpio_a, 0x200U, 1000000U) == 1U);
  NucleoProfileDispatcher_Init(&dispatcher, &facade);
  make_sensor_line(line);
#if NUCLEO_XY_PROFILE_FEATURE_ENABLED
  assert(NucleoProfileDispatcher_HandleLine(&dispatcher, line, 0U, 1U, 0U, 0U,
                                             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"status\":\"buffered\"") != NULL);
  assert(strstr(response, "\"command_id\":\"seek-x\"") != NULL);
  assert(NucleoProfileDispatcher_HandleLine(&dispatcher, line, 0U, 1U, 0U, 0U,
                                             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"status\":\"duplicate\"") != NULL);
  assert(NucleoProfileDispatcher_HandleLine(&dispatcher, "SENSOR_START seek-x 2",
                                             0U, 1U, 0U, 0U,
                                             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"code\":\"FORMAT\"") != NULL);
  assert(NucleoProfileDispatcher_HandleLine(&dispatcher, "SENSOR_START seek-x 1",
                                             0U, 1U, 0U, 0U,
                                             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"status\":\"running\"") != NULL);
  assert(facade.scheduler.active[0] == 1U);
#else
  assert(NucleoProfileDispatcher_HandleLine(&dispatcher, line, 0U, 1U, 0U, 0U,
                                             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"code\":\"STATE\"") != NULL);
  assert(starts[0] == 0U && starts[1] == 0U);
#endif

  assert(NucleoProfileDispatcher_HandleLine(&dispatcher, "SENSOR_START seek-x 1 extra",
                                             0U, 1U, 0U, 0U,
                                             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"code\":\"FORMAT\"") != NULL);
  assert(NucleoProfileDispatcher_HandleLine(&dispatcher, "SENSOR_PROFILE bad\n",
                                             0U, 1U, 0U, 0U,
                                             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"code\":\"FORMAT\"") != NULL);
  memset(line, 'A', 1024U);
  line[1024] = '\0';
  assert(NucleoProfileDispatcher_HandleLine(&dispatcher, line, 0U, 1U, 0U, 0U,
                                             response, sizeof(response)) == 1U);
  assert(strstr(response, "\"code\":\"FORMAT\"") != NULL);
  for (fuzz_case = 0U; fuzz_case < 512U; fuzz_case++) {
    size_t index;
    size_t fuzz_length = (size_t)((fuzz_case * 37U) % 1023U) + 1U;
    for (index = 0U; index < fuzz_length; index++) {
      seed = seed * 1664525U + 1013904223U;
      line[index] = (char)(33U + (seed % 94U));
    }
    line[fuzz_length] = '\0';
    assert(NucleoProfileDispatcher_HandleLine(&dispatcher, line, 0U, 1U,
                                               0U, 0U, response,
                                               sizeof(response)) == 1U);
    assert(response[0] == '{');
  }
  assert(NucleoProfileDispatcher_HandleLine(&dispatcher, "UNKNOWN", 0U, 1U, 0U, 0U,
                                             tiny, sizeof(tiny)) == 0U);
  assert(tiny[0] == '\0');
  puts("nucleo_profile_dispatcher host tests passed");
  return 0;
}
