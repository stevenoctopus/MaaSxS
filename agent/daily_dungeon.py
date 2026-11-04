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

from common import give_up, ok, run_once
from gui import say
from purchase import buy_daily
from screen import hit, read_fraction, screenshot


CLAIM = {"DailyDungeon_Results": {"next": [
    "DailyDungeon_Claim", "DailyDungeon_LeaveResults", "DailyDungeon_LowGrade",
    "DailyDungeon_UnclaimedPrompt"]}}


def log(context: Context, msg: str):
    say(context, "Daily Dungeon", msg)


def buy_attempts(context: Context, wanted: int) -> bool:
    """On the list: open the chosen dungeon's detail, buy attempts so that
    `wanted` have been bought today (a daily total, see agent/purchase.py),
    and go back to the list."""
    # Open the detail screen (same steps as a run, stopping before Match).
    if not ok(context.run_task("DailyDungeon_SelectCard", pipeline_override={
            "DailyDungeon_DifficultySelected": {"next": []}})):
        log(context, "could not open the dungeon")
        return False

    # The "+" isn't shown once today's attempts are bought and claimed.
    # TODO: check what it shows while rewards are still claimable.
    if not buy_option_shown(context):
        log(context, "no extra attempts left to buy today")
    elif buy_daily(context, "Daily Dungeon", wanted, "DailyDungeon_Buy_Open",
                   "DailyDungeon_OnDetail", popup="DailyDungeon_Buy") is None:
        return False
    return ok(context.run_task("DailyDungeon_DetailBack"))


def buy_option_shown(context: Context, wait: float = 4) -> bool:
    """The attempts line and its "+" show on the detail screen (looks again
    for `wait` seconds while the screen settles)."""
    end = time.time() + wait
    while True:
        image = screenshot(context)
        if hit(context, "DailyDungeon_Buy_Open", image) and hit(context, "DailyDungeon_BuyPlus", image):
            return True
        if time.time() >= end:
            return False
        time.sleep(0.5)


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
            run += 1
            detail = run_once(context, "Daily Dungeon", "DailyDungeon_Run", f"run {run}", CLAIM)
            if detail is None:
                return False
            grade = low_grade(detail)
            if grade is not None:
                log(context, f"run {run}: grade {grade} is below the minimum, not claimed; running again")
                continue
            # Safety stop: attempts were left but the run didn't claim, so
            # running more won't help.
            if find_node(detail, "DailyDungeon_ClaimConfirm") is None:
                return give_up(context, "Daily Dungeon", f"run {run} didn't claim its rewards though attempts were left")
