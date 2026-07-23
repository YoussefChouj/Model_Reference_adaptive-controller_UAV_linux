/**
 * @file     ekf.c
 * @brief    9-state body-frame EKF — pure C99 firmware port.
 *
 * Reference: sim/ekf.py (golden, 108 tests) + ADR-0011 §"Parallel estimator".
 *
 * Math summary:
 *  State    : x = [v_body(3), b_a_body(3), b_g_body(3)]  — 9 floats
 *  Covar    : P = diag([Q_v, Q_v, Q_v, Q_ba, Q_ba, Q_ba, Q_bg, Q_bg, Q_bg])
 *  Predict  : v += (a_body - b_a) * dt;  P_vv += dt^2*Q_v;  P_ba += Q_ba; P_bg += Q_bg
 *  UpdateOF : H = [[1,0,0,...],[0,1,0,...]]; y = z - Hx; S = HPH^T + R*I2
 *             K = P H^T S^-1;  x += K y;  P = (I-KH)P(I-KH)^T + KRK^T
 *  UpdateAccXY: same H/R as OF, R=R_acc
 *  UpdateZRate: scalar H=[0,0,1,...]; y = z - x[2]; K = P[:,2]/s; x += K*y; P -= K*P[2,:]
 *
 * Keil ARMCC compatible — no designated initializers, no compound literals.
 */
#include "ekf.h"
#include <math.h>

/* ------------------------------------------------------------------ */
/* Init                                                                 */
/* ------------------------------------------------------------------ */
void Ekf9_Init(Ekf9_t *e, uint8_t active)
{
    uint8_t i;
    for (i = 0U; i < 9U; i++) {
        e->x[i]      = 0.0f;
        e->Q_diag[i] = 0.0f;
    }
    /* Q defaults from ADR-0011 table: Q_v=1e-3, Q_ba=1e-6, Q_bg=5e-9 */
    e->Q_diag[0] = 1e-3f;  e->Q_diag[1] = 1e-3f;  e->Q_diag[2] = 1e-3f;
    e->Q_diag[3] = 1e-6f;  e->Q_diag[4] = 1e-6f;  e->Q_diag[5] = 1e-6f;
    e->Q_diag[6] = 5e-9f;  e->Q_diag[7] = 5e-9f;  e->Q_diag[8] = 5e-9f;

    /* P initial = diag(Q) */
    for (i = 0U; i < 9U; i++) {
        uint8_t j;
        for (j = 0U; j < 9U; j++) {
            e->P[i * 9U + j] = (i == j) ? e->Q_diag[i] : 0.0f;
        }
    }

    e->R_of  = 6.16e-4f;
    e->R_acc = 0.005f;
    e->R_z   = 0.04f;

    e->nis      = 0.0f;
    e->k_last[0] = 0.0f;
    e->k_last[1] = 0.0f;
    e->k_last[2] = 0.0f;

    e->active = active;

    /* Zero working buffers */
    for (i = 0U; i < 9U;  i++) e->S[i] = 0.0f;
    for (i = 0U; i < 27U; i++) e->K[i] = 0.0f;
}

/* ------------------------------------------------------------------ */
/* Predict                                                               */
/* ------------------------------------------------------------------ */
void Ekf9_Predict(Ekf9_t *e,
                   float a_body_x, float a_body_y, float a_body_z,
                   float gyro_x,   float gyro_y,   float gyro_z,
                   float dt)
{
    if (!e->active) return;

    /* State: v_body += (a_body - b_a_body) * dt */
    e->x[0] += (a_body_x - e->x[3]) * dt;
    e->x[1] += (a_body_y - e->x[4]) * dt;
    e->x[2] += (a_body_z - e->x[5]) * dt;
    /* b_a_body and b_g_body are random-walk — x[3..8] unchanged */

    /* Covariance: diagonal-block approximation
     * P_vv += dt^2 * Q_v  (indices 0,1,2)
     * P_ba += Q_ba         (indices 3,4,5)
     * P_bg += Q_bg         (indices 6,7,8)
     * Cross terms F[i,j]*dt are dropped at v0 (they are O(dt^2) vs dt^2*Q_v). */
    {
        float dt2_qv = dt * dt * e->Q_diag[0];
        e->P[0 * 9U + 0U] += dt2_qv;
        e->P[1 * 9U + 1U] += dt * dt * e->Q_diag[1];
        e->P[2 * 9U + 2U] += dt * dt * e->Q_diag[2];
        /* Q_ba adds to diagonal only (random-walk, no dt factor) */
        e->P[3 * 9U + 3U] += e->Q_diag[3];
        e->P[4 * 9U + 4U] += e->Q_diag[4];
        e->P[5 * 9U + 5U] += e->Q_diag[5];
        /* Q_bg */
        e->P[6 * 9U + 6U] += e->Q_diag[6];
        e->P[7 * 9U + 7U] += e->Q_diag[7];
        e->P[8 * 9U + 8U] += e->Q_diag[8];
    }

    e->nis = 0.0f;
}

/* ------------------------------------------------------------------ */
/* Shared 2x2 update logic (used by UpdateOf and UpdateAccXY)          */
/* ------------------------------------------------------------------ */
static void s_Update2x2(Ekf9_t *e,
                         float y0, float y1,
                         float R,
                         float *nis_out)
{
    /* S = HPH^T + R*I2.  H = [[1,0,...],[0,1,...]].
     * S = [[P00+R, P01], [P10, P11+R]] */
    float s00 = e->P[0 * 9U + 0U] + R;
    float s01 = e->P[0 * 9U + 1U];
    float s10 = e->P[1 * 9U + 0U];
    float s11 = e->P[1 * 9U + 1U] + R;

    /* 2x2 inverse: det = s00*s11 - s01*s10 */
    float det = s00 * s11 - s01 * s10;
    if (det <= 0.0f) return;   /* singular — reject update */

    /* S^-1 */
    float sinv00 =  s11 / det;
    float sinv01 = -s01 / det;
    float sinv10 = -s10 / det;
    float sinv11 =  s00 / det;

    /* K = P H^T S^-1.  H^T = [[1,0],[0,1],[0,0],...].
     * K[i*3+0] = P[i,0]*sinv00 + P[i,1]*sinv10  (col 0 = OF-x)
     * K[i*3+1] = P[i,0]*sinv01 + P[i,1]*sinv11  (col 1 = OF-y) */
    {
        uint8_t i;
        for (i = 0U; i < 9U; i++) {
            e->K[i * 3U + 0U] = e->P[i * 9U + 0U] * sinv00 + e->P[i * 9U + 1U] * sinv10;
            e->K[i * 3U + 1U] = e->P[i * 9U + 0U] * sinv01 + e->P[i * 9U + 1U] * sinv11;
        }
    }

    /* x += K * y */
    {
        uint8_t i;
        for (i = 0U; i < 9U; i++) {
            e->x[i] += e->K[i * 3U + 0U] * y0 + e->K[i * 3U + 1U] * y1;
        }
    }

    /* P = (I - K H) P (I - K H)^T + K R K^T
     * = P - K*H*P - P*H^T*K^T + K*(R*I2 + H*P*H^T)*K^T
     * Using Joseph form: P_new = P - K*H*P (overwrites P in-place row by row).
     * H selects cols 0 and 1. */
    {
        uint8_t i;
        for (i = 0U; i < 9U; i++) {
            uint8_t j;
            for (j = 0U; j < 9U; j++) {
                float kp0 = e->K[i * 3U + 0U] * e->P[0U * 9U + j];
                float kp1 = e->K[i * 3U + 1U] * e->P[1U * 9U + j];
                e->P[i * 9U + j] -= (kp0 + kp1);
            }
        }
        /* Add K R K^T = K * R*I2 * K^T (diagonal R, so K*R*K^T = R * (k_col0*k_col0' + k_col1*k_col1')) */
        {
            uint8_t i;
            for (i = 0U; i < 9U; i++) {
                e->P[i * 9U + i] += R * (e->K[i * 3U + 0U] * e->K[i * 3U + 0U]
                                         + e->K[i * 3U + 1U] * e->K[i * 3U + 1U]);
            }
        }
    }

    /* NIS = y^T S^-1 y */
    if (nis_out != 0) {
        *nis_out = y0 * (sinv00 * y0 + sinv01 * y1)
                 + y1 * (sinv10 * y0 + sinv11 * y1);
    }

    /* Cache K column 0 (x-axis gains) for telemetry */
    e->k_last[0] = e->K[0U * 3U + 0U];
    e->k_last[1] = e->K[1U * 3U + 0U];
    e->k_last[2] = e->K[2U * 3U + 0U];
}

/* ------------------------------------------------------------------ */
/* Update — Optical Flow (body XY)                                     */
/* ------------------------------------------------------------------ */
void Ekf9_UpdateOf(Ekf9_t *e, float of_x, float of_y)
{
    if (!e->active) return;

    float y0 = of_x - e->x[0];
    float y1 = of_y - e->x[1];
    s_Update2x2(e, y0, y1, e->R_of, &e->nis);
}

/* ------------------------------------------------------------------ */
/* Update — Body-lin-acc XY (gravity-removed)                          */
/* ------------------------------------------------------------------ */
void Ekf9_UpdateAccXY(Ekf9_t *e, float lin_acc_x, float lin_acc_y)
{
    if (!e->active) return;

    float y0 = lin_acc_x - e->x[0];
    float y1 = lin_acc_y - e->x[1];
    s_Update2x2(e, y0, y1, e->R_acc, &e->nis);
}

/* ------------------------------------------------------------------ */
/* Update — Z-rate (scalar)                                            */
/* ------------------------------------------------------------------ */
void Ekf9_UpdateZRate(Ekf9_t *e, float z_rate)
{
    if (!e->active) return;

    float y = z_rate - e->x[2];
    float s_zz = e->P[2 * 9U + 2U] + e->R_z;
    if (s_zz <= 0.0f) return;

    /* K[i] = P[i,2] / s_zz */
    {
        uint8_t i;
        for (i = 0U; i < 9U; i++) {
            e->K[i * 3U + 2U] = e->P[i * 9U + 2U] / s_zz;
        }
    }

    /* x += K * y */
    {
        uint8_t i;
        for (i = 0U; i < 9U; i++) {
            e->x[i] += e->K[i * 3U + 2U] * y;
        }
    }

    /* P = (I - K H) P (I - K H)^T + K R K^T,  H = [0,0,1,0,...]
     * I-KH has H row 2 non-zero: (I-KH)[i][2] = -K[i]*1 for all i.
     * P_new[i,j] = P[i,j] - K[i]*P[2,j] - P[i,2]*K[j] + R_z*K[i]*K[j]
     * Symmetric form (Joseph): P_new = P - K*P[2,:] - P[:,2]*K^T + R_z*K*K^T
     * In-place (same as 2x2 case above): */
    {
        uint8_t i;
        for (i = 0U; i < 9U; i++) {
            uint8_t j;
            float ki = e->K[i * 3U + 2U];
            for (j = 0U; j < 9U; j++) {
                e->P[i * 9U + j] -= ki * e->P[2U * 9U + j];
            }
        }
        /* Add R_z * K * K^T to diagonal */
        {
            uint8_t i;
            for (i = 0U; i < 9U; i++) {
                float ki = e->K[i * 3U + 2U];
                e->P[i * 9U + i] += e->R_z * ki * ki;
            }
        }
    }

    e->nis = y * y / e->R_z;

    /* Cache K[0..2] for telemetry */
    e->k_last[0] = e->K[0U * 3U + 2U];
    e->k_last[1] = e->K[1U * 3U + 2U];
    e->k_last[2] = e->K[2U * 3U + 2U];
}
