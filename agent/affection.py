"""Affection mode: run Daily Dungeons until this week's affection cap.

  1. Affection_Check (pipeline): claim, read "Earned This Week: N/CAP", end on
     the Daily Dungeon list.
  2. runs = ceil((CAP - N) / per_run), run DailyDungeon_Run that many times.
  3. Check again and repeat until capped. Stops if a whole batch earned nothing.
"""
import math

from daily_dungeon import log_latest
from screen import parse_fraction
from task import Task, task


def check_affection(t: Task):
    """Run Affection_Check: (current, cap)."""
    detail = t.run("Affection_Check", fail="affection check failed")
    for node in detail.nodes:
        if node.name == "Affection_Read" and node.recognition and node.recognition.hit:
            total = parse_fraction(node.recognition.best_result.text)
            if total:
                return total
    t.fail("could not read the affection total")


@task("AffectionFarm", "Affection")
def affection(t: Task):
    per_run = t.settings["per_run"]
    previous = None
    while True:
        current, cap = check_affection(t)
        runs = math.ceil(max(0, cap - current) / per_run)
        t.log(f"{current}/{cap}, {runs} run(s) needed")
        if runs == 0:
            t.log("weekly cap reached")
            return
        # Safety stop: a whole batch that earned nothing means affection
        # isn't counting, so running more won't help.
        if previous is not None and current <= previous:
            t.give_up("no affection gained since the last check")
        previous = current
        log_latest(t)  # Affection_Check ends on the list
        t.run_times("DailyDungeon_Run", runs)
