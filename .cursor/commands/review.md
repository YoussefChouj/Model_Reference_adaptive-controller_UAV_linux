# Review

Review the current diff for correctness and safety before I commit.

Focus on embedded / real-time hazards:
- ISR/task races on shared state; blocking calls or heavy float in ISRs; task stack overflow.
- Off-by-one / bounds errors; buffer and frame-size mismatches vs the ground-station protocol version.
- Sign errors and unit-chain mistakes in control loops (rad/s ↔ deg/s ↔ Nm) — anything that changes flight behavior.
- Uninitialized state, non-re-entrancy assumptions, missing volatile on ISR-shared vars.

Output findings **most-severe first**: `file:line → what's wrong → concrete failure scenario → minimal fix`.
Do not rewrite unrelated code. If nothing is wrong, say so plainly.
