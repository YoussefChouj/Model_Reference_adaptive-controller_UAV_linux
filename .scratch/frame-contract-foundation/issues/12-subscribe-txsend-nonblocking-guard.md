# What is the send policy when the subscription transmit DMA is still busy?

Type: grilling
Status: open

## Question

`Uart5_Subscribe_TxSend` (`BSP/usart5.c:139`) opens with a bare spin:

```c
while (DMA_GetCurrDataCounter(DMA1_Stream7));
DMA_Cmd(DMA1_Stream7, DISABLE);
while (DMA_GetCmdStatus(DMA1_Stream7) == ENABLE);
```

No non-blocking guard, unlike the USART3 path in `API/subscribe.c:700-707`. Today this is
survivable because subscription traffic is occasional. The redrawn destination makes it
carry **all** telemetry, so every frame goes through that spin and it will stall
`Send_Task` — the same failure shape as the UART4 hang of 2026-07-22, where a busy-wait on
a DMA that never completed took down every telemetry stream at once.

This is a blocker for the migration, not a cleanup, and the policy question has to be
answered before the code is written.

What to settle:

- **Skip, queue, or drop-oldest** when the previous transfer has not drained. The existing
  precedents disagree, deliberately: `usart3_send()` took a non-blocking guard that simply
  skips the cycle, while `Subscribe_StreamTick` already serves **one slot per cycle
  round-robin** and therefore has its own notion of a due-but-unserved slot.
- **Whether a skipped frame is counted.** For a research dataset a silent skip is the
  expensive kind of failure — it looks like data, not like loss. The v2 sequence number
  makes gaps detectable on the host, so the question is whether the firmware also needs a
  counter, or whether host-side gap detection is sufficient given every frame carries `seq`.
- **Whether the round-robin cursor should skip or hold** a slot whose turn came while the
  DMA was busy. Holding preserves per-slot cadence; skipping preserves fairness. The gcc
  harness (`API/tests/test_subscribe_harness.c`) already asserts "busy-DMA skips cleanly"
  over 80 ticks, so whichever is chosen, that assertion has to be re-read and possibly
  re-stated rather than assumed still correct.
- **Whether the same guard belongs on the USART3 transmit path** once the new radio makes
  USART3 the primary transport, or whether `subscribe.c:700-707` already covers it.

Constraint: `usart3_send()`'s existing non-blocking guard is a keeper and so is its static
TX buffer — the buffer was previously a stack local that later calls reused mid-transfer.
Do not undo either while working here.

Recommendation to argue against: mirror `usart3_send()`'s guard — skip the cycle, do not
queue — and rely on the v2 `seq` for host-side gap detection rather than adding a firmware
counter. Queuing introduces buffer ownership questions on a path that has just been proven
sensitive to exactly that (the DMA race fixed on 2026-07-29 was a shared buffer rewritten
under an in-flight transfer), and the whole point of the redraw is that the new link should
have the headroom to make skips rare.
