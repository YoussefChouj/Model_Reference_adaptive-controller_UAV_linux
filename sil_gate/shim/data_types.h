/* ============================================================================
 * sil_gate/shim/data_types.h
 *
 * HOST-TEST STUB ONLY — see sil_gate/shim/stm32f4xx.h for the contract.
 *
 * This mirrors Global_file/data_types.h exactly so that int widths are
 * identical to the ARM ABI target. The width contract is the load-bearing
 * detail: a divergence here (e.g. FP32 == double) silently changes filter
 * numerics and is exactly the kind of mismatch the gate must NOT introduce.
 * ============================================================================
 */
#ifndef SIL_SHIM_DATA_TYPES_H
#define SIL_SHIM_DATA_TYPES_H

typedef unsigned char   UCHAR8;   /* unsigned 8-bits integer */
typedef signed   char   SCHAR8;   /* signed 8-bits integer   */
typedef unsigned short  USHORT16; /* unsigned 16-bits integer */
typedef signed   short  SSHORT16; /* signed 16-bits integer   */
typedef unsigned int    UINT32;   /* unsigned 32-bits integer */
typedef int             SINT32;   /* signed 32-bits integer   */
typedef float           FP32;     /* single precision 32-bit  */
typedef double          DB64;     /* double precision 64-bit  */

typedef enum {FALSE = 0, TRUE = !FALSE} bool;

#endif /* SIL_SHIM_DATA_TYPES_H */