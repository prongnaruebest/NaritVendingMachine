#include "nucleo_serial_link.h"

#include "main.h"
#include "nucleo_motion.h"

#include <stdio.h>
#include <string.h>

#define NUCLEO_PROTOCOL_VERSION 3U
#define SERIAL_LINE_MAX 96U

static UART_HandleTypeDef *serial_uart;
static char receive_line[SERIAL_LINE_MAX];
static uint32_t receive_length;

static void transmit_text(const char *text)
{
  (void)HAL_UART_Transmit(
      serial_uart, (uint8_t *)text, (uint16_t)strlen(text), 100U);
}

static uint8_t any_axis_moving(void)
{
  return Stepper_IsMoving(AXIS_X) || Stepper_IsMoving(AXIS_Y) ||
         Stepper_IsMoving(AXIS_Z);
}

static void transmit_status(const char *type)
{
  char response[240];
  uint8_t moving = any_axis_moving();
  uint8_t armed = NucleoMotion_IsArmed();
  int length = snprintf(
      response, sizeof(response),
      "{\"type\":\"%s\",\"device\":\"NUCLEO-F439ZI\","
      "\"protocol\":%lu,\"safe\":%s,\"armed\":%s,"
      "\"watchdog\":%s,\"uptime_ms\":%lu,\"max_move_steps\":%lu,"
      "\"moving\":{\"x\":%u,\"y\":%u,\"z\":%u}}\r\n",
      type,
      (unsigned long)NUCLEO_PROTOCOL_VERSION,
      ((armed == 0U) && (moving == 0U)) ? "true" : "false",
      armed != 0U ? "true" : "false",
      NucleoMotion_WatchdogHealthy() != 0U ? "true" : "false",
      (unsigned long)HAL_GetTick(),
      (unsigned long)NUCLEO_MOTION_MAX_STEPS,
      (unsigned int)Stepper_IsMoving(AXIS_X),
      (unsigned int)Stepper_IsMoving(AXIS_Y),
      (unsigned int)Stepper_IsMoving(AXIS_Z));

  if ((length > 0) && ((size_t)length < sizeof(response))) {
    transmit_text(response);
  }
}

static const char *move_error(NucleoMotionResult result)
{
  switch (result) {
    case NUCLEO_MOTION_ERR_NOT_ARMED: return "NOT_ARMED";
    case NUCLEO_MOTION_ERR_WATCHDOG: return "WATCHDOG";
    case NUCLEO_MOTION_ERR_ARGUMENT: return "INVALID_ARGUMENT";
    case NUCLEO_MOTION_ERR_BUSY: return "BUSY";
    default: return "INTERNAL";
  }
}

static void process_move(const char *line)
{
  const char *p = line + 5;
  char axis_char = '\0';
  unsigned int direction = 0U;
  unsigned long steps = 0U;
  unsigned long speed = 0U;
  uint8_t axis = 0xffU;
  NucleoMotionResult result;

  while (*p == ' ') p++;
  if (*p == '\0') {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }
  axis_char = *p++;
  if ((axis_char == 'X') || (axis_char == 'x')) axis = AXIS_X;
  else if ((axis_char == 'Y') || (axis_char == 'y')) axis = AXIS_Y;
  else if ((axis_char == 'Z') || (axis_char == 'z')) axis = AXIS_Z;
  else {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_AXIS\"}\r\n");
    return;
  }

  while (*p == ' ') p++;
  if ((*p != '0') && (*p != '1')) {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }
  direction = (unsigned int)(*p++ - '0');

  while (*p == ' ') p++;
  if ((*p < '0') || (*p > '9')) {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }
  while ((*p >= '0') && (*p <= '9')) {
    steps = steps * 10U + (unsigned long)(*p++ - '0');
  }

  while (*p == ' ') p++;
  if ((*p < '0') || (*p > '9')) {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }
  while ((*p >= '0') && (*p <= '9')) {
    speed = speed * 10U + (unsigned long)(*p++ - '0');
  }

  while (*p == ' ') p++;
  if (*p != '\0') {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }

  result = Stepper_Move(axis, (uint8_t)direction, (uint32_t)steps,
                        (uint32_t)speed);
  if (result == NUCLEO_MOTION_OK) {
    transmit_text("{\"type\":\"ack\",\"status\":\"moving\"}\r\n");
  } else {
    char response[80];
    (void)snprintf(response, sizeof(response),
                   "{\"type\":\"error\",\"error\":\"%s\"}\r\n",
                   move_error(result));
    transmit_text(response);
  }
}

static void process_line(char *line)
{
  NucleoMotion_Poll();
  if ((strcmp(line, "PING") == 0) || (strcmp(line, "STATUS") == 0)) {
    transmit_status("pong");
  } else if (strcmp(line, "ARM SAFE") == 0) {
    if (NucleoMotion_Arm(1U) != 0U) {
      transmit_text("{\"type\":\"ack\",\"status\":\"armed\"}\r\n");
    }
  } else if (strcmp(line, "HEARTBEAT SAFE") == 0) {
    NucleoMotion_Heartbeat(1U);
    transmit_status("heartbeat");
  } else if (strncmp(line, "STOP ", 5U) == 0 && line[6] == '\0') {
    char axis_char = line[5];
    uint8_t axis = axis_char == 'X' ? AXIS_X : axis_char == 'Y' ? AXIS_Y : axis_char == 'Z' ? AXIS_Z : 0xffU;
    if (axis == 0xffU) transmit_text("{\"type\":\"error\",\"error\":\"INVALID_AXIS\"}\r\n");
    else { NucleoMotion_StopAxis(axis); transmit_text("{\"type\":\"ack\",\"status\":\"axis_stopped\"}\r\n"); }
  } else if ((strcmp(line, "HEARTBEAT UNSAFE") == 0) ||
             (strcmp(line, "STOP") == 0) ||
             (strcmp(line, "DISARM") == 0)) {
    NucleoMotion_Disarm();
    transmit_text("{\"type\":\"ack\",\"status\":\"disarmed\"}\r\n");
  } else if (strncmp(line, "MOVE ", 5U) == 0) {
    process_move(line);
  } else if (line[0] != '\0') {
    transmit_text("{\"type\":\"error\",\"error\":\"UNKNOWN_COMMAND\"}\r\n");
  }
}

void NucleoSerialLink_Poll(void)
{
  uint8_t byte = 0U;
  if (serial_uart == NULL) return;
  while (HAL_UART_Receive(serial_uart, &byte, 1U, 0U) == HAL_OK) {
    if ((byte == '\r') || (byte == '\n')) {
      if (receive_length > 0U) {
        receive_line[receive_length] = '\0';
        process_line(receive_line);
        receive_length = 0U;
      }
    } else if ((byte >= 0x20U) && (byte <= 0x7eU)) {
      if (receive_length < (SERIAL_LINE_MAX - 1U)) {
        receive_line[receive_length++] = (char)byte;
      } else {
        receive_length = 0U;
        transmit_text("{\"type\":\"error\",\"error\":\"LINE_TOO_LONG\"}\r\n");
      }
    }
  }
}

void NucleoSerialLink_Start(UART_HandleTypeDef *uart)
{
  serial_uart = uart;
  receive_length = 0U;
  transmit_text(
      "{\"type\":\"boot\",\"device\":\"NUCLEO-F439ZI\"," 
      "\"protocol\":3,\"safe\":true,\"armed\":false}\r\n");
}

