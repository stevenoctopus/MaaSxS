"""Split Mirage: once / all gems / all rewards (see track.py).

The score is the wave reached: "Today's Best: Wave ×N" on the menu, and the
wave number under each reward on the track.
"""
import json
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

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


@AgentServer.custom_action("SplitMirageFarm")
class SplitMirageFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        return farm(context, SPLIT_MIRAGE, param.get("mode", "once"))
