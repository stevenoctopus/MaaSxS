"""Crucible of Hieromon modes:

  once       one run, then claim.
  all_gifts  run until today's highest damage reaches the last gift box on
             the damage track, then claim.
  all        run until it reaches the last reward on the track, then claim.

The track's thresholds change from day to day, so all_gifts/all read the
track first (it scrolls). Progress is "Highest DMG Today" on the Crucible
menu, the number the track rewards are based on.

Claiming: tapping a claimable reward claims all claimable ones; tapping a
claimed one does nothing; tapping an unreached one opens an info popup. So we
tap the highest reward that today's highest damage has reached.
"""
import json
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok
from gui import say

VALUE_RE = re.compile(r"^(\d+(?:\.\d+)?)([KMB]?)$")
SCALE = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}


def log(context: Context, msg: str):
    say(context, "Crucible", msg)


def parse_value(text):
    """'5.51B' -> 5.51e9, '10124760960' -> 10124760960; None if not a number."""
    m = VALUE_RE.match(text.replace(",", "").strip())
    return float(m.group(1)) * SCALE[m.group(2)] if m else None


def fmt(v):
    return f"{v / 1e9:.2f}B"


def screenshot(context: Context):
    return context.tasker.controller.post_screencap().wait().get()


def read_track(context: Context):
    """[(value, label_box, is_gift)] for the rewards visible on the track,
    lowest first. The reward icon sits right above its value label."""
    image = screenshot(context)
    reco = context.run_recognition("Crucible_TrackValues", image)
    out = []
    for r in (reco.filtered_results if reco else []):
        v = parse_value(r.text)
        if v is None:
            continue
        x, y, w, _ = r.box
        icon_roi = [x + w // 2 - 40, y - 80, 80, 75]
        gift = context.run_recognition(
            "Crucible_GiftIcon", image,
            pipeline_override={"Crucible_GiftIcon": {"roi": icon_roi}})
        out.append((v, r.box, bool(gift and gift.hit)))
    return sorted(out, key=lambda t: t[0])


def scan_from_end(context: Context, find, max_steps=12):
    """Jump to the right end of the track, then step back towards the start
    until find(view) returns something (view = read_track()). Everything we
    look for is "the highest X", so the first view where X shows up has the
    answer. Returns find's result, or None if the track ran out.
    """
    context.run_task("Crucible_TrackEnd")
    seen = set()
    for _ in range(max_steps):
        view = read_track(context)
        found = find(view)
        if found is not None:
            return found
        values = {v for v, _, _ in view}
        if values <= seen:  # nothing new: we're at the left end
            return None
        seen |= values
        context.run_task("Crucible_TrackStep")
    return None


def read_highest_today(context: Context):
    reco = context.run_recognition("Crucible_HighestToday", screenshot(context))
    return parse_value(reco.best_result.text) if reco and reco.hit else None


def claim_rewards(context: Context):
    highest = read_highest_today(context)
    if highest is None:
        log(context, "could not read Highest DMG Today, skipping claim")
        return

    def highest_reached(view):
        reached = [(v, box) for v, box, _ in view if v <= highest]
        return reached[-1] if reached else None

    found = scan_from_end(context, highest_reached)
    if found is None:
        log(context, "no reward reached yet")
        return
    value, (x, y, w, _) = found
    log(context, f"claiming (tapping the {fmt(value)} reward)")
    context.run_action("Crucible_Tap", [x + w // 2 - 20, y - 60, 40, 40],
                       pipeline_override={"Crucible_Tap": {"action": "Click", "post_delay": 2000}})
    context.run_task("Crucible_CloseToMenu")


def find_target(context: Context, mode):
    """Damage needed for this mode, from today's track. None = nothing left to aim for."""
    if mode == "all":
        found = scan_from_end(context, lambda view: view[-1][0] if view else None)
        log(context, f"last reward: {fmt(found)}" if found else "could not read the damage track")
        return found
    # Claimed gifts show a checkmark instead of the gift icon, so no gift
    # icon left on the track means every gift box is already claimed.
    found = scan_from_end(
        context, lambda view: max((v for v, _, g in view if g), default=None))
    log(context, f"last gift box: {fmt(found)}" if found else "no unclaimed gift box on the track")
    return found


@AgentServer.custom_action("CrucibleFarm")
class CrucibleFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        mode = param.get("mode", "once")

        target = None
        if mode != "once":
            target = find_target(context, mode)
            if target is None:
                claim_rewards(context)
                return True
            log(context, f"target: {fmt(target)} highest damage today")

        run = 0
        while True:
            if target is not None:
                highest = read_highest_today(context)
                log(context, f"highest damage today: {fmt(highest) if highest else 'unreadable'}")
                if highest is not None and highest >= target:
                    log(context, "target reached")
                    break
            if context.tasker.stopping:
                log(context, "stop requested")
                return False
            run += 1
            log(context, f"run {run}")
            if not ok(context.run_task("Crucible_Run")):
                log(context, f"run {run} failed")
                return False
            if mode == "once":
                break
        claim_rewards(context)
        log(context, "done")
        return True
