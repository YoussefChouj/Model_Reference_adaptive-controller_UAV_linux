"""Reference-model + Lyapunov-P generator for state-space MRAC (Phase 0).

Computes the reference-model matrices (Am, Bm), the adaptive-input direction
(Ba), and the Lyapunov matrix P solving  Am^T P + P Am = -Q  for the two cases
the project actually uses:

  MODE A  "pure MRAC"        — you DESIGN the reference model directly from a
                               desired (wn, zeta) [2nd order] or bandwidth
                               [1st order]. Am is hand-picked.

  MODE B  "PID-augmented"    — the Lavretsky/Yucelen baseline+adaptive case. Am
                               is NOT free: it is the closed-loop dynamics matrix
                               of the PID-controlled plant, built from the plant
                               (A, B, C) and the PID gains (K1=Kp, K2=Ki, K3=Kd),
                               exactly as in Cells 2-4 of the Roll_Pitch_Yaw
                               PID-MRAC notebook. Ba = F^-1 B is the direction the
                               adaptive torque enters augmented state-space.

The adaptive law these feed is:   What_dot = gamma * Phi * (xi - xi_r)^T P Ba
(see wiki/sources/pid-mrac-notebook.md, Cell 6).

Outputs are printed both human-readable and as C-ready `const float[]` blocks so
the result can be pasted straight into API/mrac.c, replacing the heuristic
scalar  P = 1/(2*wn).

This script is intentionally dependency-light (numpy + scipy only) and has no
side effects — it is a calculator, not part of the firmware build.

Usage
-----
    python compute_reference_model.py                 # runs the identified-axis presets
    python compute_reference_model.py --wn 44 --zeta 0.8           # MODE A, 2nd order
    python compute_reference_model.py --bw 10                      # MODE A, 1st order
    python compute_reference_model.py --pid-demo                   # MODE B worked example

Identified-plant presets (SysID 2026-06-18, see docs/sysid_results.md):
    roll / pitch : 2nd-order ref, wn = 44.1 rad/s, zeta = 0.8  (rel-degree 2)
    yaw          : 1st-order ref  (pure integrator K~37, rel-degree 1)
"""

import argparse
import numpy as np
from scipy.linalg import solve_continuous_lyapunov


# ----------------------------------------------------------------------------
# Core solvers
# ----------------------------------------------------------------------------
def solve_P(Am, Q):
    """Solve the continuous Lyapunov equation  Am^T P + P Am = -Q  for P.

    scipy.solve_continuous_lyapunov solves  X A + A^H X = -Q for the equation
    A^H X + X A = ... ; we want Am^T P + P Am = -Q, i.e. pass A = Am to the
    "A^H X + X A = Q" form with Q -> -Q. Concretely scipy solves
        a x + x a^H = q
    so to get  Am^T P + P Am = -Q  we call solve_continuous_lyapunov(Am.T, -Q).
    """
    P = solve_continuous_lyapunov(Am.T, -Q)
    P = 0.5 * (P + P.T)  # symmetrise (kill numerical asymmetry)
    return P


def check_P(Am, P, Q, tol=1e-6):
    """Return (residual_norm, is_spd) for the solved P."""
    resid = Am.T @ P + P @ Am + Q
    resid_norm = float(np.linalg.norm(resid))
    eigs = np.linalg.eigvalsh(P)
    is_spd = bool(np.all(eigs > 0))
    return resid_norm, is_spd, eigs


# ----------------------------------------------------------------------------
# MODE A - pure MRAC reference models (you design Am directly)
# ----------------------------------------------------------------------------
def second_order_refmodel(wn, zeta, Q=None):
    """Desired 2nd-order reference model  xm/r = wn^2 / (s^2 + 2*zeta*wn*s + wn^2).

    State xm = [output ; output_dot]. Returns Am, Bm, P and a closed-form P for
    cross-checking the numerical solve.
    """
    Am = np.array([[0.0, 1.0],
                   [-wn * wn, -2.0 * zeta * wn]])
    Bm = np.array([[0.0],
                   [wn * wn]])
    if Q is None:
        Q = np.eye(2)
    P = solve_P(Am, Q)

    # Closed-form P for Q = diag(q1, q2), a0 = wn^2, a1 = 2*zeta*wn
    # (handy for the firmware comment / hand verification):
    q1, q2 = Q[0, 0], Q[1, 1]
    a0, a1 = wn * wn, 2.0 * zeta * wn
    p12 = q1 / (2.0 * a0)
    p22 = (q1 / a0 + q2) / (2.0 * a1)
    p11 = a1 * p12 + a0 * p22
    P_closed = np.array([[p11, p12], [p12, p22]])

    return Am, Bm, P, P_closed


def first_order_refmodel(bw, q=1.0):
    """Desired 1st-order reference model  xm/r = bw / (s + bw), unity DC gain.

    Scalar case: Am = -bw, Bm = bw, and  2*bw*P = q  =>  P = q/(2*bw).
    With q = 1 this reproduces the firmware's  P = 1/(2*bw).
    """
    Am = np.array([[-bw]])
    Bm = np.array([[bw]])
    Q = np.array([[q]])
    P = solve_P(Am, Q)
    return Am, Bm, P


# ----------------------------------------------------------------------------
# MODE B - PID-augmented reference model (Am derived from plant + PID gains)
# ----------------------------------------------------------------------------
def pid_augmented_refmodel(A, B, C, K1, K2, K3, Q=None):
    """Build the baseline-PID closed-loop reference model (notebook Cells 2-4).

    Augmented plant state  xi = [theta, omega, z_int]^T,  z_int_dot = theta - ref.
    PID:  tau_nom = -K1*(theta-ref) - K2*z_int - K3*omega_hat   (K1=Kp,K2=Ki,K3=Kd)

        F     = I + B*K3*C
        G     = A - B*K1*C
        Ar    = [[F^-1 G,  -F^-1 B K2],
                 [   C    ,      0     ]]
        Br    = [F^-1 B K1 ; -1]
        Ba    = [F^-1 B     ;  0]          (adaptive-input direction)
        Ar^T P + P Ar = -Q

    A, B, C describe the *inner* plant in the chosen state coordinates; for the
    drone rate loop the normalized double-integrator form is
        A = [[0,1],[0,0]], B = [[0],[1]], C = [[1,0]]
    augmented here with the integral state to give the 3x3 system above.
    """
    A = np.atleast_2d(A).astype(float)
    B = np.atleast_2d(B).astype(float)
    C = np.atleast_2d(C).astype(float)
    n = A.shape[0]

    F = np.eye(n) + B @ (K3 * C)
    Finv = np.linalg.inv(F)
    G = A - B @ (K1 * C)

    FG = Finv @ G                      # n x n
    FBK2 = Finv @ B * K2               # n x 1
    FBK1 = Finv @ B * K1               # n x 1
    FB = Finv @ B                      # n x 1

    # Ar = [[FG, -FBK2], [C, 0]]  -> (n+1) x (n+1)
    top = np.hstack([FG, -FBK2])
    bot = np.hstack([C, np.zeros((1, 1))])
    Ar = np.vstack([top, bot])

    Br = np.vstack([FBK1, np.array([[-1.0]])])
    Ba = np.vstack([FB, np.array([[0.0]])])

    if Q is None:
        Q = np.eye(n + 1)
    P = solve_P(Ar, Q)
    return {"F": F, "G": G, "Ar": Ar, "Br": Br, "Ba": Ba, "P": P, "Q": Q}


# ----------------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------------
def _fmt_mat(name, M):
    M = np.atleast_2d(M)
    rows = ["    [" + ", ".join(f"{v: .6g}" for v in row) + "]" for row in M]
    return f"{name} ({M.shape[0]}x{M.shape[1]}):\n" + "\n".join(rows)


def c_array(name, M):
    """Emit a row-major C initializer for a matrix/vector."""
    M = np.atleast_2d(M)
    flat = ", ".join(f"{v:.8f}f" for v in M.flatten())
    r, c = M.shape
    if r == 1 or c == 1:
        return f"static const float {name}[{M.size}] = {{ {flat} }};"
    return (f"static const float {name}[{r}][{c}] = {{\n"
            + ",\n".join("    { " + ", ".join(f"{v:.8f}f" for v in row) + " }"
                         for row in M)
            + "\n};")


def report_second_order(wn, zeta, Q=None):
    Am, Bm, P, P_closed = second_order_refmodel(wn, zeta, Q)
    if Q is None:
        Q = np.eye(2)
    resid, spd, eigs = check_P(Am, P, Q)
    poles = np.linalg.eigvals(Am)
    print(f"\n=== MODE A: 2nd-order reference model  (wn={wn} rad/s, zeta={zeta}) ===")
    print(f"  desired poles : {poles[0]:.4g}, {poles[1]:.4g}")
    print(f"  rise ~1.8/wn  : {1.8/wn*1000:.1f} ms   settle ~4/(zeta*wn): {4.0/(zeta*wn)*1000:.1f} ms")
    print(_fmt_mat("  Am", Am))
    print(_fmt_mat("  Bm", Bm))
    print(_fmt_mat("  P (numeric)", P))
    print(_fmt_mat("  P (closed-form)", P_closed))
    print(f"  Lyapunov residual ||Am^T P + P Am + Q|| = {resid:.2e}   P SPD: {spd}  (eig {eigs})")
    print("\n  --- C-ready ---")
    print("  " + c_array("AM", Am).replace("\n", "\n  "))
    print("  " + c_array("BM", Bm).replace("\n", "\n  "))
    print("  " + c_array("P_LYAP", P).replace("\n", "\n  "))
    return Am, Bm, P


def report_first_order(bw, q=1.0):
    Am, Bm, P = first_order_refmodel(bw, q)
    print(f"\n=== MODE A: 1st-order reference model  (bw={bw} rad/s) ===")
    print(f"  pole: {Am[0,0]:.4g}   xm/r = {bw}/(s+{bw})   P = {P[0,0]:.6g}  (firmware uses 1/(2*bw) = {1/(2*bw):.6g})")
    return Am, Bm, P


def report_pid_augmented(A, B, C, K1, K2, K3, Q=None, label=""):
    out = pid_augmented_refmodel(A, B, C, K1, K2, K3, Q)
    resid, spd, eigs = check_P(out["Ar"], out["P"], out["Q"])
    poles = np.linalg.eigvals(out["Ar"])
    print(f"\n=== MODE B: PID-augmented reference model {label} ===")
    print(f"  PID gains: Kp(K1)={K1}, Ki(K2)={K2}, Kd(K3)={K3}")
    print(f"  closed-loop poles (eig Ar): {np.round(poles, 4)}")
    print(_fmt_mat("  Ar (= Am)", out["Ar"]))
    print(_fmt_mat("  Br (= Bm)", out["Br"]))
    print(_fmt_mat("  Ba (adaptive-input dir)", out["Ba"]))
    print(_fmt_mat("  P", out["P"]))
    print(f"  Lyapunov residual = {resid:.2e}   P SPD: {spd}")
    print("\n  --- C-ready ---")
    print("  " + c_array("AR", out["Ar"]).replace("\n", "\n  "))
    print("  " + c_array("BA", out["Ba"]).replace("\n", "\n  "))
    print("  " + c_array("P_LYAP", out["P"]).replace("\n", "\n  "))
    return out


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def run_presets():
    print("#" * 72)
    print("# Identified-axis presets (docs/sysid_results.md, SysID 2026-06-18)")
    print("#" * 72)
    # Roll / pitch: 2nd-order, measured closed-loop BW 44.1 rad/s, zeta 0.8
    report_second_order(44.1, 0.8)
    # Yaw: pure integrator -> 1st-order ref. bw provisional until a clean
    # no-pre-emphasis 0.05-4 Hz re-fly fixes the closed-loop x/r reading.
    report_first_order(10.0)
    print("\n  (yaw bw=10 rad/s is PROVISIONAL — replace with the measured "
          "closed-loop x/r -3 dB once re-flown.)")


def pid_demo():
    # Normalized inner rate plant: double integrator in [theta, omega] + integral
    A = [[0.0, 1.0], [0.0, 0.0]]
    B = [[0.0], [1.0]]
    C = [[1.0, 0.0]]
    # Example pole-placement-ish PID (replace with your LQR/pole-placement gains)
    report_pid_augmented(A, B, C, K1=80.0, K2=8.0, K3=12.0, label="(demo gains)")


def main():
    ap = argparse.ArgumentParser(description="Reference-model + Lyapunov-P generator for MRAC")
    ap.add_argument("--wn", type=float, help="MODE A 2nd-order natural frequency [rad/s]")
    ap.add_argument("--zeta", type=float, default=0.8, help="MODE A 2nd-order damping (default 0.8)")
    ap.add_argument("--bw", type=float, help="MODE A 1st-order bandwidth [rad/s]")
    ap.add_argument("--pid-demo", action="store_true", help="run the MODE B worked example")
    args = ap.parse_args()

    if args.pid_demo:
        pid_demo()
    elif args.wn is not None:
        report_second_order(args.wn, args.zeta)
    elif args.bw is not None:
        report_first_order(args.bw)
    else:
        run_presets()


if __name__ == "__main__":
    main()
