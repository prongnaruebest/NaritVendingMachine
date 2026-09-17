#include "nucleo_dynamic_dispatcher.h"
#include "nucleo_dynamic_telemetry.h"
#include "nucleo_motion_features.h"

#include <stdio.h>
#include <string.h>

static const char *result_code(NucleoDynamicProtocolResult result)
{
  switch (result) {
    case NUCLEO_DYNAMIC_PROTOCOL_DUPLICATE: return "DUPLICATE";
    case NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT: return "FORMAT";
    case NUCLEO_DYNAMIC_PROTOCOL_ERR_AXIS: return "AXIS";
    case NUCLEO_DYNAMIC_PROTOCOL_ERR_RANGE: return "RANGE";
    case NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE: return "STATE";
    case NUCLEO_DYNAMIC_PROTOCOL_ERR_REVISION: return "REVISION";
    case NUCLEO_DYNAMIC_PROTOCOL_ERR_POSITION: return "POSITION";
    case NUCLEO_DYNAMIC_PROTOCOL_ERR_CONFLICT: return "CONFLICT";
    case NUCLEO_DYNAMIC_PROTOCOL_OK: return "OK";
    default: return "UNKNOWN";
  }
}

static uint8_t write_text(char *response, size_t response_size,
                          const char *format, const char *value)
{
  int written;
  if ((response == NULL) || (response_size == 0U)) return 0U;
  written = snprintf(response, response_size, format, value);
  if ((written < 0) || ((size_t)written >= response_size)) {
    response[0] = '\0';
    return 0U;
  }
  return 1U;
}

static uint8_t write_error(char *response, size_t response_size,
                           NucleoDynamicProtocolResult result)
{
  return write_text(response, response_size,
      "{\"type\":\"error\",\"code\":\"%s\",\"error\":\"dynamic command rejected\"}",
      result_code(result));
}

static uint8_t write_ack(char *response, size_t response_size,
                         const char *status)
{
  return write_text(response, response_size,
      "{\"type\":\"ack\",\"status\":\"%s\"}", status);
}

void NucleoDynamicDispatcher_Init(NucleoDynamicDispatcher *dispatcher,
                                  NucleoDynamicFacade *facade)
{
  if (dispatcher == NULL) return;
  dispatcher->facade = facade;
}

uint8_t NucleoDynamicDispatcher_HandleLine(
    NucleoDynamicDispatcher *dispatcher, const char *line, uint64_t now_us,
    uint8_t safety_permissive, uint8_t armed, char *response,
    size_t response_size)
{
  size_t length;
  if ((dispatcher == NULL) || (dispatcher->facade == NULL) ||
      (line == NULL)) {
    return write_error(response, response_size,
                       NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE);
  }
  length = strlen(line);
  if ((length == 0U) || (length > NUCLEO_DYNAMIC_COMMAND_LINE_MAX) ||
      (strchr(line, '\n') != NULL) || (strchr(line, '\r') != NULL)) {
    return write_error(response, response_size,
                       NUCLEO_DYNAMIC_PROTOCOL_ERR_FORMAT);
  }

  /* Emergency commands remain recognized even when protocol v4 is disabled. */
  if (strcmp(line, "STOP") == 0) {
    NucleoDynamicFacade_Stop(dispatcher->facade);
    return write_ack(response, response_size, "stopped");
  }
  if (strcmp(line, "DISARM") == 0) {
    NucleoDynamicFacade_Disarm(dispatcher->facade);
    return write_ack(response, response_size, "disarmed");
  }
#if NUCLEO_DYNAMIC_PROTOCOL_V4_ENABLED
  NucleoDynamicProtocolResult result;
  if (strcmp(line, "DYN_STATUS") == 0) {
    return NucleoDynamicTelemetry_Write(dispatcher->facade, response,
                                        response_size);
  }
  if (strcmp(line, "CONTROLLED_STOP") == 0) {
    NucleoDynamicFacade_ControlledStop(dispatcher->facade);
    return write_ack(response, response_size, "stopping");
  }
  if (strncmp(line, "DYN_CONFIG ", 11U) == 0) {
    result = NucleoDynamicFacade_ApplyConfig(dispatcher->facade, line, armed);
    if (result == NUCLEO_DYNAMIC_PROTOCOL_OK) {
      return write_ack(response, response_size, "configured");
    }
    return write_error(response, response_size, result);
  }
  if (strncmp(line, "DYN_POSITION ", 13U) == 0) {
    result = NucleoDynamicFacade_ApplyPosition(dispatcher->facade, line, armed);
    if (result == NUCLEO_DYNAMIC_PROTOCOL_OK) {
      return write_ack(response, response_size, "position_set");
    }
    return write_error(response, response_size, result);
  }
  if (strncmp(line, "DYN_TARGET ", 11U) == 0) {
    result = NucleoDynamicFacade_StageTarget(dispatcher->facade, line);
    if (result == NUCLEO_DYNAMIC_PROTOCOL_OK) {
      return write_ack(response, response_size, "staged");
    }
    if (result == NUCLEO_DYNAMIC_PROTOCOL_DUPLICATE) {
      return write_ack(response, response_size, "duplicate");
    }
    return write_error(response, response_size, result);
  }
  if (strncmp(line, "DYN_START ", 10U) == 0) {
    result = NucleoDynamicFacade_StartLine(dispatcher->facade, line, now_us,
                                           safety_permissive);
    if (result == NUCLEO_DYNAMIC_PROTOCOL_OK) {
      return write_ack(response, response_size, "running");
    }
    return write_error(response, response_size, result);
  }
#else
  (void)now_us;
  (void)safety_permissive;
  (void)armed;
#endif
  return write_error(response, response_size,
                     NUCLEO_DYNAMIC_PROTOCOL_ERR_STATE);
}
