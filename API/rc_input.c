#include "rc_input.h"
#include "FreeRTOS.h"
#include "task.h"
#include "global_declare.h"

/* ------------------------------------------------------------------
 * Private constants
 * ------------------------------------------------------------------ */

/* Stick dead-zone thresholds in normalised units.
 * Derived from former SBUS macros: SBUS_OFFSET=100 and SBUS_THR_OFFSET=50,
 * both relative to a 1000-unit half-range, so 100/1000 = 0.10, 50/1000 = 0.05. */
#define RC_ACTIVE_THRESHOLD      0.10f
#define RC_THR_ACTIVE_THRESHOLD  0.05f

/* Bench-mode throttle cap: prevents the drone from climbing on the bench.
 * Former raw cap was 2400; (2400 - 3000) / 1000 = -0.60. */
#define RC_BENCH_THR_CAP        -0.60f

/* Physical RC takeover rate threshold (per 10 ms RemoterTask tick).
 * Compares consecutive tick values, not a fixed snapshot.
 * 0.05 = 5 % of full range per tick → catches a full-range deflection
 * in ~0.4 s while ignoring RC noise (< 0.005/tick) and slow drift. */
#define RC_PHYSICAL_RATE_DELTA  0.05f

/* Ticks after authority grant before takeover check activates.
 * 10 × 10 ms = 100 ms for SBUS and Remoter values to settle. */
#define RC_AUTHORITY_GRACE_TICKS 10U

/* ------------------------------------------------------------------
 * Module state  (all private to this translation unit)
 * ------------------------------------------------------------------ */
static float      s_virtual[4]       = {0.0f, 0.0f, 0.0f, 0.0f};
static float      s_physical_snap[4] = {0.0f, 0.0f, 0.0f, 0.0f};
static uint8_t    s_authority        = 0U;
static TickType_t s_last_update_tick = 0U;
static uint8_t    s_heartbeat_active = 0U;
static uint8_t    s_heartbeat_lost   = 0U;
static uint16_t   s_authority_grace  = 0U;

/* ------------------------------------------------------------------
 * Internal helpers
 * ------------------------------------------------------------------ */

/* Convert from SBUS-scaled [2000, 4000] (centre 3000) to [-1, 1]. */
static float s_normalize(float raw)
{
    return (raw - 3000.0f) / 1000.0f;
}

static float s_clamp(float v, float lo, float hi)
{
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

/* ------------------------------------------------------------------
 * Public API
 * ------------------------------------------------------------------ */

float RCInput_Get(RC_Axis_t axis)
{
    float v;

    if (s_authority) {
        /* PC has authority: virtual sticks take over, physical RC ignored.
         * RC mode switch (ch10) remains the hard kill — it acts on FlyMode,
         * not on this function, so it always works regardless of authority. */
        switch (axis) {
            case RC_AXIS_THR:   v = s_virtual[0]; break;
            case RC_AXIS_PITCH: v = s_virtual[1]; break;
            case RC_AXIS_ROLL:  v = s_virtual[2]; break;
            case RC_AXIS_YAW:   v = s_virtual[3]; break;
            default:            v = 0.0f;          break;
        }
    } else {
        /* Pilot mode: physical RC sticks. */
        switch (axis) {
            case RC_AXIS_THR:   v = s_normalize((float)Remoter.ThrCtrler); break;
            case RC_AXIS_PITCH: v = s_normalize((float)Remoter.PitCtrler); break;
            case RC_AXIS_ROLL:  v = s_normalize((float)Remoter.RolCtrler); break;
            case RC_AXIS_YAW:   v = s_normalize((float)Remoter.YawCtrler); break;
            default:            v = 0.0f; break;
        }
    }

    v = s_clamp(v, -1.0f, 1.0f);

    /* Safety cap: in bench_mode the drone must not be commanded to climb. */
    if (axis == RC_AXIS_THR && bench_mode_active) {
        if (v > RC_BENCH_THR_CAP) {
            v = RC_BENCH_THR_CAP;
        }
    }

    return v;
}

int RCInput_IsActive(RC_Axis_t axis)
{
    float v, threshold;

    /* When PC has authority, apply dead-zones to ALL axes so that spring-returned
     * sticks (value = 0.0) are treated as "not active".  This lets the position
     * PID outputs flow through to the velocity loop (TWC / auto-position tracking).
     * When a VRC slider is actively deflected past the threshold the stick value
     * takes over, overriding the position PID — same behaviour as physical RC. */
    if (s_authority) {
        if ((unsigned int)axis < 4U) {
            v = s_virtual[(unsigned int)axis];
            threshold = (axis == RC_AXIS_THR) ? RC_THR_ACTIVE_THRESHOLD
                                               : RC_ACTIVE_THRESHOLD;
            return (v > threshold || v < -threshold) ? 1 : 0;
        }
        return 0;
    }

    v         = RCInput_Get(axis);
    threshold = (axis == RC_AXIS_THR) ? RC_THR_ACTIVE_THRESHOLD : RC_ACTIVE_THRESHOLD;

    return (v > threshold || v < -threshold) ? 1 : 0;
}

void RCInput_SetVirtualStick(RC_Axis_t axis, float val)
{
    if ((unsigned int)axis < 4U) {
        s_virtual[(unsigned int)axis] = s_clamp(val, -1.0f, 1.0f);
        s_last_update_tick            = xTaskGetTickCount();
        s_heartbeat_active            = 1U;
        s_heartbeat_lost              = 0U;
    }
}

void RCInput_SetAuthority(uint8_t has_authority)
{
    if (has_authority) {
        /* Pre-arm throttle to minimum to prevent a sudden jump.
         * Physical RC throttle is at -1.0 when the pilot's stick is down;
         * s_virtual[0] would otherwise be 0.0 (centre) → drone climbs. */
        s_virtual[0] = -1.0f;
        /* Pitch/roll/yaw stay at 0.0 (centre is safe for those axes). */
        /* Seed the rate-of-change buffer with current physical RC values so
         * the first Update() tick compares against "now", not against 0.0. */
        s_physical_snap[0] = s_normalize((float)Remoter.ThrCtrler);
        s_physical_snap[1] = s_normalize((float)Remoter.PitCtrler);
        s_physical_snap[2] = s_normalize((float)Remoter.RolCtrler);
        s_physical_snap[3] = s_normalize((float)Remoter.YawCtrler);
        s_authority_grace = RC_AUTHORITY_GRACE_TICKS;
        s_authority  = 1U;
    } else {
        /* Relinquish: reset all virtual sticks to centre so the drone
         * transitions to altitude / position hold on the next cycle. */
        s_authority      = 0U;
        s_virtual[0]     = 0.0f;
        s_virtual[1]     = 0.0f;
        s_virtual[2]     = 0.0f;
        s_virtual[3]     = 0.0f;
        s_heartbeat_active = 0U;
        s_heartbeat_lost   = 0U;
        s_authority_grace  = 0U;
    }
}

uint8_t RCInput_GetAuthority(void)
{
    return s_authority;
}

void RCInput_Update(void)
{
    if (!s_authority) {
        return;
    }

    /* --- Physical RC takeover check ---
     * Rate-of-change detection: fires only when the pilot is actively moving a
     * stick.  Suppressed when GS_KeySDKflag=1 (ground station explicitly holds
     * authority) or when the heartbeat is active (GS keepalive is flowing).
     * The heartbeat watchdog below is the failsafe for GS disconnect.         */
    if (!GS_KeySDKflag && !s_heartbeat_active && !sbus_lost) {
        float cur0 = s_normalize((float)Remoter.ThrCtrler);
        float cur1 = s_normalize((float)Remoter.PitCtrler);
        float cur2 = s_normalize((float)Remoter.RolCtrler);
        float cur3 = s_normalize((float)Remoter.YawCtrler);

        if (s_authority_grace > 0U) {
            /* Keep snap rolling during grace — no takeover check.
             * Lets SBUS settle before rate-of-change detection starts. */
            s_authority_grace--;
            s_physical_snap[0] = cur0;
            s_physical_snap[1] = cur1;
            s_physical_snap[2] = cur2;
            s_physical_snap[3] = cur3;
        } else {
            float d0 = cur0 - s_physical_snap[0]; if (d0 < 0.0f) d0 = -d0;
            float d1 = cur1 - s_physical_snap[1]; if (d1 < 0.0f) d1 = -d1;
            float d2 = cur2 - s_physical_snap[2]; if (d2 < 0.0f) d2 = -d2;
            float d3 = cur3 - s_physical_snap[3]; if (d3 < 0.0f) d3 = -d3;
            s_physical_snap[0] = cur0;
            s_physical_snap[1] = cur1;
            s_physical_snap[2] = cur2;
            s_physical_snap[3] = cur3;

            if (d0 > RC_PHYSICAL_RATE_DELTA || d1 > RC_PHYSICAL_RATE_DELTA ||
                d2 > RC_PHYSICAL_RATE_DELTA || d3 > RC_PHYSICAL_RATE_DELTA) {
                s_authority        = 0U;
                s_heartbeat_active = 0U;
                s_heartbeat_lost   = 0U;
                return;
            }
        }
    }

    /* --- Heartbeat watchdog ---
     * Fires only after the first CMD 0x06 has arrived (s_heartbeat_active=1).
     * The GS keepalive sends CMD 0x06 at 50 Hz, so this never fires in normal
     * operation.  If the GS process crashes or the cable is pulled, the
     * keepalive stops and after RC_HEARTBEAT_TIMEOUT_MS authority is revoked
     * so the physical RC pilot can take over safely. */
    if (!s_heartbeat_active) {
        return;
    }

    TickType_t now     = xTaskGetTickCount();
    TickType_t elapsed = now - s_last_update_tick;

    if (elapsed > pdMS_TO_TICKS(RC_HEARTBEAT_TIMEOUT_MS)) {
        s_authority        = 0U;
        s_virtual[0]       = 0.0f;
        s_virtual[1]       = 0.0f;
        s_virtual[2]       = 0.0f;
        s_virtual[3]       = 0.0f;
        s_heartbeat_lost   = 1U;
    }
}

int RCInput_IsHeartbeatLost(void)
{
    return (int)s_heartbeat_lost;
}
