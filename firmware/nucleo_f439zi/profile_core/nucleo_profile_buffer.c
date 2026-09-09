#include "nucleo_profile_buffer.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PROFILE_LINE_MAX 512U
#define PROFILE_TOKEN_COUNT (7U + (NUCLEO_PROFILE_PHASE_COUNT * 2U))

static uint8_t valid_command_id(const char *value)
{
  size_t index;
  size_t length = strlen(value);
  if ((length == 0U) || (length > NUCLEO_PROFILE_COMMAND_ID_MAX)) return 0U;
  for (index = 0U; index < length; index++) {
    unsigned char ch = (unsigned char)value[index];
    if (!(isalnum(ch) || ch == '_' || ch == '-' || ch == '.' || ch == ':')) return 0U;
  }
  return 1U;
}

static uint8_t valid_checksum(const char *value)
{
  size_t index;
  if (strlen(value) != 64U) return 0U;
  for (index = 0U; index < 64U; index++) {
    if (!isxdigit((unsigned char)value[index])) return 0U;
  }
  return 1U;
}

static uint8_t parse_u32(const char *token, uint32_t *value)
{
  char *end = NULL;
  unsigned long parsed = strtoul(token, &end, 10);
  if ((token[0] == '\0') || (end == NULL) || (*end != '\0')) return 0U;
  if (parsed > 0xffffffffUL) return 0U;
  *value = (uint32_t)parsed;
  return 1U;
}

static uint8_t parse_i32(const char *token, int32_t *value)
{
  char *end = NULL;
  long parsed = strtol(token, &end, 10);
  if ((token[0] == '\0') || (end == NULL) || (*end != '\0')) return 0U;
  if ((parsed < (-2147483647L - 1L)) || (parsed > 2147483647L)) return 0U;
  *value = (int32_t)parsed;
  return 1U;
}

void NucleoProfileBuffer_Init(NucleoProfileBuffer *buffer)
{
  if (buffer == NULL) return;
  memset(buffer, 0, sizeof(*buffer));
  buffer->state = NUCLEO_PROFILE_EMPTY;
}

NucleoProfileResult NucleoProfile_ParseLine(const char *line,
                                            NucleoProfileFrame *frame)
{
  char copy[PROFILE_LINE_MAX];
  char *tokens[PROFILE_TOKEN_COUNT];
  char *token;
  size_t count = 0U;
  size_t index;
  uint32_t parsed = 0U;

  if ((line == NULL) || (frame == NULL) || (strlen(line) >= sizeof(copy))) {
    return NUCLEO_PROFILE_ERR_FORMAT;
  }
  strcpy(copy, line);
  token = strtok(copy, " ");
  while ((token != NULL) && (count < PROFILE_TOKEN_COUNT)) {
    tokens[count++] = token;
    token = strtok(NULL, " ");
  }
  if ((token != NULL) || (count != PROFILE_TOKEN_COUNT) ||
      (strcmp(tokens[0], "PROFILE") != 0)) {
    return NUCLEO_PROFILE_ERR_FORMAT;
  }
  if (!valid_command_id(tokens[1]) || !valid_checksum(tokens[6])) {
    return NUCLEO_PROFILE_ERR_FORMAT;
  }
  if ((strlen(tokens[2]) != 1U) || ((tokens[2][0] != 'X') && (tokens[2][0] != 'Y'))) {
    return NUCLEO_PROFILE_ERR_AXIS;
  }
  memset(frame, 0, sizeof(*frame));
  strcpy(frame->command_id, tokens[1]);
  frame->axis = (tokens[2][0] == 'X') ? 0U : 1U;
  if (!parse_u32(tokens[3], &parsed) || (parsed > 1U)) return NUCLEO_PROFILE_ERR_RANGE;
  frame->direction = (uint8_t)parsed;
  if (!parse_u32(tokens[4], &frame->steps) || (frame->steps == 0U)) return NUCLEO_PROFILE_ERR_RANGE;
  if (!parse_u32(tokens[5], &frame->sequence)) return NUCLEO_PROFILE_ERR_RANGE;
  strcpy(frame->checksum, tokens[6]);
  for (index = 0U; index < NUCLEO_PROFILE_PHASE_COUNT; index++) {
    if (!parse_u32(tokens[7U + index * 2U], &frame->phases[index].duration_us) ||
        !parse_i32(tokens[8U + index * 2U], &frame->phases[index].jerk_milli_mm_s3)) {
      return NUCLEO_PROFILE_ERR_RANGE;
    }
  }
  return NUCLEO_PROFILE_OK;
}

NucleoProfileResult NucleoProfileBuffer_Stage(NucleoProfileBuffer *buffer,
                                              const NucleoProfileFrame *frame)
{
  if ((buffer == NULL) || (frame == NULL)) return NUCLEO_PROFILE_ERR_FORMAT;
  if ((buffer->state == NUCLEO_PROFILE_RUNNING) ||
      (buffer->state == NUCLEO_PROFILE_SAFETY_STOP)) return NUCLEO_PROFILE_ERR_STATE;
  if (buffer->count == 0U) {
    strcpy(buffer->command_id, frame->command_id);
  } else if (strcmp(buffer->command_id, frame->command_id) != 0) {
    return NUCLEO_PROFILE_ERR_COMMAND;
  }
  if (frame->sequence < buffer->count) {
    const NucleoProfileFrame *existing = &buffer->frames[frame->sequence];
    return (strcmp(existing->checksum, frame->checksum) == 0)
               ? NUCLEO_PROFILE_DUPLICATE
               : NUCLEO_PROFILE_ERR_OUT_OF_ORDER;
  }
  if (frame->sequence != buffer->count) return NUCLEO_PROFILE_ERR_OUT_OF_ORDER;
  if (buffer->count >= NUCLEO_PROFILE_BUFFER_CAPACITY) return NUCLEO_PROFILE_ERR_FULL;
  buffer->frames[buffer->count++] = *frame;
  buffer->state = NUCLEO_PROFILE_BUFFERED;
  return NUCLEO_PROFILE_OK;
}

NucleoProfileResult NucleoProfileBuffer_Start(NucleoProfileBuffer *buffer,
                                              const char *command_id)
{
  if ((buffer == NULL) || (command_id == NULL)) return NUCLEO_PROFILE_ERR_FORMAT;
  if ((buffer->state != NUCLEO_PROFILE_BUFFERED) || (buffer->count == 0U)) {
    return NUCLEO_PROFILE_ERR_STATE;
  }
  if (strcmp(buffer->command_id, command_id) != 0) return NUCLEO_PROFILE_ERR_COMMAND;
  buffer->state = NUCLEO_PROFILE_RUNNING;
  return NUCLEO_PROFILE_OK;
}

void NucleoProfileBuffer_SafetyStop(NucleoProfileBuffer *buffer)
{
  if (buffer == NULL) return;
  buffer->state = NUCLEO_PROFILE_SAFETY_STOP;
}
