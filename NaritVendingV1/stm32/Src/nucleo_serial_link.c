#include "nucleo_serial_link.h"

#include "main.h"
#include "cmsis_os.h"
#include "nucleo_motion.h"

#include <stdio.h>
#include <string.h>

#define NUCLEO_PROTOCOL_VERSION 2U
#define SERIAL_LINE_MAX 96U

static UART_HandleTypeDef huart3;

static void SerialLinkTask(void const *argument);

static void uart3_init(void)
{
  GPIO_InitTypeDef gpio = {0};

  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_USART3_CLK_ENABLE();

  gpio.Pin = GPIO_PIN_8 | GPIO_PIN_9;
  gpio.Mode = GPIO_MODE_AF_PP;
  gpio.Pull = GPIO_PULLUP;
  gpio.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
  gpio.Alternate = GPIO_AF7_USART3;
  HAL_GPIO_Init(GPIOD, &gpio);

  huart3.Instance = USART3;
  huart3.Init.BaudRate = 115200;
  huart3.Init.WordLength = UART_WORDLENGTH_8B;
  huart3.Init.StopBits = UART_STOPBITS_1;
  huart3.Init.Parity = UART_PARITY_NONE;
  huart3.Init.Mode = UART_MODE_TX_RX;
  huart3.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart3.Init.OverSampling = UART_OVERSAMPLING_16;
  (void)HAL_UART_Init(&huart3);
}

static void transmit_text(const char *text)
{
  (void)HAL_UART_Transmit(
      &huart3, (uint8_t *)text, (uint16_t)strlen(text), 100U);
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
      "\"watchdog\":%s,\"uptime_ms\":%lu,"
      "\"moving\":{\"x\":%u,\"y\":%u,\"z\":%u}}\r\n",
      type,
      (unsigned long)NUCLEO_PROTOCOL_VERSION,
      ((armed == 0U) && (moving == 0U)) ? "true" : "false",
      armed != 0U ? "true" : "false",
      NucleoMotion_WatchdogHealthy() != 0U ? "true" : "false",
      (unsigned long)HAL_GetTick(),
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
  char axis_char = '\0';
  char extra = '\0';
  unsigned int direction = 0U;
  unsigned long steps = 0U;
  unsigned long speed = 0U;
  uint8_t axis = 0xffU;
  NucleoMotionResult result;

  if (sscanf(line, "MOVE %c %u %lu %lu %c", &axis_char, &direction,
             &steps, &speed, &extra) != 4) {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_FORMAT\"}\r\n");
    return;
  }
  if ((axis_char == 'X') || (axis_char == 'x')) axis = AXIS_X;
  else if ((axis_char == 'Y') || (axis_char == 'y')) axis = AXIS_Y;
  else if ((axis_char == 'Z') || (axis_char == 'z')) axis = AXIS_Z;
  if (axis == 0xffU) {
    transmit_text("{\"type\":\"error\",\"error\":\"INVALID_AXIS\"}\r\n");
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

static void SerialLinkTask(void const *argument)
{
  char line[SERIAL_LINE_MAX];
  uint32_t length = 0U;
  uint8_t byte = 0U;
  (void)argument;

  transmit_text(
      "{\"type\":\"boot\",\"device\":\"NUCLEO-F439ZI\","
      "\"protocol\":2,\"safe\":true,\"armed\":false}\r\n");

  for (;;) {
    NucleoMotion_Poll();
    if (HAL_UART_Receive(&huart3, &byte, 1U, 50U) != HAL_OK) continue;

    if ((byte == '\r') || (byte == '\n')) {
      if (length > 0U) {
        line[length] = '\0';
        process_line(line);
        length = 0U;
      }
    } else if ((byte >= 0x20U) && (byte <= 0x7eU)) {
      if (length < (SERIAL_LINE_MAX - 1U)) {
        line[length++] = (char)byte;
      } else {
        length = 0U;
        transmit_text("{\"type\":\"error\",\"error\":\"LINE_TOO_LONG\"}\r\n");
      }
    }
  }
}

void NucleoSerialLink_Start(void)
{
  uart3_init();
  osThreadDef(NucleoLink, SerialLinkTask, osPriorityBelowNormal, 0, 256U);
  (void)osThreadCreate(osThread(NucleoLink), NULL);
}
