# Gazebo experiment scenarios

Scenarios are declarative inputs to `sim.runner.run_experiment`.
They are YAML mappings, so experiments can be reviewed and reproduced without editing Python.
The loader is `sim.scenarios_yaml.load_scenario`.
Validation is available separately through `validate_scenario`.

## Required fields

`name` is a non-empty string.
It labels the scenario and appears in the default run-directory name.
`duration_s` is the positive simulated duration in seconds.
The runner executes `int(duration_s / dt)` deterministic control ticks.

## Optional fields

`dt` is the controller period in seconds and defaults to `0.005`.
The default is 200 Hz and matches the firmware control-rate contract.
`seed` is an integer and defaults to `42`.
It is copied to `manifest.json` and `seed.txt`.

`initial_state` is a mapping of optional state values.
Accepted pose fields are `x`, `y`, `z`, `phi`, `theta`, and `psi`.
Accepted velocity fields are `vx`, `vy`, and `vz`.
Accepted body-rate fields are `p`, `q`, and `r`.
`motor_thrust` is a list of four per-motor thrusts in newtons.
Omitted initial values default to zero except the analytic plant's hover motors.

`command` is a mapping with `z`, `roll`, `pitch`, and `yaw`.
`z` is total thrust in newtons.
A `z` value of zero selects canonical hover thrust in the current runner.
Roll, pitch, and yaw values are body-rate commands in radians per second.
A command may be a number, applied from the first tick.
It may instead be `{value: 0.5, start_s: 0.5}` for a delayed step.

`disturbances` is a list of additive command changes.
Every item requires `start_s`, `axis`, and `magnitude`.
The axis must be one of z, roll, pitch, or yaw.
Once started, the disturbance remains active for the rest of the run.

`stop_conditions` is a list of one-key predicate mappings.
`max_abs_phi_deg` stops when absolute roll exceeds the threshold in degrees.
`min_z_m` stops when z falls below the threshold in metres.
The exit reason records the predicate name.

## Hover example

The `hover.yaml` scenario runs for five seconds at 200 Hz.
All rate commands are zero and the runner supplies canonical hover thrust.
The roll safety predicate stops the run beyond 30 degrees.
Its seed is 42.

## Roll-step example

The `step_roll.yaml` scenario also runs for five seconds at 200 Hz.
Its roll command is zero until 0.5 seconds.
At 0.5 seconds it steps to 0.5 radians per second.
Pitch and yaw remain zero while total thrust remains at hover.
This scenario exercises delayed command decoding and the roll axis.

Each successful run writes the normalized scenario to `config.yaml`.
It also writes `trajectory.csv`, `summary.json`, and `manifest.json`.
The sidecars `git_sha.txt`, `urdf_sha.txt`, and `seed.txt` complete the receipt.
Run directories are append-only artifacts and are never overwritten.
