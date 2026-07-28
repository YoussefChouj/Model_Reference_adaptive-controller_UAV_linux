/* ============================================================================
 * sil_gate/runner_main.c
 *
 * HOST-TEST RUNNER ONLY - see sil_gate/README.md for the contract.
 *
 * Compiled together with API/ekf.c (and, later, API/mrac.c) into a
 * standalone executable by sil_gate/compiler.py. The gate drives it as a
 * subprocess with a per-tick trajectory on stdin and parses the per-tick
 * state it emits on stdout.
 *
 * Wire protocol (CSV):
 *
 *   stdin (Python -> runner):
 *     "<MODULE> v1\n"          e.g. "EKF9 v1"
 *     "<N>\n"                  number of ticks
 *     N lines: dt, ax, ay, az, of_x, of_y, z_rate
 *     "END\n"
 *
 *   stdout (runner -> Python):
 *     "<MODULE> v1\n"
 *     N lines: x[0..8], nis, k_last[0..2]   (12 floats per line)
 *     "END\n"
 *
 * The runner is intentionally minimal: it does not parse arguments, does
 * not allocate, and does not do any comparison. Comparison happens on the
 * Python side (sil_gate/runner.py). This keeps the runner small enough to
 * be re-built in milliseconds when the trajectory driver changes.
 *
 * This file is NOT firmware. It is NEVER compiled into the drone's image.
 * ============================================================================
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ekf.h"

/* Maximum trajectory length the runner will accept. The spec calls for
 * 2000 ticks; cap at 8192 to leave headroom and prevent runaway reads. */
#define MAX_TICKS 8192

static int read_float(FILE *f, float *out)
{
    /* read a single float, skipping whitespace and commas */
    int c;
    char buf[64];
    int i = 0;
    while ((c = fgetc(f)) != EOF) {
        if (c == '-' || c == '+' || c == '.' || (c >= '0' && c <= '9') || c == 'e' || c == 'E') {
            if (i < (int)sizeof(buf) - 1) {
                buf[i++] = (char)c;
            }
        } else if (i > 0) {
            /* end of token - push back the delimiter */
            ungetc(c, f);
            break;
        }
        /* else: skip leading whitespace */
    }
    if (i == 0 && c == EOF) return -1;
    buf[i] = '\0';
    *out = (float)strtod(buf, NULL);
    return 0;
}

static int read_token(FILE *f, char *out, int maxlen)
{
    int c;
    int i = 0;
    while ((c = fgetc(f)) != EOF) {
        if (c == '\n' || c == '\r') {
            if (i > 0) {
                out[i] = '\0';
                return 0;
            }
            /* skip blank lines */
            continue;
        }
        if (i < maxlen - 1) {
            out[i++] = (char)c;
        }
    }
    if (i > 0) {
        out[i] = '\0';
        return 0;
    }
    return -1;
}

int main(void)
{
    char tok[64];

    /* Header: must be "<MODULE> v1". For now only "EKF9" is supported. */
    if (read_token(stdin, tok, sizeof(tok)) != 0 || strncmp(tok, "EKF9", 4) != 0) {
        fprintf(stderr, "runner: bad header '%s' (want 'EKF9 v1')\n", tok);
        return 2;
    }

    /* Tick count */
    if (read_token(stdin, tok, sizeof(tok)) != 0) {
        fprintf(stderr, "runner: missing tick count\n");
        return 2;
    }
    {
        char *endp;
        long n = strtol(tok, &endp, 10);
        if (endp == tok || n <= 0 || n > MAX_TICKS) {
            fprintf(stderr, "runner: bad tick count '%s' (1..%d)\n", tok, MAX_TICKS);
            return 2;
        }

        /* EKF state, zero-init via Ekf9_Init */
        Ekf9_t e;
        Ekf9_Init(&e, 1U);

        /* Header echo for the parser */
        printf("EKF9 v1\n");

        long i;
        for (i = 0; i < n; i++) {
            float dt, ax, ay, az, ofx, ofy, zrate;
            if (read_float(stdin, &dt)  != 0 ||
                read_float(stdin, &ax)  != 0 ||
                read_float(stdin, &ay)  != 0 ||
                read_float(stdin, &az)  != 0 ||
                read_float(stdin, &ofx) != 0 ||
                read_float(stdin, &ofy) != 0 ||
                read_float(stdin, &zrate) != 0) {
                fprintf(stderr, "runner: bad input at tick %ld\n", i);
                return 3;
            }

            /* Per-tick update chain. ZUPT (0,0) on the acc channel is the
             * only valid call to UpdateAccXY; see ekf.h. */
            Ekf9_Predict(&e, ax, ay, az, 0.0f, 0.0f, 0.0f, dt);
            Ekf9_UpdateOf(&e, ofx, ofy);
            Ekf9_UpdateAccXY(&e, 0.0f, 0.0f);
            Ekf9_UpdateZRate(&e, zrate);

            /* Emit x[0..8], nis, k_last[0..2] */
            int k;
            for (k = 0; k < 9; k++) {
                printf("%.9e%s", e.x[k], (k == 8) ? "," : ",");
            }
            printf("%.9e,", e.nis);
            for (k = 0; k < 3; k++) {
                printf("%.9e%s", e.k_last[k], (k == 2) ? "\n" : ",");
            }
        }
    }

    printf("END\n");
    return 0;
}