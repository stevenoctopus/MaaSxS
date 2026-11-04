"""Crucible of Hieromon: once / all gift boxes / all rewards (see track.py).

The score is damage: "Highest DMG Today" on the menu, and labels like "11.3B"
on the damage track.
"""
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import task_settings
from track import TrackEvent, farm

VALUE_RE = re.compile(r"^(\d+(?:\.\d+)?)([KMB]?)$")
SCALE = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}


def parse_value(text):
    """'5.51B' -> 5.51e9, '10124760960' -> 10124760960; None if not a number."""
    m = VALUE_RE.match(text.replace(",", "").strip())
    return float(m.group(1)) * SCALE[m.group(2)] if m else None


CRUCIBLE = TrackEvent(
    name="Crucible",
    marked="gift box",
    parse=parse_value,
    fmt=lambda v: f"{v / 1e9:.2f}B",
    values="Crucible_TrackValues",
    marker="Crucible_GiftIcon",
    best="Crucible_HighestToday",
    run="Crucible_Run",
    close="Crucible_CloseToMenu",
)


@AgentServer.custom_action("CrucibleFarm")
class CrucibleFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = task_settings(argv)
        return farm(context, CRUCIBLE, param.get("mode", "once"))
