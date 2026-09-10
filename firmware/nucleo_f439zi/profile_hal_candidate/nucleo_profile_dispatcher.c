#include "nucleo_profile_dispatcher.h"

#include <stdio.h>
#include <string.h>

static const char *result_code(NucleoProfileResult result)
{
  switch (result) {
    case NUCLEO_PROFILE_DUPLICATE: return "DUPLICATE";
    case NUCLEO_PROFILE_ERR_FORMAT: return "FORMAT";
    case NUCLEO_PROFILE_ERR_AXIS: return "AXIS";
    case NUCLEO_PROFILE_ERR_RANGE: return "RANGE";
    case NUCLEO_PROFILE_ERR_COMMAND: return "COMMAND";
    case NUCLEO_PROFILE_ERR_OUT_OF_ORDER: return "OUT_OF_ORDER";
    case NUCLEO_PROFILE_ERR_FULL: return "FULL";
    case NUCLEO_PROFILE_ERR_STATE: return "STATE";
    case NUCLEO_PROFILE_OK: return "OK";
    default: return "UNKNOWN";
  }
}

static uint8_t write_response(char *response, size_t response_size,
                              const char *format, const char *command_id,
                              unsigned long value, const char *status)
{
  int written;
  if ((response == NULL) || (response_size == 0U)) return 0U;
  written = snprintf(response, response_size, format, command_id, value, status);
  if ((written < 0) || ((size_t)written >= response_size)) {
    response[0] = '\0';
    return 0U;
  }
  return 1U;
}

static uint8_t write_error(char *response, size_t response_size,
                           NucleoProfileResult result)
{
  int written;
  if ((response == NULL) || (response_size == 0U)) return 0U;
  written = snprintf(response, response_size,
      "{\"type\":\"error\",\"code\":\"%s\",\"error\":\"profile rejected\"}",
      result_code(result));
  if ((written < 0) || ((size_t)written >= response_size)) {
    response[0] = '\0';
    return 0U;
  }
  return 1U;
}

void NucleoProfileDispatcher_Init(NucleoProfileDispatcher *dispatcher,
                                  NucleoProfileFacade *facade)
{
  if (dispatcher == NULL) return;
  dispatcher->facade = facade;
}

uint8_t NucleoProfileDispatcher_HandleLine(
    NucleoProfileDispatcher *dispatcher, const char *line,
    uint64_t now_us, uint8_t safety_permissive,
    uint8_t x_sensor_active, uint8_t y_sensor_active,
    char *response, size_t response_size)
{
  NucleoProfileResult result;
  size_t length;
  if ((dispatcher == NULL) || (dispatcher->facade == NULL) ||
      (line == NULL)) return write_error(response, response_size,
                                         NUCLEO_PROFILE_ERR_STATE);
  length = strlen(line);
  if ((length == 0U) || (length > NUCLEO_PROFILE_COMMAND_LINE_MAX) ||
      (strchr(line, '\n') != NULL) || (strchr(line, '\r') != NULL)) {
    return write_error(response, response_size, NUCLEO_PROFILE_ERR_FORMAT);
  }
  if (strncmp(line, "SENSOR_PROFILE ", 15U) == 0) {
    NucleoProfileFrame frame;
    result = NucleoProfile_ParseLine(line, &frame);
    if (result == NUCLEO_PROFILE_OK) {
      result = NucleoProfileFacade_StageLine(dispatcher->facade, line);
    }
    if ((result != NUCLEO_PROFILE_OK) &&
        (result != NUCLEO_PROFILE_DUPLICATE)) {
      return write_error(response, response_size, result);
    }
    return write_response(response, response_size,
        "{\"type\":\"ack\",\"command_id\":\"%s\",\"sequence\":%lu,\"status\":\"%s\"}",
        frame.command_id, (unsigned long)frame.sequence,
        (result == NUCLEO_PROFILE_DUPLICATE) ? "duplicate" : "buffered");
  }
  if (strncmp(line, "SENSOR_START ", 13U) == 0) {
    char command_id[NUCLEO_PROFILE_COMMAND_ID_MAX + 1U];
    unsigned long frames;
    char trailing;
    int fields = sscanf(line, "SENSOR_START %64s %lu %c",
                        command_id, &frames, &trailing);
    if ((fields != 2) || (frames == 0UL) ||
        (frames != dispatcher->facade->buffer.count)) {
      return write_error(response, response_size, NUCLEO_PROFILE_ERR_FORMAT);
    }
    result = NucleoProfileFacade_StartSensor(
        dispatcher->facade, command_id, now_us, safety_permissive,
        x_sensor_active, y_sensor_active);
    if (result != NUCLEO_PROFILE_OK) {
      return write_error(response, response_size, result);
    }
    return write_response(response, response_size,
        "{\"type\":\"ack\",\"command_id\":\"%s\",\"frames\":%lu,\"status\":\"%s\"}",
        command_id, frames, "running");
  }
  return write_error(response, response_size, NUCLEO_PROFILE_ERR_FORMAT);
}
