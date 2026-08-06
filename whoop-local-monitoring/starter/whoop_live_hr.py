#!/usr/bin/env python3
"""
whoop_live_hr.py — minimal live heart-rate reader for a WHOOP strap over BLE.

This is a *confidence check*: it proves your machine can talk to your own band and
read live heart rate + R-R intervals via the STANDARD Bluetooth Heart Rate Service
(0x180D / measurement 0x2A37) — no WHOOP app, no cloud, no subscription. It is the
first rung of the roadmap in ../README.md.

What this DOES:
  - scan for your strap, connect, subscribe to standard HR Measurement (0x2A37),
    parse BPM + R-R intervals, read battery level (0x2A19).

What this does NOT do (by design — see ../README.md):
  - the custom-service history drain, skin temp, motion, or SpO2. That needs the
    bonded command channel (WHOOP 5.0 requires pairing) and the R24 record decoder.
    For the full pipeline, fork Sophonbot0/whoop-vault (5.0) — don't reinvent it.

Notes for WHOOP 5.0:
  - Put the strap in PAIRING mode first: tap it ~5-8 times until the LED is solid
    blue, then let your OS bond to it (bluetoothctl / system Bluetooth settings).
    Bonding to your machine unpairs the official WHOOP app.
  - Live HR broadcast may need to be enabled once over the custom command channel
    (category byte 0x0e = 01 on 4.0; the realtime-HR toggle is opcode 0x03). If you
    connect and see the HR service but get no notifications, that's why — enable it
    via whoop-vault / a write to CMD_TO_STRAP, then re-run this.

Requires:  pip install bleak       (Python 3.9+)
Usage:     python whoop_live_hr.py                 # auto-scan by name
           python whoop_live_hr.py --address AA:BB:CC:DD:EE:FF
           python whoop_live_hr.py --name WHOOP     # override name filter

This script is for use with a band you own. Not affiliated with WHOOP.
"""

import argparse
import asyncio
from contextlib import suppress

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

# Standard SIG UUIDs (16-bit shorthand expanded to the 128-bit base).
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"  # notify: heart rate + RR
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"   # read:   battery %

# WHOOP straps advertise with names containing "WHOOP" (e.g. "WHOOP 5A1B").
DEFAULT_NAME_FILTER = "WHOOP"


def parse_hr_measurement(data: bytes):
    """Decode a Heart Rate Measurement (0x2A37) per the Bluetooth SIG spec.

    Returns (bpm, [rr_ms, ...]). RR intervals are transmitted in units of 1/1024 s
    and converted to milliseconds here — these are the beat-to-beat intervals that
    feed HRV (RMSSD/SDNN); see ../analytics-stack.md.
    """
    if not data:
        return None, []
    flags = data[0]
    hr_is_uint16 = flags & 0x01
    energy_present = (flags >> 3) & 0x01
    rr_present = (flags >> 4) & 0x01

    i = 1
    if hr_is_uint16:
        bpm = int.from_bytes(data[i:i + 2], "little")
        i += 2
    else:
        bpm = data[i]
        i += 1

    if energy_present:
        i += 2  # skip "energy expended" (uint16), not used here

    rr_ms = []
    if rr_present:
        while i + 1 < len(data):
            rr_1024 = int.from_bytes(data[i:i + 2], "little")
            i += 2
            rr_ms.append(round(rr_1024 * 1000.0 / 1024.0, 1))
    return bpm, rr_ms


async def find_strap(address: str | None, name_filter: str):
    if address:
        print(f"Looking for device at {address} ...")
        dev = await BleakScanner.find_device_by_address(address, timeout=20.0)
        if dev is None:
            raise SystemExit(f"No device found at {address}. Is it in range / paired?")
        return dev

    print(f"Scanning for a device whose name contains '{name_filter}' "
          f"(put the strap in pairing mode: tap ~5-8x → solid blue LED) ...")
    dev = await BleakScanner.find_device_by_filter(
        lambda d, ad: (d.name or ad.local_name or "").upper().find(name_filter.upper()) >= 0,
        timeout=25.0,
    )
    if dev is None:
        raise SystemExit(
            "No WHOOP-like device found. Tips: enable Bluetooth, put the strap in "
            "pairing mode, move it closer, or pass --address explicitly."
        )
    return dev


async def main():
    ap = argparse.ArgumentParser(description="Minimal WHOOP live heart-rate reader.")
    ap.add_argument("--address", help="BLE MAC/UUID of the strap (skips scanning).")
    ap.add_argument("--name", default=DEFAULT_NAME_FILTER,
                    help=f"Name substring filter (default: {DEFAULT_NAME_FILTER}).")
    args = ap.parse_args()

    dev = await find_strap(args.address, args.name)
    print(f"Found: {dev.name or '(no name)'}  [{dev.address}]  — connecting ...")

    async with BleakClient(dev) as client:
        print("Connected.\n")

        # One-shot battery read (best-effort — not all firmware exposes it here).
        with suppress(BleakError, Exception):
            batt = await client.read_gatt_char(BATTERY_LEVEL)
            print(f"Battery: {int(batt[0])}%\n")

        def on_hr(_char, data: bytearray):
            bpm, rr = parse_hr_measurement(bytes(data))
            rr_str = f"   R-R: {rr} ms" if rr else ""
            print(f"HR: {bpm:>3} bpm{rr_str}")

        try:
            await client.start_notify(HR_MEASUREMENT, on_hr)
        except BleakError as e:
            raise SystemExit(
                f"Could not subscribe to the standard HR characteristic ({e}).\n"
                "On the WHOOP 5.0 you likely need to (1) bond the strap to this machine "
                "and (2) enable HR broadcast over the custom command channel first. "
                "See ../README.md §5 and §7, or use whoop-vault."
            )

        print("Streaming live heart rate — press Ctrl-C to stop.\n")
        try:
            while True:
                await asyncio.sleep(1.0)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            with suppress(Exception):
                await client.stop_notify(HR_MEASUREMENT)
            print("\nStopped.")


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
