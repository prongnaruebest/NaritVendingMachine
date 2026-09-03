#include "nucleo_serial_link.h"

#include "main.h"
#include "cmsis_os.h"
#include "lwip/ip4_addr.h"
#include "lwip/netif.h"

#include <stdio.h>
#include <string.h>

#define NUCLEO_PROTOCOL_VERSION 1U
#define SERIAL_LINE_MAX 64U

static UART_HandleTypeDef huart3;
extern struct netif gnetif;

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

static void transmit_status(void)
{
  char response[220];
  char ip_address[IP4ADDR_STRLEN_MAX];

  if (ip4addr_ntoa_r(netif_ip4_addr(&gnetif), ip_address,
                     sizeof(ip_address)) == NULL)
  {
    (void)snprintf(ip_address, sizeof(ip_address), "0.0.0.0");
  }
  int length = snprintf(
      response,
      sizeof(response),
      "{\"type\":\"pong\",\"device\":\"NUCLEO-F439ZI\","
      "\"protocol\":%lu,\"safe\":true,\"uptime_ms\":%lu,"
      "\"ethernet\":{\"link\":%s,\"interface_up\":%s,\"ip\":\"%s\"}}\r\n",
      (unsigned long)NUCLEO_PROTOCOL_VERSION,
      (unsigned long)HAL_GetTick(),
      netif_is_link_up(&gnetif) ? "true" : "false",
      netif_is_up(&gnetif) ? "true" : "false",
      ip_address);

  if (length > 0)
  {
    transmit_text(response);
  }
}

static void process_line(char *line)
{
  if ((strcmp(line, "PING") == 0) || (strcmp(line, "STATUS") == 0))
  {
    transmit_status();
  }
  else if (line[0] != '\0')
  {
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
      "\"protocol\":1,\"safe\":true}\r\n");

  for (;;)
  {
    if (HAL_UART_Receive(&huart3, &byte, 1U, 100U) != HAL_OK)
    {
      continue;
    }
    if ((byte == '\r') || (byte == '\n'))
    {
      if (length > 0U)
      {
        line[length] = '\0';
        process_line(line);
        length = 0U;
      }
    }
    else if ((byte >= 0x20U) && (byte <= 0x7eU))
    {
      if (length < (SERIAL_LINE_MAX - 1U))
      {
        line[length++] = (char)byte;
      }
      else
      {
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
