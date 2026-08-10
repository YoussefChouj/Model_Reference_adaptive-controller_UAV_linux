/* ============================================================================
 * sil_gate/shim/robot_types.h
 *
 * HOST-TEST STUB ONLY — see sil_gate/shim/stm32f4xx.h for the contract.
 *
 * The real Global_file/robot_types.h is a 350-line file defining all the
 * firmware structs (PIDTypeDef, CtrlerTypeDef, DroneStatusTypeDef, ...).
 * sil_gate targets (ekf.c, mrac.c) need only the layout-correct types they
 * dereference: PIDTypeDef and CtrlerTypeDef. The struct field ORDER must
 * match Global_file/robot_types.h exactly so mrac.c's
 *   p_rate = current_state->gyroyPID.FB * ...
 * accesses the right memory. mrac.c dereferences FB, Des, U on each
 * PIDTypeDef and treats CtrlerTypeDef as a flat layout of named PIDs.
 *
 * Other structs (DroneStatusTypeDef, RemoterTypeDef, ST_IMU_DATA, etc.) are
 * forward-declared as opaque — sil_gate never dereferences them.
 * ============================================================================
 */
#ifndef SIL_SHIM_ROBOT_TYPES_H
#define SIL_SHIM_ROBOT_TYPES_H

#include "data_types.h"  /* SIL SHIM — see sil_gate/shim/data_types.h */
#include "stm32f4xx.h"   /* SIL SHIM — see sil_gate/shim/stm32f4xx.h */

/* ----------------------------------------------------------------------------
 * Layout-correct PIDTypeDef and CtrlerTypeDef (mirrors Global_file/robot_types.h).
 * Field order is load-bearing — mrac.c reads FB, Des, U by name and the ABI
 * is fixed by the ARM target. Any drift here changes the offset of FB and
 * silently corrupts the test inputs. Do not reorder.
 * ------------------------------------------------------------------------- */
typedef struct {
    float Des;
    float FB;
    float Kp;
    float Ki;
    float Kd;
    float Up;
    float Ui;
    float Ud;
    float E;
    float PreE;
    float SumE;
    float U;
    float UMax;
    float UpMax;
    float UiMax;
    float UdMax;
    float SumEMax;
    float EMin;
    /* --- Anti-windup extension (zero-init keeps legacy default) --- */
    int   aw_mode;
    float Kt;
} PIDTypeDef;

typedef struct {
    PIDTypeDef pitchPID;
    PIDTypeDef rollPID;
    PIDTypeDef yawPID;
    PIDTypeDef gyroxPID;
    PIDTypeDef gyroyPID;
    PIDTypeDef gyrozPID;
    PIDTypeDef Z_posPID;
    PIDTypeDef Z_ratePID;
    PIDTypeDef locxPID;
    PIDTypeDef locyPID;
    PIDTypeDef locxsPID;
    PIDTypeDef locysPID;
    PIDTypeDef stree_yaw_speed;
    PIDTypeDef stree_pitch_speed;
} CtrlerTypeDef;

/* Other structs from the real header — opaque forward declarations only.
 * Any sil_gate target that dereferences one of these will fail to compile,
 * which is the signal we want. */
struct _DroneStatusTypeDef;
typedef struct _DroneStatusTypeDef DroneStatusTypeDef;

struct _StickMotionTypeDef;
typedef struct _StickMotionTypeDef StickMotionTypeDef;

struct _SYSTEM_MONITOR;
typedef struct _SYSTEM_MONITOR SYSTEM_MONITOR;

struct _RemoterTypeDef;
typedef struct _RemoterTypeDef RemoterTypeDef;

#endif /* SIL_SHIM_ROBOT_TYPES_H */
