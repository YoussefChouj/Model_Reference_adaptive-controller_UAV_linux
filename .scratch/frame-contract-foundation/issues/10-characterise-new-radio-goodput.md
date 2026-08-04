# Characterise the new radio's real goodput and loss

Type: task
Status: open

## Question

Nothing to decide — a number to obtain. It is the first ticket on the redrawn map because
almost every later decision is a rate-budgeting decision, and there is currently no
measurement to budget against.

The replacement BLE module (921600 baud, +4 dBm) arrives 2026-07-31 and goes on **USART3**,
which is currently physically disconnected (the operator cut the wire). 921600 baud is
8x the 115200 that UART5 runs at, but **it is the UART rate to the module, not the
over-air goodput**. The precedent says discount it heavily: the previous radio was
configured at 115200 (11520 B/s line rate) and measured **5413 B/s at 0.14% loss** — 47%
of line rate — with a "keep frames under 104 B" finding attached. Assume a similar
discount and 8x becomes ~4x, which is probably still enough. "Probably" is what this
ticket removes.

The instrument already exists and is already flashed. `TASK/send_data.c` carries
`USART3_THROUGHPUT_TEST = 1` with `USART3_TEST_FLOATS = 63`, so `usart3_send()` emits a
256-byte JustFloat pattern — frame counter, three real attitude floats, then a fixed ramp.
Harmless until now only because the wire was cut. It is exactly a goodput-and-loss
harness, which is why [Retire USART3_THROUGHPUT_TEST](08-usart3-throughput-test-flag.md)
was flipped to depend on this ticket instead of deleting the path.

What to produce:

- **Sustained goodput in B/s** at the new baud, and the **loss rate**, from the frame
  counter in the test pattern. Both under a realistic run length, not a burst.
- **The frame-size relationship.** The old radio degraded above ~104 B per frame. Sweep
  frame size and find where this one degrades, because that number sets the manifest
  slot sizing later.
- **Whether the 10 ms `Send_Task` tick still binds.** 256 B at 115200 is 22.2 ms against a
  10 ms tick, which is why the non-blocking DMA guard drops most frames today. At 921600
  the same frame is 2.8 ms and comfortably inside the tick — so the guard's drop behaviour
  should change character entirely. Confirm it does.
- **Whether `usart3_send()`'s DMA guard is now the limiter rather than the link.** The
  measurement is worthless if it characterises the guard instead of the radio.

Constraints that apply:

- **Requires an explicit operator go-ahead in chat before any flash or target interaction.**
- If a reflash is needed, it goes through
  `python -m ground_station.flashtool.rebuild_and_flash --yes` and nothing else. Never a
  bare UV4 invocation — `<pMon>BIN\CMSIS_AGDI.dll` claims the CMSIS-DAP probe on project
  load and halts a powered core.
- `OBJ/JX_FLY.axf` must end up matching whatever image is running.
- The running dashboard holds COM6 exclusively; close it before any serial capture and
  relaunch afterwards.

Note the current firmware already has everything needed, so this may require **no reflash
at all** — the test path is in the flashed image (`Code=81484`, 2026-07-29). Check that
first; a measurement with no flash is strictly preferable.
