"""Record the screen while you (or the bot) play, to see which screens appear.

    python tools/watch.py SESSION [--seconds 300] [--until REGEX]

Saves a screenshot to debug/watch/SESSION/ whenever the screen changes
noticeably, and prints what OCR reads on it. With --until, stops as soon as
OCR finds text matching REGEX (e.g. --until "^Ready$").
"""
import argparse
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from maa.pipeline import JOCR, JRecognitionType
from maa.resource import Resource
from maa.tasker import Tasker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screenshot import ROOT, connect  # noqa: E402

CHANGE = 12.0      # mean abs pixel difference (0-255) on a 90x160 thumbnail


def thumb(img):
    return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (90, 160)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--seconds", type=float, default=300)
    ap.add_argument("--until")
    args = ap.parse_args()

    out = ROOT / "debug" / "watch" / args.session
    out.mkdir(parents=True, exist_ok=True)
    resource = Resource()
    resource.post_bundle(str(ROOT / "assets" / "resource")).wait()
    ctrl = connect()
    tasker = Tasker()
    tasker.bind(resource, ctrl)
    until = re.compile(args.until) if args.until else None

    last, n, t0 = None, 0, time.time()
    while time.time() - t0 < args.seconds:
        img = ctrl.post_screencap().wait().get()
        th = thumb(img)
        if last is not None and float(np.abs(th - last).mean()) < CHANGE:
            time.sleep(0.5)
            continue
        last = th
        n += 1
        stamp = f"{n:03d}_{time.time() - t0:06.1f}s"
        cv2.imwrite(str(out / f"{stamp}.png"), img)
        reco = tasker.post_recognition(JRecognitionType.OCR, JOCR(), img).wait().get()
        texts = [r.text for r in (reco.nodes[0].recognition.all_results if reco.nodes else [])
                 if r.score > 0.8]
        print(f"[{stamp}] " + " | ".join(texts)[:300], flush=True)
        if until and any(until.search(t) for t in texts):
            print(f"Found {args.until!r}, stopping.", flush=True)
            return
    print("Time limit reached.", flush=True)


if __name__ == "__main__":
    main()
