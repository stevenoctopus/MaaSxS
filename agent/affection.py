"""Affection mode: run Daily Dungeons until this week's affection cap.

  1. Affection_Check (pipeline): claim, read "Earned This Week: N/CAP", end on
     the Daily Dungeon list.
  2. runs = ceil((CAP - N) / per_run), run DailyDungeon_Run that many times.
  3. Check again and repeat until capped. Stops if a whole batch earned nothing.
"""
import math

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import give_up, ok, run_times, task_settings
from gui import say
from screen import parse_fraction


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
            total = parse_fraction(node.recognition.best_result.text)
            if total:
                return total
    log(context, "could not read the affection total")
    return None


@AgentServer.custom_action("AffectionFarm")
class AffectionFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = task_settings(argv)
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
                return give_up(context, "Affection", "no affection gained since the last check")
            previous = current
            if not run_times(context, "Affection", "DailyDungeon_Run", runs):
                return False
