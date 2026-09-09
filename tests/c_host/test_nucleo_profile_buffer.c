#include "nucleo_profile_buffer.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static const char *HASH_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
static const char *HASH_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

static void make_line(char *line, const char *id, const char axis, unsigned long sequence, const char *hash)
{
  unsigned int index;
  char phase[96];
  sprintf(line, "PROFILE %s %c 1 6471 %lu %s", id, axis, sequence, hash);
  for (index = 0U; index < 7U; index++) {
    unsigned long end_step = (index == 6U) ? 6471UL : (unsigned long)(index + 1U) * 900UL;
    sprintf(phase, " 1000 %lu 1000 2000 10000 10000 100000", end_step);
    strcat(line, phase);
  }
}

int main(void)
{
  NucleoProfileBuffer buffer;
  NucleoProfileFrame x;
  NucleoProfileFrame y;
  char line[512];

  NucleoProfileBuffer_Init(&buffer);
  assert(buffer.state == NUCLEO_PROFILE_EMPTY);
  assert(NucleoProfileBuffer_Start(&buffer, "move-1") == NUCLEO_PROFILE_ERR_STATE);

  make_line(line, "move-1", 'X', 0UL, HASH_A);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_OK);
  assert(x.axis == 0U && x.steps == 6471U && x.sequence == 0U);
  assert(NucleoProfileBuffer_Stage(&buffer, &x) == NUCLEO_PROFILE_OK);
  assert(NucleoProfileBuffer_Stage(&buffer, &x) == NUCLEO_PROFILE_DUPLICATE);

  make_line(line, "move-1", 'Y', 1UL, HASH_B);
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
  make_line(line, "move-2", 'X', 1UL, HASH_A);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_OK);
  assert(NucleoProfileBuffer_Stage(&buffer, &x) == NUCLEO_PROFILE_ERR_OUT_OF_ORDER);

  make_line(line, "move-2", 'Z', 0UL, HASH_A);
  assert(NucleoProfile_ParseLine(line, &x) == NUCLEO_PROFILE_ERR_AXIS);
  puts("nucleo_profile_buffer host tests passed");
  return 0;
}
