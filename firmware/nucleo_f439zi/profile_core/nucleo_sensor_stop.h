#ifndef NUCLEO_SENSOR_STOP_H
#define NUCLEO_SENSOR_STOP_H

#include <stdint.h>

#define NUCLEO_SENSOR_WATCHDOG_MIN_US 100000ULL
#define NUCLEO_SENSOR_WATCHDOG_MAX_US 3600000000ULL

typedef enum {
  NUCLEO_SENSOR_X_MIN = 0,
  NUCLEO_SENSOR_X_MAX,
  NUCLEO_SENSOR_Y_MIN,
  NUCLEO_SENSOR_Y_MAX
} NucleoTerminationSensor;

typedef enum {
  NUCLEO_SENSOR_STOP_CONTROLLED = 0,
  NUCLEO_SENSOR_STOP_IMMEDIATE
} NucleoSensorStopMode;

typedef enum {
  NUCLEO_SENSOR_IDLE = 0,
  NUCLEO_SENSOR_SEARCHING,
  NUCLEO_SENSOR_FOUND,
  NUCLEO_SENSOR_STUCK_ACTIVE,
  NUCLEO_SENSOR_WATCHDOG_TIMEOUT,
  NUCLEO_SENSOR_SAFETY_STOP
} NucleoSensorStopState;

typedef enum {
  NUCLEO_SENSOR_RESULT_OK = 0,
  NUCLEO_SENSOR_RESULT_ERR_AXIS,
  NUCLEO_SENSOR_RESULT_ERR_SENSOR,
  NUCLEO_SENSOR_RESULT_ERR_RANGE,
  NUCLEO_SENSOR_RESULT_ERR_BUSY,
  NUCLEO_SENSOR_RESULT_ERR_STUCK,
  NUCLEO_SENSOR_RESULT_ERR_STATE
} NucleoSensorStopResult;

typedef enum {
  NUCLEO_SENSOR_EVENT_NONE = 0,
  NUCLEO_SENSOR_EVENT_X_CONTROLLED = 1U << 0,
  NUCLEO_SENSOR_EVENT_X_IMMEDIATE = 1U << 1,
  NUCLEO_SENSOR_EVENT_Y_CONTROLLED = 1U << 2,
  NUCLEO_SENSOR_EVENT_Y_IMMEDIATE = 1U << 3,
  NUCLEO_SENSOR_EVENT_X_WATCHDOG = 1U << 4,
  NUCLEO_SENSOR_EVENT_Y_WATCHDOG = 1U << 5,
  NUCLEO_SENSOR_EVENT_GLOBAL_SAFETY = 1U << 6
} NucleoSensorStopEvent;

typedef struct {
  uint8_t active;
  NucleoTerminationSensor sensor;
  NucleoSensorStopMode stop_mode;
  NucleoSensorStopState state;
  uint64_t started_at_us;
  uint64_t watchdog_us;
} NucleoSensorStopChannel;

typedef struct {
  NucleoSensorStopChannel axes[2];
  uint8_t safety_latched;
} NucleoSensorStopSupervisor;

void NucleoSensorStop_Init(NucleoSensorStopSupervisor *supervisor);
NucleoSensorStopResult NucleoSensorStop_Start(
    NucleoSensorStopSupervisor *supervisor, uint8_t axis,
    NucleoTerminationSensor sensor, NucleoSensorStopMode stop_mode,
    uint64_t now_us, uint64_t watchdog_us, uint8_t sensor_active);
uint32_t NucleoSensorStop_Tick(
    NucleoSensorStopSupervisor *supervisor, uint64_t now_us,
    uint8_t safety_permissive, uint8_t x_sensor_active,
    uint8_t y_sensor_active);
void NucleoSensorStop_Reset(NucleoSensorStopSupervisor *supervisor);

#endif
