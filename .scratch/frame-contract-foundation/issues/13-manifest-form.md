# What does a named manifest declare, and how does a subscription select one?

Type: grilling
Status: open

## Question

The keystone of the redrawn map. The operator's proposal: retire the fixed frames, and
preserve their content as **named manifests** — defaults the flexible subscription can
choose from — so that a known-good set of variables at known rates is never lost, and a
past logging configuration can be recovered by name rather than reconstructed by memory.

The precedent is already in the repo and already shipped: `ground_station/livewatch/
log_frames.md` is a Markdown table that is the source of truth for stream frames and
**needs no rebuild to change**. `ground_station/livewatch/manifests.yaml` and
`params_manifest.json` are the other two data-as-contract artefacts. This ticket decides
whether manifests are that same thing under a name, or something more.

What to settle:

- **What a manifest entry declares.** At minimum a symbol name and a rate. Open: whether it
  also carries a channel name (for VOFA and CSV columns), a unit, an expected array length,
  and a slot assignment — or whether those are derived.
- **Symbol names versus addresses.** Subscription requests are `(address, size, count)`
  tuples resolved from `OBJ/JX_FLY.axf` via DWARF. That is the mechanism's real coupling:
  **every rebuild shifts addresses**, and the .axf must match the flashed image or the
  resolver reads garbage. A manifest written in symbol names survives a rebuild; one
  written in addresses does not. Decide explicitly, and decide when resolution happens.
- **How the fixed frames' content is captured.** Frame A, B, C, ID, bench and OF become six
  manifests, or a smaller number of composed ones. Note this is not a mechanical
  transcription: the fixed frames do **packing and conversion** the subscription path does
  not — Frame C packs rpm as `u16` and angles as float degrees, while a subscription
  returns the raw firmware representation at an address. Decide whether a manifest can
  declare a conversion, or whether the host does it downstream by channel name.
- **Slot budgeting.** `SUBSCRIBE_MAX_SLOTS` is 4, so a manifest cannot ask for more than
  four independent rates. Frames A/C run at ~65 Hz and B at ~16.3 Hz today, which fits —
  but decide whether a manifest declares its slots or whether an allocator assigns them.
- **Whether a manifest is validated against the budget before it is sent.** The firmware
  already refuses over-budget requests with a `0x7F` error, so the host could simply try
  and handle refusal — or it could check first and give a better message.

Hard constraint that must survive: **`SUBSCRIBE_ADDR_SRAM_LO/HI` must never be defined in
`JX_FLY.uvprojx`.** The `#ifndef` guards in `API/subscribe.h` exist so the gcc harness can
retarget the allowlist at host memory; defining them in the firmware build would silently
widen what a host can ask the drone to read. Guarded by
`test_firmware_build_does_not_widen_the_address_allowlist`. A manifest layer must not
become a reason to relax it.

Also settle whether manifests are the place `docs/interfaces.md` and
`wiki/concepts/ground-station-binary-protocol.md` get their content from, or whether those
stay hand-written. Both are already drifted, and a manifest is the natural source.

Recommendation to argue against: symbol names, not addresses, resolved on the host at
subscription time; one manifest per retired fixed frame to start, because that preserves
exactly what exists today and makes the migration diffable; conversions declared in the
manifest rather than hidden on the host, because a conversion that lives only in host code
is the same drift mechanism this whole effort exists to kill.
