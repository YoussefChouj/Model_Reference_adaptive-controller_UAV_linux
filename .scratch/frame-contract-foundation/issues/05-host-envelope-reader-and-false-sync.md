# Does the host envelope reader become the single sync-and-dispatch owner in wave 1?

Type: grilling
Status: open
Blocked by: 04

## Question

`SerialBridge._rx_loop` (`ground_station/comm/serial_bridge.py:1279`) does **not** skip the
payloads of frame types it does not handle — `0x07`, `0x08`, `0x09`–`0x0C`, `0x7F`. It
rescans those bytes one at a time looking for the next sync word, which means a payload
byte pair that happens to read `0xAA 0xBB` can be mistaken for a frame start. Latent
today because those types only appear while a subscription is streaming; live the moment
one runs on the same transport as the fixed frames.

The envelope carries an explicit length, so a reader that owns sync detection can always
skip a payload it does not want. That is the fix, and it is the host-side mirror of the
firmware envelope module.

What to settle:

- Whether wave 1 introduces a host envelope reader that owns sync detection, length
  extraction, CRC verification and dispatch — with the six `_unpack_frame_*` methods
  becoming payload decoders behind it.
- Whether that reader also serves the flexible frames, or only skips them correctly. This
  depends on the answer to [Does the flexible-telemetry path adopt the Frame envelope in
  wave 1?](04-subscribe-adopts-envelope.md), which is why this ticket is blocked on it.
- Which CRC policies the reader must recognise to verify rather than merely skip.
- Whether `_rx_loop`'s resync behaviour on a bad CRC changes. Bad-CRC frames are currently
  dropped silently; for a research dataset it may be worth counting them.

Note the asymmetry to preserve: the uplink has two prefixes, `0xCC 0xDD` for the fixed
9-byte command and `0xCC 0xDE` for the extended length-prefixed one, and `0x21` requests
are accepted on **UART5 only**. USART3 command dispatch stays unwired deliberately — the
radio carries the data plane and has no inbound parser, so do not add one.
