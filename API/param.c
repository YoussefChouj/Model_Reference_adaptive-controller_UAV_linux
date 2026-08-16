#include "param.h"
#include "mrac.h"
#include <string.h>
#include <stdio.h>

/* MRAC config rows — declared extern in mrac.h */
extern MRAC_AxisConfig_t mrac_config_pitch;
extern MRAC_AxisConfig_t mrac_config_roll;
extern MRAC_AxisConfig_t mrac_config_yaw;
extern MRAC_AxisConfig_t mrac_config_z;

/* Registry table — file-scope (.bss), zero-initialised. */
static ParamEntry s_registry[PARAM_MAX_ENTRIES];
ParamEntry g_param_registry[PARAM_MAX_ENTRIES];   /* extern alias */
uint16_t  g_param_count = 0U;

/* Forward declarations for setters/getters so the macro below is clean. */
static void set_float(float* dst, float v);
static void get_float(const volatile void* src, float* out);

/* Helper: null-terminated name comparison (safe against non-null-terminated wire names). */
static uint8_t name_match(const char* reg_name, const char* wire_name, uint16_t wire_len)
{
    uint16_t i;
    /* Walk reg_name and wire_name in lockstep; stop at first NUL or PARAM_NAME_LEN. */
    for (i = 0U; i < PARAM_NAME_LEN; i++) {
        if (i >= wire_len) {
            /* wire ran out — only a NUL in reg_name past this point is a match. */
            return (reg_name[i] == '\0') ? 1U : 0U;
        }
        if (reg_name[i] != wire_name[i]) {
            return 0U;
        }
        if (reg_name[i] == '\0') {
            return 1U;   /* both hit NUL — exact match */
        }
    }
    return 0U;
}

/* Helper: copy a float from wire bytes (LE) into a float, then write to dst. */
static void set_float(float* dst, float v)
{
    *dst = v;
}

static void get_float(const volatile void* src, float* out)
{
    *out = *(const volatile float*)src;
}

/* Populate one registry row. Advances g_param_count. */
static void reg_add(const char* name, volatile void* ptr, uint8_t size_bytes, uint8_t type)
{
    if (g_param_count >= PARAM_MAX_ENTRIES) {
        return;   /* silently refuse overflow — keep table stable */
    }
    s_registry[g_param_count].name       = name;
    s_registry[g_param_count].ptr        = ptr;
    s_registry[g_param_count].size_bytes = size_bytes;
    s_registry[g_param_count].type      = type;
    /* also populate the extern alias */
    g_param_registry[g_param_count] = s_registry[g_param_count];
    g_param_count++;
}

void Param_Init(void)
{
    uint16_t i;
    /* Reset count first so repeated calls are idempotent. */
    g_param_count = 0U;
    for (i = 0U; i < PARAM_MAX_ENTRIES; i++) {
        g_param_registry[i].name = 0;
        g_param_registry[i].ptr  = 0;
    }

    /* Axis-indexed — What_lower_limit[0] per axis. */
    reg_add("mrac_state.pitch.What_lower_limit[0]",
            (volatile void*)&mrac_config_pitch.What_lower_limit[0],
            4U, PARAM_TYPE_FLOAT);
    reg_add("mrac_state.roll.What_lower_limit[0]",
            (volatile void*)&mrac_config_roll.What_lower_limit[0],
            4U, PARAM_TYPE_FLOAT);
    reg_add("mrac_state.yaw.What_lower_limit[0]",
            (volatile void*)&mrac_config_yaw.What_lower_limit[0],
            4U, PARAM_TYPE_FLOAT);
    reg_add("mrac_state.z.What_lower_limit[0]",
            (volatile void*)&mrac_config_z.What_lower_limit[0],
            4U, PARAM_TYPE_FLOAT);

    /* MRAC axis tunable struct fields. */
    reg_add("e_deadzone", (volatile void*)&mrac_config_pitch.e_deadzone, 4U, PARAM_TYPE_FLOAT);
    reg_add("e_freeze",   (volatile void*)&mrac_config_pitch.e_freeze,   4U, PARAM_TYPE_FLOAT);

    /* Sigma leakage per axis (mrac.c MRAC_Init sets sigma = 0.01 for all axes). */
    reg_add("sigma_pitch", (volatile void*)&mrac_config_pitch.sigma, 4U, PARAM_TYPE_FLOAT);
    reg_add("sigma_roll",  (volatile void*)&mrac_config_roll.sigma,  4U, PARAM_TYPE_FLOAT);
    reg_add("sigma_yaw",    (volatile void*)&mrac_config_yaw.sigma,   4U, PARAM_TYPE_FLOAT);
}

/* Returns PARAM_STATUS_OK on success, PARAM_STATUS_NOT_FOUND if not found.
 * No type coercion in v0 — if the name exists the write goes through. */
uint8_t Param_Set(const char* name, float value)
{
    uint16_t i;
    for (i = 0U; i < g_param_count; i++) {
        if (name_match(s_registry[i].name, name, PARAM_NAME_LEN)) {
            volatile uint8_t*  b;
            switch (s_registry[i].type) {
                case PARAM_TYPE_FLOAT:
                    set_float((float*)s_registry[i].ptr, value);
                    return PARAM_STATUS_OK;
                case PARAM_TYPE_UINT8:
                    b = (volatile uint8_t*)s_registry[i].ptr;
                    *b = (uint8_t)value;
                    return PARAM_STATUS_OK;
                case PARAM_TYPE_INT32: {
                    volatile int32_t* iv = (volatile int32_t*)s_registry[i].ptr;
                    *iv = (int32_t)value;
                    return PARAM_STATUS_OK;
                }
                default:
                    return PARAM_STATUS_NOT_FOUND;
            }
        }
    }
    return PARAM_STATUS_NOT_FOUND;
}

/* Returns PARAM_STATUS_OK and fills *out_value, or PARAM_STATUS_NOT_FOUND. */
uint8_t Param_Get(const char* name, float* out_value)
{
    uint16_t i;
    for (i = 0U; i < g_param_count; i++) {
        if (name_match(s_registry[i].name, name, PARAM_NAME_LEN)) {
            float val;
            switch (s_registry[i].type) {
                case PARAM_TYPE_FLOAT: {
                    get_float(s_registry[i].ptr, &val);
                    *out_value = val;
                    return PARAM_STATUS_OK;
                }
                case PARAM_TYPE_UINT8: {
                    volatile uint8_t* b = (volatile uint8_t*)s_registry[i].ptr;
                    *out_value = (float)(*b);
                    return PARAM_STATUS_OK;
                }
                case PARAM_TYPE_INT32: {
                    volatile int32_t* iv = (volatile int32_t*)s_registry[i].ptr;
                    *out_value = (float)(*iv);
                    return PARAM_STATUS_OK;
                }
                default:
                    return PARAM_STATUS_NOT_FOUND;
            }
        }
    }
    return PARAM_STATUS_NOT_FOUND;
}
