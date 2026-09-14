#ifndef NUCLEO_SHA256_H
#define NUCLEO_SHA256_H

#include <stddef.h>
#include <stdint.h>

void NucleoSha256_Hex(const uint8_t *data, size_t length, char output[65]);

#endif
