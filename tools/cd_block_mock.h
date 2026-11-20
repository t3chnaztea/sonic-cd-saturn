#ifndef SCD_CD_BLOCK_MOCK_H
#define SCD_CD_BLOCK_MOCK_H
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include "cd-command-api.h"
#ifndef __unused
#define __unused __attribute__((unused))
#endif
extern uint16_t mock_registers[32];
#define CD_BLOCK(offset) (offset)
#define MEMORY_READ(bits,address) (mock_registers[(address)/2])
#define MEMORY_WRITE_AND(bits,address,value) (mock_registers[(address)/2]&=(value))
#define MEMORY_WRITE_OR(bits,address,value) (mock_registers[(address)/2]|=(value))
#endif
