"""Saving screenshots of something that went wrong, to debug/<folder>/, so
they can become saved screens for a test (tests/screens)."""
import struct
import time
import zlib
from pathlib import Path

import numpy as np


def save_png(path, image):
    """Write a BGR screenshot as a PNG (numpy + zlib: the binding has no
    image file I/O)."""
    h, w = image.shape[:2]
    rows = np.ascontiguousarray(image[:, :, 2::-1]).reshape(h, w * 3)  # BGR -> RGB
    raw = b"".join(b"\0" + rows[y].tobytes() for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def keep(folder: str, images, what: str):
    """Save `images` as debug/<folder>/<time>_<what>_<n>.png."""
    path = Path("debug") / folder
    path.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for i, image in enumerate(images):
        save_png(path / f"{stamp}_{what}_{i}.png", image)
