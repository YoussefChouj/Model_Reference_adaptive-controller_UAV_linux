// ------------------------------------------------------------------------------
// Model Reference Adaptive Control (MRAC) for 6DOF Quadcopter
// ------------------------------------------------------------------------------
// This header file defines the configuration, states, and function prototypes
// for the 4-layer MRAC augmentation (Pitch rate, Roll rate, Yaw rate, Z rate).
// ------------------------------------------------------------------------------

#ifndef MRAC_H
#define MRAC_H

#include <stdint.h>

// ------------------------------------------------------------------------------
// 1. Feature Configuration Flags
// ------------------------------------------------------------------------------
// Use these macros to enable/disable MRAC features at compile time.

// ------------------------------------------------------------------------------
// Payload Configuration Toggle
// ------------------------------------------------------------------------------
#define PAYLOAD_LIGHT 0 // Naked drone (Battery, optical flow, typical sensors, ~0.4kg to 0.6kg)
#define PAYLOAD_HEAVY 1 // Heavy drone (Mounted Jetson Orin, Realsense D435i, T265, ~1.5kg)

// ---> SET YOUR PAYLOAD HERE <---
#define ACTIVE_PAYLOAD PAYLOAD_LIGHT

// ------------------------------------------------------------------------------
// MRAC Output Scalers (Nm to Linear Mixer Units) - Defaults
// ------------------------------------------------------------------------------
#if ACTIVE_PAYLOAD == PAYLOAD_HEAVY
    // Derived algebraically assuming linear ESC mapping [2000 to 4000]:
    // Hover = 2800 (800 units above idle) for 1.5 kg, L = 0.19m.
    #define DEFAULT_MRAC_TO_MIXER_PR    286.0f   // Mixer units per Nm (Pitch/Roll)
    #define DEFAULT_MRAC_TO_MIXER_YAW   458.0f   // Mixer units per Nm (Yaw - 1.6x PR ratio based on inner PID Kp ratio 8/5)
    #define DEFAULT_MRAC_TO_MIXER_Z      54.0f   // Mixer units per N (Vertical Thrust)
#else
    // Derived for lighter payload w/o heavy sensors (~0.4kg to 0.6kg)
    #define DEFAULT_MRAC_TO_MIXER_PR    1170.0f  // Mixer units per Nm (Pitch/Roll)
    #define DEFAULT_MRAC_TO_MIXER_YAW   1872.0f  // Mixer units per Nm (Yaw - 1.6x PR ratio based on inner PID Kp ratio 8/5)
    #define DEFAULT_MRAC_TO_MIXER_Z      222.0f  // Mixer units per N (Vertical Thrust)
#endif



// Regressor type selection (choose ONE)
#define USE_STRUCTURED_UNCERTAINTY     1    // Physics-based: 6 features (bias, angle, rate, drag, un, v) [RECOMMENDED]
#define USE_UNSTRUCTURED_UNCERTAINTY   0    // RBF-based: 6 features (computational cost higher, enable for comparison)

// Core adaptive features
#define ENABLE_MRAC_COMPUTATION        1    // Master switch for adaptive law turn off mrac computations
#define ENABLE_MRAC_OUTPUT_INJECTION   1    // The "Shadow Mode" toggle. If 0, MRAC learns and computes u_ad, but we send 0.0f to the motor mixer.
#define ENABLE_PROJECTION_OPERATOR     1    // Bound adaptive weights to safe limits — MUST be on to prevent drift
#define ENABLE_SIGMA_MODIFICATION      1
#define ENABLE_WEIGHT_NORMALIZATION    1    // Normalize by (1 + theta'theta)
#define ENABLE_LOW_FREQ_LEARNING       1    // L1-style filtered weight updates

// Advanced features
#define ENABLE_PERFORMANCE_RECOVERY    1    // L1 state predictor + low-pass filtered correction
#define INCLUDE_CONTROL_IN_REGRESSOR   1    // Add [un, v] to regressor (important for actuator modeling)

// Future features (disabled for now)
#define ENABLE_LYAPUNOV_BARRIER        0    // Barrier Lyapunov function (Layer 8)
#define ENABLE_DEADZONE                1
#define ENABLE_PSEUDO_CONTROL_HEDGING  1    // PCH to prevent windup    // Gradient deadzone near zero error


// ------------------------------------------------------------------------------
// Operation Mode Flags
// ------------------------------------------------------------------------------
// Define maximum basis size depending on the chosen uncertainty model.
// For structured 6DOF: [Bias, Rate, Quadratic Rate, Cross-Coupling, LOE, Perf Rec]

#define NUM_BASIS   4

#if USE_STRUCTURED_UNCERTAINTY == 1
    //  Structured: [bias, angle, rate, drag] + [un, v] = 4 or 6 features 
    #if INCLUDE_CONTROL_IN_REGRESSOR == 1
        #define MAX_NUM_BASIS   (NUM_BASIS + 2)
    #else
        #define MAX_NUM_BASIS   NUM_BASIS
    #endif
#else
    //  Unstructured (RBF): 
    #if INCLUDE_CONTROL_IN_REGRESSOR == 1
        #define MAX_NUM_BASIS   (2*NUM_BASIS + 2)
    #else
        #define MAX_NUM_BASIS   (2*NUM_BASIS)
    #endif
#endif

// ------------------------------------------------------------------------------
// 3. Definitions and Types
// ------------------------------------------------------------------------------

// Enum for the 4 MRAC axes
typedef enum {
    MRAC_AXIS_PITCH = 0,
    MRAC_AXIS_ROLL  = 1,
    MRAC_AXIS_YAW   = 2,
    MRAC_AXIS_Z     = 3
} MRAC_Axis_e;

// Control limits (defaults applied in MRAC_Init)
// Refactored to mutable float fields in MRAC_AxisConfig_t

// Initial gamma/What_limit/What_tol values are set in MRAC_Init() (mrac.c).
// They are runtime-mutable via CMD 0x02 / 0x05 / 0x08 from the ground station.

#define MRAC_DT             0.005f      // [s] 5ms control period (200Hz)


// Configuration structure for an MRAC axis (constants and gains)
typedef struct {
    // Reference Model Parameters (wn, zeta for 2nd order models)
    /// empty for now since we are using a 1st order model for simplicity, but can be added back if needed
    
    // Adaptive law parameters
    //  Per-component learning rates: gamma[i] compensates for regressor magnitude imbalance.
        // Rule of thumb: gamma[i] = gamma_base / (typical |theta[i]|^2)
        // For theta=[bias=1, angle~0.15, rate~0.5, drag~0.25]:
        //   gamma[0]=0.50 (bias, theta^2=1.0)
        //   gamma[1]=3.30 (angle, theta^2=0.023, needs 44x more gain)
        //   gamma[2]=1.00 (rate, theta^2=0.25)
        //   gamma[3]=2.00 (drag, theta^2=0.063) 
    float gamma[MAX_NUM_BASIS]; // [array] Per-weight learning rates (diagonal Gamma matrix)
    float sigma_lf;             // [scalar] Low-frequency leakage (L1-style)
    float sigma;                // [scalar] Sigma-modification leakage
    float gam_f;                // [scalar] Low-pass filter gain for Whatf
    float omega_u;              // [rad/s] L1-style Low-pass filter cutoff parameter for adaptation signal
    
    // Projection operator bounds — per-component arrays (see WLIM/WTOL macros in mrac.h)
    // What_limit[i]: maximum |W_i| for basis i, derived from disturbance budget / theta_max_i
    // What_tol[i]:   soft-zone width (projection starts scaling at limit-tol, reaches 0 at limit)
    float What_limit[MAX_NUM_BASIS]; // per-component max weight magnitude
    float What_tol[MAX_NUM_BASIS];   // per-component soft boundary tolerance (20% of limit)
    // What_lower_limit[i]: per-component asymmetric lower bound on weight magnitude
    // prevents W[un] from going negative and cancelling nominal control
    float What_lower_limit[MAX_NUM_BASIS];
    
    // Performance recovery parameters
    float lambda_perf;          // [rad/s] State predictor bandwidth
    float tau_v;                // [s] Low-pass filter time constant for v
    
    // Physical limits
    float u_max;                // [Nm or N] Max control torque or force
    float mrac_to_mixer;        // Mixer units per torque/thrust
    float J;                    // Rotational: moment of inertia [kg·m²] | Z-axis: vehicle mass [kg]
    
    float e_deadzone;           // [norm] Error deadzone threshold
    float e_freeze;             // [rad/s] Hard-freeze threshold - ua zeroed and weights frozen above this error
    float e_sat;                // [rad/s] Tanh saturation scale for gradient PBe signal
    float k_e;                  // [-] e-modification: extra leakage proportional to |e|

    // Reserved for future reference model implementation
    float ref_model_bw;         // [rad/s] Reference model bandwidth
    float P_lyap;               // Lyapunov matrix scalar (default 1.0f)
    
} MRAC_AxisConfig_t;

// State structure for an MRAC axis (mutable runtime data)
typedef struct {
    // Reference model states (xm, omega_m)
    float xm;           // Reference state (e.g. desired rate)
    
    // Plant states (x, omega)
    float x;            // Actual plant state (e.g. measured gyro rate)
    
    // Tracking errors (e)
    float e;            // Tracking error (x - xm)
    
    // Regressor vector (Phi array of size MAX_BASIS_FEATURES)
    float Phi[MAX_NUM_BASIS];
    
    // Adaptive weights (Theta array of size MAX_BASIS_FEATURES)
    float Theta[MAX_NUM_BASIS];
    // Low-frequency filtered weight copy for L1-style leakage (tracks Theta with lag)
    float Whatf[MAX_NUM_BASIS];
    
    // Computed nominal control output (u_nom)
    float u_nom;
    
    // Computed adaptive control output (u_ad)
    float u_ad;
    
    // Saturation deficit used for Pseudo Control Hedging
    float u_def;        // u_cmd - u_actual_after_mixer
} MRAC_AxisState_t;

// Main MRAC structure holding all 4 axes
typedef struct {
    MRAC_AxisState_t pitch;
    MRAC_AxisState_t roll;
    MRAC_AxisState_t yaw;
    MRAC_AxisState_t z_rate;
} MRAC_State_t;

typedef struct {
    uint8_t adaptation_on;          // Master adaptive switch
    uint8_t projection_on;          // Weight projection
    uint8_t deadzone_on;            // Gradient deadzone
    uint8_t hard_freeze_on;         // Hard freeze on transient error spike
    uint8_t tanh_saturation_on;     // Tanh soft saturation on PBe
    uint8_t e_modification_on;      // e-modification term
    uint8_t l1_filtering_on;        // L1 adaptive low-pass filter on u_ad
    uint8_t axis_enable_pitch;
    uint8_t axis_enable_roll;
    uint8_t axis_enable_yaw;
} MRAC_FeatureFlags_t;

// ------------------------------------------------------------------------------
// External Globals
// ------------------------------------------------------------------------------
extern MRAC_State_t mrac_state;
extern MRAC_FeatureFlags_t mrac_flags;
extern MRAC_AxisConfig_t mrac_config_pitch;
extern MRAC_AxisConfig_t mrac_config_roll;
extern MRAC_AxisConfig_t mrac_config_yaw;
extern MRAC_AxisConfig_t mrac_config_z;

#include "robot_types.h"

// ------------------------------------------------------------------------------
// 4. Public Function Prototypes
// ------------------------------------------------------------------------------

// Initialize MRAC states, base configurations, and zero the adaptive weights
void MRAC_Init(void);

// Reset all adaptive weights and align reference models with plant state
void MRAC_Reset(void);

// Main periodic MRAC controller computation (Called deeply from StabilizerTask)
void MRAC_Control(const CtrlerTypeDef* current_state);

#endif // MRAC_H
