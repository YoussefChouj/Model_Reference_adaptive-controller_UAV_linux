/* ============================================================================
 * sil_gate/shim/global_declare.h
 *
 * HOST-TEST STUB ONLY — see sil_gate/shim/stm32f4xx.h for the contract.
 *
 * The real Global_file/global_declare.h is a 320-line umbrella header that
 * pulls in robot_types.h (350 lines), declares many externs, and defines
 * inline-asm helpers used elsewhere. sil_gate targets (API/ekf.c, API/mrac.c)
 * do not reach any of that — they only need the integer typedefs that
 * global_declare.h provides transitively via robot_types.h + stm32f4xx.h.
 *
 * This stub deliberately mirrors the *include chain* of the real header so
 * that an `#include "global_declare.h"` in firmware code continues to resolve
 * to a parseable shim. Anything the gate does not need is intentionally
 * omitted — see sil_gate/README.md "Seam".
 * ============================================================================
 */
#ifndef SIL_SHIM_GLOBAL_DECLARE_H
#define SIL_SHIM_GLOBAL_DECLARE_H

#include "stm32f4xx.h"   /* SIL SHIM — see sil_gate/shim/stm32f4xx.h */
#include "robot_types.h" /* SIL SHIM — see sil_gate/shim/robot_types.h */

#endif /* SIL_SHIM_GLOBAL_DECLARE_H */