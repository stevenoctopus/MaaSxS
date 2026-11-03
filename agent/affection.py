"""Affection mode: run Daily Dungeons until this week's affection cap.

Flow:
  1. Affection_Check (pipeline): claim, read "Earned This Week: N/CAP", return
     to the Daily Dungeon list.
  2. runs = ceil((CAP - N) / per_run)
  3. Run DailyDungeon_Run that many times.
  4. Check again; if still short, work out the runs needed and repeat until
     the cap is reached. Stops if a whole batch earned no affection.
"""
import json
import math
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from gui import say

TOTAL_RE = re.compile(r"(\d+)\s*/\s*(\d+)")

_context = None  # set when the action starts, so log() can reach the GUI


def log(msg):
    if _context is None:
        print(f"[Affection] {msg}", flush=True)
    else:
        say(_context, "Affection", msg)


def check_affection(context: Context):
    """Run the Affection_Check pipeline; return (current, cap) or None."""
    detail = context.run_task("Affection_Check")
    if detail is None or not detail.status.succeeded:
        log("affection check failed")
        return None
    for node in detail.nodes:
        if node.name == "Affection_Read" and node.recognition and node.recognition.hit:
            m = TOTAL_RE.search(node.recognition.best_result.text)
            if m:
                return int(m.group(1)), int(m.group(2))
    log("could not read the affection total")
    return None


def run_dungeons(context: Context, count: int) -> int:
    """Run DailyDungeon_Run `count` times; returns how many succeeded."""
    done = 0
    for i in range(count):
        if context.tasker.stopping:
            log("stop requested")
            break
        log(f"run {i + 1}/{count}")
        detail = context.run_task("DailyDungeon_Run")
        if detail is None or not detail.status.succeeded:
            log(f"run {i + 1} failed, stopping")
            break
        done += 1
    return done


@AgentServer.custom_action("AffectionFarm")
class AffectionFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        global _context
        _context = context
        param = json.loads(argv.custom_action_param or "{}") or {}
        per_run = int(param.get("per_run", 7))

        previous = None
        while True:
            total = check_affection(context)
            if total is None:
                return False
            current, cap = total
            runs = math.ceil(max(0, cap - current) / per_run)
            log(f"{current}/{cap}, {runs} run(s) needed")
            if runs == 0:
                log("weekly cap reached")
                return True
            # A whole batch of runs that earned nothing means something is
            # wrong (e.g. affection not counting); stop instead of looping.
            if previous is not None and current <= previous:
                log("no affection gained since the last check, stopping")
                return False
            previous = current
            if run_dungeons(context, runs) < runs:
                return False
