"""Daily Dungeon, Daily mode: buy extra reward attempts (Dawnium), then run
and claim until no reward attempts are left. Runs below the "Claim grade"
leave without claiming and don't use an attempt.

Starts and ends on the Daily Dungeon list. By default a run leaves its results
without claiming (Affection mode); CLAIM switches the results screen to
claiming (see daily_dungeon.json).
"""
import json
import time

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok, read_fraction
from gui import say


CLAIM = {"DailyDungeon_Results": {"next": [
    "DailyDungeon_Claim", "DailyDungeon_LeaveResults", "DailyDungeon_LowGrade",
    "DailyDungeon_UnclaimedPrompt"]}}


def log(context: Context, msg: str):
    say(context, "Daily Dungeon", msg)


def buy_attempts(context: Context, wanted: int) -> bool:
    """On the list: open the chosen dungeon's detail, buy attempts so that
    `wanted` have been bought today (attempts already bought today count),
    within the daily purchase limit, and go back to the list."""
    # Open the detail screen (same steps as a run, stopping before Match).
    if not ok(context.run_task("DailyDungeon_SelectCard", pipeline_override={
            "DailyDungeon_DifficultySelected": {"next": []}})):
        log(context, "could not open the dungeon")
        return False

    if not ok(context.run_task("DailyDungeon_Buy_Open")):
        # No popup: today's purchases are used up.
        log(context, "no extra attempts left to buy today")
    else:
        limit = read_fraction(context, "DailyDungeon_Buy_Limit")
        bought, cap = limit if limit else (0, 0)
        count = max(0, min(wanted, cap) - bought)
        if count == 0:
            log(context, f"{bought} attempt(s) already bought today, nothing to buy")
            context.run_task("DailyDungeon_Buy_Cancel")
        else:
            for _ in range(count - 1):  # the slider starts at 1
                context.run_task("DailyDungeon_Buy_More")
            shown = read_fraction(context, "DailyDungeon_Buy_Count")
            if shown is None or shown[0] != count:
                log(context, f"the purchase popup shows {shown}, expected {count}; not buying")
                context.run_task("DailyDungeon_Buy_Cancel")
                return False
            log(context, f"buying {count} extra attempt(s) ({bought} already bought today)")
            if not ok(context.run_task("DailyDungeon_Buy_Purchase")):
                log(context, "purchase failed")
                return False
    return ok(context.run_task("DailyDungeon_DetailBack"))


def find_node(detail, name):
    return next((n for n in (detail.nodes or []) if n.name == name), None)


def low_grade(detail):
    """The grade if this run left without claiming because it was too low, else None."""
    node = find_node(detail, "DailyDungeon_LowGrade")
    if node is None:
        return None
    reco = node.recognition
    return reco.best_result.text if reco and reco.best_result else "?"


@AgentServer.custom_action("DungeonDaily")
class DungeonDaily(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        buy = int(param.get("buy", 0))

        if buy > 0 and not buy_attempts(context, buy):
            return False

        run = 0
        while True:
            time.sleep(1.5)  # the list updates its count a moment after we land
            attempts = read_fraction(context, "DailyDungeon_ListAttempts")
            if attempts is None:
                log(context, "could not read the reward attempts")
                return False
            left = attempts[0]
            log(context, f"{left} reward attempt(s) left")
            if left == 0:
                log(context, "done")
                return True
            if context.tasker.stopping:
                log(context, "stop requested")
                return False
            run += 1
            log(context, f"run {run}")
            detail = context.run_task("DailyDungeon_Run", pipeline_override=CLAIM)
            if not ok(detail):
                log(context, f"run {run} failed")
                return False
            grade = low_grade(detail)
            if grade is not None:
                log(context, f"run {run}: grade {grade} is below the minimum, not claimed; running again")
                continue
            # Safety stop: attempts were left but the run didn't claim, so
            # running more won't help.
            if find_node(detail, "DailyDungeon_ClaimConfirm") is None:
                log(context, f"run {run} didn't claim its rewards, stopping")
                return False
