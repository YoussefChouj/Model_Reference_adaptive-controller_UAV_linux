# Sim fidelity — what can sim/ decide for the chosen mechanism?

Type: research
Status: open
Blocked by: 04

## Question

Given the chosen mechanism (ticket 04) and the pending physical modeling (actuator dynamics, lift-force-to-PWM curve, moment of inertia — torque stand built, measurements pending): which claims about the mechanism can the current firmware-parity `sim/` decide credibly, and which must wait for better plant modeling or go straight to cautious mode-0 flight tests? Deliverable: a per-claim table (claim → sim-decidable now / needs modeling X / flight-only), so the experiment spec (ticket 07) can sequence honestly.
