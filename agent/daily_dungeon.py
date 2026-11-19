"""Daily Dungeon, Daily mode: buy extra reward attempts (Dawnium), then run
and claim until no reward attempts are left. Runs below the "Claim grade"
leave without claiming and don't use an attempt.

Starts and ends on the Daily Dungeon list. By default a run leaves its results
without claiming (Affection mode); the Daily case in interface.json switches
the results screen to claiming (see daily_dungeon.json).
"""
import re
import time

from maa.context import Context

from common import ok
from purchase import buy_daily
from screen import parse_fraction, read_fraction, recognize
from task import Task, task


def latest_dungeon(context: Context, image=None):
    """On the list: the latest dungeon's name (the middle card), or None."""
    reco = recognize(context, "DailyDungeon_LatestTitle", image)
    return reco.best_result.text if reco else None


def log_latest(t: Task):
    t.log(f"latest dungeon: {latest_dungeon(t.c) or '?'}")


def buy_attempts(t: Task, wanted: int):
    """On the list: open the latest dungeon's detail and buy attempts so that
    `wanted` have been bought today (a daily total, see agent/purchase.py).
    Stays on the detail screen, so the first run can start from there."""
    # Open the detail screen (same steps as a run, stopping before Match).
    t.run("DailyDungeon_SelectCard", {"DailyDungeon_DifficultySelected": {"next": []}},
          fail="could not open the dungeon")

    # The "+" isn't shown once today's attempts are bought and claimed. While
    # bought ones are unclaimed ("4/2") it shows, but once today's purchases
    # are used up tapping it only shows a toast (DailyDungeon_Buy_Refused).
    if not buy_option_shown(t.c):
        t.log("no extra attempts left to buy today")
    else:
        buy_daily(t, wanted, "DailyDungeon_Buy_Open", "Screen_DungeonDetail",
                  popup="DailyDungeon_Buy", refused="DailyDungeon_Buy_Refused")


def detail_attempts(context: Context, image=None):
    """On the detail screen: reward attempts left ("Daily Reward Attempts:
    3/2" -> 3; "Out of daily reward attempts." -> 0), or None if unreadable."""
    reco = recognize(context, "DailyDungeon_Buy_Open", image)
    if not reco:
        return None
    text = reco.best_result.text
    if re.search(r"Out\s?of", text):
        return 0
    fraction = parse_fraction(text)
    return fraction[0] if fraction else None


def buy_option_shown(context: Context, timeout: int = 4000) -> bool:
    """The attempts line and its "+" show on the detail screen (looks again
    for `timeout` ms while the screen settles)."""
    return ok(context.run_task("DailyDungeon_BuyShown", pipeline_override={
        "DailyDungeon_BuyShown": {"timeout": timeout}}))


def find_node(detail, name):
    return next((n for n in (detail.nodes or []) if n.name == name), None)


def low_grade(detail):
    """The grade if this run left without claiming because it was too low, else None."""
    node = find_node(detail, "DailyDungeon_LowGrade")
    if node is None:
        return None
    reco = node.recognition
    return reco.best_result.text if reco and reco.best_result else "?"


@task("DungeonDaily", "Daily Dungeon")
def dungeon_daily(t: Task):
    log_latest(t)
    # After buying we're on the detail screen: the first run starts there
    # (from the difficulty tab) instead of going back to the list.
    on_detail = t.settings["buy"] > 0
    if on_detail:
        buy_attempts(t, t.settings["buy"])

    run = 0
    while True:
        time.sleep(1.5)  # the count updates a moment after we land
        if on_detail:
            left = t.need(detail_attempts(t.c), "could not read the reward attempts")
        else:
            left = t.need(read_fraction(t.c, "DailyDungeon_ListAttempts"), "could not read the reward attempts")[0]
        t.log(f"{left} reward attempt(s) left")
        if left == 0:
            if on_detail:
                t.run("DailyDungeon_DetailBack", fail="could not get back to the list")
            t.log("done")
            return
        run += 1
        detail = t.step("DailyDungeon_SelectDifficulty" if on_detail else "DailyDungeon_Run", f"run {run}")
        on_detail = False  # a run ends on the list
        grade = low_grade(detail)
        if grade is not None:
            t.log(f"run {run}: grade {grade} is below the minimum, not claimed; running again")
            continue
        # Safety stop: attempts were left but the run didn't claim, so
        # running more won't help.
        if find_node(detail, "DailyDungeon_ClaimConfirm") is None:
            t.give_up(f"run {run} didn't claim its rewards though attempts were left")
