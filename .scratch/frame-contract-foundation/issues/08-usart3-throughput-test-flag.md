# Retire USART3_THROUGHPUT_TEST before the replacement radio is connected

Type: task
Status: open

## Question

Scope-adjacent, ticketed anyway because it is the same failure this map exists to prevent:
source that says one thing while the wire says another, discovered only by reading the
diff. It is independent of every other ticket here.

`TASK/send_data.c` carries `USART3_THROUGHPUT_TEST` set to **1**, with
`USART3_TEST_FLOATS = 63`. `usart3_send()` therefore emits a 256-byte JustFloat test
pattern — a frame counter, three real attitude floats, then a fixed ramp — instead of the
16-byte VOFA+ attitude frame. Its own comment says "TEMPORARY, set back to 0 when done".

**This is in the flashed image** (`Code=81484`, flashed 2026-07-29). Harmless only because
the USART3 wire is physically cut. The replacement BLE module (921600, +4 dBm) was due
around 2026-07-31 and is a drop-in, so the first bring-up will show test patterns, not
telemetry — and will look like a broken radio.

Two further inconsistencies in the same block: the surrounding comment reasons about
23 floats / 96 B / 1.67 ms of margin from an earlier sweep and no longer matches the
constant, and 256 B at 115200 is 22.2 ms against a 10 ms Send_Task tick, so the
non-blocking DMA guard added in the same change drops most frames anyway.

The work:

- Set the flag to 0, or remove the test path entirely, and say which.
- Correct or delete the stale 23-float reasoning in the comment.
- Decide whether this reaches the drone on its own or rides along with the next flash.
  Flashing is fine — props off, crashes are acceptable on this platform — but
  `OBJ/JX_FLY.axf` must end up matching whatever image is running, so it goes through
  `python -m ground_station.flashtool.rebuild_and_flash --yes` and nothing else.
- **Requires an explicit operator go-ahead in chat before any flash.**

Context: `usart3_send()`'s other changes in that commit are keepers — the static TX buffer
(it was a stack local that later calls reused mid-transfer) and the non-blocking DMA guard
that replaced a busy-wait capping the entire send loop, telemetry plus EKF predict, at
~60 Hz instead of 100 Hz. Only the throughput-test path is temporary.
