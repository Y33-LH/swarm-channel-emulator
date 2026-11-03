#ifndef SWARM_PAYLOAD_DRIVER_H
#define SWARM_PAYLOAD_DRIVER_H
#define SWARM_BASE 0x43C00000U
#define SWARM_PL_VERSION 0x000d0004U
#define SWARM_BODY_BYTES 96U
#define SWARM_PAYLOAD_MAX 64U
enum swarm_register {
 SW_CONTROL=0x00,SW_TX_LEN=0x04,SW_TAG=0x08,SW_FLAGS=0x0c,
 SW_STATUS=0x10,SW_RESULT_CODE=0x14,SW_RX_LEN=0x18,SW_RX_FRAME_BYTES=0x1c,
 SW_TX_BITS=0x20,SW_RX_BITS=0x24,SW_CYCLES=0x28,SW_GENERATION=0x2c,
 SW_TIMEOUT=0x30,SW_LAST_ERROR=0x34,SW_RESULT_TAG=0x38,SW_VERSION=0x3c,
 SW_GAIN=0x40,SW_SIGMA=0x44,SW_HOLD_RX=0x48,SW_CRC_PAIR=0x4c,
 SW_START_OFFSET=0x50,SW_PHASE=0x54,SW_SEED=0x58,SW_PHASE_STEP=0x5c,
 SW_SUPPRESS=0x60,SW_CAPTURES=0x64,SW_SAMPLES=0x68,SW_SYNC_ERRORS=0x6c,
 SW_PATH_DELAY=0x70,SW_FRAME_CLASS=0x74,SW_ECHO_GAIN=0x78,SW_ECHO_DELAY=0x7c,
 SW_ECHO_PHASE=0x80,SW_ECHO_STEP=0x84,SW_GAIN_DELTA=0x88,SW_ECHO_GAIN_DELTA=0x8c,
 SW_FINAL_RNG=0x90,SW_FINAL_PHASE=0x94,SW_FINAL_ECHO_PHASE=0x98,SW_CLIPPING=0x9c,
 SW_BIT_ERRORS=0xa0,SW_COMPARED_BITS=0xa4,SW_TRAIN_I=0xa8,SW_TRAIN_Q=0xac,
 SW_TRAIN_ENERGY_LO=0xb0,SW_TRAIN_ENERGY_HI=0xb4,SW_TRAIN_COUNT=0xb8,
 SW_TX_BUFFER=0x100,SW_RX_BUFFER=0x200
};
enum swarm_api_error {SW_EOK=0,SW_EBUSY=1,SW_EPENDING=2,SW_ELENGTH=3,SW_EINCOMPLETE=4,SW_EHEADER=5,SW_ECOMMAND=6,SW_EREADONLY=7,SW_EADDRESS=8,SW_ENORESULT=9,SW_ERANGE=10};
enum swarm_result {SW_OK=0,SW_CRC_FAIL=1,SW_FORMAT_FAIL=2,SW_ABORTED=3,SW_TIMEOUT_RESULT=4,SW_NO_FRAME=5,SW_SYNC_FAIL=6};
/* Single caller owns this one-slot endpoint. Caller constructs 96 body bytes;
 * hardware creates CRC. Must release a terminal result before next prepare. */
unsigned sw_payload_prepare(const unsigned char body[96],unsigned length,unsigned tag);
unsigned sw_payload_start(void);
/* Returns 1 for any terminal result (inspect STATUS/RESULT_CODE), 0 if the
 * ARM watchdog expires; on ARM watchdog it issues ABORT to recover hardware. */
int sw_payload_wait(unsigned timeout_ms);
/* Copies all 96 actual RX bytes, only if DONE and RX_VALID; returns API error. */
unsigned sw_payload_read(unsigned char body[96]);
unsigned sw_payload_release(void);
void sw_payload_abort(void);
#endif
