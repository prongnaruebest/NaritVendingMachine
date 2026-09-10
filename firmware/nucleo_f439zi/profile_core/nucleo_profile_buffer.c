#include "nucleo_profile_buffer.h"
#include "nucleo_sha256.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PROFILE_LINE_MAX 1024U
#define PROFILE_TOKEN_COUNT (7U + (NUCLEO_PROFILE_PHASE_COUNT * 7U))
#define SENSOR_PROFILE_TOKEN_COUNT (10U + (NUCLEO_PROFILE_PHASE_COUNT * 7U))
#define PROFILE_MAX_RATE_MILLIHZ 50000000UL

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

static uint8_t checksum_matches(char **tokens, size_t count,
                                size_t checksum_offset)
{
  char canonical[PROFILE_LINE_MAX];
  char expected[65];
  size_t used = 0U;
  size_t index;
  for (index = 0U; index < count; index++) {
    size_t token_length;
    if (index == checksum_offset) continue;
    token_length = strlen(tokens[index]);
    if ((used != 0U) && (used + 1U >= sizeof(canonical))) return 0U;
    if (used != 0U) canonical[used++] = ' ';
    if (used + token_length >= sizeof(canonical)) return 0U;
    memcpy(&canonical[used], tokens[index], token_length);
    used += token_length;
  }
  canonical[used] = '\0';
  NucleoSha256_Hex((const uint8_t *)canonical, used, expected);
  for (index = 0U; index < 64U; index++) {
    if (tolower((unsigned char)tokens[checksum_offset][index]) != expected[index]) {
      return 0U;
    }
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

static uint8_t parse_u64(const char *token, uint64_t *value)
{
  char *end = NULL;
  unsigned long long parsed = strtoull(token, &end, 10);
  if ((token[0] == '\0') || (end == NULL) || (*end != '\0')) return 0U;
  *value = (uint64_t)parsed;
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
  char *tokens[SENSOR_PROFILE_TOKEN_COUNT];
  char *token;
  size_t count = 0U;
  size_t index;
  uint32_t parsed = 0U;
  size_t expected_count;
  size_t checksum_offset;
  size_t phase_offset;
  uint8_t sensor_profile;

  if ((line == NULL) || (frame == NULL) || (strlen(line) >= sizeof(copy))) {
    return NUCLEO_PROFILE_ERR_FORMAT;
  }
  strcpy(copy, line);
  token = strtok(copy, " ");
  while ((token != NULL) && (count < SENSOR_PROFILE_TOKEN_COUNT)) {
    tokens[count++] = token;
    token = strtok(NULL, " ");
  }
  if (count == 0U) return NUCLEO_PROFILE_ERR_FORMAT;
  sensor_profile = (strcmp(tokens[0], "SENSOR_PROFILE") == 0) ? 1U : 0U;
  expected_count = sensor_profile ? SENSOR_PROFILE_TOKEN_COUNT : PROFILE_TOKEN_COUNT;
  checksum_offset = sensor_profile ? 9U : 6U;
  phase_offset = sensor_profile ? 10U : 7U;
  if ((token != NULL) || (count != expected_count) ||
      ((!sensor_profile) && (strcmp(tokens[0], "PROFILE") != 0))) {
    return NUCLEO_PROFILE_ERR_FORMAT;
  }
  if (!valid_command_id(tokens[1]) || !valid_checksum(tokens[checksum_offset])) {
    return NUCLEO_PROFILE_ERR_FORMAT;
  }
  if (!checksum_matches(tokens, count, checksum_offset)) {
    return NUCLEO_PROFILE_ERR_COMMAND;
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
  if (sensor_profile) {
    const char axis_name = tokens[2][0];
    const char *expected_min = (axis_name == 'X') ? "X_MIN" : "Y_MIN";
    const char *expected_max = (axis_name == 'X') ? "X_MAX" : "Y_MAX";
    if ((strcmp(tokens[6], expected_min) != 0) &&
        (strcmp(tokens[6], expected_max) != 0)) return NUCLEO_PROFILE_ERR_AXIS;
    frame->sensor_terminated = 1U;
    frame->termination_sensor = (uint8_t)(axis_name == 'X'
        ? (strcmp(tokens[6], "X_MIN") == 0 ? 0U : 1U)
        : (strcmp(tokens[6], "Y_MIN") == 0 ? 2U : 3U));
    if (strcmp(tokens[7], "controlled") == 0) frame->sensor_stop_mode = 0U;
    else if (strcmp(tokens[7], "immediate") == 0) frame->sensor_stop_mode = 1U;
    else return NUCLEO_PROFILE_ERR_RANGE;
    if (!parse_u64(tokens[8], &frame->sensor_watchdog_us) ||
        (frame->sensor_watchdog_us < 100000ULL) ||
        (frame->sensor_watchdog_us > 3600000000ULL)) {
      return NUCLEO_PROFILE_ERR_RANGE;
    }
  }
  strcpy(frame->checksum, tokens[checksum_offset]);
  for (index = 0U; index < NUCLEO_PROFILE_PHASE_COUNT; index++) {
    size_t offset = phase_offset + index * 7U;
    NucleoProfilePhase *phase = &frame->phases[index];
    if (!parse_u32(tokens[offset], &phase->duration_us) ||
        !parse_u32(tokens[offset + 1U], &phase->end_step) ||
        !parse_u32(tokens[offset + 2U], &phase->start_rate_millihz) ||
        !parse_u32(tokens[offset + 3U], &phase->end_rate_millihz) ||
        !parse_i32(tokens[offset + 4U], &phase->start_accel_millihz_s) ||
        !parse_i32(tokens[offset + 5U], &phase->end_accel_millihz_s) ||
        !parse_i32(tokens[offset + 6U], &phase->jerk_millihz_s2)) {
      return NUCLEO_PROFILE_ERR_RANGE;
    }
    if ((phase->start_rate_millihz > PROFILE_MAX_RATE_MILLIHZ) ||
        (phase->end_rate_millihz > PROFILE_MAX_RATE_MILLIHZ) ||
        ((index > 0U) && (phase->end_step < frame->phases[index - 1U].end_step)) ||
        (phase->end_step > frame->steps)) return NUCLEO_PROFILE_ERR_RANGE;
  }
  if (frame->phases[NUCLEO_PROFILE_PHASE_COUNT - 1U].end_step != frame->steps) {
    return NUCLEO_PROFILE_ERR_RANGE;
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
