"""Connect to the emulator through MaaFramework and save one screenshot.

    python tools/screenshot.py [name]

Saves to debug/screenshots/<name>.png at MaaFramework's working resolution
(short side 720), which is the resolution templates must be cropped from.
"""
import os
import sys
from pathlib import Path

from maa.controller import AdbController
from maa.toolkit import Toolkit

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "debug" / "screenshots"


def connect():
    Toolkit.init_option(str(ROOT / "debug"))
    devices = Toolkit.find_adb_devices()
    if not devices:
        sys.exit("No emulator found. Is the emulator running with ADB debugging on?")
    # MAASXS_DEVICE picks one when several are running: any part of the name
    # or address, e.g. "LDPlayer", "MuMu" or "emulator-5556".
    want = os.environ.get("MAASXS_DEVICE", "").lower()
    if want:
        devices = [d for d in devices if want in d.name.lower() or want in d.address.lower()]
        if not devices:
            sys.exit(f"No emulator matches MAASXS_DEVICE={want!r}.")
    d = devices[0]
    # MAASXS_ADDRESS overrides the address when the scan reports a stale one
    # (check with: <emulator>/adb.exe devices).
    address = os.environ.get("MAASXS_ADDRESS") or d.address
    print(f"Using {d.name} at {address} ({d.adb_path})")
    ctrl = AdbController(
        adb_path=d.adb_path,
        address=address,
        screencap_methods=d.screencap_methods,
        input_methods=d.input_methods,
        config=d.config,
    )
    if not ctrl.post_connection().wait().succeeded:
        sys.exit("Connection failed.")
    return ctrl


def main():
    import cv2

    name = sys.argv[1] if len(sys.argv) > 1 else "screen"
    ctrl = connect()
    img = ctrl.post_screencap().wait().get()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    cv2.imwrite(str(path), img)
    h, w = img.shape[:2]
    print(f"Saved {path.relative_to(ROOT)} ({w}x{h}), device resolution {ctrl.resolution}")


if __name__ == "__main__":
    main()
