"""Split Mirage: once / all gems / all rewards (see track.py).

The score is the wave reached: "Today's Best: Wave ×N" on the menu, and the
wave number under each reward on the track.
"""
import re

from task import Task, task
from track import TrackEvent, farm


def parse_wave(text):
    """'10' -> 10, "Today's Best: Wave x7" -> 7; None if there's no number at the end."""
    m = re.search(r"(\d+)$", text.strip())
    return int(m.group(1)) if m else None


SPLIT_MIRAGE = TrackEvent(
    name="Split Mirage",
    marked="gem",
    parse=parse_wave,
    fmt=lambda v: f"wave {v}",
    values="SplitMirage_TrackValues",
    marker="SplitMirage_GemIcon",
    best="SplitMirage_Best",
    run="SplitMirage_Run",
    close="SplitMirage_CloseToMenu",
)


@task("SplitMirageFarm", SPLIT_MIRAGE.name)
def split_mirage(t: Task):
    farm(t, SPLIT_MIRAGE)
