# Telemetry log frames

**This file is the default telemetry frame.** `stream_log` reads it when you run it
with no `--group`/`--symbol` argument, so "just log the usual things" is one command:

```bash
python -m ground_station.livewatch.stream_log --seconds 30 --out logs/run.csv
```

Edit the table, re-run, get different variables. No firmware change, no reflash — the
subscription is sent over the wire at runtime.

## The frame

One row per slot. The firmware has **4 slots**, each ticking at its own rate, so put
fast-moving signals in a fast slot and slow ones in a slow slot instead of paying the
fast rate for everything. Each slot writes its **own CSV** (`run.slot0.csv`, …) because
slots sample at different rates and padding a 5 Hz signal out to 40 Hz would misrepresent
how often it was actually measured.

| Slot | Rate (Hz) | Variables |
| ---- | --------- | --------- |
| 0 | 20 | mrac_state.roll.Theta:6 |
| 1 | 10 | mrac_state.pitch.Theta:6 |
| 2 | 5  | imu_data.rol:3 |

Measured on the drone 2026-07-29: **0 dropped, 0 malformed** on all three slots.

Slots must start at 0 and be contiguous. Drop a row to use fewer slots.

## Writing the Variables column

Comma-separated. Each entry is a **DWARF path** — you name the variable the way the C
code does and never touch an address:

- `s_ekf.x` — a scalar or the start of an array
- `mrac_state.roll.Theta:6` — `:6` means *6 consecutive elements*, one range tuple
- `imu_data.rol:3` — `:N` also sweeps N contiguous **neighbours**, so this gets
  `rol`, `pit`, `yaw` in one tuple

`:N` is how you log an array cheaply: the address is sent **once**, at subscribe time, and
the data frames carry values only. Naming 6 elements individually costs the same on the
wire as `:6`, but `:6` is the honest description.

**`:N` is not bounds-checked.** The symbol resolver will happily resolve `Theta[63]`
even though `MAX_NUM_BASIS` is 6 (`API/mrac.h:85`). Read the header, then write the count.

## Fitting inside the link budget

The firmware refuses (`0x7F`) any subscription whose **total across all slots** exceeds
its share of the transport. That is deliberate: telemetry must never starve the control
frames.

| Transport | Share | Budget |
| --- | --- | --- |
| UART5 (CMSIS-DAP VCP, `--transport uart5`, default) | 20 % of 11520 B/s | **2304 B/s** |
| USART3 (long-range radio, `--transport usart3`) | 90 % | 10368 B/s |

UART5 is the tight one — it is already ~100 % saturated by the existing telemetry frames,
which is why streaming only gets a fifth of it. Cost of a slot:

```
bytes_per_second = (12 + payload_bytes) * 100 / divider       divider = round(80.4 / rate)
```

The 12 B is 6 header + 4 **source timestamp** + 2 CRC16; the 100 is the nominal `Send_Task`
rate the firmware budgets against (it actually runs at ~80 Hz, so the guard errs toward
refusing early).

Each CSV row starts with `t_src_ms, t_host_s, seq`. **`t_src_ms` is the drone's own clock**
(`xTaskGetTickCount`, milliseconds), sampled in the cycle that copied the values — that is
the one to use for system identification. `t_host_s` is arrival time at the PC, smeared by
USB and OS scheduling; it is kept only so you can see that smearing.

### The firmware's guard is more optimistic than the wire — measured 2026-07-29

The 2304 B/s figure is baud arithmetic. It does **not** know that UART5 is already ~100 %
saturated by the existing telemetry frames, so a subscription the firmware happily accepts
can still lose frames when the TX DMA is busy at send time. Measured on the drone:

| Frame | Cost | Result |
| --- | --- | --- |
| 40 / 10 / 5 Hz | 2055 B/s | accepted, but **14 % dropped** on every slot |
| 20 / 10 / 5 Hz | 1580 B/s | **0 dropped, 0 malformed** |
| single slot @ 40 Hz | 1550 B/s | 0 dropped |

So treat **~1600 B/s as the real UART5 ceiling**, not 2304. Losses show up honestly as SEQ
gaps in the `dropped` count — the link degrades loudly, never silently.

Expect achieved rates ~8 % under the requested figure: the stream's own bytes slow
`Send_Task` on a link this full. `seq` is the ground truth for what was actually emitted.

If you need more than ~1600 B/s, move to USART3 once the replacement radio is fitted — it
allows 10368 B/s, 6.5× the headroom — or slow a slot down; halving a rate halves its cost.

## Finding variable names

```bash
python -m ground_station.livewatch names --filter mrac   # search symbols
python -m ground_station.livewatch fields mrac_state.roll  # struct members
```
