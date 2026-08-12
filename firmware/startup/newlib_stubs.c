/* Minimal newlib stubs for the bare-metal GCC build.
 *
 * newlib's libm expects __errno to be defined somewhere; we route it to a
 * 4-byte integer in .bss. retarget.c provides the file-level syscalls
 * (open, close, read, write, fstat, isatty, lseek); we just need errno.
 */
#include <errno.h>

int errno;
int *__errno(void) { return &errno; }
