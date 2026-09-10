#include "nucleo_profile_buffer.h"
#include "nucleo_sha256.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void make_line(char *line, const char *id, const char axis, unsigned long sequence)
{
  unsigned int index;
  char phase[96];
  char header[128];
  char phases[768] = "";
  char canonical[896];
  char hash[65];
  sprintf(header, "PROFILE %s %c 1 6471 %lu", id, axis, sequence);
  for (index = 0U; index < 7U; index++) {
    unsigned long end_step = (index == 6U) ? 6471UL : (unsigned long)(index + 1U) * 900UL;
    sprintf(phase, " 1000 %lu 1000 2000 10000 10000 100000", end_step);
    strcat(phases, phase);
  }
  sprintf(canonical, "%s%s", header, phases);
  NucleoSha256_Hex((const uint8_t *)canonical, strlen(canonical), hash);
  sprintf(line, "%s %s%s", header, hash, phases);
}

static void make_sensor_line(char *line, const char *sensor, const char *mode,
                             unsigned long long watchdog)
{
  unsigned int index;
  char phase[96];
  char header[192];
  char phases[768] = "";
  char canonical[960];
  char hash[65];
  sprintf(header, "SENSOR_PROFILE seek-x X 1 6471 0 %s %s %llu",
          sensor, mode, watchdog);
  for (index = 0U; index < 7U; index++) {
    unsigned long end_step = (index == 6U) ? 6471UL : (unsigned long)(index + 1U) * 900UL;
    sprintf(phase, " 1000 %lu 1000 2000 10000 10000 100000", end_step);
    strcat(phases, phase);
  }
  sprintf(canonical, "%s%s", header, phases);
  NucleoSha256_Hex((const uint8_t *)canonical, strlen(canonical), hash);
  sprintf(line, "%s %s%s", header, hash, phases);
}

int main(void)
{
  NucleoProfileBuffer buffer;
  NucleoProfileFrame x;
  NucleoProfileFrame y;
  char line[512];
  char digest[65];

  NucleoSha256_Hex((const uint8_t *)"abc", 3U, digest);
  assert(strcmp(digest, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") == 0);

  NucleoProfileBuffer_Init(&buffer);
  assert(buffer.state == NUCLEO_PROFILE_EMPTY);
  assert(NucleoProfileBuffer_Start(&buffer, "move-1") == NUCLEO_PROFILE_ERR_STATE);

  make_line(line, "move-1", 'X', 0UL);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_OK);
  assert(x.axis == 0U && x.steps == 6471U && x.sequence == 0U);
  line[strlen(line) - 1U] = '1';
  assert(NucleoProfile_ParseLine(line, &y) == NUCLEO_PROFILE_ERR_COMMAND);
  make_line(line, "move-1", 'X', 0UL);
  assert(NucleoProfileBuffer_Stage(&buffer, &x) == NUCLEO_PROFILE_OK);
  assert(NucleoProfileBuffer_Stage(&buffer, &x) == NUCLEO_PROFILE_DUPLICATE);

  make_line(line, "move-1", 'Y', 1UL);
  assert(NucleoProfile_ParseLine(line, &y) == NUCLEO_PROFILE_OK);
  assert(NucleoProfileBuffer_Stage(&buffer, &y) == NUCLEO_PROFILE_OK);
  assert(buffer.count == 2U);
  assert(NucleoProfileBuffer_Start(&buffer, "wrong") == NUCLEO_PROFILE_ERR_COMMAND);
  assert(NucleoProfileBuffer_Start(&buffer, "move-1") == NUCLEO_PROFILE_OK);
  assert(buffer.state == NUCLEO_PROFILE_RUNNING);

  NucleoProfileBuffer_SafetyStop(&buffer);
  assert(buffer.state == NUCLEO_PROFILE_SAFETY_STOP);
  assert(NucleoProfileBuffer_Stage(&buffer, &x) == NUCLEO_PROFILE_ERR_STATE);

  NucleoProfileBuffer_Init(&buffer);
  make_line(line, "move-2", 'X', 1UL);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_OK);
  assert(NucleoProfileBuffer_Stage(&buffer, &x) == NUCLEO_PROFILE_ERR_OUT_OF_ORDER);

  make_line(line, "move-2", 'Z', 0UL);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_ERR_AXIS);

  make_sensor_line(line, "X_MAX", "controlled", 60000000ULL);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_OK);
  assert(x.sensor_terminated == 1U && x.termination_sensor == 1U);
  assert(x.sensor_stop_mode == 0U && x.sensor_watchdog_us == 60000000ULL);
  make_sensor_line(line, "Y_MAX", "controlled", 60000000ULL);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_ERR_AXIS);
  make_sensor_line(line, "X_MAX", "coast", 60000000ULL);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_ERR_RANGE);
  make_sensor_line(line, "X_MAX", "immediate", 99999ULL);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_ERR_RANGE);
  puts("nucleo_profile_buffer host tests passed");
  return 0;
}
