"""Crucible of Hieromon: run once, or until a run kills the boss, then claim.

Kill check: a run kills the boss when its Team DMG reaches the top reward on
the damage track (the boss's full HP). The top reward is read from the track
before each run, so it follows boss/tier changes.

Claiming: tapping a claimable reward claims all claimable ones; tapping a
claimed one does nothing; tapping an unreached one opens an info popup. So we
tap the highest reward that today's highest damage has reached.
"""
import json
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

VALUE_RE = re.compile(r"^(\d+(?:\.\d+)?)([KMB]?)$")
SCALE = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}


def log(msg):
    print(f"[Crucible] {msg}", flush=True)


def parse_value(text):
    """'5.51B' -> 5.51e9, '10124760960' -> 10124760960; None if not a number."""
    m = VALUE_RE.match(text.replace(",", "").strip())
    return float(m.group(1)) * SCALE[m.group(2)] if m else None


def fmt(v):
    return f"{v / 1e9:.2f}B"


def screenshot(context: Context):
    return context.tasker.controller.post_screencap().wait().get()


def read_track(context: Context):
    """[(value, box)] for the reward thresholds visible on the track."""
    reco = context.run_recognition("Crucible_TrackValues", screenshot(context))
    out = []
    for r in (reco.filtered_results if reco else []):
        v = parse_value(r.text)
        if v is not None:
            out.append((v, r.box))
    return sorted(out, key=lambda t: t[0])


def read_highest_today(context: Context):
    reco = context.run_recognition("Crucible_HighestToday", screenshot(context))
    if reco and reco.hit:
        return parse_value(reco.best_result.text)
    return None


def top_reward(context: Context):
    """Scroll the track to its end and return the highest threshold."""
    context.run_task("Crucible_TrackRight")
    track = read_track(context)
    return track[-1][0] if track else None


def gift_box(label_box):
    """The gift icon sits right above its value label."""
    x, y, w, h = (label_box if isinstance(label_box, (list, tuple))
                  else (label_box.x, label_box.y, label_box.w, label_box.h))
    cx = x + w // 2
    return [cx - 20, y - 60, 40, 40]


def claim_rewards(context: Context):
    highest = read_highest_today(context)
    if highest is None:
        log("could not read Highest DMG Today, skipping claim")
        return
    log(f"highest damage today: {fmt(highest)}")
    for swipe in ("Crucible_TrackRight", "Crucible_TrackLeft"):
        context.run_task(swipe)
        reached = [(v, box) for v, box in read_track(context) if v <= highest]
        if reached:
            value, box = reached[-1]
            log(f"tapping the {fmt(value)} reward")
            context.run_action("Crucible_Tap", gift_box(box),
                               pipeline_override={"Crucible_Tap": {"action": "Click", "post_delay": 2000}})
            context.run_task("Crucible_CloseToMenu")
            return
    log("no reward reached yet")


def team_damage(detail):
    for node in detail.nodes:
        if node.name == "Crucible_TeamDmg" and node.recognition and node.recognition.hit:
            return parse_value(node.recognition.best_result.text)
    return None


@AgentServer.custom_action("CrucibleFarm")
class CrucibleFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        until_kill = bool(param.get("until_kill", False))

        run = 0
        while True:
            if context.tasker.stopping:
                log("stop requested")
                return False
            top = top_reward(context)
            run += 1
            log(f"run {run}" + (f" (kill = {fmt(top)})" if top else ""))
            detail = context.run_task("Crucible_Run")
            if detail is None or not detail.status.succeeded:
                log(f"run {run} failed")
                return False
            dmg = team_damage(detail)
            log(f"team damage: {fmt(dmg) if dmg else 'unreadable'}")
            killed = dmg is not None and top is not None and dmg >= top
            if killed:
                log("boss killed")
            if not until_kill or killed:
                break
        claim_rewards(context)
        log("done")
        return True
