#ifndef NUCLEO_PROFILE_BUFFER_H
#define NUCLEO_PROFILE_BUFFER_H

#include <stddef.h>
#include <stdint.h>

#define NUCLEO_PROFILE_COMMAND_ID_MAX 64U
#define NUCLEO_PROFILE_PHASE_COUNT 7U
#define NUCLEO_PROFILE_BUFFER_CAPACITY 2U

typedef enum {
  NUCLEO_PROFILE_EMPTY = 0,
  NUCLEO_PROFILE_BUFFERED,
  NUCLEO_PROFILE_RUNNING,
  NUCLEO_PROFILE_COMPLETE,
  NUCLEO_PROFILE_SAFETY_STOP,
  NUCLEO_PROFILE_FAILED
} NucleoProfileState;

typedef enum {
  NUCLEO_PROFILE_OK = 0,
  NUCLEO_PROFILE_DUPLICATE,
  NUCLEO_PROFILE_ERR_FORMAT,
  NUCLEO_PROFILE_ERR_AXIS,
  NUCLEO_PROFILE_ERR_RANGE,
  NUCLEO_PROFILE_ERR_COMMAND,
  NUCLEO_PROFILE_ERR_OUT_OF_ORDER,
  NUCLEO_PROFILE_ERR_FULL,
  NUCLEO_PROFILE_ERR_STATE
} NucleoProfileResult;

typedef struct {
  uint32_t duration_us;
  int32_t jerk_milli_mm_s3;
} NucleoProfilePhase;

typedef struct {
  char command_id[NUCLEO_PROFILE_COMMAND_ID_MAX + 1U];
  uint8_t axis;
  uint8_t direction;
  uint32_t steps;
  uint32_t sequence;
  char checksum[65U];
  NucleoProfilePhase phases[NUCLEO_PROFILE_PHASE_COUNT];
} NucleoProfileFrame;

typedef struct {
  NucleoProfileState state;
  char command_id[NUCLEO_PROFILE_COMMAND_ID_MAX + 1U];
  uint32_t count;
  NucleoProfileFrame frames[NUCLEO_PROFILE_BUFFER_CAPACITY];
} NucleoProfileBuffer;

void NucleoProfileBuffer_Init(NucleoProfileBuffer *buffer);
NucleoProfileResult NucleoProfile_ParseLine(const char *line,
                                            NucleoProfileFrame *frame);
NucleoProfileResult NucleoProfileBuffer_Stage(NucleoProfileBuffer *buffer,
                                              const NucleoProfileFrame *frame);
NucleoProfileResult NucleoProfileBuffer_Start(NucleoProfileBuffer *buffer,
                                              const char *command_id);
void NucleoProfileBuffer_SafetyStop(NucleoProfileBuffer *buffer);

#endif
