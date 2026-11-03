"""Crucible of Hieromon modes:

  once       one run, then claim.
  all_gifts  run until today's highest damage reaches the last gift box on
             the damage track, then claim.
  all        run until it reaches the last reward on the track, then claim.

The track's thresholds change from day to day, so all_gifts/all read the
track first (both halves; it scrolls). Progress is "Highest DMG Today" on the
Crucible menu, the number the track rewards are based on.

Claiming: tapping a claimable reward claims all claimable ones; tapping a
claimed one does nothing; tapping an unreached one opens an info popup. So we
tap the highest reward that today's highest damage has reached.
"""
import json
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from gui import say

VALUE_RE = re.compile(r"^(\d+(?:\.\d+)?)([KMB]?)$")
SCALE = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}

_context = None  # set when the action starts, so log() can reach the GUI


def log(msg):
    if _context is None:
        print(f"[Crucible] {msg}", flush=True)
    else:
        say(_context, "Crucible", msg)


def parse_value(text):
    """'5.51B' -> 5.51e9, '10124760960' -> 10124760960; None if not a number."""
    m = VALUE_RE.match(text.replace(",", "").strip())
    return float(m.group(1)) * SCALE[m.group(2)] if m else None


def fmt(v):
    return f"{v / 1e9:.2f}B"


def xywh(box):
    return tuple(box) if isinstance(box, (list, tuple)) else (box.x, box.y, box.w, box.h)


def screenshot(context: Context):
    return context.tasker.controller.post_screencap().wait().get()


def icon_roi(label_box):
    """The reward icon sits right above its value label."""
    x, y, w, h = xywh(label_box)
    cx = x + w // 2
    return [cx - 40, y - 80, 80, 75]


def read_track(context: Context, image=None):
    """[(value, label_box, is_gift)] for the rewards visible on the track."""
    image = screenshot(context) if image is None else image
    reco = context.run_recognition("Crucible_TrackValues", image)
    out = []
    for r in (reco.filtered_results if reco else []):
        v = parse_value(r.text)
        if v is None:
            continue
        gift = context.run_recognition(
            "Crucible_GiftIcon", image,
            pipeline_override={"Crucible_GiftIcon": {"roi": icon_roi(r.box)}})
        out.append((v, r.box, bool(gift and gift.hit)))
    return sorted(out, key=lambda t: t[0])


def scan_from_end(context: Context, find, max_steps=12):
    """Jump to the right end of the track, then step back towards the start
    until find(view) returns something. view = [(value, label_box, is_gift)].
    Everything we look for is "the highest X", so the first view where X shows
    up has the answer. Returns find's result, or None if the track ran out.
    """
    context.run_task("Crucible_TrackRight")
    context.run_task("Crucible_TrackRight")
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
    if reco and reco.hit:
        return parse_value(reco.best_result.text)
    return None


def claim_rewards(context: Context):
    highest = read_highest_today(context)
    if highest is None:
        log("could not read Highest DMG Today, skipping claim")
        return
    def highest_reached(view):
        reached = [(v, box) for v, box, _ in view if v <= highest]
        return reached[-1] if reached else None

    found = scan_from_end(context, highest_reached)
    if found is None:
        log("no reward reached yet")
        return
    value, box = found
    x, y, w, h = xywh(box)
    log(f"claiming (tapping the {fmt(value)} reward)")
    context.run_action("Crucible_Tap", [x + w // 2 - 20, y - 60, 40, 40],
                       pipeline_override={"Crucible_Tap": {"action": "Click", "post_delay": 2000}})
    context.run_task("Crucible_CloseToMenu")


def find_target(context: Context, mode):
    """Damage needed for this mode, from today's track. None = nothing left to aim for."""
    if mode == "all":
        found = scan_from_end(context, lambda view: view[-1][0] if view else None)
        if found is None:
            log("could not read the damage track")
        else:
            log(f"last reward: {fmt(found)}")
        return found
    # Claimed gifts show a checkmark instead of the gift icon, so no gift
    # icon left on the track means every gift box is already claimed.
    found = scan_from_end(
        context, lambda view: max((v for v, _, g in view if g), default=None))
    log(f"last gift box: {fmt(found)}" if found else "no unclaimed gift box on the track")
    return found


@AgentServer.custom_action("CrucibleFarm")
class CrucibleFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        global _context
        _context = context
        param = json.loads(argv.custom_action_param or "{}") or {}
        mode = param.get("mode", "once")

        target = None
        if mode != "once":
            target = find_target(context, mode)
            if target is None:
                log("nothing left to aim for on today's track")
                claim_rewards(context)
                return True
            log(f"target: {fmt(target)} highest damage today")

        run = 0
        while True:
            if target is not None:
                highest = read_highest_today(context)
                log(f"highest damage today: {fmt(highest) if highest else 'unreadable'}")
                if highest is not None and highest >= target:
                    log("target reached")
                    break
            if context.tasker.stopping:
                log("stop requested")
                return False
            run += 1
            log(f"run {run}")
            detail = context.run_task("Crucible_Run")
            if detail is None or not detail.status.succeeded:
                log(f"run {run} failed")
                return False
            if mode == "once":
                break
        claim_rewards(context)
        log("done")
        return True
