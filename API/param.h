#ifndef PARAM_H
#define PARAM_H

#include <stdint.h>

/* Param value type tags. */
#define PARAM_TYPE_FLOAT  1U
#define PARAM_TYPE_UINT8  2U
#define PARAM_TYPE_INT32  3U

/* Status codes returned by Param_Set / Param_Get. */
#define PARAM_STATUS_OK         0U
#define PARAM_STATUS_NOT_FOUND  1U

#define PARAM_MAX_ENTRIES  32U
#define PARAM_NAME_LEN     32U   /* fixed-width name field, NUL-padded */

/* A row in the firmware param registry. */
typedef struct {
    const char* name;            /* e.g. "e_deadzone" */
    volatile void* ptr;         /* live pointer to the variable */
    uint8_t      size_bytes;   /* 4 for float, 1 for uint8_t, 4 for int32 */
    uint8_t      type;          /* PARAM_TYPE_* */
} ParamEntry;

/* Initial population strategy: hard-curated list drawn from
 * MRAC_AxisConfig_t fields (agent-02 writable registry) and globals.
 * Codegen from YAML/JSON manifest is a future spec. */
extern ParamEntry g_param_registry[PARAM_MAX_ENTRIES];
extern uint16_t  g_param_count;

void Param_Init(void);

/* Returns PARAM_STATUS_OK on success, PARAM_STATUS_NOT_FOUND if name
 * is not in the registry. */
uint8_t Param_Set(const char* name, float value);

/* Fills *out_value and returns PARAM_STATUS_OK on success.
 * Returns PARAM_STATUS_NOT_FOUND if name is not in the registry. */
uint8_t Param_Get(const char* name, float* out_value);

#endif
