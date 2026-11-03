"""Connect to the emulator through MaaFramework and save one screenshot.

    python tools/screenshot.py [name]

Saves to debug/screenshots/<name>.png at MaaFramework's working resolution
(short side 720), which is the resolution templates must be cropped from.
"""
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
        sys.exit("No emulator found. Is LDPlayer running with ADB debugging on?")
    d = devices[0]
    print(f"Using {d.name} at {d.address} ({d.adb_path})")
    ctrl = AdbController(
        adb_path=d.adb_path,
        address=d.address,
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
