# BLE radio bring-up + capacity characterization (2026-07-31)

> Moved verbatim out of CLAUDE.md on 2026-08-09 to cut per-turn
> context churn. CLAUDE.md keeps a compact index pointing here.

### New-radio bring-up (2026-07-31) — CLOSED, kept for evidence

**RF LINK CONFIRMED.** `scratchpad/air_loopback.py COM8 COM7` (both modules on the desk,
FC not involved): at **921600 both directions returned `CLEAN`** — the ASCII pattern crossed
byte-exact each way. Every rate below 921600 returned *garbled* bytes, which is the host-vs-
module baud mismatch signature and independently confirms **both module UARTs are at 921600**.
(Received count is ~2× sent: late carry-over from the previous sweep step landing after the
buffer flush — harness artefact, the head is contiguous and correct.)

**What actually fixed it**: on the slave — 发射功率 → 4 → 设置, then 删除已配对列表; on the
master at 921600 — 波特率 921600 → 设置, 发射功率 4 → 设置, 删除已配对列表, 扫描设备,
then **配对设备 targeting `E149F116F5CD` selected from the earlier list**. The slave still
never appeared in any 扫描设备 output, yet the bond took (`已配对数量: 1`) and traffic flows.
**Lesson: a MAC absent from the scan list is not proof it cannot be bonded — pair by MAC
explicitly.**

Historical diagnosis (kept — it is what exonerated the FC). FC side proven over read-only SWD
(majority-voted — the probe returns corrupted single reads, see gotcha below):
- USART3 `CR1=0x201C` UE=1 TE=1, `CR3` DMAT=1; PC10/PC11 mode=ALT **AF7**; `RCC_AHB1ENR.GPIOCEN=1`
- `DMA1_Stream3` `CR=0x08030451` EN=1 dir=mem→periph CHSEL=4, `PAR=0x40004804`(=USART3_DR),
  **EN duty 71.9 %**, NDTR cycling 0..254 → 256 B frames streaming continuously
- `MODER=0x02A105A0 PUPDR=0x0101A55A AFRH=0x00087700 OTYPER=0` (15/15 unanimous)
- **PC10 (TX) high 44.9 %** of 1676 samples → the FC really is driving the line

**WIRING IS CORRECT — do not swap again.** Operator swapped drone-side TX/RX on 2026-07-31;
still dead, so the swap was not the fault. Decisive test (`scratchpad/rx_drive_test.py`):
PC11 has `pull=NONE` yet reads high **100 % of 1131** samples, and **stays high 100 % of 1122
samples against the STM32's internal ~40 kΩ pull-down**. A weak module pull-up would have
collapsed; only a push-pull driver wins. → **PC11 is on the module's TX OUTPUT, which is
powered and idling correctly.** (RMW touched only `PUPDR[23:22]`, restored to `0x0101A55A`,
verified.)

**Baud is conclusively NOT the fault.** `scratchpad/baud_hunt.py` swept `USART3->BRR` across
**11 rates** — 1000000/921600/460800/256000/230400/128000/115200/57600/38400/19200/9600 —
with readback verified at each step and the host listening on COM7. **0 bytes at every one.**
Byte *presence* is baud-agnostic (a mismatched UART returns garbage, never silence), so a
1-D sweep suffices: the dongle emits **nothing at all**, at any FC rate. BRR restored `0x016C`.

**Both directions dead with the wiring right.** `scratchpad/bidir_test.py` with FC held at
921600: downlink 0 B / 0 tails in 3 s; uplink 2560 B written to the dongle left
`UA3RxFrameCnt` at **0** (it had been 97 pre-reboot — that was a *floating-line noise*
artefact, not real traffic, so it is NOT evidence of a working uplink). USART3 `SR` over
~550 samples showed only `TC`/`TXE`, **never `RXNE`/`FE`/`NE`/`ORE`** → literally zero start
bits arrive on PC11. Conclusion: the drone module accepts UART but never transmits RF, and
the dongle never receives RF. Fault is upstream of the FC — pairing/channel/address, RF power
or antenna, or the dongle itself.

**FC FULLY EXONERATED — the radios were unpaired.** Operator moved BOTH modules onto the PC
(dongle direct-USB; drone-side module via a USB-TTL adapter), removing the FC entirely.
The first `air_loopback.py` run (before pairing) crossed **0 bytes in both directions at all 9
datasheet rates**. Two modules on one desk that cannot reach each other is not a firmware,
wiring or baud fault — that is what localised the failure to the BLE bond.

**TWO CH340s are enumerated — the earlier "COM7 is the only USB-serial device" note was WRONG:**
- `COM7` = `USB\VID_1A86&PID_7523\5&1A3A044C&0&1` — **the BLE dongle (master)**, stable across sessions
- the slave (drone-side, on the USB-TTL adapter) **renumbers with the USB socket** — `COM3`
  (`...&0&3`) first, then `COM8` (`...&0&4`) after a replug. **Always re-enumerate before a
  desk test**; do not hardcode it. It is not present at all once the module goes back to the FC.
(COM4/COM5 are Bluetooth SPP, irrelevant.) This also means `stream_log.py:391`'s COM3 default
is stale-but-once-correct, not an invented value — re-check before "fixing" it.

**Seller's docs, `D:\Downloads\038 无线串口调试模块\`** (Yuanxi Technology / 上海远夕智能科技):
- **It is a 2.4 GHz BLE SOC module** (GFSK, 2400–2483.5 MHz, −36…**+4 dBm**), **air cap
  「最大速率 45KB/S」 ≈ 45000 B/s**. This — not 921600 baud — is the real ceiling for the
  goodput ticket. 921600 UART = 92160 B/s, i.e. **2× what the air can carry**; the radio will
  bind first. Still ~8× the old radio's measured 5413 B/s and ~4× UART5's 11520 B/s.
- Device TTL is 3.3 V, **5 V tolerant**; device-side supply 3.3–12 V → the operator's 5 V is fine.
- Ships **pre-paired at 115200**; **green LED lit = paired** (「绿灯亮，说明收发两边已配对」).
- Only these bauds exist: 9600/14400/19200/38400/57600/115200/230400/460800/921600.
- **Every config operation requires physically holding the module's tiny button** (pinhole in
  the case; SIM-eject pin). Tool: `无线串口配置工具v1.0.2.exe`. Video: bilibili BV1jESLBFEhe.
- Factory roles: **PC end = 主机 master, device end = 从机 slave.**
- Tool buttons: 打开串口 / 连接设备 / 读取参数 / 扫描设备 / 配对设备 / 删除已配对列表 / 恢复出厂设置.

**ROOT CAUSE (2026-07-31 21:1x) — the two modules had no BLE bond.** Both interrogated with
`无线串口配置工具v1.0.2.exe` (hold the module's button for EVERY op):
| | MAC | TX power (now) | UART baud (now) |
|---|---|---|---|
| master (dongle, COM7) | **C611912894D3** | 4 dBm | 921600 |
| slave (drone-side) | **E149F116F5CD** | 4 dBm (was 0) | 921600 |

The slave appeared in **none** of four 扫描设备 runs, including those taken with it powered —
yet 配对设备 against its MAC still bonded. RSSI-differencing the scans was a dead end and
produced a demonstrated false positive (`B4E7B31D4D4A`, later revealed as a neighbour's
"EDIFIER BLE"); `76C79AB801E7` (−56 dBm) appeared once and never returned. **Do not pair by
RSSI — pair by MAC.**

**0 dBm vs 4 dBm was NOT the fault** (0 dBm = 1 mW; the 170 m spec figure is at +4 dBm, so
0 dBm still reaches tens of metres). Raised to 4 for margin regardless.

**`omega_u = 921600` costs −0.93 %**: APB1 is 42 MHz, so the closest divisor is `BRR=0x2E` →
**913043 baud**. Within 8N1 tolerance; note it before committing 921600 to the header.

**Host/firmware defects found, NOT yet fixed** (would break `--transport usart3` even once the
wire is right):
1. `ground_station/livewatch/stream_log.py:391` — usart3 data port defaults to **COM3**; the
   dongle is **COM7**.
2. `stream_log.py:116` and `:291` — data port opened at hardcoded **115200**, ignoring the
   usart3 baud, so it would decode garbage at 921600.
3. No `--usart3-baud` CLI flag, though `build_stream_request`/`stream_log_multi` take
   `usart3_baud=115200`.
4. `BSP/usart3.h:19` `USART3_BAUD 115200` feeds the link-budget cap at `API/subscribe.c:531`
   → the firmware would still refuse subscriptions above 10368 B/s.


### Superseded — the dead-link investigation (kept for the evidence)

**REGRESSION 2026-07-31 ~21:5x — link died again after the module was moved back to the FC.**
Module reconnected to USART3; `set_brr.py 921600` wrote `BRR=0x002E` (913043 baud, −0.93 %),
readback 9/9 unanimous, **left set** (that script deliberately does not restore, unlike the
diagnostics). Dashboard PIDs and the config tool were killed first to free COM6/COM7.

FC re-verified good after the move — nothing shifted:
- `MODER=0x02A105A0 OTYPER=0 PUPDR=0x0101A55A AFRH=0x00087700`, all 15/15, PC10/PC11 ALT AF7
- **PC10 high 44.8 %**, **PC11 high 100.0 % at `pull=NONE`** of 1795 samples (was 44.9/100.0
  before the move — module powered, driving, orientation unchanged)
- `bidir_test.py`: downlink **0 B / 0 tails in 3 s**; uplink 2560 B → `UA3RxFrameCnt` 0→0;
  `SR` over 560 samples shows **only `TC`/`TXE`, never `RXNE`/`FE`/`NE`/`ORE`**
- `goodput.py COM7 921600 {10,25} 63`: **0 B** both runs

So the FC is exonerated a second time and the BLE bond that worked on the desk did not survive.
Two candidate causes, in order: (a) the **slave power-cycled** when it moved from the USB-TTL
adapter to the FC's 5 V and did not re-bond; (b) the **master was never power-cycled** after the
config tool wrote 保存自动重连设置/开启自动重连, and the tool was killed with COM7 still open.

**NEXT ACTION — operator, physical**: (1) report whether the **green LED** is lit on each
module (绿灯亮 = 已配对 — this single observation separates "not bonded" from "bonded but not
passing data"); (2) **unplug and replug the dongle's USB** for a cold start. Then re-run
`goodput.py COM7 921600 10 63`. If still dead, put the slave back on the USB-TTL adapter and
re-run `air_loopback.py <slave-COM> COM7` — if the desk test also fails now, the bond is being
lost on every slave power cycle and the pairing must be re-done and re-verified after a
deliberate power cycle.

**Measurement harness, ready the moment RF works**:
`.venv/Scripts/python.exe <scratchpad>/goodput.py COM7 921600 10 63` — measures goodput,
frame rate, byte integrity and **air loss from consecutive seq deltas** (never max−min; that
trap once reported 96 % loss against a true 0.14 %). Instrument needs no reflash: the flashed
image already carries `USART3_THROUGHPUT_TEST=1`, `USART3_TEST_FLOATS=63` → 256 B JustFloat
frames, `float[0]`=counter, `floats[4..]`=fixed ramp `i` for corruption detection
(`TASK/send_data.c:346-402`). Then sweep frame size for the degradation knee, and confirm
whether the 10 ms `Send_Task` tick or `usart3_send()`'s skip-if-busy DMA guard is the limiter
rather than the air link.

**Probe gotcha (new):** the wireless CMSIS-DAP returns **silently corrupted single reads** —
one pass reported `GPIOCEN=0` and `PC11 high 0.0 %`, both false. 15× majority vote gave
`AHB1ENR=0x0030000F` unanimously. Always vote repeated reads; never trust one.
