#include "nucleo_serial_link.h"

#include "nucleo_motion.h"
#include "nucleo_motion_features.h"

#include <stdio.h>
#include <string.h>

#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
#define NUCLEO_PROTOCOL_VERSION 4U
#define NUCLEO_CAPABILITIES_JSON \
  "\"capabilities\":[\"continuous_profile\",\"seven_segment_s_curve\"," \
  "\"buffered_segments\",\"profile_sequence\",\"profile_telemetry\"," \
  "\"dynamic_motion\",\"terminal_rate_config\"," \
  "\"dynamic_watchdog_heartbeat\"],"
#else
#define NUCLEO_PROTOCOL_VERSION 3U
#define NUCLEO_CAPABILITIES_JSON ""
#endif

#define SERIAL_LINE_MAX 160U
#define SERIAL_RX_RING_SIZE 512U

static UART_HandleTypeDef *serial_uart;
static char receive_line[SERIAL_LINE_MAX];
static uint32_t receive_length;
static uint8_t receive_interrupt_byte;
static volatile uint8_t receive_ring[SERIAL_RX_RING_SIZE];
static volatile uint16_t receive_ring_head;
static volatile uint16_t receive_ring_tail;
static volatile uint32_t receive_overrun_count;
static volatile uint32_t receive_dropped_bytes;

static uint16_t receive_ring_next(uint16_t index)
{
  return (uint16_t)((index + 1U) % SERIAL_RX_RING_SIZE);
}

static void arm_interrupt_receive(void)
{
  if (serial_uart != NULL) {
    (void)HAL_UART_Receive_IT(serial_uart, &receive_interrupt_byte, 1U);
  }
}

static void transmit_text(const char *message)
{
  (void)HAL_UART_Transmit(serial_uart, (uint8_t *)message,
                         (uint16_t)strlen(message), 100U);
}

static uint8_t any_axis_moving(void)
{
  return Stepper_IsMoving(AXIS_X) || Stepper_IsMoving(AXIS_Y) ||
         Stepper_IsMoving(AXIS_Z);
}

static void transmit_status(const char *type)
{
  char response[512];
  uint8_t moving = any_axis_moving();
  uint8_t armed = NucleoMotion_IsArmed();
  int length = snprintf(
      response, sizeof(response),
      "{\"type\":\"%s\",\"device\":\"NUCLEO-G491RE\","
      "\"protocol\":%lu," NUCLEO_CAPABILITIES_JSON
      "\"safe\":%s,\"armed\":%s,"
      "\"watchdog\":%s,\"uptime_ms\":%lu,\"max_move_steps\":%lu,"
      "\"uart_overrun_count\":%lu,\"rx_dropped_bytes\":%lu,"
      "\"moving\":{\"x\":%u,\"y\":%u,\"z\":%u}}\r\n",
      type,
      (unsigned long)NUCLEO_PROTOCOL_VERSION,
      ((armed == 0U) && (moving == 0U)) ? "true" : "false",
      armed != 0U ? "true" : "false",
      NucleoMotion_WatchdogHealthy() != 0U ? "true" : "false",
      (unsigned long)HAL_GetTick(),
      (unsigned long)NUCLEO_MOTION_MAX_STEPS,
      (unsigned long)receive_overrun_count,
      (unsigned long)receive_dropped_bytes,
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
    case NUCLEO_MOTION_ERR_NOT_ARMED:
      return "NOT_ARMED";
    case NUCLEO_MOTION_ERR_WATCHDOG:
      return "WATCHDOG";
    case NUCLEO_MOTION_ERR_ARGUMENT:
      return "INVALID_ARGUMENT";
    case NUCLEO_MOTION_ERR_BUSY:
      return "BUSY";
    default:
      return "INTERNAL";
  }
}

static uint8_t parse_decimal_u32(const char **cursor, uint32_t *value)
{
  uint32_t parsed = 0U;

  if ((**cursor < '0') || (**cursor > '9')) {
    return 0U;
  }
  while ((**cursor >= '0') && (**cursor <= '9')) {
    uint32_t digit = (uint32_t)(**cursor - '0');
    if (parsed > ((UINT32_MAX - digit) / 10U)) {
      return 0U;
    }
    parsed = parsed * 10U + digit;
    ++(*cursor);
  }
  *value = parsed;
  return 1U;
}

static void process_move(const char *line)
{
  const char *cursor = line + 5;
  char axis_char;
  unsigned int direction;
  uint32_t steps = 0U;
  uint32_t speed_hz = 0U;
  uint8_t axis;
  NucleoMotionResult result;

  while (*cursor == ' ') {
    ++cursor;
  }
  axis_char = *cursor++;
  if ((axis_char == 'X') || (axis_char == 'x')) {
    axis = AXIS_X;
  } else if ((axis_char == 'Y') || (axis_char == 'y')) {
    axis = AXIS_Y;
  } else if ((axis_char == 'Z') || (axis_char == 'z')) {
    axis = AXIS_Z;
  } else {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_AXIS\"}\r\n");
    return;
  }

  while (*cursor == ' ') {
    ++cursor;
  }
  if ((*cursor != '0') && (*cursor != '1')) {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }
  direction = (unsigned int)(*cursor++ - '0');

  while (*cursor == ' ') {
    ++cursor;
  }
  if (parse_decimal_u32(&cursor, &steps) == 0U) {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }

  while (*cursor == ' ') {
    ++cursor;
  }
  if (parse_decimal_u32(&cursor, &speed_hz) == 0U) {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }

  while (*cursor == ' ') {
    ++cursor;
  }
  if (*cursor != '\0') {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }

  result = Stepper_Move(axis, (uint8_t)direction, steps, speed_hz);
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
  size_t length = strlen(line);

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
  } else if ((length == 6U) && (strncmp(line, "STOP ", 5U) == 0)) {
    uint8_t axis = line[5] == 'X' ? AXIS_X
                   : line[5] == 'Y' ? AXIS_Y
                   : line[5] == 'Z' ? AXIS_Z
                                    : 0xffU;
    if (axis == 0xffU) {
      transmit_text("{\"type\":\"error\",\"error\":\"INVALID_AXIS\"}\r\n");
    } else {
      NucleoMotion_StopAxis(axis);
      transmit_text("{\"type\":\"ack\",\"status\":\"axis_stopped\"}\r\n");
    }
  } else if ((strcmp(line, "HEARTBEAT UNSAFE") == 0) ||
             (strcmp(line, "STOP") == 0) ||
             (strcmp(line, "DISARM") == 0)) {
    NucleoMotion_Disarm();
    transmit_text("{\"type\":\"ack\",\"status\":\"disarmed\"}\r\n");
  } else if (strncmp(line, "MOVE ", 5U) == 0) {
    process_move(line);
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
  } else if ((strncmp(line, "DYN_", 4U) == 0) ||
             (strcmp(line, "CONTROLLED_STOP") == 0)) {
    char response[768];
    if (NucleoMotion_HandleDynamicLine(line, response, sizeof(response)) != 0U) {
      transmit_text(response);
      transmit_text("\r\n");
    } else {
      transmit_text("{\"type\":\"error\",\"error\":\"DYNAMIC_REJECTED\"}\r\n");
    }
#endif
  } else if (line[0] != '\0') {
    transmit_text("{\"type\":\"error\",\"error\":\"UNKNOWN_COMMAND\"}\r\n");
  }
}

void NucleoSerialLink_Poll(void)
{
  uint8_t byte;

  if (serial_uart == NULL) {
    return;
  }
  while (receive_ring_tail != receive_ring_head) {
    byte = receive_ring[receive_ring_tail];
    receive_ring_tail = receive_ring_next(receive_ring_tail);
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
  receive_ring_head = 0U;
  receive_ring_tail = 0U;
  receive_overrun_count = 0U;
  receive_dropped_bytes = 0U;
  /* Safety traffic must pre-empt the 1 kHz planner (priority 4) and STEP
   * compare service (priority 5). The ISR only stores one byte; parsing and
   * responses remain in the main loop. */
  HAL_NVIC_SetPriority(LPUART1_IRQn, 3U, 0U);
  HAL_NVIC_EnableIRQ(LPUART1_IRQn);
  arm_interrupt_receive();
  transmit_text(
      "{\"type\":\"boot\",\"device\":\"NUCLEO-G491RE\","
      "\"protocol\":"
#if NUCLEO_G491_DYNAMIC_MOTION_ENABLED
      "4," NUCLEO_CAPABILITIES_JSON
#else
      "3,"
#endif
      "\"safe\":true,\"armed\":false}\r\n");
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *uart)
{
  uint16_t next;
  if ((serial_uart == NULL) || (uart != serial_uart)) return;
  next = receive_ring_next(receive_ring_head);
  if (next == receive_ring_tail) {
    ++receive_dropped_bytes;
  } else {
    receive_ring[receive_ring_head] = receive_interrupt_byte;
    receive_ring_head = next;
  }
  arm_interrupt_receive();
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *uart)
{
  if ((serial_uart == NULL) || (uart != serial_uart)) return;
  ++receive_overrun_count;
  __HAL_UART_CLEAR_OREFLAG(uart);
  arm_interrupt_receive();
}
