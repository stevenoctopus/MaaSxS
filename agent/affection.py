"""Affection mode: run Daily Dungeons until this week's affection cap.

  1. Affection_Check (pipeline): claim, read "Earned This Week: N/CAP", end on
     the Daily Dungeon list.
  2. runs = ceil((CAP - N) / per_run), run DailyDungeon_Run that many times.
  3. Check again and repeat until capped. Stops if a whole batch earned nothing.
"""
import json
import math
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok
from gui import say

TOTAL_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


def log(context: Context, msg: str):
    say(context, "Affection", msg)


def check_affection(context: Context):
    """Run Affection_Check; return (current, cap) or None."""
    detail = context.run_task("Affection_Check")
    if not ok(detail):
        log(context, "affection check failed")
        return None
    for node in detail.nodes:
        if node.name == "Affection_Read" and node.recognition and node.recognition.hit:
            m = TOTAL_RE.search(node.recognition.best_result.text)
            if m:
                return int(m.group(1)), int(m.group(2))
    log(context, "could not read the affection total")
    return None


def run_dungeons(context: Context, count: int) -> bool:
    """Run DailyDungeon_Run `count` times; False if a run fails or a stop is requested."""
    for i in range(count):
        if context.tasker.stopping:
            log(context, "stop requested")
            return False
        log(context, f"run {i + 1}/{count}")
        if not ok(context.run_task("DailyDungeon_Run")):
            log(context, f"run {i + 1} failed")
            return False
    return True


@AgentServer.custom_action("AffectionFarm")
class AffectionFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        per_run = int(param.get("per_run", 7))

        previous = None
        while True:
            total = check_affection(context)
            if total is None:
                return False
            current, cap = total
            runs = math.ceil(max(0, cap - current) / per_run)
            log(context, f"{current}/{cap}, {runs} run(s) needed")
            if runs == 0:
                log(context, "weekly cap reached")
                return True
            # Safety stop: a whole batch that earned nothing means affection
            # isn't counting, so running more won't help.
            if previous is not None and current <= previous:
                log(context, "no affection gained since the last check, stopping")
                return False
            previous = current
            if not run_dungeons(context, runs):
                return False
