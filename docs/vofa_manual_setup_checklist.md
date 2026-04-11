# VOFA Manual Setup Checklist

Use this once to build your ideal VOFA organization. After saving and closing VOFA, your setup should persist.

## Pre-Setup

*   Close all VOFA windows.
*   Start dashboard.
*   Click `Frame A Workspace` button.
*   Verify UDP local port = `1347`.
*   Verify protocol = `JustFloat`.

## Frame A Workspace

### Create Tabs

*   Tab: `A Status`
*   Tab: `A MRAC Error`
*   Tab: `A MRAC Adaptive`

### Channel Rename Map (Frame A)

*   I0 -> mrac\_pitch\_e
*   I1 -> mrac\_pitch\_u\_ad
*   I2 -> mrac\_roll\_e
*   I3 -> mrac\_roll\_u\_ad
*   I4 -> mrac\_yaw\_e
*   I5 -> mrac\_yaw\_u\_ad
*   I6 -> mrac\_z\_e
*   I7 -> mrac\_z\_u\_ad
*   I8 -> status\_arm
*   I9 -> status\_flymode
*   I10 -> status\_sbus\_lost
*   I11 -> status\_twc\_execute
*   I12 -> status\_twc\_arrived

### Tab-to-Variable Assignment (Frame A)

*   `A Status`: I8, I9, I10, I11, I12
*   `A MRAC Error`: I0, I2, I4, I6
*   `A MRAC Adaptive`: I1, I3, I5, I7

### Plot Readability (Frame A)

*   Enable Y-axis labels.
*   Enable line labels or legend.
*   Use fixed Y range for status tab (for example -0.2 to 2.0).
*   Keep error/adaptive tabs auto Y-range initially, then tune after flight.

## Frame B Workspace

*   Click `Frame B Workspace` button.
*   Verify UDP local port = `1348`.
*   Verify protocol = `JustFloat`.

### Create Tabs (Recommended)

*   Tab: `B Tracking`
*   Tab: `B U_nom`
*   Tab: `B PID Attitude U`
*   Tab: `B PID Rate U`
*   Tab: `B Position U`
*   Tab: `B Path State`
*   Optional Tab: `B Pitch Theta`
*   Optional Tab: `B Roll Theta`
*   Optional Tab: `B Yaw Theta`
*   Optional Tab: `B Z Theta`

### B Core Channel Groups (MAX\_NUM\_BASIS=6)

*   `B Tracking`: I7, I15, I23, I31
*   `B U_nom`: I6, I14, I22, I30
*   `B PID Attitude U`: I34, I37, I40
*   `B PID Rate U`: I43, I46, I49, I52
*   `B Position U`: I55, I58, I61, I64, I67
*   `B Path State`: I68, I69, I70, I71, I72, I73, I74

### B Rename Rules

#### MRAC Weights and References

*   I0-I5 -> mrac\_pitch\_theta\_0 .. mrac\_pitch\_theta\_5
*   I6 -> mrac\_pitch\_u\_nom
*   I7 -> mrac\_pitch\_xm
*   I8-I13 -> mrac\_roll\_theta\_0 .. mrac\_roll\_theta\_5
*   I14 -> mrac\_roll\_u\_nom
*   I15 -> mrac\_roll\_xm
*   I16-I21 -> mrac\_yaw\_theta\_0 .. mrac\_yaw\_theta\_5
*   I22 -> mrac\_yaw\_u\_nom
*   I23 -> mrac\_yaw\_xm
*   I24-I29 -> mrac\_z\_theta\_0 .. mrac\_z\_theta\_5
*   I30 -> mrac\_z\_u\_nom
*   I31 -> mrac\_z\_xm

#### PID Triplets (FB, Des, U)

*   I32-I34 -> pid\_pitch\_FB, pid\_pitch\_Des, pid\_pitch\_U
*   I35-I37 -> pid\_roll\_FB, pid\_roll\_Des, pid\_roll\_U
*   I38-I40 -> pid\_yaw\_FB, pid\_yaw\_Des, pid\_yaw\_U
*   I41-I43 -> pid\_gyrox\_FB, pid\_gyrox\_Des, pid\_gyrox\_U
*   I44-I46 -> pid\_gyroy\_FB, pid\_gyroy\_Des, pid\_gyroy\_U
*   I47-I49 -> pid\_gyroz\_FB, pid\_gyroz\_Des, pid\_gyroz\_U
*   I50-I52 -> pid\_z\_rate\_FB, pid\_z\_rate\_Des, pid\_z\_rate\_U
*   I53-I55 -> pid\_locx\_FB, pid\_locx\_Des, pid\_locx\_U
*   I56-I58 -> pid\_locy\_FB, pid\_locy\_Des, pid\_locy\_U
*   I59-I61 -> pid\_z\_pos\_FB, pid\_z\_pos\_Des, pid\_z\_pos\_U
*   I62-I64 -> pid\_locxs\_FB, pid\_locxs\_Des, pid\_locxs\_U
*   I65-I67 -> pid\_locys\_FB, pid\_locys\_Des, pid\_locys\_U

#### Path State

*   I68 -> path\_active\_path\_mode
*   I69 -> path\_twc\_target\_x
*   I70 -> path\_twc\_target\_y
*   I71 -> path\_twc\_target\_z
*   I72 -> path\_sinusoid\_t\_elapsed
*   I73 -> path\_circle\_theta
*   I74 -> path\_twc\_arrived

### Plot Readability (Frame B)

*   Enable Y-axis labels on all B tabs.
*   Keep only needed variables visible per tab.
*   Use line width >= 2 for critical channels.
*   Use stable color convention per axis:
    *   pitch = red
    *   roll = green
    *   yaw = blue
    *   z = magenta

## Save and Persistence

*   Save workspace after finishing Frame A organization.
*   Save workspace after finishing Frame B organization.
*   Close VOFA normally (do not force kill) so context persists.
*   Reopen with dashboard buttons and verify tabs/names remain as configured.

## Final Validation

*   Frame A button opens local port `1347` and your A tabs.
*   Frame B button opens local port `1348` and your B tabs.
*   No unwanted auto-close when opening the other frame workspace.
*   Variable names are readable and no longer interpreted as unknown placeholders during tuning.