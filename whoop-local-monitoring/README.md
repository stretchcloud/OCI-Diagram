# Using a WHOOP 5.0 Without the Subscription — Deep Research & Build Guide

> **What this is.** A thorough, source-verified guide to reading your **own** WHOOP band's
> sensor data directly over Bluetooth Low Energy (BLE) and computing your own health
> metrics locally — with no WHOOP subscription and no WHOOP cloud. It is written for a
> **WHOOP 5.0**, with the fully-documented **4.0** protocol as the reference baseline.
>
> **This is an interoperability / right-to-repair effort, not service theft.** See
> [§2 Legality & ethics](#2-is-this-legal-and-ethical). The short version: reading the raw
> data your own hardware broadcasts is legitimate; cracking WHOOP's cloud login to freeload
> their paid server-side compute is not — and, importantly, is **not needed**, because the
> sensor data lives on the band you own.

---

## 1. TL;DR — the verdict

**Yes, this is achievable, and most of the hard work is already done by the open-source
community.** Three things make it feasible:

1. **The paywall is in the app/cloud, not the band.** The strap itself exposes its sensor
   data over standard and custom BLE services. There is **no proprietary application-layer
   authentication and no payload encryption** guarding the data — integrity is protected by
   plain (non-cryptographic) CRC checksums. (Verified from decompiled-protocol source; see
   [§7](#7-the-whoop-ble-protocol-reference).)
2. **Live heart rate is nearly free.** WHOOP exposes the *standard* Bluetooth Heart Rate
   Service (`0x180D` / measurement `0x2A37`). Any generic BLE heart-rate app can read your
   live BPM + R-R intervals once broadcast is on.
3. **Working code already exists** for local, subscription-free extraction — most maturely
   for the 4.0, and with an active 5.0 effort you can build on.

**The honest catch:** WHOOP's *scores* — Recovery %, Strain (0–21), Sleep stages — are
computed in their cloud with proprietary algorithms. Offline you don't get those exact
numbers. You get the **raw signals** (heart rate, R-R intervals, PPG waveforms,
accelerometer, and *uncalibrated* SpO₂/temperature ADC counts) and rebuild
scientifically-grounded equivalents yourself ([§9](#9-rebuilding-the-health-metrics-locally)).

**Fastest route for your 5.0:** start from [`Sophonbot0/whoop-vault`](https://github.com/Sophonbot0/whoop-vault)
(Python/Linux, live + historical) and/or the multi-platform
[`ryanbr/noop`](https://github.com/ryanbr/noop) / [`OpenStrap/edge`](https://github.com/OpenStrap/edge).
Don't start from scratch. See the [decision tree](#6-the-fastest-path-use-what-exists).

---

## 2. Is this legal and ethical?

This is the same category of work that powers well-known projects like **Gadgetbridge**
(which frees Mi Band / Amazfit / Pebble and dozens of others from vendor cloud apps). The
guiding principles:

**Legitimate (well-supported):**
- Reading the raw sensor stream **from a band you physically own**, locally over BLE.
- Reverse-engineering the BLE protocol **by observing your own device's traffic** to build
  an independent, interoperable client.
- Computing your **own** recovery/strain/sleep analytics from published science.
- Keeping everything local; exporting your own history via WHOOP's export or a GDPR/CCPA
  data-access request.

**Crosses a line (avoid):**
- Decompiling and **redistributing** WHOOP's firmware or app binaries, or copying their
  proprietary scoring algorithms/assets. (Observing your device's protocol is fine;
  republishing their code is not. Gadgetbridge's own guidance: observe the protocol, don't
  redistribute the vendor APK.)
- **Cracking cloud authentication to use WHOOP's paid servers for free** — that is
  freeloading a service, distinct from reading your own hardware. It's also unnecessary.
- Commercializing a WHOOP-compatible clone, or presenting derived numbers as medical-grade.

**The legal backdrop (US; not legal advice):**
- **DMCA §1201(f)** is a *permanent statutory exception* for reverse engineering to achieve
  **interoperability** of an independently-created program. Passively reading telemetry the
  band openly broadcasts arguably doesn't implicate §1201 at all.
- **Reverse engineering for interoperability is established fair use** — *Sega v. Accolade*
  (9th Cir. 1992) and *Sony v. Connectix* (9th Cir. 2000).
- **WHOOP's Terms of Use** prohibit reverse engineering "*except to the extent this
  restriction is expressly prohibited by applicable law*" — and breaching a ToS is a
  contract matter, not a DMCA violation.

**Practical (not legal) risks you are accepting:** WHOOP could terminate your account/
membership, decline warranty/support, or ship a **firmware update that changes the protocol
or adds real authentication** and breaks third-party access. Treat any working setup as
something a future update could disrupt. (See also the [caution in §11](#11-risks-gotchas-and-caution)
about community repos that went offline in mid-2026.)

---

## 3. How WHOOP actually works (and where the paywall sits)

```
   ┌──────────┐   BLE    ┌──────────────┐   HTTPS   ┌──────────────┐
   │  WHOOP   │ ───────► │  Phone app   │ ────────► │ WHOOP cloud  │
   │  strap   │ ◄─────── │ (relay+UI)   │ ◄──────── │ (the algos)  │
   └──────────┘          └──────────────┘           └──────────────┘
     sensors +             pass-through            Recovery / Strain /
   on-device history       + display               Sleep scoring  ◄── the paywall
```

- **Band → phone (BLE):** the strap streams raw, per-second sensor telemetry and stores
  weeks of history in on-board flash. **This link is fully local and is what you'll use.**
- **Phone → cloud (HTTPS):** the app is largely a relay + display; the **proprietary
  scoring runs in WHOOP's cloud**, gated by your subscription.
- **When your subscription lapses:** the band **stops syncing** and no new data/insights
  appear in the app. The hardware you bought effectively goes inert — the classic
  "tethered device bricked without a subscription" scenario. **Export your history
  *before* cancelling** (in-app/web export, limited to ~1 per 24h, or a GDPR/CCPA request);
  post-cancellation access is reported as unreliable.
- **The official developer API** (`developer.whoop.com`, OAuth 2.0) only returns
  **processed summaries** (recovery/sleep/workouts — no raw or continuous data), is
  rate-limited (100/min, 10k/day), reads from the cloud, and **presupposes an active
  membership**. It is *not* a subscription-free path and it cannot give you the raw stream.

---

## 4. What you can and cannot get

| Data | Source | Available offline over BLE? |
|---|---|---|
| Live heart rate (BPM) | Standard HR service `0x2A37` + custom stream | ✅ Yes |
| R-R / inter-beat intervals (ms) | Custom data records | ✅ Yes — **this is the basis for HRV** |
| Raw PPG waveform (green, red/IR ADC) | Custom data records | ✅ Yes (raw ADC counts) |
| 3-axis accelerometer / gravity (g) | Custom data records + IMU stream | ✅ Yes |
| Skin temperature | Custom data records | ⚠️ **Raw ADC only — no on-band calibration to °C** |
| SpO₂ (blood oxygen) | Custom data records (red/IR ADC) | ⚠️ **Raw ADC only — no on-band % ; measured ~once/night** |
| Ambient light, skin-contact quality, battery, events | Custom records/commands | ✅ Yes |
| Weeks of per-second **history** in flash | Batch sync protocol | ✅ Yes |
| **Recovery %** | WHOOP cloud | ❌ No — recompute yourself |
| **Strain (0–21)** | WHOOP cloud | ❌ No — recompute yourself |
| **Sleep stages (light/deep/REM)** | WHOOP cloud | ❌ No — recompute yourself |
| Calibrated HRV / SpO₂% / respiratory rate | WHOOP cloud | ❌ No — recompute yourself |

**The two honest limitations to internalize up front:**

1. **SpO₂ and skin temperature come off the band as *raw, relative ADC counts with no
   calibration curve.*** There is no truthful absolute `%` or `°C` conversion available over
   BLE, and WHOOP only samples them briefly during sleep. Treat them as **trend/relative
   signals**, not clinical values. (Verified from the OpenStrap decoder source, which
   deliberately refuses to fabricate calibrated values.)
2. **Scores are proprietary.** You reproduce the *science and shape* of Recovery/Strain/
   Sleep, not WHOOP's exact numbers. Expect offsets. Validate against how you feel and
   perform, not against the WHOOP app.

---

## 5. Your device: WHOOP 5.0 specifics

The 5.0 (codenamed **"Maverick"** in community work) is **newer and less mature** in the
open-source ecosystem than the 4.0 ("Gen4 / Harvard"), and it adds one meaningful hurdle.

**Standard BLE bonding is required for the rich data (the 4.0 needed none).** This splits
access into two tiers:

- **Tier 1 — bond-free:** Live heart rate (`0x2A37`) and battery (`0x2A19`) are standard
  characteristics readable without pairing. Enough for "watch my live HR."
- **Tier 2 — bonded:** The custom command channel (reportedly service base `fd4b0001-…`,
  characteristics `fd4b0002–0007`) — needed for the historical-data drain, high-frequency
  sync, temperature, and motion — requires your device to be the strap's **bonded** device.

> ⚠️ **The real trade-off (not encryption to "break"):** a WHOOP strap holds a bond with
> **exactly one device at a time.** To bond it to your own app you put the strap in pairing
> mode — **tap it ~5–8 times until the LED is solid blue** — and pair via your OS Bluetooth
> stack (e.g. BlueZ). Doing so **unpairs it from the official WHOOP app.** You're not
> defeating cryptography; you're becoming the legitimate bonded owner. There is still **no
> app-layer auth or payload encryption** beyond the standard BLE bond.

**5.0 status & unknowns (be realistic):**
- `whoop-vault` reports live HR, skin temp, motion/gravity, battery, ~58 event types, **and
  a full historical drain** on firmware **r52 (50.38.1.0)**.
- On that firmware, the real-time IMU stream and raw PPG are reportedly **not emitted even
  when toggled** — a 5.0 limitation vs the 4.0.
- The exact 128-bit 5.0 UUIDs are **single-source / unverified** in public write-ups
  (the `fd4b` prefix is not a confirmed WHOOP Bluetooth-SIG assignment — treat as
  provisional and confirm against `whoop-vault`'s source or your own `nRF Connect` scan).

---

## 6. The fastest path: use what exists

**Do not start from a blank file.** Rank of projects relevant to a 5.0, best first:

| Project | Lang / platform | Models | What you get | Notes |
|---|---|---|---|---|
| [`Sophonbot0/whoop-vault`](https://github.com/Sophonbot0/whoop-vault) | Python + BlueZ (Linux) | **5.0** | Live HR/temp/motion/battery + **full historical drain** → SQLite + local web dashboard | **Best 5.0 starting point.** Built by decompiling the Android app with `jadx`. |
| [`ryanbr/noop`](https://github.com/ryanbr/noop) | Swift (macOS/iOS) + Kotlin (Android) | 4.0 full, **5.0 live HR** | On-device metrics, local SQLite, offline | Large community; deeper 5.0 metrics still experimental |
| [`OpenStrap/edge`](https://github.com/OpenStrap/edge) | Flutter/Dart (iOS/Android) | 4.0 full, **5.0 experimental** | Full consumer app, on-device scoring, no cloud/account | Flagship 4.0 app; 5.0 "detected but not validated" |
| [`OpenStrap/protocol`](https://github.com/OpenStrap/protocol) | Pure Dart | 4.0 (authoritative) | Reusable decoder — the **best protocol reference** | Source of most of [§7](#7-the-whoop-ble-protocol-reference) |
| [`Sivasai2207/WHOOP-Reverse-Engineering-5.0`](https://github.com/Sivasai2207/WHOOP-Reverse-Engineering-5.0) | Kotlin | 5.0 | Minimal 5.0 RE notes | Early stage |
| [`christianmeurer/whoop-reader`](https://github.com/christianmeurer/whoop-reader) | Python (`bleak`) | 4.0 | HR/RR/SpO₂/temp/accel/battery reader | Good, simple `bleak` reference to learn from |
| [`grivera82/whoop-live`](https://github.com/grivera82/whoop-live) | Python | 4.0 (works on 5.0 HR) | Live HR via **standard** HR broadcast | Smallest possible starting point |

**Recommended decision tree:**

```
Do you just want to see LIVE heart rate?
 └─ Yes → Any generic BLE HR app (nRF Connect / a Polar-style app), or the
          starter script in ./starter/ . Enable HR broadcast first (see §7).
 └─ No, I want my full data (history, HRV, my own recovery/strain/sleep):
      Are you comfortable on Linux + Python?
       └─ Yes → Fork Sophonbot0/whoop-vault (5.0). Pair the strap to your machine,
                run the daemon, drain history to SQLite, then layer §9 analytics.
       └─ No / want a phone app → Try ryanbr/noop (5.0 live works today) and watch
                OpenStrap/edge for 5.0 validation. Contribute captures back.
```

---

## 7. The WHOOP BLE protocol (reference)

> **Source & confidence.** The 4.0 details below are **verified from primary source** —
> the `OpenStrap/protocol` Dart decoder (`constants.dart`, `crc.dart`, `records.dart`) and
> the `bWanShiTong` write-up, which everyone cites. The 5.0 uses an analogous structure with
> a different UUID base and some fields not yet emitted; treat 5.0 specifics as provisional.

### 7.1 GATT services & characteristics

**WHOOP 4.0 (verified).** Custom 128-bit service, base `6108xxxx-8d6d-82b8-614a-1c8cb0f8dcc6`:

| UUID | Role | Properties |
|---|---|---|
| `61080001-8d6d-82b8-614a-1c8cb0f8dcc6` | Service | — |
| `61080002-8d6d-82b8-614a-1c8cb0f8dcc6` | `CMD_TO_STRAP` — send commands | Write |
| `61080003-8d6d-82b8-614a-1c8cb0f8dcc6` | `CMD_FROM_STRAP` — command responses | Notify |
| `61080004-8d6d-82b8-614a-1c8cb0f8dcc6` | `EVENTS_FROM_STRAP` — events | Notify |
| `61080005-8d6d-82b8-614a-1c8cb0f8dcc6` | `DATA_FROM_STRAP` — sensor/history data | Notify |
| `61080007-8d6d-82b8-614a-1c8cb0f8dcc6` | `MEMFAULT` — diagnostics/logs | Notify |

Plus the **standard** Heart Rate Service (`0x180D`, measurement `0x2A37`) and Battery
(`0x2A19`). (Note: an older reader listed the service as `61080000-…`; the source-verified
value is `61080001-…`.)

**WHOOP 5.0 (provisional).** Analogous layout in base `fd4b0001-…`: `fd4b0002` (write),
`fd4b0003` (cmd responses), `fd4b0004` (events), `fd4b0005` (data), `fd4b0007` (memfault),
plus standard `0x2A37` and `0x2A19`. **Confirm the full UUIDs with your own scan.**

### 7.2 Frame format & CRC (verified)

Every frame:

```
0xAA │ revision │ length(u16 LE) │ CRC-8(length) │ inner_payload[length] │ CRC-32(inner)
 SOF    0x01        2 bytes          poly 0x07        (4-byte aligned)        zlib/IEEE
```

- **CRC-8**, polynomial **`0x07`**, computed over the 2-byte length field only.
- **CRC-32**, standard **zlib/IEEE** (reflected poly `0xEDB88320`, init `0xFFFFFFFF`, final
  XOR `0xFFFFFFFF` — i.e. exactly Python's `zlib.crc32`), over the padded inner payload.
  (The `bWanShiTong` post quotes the same polynomial `0x04C11DB7` with init 0 / xor-out
  `0xF43F44AC` over a different byte span — mathematically the same CRC-32 family.)

**Inner payload** starts with `packet_type` at `inner[0]`:

| `inner[0]` | Packet type |
|---|---|
| `0x23` | COMMAND |
| `0x24` | COMMAND_RESPONSE |
| `0x28` | REALTIME_DATA |
| `0x2B` | REALTIME_RAW_DATA |
| `0x2F` | HISTORICAL_DATA |
| `0x30` | EVENT |
| `0x31` | METADATA (sync markers) |
| `0x32` | CONSOLE_LOGS |
| `0x33` | REALTIME_IMU_STREAM |
| `0x34` | HISTORICAL_IMU_STREAM |

### 7.3 Command opcodes (inside a `0x23` COMMAND) — the useful subset (verified)

| Opcode | Command | Purpose |
|---|---|---|
| `0x01` | `LINK_VALID` | Link check |
| `0x02` | `GET_MAX_PROTOCOL_VERSION` | Firmware/feature gating |
| `0x03` | `TOGGLE_REALTIME_HR` | Start/stop realtime HR path |
| `0x0A` | `SET_CLOCK` | **Set the strap RTC** — `[u32 epoch LE, u32 pad]`. **Do this first.** |
| `0x0B` | `GET_CLOCK` | Read strap RTC |
| `0x16` | `SEND_HISTORICAL_DATA` | Ask the strap to send stored history |
| `0x17` | `HISTORICAL_DATA_RESULT` | **The per-batch ACK** (echo the 8-byte token) |
| `0x1A` | `GET_BATTERY_LEVEL` | Battery |
| `0x42` | `SET_ALARM_TIME` | On-device haptic alarm |
| `0x60` | `ENTER_HIGH_FREQ_SYNC` | Speed up the history drain |
| `0x6A` | `TOGGLE_IMU_MODE` | Enable IMU stream (`0x33`) |
| `0x6B` | `ENABLE_OPTICAL_DATA` | Enable raw optical data |
| `0x6C` | `TOGGLE_OPTICAL_MODE` | Toggle raw PPG stream |

> **Enabling standard HR broadcast:** the `bWanShiTong` 4.0 write-up documents a category
> byte **`0x0e` with value `01`** to enable/disable the *standard* Heart-Rate-Service
> broadcast (the mechanism `whoop-live` relies on). OpenStrap's own realtime path uses
> `TOGGLE_REALTIME_HR = 0x03`. On the 5.0, enabling the command channel first requires being
> bonded ([§5](#5-your-device-whoop-50-specifics)).

> 🛑 **NEVER send these (they can brick the link, burn the battery, or erase flash):**
> `0x19` FORCE_TRIM (data erase), `0x1D` REBOOT, `0x20` POWER_CYCLE, `0x24`/`0x25`/`0x26`
> firmware-load, `0x9A` PERSISTENT_R21. The source keeps these in an explicit
> `dangerousCmds` "never auto-fire" set — respect it.

### 7.4 The raw data record `R24` — what you actually get per second (verified)

The 1 Hz historical biometric record (`inner[1] == 24`; sibling versions v7/v9/v12/v18/v25).
Offsets are **inner-relative** (inner starts at the `0x2F` packet-type byte; add 4 for
frame-absolute). Field map verified from `records.dart::parseR24`:

| Field | Offset | Type | Notes |
|---|---|---|---|
| `hist_version` | `inner[1]` | u8 | layout version (HR offset varies: v24/v12/v9→17, v18→14, v7→27) |
| `counter` | `inner[3:7]` | u32 LE | record counter |
| `ts_epoch` | `inner[7:11]` | u32 LE | **unix seconds** (garbage until you `SET_CLOCK`) |
| `ts_subsec` | `inner[11:13]` | u16 LE | sub-seconds |
| `hr` | `inner[17]` | u8 | heart rate (bpm); `0` = off-wrist |
| `rr_count` | `inner[18]` | u8 | number of R-R intervals (0–4 accepted) |
| `rr_intervals_ms` | `inner[19…]` | i16 LE × count | **beat-to-beat intervals → HRV** (bounded 200–2500 ms) |
| `ppg_green` | `inner[29]` | u16 LE | raw green-LED PPG ADC |
| `ppg_red_ir` | `inner[31]` | u16 LE | raw red/IR-LED PPG ADC |
| `accel_g` | `inner[36:48]` | 3× f32 LE | gravity/accel vector in g |
| `skin_contact` | `inner[51]` | u8 | contact **quality** (0–198), not a wear flag |
| `spo2_red_raw` | `inner[64]` | u16 LE | **raw** red-channel ADC (no % calibration) |
| `spo2_ir_raw` | `inner[66]` | u16 LE | **raw** IR-channel ADC |
| `skin_temp_raw` | `inner[68]` | u16 LE | **raw** temp ADC (no °C calibration) |
| `ambient_raw` | `inner[70]` | u16 LE | raw ambient-light ADC |

Minimum record length ~89 bytes (some v12 firmware at 88). ~17+ trailing bytes remain
undecoded. **v25** records (5.0-era, PPG-derived) currently decode only time + gravity —
the optical fields are not solved and are deliberately left zero rather than faked.

### 7.5 The sync / history-drain handshake (verified)

No cryptographic handshake — just a bonded connection and a polite request/ACK loop:

1. **Connect → bond** (standard BLE; you'll see an `EVENT` `BLE_BONDED` = id 23).
2. **Raise MTU** (large payloads get chunked at the default 23-byte MTU).
3. **Subscribe** to the notify characteristics (`CMD_FROM`, `EVENTS`, `DATA`).
4. **`SET_CLOCK` (`0x0A`)** with the current unix epoch — **or every timestamp is 1970**.
   Confirmed by an `EVENT` `SET_RTC` (id 16).
5. Optionally **`ENTER_HIGH_FREQ_SYNC` (`0x60`)** to speed the drain.
6. **`SEND_HISTORICAL_DATA` (`0x16`)** → history streams in on `DATA_FROM_STRAP` as `0x2F`
   packets carrying `R24` records.
7. After each batch, a `0x31` **METADATA** marker carries an **8-byte token**; echo it back
   with **`HISTORICAL_DATA_RESULT` (`0x17`)** using an **acknowledged write**, or the strap
   re-sends the same batch forever.
8. Repeat until the `historyComplete` (metadata sub-type 3) marker — then **stop** (don't
   ACK that one). Live high-rate streams and 1 Hz history use **separate sequence ranges**,
   so their ACKs don't collide. The cursor is resumable after a dropped connection.

---

## 8. If you must reverse-engineer the 5.0 yourself

You probably won't need to for basic use — but if you're extending the 5.0 map (e.g. solving
the v25 optical fields), this is the standard workflow. **Only ever target your own band.**

**Phase 1 — Discovery.** Enumerate the GATT database with **nRF Connect for Mobile**
(Android/iOS) or **LightBlue** (iOS/macOS), or `bluetoothctl`/`btmon` on Linux. Record every
service/characteristic UUID and which ones notify. Put the strap in pairing mode first
(tap 5–8× → solid blue).

**Phase 2 — Capture the official app talking to the band.**
- **Android** (easiest): enable **Developer options → "Bluetooth HCI snoop log"**, toggle
  Bluetooth off/on, reproduce the behavior in the WHOOP app, then pull the log:
  ```
  adb bugreport report.zip           # non-root; log inside at FS/data/log/bt/btsnoop_hci.log
  # or, rooted:  adb pull /data/misc/bluetooth/logs/btsnoop_hci.log
  ```
  Open in **Wireshark** (native `btsnoop` support). Filter with `btatt`.
- **iOS:** install Apple's Bluetooth logging profile, capture with **PacketLogger**
  (Additional Tools for Xcode), export to BTSnoop → Wireshark.
- **Over-the-air sniffer** (when you can't instrument the phone): **Sniffle** on a TI
  CC1352/CC26x2 is the best hobbyist option (captures all three advertising channels);
  Nordic **nRF Sniffer** (nRF52840 + Wireshark extcap) also works. Note: a bonded, encrypted
  link can't be decoded OTA without the keys — prefer host-side capture.

**Phase 3 — Read the app's own code (static analysis).** Pull the APK
(`adb shell pm path com.whoop.android` → `adb pull …/base.apk`), decompile with **jadx**
(`jadx -d out base.apk`) and **apktool**. Grep for characteristic UUIDs, packet builders,
opcode constants, CRC helpers, and any `protobuf` classes. (This is how `whoop-vault` and
OpenStrap recovered the 5.0/4.0 maps.) *Observe and reimplement — don't redistribute their
binaries.*

**Phase 4 — Runtime hooks (only if something's opaque).** On a rooted Android, **Frida** +
the ready-made **`optiv/blemon`** script hooks `BluetoothGattCallback` and prints UUID + hex
for every read/write/notify — the fastest way to correlate an in-app action with its packet.
(WHOOP has no payload encryption, so you likely won't need crypto hooks — but the same
technique dumps keys/plaintext if a future firmware adds them.)

**Phase 5 — Model the protocol.** One app action → find its packet → build a command table.
Identify opcode, length, sequence counter, and trailing CRC. High-entropy payloads mean
encryption (go back to Frida). See the excellent public walkthroughs: the *Domyos EL500*
elliptical reverse-engineering, the **BLE CTF**, and the **Gadgetbridge** BT-protocol wiki.

**Phase 6 — Reimplement.** Rebuild the exact sequence: connect → MTU → subscribe (write the
CCCD `0x2902`: `0x0001` notify) → `SET_CLOCK` → commands. **Python `bleak`** is the
cross-platform default (see `./starter/`); `bluepy` (Linux), `noble` (Node), or **Web
Bluetooth** (Chrome/Edge only) are alternatives. Respect any sequence counter and recompute
the CRC on every write.

**Key gotchas:** bond first (5.0 needs it); default **ATT MTU is 23 bytes** (negotiate up,
once per connection) so large frames arrive chunked — reassemble on the `0xAA` SOF + length;
modern Android needs root for a direct snoop pull (use `adb bugreport`).

---

## 9. Rebuilding the health metrics locally

You have raw signals; here's how to turn them into the metrics WHOOP sells — with open,
published methods and maintained Python libraries. (Reproduces the *science*, not WHOOP's
exact formulas.)

**Heart rate from PPG** — band-pass filter → peak-detect → peak-to-peak → BPM. Libs:
**HeartPy** (`heartpy.process`, noise-robust for wrist PPG), **NeuroKit2** (`nk.ppg_process`),
**SciPy**. *Prefer the band's own R-R intervals when present — cleaner than re-detecting.*

**HRV (the backbone of "recovery")** — from the R-R/IBI series compute **RMSSD, SDNN,
pNN50** (time domain) and LF/HF (frequency). **Artifact-correct first** or HRV is garbage.
Libs: **`hrv-analysis`** (Aura — explicit `remove_outliers`/`remove_ectopic_beats`),
**NeuroKit2** (`nk.hrv`), **pyHRV**. The key signal is **RMSSD during deep sleep**,
`ln`-transformed (lnRMSSD).

**Recovery / Readiness (your own score)** — there's no open library that outputs a branded
score, but the recipe is well-established: nightly, compute lnRMSSD, resting HR, respiratory
rate, sleep duration/efficiency, and skin-temp deviation; maintain a **personal rolling
baseline** (7-day for reactivity, ~28–60-day for "normal range"); convert each to a
**z-score vs baseline** (sign it so "good" is positive); weighted-sum → squash to 0–100.
(Marco Altini's lnRMSSD-baseline + coefficient-of-variation method is the canonical open
approach.) **FLIRT** helps generate features if you go the ML route.

**Sleep staging** — **sleep/wake** from the accelerometer via **Cole-Kripke** or **Sadeh**
actigraphy (lib: **pyActigraphy**). **4-stage** (light/deep/REM) needs HR+HRV+motion+clock
features — see **`ojwalch/sleep_classifiers`** (Apple-Watch-derived models + PhysioNet
dataset). Be realistic: consumer multi-stage staging lands around Cohen's κ ≈ 0.4–0.6;
deep/REM boundaries are the least reliable. Treat stage durations as estimates.

**Respiratory rate** — from R-R (respiratory sinus arrhythmia / HF band) or PPG amplitude
modulation. Libs: **NeuroKit2** (`rsp_rate`, `ecg_rsp`, `hrv_rsa`), **HeartPy**
(`breathingrate`). Best at rest/sleep.

**Strain / training load** — from continuous HR: **Banister TRIMP** (duration × mean HR ×
HR-reserve weight) or **Edwards zone TRIMP** (Σ minutes-in-zone × zone weight). These are
~10-line NumPy/pandas formulas (need your HRrest and HRmax). WHOOP Strain is a
log/Borg-scaled 0–21 mapping of cardiovascular load — reproduce the shape with a monotonic
concave map fit to your own distribution.

**SpO₂ & skin temperature** — you only have **raw ADC**. True SpO₂ needs the red/IR
**ratio-of-ratios** `R = (AC_red/DC_red)/(AC_IR/DC_IR)` then an empirical `SpO₂ ≈ A − B·R`
calibration **you'd have to fit yourself against a reference oximeter** — and wrist
reflectance is hard, so treat it as approximate at best. For skin temp, report **nightly
deviation from a personal baseline** (illness/menstrual-cycle signal), never an absolute °C.

**Recommended local stack:** a `bleak` collector → **E2E-PPG** or **NeuroKit2** for
PPG→IBI with signal-quality assessment → **`hrv-analysis`** for artifact correction + HRV/RHR
→ **NeuroKit2** for respiration → **pyActigraphy** + **sleep_classifiers** for sleep →
**pandas** rolling baselines/z-scores → your own Recovery (0–100) and log-mapped Strain
(0–21). Motion-artifact **signal-quality assessment is not optional** — it's what makes
wrist-PPG HRV trustworthy. See [`analytics-stack.md`](./analytics-stack.md) for the full
library list with links.

---

## 10. Suggested build roadmap

1. **Prove live HR (a weekend).** Put the strap in pairing mode, run a generic BLE HR app or
   `./starter/whoop_live_hr.py`. Confirm you see BPM. This validates your Bluetooth stack.
2. **Bond & drain history.** Fork **`whoop-vault`** on a Linux box, pair your 5.0, run the
   daemon, and get weeks of per-second records into SQLite. `SET_CLOCK` first.
3. **Verify the raw fields.** Sanity-check HR against a chest strap; confirm R-R intervals
   look physiological; log the raw SpO₂/temp ADC (don't trust absolute values).
4. **Build the analytics pipeline** ([§9](#9-rebuilding-the-health-metrics-locally)): HRV →
   personal baselines → your Recovery score; TRIMP → your Strain; actigraphy → sleep/wake.
5. **Add a dashboard.** `whoop-vault` ships a local web UI; or pipe SQLite → Grafana (see
   `gowhoop`) → your own panels.
6. **Contribute back.** The 5.0 map has gaps (v25 optical fields, full UUIDs). Sharing clean
   captures helps the whole ecosystem — and keeps *your* setup maintained.

---

## 11. Risks, gotchas, and caution

- **Firmware updates can break everything.** WHOOP could rotate the protocol or add real
  authentication in an update. Consider pinning firmware / declining updates once you have a
  working setup, and keep your own captures.
- **Bonding is exclusive.** Pairing to your own app **unpairs the official app**. You can't
  trivially run both.
- **Raw ADC ≠ calibrated values.** Re-read [§4](#4-what-you-can-and-cannot-get). Don't ship
  "SpO₂ 97%" or "36.8°C" from these — they're relative.
- **`SET_CLOCK` or bust.** Skip it and every record is timestamped 1970.
- **Never auto-fire the destructive opcodes** in [§7.3](#73-command-opcodes-inside-a-0x23-command--the-useful-subset-verified).
- **Community-repo volatility (a real signal).** In mid-2026 several prominent projects went
  offline — the popular iOS `NoopApp/noop` was removed around 2026-07-06 and
  `bWanShiTong/openwhoop` became inaccessible around 2026-08. The **cause is unverified**
  (voluntary vs takedown), but the lesson is concrete: **clone/fork the repos you rely on
  now**, keep local copies, and don't assume any single project will stay up.
- **This may violate WHOOP's ToS** even where it's lawful. The realistic downside is losing
  your account/warranty, not a copyright suit — but decide with eyes open.

---

## 12. Resources

**Protocol & code (clone these now):**
- `OpenStrap/protocol` — https://github.com/OpenStrap/protocol (authoritative 4.0 decoder)
- `OpenStrap/edge` — https://github.com/OpenStrap/edge (flagship app)
- `Sophonbot0/whoop-vault` — https://github.com/Sophonbot0/whoop-vault (**best 5.0 start**)
- `ryanbr/noop` — https://github.com/ryanbr/noop (multi-platform; 5.0 live HR)
- `bWanShiTong/reverse-engineering-whoop-post` — https://github.com/bWanShiTong/reverse-engineering-whoop-post (canonical 4.0 write-up)
- `christianmeurer/whoop-reader` — https://github.com/christianmeurer/whoop-reader (simple Python `bleak` reader)
- `grivera82/whoop-live` — https://github.com/grivera82/whoop-live (live HR via standard broadcast)
- `Sivasai2207/WHOOP-Reverse-Engineering-5.0` — https://github.com/Sivasai2207/WHOOP-Reverse-Engineering-5.0

**Reverse-engineering tooling:** nRF Connect for Mobile · Wireshark · jadx · apktool ·
Frida + `optiv/blemon` · Sniffle (TI CC1352) · Nordic nRF Sniffer · `bleak` (Python) ·
Web Bluetooth · the BLE CTF (`hackgnar/ble_ctf`) · Gadgetbridge BT-protocol wiki.

**Analytics libraries:** HeartPy · NeuroKit2 · `hrv-analysis` (Aura) · pyHRV · pyActigraphy ·
`ojwalch/sleep_classifiers` · E2E-PPG · FLIRT. Full list + links in
[`analytics-stack.md`](./analytics-stack.md).

**Precedent & legal:** Gadgetbridge (gadgetbridge.org) · DMCA §1201(f) · *Sega v. Accolade* ·
*Sony v. Connectix* · EFF Coders' Rights "Reverse Engineering FAQ."

**Official (for reference, not subscription-free):** `developer.whoop.com` (OAuth API,
processed summaries only) · in-app data export · `privacy.whoop.com` (GDPR/CCPA export).

---

---

## 13. Unlocking the paid-tier features (Peak / Life)

WHOOP gates extra metrics behind pricier tiers — Healthspan/WHOOP Age, Health Monitor,
Real-time Stress Monitor (Peak), and ECG, AFib notifications, Blood Pressure Insights (Life,
which ships the **MG** hardware).

**Of those six, exactly one is genuinely impossible on a WHOOP 5.0.** The headline findings:

- **The Peak-tier features are provably software-only** — WHOOP shipped Healthspan to the
  **4.0** via an app update. Nothing about your hardware is the limitation.
- **WHOOP's own AFib detection is PPG-based, not ECG-based** (their trial registration: PPG +
  XGBoost over beat-to-beat intervals). Your 5.0 has every sensor it needs.
- **Only ECG is a real hardware wall** — the MG adds conductive electrodes in the *band*.
  A ~$79 KardiaMobile gives you more, once.
- **Don't try to output blood pressure in mmHg** — single-site wrist PPG structurally can't do it,
  and the 2025 AHA/ACC guideline recommends against cuffless BP entirely.

See **[`premium-metrics.md`](./premium-metrics.md)** for the full analysis, the verified
hardware/software gating table, and how to compute each metric yourself.

---

*See [`starter/whoop_live_hr.py`](./starter/whoop_live_hr.py) for a minimal, dependency-light
live-heart-rate script to confirm your setup, [`analytics-stack.md`](./analytics-stack.md)
for the metric-by-metric library reference, [`premium-metrics.md`](./premium-metrics.md) for
rebuilding the paid-tier features, and [`starter/premium_metrics.py`](./starter/premium_metrics.py)
for working implementations of Baevsky's Stress Index, NightSignal illness detection, the
WHOOP-Age hazard-ratio conversion, VO₂max and the Sleep Regularity Index.*

*Compiled from source-verified reverse-engineering work by the open-source community. Not
affiliated with or endorsed by WHOOP. Not a medical device. For use with hardware you own.*
