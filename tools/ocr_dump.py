"""Print everything OCR reads in a saved screenshot (or a live one).

    python tools/ocr_dump.py debug/screenshots/x.png [x y w h]
    python tools/ocr_dump.py live [x y w h]

Use it to see the exact text the game shows, before writing `expected`.
"""
import sys
from pathlib import Path

import cv2
from maa.pipeline import JOCR, JRecognitionType
from maa.resource import Resource
from maa.tasker import Tasker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screenshot import ROOT, connect  # noqa: E402


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "live"
    roi = tuple(int(v) for v in sys.argv[2:6]) if len(sys.argv) >= 6 else (0, 0, 0, 0)

    resource = Resource()
    resource.post_bundle(str(ROOT / "assets" / "resource")).wait()
    ctrl = connect()
    tasker = Tasker()
    tasker.bind(resource, ctrl)

    img = ctrl.post_screencap().wait().get() if src == "live" else cv2.imread(src)
    job = tasker.post_recognition(JRecognitionType.OCR, JOCR(roi=roi), img).wait()
    reco = job.get().nodes[0].recognition if job.get().nodes else None
    for r in (reco.all_results if reco else []):
        print(f"{r.score:.2f}  {list(r.box)}  {r.text!r}")


if __name__ == "__main__":
    main()
