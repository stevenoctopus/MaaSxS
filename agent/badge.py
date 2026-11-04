"""Make the Vendor Booth's tilted "-N%" discount badges readable by OCR.

The badge text is cream on an orange sunburst and tilted ~20 degrees, which
OCR misses about half the time. prep() enlarges a badge crop, turns it level
and keeps only the text: black on white. numpy only (no OpenCV in the
bundled Python).
"""
import math

import numpy as np

SCALE = 2
ANGLE = 22  # degrees the badge text is tilted (rising to the right)


def transform(img: np.ndarray, degrees: float, scale: int) -> np.ndarray:
    """Enlarge `scale` times and rotate counter-clockwise about the centre
    (bilinear), white outside."""
    h, w = img.shape[:2]
    H, W = h * scale, w * scale
    a = math.radians(degrees)
    cos, sin = math.cos(a), math.sin(a)
    ys, xs = np.mgrid[0:H, 0:W].astype(float)
    cx, cy = (W - 1) / 2, (H - 1) / 2
    # For each output pixel, where it comes from in the source (inverse map).
    sx = (cos * (xs - cx) - sin * (ys - cy) + cx) / scale
    sy = (sin * (xs - cx) + cos * (ys - cy) + cy) / scale
    x0, y0 = np.floor(sx).astype(int), np.floor(sy).astype(int)
    fx, fy = (sx - x0)[..., None], (sy - y0)[..., None]
    inside = (x0 >= 0) & (x0 < w - 1) & (y0 >= 0) & (y0 < h - 1)
    x0c, y0c = np.clip(x0, 0, w - 2), np.clip(y0, 0, h - 2)
    src = img.astype(float)
    val = (src[y0c, x0c] * (1 - fx) * (1 - fy) + src[y0c, x0c + 1] * fx * (1 - fy)
           + src[y0c + 1, x0c] * (1 - fx) * fy + src[y0c + 1, x0c + 1] * fx * fy)
    out = np.full((H, W, img.shape[2]), 255.0)
    out[inside] = val[inside]
    return out.astype(np.uint8)


def spans(mask: np.ndarray) -> np.ndarray:
    """Per row: True between the first and last True (fills holes)."""
    any_ = mask.any(axis=1)
    first = np.where(any_, mask.argmax(axis=1), mask.shape[1])
    last = np.where(any_, mask.shape[1] - 1 - mask[:, ::-1].argmax(axis=1), -1)
    cols = np.arange(mask.shape[1])
    return (cols >= first[:, None]) & (cols <= last[:, None])


def prep(crop: np.ndarray) -> np.ndarray:
    """A BGR badge crop -> enlarged, levelled, black text on white."""
    rot = transform(crop, -ANGLE, SCALE)
    b, g, r = [rot[..., i].astype(int) for i in range(3)]
    orange = (r > 200) & (r - b > 90)
    # The badge: the orange area with its holes (the text) filled, along
    # rows and along columns. The text: cream pixels inside it.
    badge = spans(orange) & spans(orange.T).T
    text = badge & (r > 225) & (g > 205) & (b > 150) & (r - b < 90)
    out = np.full_like(rot, 255)
    out[text] = 0
    return out
