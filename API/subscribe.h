#ifndef  __SUBSCRIBE_H__
#define  __SUBSCRIBE_H__

/* UART5 extended-prefix (0xCC 0xDE) subscription producer.
 *
 * Implements the firmware-side of HANDOFF §5 item 1: host sends a list of
 * (address:uint32 LE, size:uint16 LE) tuples on UART5; firmware validates
 * each tuple against the SRAM/CCM allowlist, packs the requested bytes
 * from those addresses, and replies with either a 0x07 tuple reply or a
 * 0x7F error reply. Read-only observation: nothing in this module writes
 * to the requested addresses.
 *
 * Pinned byte layout (FC -> host reply frame, frame_type 0x07):
 *
 *   offset  width  field                                         value
 *   0       1      SYNC_HI                                       0xAA
 *   1       1      SYNC_LO                                       0xBB
 *   2       1      FRAME_TYPE                                    0x07
 *   3       1      LEN_HI                                        (payload length >> 8) & 0xFF
 *   4       1      LEN_LO                                        (payload length) & 0xFF
 *   5       1      MAX_NUM_BASIS                                 tuple count
 *   6       6*N+sum(size_i)   payload: N tuples of (address:uint32 LE,
 *                          size:uint16 LE, value:size bytes)
 *   trailer CRC8 XOR over [FRAME_TYPE, LEN_HI, LEN_LO, MAX_NUM_BASIS, payload...]
 *
 * Pinned byte layout (FC -> host error-reply frame, frame_type 0x7F):
 *
 *   offset  width  field                                         value
 *   0       1      SYNC_HI                                       0xAA
 *   1       1      SYNC_LO                                       0xBB
 *   2       1      FRAME_TYPE                                    0x7F
 *   3       1      LEN_HI                                        (payload length >> 8) & 0xFF
 *   4       1      LEN_LO                                        (payload length) & 0xFF
 *   5       1      MAX_NUM_BASIS                                 echo of requested tuple count
 *   6       ...    payload: UTF-8 string, NUL-terminated, <= 240 bytes
 *   trailer CRC8 XOR over [FRAME_TYPE, LEN_HI, LEN_LO, MAX_NUM_BASIS, payload...]
 *
 * Constraints:
 *  - Subscriptions are read-only; nothing here writes back to the address.
 *  - max 32 tuples per request (subscribe.h MAX_TUPLES).
 *  - Address allowlist: SRAM 0x20000000..0x2001FFFF and CCM 0x10000000..0x1000FFFF.
 *    Bounds derived from OBJ/JX_FLY.map RW_IRAM1 region (Max 0x20000) and
 *    STM32F407 datasheet (CCM 64 KB at 0x10000000).
 *  - size must be in {1, 2, 4}; address must be aligned to size.
 *  - Send_Task stack is 500 words (2 kB); no stack locals > 32 B. Reply
 *    and error buffers are file-scope statics in API/subscribe.c.
 */

#include "stm32f4xx.h"

#define SUBSCRIBE_MAX_TUPLES       32U
#define SUBSCRIBE_FRAME_TYPE_REPLY  0x07U
#define SUBSCRIBE_FRAME_TYPE_ERROR 0x7FU
#define SUBSCRIBE_CMD               0x20U
/* SRAM bound: STM32F407 has 128 KB SRAM starting at 0x20000000; the
 * linker's RW_IRAM1 region is `Max: 0x00020000` (= 128 KB). Verified
 * against OBJ/JX_FLY.map (RW_IRAM1 Base 0x20000000, Size 0x0001b388,
 * Max 0x00020000). */
#define SUBSCRIBE_ADDR_SRAM_LO      0x20000000U
#define SUBSCRIBE_ADDR_SRAM_HI      0x2001FFFFU
/* CCM bound: STM32F407 has 64 KB CCM at 0x10000000..0x1000FFFF. The
 * current link map places no symbols there, but the physical address
 * range is valid; reading from it returns whatever happens to be
 * physically present (typically zero, not a HardFault). */
#define SUBSCRIBE_ADDR_CCM_LO       0x10000000U
#define SUBSCRIBE_ADDR_CCM_HI       0x1000FFFFU

typedef struct {
    uint32_t address;
    uint16_t size;
} Subscribe_Tuple_t;

typedef struct {
    uint8_t         count;
    Subscribe_Tuple_t tuples[SUBSCRIBE_MAX_TUPLES];
} Subscribe_Request_t;

/* Validate one tuple. Returns 1 on accept, 0 on reject (writes a brief
 * reason into `err_out` up to err_cap bytes incl. NUL). */
uint8_t Subscribe_ValidateTuple(uint32_t address, uint16_t size,
                                char* err_out, uint16_t err_cap);

/* Parse a host->FC request frame into `req`. Frame layout:
 *   [0xCC] [0xDE] [CMD=0x20] [LEN_HI] [LEN_LO] [MAX_NUM_BASIS]
 *   [payload: count * 6 bytes]
 *   [CRC8 XOR]
 * Returns 1 on accept, 0 on reject. On reject, `err_out` is filled.
 *
 * `buf` is the raw staging buffer including the leading 0xCC 0xDE sync
 * bytes; `len` is the full frame length.
 */
uint8_t Subscribe_ParseRequest(const uint8_t* buf, uint16_t len,
                               Subscribe_Request_t* req,
                               char* err_out, uint16_t err_cap);

/* Build the 0x07 reply into `out` (file-scope static in subscribe.c).
 * Caller owns the buffer between DMA arming and DMA completion. Writes
 * the total frame length to `out_len`. Returns 1 on success, 0 if
 * `out_cap` is too small (won't happen with the 512 B file-scope
 * buffer — kept for defensive coding).
 */
uint8_t Subscribe_BuildReply(const Subscribe_Request_t* req,
                             uint8_t* out, uint16_t out_cap,
                             uint16_t* out_len);

/* Build the 0x7F error reply into `out`. `count` is echoed into the
 * MAX_NUM_BASIS slot so the host can correlate the error with its
 * request. `msg` is a NUL-terminated C string <= 240 bytes (truncated
 * silently if longer).
 */
uint8_t Subscribe_BuildError(const char* msg, uint8_t count,
                             uint8_t* out, uint16_t out_cap,
                             uint16_t* out_len);

#endif