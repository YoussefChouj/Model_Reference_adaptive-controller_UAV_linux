/**
 * @module  subscribe.c
 * @subsystem  comm
 * @depends  subscribe.h
 * @owns  UART5 address-subscription request parser and reply builder
 * @caution  byte layout is the firmware side of the wire contract pinned in
 *           .agent_contracts/uart5_livewatch_path/spec.md Context and mirrored
 *           in transport.py:_build_request / _decode_tuples
 */

#include "subscribe.h"
#include "usart5.h"   /* Uart5_Subscribe_TxSend */

/* File-scope reply buffer. Send_Task stack is 500 words (2 kB); the worst-
 * case reply is 6 (header) + 32 * (6 + 4) (tuples with 4-byte value) + 1 (CRC)
 * = 327 B. tx_buf[512] fits comfortably. */
static uint8_t tx_buf[512];
static uint16_t tx_len;

/* File-scope error-reply buffer. Worst case: 240-byte string + 7 header/CRC
 * = 247 B. err_buf[256] fits comfortably. */
static uint8_t err_buf[256];
static uint16_t err_len;

/* Pending request stashed by Subscribe_ParseRequest; consumed by
 * Subscribe_BuildReply in the same Send_Task cycle. File-scope because
 * Subscribe_Request_t is 1 + 32 * 6 = 193 B; Send_Task stack is 500 words / 2 kB. */
static Subscribe_Request_t s_pending;

/* File-scope scratch buffer for Subscribe_BuildError's CAP-N truncate. The
 * 240-byte error payload cap (per spec) plus a NUL slot is 241 B; putting
 * this on Send_Task's 500-word stack would risk overflow during a 32-tuple
 * rejection (worst-case stack frame: 193 B req + 241 B truncated_msg + 32 B
 * err + housekeeping). */
static uint8_t err_truncate_tmp[241];

static uint8_t XorCrc(const uint8_t* data, uint16_t len)
{
    uint8_t crc = 0U;
    uint16_t i;
    for (i = 0U; i < len; i++) {
        crc ^= data[i];
    }
    return crc;
}

/* Copy a NUL-terminated ASCII/UTF-8 string into `dst` (up to dst_cap
 * bytes). NUL terminator is copied if dst_cap > 0. No formatting. */
static uint16_t CopyStr(uint8_t* dst, const char* src, uint16_t dst_cap)
{
    uint16_t i;
    if (dst_cap == 0U) {
        return 0U;
    }
    for (i = 0U; i < dst_cap - 1U; i++) {
        if (src[i] == '\0') {
            break;
        }
        dst[i] = (uint8_t)src[i];
    }
    dst[i] = 0U;
    return (uint16_t)(i + 1U);
}

uint8_t Subscribe_ValidateTuple(uint32_t address, uint16_t size,
                                char* err_out, uint16_t err_cap)
{
    uint8_t in_sram;
    uint8_t in_ccm;

    /* Size must be in {1, 2, 4}. */
    if ((size != 1U) && (size != 2U) && (size != 4U)) {
        (void)CopyStr((uint8_t*)err_out, "E:size not in {1,2,4}", err_cap);
        return 0U;
    }
    /* Address must be aligned to size. STM32 unaligned reads can HardFault. */
    if ((address % (uint32_t)size) != 0U) {
        (void)CopyStr((uint8_t*)err_out, "E:addr not aligned to size", err_cap);
        return 0U;
    }
    in_sram = (address >= SUBSCRIBE_ADDR_SRAM_LO) &&
              (address <= SUBSCRIBE_ADDR_SRAM_HI);
    in_ccm  = (address >= SUBSCRIBE_ADDR_CCM_LO) &&
              (address <= SUBSCRIBE_ADDR_CCM_HI);
    if (!in_sram && !in_ccm) {
        /* Diagnostic: include the offending address in hex. Keep the
         * message short — error payload is capped at 240 B. */
        (void)CopyStr((uint8_t*)err_out, "E:addr outside SRAM/CCM", err_cap);
        return 0U;
    }
    /* Read+size upper-bound: address + size must not wrap or exceed the
     * upper end of the matched region. The simple form is "address+size-1
     * in range"; the (size-1) check avoids the wrap corner case at the
     * top of the address space. */
    if ((size > 0U) && (address > (UINT32_MAX - (uint32_t)size))) {
        (void)CopyStr((uint8_t*)err_out, "E:addr+size wrap", err_cap);
        return 0U;
    }
    if (in_sram &&
        ((address + (uint32_t)size - 1U) > SUBSCRIBE_ADDR_SRAM_HI)) {
        (void)CopyStr((uint8_t*)err_out, "E:tuple crosses SRAM end", err_cap);
        return 0U;
    }
    if (in_ccm &&
        ((address + (uint32_t)size - 1U) > SUBSCRIBE_ADDR_CCM_HI)) {
        (void)CopyStr((uint8_t*)err_out, "E:tuple crosses CCM end", err_cap);
        return 0U;
    }
    if (err_out != 0) {
        err_out[0] = '\0';
    }
    return 1U;
}

uint8_t Subscribe_ParseRequest(const uint8_t* buf, uint16_t len,
                               Subscribe_Request_t* req,
                               char* err_out, uint16_t err_cap)
{
    uint8_t i;
    uint16_t payload_len;
    uint8_t count;
    uint16_t expected_frame_len;
    uint8_t calc_crc;
    uint16_t base;
    uint32_t address;
    uint16_t size;

    if (req == 0) {
        (void)CopyStr((uint8_t*)err_out, "E:null req", err_cap);
        return 0U;
    }
    req->count = 0U;
    /* Minimum frame: 6 header + 0 payload + 1 CRC = 7 bytes. */
    if (len < 7U) {
        (void)CopyStr((uint8_t*)err_out, "E:truncated frame", err_cap);
        return 0U;
    }
    if (buf[0] != 0xCCU || buf[1] != 0xDEU) {
        (void)CopyStr((uint8_t*)err_out, "E:bad sync", err_cap);
        return 0U;
    }
    if (buf[2] != SUBSCRIBE_CMD) {
        (void)CopyStr((uint8_t*)err_out, "E:bad cmd", err_cap);
        return 0U;
    }
    payload_len = (uint16_t)(((uint16_t)buf[3] << 8) | (uint16_t)buf[4]);
    if ((payload_len % 6U) != 0U) {
        (void)CopyStr((uint8_t*)err_out, "E:bad len", err_cap);
        return 0U;
    }
    count = buf[5];
    if (count > SUBSCRIBE_MAX_TUPLES) {
        (void)CopyStr((uint8_t*)err_out, "E:too many tuples", err_cap);
        return 0U;
    }
    if ((uint16_t)count * 6U != payload_len) {
        (void)CopyStr((uint8_t*)err_out, "E:len vs count mismatch", err_cap);
        return 0U;
    }
    expected_frame_len = (uint16_t)(6U + payload_len + 1U);
    if (len < expected_frame_len) {
        (void)CopyStr((uint8_t*)err_out, "E:truncated frame", err_cap);
        return 0U;
    }
    calc_crc = XorCrc(&buf[2], (uint16_t)(expected_frame_len - 3U));
    if (calc_crc != buf[expected_frame_len - 1U]) {
        (void)CopyStr((uint8_t*)err_out, "E:CRC mismatch", err_cap);
        return 0U;
    }
    /* Walk the tuple payload. */
    for (i = 0U; i < count; i++) {
        base = (uint16_t)(6U + (uint16_t)i * 6U);
        /* Little-endian un-pack without relying on memcpy alignment:
         * STM32 unaligned 32-bit reads can fault on some compilers. */
        address = ((uint32_t)buf[base]) |
                  ((uint32_t)buf[base + 1U] << 8) |
                  ((uint32_t)buf[base + 2U] << 16) |
                  ((uint32_t)buf[base + 3U] << 24);
        size     = ((uint16_t)buf[base + 4U]) |
                   ((uint16_t)buf[base + 5U] << 8);
        if (Subscribe_ValidateTuple(address, size, err_out, err_cap) == 0U) {
            return 0U;
        }
        req->tuples[i].address = address;
        req->tuples[i].size    = size;
    }
    req->count = count;
    if (err_out != 0) {
        err_out[0] = '\0';
    }
    return 1U;
}

uint8_t Subscribe_BuildReply(const Subscribe_Request_t* req,
                             uint8_t* out, uint16_t out_cap,
                             uint16_t* out_len)
{
    uint8_t i;
    uint16_t idx;
    uint16_t payload_len;
    uint8_t count = req->count;
    /* Compute payload length first to bounds-check the output. */
    payload_len = 0U;
    for (i = 0U; i < count; i++) {
        payload_len = (uint16_t)(payload_len + 6U + req->tuples[i].size);
    }
    if ((uint16_t)(6U + payload_len + 1U) > out_cap) {
        return 0U;
    }
    /* Header. */
    out[0] = 0xAAU;
    out[1] = 0xBBU;
    out[2] = SUBSCRIBE_FRAME_TYPE_REPLY;
    out[3] = (uint8_t)((payload_len >> 8) & 0xFFU);
    out[4] = (uint8_t)(payload_len & 0xFFU);
    out[5] = count;
    idx = 6U;
    /* Tuples: address LE, size LE, value bytes (size many). */
    for (i = 0U; i < count; i++) {
        uint32_t a = req->tuples[i].address;
        uint16_t s = req->tuples[i].size;
        uint8_t k;
        out[idx]     = (uint8_t)(a & 0xFFU);
        out[idx + 1U] = (uint8_t)((a >> 8) & 0xFFU);
        out[idx + 2U] = (uint8_t)((a >> 16) & 0xFFU);
        out[idx + 3U] = (uint8_t)((a >> 24) & 0xFFU);
        out[idx + 4U] = (uint8_t)(s & 0xFFU);
        out[idx + 5U] = (uint8_t)((s >> 8) & 0xFFU);
        idx = (uint16_t)(idx + 6U);
        /* Read `s` bytes from address `a`. Byte-by-byte read keeps us
         * unaligned-safe. Compiler ARMCC V5.06 may synthesise a multi-
         * byte load from an aligned address, which is fine — but a
         * misaligned read on a hardfaulting peripheral map is what we
         * want to avoid, and the validator above already rejected any
         * unaligned (address, size) pair. */
        for (k = 0U; k < s; k++) {
            const uint8_t* p = (const uint8_t*)(a + (uint32_t)k);
            out[idx] = *p;
            idx = (uint16_t)(idx + 1U);
        }
    }
    /* CRC8 XOR over [frame_type, LEN_HI, LEN_LO, MAX_NUM_BASIS, payload...]. */
    out[idx] = XorCrc(&out[2], (uint16_t)(idx - 2U));
    idx = (uint16_t)(idx + 1U);
    *out_len = idx;
    return 1U;
}

uint8_t Subscribe_BuildError(const char* msg, uint8_t count,
                             uint8_t* out, uint16_t out_cap,
                             uint16_t* out_len)
{
    uint16_t idx;
    uint16_t payload_len;
    uint16_t str_len;
    uint16_t truncated_cap = sizeof(err_truncate_tmp);
    /* Cap string at 240 bytes per spec. */
    str_len = CopyStr(err_truncate_tmp, msg, truncated_cap);
    if (str_len > 240U) {
        str_len = 240U;
        err_truncate_tmp[239U] = 0U;
    }
    payload_len = str_len;
    if ((uint16_t)(6U + payload_len + 1U) > out_cap) {
        return 0U;
    }
    out[0] = 0xAAU;
    out[1] = 0xBBU;
    out[2] = SUBSCRIBE_FRAME_TYPE_ERROR;
    out[3] = (uint8_t)((payload_len >> 8) & 0xFFU);
    out[4] = (uint8_t)(payload_len & 0xFFU);
    out[5] = count;
    idx = 6U;
    {
        uint16_t k;
        for (k = 0U; k < str_len; k++) {
            out[idx] = err_truncate_tmp[k];
            idx = (uint16_t)(idx + 1U);
        }
    }
    out[idx] = XorCrc(&out[2], (uint16_t)(idx - 2U));
    idx = (uint16_t)(idx + 1U);
    *out_len = idx;
    return 1U;
}

/* Build a reply from the staged IRQ-side frame and hand it off to the
 * DMA. Called from TASK/send_data.c (Send_Task context) AFTER the live
 * telemetry DMA has completed. The reply is fired on a *second* DMA
 * turn so the existing A/B stream is unchanged. */
void Uart5_Subscribe_HandleRequest(void)
{
    Subscribe_Request_t* req = &s_pending;
    char err[32];

    if (UA5RxSubscribePending == 0U) {
        return;
    }
    if (Subscribe_ParseRequest(UA5RxSubscribeBuf, UA5RxSubscribeLen,
                               req, err, sizeof(err)) != 1U) {
        /* Validation failed -> build a 0x7F error reply echoing the
         * tuple count we observed (or 0 if we never got that far). */
        uint8_t count = 0U;
        if (UA5RxSubscribeLen >= 6U) {
            count = UA5RxSubscribeBuf[5];
        }
        if (Subscribe_BuildError(err, count, err_buf,
                                 (uint16_t)sizeof(err_buf),
                                 &err_len) != 1U) {
            /* Should not happen with err_buf[256] and a 31-byte err[]. */
            UA5RxSubscribePending = 0U;
            return;
        }
        Uart5_Subscribe_TxSend(err_buf, err_len);
    } else {
        if (Subscribe_BuildReply(req, tx_buf, (uint16_t)sizeof(tx_buf),
                                 &tx_len) != 1U) {
            (void)Subscribe_BuildError("E:reply too large", req->count,
                                       err_buf, (uint16_t)sizeof(err_buf),
                                       &err_len);
            Uart5_Subscribe_TxSend(err_buf, err_len);
        } else {
            Uart5_Subscribe_TxSend(tx_buf, tx_len);
        }
    }
    UA5RxSubscribePending = 0U;
}