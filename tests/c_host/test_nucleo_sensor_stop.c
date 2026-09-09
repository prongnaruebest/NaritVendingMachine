#include "nucleo_sensor_stop.h"

#include <assert.h>
#include <stdio.h>

int main(void)
{
  NucleoSensorStopSupervisor supervisor;
  uint32_t events;

  NucleoSensorStop_Init(&supervisor);
  assert(NucleoSensorStop_Start(&supervisor, 0U, NUCLEO_SENSOR_X_MIN,
      NUCLEO_SENSOR_STOP_CONTROLLED, 1000ULL, 1000000ULL, 0U) ==
      NUCLEO_SENSOR_RESULT_OK);
  assert(NucleoSensorStop_Start(&supervisor, 1U, NUCLEO_SENSOR_Y_MAX,
      NUCLEO_SENSOR_STOP_IMMEDIATE, 1000ULL, 2000000ULL, 0U) ==
      NUCLEO_SENSOR_RESULT_OK);

  events = NucleoSensorStop_Tick(&supervisor, 2000ULL, 1U, 1U, 0U);
  assert((events & NUCLEO_SENSOR_EVENT_X_CONTROLLED) != 0U);
  assert(supervisor.axes[0].state == NUCLEO_SENSOR_FOUND);
  assert(supervisor.axes[1].state == NUCLEO_SENSOR_SEARCHING);

  events = NucleoSensorStop_Tick(&supervisor, 3000ULL, 1U, 1U, 1U);
  assert((events & NUCLEO_SENSOR_EVENT_Y_IMMEDIATE) != 0U);
  assert(supervisor.axes[1].state == NUCLEO_SENSOR_FOUND);

  NucleoSensorStop_Reset(&supervisor);
  assert(NucleoSensorStop_Start(&supervisor, 0U, NUCLEO_SENSOR_X_MAX,
      NUCLEO_SENSOR_STOP_IMMEDIATE, 0ULL, 100000ULL, 1U) ==
      NUCLEO_SENSOR_RESULT_ERR_STUCK);
  assert(supervisor.axes[0].state == NUCLEO_SENSOR_STUCK_ACTIVE);
  assert(NucleoSensorStop_Start(&supervisor, 0U, NUCLEO_SENSOR_Y_MIN,
      NUCLEO_SENSOR_STOP_IMMEDIATE, 0ULL, 100000ULL, 0U) ==
      NUCLEO_SENSOR_RESULT_ERR_SENSOR);

  NucleoSensorStop_Reset(&supervisor);
  assert(NucleoSensorStop_Start(&supervisor, 0U, NUCLEO_SENSOR_X_MAX,
      NUCLEO_SENSOR_STOP_CONTROLLED, 0ULL, 100000ULL, 0U) ==
      NUCLEO_SENSOR_RESULT_OK);
  events = NucleoSensorStop_Tick(&supervisor, 100000ULL, 1U, 0U, 0U);
  assert((events & NUCLEO_SENSOR_EVENT_X_WATCHDOG) != 0U);
  assert(supervisor.axes[0].state == NUCLEO_SENSOR_WATCHDOG_TIMEOUT);

  NucleoSensorStop_Reset(&supervisor);
  assert(NucleoSensorStop_Start(&supervisor, 0U, NUCLEO_SENSOR_X_MIN,
      NUCLEO_SENSOR_STOP_CONTROLLED, 0ULL, 1000000ULL, 0U) ==
      NUCLEO_SENSOR_RESULT_OK);
  assert(NucleoSensorStop_Start(&supervisor, 1U, NUCLEO_SENSOR_Y_MIN,
      NUCLEO_SENSOR_STOP_CONTROLLED, 0ULL, 1000000ULL, 0U) ==
      NUCLEO_SENSOR_RESULT_OK);
  events = NucleoSensorStop_Tick(&supervisor, 1ULL, 0U, 0U, 0U);
  assert(events == NUCLEO_SENSOR_EVENT_GLOBAL_SAFETY);
  assert(supervisor.axes[0].state == NUCLEO_SENSOR_SAFETY_STOP);
  assert(supervisor.axes[1].state == NUCLEO_SENSOR_SAFETY_STOP);
  assert(NucleoSensorStop_Start(&supervisor, 0U, NUCLEO_SENSOR_X_MIN,
      NUCLEO_SENSOR_STOP_CONTROLLED, 2ULL, 1000000ULL, 0U) ==
      NUCLEO_SENSOR_RESULT_ERR_STATE);

  NucleoSensorStop_Reset(&supervisor);
  assert(NucleoSensorStop_Start(&supervisor, 0U, NUCLEO_SENSOR_X_MIN,
      NUCLEO_SENSOR_STOP_CONTROLLED, 3ULL, 1000000ULL, 0U) ==
      NUCLEO_SENSOR_RESULT_OK);

  puts("nucleo_sensor_stop host tests passed");
  return 0;
}
