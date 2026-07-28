/* ============================================================================
 * sil_gate/shim/robot_types.h
 *
 * HOST-TEST STUB ONLY — see sil_gate/shim/stm32f4xx.h for the contract.
 *
 * The real Global_file/robot_types.h is a 350-line file defining all the
 * firmware structs (PIDTypeDef, CtrlerTypeDef, DroneStatusTypeDef, ...).
 * sil_gate targets (ekf.c, mrac.c) do not reference any of them — ekf.c
 * uses only `uint8_t` from this chain, and mrac.c uses `CtrlerTypeDef *` as
 * an opaque pointer.
 *
 * To keep the shim honest and the gate future-proof, we forward only the
 * include chain. If a future target starts dereferencing a struct here,
 * the compile will fail with an incomplete-type error — exactly the signal
 * we want.
 * ============================================================================
 */
#ifndef SIL_SHIM_ROBOT_TYPES_H
#define SIL_SHIM_ROBOT_TYPES_H

#include "data_types.h"  /* SIL SHIM — see sil_gate/shim/data_types.h */
#include "stm32f4xx.h"   /* SIL SHIM — see sil_gate/shim/stm32f4xx.h */

/* Opaque forward declaration so MRAC_Control(CtrlerTypeDef *) parses.
 * sil_gate never dereferences this. */
struct _CtrlerTypeDef;
typedef struct _CtrlerTypeDef CtrlerTypeDef;

#endif /* SIL_SHIM_ROBOT_TYPES_H */